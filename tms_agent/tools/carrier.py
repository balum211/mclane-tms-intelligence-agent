"""Carrier management tools: scorecards, tender acceptance and lane-level carrier recommendations."""

from __future__ import annotations

from tms_agent.tools.common import fail, ok, run, safe, window

EQUIPMENT = {"DRY_53", "REEFER_53", "MULTI_TEMP_53", "PUP_28"}


@safe
def get_carrier_scorecard(days: int = 90) -> dict:
    """Carrier scorecard: volume, on-time, lateness, claims, cost per mile and tender acceptance.

    Args:
        days: Lookback window in days.

    Returns:
        One row per carrier (private fleet included as MCLN for benchmarking), worst on-time first.
    """
    start, end = window(days)
    rows = run("""
        WITH svc AS (
            SELECT l.carrier_id, COUNT(DISTINCT l.load_id) AS loads, COUNT(*) AS stops,
                   1.0 * SUM(CASE WHEN s.on_time_flag THEN 1 ELSE 0 END) / COUNT(*) AS on_time_pct,
                   AVG(CASE WHEN s.on_time_flag THEN NULL ELSE s.minutes_late END) AS avg_minutes_late_when_late,
                   1.0 * SUM(s.cases_damaged + s.cases_short) / NULLIF(SUM(s.cases_delivered + s.cases_short), 0) AS claims_case_rate
            FROM {p}loads l JOIN {p}stops s ON s.load_id = l.load_id
            WHERE l.load_status = 'COMPLETED' AND l.load_date BETWEEN :start AND :end
            GROUP BY l.carrier_id
        ), cpm AS (
            SELECT carrier_id, 1.0 * SUM(total_cost) / NULLIF(SUM(total_miles), 0) AS cost_per_mile
            FROM {p}v_load_profitability WHERE load_date BETWEEN :start AND :end GROUP BY carrier_id
        ), tnd AS (
            SELECT carrier_id, COUNT(*) AS tenders,
                   1.0 * SUM(CASE WHEN response = 'ACCEPTED' THEN 1 ELSE 0 END) / COUNT(*) AS acceptance_pct
            FROM {p}carrier_tenders WHERE tender_date BETWEEN :start AND :end GROUP BY carrier_id
        )
        SELECT c.carrier_id, c.carrier_name, c.carrier_type, c.safety_rating, c.insurance_expiry_date,
               svc.loads, svc.on_time_pct, svc.avg_minutes_late_when_late, svc.claims_case_rate,
               cpm.cost_per_mile, tnd.tenders, tnd.acceptance_pct
        FROM {p}carriers c
        JOIN svc ON svc.carrier_id = c.carrier_id
        LEFT JOIN cpm ON cpm.carrier_id = c.carrier_id
        LEFT JOIN tnd ON tnd.carrier_id = c.carrier_id
        ORDER BY svc.on_time_pct ASC
    """, {"start": start, "end": end})
    end_s = str(end)
    for r in rows:
        flags = []
        if r["on_time_pct"] is not None and r["on_time_pct"] < 0.9:
            flags.append("ON_TIME_BELOW_90")
        if r.get("acceptance_pct") is not None and r["acceptance_pct"] < 0.75 and (r["tenders"] or 0) >= 10:
            flags.append("LOW_TENDER_ACCEPTANCE")
        if r["safety_rating"] == "CONDITIONAL":
            flags.append("CONDITIONAL_SAFETY_RATING")
        if r["insurance_expiry_date"] and str(r["insurance_expiry_date"]) < end_s:
            flags.append("INSURANCE_EXPIRED")
        if (r["loads"] or 0) < 15:
            flags.append("LOW_SAMPLE_SIZE")
        r["flags"] = flags
    return ok(rows, window=[str(start), str(end)])


