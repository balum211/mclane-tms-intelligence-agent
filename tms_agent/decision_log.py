"""Audit trail for every agent recommendation and action.

Each decision is written as a structured log line (picked up by Cloud Logging on Agent Engine /
Cloud Run), appended to a local JSONL file, and optionally streamed into BigQuery
(`TMS_DECISION_LOG_BQ_TABLE=project.dataset.agent_decision_log`) or AlloyDB
(`TMS_DECISION_LOG_ALLOYDB_DSN`, table <schema>.agent_decision_log).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import threading
import uuid
from pathlib import Path

log = logging.getLogger("tms.decisions")
_lock = threading.Lock()

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "decision_log.jsonl"


def _path() -> Path:
    return Path(os.getenv("TMS_DECISION_LOG_PATH", str(_DEFAULT_PATH)))


def log_decision(decision_type: str, status: str, rationale: str, *, load_id: str | None = None,
                 carrier_id: str | None = None, amount_usd: float | None = None, confidence: float | None = None,
                 actor: str = "agent", data_used: dict | None = None) -> dict:
    rec = {
        "decision_id": f"DEC-{uuid.uuid4().hex[:12]}",
        "decision_ts": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "decision_type": decision_type,
        "load_id": load_id,
        "carrier_id": carrier_id,
        "amount_usd": round(float(amount_usd), 2) if amount_usd is not None else None,
        "confidence": round(float(confidence), 3) if confidence is not None else None,
        "status": status,
        "actor": actor,
        "rationale": rationale,
        "data_used": json.dumps(data_used or {}, default=str),
    }
    log.info(json.dumps({"event": "tms_agent_decision", **rec}))
    try:
        p = _path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with _lock, p.open("a") as fh:
            fh.write(json.dumps(rec) + "\n")
    except OSError as e:  # read-only filesystem on some runtimes: structured log still captured
        log.warning("decision log file not writable: %s", e)
    _sink_bigquery(rec)
    _sink_alloydb(rec)
    return rec


def read_decisions(limit: int = 20) -> list[dict]:
    p = _path()
    if not p.exists():
        return []
    lines = p.read_text().strip().splitlines()
    return [json.loads(x) for x in lines[-int(limit):]][::-1]


def _sink_bigquery(rec: dict) -> None:
    table = os.getenv("TMS_DECISION_LOG_BQ_TABLE")
    if not table:
        return
    try:
        from google.cloud import bigquery

        errors = bigquery.Client().insert_rows_json(table, [rec])
        if errors:
            log.warning("BigQuery decision log insert errors: %s", errors)
    except Exception as e:  # noqa: BLE001
        log.warning("BigQuery decision log failed: %s", e)


def _sink_alloydb(rec: dict) -> None:
    dsn = os.getenv("TMS_DECISION_LOG_ALLOYDB_DSN")
    if not dsn:
        return
    schema = os.getenv("TMS_ALLOYDB_SCHEMA", "tms")
    try:
        import psycopg

        cols = ", ".join(rec)
        vals = ", ".join(f"%({k})s" for k in rec)
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute(f"INSERT INTO {schema}.agent_decision_log ({cols}) VALUES ({vals})", rec)
    except Exception as e:  # noqa: BLE001
        log.warning("AlloyDB decision log failed: %s", e)
