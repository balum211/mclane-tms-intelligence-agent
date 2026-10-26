"""Delay prediction for loads departing in the next 24 hours.

Model: smoothed target encoding per pre-departure feature, combined in log-odds space (an
explainable naive-Bayes style scorer). It trains in-process on completed loads in seconds, works
on every backend, and every prediction lists its top risk drivers. For production at scale use
the BigQuery ML logistic regression in sql/bigquery_ml_delay_model.sql or Vertex AI AutoML Tabular.

Label: a completed load is "late" if any delivery stop missed its appointment window.
Features (all known before dispatch): origin DC x day of week, carrier, equipment / reefer unit
age, stop count bucket, riskiest receiver on the route (historical late rate), planned route miles.
"""

from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict
from functools import lru_cache

from tms_agent.db import get_backend
from tms_agent.tools.common import as_of, ok, run, safe

PRIOR_WEIGHT = 20.0  # smoothing strength toward the base rate
FEATURE_WEIGHT = 0.8  # damp double counting of correlated features
_DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def _logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def _load_rows(statuses: str, start: dt.date, end: dt.date) -> list[dict]:
    b = get_backend()
    return run(f"""
        SELECT l.load_id, l.load_date, l.origin_dc_id, {b.dow('l.load_date')} AS dow, l.carrier_id,
               l.equipment_type, l.stop_count, l.total_miles, l.load_status, l.planned_start_ts,
               COALESCE(t.reefer_unit_age_years, 0) AS reefer_age,
               SUM(CASE WHEN s.on_time_flag = FALSE THEN 1 ELSE 0 END) AS late_stops
        FROM {{p}}loads l
        JOIN {{p}}stops s ON s.load_id = l.load_id
        LEFT JOIN {{p}}trailers t ON t.trailer_id = l.trailer_id
        WHERE l.load_status IN ({statuses}) AND l.load_date BETWEEN :start AND :end
        GROUP BY l.load_id, l.load_date, l.origin_dc_id, {b.dow('l.load_date')}, l.carrier_id, l.equipment_type,
                 l.stop_count, l.total_miles, l.load_status, l.planned_start_ts, t.reefer_unit_age_years
    """, {"start": start, "end": end}, max_rows=200000)


def _receiver_risk(start: dt.date, end: dt.date) -> tuple[dict, dict]:
    """Riskiest receiver on each load's route, from stop history in [start, end].

    Uses leave-one-load-out rates so a training load's own stops never inform its own feature
    (avoids target leakage); loads outside the window simply see the full history.
    """
    route = run("""
        SELECT s.load_id, s.location_id,
               CASE WHEN s.arrival_ts IS NULL OR s.delivery_date < :start OR s.delivery_date > :end THEN NULL
                    WHEN s.on_time_flag THEN 0 ELSE 1 END AS late
        FROM {p}stops s JOIN {p}loads l ON l.load_id = s.load_id
        WHERE l.load_date BETWEEN :start AND :horizon
    """, {"start": start, "end": end, "horizon": end + dt.timedelta(days=3)}, max_rows=1000000)
    n: dict[str, int] = defaultdict(int)
    late: dict[str, int] = defaultdict(int)
    for r in route:
        if r["late"] is not None:
            n[r["location_id"]] += 1
            late[r["location_id"]] += r["late"]
    tot = sum(n.values()) or 1
    base = sum(late.values()) / tot
    worst: dict[str, float] = defaultdict(float)
    for r in route:
        loc, own = r["location_id"], r["late"]
        ln, ll = n[loc] - (1 if own is not None else 0), late[loc] - (own or 0)
        worst[r["load_id"]] = max(worst[r["load_id"]], (ll + 5 * base) / (ln + 5))
    return worst, {"base_stop_late_rate": base}


def _features(r: dict, receiver: dict) -> dict:
    stops = int(r["stop_count"] or 0)
    rr = receiver.get(r["load_id"], 0)
    miles = float(r["total_miles"] or 0)
    return {
        "dc_day": f"{r['origin_dc_id']} {_DOW[int(r['dow'])]}",
        "carrier": r["carrier_id"],
        "equipment": f"{r['equipment_type']}{' old-reefer' if int(r['reefer_age'] or 0) >= 9 else ''}",
        "stops": "1-3 stops" if stops <= 3 else ("4-6 stops" if stops <= 6 else "7+ stops"),
        "receiver": "high-risk receiver" if rr >= 0.2 else ("medium-risk receiver" if rr >= 0.12 else "low-risk receivers"),
        "miles": "<250 mi" if miles < 250 else ("250-500 mi" if miles < 500 else "500+ mi"),
    }


class DelayModel:
    def __init__(self, rows: list[dict], receiver: dict):
        self.n = len(rows)
        self.base = sum(1 for r in rows if r["late_stops"] > 0) / max(1, self.n)
        counts: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
        for r in rows:
            y = 1 if r["late_stops"] > 0 else 0
            for f, v in _features(r, receiver).items():
                c = counts[(f, v)]
                c[0] += 1
                c[1] += y
        self.table = {k: ((c[1] + PRIOR_WEIGHT * self.base) / (c[0] + PRIOR_WEIGHT), c[0]) for k, c in counts.items()}

    def score(self, r: dict, receiver: dict) -> dict:
        base_logit = _logit(self.base)
        z, drivers, support = base_logit, [], []
        for f, v in _features(r, receiver).items():
            p, n = self.table.get((f, v), (self.base, 0))
            contrib = FEATURE_WEIGHT * (_logit(p) - base_logit)
            z += contrib
            support.append(n)
            drivers.append({"feature": f, "value": v, "historical_late_rate": round(p, 3), "loads_seen": n,
                            "contribution": round(contrib, 3)})
        prob = 1 / (1 + math.exp(-z))
        drivers.sort(key=lambda d: -d["contribution"])
        confidence = round(min(0.95, 0.55 + 0.4 * min(1.0, min(support) / 50)), 2)
        return {"late_probability": round(prob, 3), "confidence": confidence,
                "top_risk_drivers": [d for d in drivers if d["contribution"] > 0.05][:3]}


