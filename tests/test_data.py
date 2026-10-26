"""Synthetic data integrity and planted-story checks."""

import duckdb
import pytest

from tms_agent.schema import TABLES


@pytest.fixture(scope="module")
def con(tms_duckdb):
    c = duckdb.connect(str(tms_duckdb["db"]), read_only=True)
    yield c
    c.close()


def q(con, sql):
    return con.execute(sql).fetchall()


def test_every_table_has_rows(con):
    for t in TABLES:
        if t.name == "agent_decision_log":  # filled at runtime by the agent
            continue
        assert q(con, f"SELECT COUNT(*) FROM {t.name}")[0][0] > 0, t.name


def test_primary_keys_unique(con):
    for t in TABLES:
        if t.primary_key:
            dupes = q(con, f"SELECT COUNT(*) - COUNT(DISTINCT {t.primary_key}) FROM {t.name}")[0][0]
            assert dupes == 0, t.name


def test_foreign_keys_resolve(con):
    for t in TABLES:
        for col, ref in t.foreign_keys.items():
            rt, rc = ref.split(".")
            orphans = q(con, f"""SELECT COUNT(*) FROM {t.name} x LEFT JOIN {rt} r ON r.{rc} = x.{col}
                                 WHERE x.{col} IS NOT NULL AND r.{rc} IS NULL""")[0][0]
            assert orphans == 0, f"{t.name}.{col} -> {ref}"


def test_load_totals_match_lines(con):
    diff = q(con, """SELECT MAX(ABS(l.total_cost - c.s)) FROM loads l
                     JOIN (SELECT load_id, SUM(amount) s FROM load_costs GROUP BY 1) c USING (load_id)""")[0][0]
    assert diff < 1.0


def test_story_bad_broker_is_worst_on_time(con):
    rows = q(con, "SELECT carrier_id FROM v_carrier_scorecard WHERE loads >= 30 ORDER BY on_time_pct LIMIT 1")
    assert rows[0][0] == "CR006"


def test_story_burgerbarn_detention_leakage(con):
    name, billed, value = q(con, """
        SELECT cu.customer_name, SUM(i.detention_billed), SUM(s.detention_minutes) / 60.0 * 75
        FROM stops s JOIN invoices i USING (order_id) JOIN customers cu ON cu.customer_id = i.customer_id
        GROUP BY 1 ORDER BY 3 DESC LIMIT 1""")[0]
    assert name == "BurgerBarn" and billed < 0.5 * float(value)


def test_story_dc05_nv_is_worst_lane(con):
    lane = q(con, """SELECT lane FROM v_load_profitability GROUP BY lane HAVING COUNT(*) >= 20
                     ORDER BY SUM(margin) / SUM(total_revenue) LIMIT 1""")[0][0]
    assert lane == "DC05->NV"


def test_story_old_reefers_fail_more(con):
    rows = dict(q(con, """
        SELECT t.reefer_unit_age_years >= 9, 1.0 * COUNT(e.exception_id) / COUNT(DISTINCT l.load_id)
        FROM loads l JOIN trailers t USING (trailer_id)
        LEFT JOIN exceptions e ON e.load_id = l.load_id AND e.exception_type = 'REEFER_TEMP_EXCURSION'
        WHERE t.reefer_unit_age_years IS NOT NULL GROUP BY 1"""))
    assert rows[True] > 4 * rows[False]


def test_in_transit_loads_exist(con):
    assert q(con, "SELECT COUNT(*) FROM loads WHERE load_status = 'IN_TRANSIT'")[0][0] > 0
