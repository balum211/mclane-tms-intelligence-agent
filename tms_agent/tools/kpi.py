"""Network KPI snapshot used by the coordinator for daily briefings."""

from __future__ import annotations

import datetime as dt

from tms_agent.tools.common import ok, run, safe, window

_KPI_SQL = """
SELECT COUNT(*) AS completed_loads,
       SUM(total_revenue) AS revenue, SUM(margin) AS margin,
       1.0 * SUM(margin) / NULLIF(SUM(total_revenue), 0) AS margin_pct,
       1.0 * SUM(total_cost) / NULLIF(SUM(total_miles), 0) AS cost_per_mile,
       1.0 * SUM(empty_miles) / NULLIF(SUM(total_miles), 0) AS empty_mile_pct,
       1.0 * SUM(CASE WHEN carrier_type = 'PRIVATE_FLEET' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS private_fleet_pct
FROM {p}v_load_profitability
WHERE load_date BETWEEN :start AND :end AND (:dc_id = '' OR origin_dc_id = :dc_id)
"""

_SVC_SQL = """
SELECT COUNT(*) AS stops,
       1.0 * SUM(CASE WHEN on_time_flag THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS on_time_pct,
       SUM(detention_minutes) / 60.0 AS detention_hours,
       1.0 * SUM(cases_short + cases_damaged) / NULLIF(SUM(cases_delivered + cases_short), 0) AS claims_case_rate,
       SUM(CASE WHEN refused_flag THEN 1 ELSE 0 END) AS refused_stops
FROM {p}v_stop_service
WHERE delivery_date BETWEEN :start AND :end AND (:dc_id = '' OR origin_dc_id = :dc_id)
"""


def _period(start: dt.date, end: dt.date, dc_id: str) -> dict:
    p = {"start": start, "end": end, "dc_id": dc_id}
    out = run(_KPI_SQL, p)[0]
    out.update(run(_SVC_SQL, p)[0])
    return out


@safe
def get_ops_kpi_snapshot(days: int = 7, dc_id: str = "") -> dict:
    """Network (or single-DC) KPI snapshot for the last N days versus the prior N days.

    KPIs: completed loads, revenue, margin and margin %, cost per mile, empty-mile %, private
    fleet share, on-time %, detention hours, claims rate, refused stops, plus open exceptions
    by severity and today's in-transit load count.

    Args:
        days: Period length in days (default 7).
        dc_id: Optional origin DC filter, e.g. 'DC03'.

    Returns:
        dict with 'current', 'prior', 'delta' (current - prior) and 'today'.
    """
    dc_id = dc_id.upper()
    start, end = window(days)
    pstart, pend = start - dt.timedelta(days=days), start - dt.timedelta(days=1)
    cur, prior = _period(start, end, dc_id), _period(pstart, pend, dc_id)
    delta = {}
    for k, v in cur.items():
        if isinstance(v, (int, float)) and isinstance(prior.get(k), (int, float)):
            delta[k] = round(v - prior[k], 4)
    open_exc = run("""
        SELECT e.severity, COUNT(*) AS open_exceptions
        FROM {p}exceptions e JOIN {p}loads l ON l.load_id = e.load_id
        WHERE e.resolved_flag = FALSE AND (:dc_id = '' OR l.origin_dc_id = :dc_id)
        GROUP BY e.severity
    """, {"dc_id": dc_id})
    in_transit = run("""
        SELECT COUNT(*) AS in_transit_loads FROM {p}loads
        WHERE load_status = 'IN_TRANSIT' AND (:dc_id = '' OR origin_dc_id = :dc_id)
    """, {"dc_id": dc_id})[0]
    return ok({
        "current": {"window": [str(start), str(end)], **cur},
        "prior": {"window": [str(pstart), str(pend)], **prior},
        "delta": delta,
        "today": {"as_of_date": str(end), **in_transit,
                  "open_exceptions_by_severity": {r["severity"]: r["open_exceptions"] for r in open_exc}},
    }, scope=dc_id or "NETWORK")
