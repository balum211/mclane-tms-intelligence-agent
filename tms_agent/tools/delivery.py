"""Delivery performance tools: Retail vs Restaurant OTD, dwell time changes, geofences and live tracking."""

from __future__ import annotations

import datetime as dt
import os

from tms_agent.db import get_backend
from tms_agent.mileage import haversine_miles, route_miles
from tms_agent.tools.common import as_of, fail, ok, run, safe, window

AVG_MPH = 47.0
RESTAURANT_EARLY_GRACE_MIN = 15  # must match otd_flag in the v_stop_service view


def _truck_hour_cost() -> float:
    return float(os.getenv("TMS_TRUCK_HOUR_COST_USD", "85"))


@safe
def get_otd_scorecard(days: int = 28, group_by: str = "channel", channel: str = "") -> dict:
    """McLane on-time delivery (OTD) for Retail (grocery / convenience) vs Restaurant (foodservice) stops.

    OTD rules: a Retail stop is on time when it does not arrive after the appointment window end.
    A Restaurant stop must also not arrive more than 15 minutes before the window start, because
    restaurants are often not staffed to receive early. Use this for any OTD question.

    Args:
        days: Lookback window in days ending at the dataset as-of date (default 28).
        group_by: channel, dc, customer, carrier or week.
        channel: Optional filter: RETAIL or RESTAURANT. Empty for both.

    Returns:
        Rows with stops, otd_pct, not_late_pct, early_misses, late_misses, target_pct, gap_pts and
        late_penalty_exposure_usd, plus the rule definitions and the window used.
    """
    start, end = window(days)
    b = get_backend()
    dims = {
        "channel": ("v.otd_channel", "v.otd_channel"),
        "dc": ("v.otd_channel, v.origin_dc_id", "v.otd_channel, v.origin_dc_id"),
        "customer": ("v.otd_channel, v.customer_name", "v.otd_channel, v.customer_name"),
        "carrier": ("v.otd_channel, v.carrier_id", "v.otd_channel, v.carrier_id"),
        "week": (f"v.otd_channel, {b.week('v.delivery_date')} AS week_start", f"v.otd_channel, {b.week('v.delivery_date')}"),
    }
    if group_by not in dims:
        return fail(f"group_by must be one of {sorted(dims)}")
    ch = channel.upper()
    if ch not in ("", "RETAIL", "RESTAURANT"):
        return fail("channel must be RETAIL, RESTAURANT or empty")
    select, group = dims[group_by]
    rows = run(f"""
        SELECT {select}, COUNT(*) AS stops,
               1.0 * SUM(CASE WHEN v.otd_flag THEN 1 ELSE 0 END) / COUNT(*) AS otd_pct,
               1.0 * SUM(CASE WHEN v.on_time_flag THEN 1 ELSE 0 END) / COUNT(*) AS not_late_pct,
               SUM(CASE WHEN v.minutes_late = 0 AND NOT v.otd_flag THEN 1 ELSE 0 END) AS early_misses,
               SUM(CASE WHEN v.minutes_late > 0 THEN 1 ELSE 0 END) AS late_misses,
               AVG(cu.on_time_target_pct) AS target_pct,
               SUM(CASE WHEN v.minutes_late > 0 THEN cu.late_penalty_per_stop ELSE 0 END) AS late_penalty_exposure_usd
        FROM {{p}}v_stop_service v JOIN {{p}}customers cu ON cu.customer_id = v.customer_id
        WHERE v.delivery_date BETWEEN :start AND :end AND (:ch = '' OR v.otd_channel = :ch)
        GROUP BY {group}
        ORDER BY {'week_start, v.otd_channel' if group_by == 'week' else 'otd_pct'}
        LIMIT 60
    """, {"start": start, "end": end, "ch": ch})
    for r in rows:
        r["gap_pts"] = round((r["otd_pct"] - r["target_pct"]) * 100, 1) if r["target_pct"] is not None else None
    return ok(rows, window=[str(start), str(end)], definitions={
        "RETAIL": "On time = arrival not after appointment window end.",
        "RESTAURANT": f"On time = arrival not after window end and not more than {RESTAURANT_EARLY_GRACE_MIN} min "
                      "before window start.",
    })


