"""Every curated tool runs against the DuckDB backend and returns success."""

import pytest

from tms_agent.tools import analytics, audit, carrier, cost, delivery, exceptions, fleet, insights, kpi, miles, predict

CALLS = [
    (exceptions.get_open_exceptions, {"min_severity": "LOW"}),
    *[(exceptions.get_late_delivery_summary, {"days": 30, "group_by": g})
      for g in ["customer", "dc", "carrier", "day_of_week", "dc_day_of_week", "root_cause"]],
    (exceptions.get_detention_hotspots, {"days": 30}),
    (exceptions.get_at_risk_loads, {}),
    (exceptions.get_reefer_excursions, {"days": 60}),
    (cost.get_lane_profitability, {"days": 30}),
    (cost.get_load_margin_outliers, {"days": 14, "limit": 5}),
    (cost.get_accessorial_leakage, {"days": 60}),
    (cost.get_fuel_surcharge_recovery, {"weeks": 6}),
    (cost.get_cost_breakdown, {"days": 30, "dc_id": "DC04"}),
    (carrier.get_carrier_scorecard, {"days": 60}),
    (carrier.get_tender_acceptance, {"days": 60}),
    (carrier.recommend_carriers, {"origin_dc_id": "DC01", "dest_state": "TX", "equipment_type": "REEFER_53"}),
    (fleet.get_driver_hos_status, {}),
    (fleet.get_fleet_utilization, {"days": 7}),
    (fleet.get_maintenance_due, {"days_ahead": 30}),
    (kpi.get_ops_kpi_snapshot, {"days": 7}),
    (kpi.get_ops_kpi_snapshot, {"days": 7, "dc_id": "DC03"}),
    (analytics.get_tms_schema, {}),
    (audit.audit_carrier_invoices, {"days": 60, "group_by": "carrier"}),
    (audit.audit_carrier_invoices, {"days": 60, "group_by": "lane"}),
    (audit.audit_carrier_invoices, {"days": 60, "group_by": "finding"}),
    (predict.predict_load_delays, {"min_probability": 0.0}),
    (predict.get_delay_model_card, {}),
    (insights.get_spot_vs_contract_premium, {"days": 30}),
    (insights.get_weekly_insights_pack, {}),
    (analytics.get_tms_schema, {"table_names": ["loads"]}),
    *[(delivery.get_otd_scorecard, {"days": 28, "group_by": g}) for g in ["channel", "dc", "customer", "carrier", "week"]],
    (delivery.get_otd_scorecard, {"days": 28, "group_by": "dc", "channel": "RESTAURANT"}),
    *[(delivery.get_dwell_time_changes, {"group_by": g, "min_stops": 5, "min_change_minutes": 0})
      for g in ["customer", "location", "dc", "channel"]],
    (delivery.get_geofence_compliance, {"days": 30}),
    (delivery.get_geofence_compliance, {"days": 30, "dc_id": "DC04"}),
    (miles.get_out_of_route_miles, {"days": 60, "group_by": "driver"}),
    (miles.get_out_of_route_miles, {"days": 60, "group_by": "dc"}),
]


@pytest.mark.parametrize("fn,kwargs", CALLS, ids=[f"{f.__name__}-{i}" for i, (f, _) in enumerate(CALLS)])
def test_tool_success(fn, kwargs):
    out = fn(**kwargs)
    assert out["status"] == "success", out.get("error_message")
    assert out["data"]


def test_bad_arguments_return_structured_errors():
    assert exceptions.get_late_delivery_summary(group_by="planet")["status"] == "error"
    assert carrier.recommend_carriers("DC01", "TX", "SPACESHIP")["status"] == "error"


class _Ctx:
    def __init__(self):
        self.state = {}


def test_run_tms_sql_reads_and_blocks():
    ctx = _Ctx()
    out = analytics.run_tms_sql("SELECT carrier_id, COUNT(*) AS n FROM loads GROUP BY 1", ctx, max_rows=3)
    assert out["status"] == "success" and out["row_count"] == 3 and out["truncated"]
    assert "last_sql" in ctx.state
    bad = analytics.run_tms_sql("DELETE FROM loads", ctx)
    assert bad["status"] == "error" and "guard" in bad["error_message"]


def test_accessorial_leakage_finds_burgerbarn():
    top = cost.get_accessorial_leakage(days=60)["data"][0]
    assert top["customer_name"] == "BurgerBarn"
