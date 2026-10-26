"""Shared helpers for the curated TMS tools."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from tms_agent.db import get_backend

log = logging.getLogger(__name__)

SEVERITY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def as_of() -> dt.date:
    """'Today' for the dataset: the latest dispatch date that has activity."""
    rows = get_backend().query(
        "SELECT MAX(load_date) AS d FROM {p}loads WHERE load_status IN ('COMPLETED', 'IN_TRANSIT')"
    )
    d = rows[0]["d"]
    return dt.date.fromisoformat(d[:10]) if isinstance(d, str) else d


def window(days: int) -> tuple[dt.date, dt.date]:
    end = as_of()
    return end - dt.timedelta(days=max(1, int(days)) - 1), end


def run(sql: str, params: dict | None = None, max_rows: int = 200) -> list[dict]:
    return get_backend().query(sql, params or {}, max_rows=max_rows)


def ok(data: Any, **meta) -> dict:
    out = {"status": "success", "data": data}
    out.update(meta)
    return out


def fail(message: str) -> dict:
    log.warning("tool error: %s", message)
    return {"status": "error", "error_message": message}


def safe(fn):
    """Turn exceptions into structured errors the model can reason about."""
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            return fail(f"{type(e).__name__}: {e}")

    return wrapper
