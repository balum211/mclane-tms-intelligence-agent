"""Freight cost and margin tools: lane profitability, margin outliers, accessorial leakage, fuel recovery."""

from __future__ import annotations

from tms_agent.db import get_backend
from tms_agent.tools.common import fail, ok, run, safe, window


@safe
def get_lane_profitability(days: int = 30, min_loads: int = 5, sort: str = "worst", limit: int = 10) -> dict:
    """Margin, cost per mile and empty-mile ratio by lane (origin DC -> destination state).

    Args:
        days: Lookback window in days.
        min_loads: Ignore lanes with fewer completed loads than this.
        sort: 'worst' (lowest margin first) or 'best'.
        limit: Max lanes.

    Returns:
        Lanes with loads, revenue, cost, margin, margin_pct, revenue/cost per mile and empty_mile_pct.
    """
    if sort not in ("worst", "best"):
        return fail("sort must be 'worst' or 'best'")
    start, end = window(days)
    sql = f"""
    SELECT lane, origin_dc_id, dest_region_state, COUNT(*) AS loads,
           SUM(total_revenue) AS revenue, SUM(total_cost) AS cost, SUM(margin) AS margin,
           1.0 * SUM(margin) / NULLIF(SUM(total_revenue), 0) AS margin_pct,
           1.0 * SUM(total_revenue) / NULLIF(SUM(total_miles), 0) AS revenue_per_mile,
           1.0 * SUM(total_cost) / NULLIF(SUM(total_miles), 0) AS cost_per_mile,
           1.0 * SUM(empty_miles) / NULLIF(SUM(total_miles), 0) AS empty_mile_pct,
           AVG(stop_count) AS avg_stops,
           1.0 * SUM(CASE WHEN carrier_type = 'PRIVATE_FLEET' THEN 0 ELSE 1 END) / COUNT(*) AS outsourced_pct
    FROM {{p}}v_load_profitability
    WHERE load_date BETWEEN :start AND :end
    GROUP BY lane, origin_dc_id, dest_region_state
    HAVING COUNT(*) >= {int(min_loads)}
    ORDER BY margin_pct {"ASC" if sort == "worst" else "DESC"}
    LIMIT {int(limit)}
    """
    network = run("""
        SELECT COUNT(*) AS loads, 1.0 * SUM(margin) / NULLIF(SUM(total_revenue), 0) AS margin_pct,
               1.0 * SUM(total_cost) / NULLIF(SUM(total_miles), 0) AS cost_per_mile,
               1.0 * SUM(empty_miles) / NULLIF(SUM(total_miles), 0) AS empty_mile_pct
        FROM {p}v_load_profitability WHERE load_date BETWEEN :start AND :end
    """, {"start": start, "end": end})
    return ok(run(sql, {"start": start, "end": end}), network_benchmark=network[0], window=[str(start), str(end)])


@safe
def get_load_margin_outliers(days: int = 14, limit: int = 15) -> dict:
    """The lowest-margin completed loads with their cost lines, to explain where money was lost.

    Args:
        days: Lookback window in days.
        limit: Max loads.

    Returns:
        Loads sorted by margin ascending, each with a cost breakdown by cost_type.
    """
    start, end = window(days)
    loads = run(f"""
        SELECT load_id, load_date, lane, carrier_id, carrier_type, equipment_type, stop_count,
               loaded_miles, empty_miles, total_revenue, total_cost, margin, margin_pct
        FROM {{p}}v_load_profitability WHERE load_date BETWEEN :start AND :end
        ORDER BY margin ASC LIMIT {int(limit)}
    """, {"start": start, "end": end})
    if loads:
        ids = ", ".join(f"'{r['load_id']}'" for r in loads)
        lines = run(f"SELECT load_id, cost_type, SUM(amount) AS amount FROM {{p}}load_costs "
                    f"WHERE load_id IN ({ids}) GROUP BY load_id, cost_type", max_rows=1000)
        by_load: dict[str, dict] = {}
        for ln in lines:
            by_load.setdefault(ln["load_id"], {})[ln["cost_type"]] = ln["amount"]
        for r in loads:
            r["cost_breakdown"] = by_load.get(r["load_id"], {})
    return ok(loads, window=[str(start), str(end)])