@safe
def get_tender_acceptance(days: int = 90, dc_id: str = "") -> dict:
    """Tender acceptance, rejection and expiry rates per carrier.

    Args:
        days: Lookback window in days.
        dc_id: Optional origin DC filter.

    Returns:
        Per carrier: tenders, accepted, rejected, expired, acceptance_pct, avg response minutes.
    """
    start, end = window(days)
    rows = run("""
        SELECT t.carrier_id, c.carrier_name, COUNT(*) AS tenders,
               SUM(CASE WHEN t.response = 'ACCEPTED' THEN 1 ELSE 0 END) AS accepted,
               SUM(CASE WHEN t.response = 'REJECTED' THEN 1 ELSE 0 END) AS rejected,
               SUM(CASE WHEN t.response = 'EXPIRED' THEN 1 ELSE 0 END) AS expired,
               1.0 * SUM(CASE WHEN t.response = 'ACCEPTED' THEN 1 ELSE 0 END) / COUNT(*) AS acceptance_pct,
               AVG(t.response_minutes) AS avg_response_minutes
        FROM {p}carrier_tenders t
        JOIN {p}carriers c ON c.carrier_id = t.carrier_id
        JOIN {p}loads l ON l.load_id = t.load_id
        WHERE t.tender_date BETWEEN :start AND :end AND (:dc_id = '' OR l.origin_dc_id = :dc_id)
        GROUP BY t.carrier_id, c.carrier_name
        ORDER BY acceptance_pct ASC
    """, {"start": start, "end": end, "dc_id": dc_id.upper()})
    return ok(rows, window=[str(start), str(end)])


@safe
def recommend_carriers(origin_dc_id: str, dest_state: str, equipment_type: str = "DRY_53", days: int = 90) -> dict:
    """Ranks carriers for a lane (origin DC -> destination state) and equipment type.

    Score = 50% on-time + 25% cost per mile (cheaper is better) + 25% tender acceptance,
    computed from this lane's history where available, otherwise the carrier's network history.

    Args:
        origin_dc_id: Origin DC, e.g. 'DC01'.
        dest_state: Two letter destination state, e.g. 'OK'.
        equipment_type: DRY_53, REEFER_53, MULTI_TEMP_53 or PUP_28.
        days: Lookback window in days.

    Returns:
        Ranked carriers with lane_loads, on_time_pct, cost_per_mile, acceptance_pct, score, basis.
    """
    equipment_type = equipment_type.upper()
    if equipment_type not in EQUIPMENT:
        return fail(f"equipment_type must be one of {sorted(EQUIPMENT)}")
    start, end = window(days)
    params = {"start": start, "end": end, "dc": origin_dc_id.upper(), "st": dest_state.upper(),
              "equip": f"%{equipment_type}%"}
    rows = run("""
        WITH lane AS (
            SELECT l.carrier_id, COUNT(DISTINCT l.load_id) AS lane_loads,
                   1.0 * SUM(CASE WHEN s.on_time_flag THEN 1 ELSE 0 END) / COUNT(*) AS lane_on_time,
                   1.0 * SUM(l.total_cost) / NULLIF(SUM(l.total_miles), 0) AS lane_cpm_raw
            FROM {p}loads l JOIN {p}stops s ON s.load_id = l.load_id
            WHERE l.load_status = 'COMPLETED' AND l.load_date BETWEEN :start AND :end
              AND l.origin_dc_id = :dc AND l.dest_region_state = :st
            GROUP BY l.carrier_id
        ), net AS (
            SELECT l.carrier_id,
                   1.0 * SUM(CASE WHEN s.on_time_flag THEN 1 ELSE 0 END) / COUNT(*) AS net_on_time
            FROM {p}loads l JOIN {p}stops s ON s.load_id = l.load_id
            WHERE l.load_status = 'COMPLETED' AND l.load_date BETWEEN :start AND :end
            GROUP BY l.carrier_id
        ), cpm AS (
            SELECT carrier_id, 1.0 * SUM(total_cost) / NULLIF(SUM(total_miles), 0) AS net_cpm
            FROM {p}v_load_profitability WHERE load_date BETWEEN :start AND :end GROUP BY carrier_id
        ), tnd AS (
            SELECT carrier_id, 1.0 * SUM(CASE WHEN response = 'ACCEPTED' THEN 1 ELSE 0 END) / COUNT(*) AS acceptance_pct
            FROM {p}carrier_tenders WHERE tender_date BETWEEN :start AND :end GROUP BY carrier_id
        )
        SELECT c.carrier_id, c.carrier_name, c.carrier_type, c.safety_rating, c.contract_rate_per_mile,
               COALESCE(lane.lane_loads, 0) AS lane_loads, lane.lane_on_time, net.net_on_time,
               lane.lane_cpm_raw, cpm.net_cpm, tnd.acceptance_pct
        FROM {p}carriers c
        LEFT JOIN lane ON lane.carrier_id = c.carrier_id
        LEFT JOIN net ON net.carrier_id = c.carrier_id
        LEFT JOIN cpm ON cpm.carrier_id = c.carrier_id
        LEFT JOIN tnd ON tnd.carrier_id = c.carrier_id
        WHERE c.equipment_types LIKE :equip AND (lane.lane_loads IS NOT NULL OR net.net_on_time IS NOT NULL)
    """, params)
    if not rows:
        return ok([], note="No carrier history for this equipment type in the window.")
    for r in rows:
        r["on_time_pct"] = r["lane_on_time"] if r["lane_loads"] >= 3 else r["net_on_time"]
        r["cost_per_mile"] = r["lane_cpm_raw"] if r["lane_loads"] >= 3 else r["net_cpm"]
        r["basis"] = "lane history" if r["lane_loads"] >= 3 else "network history"
    cpms = [r["cost_per_mile"] for r in rows if r["cost_per_mile"]]
    lo, hi = (min(cpms), max(cpms)) if cpms else (0, 1)
    for r in rows:
        otp = r["on_time_pct"] or 0
        cost_score = 1 - ((r["cost_per_mile"] or hi) - lo) / ((hi - lo) or 1)
        acc = r["acceptance_pct"] if r["acceptance_pct"] is not None else 1.0  # private fleet always accepts
        penalty = 0.1 if r["safety_rating"] == "CONDITIONAL" else 0
        r["score"] = round(100 * (0.5 * otp + 0.25 * cost_score + 0.25 * acc - penalty), 1)
        for k in ("lane_on_time", "net_on_time", "lane_cpm_raw", "net_cpm"):
            r.pop(k, None)
    rows.sort(key=lambda r: -r["score"])
    return ok(rows, lane=f"{origin_dc_id.upper()}->{dest_state.upper()}", equipment_type=equipment_type,
              window=[str(start), str(end)])


