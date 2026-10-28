"""Weekly insights pack: one call that gathers everything leadership reviews each week."""

from __future__ import annotations

from tms_agent.tools.audit import audit_carrier_invoices
from tms_agent.tools.carrier import get_carrier_scorecard
from tms_agent.tools.common import ok, run, safe, window
from tms_agent.tools.cost import get_accessorial_leakage, get_lane_profitability
from tms_agent.tools.delivery import get_dwell_time_changes, get_geofence_compliance, get_otd_scorecard
from tms_agent.tools.kpi import get_ops_kpi_snapshot
from tms_agent.tools.miles import get_out_of_route_miles
from tms_agent.tools.predict import predict_load_delays


@safe
def get_spot_vs_contract_premium(days: int = 30) -> dict:
    """Spend on loads without a lane contract (spot) and broker loads versus contract carrier cost per mile.

    Args:
        days: Lookback window in days.

    Returns:
        Per carrier type and contract status: loads, spend, cost per mile; plus estimated overspend
        if spot / broker loads had moved at the contract average cost per mile.
    """
    start, end = window(days)
    rows = run("""
        SELECT v.carrier_type,
               CASE WHEN r.rate_id IS NULL THEN 'SPOT' ELSE 'CONTRACT' END AS rate_basis,
               COUNT(*) AS loads, SUM(v.total_cost) AS spend, SUM(v.total_miles) AS miles,
               1.0 * SUM(v.total_cost) / NULLIF(SUM(v.total_miles), 0) AS cost_per_mile
        FROM {p}v_load_profitability v
        LEFT JOIN {p}carrier_rates r ON r.carrier_id = v.carrier_id AND r.origin_dc_id = v.origin_dc_id
             AND r.dest_state = v.dest_region_state AND r.equipment_type = v.equipment_type
        WHERE v.carrier_type <> 'PRIVATE_FLEET' AND v.load_date BETWEEN :start AND :end
        GROUP BY 1, 2 ORDER BY 1, 2
    """, {"start": start, "end": end})
    contract = [r for r in rows if r["carrier_type"] == "CONTRACT" and r["rate_basis"] == "CONTRACT"]
    benchmark = contract[0]["cost_per_mile"] if contract else None
    overspend = 0.0
    if benchmark:
        for r in rows:
            if r["rate_basis"] == "SPOT" or r["carrier_type"] == "BROKER":
                overspend += max(0.0, float(r["spend"]) - float(r["miles"]) * float(benchmark))
    return ok(rows, contract_cost_per_mile=benchmark, est_overspend_usd=round(overspend, 2),
              window=[str(start), str(end)])


@safe
def get_weekly_insights_pack() -> dict:
    """Collects the weekly TMS review: KPIs vs prior week, worst lanes, carrier flags, invoice audit
    savings, accessorial leakage, spot/broker premium, tomorrow's at-risk loads, Retail vs Restaurant
    OTD, dwell time changes, out-of-route drivers and geocode fixes.

    Returns:
        A dict of sections; the coordinator turns it into the weekly insight narrative.
    """
    def data(res, key=None):
        if res.get("status") != "success":
            return {"error": res.get("error_message")}
        return res["data"] if key is None else res["data"][key]

    carriers = data(get_carrier_scorecard(30))
    leakage = get_accessorial_leakage(30)
    audit = audit_carrier_invoices(7, group_by="finding", limit=5)
    spot = get_spot_vs_contract_premium(30)
    delays = predict_load_delays(24, 0.3, 5)
    return ok({
        "kpis_7d_vs_prior": data(get_ops_kpi_snapshot(7)),
        "worst_lanes_30d": data(get_lane_profitability(30, 10, "worst", 3)),
        "carrier_flags_30d": [c for c in carriers if isinstance(c, dict) and c.get("flags")] if isinstance(carriers, list) else carriers,
        "invoice_audit_7d": data(audit, "summary") | {"by_finding": data(audit, "breakdown")[:5]} if audit.get("status") == "success" else data(audit),
        "accessorial_leakage_30d": {"total_recoverable_usd": leakage.get("total_recoverable_usd"),
                                    "annualized_recoverable_usd": leakage.get("annualized_recoverable_usd"),
                                    "top": (leakage.get("data") or [])[:3]},
        "spot_vs_contract_30d": {"rows": spot.get("data"), "est_overspend_usd": spot.get("est_overspend_usd")},
        "at_risk_tomorrow": {"flagged": delays.get("flagged"), "upcoming": delays.get("upcoming_loads"),
                             "top": (delays.get("data") or [])[:5]},
        "otd_by_channel_28d": data(get_otd_scorecard(28, "channel")),
        "dwell_time_changes": data(get_dwell_time_changes(limit=5)),
        "out_of_route_90d": [r for r in (data(get_out_of_route_miles(90, "driver")) or []) if isinstance(r, dict) and r.get("flag")],
        "geocode_fixes_30d": (lambda g: {"geofence_auto_arrival_pct": g.get("geofence_auto_arrival_pct"),
                                         "locations": g.get("locations_missing_geofence", [])[:5]}
                              if isinstance(g, dict) and "error" not in g else g)(data(get_geofence_compliance(30))),
    })
