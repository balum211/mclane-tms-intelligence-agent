from tms_data.ddl import render


def test_bigquery_ddl_has_partitioning_and_backticks():
    sql = render("bigquery", "my-proj.mclane_tms.")
    assert "CREATE TABLE IF NOT EXISTS `my-proj.mclane_tms.loads`" in sql
    assert "PARTITION BY load_date" in sql
    assert "`my-proj.mclane_tms.v_load_profitability`" in sql
    assert "{p}" not in sql


def test_alloydb_ddl_has_schema_indexes_and_comments():
    sql = render("alloydb", "tms.")
    assert sql.startswith("CREATE SCHEMA IF NOT EXISTS tms;")
    assert "PRIMARY KEY (load_id)" in sql
    assert "CREATE INDEX IF NOT EXISTS ix_loads_load_date" in sql
    assert "COMMENT ON COLUMN tms.loads.load_id" in sql