def _guardrails() -> tuple[float, float]:
    import os

    return (float(os.getenv("TMS_AUTO_TENDER_MAX_USD", "2500")),
            float(os.getenv("TMS_AUTO_TENDER_MIN_CONFIDENCE", "0.80")))


def evaluate_load_options(load_id: str, days: int = 90) -> dict:
    """Core scoring used by recommend_carrier_for_load and tender_load (never trusts model-supplied numbers)."""
    from tms_agent.db import get_backend

    load = run("""
        SELECT l.load_id, l.load_date, l.origin_dc_id, l.dest_region_state, l.equipment_type, l.stop_count,
               l.total_miles, l.carrier_id AS current_carrier_id, l.load_status, dc.padd_region
        FROM {p}loads l JOIN {p}locations dc ON dc.location_id = l.origin_dc_id WHERE l.load_id = :id
    """, {"id": load_id.upper()})
    if not load:
        raise ValueError(f"Load {load_id} not found")
    ld = load[0]
    start, end = window(days)
    miles, stops = float(ld["total_miles"]), int(ld["stop_count"])
    wk = get_backend().week(":d")
    diesel = run(f"SELECT diesel_price_per_gal FROM {{p}}fuel_prices WHERE padd_region = :padd AND week_start_date = {wk}",
                 {"padd": ld["padd_region"], "d": ld["load_date"] if not isinstance(ld["load_date"], str)
                  else __import__("datetime").date.fromisoformat(ld["load_date"][:10])})
    diesel_price = float(diesel[0]["diesel_price_per_gal"]) if diesel else None
    fuel = miles * max(0.0, ((diesel_price or 3.8) - 1.25) / 6.0)
    ranked = recommend_carriers(ld["origin_dc_id"], ld["dest_region_state"], ld["equipment_type"], days)
    if ranked["status"] != "success":
        raise ValueError(ranked.get("error_message"))
    rates = {r["carrier_id"]: r for r in run("""
        SELECT carrier_id, rate_id, rate_per_mile, stop_charge, min_charge FROM {p}carrier_rates
        WHERE origin_dc_id = :dc AND dest_state = :st AND equipment_type = :eq
    """, {"dc": ld["origin_dc_id"], "st": ld["dest_region_state"], "eq": ld["equipment_type"]})}
    private_cpm = run("""
        SELECT 1.0 * SUM(total_cost) / NULLIF(SUM(total_miles), 0) AS cpm FROM {p}v_load_profitability
        WHERE carrier_id = 'MCLN' AND origin_dc_id = :dc AND load_date BETWEEN :start AND :end
    """, {"dc": ld["origin_dc_id"], "start": start, "end": end})[0]["cpm"]
    capacity = run("""
        SELECT (SELECT COUNT(*) FROM {p}drivers WHERE home_dc_id = :dc AND status = 'ACTIVE')
             - (SELECT COUNT(DISTINCT driver_id) FROM {p}loads WHERE origin_dc_id = :dc AND load_date = :d
                AND driver_id IS NOT NULL AND load_id <> :id) AS free_drivers
    """, {"dc": ld["origin_dc_id"], "d": ld["load_date"] if not isinstance(ld["load_date"], str)
          else __import__("datetime").date.fromisoformat(ld["load_date"][:10]), "id": ld["load_id"]})[0]["free_drivers"]
    options = []
    for c in ranked["data"]:
        cid = c["carrier_id"]
        if cid == "MCLN":
            if not private_cpm or (capacity or 0) <= 0:
                continue
            cost, basis = float(private_cpm) * miles, "private fleet cost/mile at this DC (90d)"
        elif cid in rates:
            r = rates[cid]
            cost = max(float(r["min_charge"]), miles * float(r["rate_per_mile"]) + stops * float(r["stop_charge"])) + fuel
            basis = f"contract {r['rate_id']} + DOE fuel surcharge"
        else:
            cost = miles * float(c["contract_rate_per_mile"] or 2.5) * 1.35 + stops * 40 + fuel
            basis = "SPOT estimate (no lane contract, +35% premium)"
        options.append({**c, "expected_cost_usd": round(cost, 2), "cost_basis": basis})
    # Re-score cost on the load's actual expected cost.
    costs = [o["expected_cost_usd"] for o in options]
    lo, hi = (min(costs), max(costs)) if costs else (0, 1)
    for o in options:
        cost_score = 1 - (o["expected_cost_usd"] - lo) / ((hi - lo) or 1)
        acc = o["acceptance_pct"] if o["acceptance_pct"] is not None else 1.0
        penalty = 0.1 if o["safety_rating"] == "CONDITIONAL" else 0
        o["score"] = round(100 * (0.5 * (o["on_time_pct"] or 0) + 0.25 * cost_score + 0.25 * acc - penalty), 1)
    options.sort(key=lambda o: -o["score"])
    return {"load": {**ld, "doe_diesel": diesel_price, "free_private_drivers": capacity}, "options": options}


