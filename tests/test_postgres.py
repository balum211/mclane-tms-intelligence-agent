"""Optional: run every tool against a real PostgreSQL / AlloyDB.

    TMS_TEST_PG_DSN=postgresql://postgres@127.0.0.1:5432/postgres pytest tests/test_postgres.py
"""

import os

import pytest

DSN = os.getenv("TMS_TEST_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="set TMS_TEST_PG_DSN to run against PostgreSQL / AlloyDB")


@pytest.fixture(scope="module")
def pg_backend(tms_duckdb):
    from tms_agent.db import get_backend
    from tms_data.load import load_alloydb

    load_alloydb(tms_duckdb["csv"], DSN, schema="tms_test")
    old = {k: os.environ.get(k) for k in ("TMS_DB_BACKEND", "TMS_ALLOYDB_DSN", "TMS_ALLOYDB_SCHEMA")}
    os.environ.update(TMS_DB_BACKEND="alloydb", TMS_ALLOYDB_DSN=DSN, TMS_ALLOYDB_SCHEMA="tms_test")
    get_backend.cache_clear()
    yield
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    get_backend.cache_clear()


def test_all_tools_on_postgres(pg_backend):
    from test_tools import CALLS

    failures = [(fn.__name__, kw, out.get("error_message")) for fn, kw in CALLS
                if (out := fn(**kw))["status"] != "success"]
    assert not failures


def test_adhoc_sql_with_percent_on_postgres(pg_backend):
    from tms_agent.tools.analytics import run_tms_sql

    class Ctx:
        state = {}

    out = run_tms_sql("SELECT carrier_id FROM tms_test.carriers WHERE carrier_id LIKE 'CR%'", Ctx())
    assert out["status"] == "success" and out["row_count"] > 0