@safe
def get_accessorial_leakage(days: int = 60) -> dict:
    """Detention and lumper costs incurred versus accessorials billed to customers.

    Detention is billable after 120 minutes free time at $75/hr. Leakage = billable detention
    that never made it to an invoice, plus lumper fees paid to carriers that were not recovered.

    Args:
        days: Lookback window in days.

    Returns:
        Per customer: billable detention, detention billed, unbilled detention, lumper paid,
        and total recoverable revenue, sorted by recoverable revenue.
    """
    start, end = window(days)
    rows = run("""
        WITH det AS (
            SELECT loc.customer_id, SUM(s.detention_minutes) / 60.0 * 75 AS billable_detention,
                   SUM(COALESCE(i.detention_billed, 0)) AS detention_billed
            FROM {p}stops s
            JOIN {p}locations loc ON loc.location_id = s.location_id
            LEFT JOIN {p}invoices i ON i.order_id = s.order_id
            WHERE s.delivery_date BETWEEN :start AND :end AND s.detention_minutes > 0
            GROUP BY loc.customer_id
        ), lumper AS (
            SELECT o.customer_id, SUM(lc.amount * 1.0 / l.stop_count) AS lumper_paid
            FROM {p}load_costs lc
            JOIN {p}loads l ON l.load_id = lc.load_id
            JOIN {p}orders o ON o.load_id = l.load_id
            WHERE lc.cost_type = 'LUMPER' AND lc.cost_date BETWEEN :start AND :end
            GROUP BY o.customer_id
        )
        SELECT cu.customer_id, cu.customer_name, cu.segment,
               COALESCE(det.billable_detention, 0) AS billable_detention_usd,
               COALESCE(det.detention_billed, 0) AS detention_billed_usd,
               COALESCE(det.billable_detention, 0) - COALESCE(det.detention_billed, 0) AS unbilled_detention_usd,
               COALESCE(lumper.lumper_paid, 0) AS lumper_paid_usd
        FROM {p}customers cu
        LEFT JOIN det ON det.customer_id = cu.customer_id
        LEFT JOIN lumper ON lumper.customer_id = cu.customer_id
        WHERE det.customer_id IS NOT NULL OR lumper.customer_id IS NOT NULL
    """, {"start": start, "end": end})
    for r in rows:
        r["recoverable_usd"] = round(float(r["unbilled_detention_usd"]) + float(r["lumper_paid_usd"]), 2)
        billable = float(r["billable_detention_usd"])
        r["detention_capture_rate"] = round(float(r["detention_billed_usd"]) / billable, 3) if billable else None
    rows.sort(key=lambda r: -r["recoverable_usd"])
    total = round(sum(r["recoverable_usd"] for r in rows), 2)
    days_n = (end - start).days + 1
    return ok(rows, window=[str(start), str(end)], total_recoverable_usd=total,
              annualized_recoverable_usd=round(total * 365 / days_n, 0))


@safe
def get_fuel_surcharge_recovery(weeks: int = 10, dc_id: str = "") -> dict:
    """Weekly fuel cost versus fuel surcharge billed, with the DOE diesel price for context.

    Args:
        weeks: Number of recent weeks.
        dc_id: Optional origin DC filter.

    Returns:
        Weekly rows: fuel_cost, fuel_surcharge_billed, recovery_pct and avg diesel price per gallon.
    """
    b = get_backend()
    start, end = window(weeks * 7)
    wk = b.week("l.load_date")
    rows = run(f"""
        WITH fc AS (
            SELECT load_id, SUM(amount) AS fuel_cost FROM {{p}}load_costs WHERE cost_type = 'FUEL' GROUP BY load_id
        ), fs AS (
            SELECT load_id, SUM(revenue_fuel_surcharge) AS fsc FROM {{p}}orders GROUP BY load_id
        )
        SELECT {wk} AS week_start, COUNT(*) AS loads, SUM(fc.fuel_cost) AS fuel_cost,
               SUM(fs.fsc) AS fuel_surcharge_billed,
               1.0 * SUM(fs.fsc) / NULLIF(SUM(fc.fuel_cost), 0) AS recovery_pct
        FROM {{p}}loads l JOIN fc ON fc.load_id = l.load_id JOIN fs ON fs.load_id = l.load_id
        WHERE l.load_date BETWEEN :start AND :end AND l.load_status = 'COMPLETED'
          AND (:dc_id = '' OR l.origin_dc_id = :dc_id)
        GROUP BY {wk} ORDER BY week_start
    """, {"start": start, "end": end, "dc_id": dc_id.upper()})
    fuel = run("""
        SELECT week_start_date, padd_region, diesel_price_per_gal FROM {p}fuel_prices
        WHERE week_start_date BETWEEN :start AND :end ORDER BY week_start_date, padd_region
    """, {"start": start, "end": end})
    return ok({"weekly": rows, "doe_diesel": fuel}, window=[str(start), str(end)],
              note="Surcharge is billed from the DOE index with a 2 week lag; recovery drops when diesel spikes.")


@safe
def get_cost_breakdown(days: int = 30, dc_id: str = "") -> dict:
    """Cost per mile by cost type, split private fleet versus outside carriers.

    Args:
        days: Lookback window in days.
        dc_id: Optional origin DC filter.

    Returns:
        Rows of carrier_type, cost_type, total amount and cost per mile.
    """
    start, end = window(days)
    rows = run("""
        WITH miles AS (
            SELECT c.carrier_type, SUM(l.total_miles) AS miles
            FROM {p}loads l JOIN {p}carriers c ON c.carrier_id = l.carrier_id
            WHERE l.load_status = 'COMPLETED' AND l.load_date BETWEEN :start AND :end
              AND (:dc_id = '' OR l.origin_dc_id = :dc_id)
            GROUP BY c.carrier_type
        )
        SELECT c.carrier_type, lc.cost_type, SUM(lc.amount) AS amount,
               1.0 * SUM(lc.amount) / NULLIF(MAX(m.miles), 0) AS cost_per_mile
        FROM {p}load_costs lc
        JOIN {p}loads l ON l.load_id = lc.load_id
        JOIN {p}carriers c ON c.carrier_id = l.carrier_id
        JOIN miles m ON m.carrier_type = c.carrier_type
        WHERE l.load_status = 'COMPLETED' AND l.load_date BETWEEN :start AND :end
          AND (:dc_id = '' OR l.origin_dc_id = :dc_id)
        GROUP BY c.carrier_type, lc.cost_type
        ORDER BY c.carrier_type, amount DESC
    """, {"start": start, "end": end, "dc_id": dc_id.upper()})
    return ok(rows, window=[str(start), str(end)])
