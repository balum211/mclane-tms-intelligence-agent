"""Service exception tools: late deliveries, detention, at-risk loads, reefer excursions."""

from __future__ import annotations

from tms_agent.db import get_backend
from tms_agent.tools.common import SEVERITY_RANK, as_of, fail, ok, run, safe, window

_DOW = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


@safe
def get_open_exceptions(min_severity: str = "MEDIUM", dc_id: str = "", limit: int = 25) -> dict:
    """Lists unresolved operational exceptions (late, detention, reefer, HOS risk, shortages...).

    Args:
        min_severity: LOW, MEDIUM, HIGH or CRITICAL. Returns this severity and above.
        dc_id: Optional origin DC filter, e.g. 'DC04'. Empty for all DCs.
        limit: Max rows (default 25).

    Returns:
        Open exceptions sorted by severity then time, with load, carrier, driver and customer context.
    """
    sev = min_severity.upper()
    if sev not in SEVERITY_RANK:
        return fail("min_severity must be LOW, MEDIUM, HIGH or CRITICAL")
    allowed = [s for s, r in SEVERITY_RANK.items() if r >= SEVERITY_RANK[sev]]
    in_list = ", ".join(f"'{s}'" for s in allowed)
    sql = f"""
    SELECT e.exception_id, e.exception_type, e.severity, e.event_ts, e.root_cause, e.description,
           e.cost_impact, e.load_id, l.origin_dc_id, l.carrier_id, l.driver_id, l.load_status,
           cu.customer_name, loc.location_name
    FROM {{p}}exceptions e
    JOIN {{p}}loads l ON l.load_id = e.load_id
    LEFT JOIN {{p}}stops s ON s.stop_id = e.stop_id
    LEFT JOIN {{p}}locations loc ON loc.location_id = s.location_id
    LEFT JOIN {{p}}customers cu ON cu.customer_id = loc.customer_id
    WHERE e.resolved_flag = FALSE AND e.severity IN ({in_list})
      AND (:dc_id = '' OR l.origin_dc_id = :dc_id)
    ORDER BY CASE e.severity WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END, e.event_ts DESC
    LIMIT {int(limit)}
    """
    rows = run(sql, {"dc_id": dc_id.upper()})
    return ok(rows, as_of_date=as_of().isoformat(), count=len(rows))


@safe
def get_late_delivery_summary(days: int = 30, group_by: str = "customer") -> dict:
    """On-time delivery performance and late-stop counts over the last N days.

    Args:
        days: Lookback window in days ending at the dataset as-of date.
        group_by: One of customer, dc, carrier, day_of_week, dc_day_of_week, root_cause.

    Returns:
        Rows with stops, on_time_pct, late_stops, avg_minutes_late (late stops only) and, for
        customers, the contracted on_time_target_pct and estimated late penalties.
    """
    start, end = window(days)
    b = get_backend()
    if group_by == "root_cause":
        sql = """
        SELECT e.root_cause, COUNT(*) AS late_exceptions,
               AVG(s.minutes_late) AS avg_minutes_late, SUM(e.cost_impact) AS est_cost_impact
        FROM {p}exceptions e JOIN {p}stops s ON s.stop_id = e.stop_id
        WHERE e.exception_type = 'LATE_ARRIVAL' AND e.event_date BETWEEN :start AND :end
        GROUP BY e.root_cause ORDER BY late_exceptions DESC
        """
        return ok(run(sql, {"start": start, "end": end}), window=[str(start), str(end)])
    dims = {
        "customer": ("v.customer_id, v.customer_name, cu.on_time_target_pct, cu.late_penalty_per_stop",
                     "v.customer_id, v.customer_name, cu.on_time_target_pct, cu.late_penalty_per_stop"),
        "dc": ("v.origin_dc_id", "v.origin_dc_id"),
        "carrier": ("v.carrier_id", "v.carrier_id"),
        "day_of_week": (f"{b.dow('v.delivery_date')} AS dow", f"{b.dow('v.delivery_date')}"),
        "dc_day_of_week": (f"v.origin_dc_id, {b.dow('v.delivery_date')} AS dow",
                           f"v.origin_dc_id, {b.dow('v.delivery_date')}"),
    }
    if group_by not in dims:
        return fail(f"group_by must be one of {sorted(list(dims) + ['root_cause'])}")
    select, group = dims[group_by]
    sql = f"""
    SELECT {select}, COUNT(*) AS stops,
           1.0 * SUM(CASE WHEN v.on_time_flag THEN 1 ELSE 0 END) / COUNT(*) AS on_time_pct,
           SUM(CASE WHEN v.on_time_flag THEN 0 ELSE 1 END) AS late_stops,
           AVG(CASE WHEN v.on_time_flag THEN NULL ELSE v.minutes_late END) AS avg_minutes_late
    FROM {{p}}v_stop_service v
    JOIN {{p}}customers cu ON cu.customer_id = v.customer_id
    WHERE v.delivery_date BETWEEN :start AND :end
    GROUP BY {group}
    ORDER BY on_time_pct ASC
    """
    rows = run(sql, {"start": start, "end": end})
    for r in rows:
        if "dow" in r and r["dow"] is not None:
            r["day_of_week"] = _DOW[int(r.pop("dow"))]
        if "late_penalty_per_stop" in r:
            r["est_late_penalties_usd"] = round(float(r["late_penalty_per_stop"] or 0) * r["late_stops"] * 0.6, 2)
            r["gap_to_target_pts"] = round((r["on_time_pct"] - float(r["on_time_target_pct"])) * 100, 1)
    return ok(rows, window=[str(start), str(end)])


