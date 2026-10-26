import datetime as dt
import os

import pytest

AS_OF = dt.date(2026, 10, 23)


@pytest.fixture(scope="session", autouse=True)
def tms_duckdb(tmp_path_factory):
    """Generate a small synthetic dataset and load it into DuckDB once per test session."""
    from tms_data.generate import generate
    from tms_data.load import load_duckdb

    root = tmp_path_factory.mktemp("tms")
    counts = generate(root / "csv", days=60, as_of=AS_OF, seed=7, loads_per_dc_day=5)
    db = root / "tms.duckdb"
    load_duckdb(root / "csv", db)
    os.environ["TMS_DB_BACKEND"] = "duckdb"
    os.environ["TMS_DUCKDB_PATH"] = str(db)
    os.environ["TMS_DECISION_LOG_PATH"] = str(root / "decision_log.jsonl")
    from tms_agent.db import get_backend

    get_backend.cache_clear()
    yield {"db": db, "csv": root / "csv", "counts": counts}
    get_backend.cache_clear()