@safe
def get_dwell_time_changes(recent_days: int = 21, baseline_days: int = 56, group_by: str = "customer",
                           min_change_minutes: float = 10.0, min_stops: int = 20, limit: int = 15) -> dict:
    """Finds receivers whose dwell time (arrival to departure) changed recently vs their baseline.

    A dwell increase costs truck hours and pushes later stops late; a decrease frees capacity. The
    dollar impact uses TMS_TRUCK_HOUR_COST_USD (default $85 per truck hour, driver plus equipment).

    Args:
        recent_days: Length of the recent window ending at the as-of date (default 21).
        baseline_days: Length of the baseline window just before the recent window (default 56).
        group_by: customer, location, dc or channel.
        min_change_minutes: Only return groups whose average dwell moved at least this much.
        min_stops: Minimum stops in each window; smaller groups are flagged LOW_SAMPLE, not ranked.
        limit: Max rows.

    Returns:
        Rows with baseline and recent average dwell, change in minutes and %, direction, recent
        stops, extra truck hours in the recent window, annualized $ impact and new detention minutes.
    """
    end = as_of()
    recent_start = end - dt.timedelta(days=max(1, recent_days) - 1)
    base_start = recent_start - dt.timedelta(days=max(1, baseline_days))
    dims = {
        "customer": "v.customer_name",
        "location": "v.location_id, v.location_name, v.customer_name",
        "dc": "v.origin_dc_id",
        "channel": "v.otd_channel",
    }
    if group_by not in dims:
        return fail(f"group_by must be one of {sorted(dims)}")
    rows = run(f"""
        SELECT {dims[group_by]},
               SUM(CASE WHEN v.delivery_date < :rs THEN 1 ELSE 0 END) AS baseline_stops,
               SUM(CASE WHEN v.delivery_date >= :rs THEN 1 ELSE 0 END) AS recent_stops,
               AVG(CASE WHEN v.delivery_date < :rs THEN v.dwell_minutes END) AS baseline_dwell_min,
               AVG(CASE WHEN v.delivery_date >= :rs THEN v.dwell_minutes END) AS recent_dwell_min,
               AVG(CASE WHEN v.delivery_date < :rs THEN v.detention_minutes END) AS baseline_detention_min,
               AVG(CASE WHEN v.delivery_date >= :rs THEN v.detention_minutes END) AS recent_detention_min
        FROM {{p}}v_stop_service v
        WHERE v.delivery_date BETWEEN :bs AND :end
        GROUP BY {dims[group_by]}
    """, {"rs": recent_start, "bs": base_start, "end": end}, max_rows=2000)
    out, low_sample = [], []
    rate = _truck_hour_cost()
    for r in rows:
        if r["recent_dwell_min"] is None or r["baseline_dwell_min"] is None:
            continue
        change = r["recent_dwell_min"] - r["baseline_dwell_min"]
        if abs(change) < min_change_minutes:
            continue
        r["change_min"] = round(change, 1)
        r["change_pct"] = round(change / r["baseline_dwell_min"], 3) if r["baseline_dwell_min"] else None
        r["direction"] = "INCREASE" if change > 0 else "DECREASE"
        r["truck_hours_recent_window"] = round(change * r["recent_stops"] / 60, 1)
        r["annualized_impact_usd"] = round(change * r["recent_stops"] / 60 * rate * 365 / max(1, recent_days), 0)
        r["detention_change_min"] = round((r["recent_detention_min"] or 0) - (r["baseline_detention_min"] or 0), 1)
        if r["recent_stops"] < min_stops or r["baseline_stops"] < min_stops:
            r["flag"] = "LOW_SAMPLE"
            low_sample.append(r)
        else:
            out.append(r)
    out.sort(key=lambda r: -abs(r["annualized_impact_usd"]))
    return ok(out[: int(limit)], low_sample=low_sample[:10],
              recent_window=[str(recent_start), str(end)], baseline_window=[str(base_start), str(recent_start - dt.timedelta(days=1))],
              truck_hour_cost_usd=rate,
              reasoning="Average dwell per stop, recent window vs baseline. Positive annualized_impact_usd is extra cost.")