@safe
def get_detention_hotspots(days: int = 30, limit: int = 10) -> dict:
    """Receivers (stores/restaurants) and customers generating the most detention.

    Args:
        days: Lookback window in days.
        limit: Max customers to return.

    Returns:
        Per customer: stops with detention, detention hours, avg dwell, detention value at
        $75/hr versus detention actually billed (the gap is unbilled accessorial revenue).
    """
    start, end = window(days)
    sql = f"""
    SELECT cu.customer_id, cu.customer_name, cu.segment,
           COUNT(*) AS stops,
           SUM(CASE WHEN s.detention_minutes > 0 THEN 1 ELSE 0 END) AS stops_with_detention,
           SUM(s.detention_minutes) / 60.0 AS detention_hours,
           AVG(s.dwell_minutes) AS avg_dwell_minutes,
           SUM(s.detention_minutes) / 60.0 * 75 AS detention_value_usd,
           SUM(COALESCE(i.detention_billed, 0)) AS detention_billed_usd
    FROM {{p}}stops s
    JOIN {{p}}locations loc ON loc.location_id = s.location_id
    JOIN {{p}}customers cu ON cu.customer_id = loc.customer_id
    LEFT JOIN {{p}}invoices i ON i.order_id = s.order_id
    WHERE s.delivery_date BETWEEN :start AND :end AND s.arrival_ts IS NOT NULL
    GROUP BY cu.customer_id, cu.customer_name, cu.segment
    HAVING SUM(s.detention_minutes) > 0
    ORDER BY detention_hours DESC
    LIMIT {int(limit)}
    """
    rows = run(sql, {"start": start, "end": end})
    for r in rows:
        r["unbilled_detention_usd"] = round(float(r["detention_value_usd"]) - float(r["detention_billed_usd"]), 2)
    return ok(rows, window=[str(start), str(end)], detention_rate_usd_per_hr=75, free_time_minutes=120)


