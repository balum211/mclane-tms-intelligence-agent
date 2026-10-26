import pytest

from tms_agent.sql_guard import UnsafeSQLError, ensure_read_only, with_limit


@pytest.mark.parametrize("sql", [
    "SELECT * FROM loads",
    "with x as (select 1 a) select * from x",
    "SELECT 'DELETE me' AS note FROM loads;",
    "-- comment\nSELECT carrier_id FROM carriers",
])
def test_allows_reads(sql):
    assert ensure_read_only(sql).upper().lstrip().startswith(("SELECT", "WITH"))


@pytest.mark.parametrize("sql", [
    "DELETE FROM loads",
    "SELECT 1; DROP TABLE loads",
    "UPDATE loads SET total_cost = 0",
    "WITH x AS (SELECT 1) INSERT INTO loads SELECT * FROM x",
    "SELECT * FROM read_csv('/etc/passwd')",
    "CREATE TABLE t AS SELECT 1",
    "",
])
def test_blocks_writes(sql):
    with pytest.raises(UnsafeSQLError):
        ensure_read_only(sql)


def test_with_limit_wraps():
    assert with_limit("SELECT 1", 5).endswith("LIMIT 5")
