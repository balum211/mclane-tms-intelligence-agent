"""Database backends for the TMS agent: BigQuery, AlloyDB (PostgreSQL) or DuckDB.

Select with TMS_DB_BACKEND=bigquery|alloydb|duckdb. All tools write queries with
`{p}` as the table prefix and `:name` parameters; the backend rewrites both.
"""

from __future__ import annotations

import datetime as dt
import decimal
import os
import re
import threading
from functools import lru_cache
from typing import Any

_PARAM = re.compile(r"(?<![:\w]):([a-zA-Z_]\w*)")


def _jsonable(v: Any) -> Any:
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    if isinstance(v, float):
        return round(v, 4)
    return v


class Backend:
    dialect = "ansi"
    prefix = ""

    def query(self, sql: str, params: dict | None = None, max_rows: int = 200) -> list[dict]:
        raise NotImplementedError

    def render(self, sql: str) -> str:
        return sql.replace("{p}", self.prefix)

    # Dialect specific expressions used by the curated tools.
    def week(self, col: str) -> str:
        return f"CAST(date_trunc('week', {col}) AS DATE)"

    def dow(self, col: str) -> str:
        """Day of week, 0 = Sunday ... 6 = Saturday."""
        return f"CAST(EXTRACT(DOW FROM {col}) AS INTEGER)"


class DuckDBBackend(Backend):
    """Local, zero-cloud backend used for development, tests and offline demos."""

    dialect = "duckdb (PostgreSQL-like)"

    def __init__(self, path: str):
        import duckdb

        self.path = path
        self._conn = duckdb.connect(path, read_only=True)
        self._lock = threading.Lock()

    def query(self, sql, params=None, max_rows=200):
        sql = self.render(sql)
        if params:
            sql = _PARAM.sub(r"$\1", sql)
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(sql, params or {})
            cols = [d[0] for d in cur.description]
            rows = cur.fetchmany(max_rows)
        return [{c: _jsonable(v) for c, v in zip(cols, r)} for r in rows]


class BigQueryBackend(Backend):
    dialect = "bigquery (GoogleSQL)"

    def __init__(self, project: str, dataset: str, location: str | None = None,
                 max_bytes_billed: int = 5 * 1024**3):
        from google.cloud import bigquery

        self._bq = bigquery
        self.client = bigquery.Client(project=project, location=location)
        self.prefix = f"`{project}.{dataset}`."
        self.max_bytes_billed = max_bytes_billed

    def render(self, sql: str) -> str:
        # `proj.ds`.table -> `proj.ds.table` keeps BigQuery happy with backticks.
        return re.sub(r"`([^`]+)`\.(\w+)", r"`\1.\2`", sql.replace("{p}", self.prefix))

    def week(self, col: str) -> str:
        return f"DATE_TRUNC({col}, WEEK(MONDAY))"

    def dow(self, col: str) -> str:
        return f"(EXTRACT(DAYOFWEEK FROM {col}) - 1)"

    def _param(self, name, value):
        bq = self._bq
        if isinstance(value, bool):
            return bq.ScalarQueryParameter(name, "BOOL", value)
        if isinstance(value, int):
            return bq.ScalarQueryParameter(name, "INT64", value)
        if isinstance(value, float):
            return bq.ScalarQueryParameter(name, "FLOAT64", value)
        if isinstance(value, dt.datetime):
            return bq.ScalarQueryParameter(name, "TIMESTAMP", value)
        if isinstance(value, dt.date):
            return bq.ScalarQueryParameter(name, "DATE", value)
        return bq.ScalarQueryParameter(name, "STRING", value)

    def query(self, sql, params=None, max_rows=200):
        sql = self.render(sql)
        if params:
            sql = _PARAM.sub(r"@\1", sql)
        cfg = self._bq.QueryJobConfig(
            query_parameters=[self._param(k, v) for k, v in (params or {}).items()],
            maximum_bytes_billed=self.max_bytes_billed,
            labels={"app": "tms-intelligence-agent"},
        )
        rows = self.client.query(sql, job_config=cfg).result(max_results=max_rows)
        return [{k: _jsonable(v) for k, v in dict(r).items()} for r in rows]


class AlloyDBBackend(Backend):
    """AlloyDB for PostgreSQL. Connect through the AlloyDB Auth Proxy or a private IP."""

    dialect = "postgresql (AlloyDB)"

    def __init__(self, dsn: str, schema: str = "tms"):
        from psycopg_pool import ConnectionPool

        import atexit

        self.pool = ConnectionPool(dsn, min_size=1, max_size=5, kwargs={"autocommit": True}, open=True)
        atexit.register(self.pool.close)
        self.prefix = f"{schema}."

    def query(self, sql, params=None, max_rows=200):
        sql = self.render(sql)
        if params:
            sql = _PARAM.sub(r"%(\1)s", sql)
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET statement_timeout = '30s'")
            # Without params psycopg must not parse '%' (e.g. LIKE 'CR%') as placeholders.
            cur.execute(sql, params) if params else cur.execute(sql)
            cols = [d.name for d in cur.description]
            rows = cur.fetchmany(max_rows)
        return [{c: _jsonable(v) for c, v in zip(cols, r)} for r in rows]


@lru_cache(maxsize=1)
def get_backend() -> Backend:
    kind = os.getenv("TMS_DB_BACKEND", "duckdb").lower()
    if kind == "bigquery":
        return BigQueryBackend(
            project=os.environ.get("TMS_BQ_PROJECT") or os.environ["GOOGLE_CLOUD_PROJECT"],
            dataset=os.getenv("TMS_BQ_DATASET", "mclane_tms"),
            location=os.getenv("TMS_BQ_LOCATION", "US"),
        )
    if kind == "alloydb":
        return AlloyDBBackend(dsn=os.environ["TMS_ALLOYDB_DSN"], schema=os.getenv("TMS_ALLOYDB_SCHEMA", "tms"))
    if kind == "duckdb":
        default = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tms.duckdb")
        return DuckDBBackend(os.getenv("TMS_DUCKDB_PATH", default))
    raise ValueError(f"Unknown TMS_DB_BACKEND={kind!r}")