@safe
def get_at_risk_loads(limit: int = 25) -> dict:
    """In-transit loads at risk of missing their next appointment, HOS limits or temperature.

    Combines: next undelivered stop and its window, latest telematics ETA, driver hours-of-service
    remaining, remaining stops, and reefer temperature deviation from setpoint.

    Args:
        limit: Max loads to return.

    Returns:
        Loads with risk_reasons and a risk_score (higher = act first).
    """
    sql = f"""
    WITH next_stop AS (
        SELECT s.load_id, MIN(s.stop_sequence) AS next_seq, COUNT(*) AS stops_remaining
        FROM {{p}}stops s JOIN {{p}}loads l ON l.load_id = s.load_id
        WHERE l.load_status = 'IN_TRANSIT' AND s.arrival_ts IS NULL
        GROUP BY s.load_id
    ), last_ping AS (
        SELECT load_id, MAX(event_ts) AS last_ts FROM {{p}}check_calls GROUP BY load_id
    )
    SELECT l.load_id, l.origin_dc_id, l.carrier_id, l.driver_id, l.equipment_type,
           ns.stops_remaining, s.location_id AS next_location_id, loc.location_name AS next_location,
           cu.customer_name, cu.service_tier, s.appt_window_end_ts AS next_window_end,
           cc.eta_next_stop_ts AS telematics_eta, cc.reefer_temp_f, cc.reefer_setpoint_f,
           d.driver_name, d.hos_drive_hours_remaining, d.hos_cycle_hours_remaining
    FROM next_stop ns
    JOIN {{p}}loads l ON l.load_id = ns.load_id
    JOIN {{p}}stops s ON s.load_id = ns.load_id AND s.stop_sequence = ns.next_seq
    JOIN {{p}}locations loc ON loc.location_id = s.location_id
    JOIN {{p}}customers cu ON cu.customer_id = loc.customer_id
    LEFT JOIN last_ping lp ON lp.load_id = l.load_id
    LEFT JOIN {{p}}check_calls cc ON cc.load_id = lp.load_id AND cc.event_ts = lp.last_ts
    LEFT JOIN {{p}}drivers d ON d.driver_id = l.driver_id
    """
    rows = run(sql, max_rows=1000)
    out = []
    for r in rows:
        reasons, score = [], 0
        hos = r.get("hos_drive_hours_remaining")
        if hos is not None and hos < 2 and r["stops_remaining"] > 0:
            reasons.append(f"Driver has {hos}h drive time left with {r['stops_remaining']} stops remaining")
            score += 40
        eta, wend = r.get("telematics_eta"), r.get("next_window_end")
        if eta and wend and str(eta) > str(wend):
            reasons.append(f"Telematics ETA {eta} is after window end {wend}")
            score += 35 + (10 if r["service_tier"] == "PLATINUM" else 0)
        if r.get("reefer_temp_f") is not None and r.get("reefer_setpoint_f") is not None:
            dev = float(r["reefer_temp_f"]) - float(r["reefer_setpoint_f"])
            if dev > 5:
                reasons.append(f"Reefer {dev:.1f}F above setpoint")
                score += 45
        if r["stops_remaining"] >= 5:
            score += 5
        if reasons:
            out.append({**r, "risk_score": score, "risk_reasons": reasons})
    out.sort(key=lambda x: -x["risk_score"])
    return ok(out[: int(limit)], in_transit_loads=len(rows), at_risk=len(out), as_of_date=as_of().isoformat())


@safe
def get_reefer_excursions(days: int = 60) -> dict:
    """Reefer temperature excursions by trailer refrigeration-unit age, plus the worst trailers.

    Args:
        days: Lookback window in days.

    Returns:
        'by_unit_age': excursion rate per load for reefer unit age buckets;
        'worst_trailers': trailers with repeated excursions (candidates for repair / replacement).
    """
    start, end = window(days)
    by_age = run(f"""
        SELECT CASE WHEN t.reefer_unit_age_years >= 9 THEN '9+ yrs'
                    WHEN t.reefer_unit_age_years >= 5 THEN '5-8 yrs' ELSE '0-4 yrs' END AS reefer_unit_age,
               COUNT(DISTINCT l.load_id) AS reefer_loads,
               COUNT(DISTINCT e.exception_id) AS excursions,
               1.0 * COUNT(DISTINCT e.exception_id) / COUNT(DISTINCT l.load_id) AS excursion_rate,
               SUM(e.cost_impact) AS est_product_loss_usd
        FROM {{p}}loads l
        JOIN {{p}}trailers t ON t.trailer_id = l.trailer_id
        LEFT JOIN {{p}}exceptions e ON e.load_id = l.load_id AND e.exception_type = 'REEFER_TEMP_EXCURSION'
        WHERE t.reefer_unit_age_years IS NOT NULL AND l.load_date BETWEEN :start AND :end
        GROUP BY 1 ORDER BY excursion_rate DESC
    """, {"start": start, "end": end})
    worst = run(f"""
        SELECT t.trailer_id, t.home_dc_id, t.trailer_type, t.reefer_unit_age_years,
               COUNT(*) AS excursions, SUM(e.cost_impact) AS est_product_loss_usd
        FROM {{p}}exceptions e
        JOIN {{p}}loads l ON l.load_id = e.load_id
        JOIN {{p}}trailers t ON t.trailer_id = l.trailer_id
        WHERE e.exception_type = 'REEFER_TEMP_EXCURSION' AND e.event_date BETWEEN :start AND :end
        GROUP BY t.trailer_id, t.home_dc_id, t.trailer_type, t.reefer_unit_age_years
        HAVING COUNT(*) >= 2
        ORDER BY excursions DESC, est_product_loss_usd DESC
        LIMIT 15
    """, {"start": start, "end": end})
    return ok({"by_unit_age": by_age, "worst_trailers": worst}, window=[str(start), str(end)])
