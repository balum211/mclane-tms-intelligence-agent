"""McLane operational signals: PC*MILER miles, geofences, dwell time change and Retail vs Restaurant OTD."""

import io
import json

from tms_agent import mileage
from tms_agent.tools import delivery, miles
from tms_agent.tools.common import run


def test_route_times_are_physically_consistent():
    bad = run("""SELECT COUNT(*) AS n FROM {p}stops a JOIN {p}stops b
                 ON a.load_id = b.load_id AND b.stop_sequence = a.stop_sequence + 1
                 WHERE b.arrival_ts < a.departure_ts""")[0]["n"]
    assert bad == 0


def test_restaurant_otd_is_stricter_than_retail_and_dc07_runs_early():
    rows = {r["otd_channel"]: r for r in delivery.get_otd_scorecard(days=60)["data"]}
    assert rows["RETAIL"]["otd_pct"] == rows["RETAIL"]["not_late_pct"]  # early is fine for retail
    assert rows["RESTAURANT"]["otd_pct"] < rows["RESTAURANT"]["not_late_pct"]
    by_dc = delivery.get_otd_scorecard(days=60, group_by="dc", channel="RESTAURANT")["data"]
    worst_early = max(by_dc, key=lambda r: r["early_misses"] / r["stops"])
    assert worst_early["origin_dc_id"] == "DC07"


def test_dwell_change_finds_both_customers():
    res = delivery.get_dwell_time_changes(recent_days=21, baseline_days=35)
    by_name = {r["customer_name"]: r for r in res["data"]}
    assert by_name["Fresh Basket Grocers"]["direction"] == "INCREASE"
    assert by_name["Fresh Basket Grocers"]["change_min"] >= 15
    assert by_name["Cluck & Co Chicken"]["direction"] == "DECREASE"
    assert res["data"][0]["customer_name"] in ("Fresh Basket Grocers", "Cluck & Co Chicken")


def test_geofence_misses_point_to_bad_geocodes_with_suggested_fix():
    res = delivery.get_geofence_compliance(days=60)["data"]
    assert 0.8 < res["geofence_auto_arrival_pct"] < 1.0
    flagged = res["locations_missing_geofence"]
    assert flagged and all(r["geocode_quality"] == "ZIP_CENTROID" for r in flagged)
    fixed = [r for r in flagged if "suggested_latitude" in r]
    assert fixed and all(r["offset_m"] > 1000 for r in fixed)


def test_every_geofence_arrival_has_enter_and_exit():
    missing = run("""SELECT COUNT(*) AS n FROM {p}stops s
                     WHERE s.arrival_source = 'GEOFENCE' AND 2 <> (
                         SELECT COUNT(*) FROM {p}geofence_events g WHERE g.stop_id = s.stop_id)""")[0]["n"]
    assert missing == 0


def test_out_of_route_drivers_are_flagged():
    rows = miles.get_out_of_route_miles(days=60, min_loads=3)["data"]
    flagged = [r for r in rows if r["flag"]]
    assert flagged and all(r["origin_dc_id"] == "DC08" for r in flagged)
    assert all(r["extra_cost_usd"] > 0 for r in flagged)


def test_pcmiler_check_confirms_inflated_miles():
    inv = run("""SELECT ci.load_id FROM {p}carrier_invoices ci JOIN {p}loads l ON l.load_id = ci.load_id
                 WHERE ci.billed_miles > l.total_miles * 1.05 ORDER BY ci.carrier_invoice_id""", max_rows=1)
    assert inv
    res = miles.check_pcmiler_miles(inv[0]["load_id"])["data"]
    assert res["verdict"] == "MILES_INFLATED" and "PC*MILER" in res["evidence"]
    assert res["rerouted_source"] == "ESTIMATE_HAVERSINE"  # no API key in tests: labelled, not passed off as PC*MILER


def test_pcmiler_client_parses_mileage_report(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"], seen["auth"] = req.full_url, req.headers.get("Authorization")
        return io.BytesIO(json.dumps([{"ReportLines": [{"TMiles": "10.0"}, {"TMiles": "1,234.5"}]}]).encode())

    monkeypatch.setenv("PCMILER_API_KEY", "test-key")
    monkeypatch.setattr(mileage.urllib.request, "urlopen", fake_urlopen)
    res = mileage.route_miles([(31.10, -97.34), (30.27, -97.74)])
    assert res == {"miles": 1234.5, "source": "PCMILER_PRACTICAL", "note": ""}
    assert "reports=Mileage" in seen["url"] and "-97.340000%2C31.100000" in seen["url"]  # lon,lat order
    assert seen["auth"] == "test-key"


def test_pcmiler_failure_falls_back_with_label(monkeypatch):
    def boom(req, timeout):
        raise OSError("network down")

    monkeypatch.setenv("PCMILER_API_KEY", "test-key")
    monkeypatch.setattr(mileage.urllib.request, "urlopen", boom)
    res = mileage.route_miles([(31.10, -97.34), (30.27, -97.74)])
    assert res["source"] == "ESTIMATE_HAVERSINE" and "failed" in res["note"]


def test_track_load_projects_arrival():
    lid = run("""SELECT l.load_id FROM {p}loads l JOIN {p}check_calls c ON c.load_id = l.load_id
                 WHERE l.load_status = 'IN_TRANSIT' ORDER BY l.load_id""", max_rows=1)[0]["load_id"]
    res = delivery.track_load(lid)
    assert res["status"] == "success"
    d = res["data"]
    assert d["next_stop"] and d["projected_arrival_ts"] and d["miles_source"] == "ESTIMATE_HAVERSINE"
    assert delivery.track_load("LGH9999999")["status"] == "error"