@lru_cache(maxsize=4)
def _trained(as_of_date: dt.date, train_days: int, holdout_days: int = 0) -> tuple[DelayModel, dict]:
    end = as_of_date - dt.timedelta(days=1 + holdout_days)
    start = end - dt.timedelta(days=train_days)
    rows = _load_rows("'COMPLETED'", start, end)
    receiver, _ = _receiver_risk(start, end)
    return DelayModel(rows, receiver), receiver


_MITIGATIONS = {
    "carrier": "Re-tender to a higher on-time carrier on this lane (see recommend_carrier_for_load) or move to private fleet.",
    "dc_day": "Pull dispatch forward 60-90 min / pre-stage trailers; this DC-weekday has a late-dispatch pattern.",
    "receiver": "Confirm the receiving appointment today and add dock buffer for the high-risk receiver.",
    "stops": "Split the route or re-sequence so high-tier customers are served first.",
    "equipment": "Swap the trailer: refrigeration units >= 9 years fail far more often (pre-trip reefer check).",
    "miles": "Long route: check HOS plan and add a relay or earlier start.",
}


@safe
def predict_load_delays(horizon_hours: int = 24, min_probability: float = 0.3, limit: int = 20) -> dict:
    """Predicts which planned / dispatched loads departing in the next N hours will deliver late.

    Args:
        horizon_hours: Look-ahead window from the end of the dataset as-of day (default 24).
        min_probability: Only return loads at or above this late probability.
        limit: Max loads.

    Returns:
        At-risk loads with late_probability, confidence, top_risk_drivers and suggested mitigations,
        plus the model's base late rate.
    """
    today = as_of()
    model, _ = _trained(today, 90)
    horizon_end = today + dt.timedelta(days=max(1, math.ceil(horizon_hours / 24)))
    upcoming = _load_rows("'PLANNED', 'DISPATCHED'", today + dt.timedelta(days=1), horizon_end)
    receiver, _ = _receiver_risk(today - dt.timedelta(days=90), today)
    scored = []
    for r in upcoming:
        s = model.score(r, receiver)
        if s["late_probability"] >= min_probability:
            scored.append({
                "load_id": r["load_id"], "load_date": r["load_date"], "planned_start_ts": r["planned_start_ts"],
                "origin_dc_id": r["origin_dc_id"], "carrier_id": r["carrier_id"],
                "equipment_type": r["equipment_type"], "stop_count": r["stop_count"], **s,
                "mitigations": [_MITIGATIONS[d["feature"]] for d in s["top_risk_drivers"]],
            })
    scored.sort(key=lambda x: -x["late_probability"])
    return ok(scored[: int(limit)], upcoming_loads=len(upcoming), flagged=len(scored),
              base_late_rate=round(model.base, 3), trained_on_loads=model.n, as_of_date=str(today))


@safe
def get_delay_model_card(holdout_days: int = 14, threshold: float = 0.3) -> dict:
    """Evaluates the delay model on a time-based holdout (last N days, unseen in training).

    Args:
        holdout_days: Days held out for evaluation.
        threshold: Probability threshold for a 'late' prediction.

    Returns:
        precision, recall, F1, AUC, lift of the top decile and the base late rate.
    """
    today = as_of()
    model, _ = _trained(today, 90, holdout_days)
    test_start = today - dt.timedelta(days=holdout_days)
    rows = _load_rows("'COMPLETED'", test_start, today)
    receiver, _ = _receiver_risk(test_start - dt.timedelta(days=90), test_start - dt.timedelta(days=1))
    preds = [(model.score(r, receiver)["late_probability"], 1 if r["late_stops"] > 0 else 0) for r in rows]
    tp = sum(1 for p, y in preds if p >= threshold and y)
    fp = sum(1 for p, y in preds if p >= threshold and not y)
    fn = sum(1 for p, y in preds if p < threshold and y)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    pos = [p for p, y in preds if y]
    neg = [p for p, y in preds if not y]
    auc = (sum(1.0 if a > b else 0.5 if a == b else 0.0 for a in pos for b in neg) / (len(pos) * len(neg))
           if pos and neg else None)
    ranked = sorted(preds, key=lambda x: -x[0])
    top = ranked[: max(1, len(ranked) // 10)]
    base = sum(y for _, y in preds) / max(1, len(preds))
    return ok({
        "model": "smoothed target-encoding log-odds scorer (explainable)",
        "features": ["origin DC x weekday", "carrier", "equipment / reefer age", "stop count", "riskiest receiver",
                     "route miles"],
        "train_window_days": 90, "holdout_days": holdout_days, "holdout_loads": len(preds), "threshold": threshold,
        "precision": round(precision, 3), "recall": round(recall, 3),
        "f1": round(2 * precision * recall / (precision + recall), 3) if precision + recall else 0.0,
        "auc": round(auc, 3) if auc is not None else None,
        "base_late_rate": round(base, 3),
        "top_decile_late_rate": round(sum(y for _, y in top) / len(top), 3),
        "top_decile_lift": round((sum(y for _, y in top) / len(top)) / base, 2) if base else None,
    })
