"""Mileage tools: PC*MILER planned miles vs billed and driven miles."""

from __future__ import annotations

import os

from tms_agent.mileage import route_miles
from tms_agent.tools.common import fail, ok, run, safe, window


@safe
def check_pcmiler_miles(load_id: str) -> dict:
    """Compares a load's PC*MILER miles with the carrier's billed miles and the odometer.

    TMW plans every load with PC*MILER practical miles (loads.total_miles). This tool also
    re-routes the stop sequence (live PC*MILER when PCMILER_API_KEY is set, otherwise a labelled
    estimate) so a reviewer can see whether a carrier's billed miles are defensible.

    Args:
        load_id: Load / leg number, e.g. 'LGH0000088'.

    Returns:
        PC*MILER practical and shortest miles from TMW, re-routed miles with their source, billed
        miles from the carrier invoice, actual odometer miles, variances and a verdict.
    """
    lid = load_id.strip().upper()
    load = run("""
        SELECT l.load_id, l.carrier_id, l.origin_dc_id, l.total_miles, l.pcmiler_shortest_miles, l.mileage_source,
               l.actual_odometer_miles, ci.carrier_invoice_id, ci.billed_miles
        FROM {p}loads l LEFT JOIN {p}carrier_invoices ci ON ci.load_id = l.load_id
        WHERE l.load_id = :lid
    """, {"lid": lid})
    if not load:
        return fail(f"Load {lid} not found.")
    r = load[0]
    pts = run("""
        SELECT loc.latitude, loc.longitude, loc.geocode_quality, s.stop_sequence
        FROM {p}stops s JOIN {p}locations loc ON loc.location_id = s.location_id
        WHERE s.load_id = :lid ORDER BY s.stop_sequence
    """, {"lid": lid})
    dc = run("SELECT latitude, longitude FROM {p}locations WHERE location_id = :dc", {"dc": r["origin_dc_id"]})
    seq = [(dc[0]["latitude"], dc[0]["longitude"])] + [(p["latitude"], p["longitude"]) for p in pts] + \
          [(dc[0]["latitude"], dc[0]["longitude"])]
    rerouted = route_miles(seq)
    planned = r["total_miles"]
    out = dict(r, rerouted_miles=rerouted["miles"], rerouted_source=rerouted["source"], rerouted_note=rerouted["note"])
    review = []
    if any(p["geocode_quality"] == "ZIP_CENTROID" for p in pts):
        review.append("A stop has ZIP_CENTROID coordinates, so re-routed miles are approximate.")
    if r["billed_miles"] is not None and planned:
        var = (r["billed_miles"] - planned) / planned
        out["billed_vs_pcmiler_pct"] = round(var, 3)
        out["verdict"] = "MILES_INFLATED" if var > 0.02 else "OK"
        out["evidence"] = f"billed {r['billed_miles']} mi vs PC*MILER practical {planned} mi ({var:+.1%})"
    else:
        out["verdict"] = "NO_CARRIER_BILL" if r["carrier_id"] != "MCLN" else "PRIVATE_FLEET"
    if r["actual_odometer_miles"] is not None and planned:
        out["out_of_route_pct"] = round(r["actual_odometer_miles"] / planned - 1, 3)
    return ok(out, needs_review=review)


@safe
def get_out_of_route_miles(days: int = 90, group_by: str = "driver", min_loads: int = 5, limit: int = 15) -> dict:
    """Private fleet out-of-route (OOR) miles: odometer miles driven vs PC*MILER practical miles.

    Args:
        days: Lookback window in days (default 90).
        group_by: driver or dc.
        min_loads: Minimum completed loads for a group to be ranked.
        limit: Max rows.

    Returns:
        Rows with loads, PC*MILER miles, odometer miles, OOR %, extra miles and the extra variable
        cost (fuel + maintenance per mile on those loads), flagged when OOR exceeds
        TMS_OOR_FLAG_PCT (default 8%).
    """
    start, end = window(days)
    dims = {"driver": "l.driver_id, d.driver_name, l.origin_dc_id", "dc": "l.origin_dc_id"}
    if group_by not in dims:
        return fail(f"group_by must be one of {sorted(dims)}")
    rows = run(f"""
        WITH vc AS (
            SELECT load_id, SUM(amount) AS variable_cost FROM {{p}}load_costs
            WHERE cost_type IN ('FUEL', 'MAINTENANCE_ALLOC') GROUP BY load_id
        )
        SELECT {dims[group_by]}, COUNT(*) AS loads, SUM(l.total_miles) AS pcmiler_miles,
               SUM(l.actual_odometer_miles) AS odometer_miles,
               1.0 * SUM(l.actual_odometer_miles) / NULLIF(SUM(l.total_miles), 0) - 1 AS oor_pct,
               SUM(l.actual_odometer_miles - l.total_miles) AS extra_miles,
               1.0 * SUM(vc.variable_cost) / NULLIF(SUM(l.total_miles), 0) AS variable_cost_per_mile
        FROM {{p}}loads l
        LEFT JOIN {{p}}drivers d ON d.driver_id = l.driver_id
        LEFT JOIN vc ON vc.load_id = l.load_id
        WHERE l.actual_odometer_miles IS NOT NULL AND l.load_date BETWEEN :start AND :end
        GROUP BY {dims[group_by]}
        HAVING COUNT(*) >= :min_loads
        ORDER BY oor_pct DESC
        LIMIT {int(limit)}
    """, {"start": start, "end": end, "min_loads": int(min_loads)})
    threshold = float(os.getenv("TMS_OOR_FLAG_PCT", "0.08"))
    for r in rows:
        r["extra_cost_usd"] = round((r["extra_miles"] or 0) * (r["variable_cost_per_mile"] or 0), 2)
        r["flag"] = "HIGH_OUT_OF_ROUTE" if (r["oor_pct"] or 0) > threshold else ""
    return ok(rows, window=[str(start), str(end)], flag_threshold_pct=threshold,
              reasoning="Odometer miles above PC*MILER practical miles are out-of-route; cost uses fuel + maintenance per mile.")
