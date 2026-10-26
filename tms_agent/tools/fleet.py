"""Private fleet tools: driver hours of service, utilization and maintenance."""

from __future__ import annotations

import datetime as dt

from tms_agent.tools.common import ok, run, safe, window


@safe
def get_driver_hos_status(dc_id: str = "", max_drive_hours: float = 3.0) -> dict:
    """Active drivers who are low on hours-of-service, and whether they are on an in-transit load.

    Args:
        dc_id: Optional home DC filter.
        max_drive_hours: Return drivers with at most this many drive hours remaining today.

    Returns:
        Drivers with drive / cycle hours remaining, current load and stops remaining.
    """
    rows = run("""
        WITH cur AS (
            SELECT l.driver_id, l.load_id,
                   SUM(CASE WHEN s.arrival_ts IS NULL THEN 1 ELSE 0 END) AS stops_remaining
            FROM {p}loads l JOIN {p}stops s ON s.load_id = l.load_id
            WHERE l.load_status = 'IN_TRANSIT' AND l.driver_id IS NOT NULL
            GROUP BY l.driver_id, l.load_id
        )
        SELECT d.driver_id, d.driver_name, d.home_dc_id, d.driver_type, d.safety_score,
               d.hos_drive_hours_remaining, d.hos_cycle_hours_remaining,
               cur.load_id AS current_load_id, cur.stops_remaining
        FROM {p}drivers d LEFT JOIN cur ON cur.driver_id = d.driver_id
        WHERE d.status = 'ACTIVE' AND d.hos_drive_hours_remaining <= :max_h
          AND (:dc_id = '' OR d.home_dc_id = :dc_id)
        ORDER BY CASE WHEN cur.load_id IS NULL THEN 1 ELSE 0 END, d.hos_drive_hours_remaining
    """, {"max_h": float(max_drive_hours), "dc_id": dc_id.upper()})
    return ok(rows, count=len(rows), on_active_loads=sum(1 for r in rows if r["current_load_id"]))


@safe
def get_fleet_utilization(days: int = 7) -> dict:
    """Per-DC fleet utilization: loads, private vs outsourced share, empty miles, equipment availability.

    Args:
        days: Lookback window in days.

    Returns:
        Per DC: loads, private_fleet_pct, empty_mile_pct, avg stops per load, tractors in shop and
        tractors with overdue preventive maintenance.
    """
    start, end = window(days)
    loads = run("""
        SELECT origin_dc_id, COUNT(*) AS loads,
               1.0 * SUM(CASE WHEN carrier_id = 'MCLN' THEN 1 ELSE 0 END) / COUNT(*) AS private_fleet_pct,
               1.0 * SUM(empty_miles) / NULLIF(SUM(total_miles), 0) AS empty_mile_pct,
               AVG(stop_count) AS avg_stops_per_load
        FROM {p}loads WHERE load_date BETWEEN :start AND :end AND load_status <> 'CANCELLED'
        GROUP BY origin_dc_id ORDER BY origin_dc_id
    """, {"start": start, "end": end})
    equip = run("""
        SELECT home_dc_id AS origin_dc_id, COUNT(*) AS tractors,
               SUM(CASE WHEN status <> 'IN_SERVICE' THEN 1 ELSE 0 END) AS tractors_unavailable,
               SUM(CASE WHEN next_pm_due_date < :today THEN 1 ELSE 0 END) AS pm_overdue
        FROM {p}tractors GROUP BY home_dc_id
    """, {"today": end})
    eq = {r["origin_dc_id"]: r for r in equip}
    for r in loads:
        r.update({k: v for k, v in eq.get(r["origin_dc_id"], {}).items() if k != "origin_dc_id"})
    return ok(loads, window=[str(start), str(end)])


@safe
def get_maintenance_due(days_ahead: int = 14, dc_id: str = "") -> dict:
    """Tractors with preventive maintenance overdue or due within N days.

    Args:
        days_ahead: Horizon in days.
        dc_id: Optional home DC filter.

    Returns:
        Tractors sorted by due date, with model year, odometer and status.
    """
    _, today = window(1)
    rows = run("""
        SELECT tractor_id, home_dc_id, make, model_year, odometer_miles, status, next_pm_due_date
        FROM {p}tractors
        WHERE next_pm_due_date <= :horizon AND (:dc_id = '' OR home_dc_id = :dc_id)
        ORDER BY next_pm_due_date
    """, {"horizon": today + dt.timedelta(days=int(days_ahead)), "dc_id": dc_id.upper()}, max_rows=500)
    for r in rows:
        r["overdue"] = str(r["next_pm_due_date"]) < str(today)
    return ok(rows, count=len(rows), overdue=sum(r["overdue"] for r in rows))