@safe
def recommend_carrier_for_load(load_id: str) -> dict:
    """Recommends the best carrier (or private fleet) for one load, with reasoning, confidence and $ impact.

    Considers lane on-time history, expected cost from the contract rate table + DOE fuel surcharge
    (or private fleet cost per mile and driver capacity), tender acceptance and safety rating.

    Args:
        load_id: Load number, e.g. 'LGH0005498'.

    Returns:
        recommended option, alternatives, confidence, $ and on-time impact versus the currently
        assigned carrier, and whether guardrails allow auto-tender.
    """
    ev = evaluate_load_options(load_id)
    opts, ld = ev["options"], ev["load"]
    if not opts:
        return fail("No eligible carrier for this lane and equipment.")
    best = opts[0]
    runner_up = opts[1]["score"] if len(opts) > 1 else 0
    gap = best["score"] - runner_up
    confidence = 0.5 + 0.25 * min(1.0, best["lane_loads"] / 15) + 0.25 * min(1.0, gap / 10)
    if "SPOT" in best["cost_basis"]:
        confidence -= 0.15
    confidence = round(max(0.0, min(0.99, confidence)), 2)
    current = next((o for o in opts if o["carrier_id"] == ld["current_carrier_id"]), None)
    impact = None
    if current and current["carrier_id"] != best["carrier_id"]:
        impact = {"vs_current_carrier": current["carrier_id"],
                  "cost_savings_usd": round(current["expected_cost_usd"] - best["expected_cost_usd"], 2),
                  "on_time_pct_change_pts": round(((best["on_time_pct"] or 0) - (current["on_time_pct"] or 0)) * 100, 1)}
    max_usd, min_conf = _guardrails()
    blockers = []
    if best["expected_cost_usd"] > max_usd:
        blockers.append(f"cost ${best['expected_cost_usd']:,.0f} > auto-tender cap ${max_usd:,.0f}")
    if confidence < min_conf:
        blockers.append(f"confidence {confidence:.0%} < {min_conf:.0%}")
    if best["safety_rating"] == "CONDITIONAL":
        blockers.append("carrier has CONDITIONAL safety rating")
    return ok({
        "load": ld, "recommended": best, "alternatives": opts[1:4], "confidence": confidence,
        "impact": impact,
        "reasoning": (f"{best['carrier_name']} scores {best['score']} (on-time {best['on_time_pct']:.1%} on "
                      f"{best['basis']}, expected cost ${best['expected_cost_usd']:,.0f} via {best['cost_basis']}); "
                      f"next best scores {runner_up}."),
        "guardrails": {"auto_tender_allowed": not blockers, "blockers": blockers,
                       "max_auto_tender_usd": max_usd, "min_confidence": min_conf},
    })