@safe
def get_geofence_compliance(days: int = 30, dc_id: str = "", min_arrivals: int = 3, limit: int = 15) -> dict:
    """Geofence auto-arrival health and locations whose geofence does not fire (likely bad geocodes).

    Tracked trucks should arrive by GEOFENCE. DRIVER_MANUAL arrivals at a location that is usually
    missed point to wrong coordinates. When the ELD logged a stationary ping at the manual arrival,
    the median of those pings is returned as suggested coordinates.

    Args:
        days: Lookback window in days (default 30).
        dc_id: Optional servicing DC filter, e.g. 'DC04'.
        min_arrivals: Minimum tracked arrivals for a location to be judged.
        limit: Max locations returned.

    Returns:
        Arrival source mix, and locations with geofence miss rate >= 50% with geocode quality,
        stored and suggested coordinates and the offset in meters.
    """
    start, end = window(days)
    params = {"start": start, "end": end, "dc_id": dc_id.upper()}
    mix = run("""
        SELECT s.arrival_source, COUNT(*) AS arrivals
        FROM {p}stops s JOIN {p}loads l ON l.load_id = s.load_id
        WHERE s.arrival_ts IS NOT NULL AND s.delivery_date BETWEEN :start AND :end
          AND (:dc_id = '' OR l.origin_dc_id = :dc_id)
        GROUP BY s.arrival_source ORDER BY arrivals DESC
    """, params)
    tracked = sum(r["arrivals"] for r in mix if r["arrival_source"] in ("GEOFENCE", "DRIVER_MANUAL"))
    geo = sum(r["arrivals"] for r in mix if r["arrival_source"] == "GEOFENCE")
    locs = run("""
        SELECT loc.location_id, loc.location_name, loc.dc_id, loc.geocode_quality, loc.geofence_radius_m,
               loc.latitude, loc.longitude,
               SUM(CASE WHEN s.arrival_source IN ('GEOFENCE', 'DRIVER_MANUAL') THEN 1 ELSE 0 END) AS tracked_arrivals,
               SUM(CASE WHEN s.arrival_source = 'DRIVER_MANUAL' THEN 1 ELSE 0 END) AS manual_arrivals
        FROM {p}stops s JOIN {p}locations loc ON loc.location_id = s.location_id
        WHERE s.arrival_ts IS NOT NULL AND s.delivery_date BETWEEN :start AND :end
          AND (:dc_id = '' OR loc.dc_id = :dc_id)
        GROUP BY loc.location_id, loc.location_name, loc.dc_id, loc.geocode_quality, loc.geofence_radius_m,
                 loc.latitude, loc.longitude
    """, params, max_rows=5000)
    flagged = []
    for r in locs:
        if r["tracked_arrivals"] < min_arrivals:
            continue
        r["geofence_miss_rate"] = round(r["manual_arrivals"] / r["tracked_arrivals"], 3)
        if r["geofence_miss_rate"] >= 0.5:
            flagged.append(r)
    flagged.sort(key=lambda r: (-r["geofence_miss_rate"], -r["tracked_arrivals"]))
    flagged = flagged[: int(limit)]
    if flagged:
        ids = ", ".join(f"'{r['location_id']}'" for r in flagged)  # ids come from our own query
        pings = run(f"""
            SELECT s.location_id, c.latitude, c.longitude
            FROM {{p}}stops s JOIN {{p}}check_calls c ON c.load_id = s.load_id AND c.event_ts = s.arrival_ts
            WHERE s.arrival_source = 'DRIVER_MANUAL' AND c.speed_mph = 0 AND s.location_id IN ({ids})
        """, max_rows=5000)
        by_loc: dict[str, list[tuple[float, float]]] = {}
        for p in pings:
            by_loc.setdefault(p["location_id"], []).append((p["latitude"], p["longitude"]))
        for r in flagged:
            pts = by_loc.get(r["location_id"], [])
            if len(pts) >= 2:
                lat = sorted(p[0] for p in pts)[len(pts) // 2]
                lon = sorted(p[1] for p in pts)[len(pts) // 2]
                r["suggested_latitude"], r["suggested_longitude"] = round(lat, 5), round(lon, 5)
                r["offset_m"] = int(haversine_miles((r["latitude"], r["longitude"]), (lat, lon)) * 1609.34)
                r["evidence_pings"] = len(pts)
                r["action"] = "Update the location coordinates in TMW (company profile) and re-sync the geofence."
            else:
                r["action"] = "NEEDS_REVIEW: not enough stationary ELD pings to suggest coordinates; verify the address."
    return ok({"arrival_source_mix": mix, "tracked_arrivals": tracked,
               "geofence_auto_arrival_pct": round(geo / tracked, 3) if tracked else None,
               "locations_missing_geofence": flagged},
              window=[str(start), str(end)])


@safe
def track_load(load_id: str) -> dict:
    """Live position and projected arrival for an in-transit load, from the latest ELD ping.

    Args:
        load_id: Load / leg number, e.g. 'LGH0005480'.

    Returns:
        Last ping (time, lat/lon, speed, minutes old), next stop with appointment window, remaining
        miles (PC*MILER when configured, otherwise a labelled estimate), projected arrival and
        projected minutes late, plus any geocode warning for the next stop.
    """
    lid = load_id.strip().upper()
    load = run("SELECT load_id, load_status, origin_dc_id, carrier_id, driver_id FROM {p}loads WHERE load_id = :lid",
               {"lid": lid})
    if not load:
        return fail(f"Load {lid} not found.")
    nxt = run("""
        SELECT s.stop_id, s.stop_sequence, s.location_id, loc.location_name, loc.latitude, loc.longitude,
               loc.geocode_quality, s.appt_window_start_ts, s.appt_window_end_ts
        FROM {p}stops s JOIN {p}locations loc ON loc.location_id = s.location_id
        WHERE s.load_id = :lid AND s.arrival_ts IS NULL
        ORDER BY s.stop_sequence LIMIT 1
    """, {"lid": lid})
    ping = run("""
        SELECT event_ts, latitude, longitude, speed_mph, eta_next_stop_ts FROM {p}check_calls
        WHERE load_id = :lid ORDER BY event_ts DESC LIMIT 1
    """, {"lid": lid})
    out = {"load": load[0], "next_stop": nxt[0] if nxt else None, "last_ping": ping[0] if ping else None}
    if not nxt:
        return ok(out, note="No remaining stops: the load has delivered everything.")
    if not ping:
        return ok(out, needs_review=["NO_TELEMATICS: no ELD / visibility pings for this load; ask the carrier for a check call."])
    p, s = ping[0], nxt[0]
    ping_ts = dt.datetime.fromisoformat(str(p["event_ts"]).replace("Z", ""))
    miles = route_miles([(p["latitude"], p["longitude"]), (s["latitude"], s["longitude"])])
    eta = ping_ts + dt.timedelta(minutes=miles["miles"] / AVG_MPH * 60)
    win_end = dt.datetime.fromisoformat(str(s["appt_window_end_ts"]).replace("Z", ""))
    out.update(remaining_miles=miles["miles"], miles_source=miles["source"], miles_note=miles["note"],
               projected_arrival_ts=eta.isoformat(timespec="minutes"),
               projected_minutes_late=max(0, int((eta - win_end).total_seconds() // 60)))
    warnings = []
    if s["geocode_quality"] == "ZIP_CENTROID":
        warnings.append("Next stop has ZIP_CENTROID coordinates: distance and geofence arrival may be off by 1-4 km.")
    return ok(out, warnings=warnings, assumptions=f"ETA uses {AVG_MPH:.0f} mph average from the last ping.")
