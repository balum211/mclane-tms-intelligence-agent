"""Invoice audit accuracy, delay model quality, carrier recommendation and tender guardrails."""

import csv

import pytest

from tms_agent.tools import audit, carrier, predict, tender
from tms_agent.tools.common import run


def test_invoice_audit_catches_planted_overbilling(tms_duckdb):
    truth = {r["carrier_invoice_id"]: r["error_code"]
             for r in csv.DictReader(open(tms_duckdb["csv"] / "_truth_invoice_errors.csv"))}
    rows = run(audit._audit_sql("1=1"), max_rows=100000)
    results = [audit.audit_invoice_row(r) for r in rows]
    flagged = {a["carrier_invoice_id"]: [f["code"] for f in a["findings"]] for a in results if a["verdict"] == "OVERBILLED"}
    tp = len(set(flagged) & set(truth))
    assert tp / len(flagged) >= 0.95  # precision
    assert tp / len(truth) >= 0.9  # recall
    assert sum(truth[k] in flagged[k] for k in set(flagged) & set(truth)) / tp >= 0.9  # right reason


def test_messy_invoice_is_flagged_not_guessed():
    rows = run(audit._audit_sql("ci.billed_fuel_surcharge IS NULL"), max_rows=5)
    assert rows, "generator should produce scanned invoices with missing fuel surcharge"
    res = audit.audit_invoice_row(rows[0])
    assert any(r.startswith("MISSING_FUEL_SURCHARGE") for r in res["needs_review"])


def test_extracted_document_audit_without_gemini():
    # A contracted invoice, so the +$500 linehaul is checkable (spot loads only go to review).
    inv = run(audit._audit_sql("r.rate_id IS NOT NULL") + " ORDER BY ci.carrier_invoice_id", max_rows=1)[0]
    doc = {"load_id": inv["load_id"], "carrier_invoice_id": "SCAN-1", "billed_rate_per_mile": None,
           "billed_miles": inv["total_miles"], "billed_linehaul": float(inv["billed_linehaul"]) + 500,
           "billed_fuel_surcharge": None, "billed_detention": 0, "billed_lumper": 0,
           "lumper_receipt_attached": None, "illegible_fields": ["fuel surcharge"]}
    out = audit.audit_extracted_invoice(doc)["data"]["audit"]
    assert out["verdict"] == "OVERBILLED" and out["needs_review"]


def test_delay_model_beats_random():
    card = predict.get_delay_model_card()["data"]
    assert card["auc"] > 0.6 and card["top_decile_lift"] > 1.1


def _ctx(confirmed=None):
    class Conf:
        def __init__(self, c):
            self.confirmed = c

    class Ctx:
        def __init__(self):
            self.state, self.hint = {}, None
            self.tool_confirmation = None if confirmed is None else Conf(confirmed)

        def request_confirmation(self, hint=None, payload=None):
            self.hint = hint

    return Ctx()


@pytest.fixture()
def planned_load():
    return run("SELECT load_id FROM {p}loads WHERE load_status IN ('PLANNED', 'DISPATCHED') "
               "AND carrier_id <> 'MCLN' ORDER BY load_id LIMIT 1")[0]["load_id"]


def test_recommend_carrier_for_load_has_reasoning_confidence_impact(planned_load):
    d = carrier.recommend_carrier_for_load(planned_load)["data"]
    assert d["recommended"]["expected_cost_usd"] > 0
    assert 0 <= d["confidence"] <= 1 and d["reasoning"] and "auto_tender_allowed" in d["guardrails"]


def test_tender_above_cap_requires_approval(planned_load, monkeypatch):
    monkeypatch.setenv("TMS_AUTO_TENDER_MAX_USD", "1")
    best = carrier.recommend_carrier_for_load(planned_load)["data"]["recommended"]["carrier_id"]
    ctx = _ctx()
    out = tender.tender_load(planned_load, best, ctx)["data"]
    assert out["status"] == "PENDING_APPROVAL" and ctx.hint
    assert tender.tender_load(planned_load, best, _ctx(confirmed=True))["data"]["status"] == "APPROVED"
    assert tender.tender_load(planned_load, best, _ctx(confirmed=False))["data"]["status"] == "REJECTED"
    statuses = [d["status"] for d in tender.get_decision_log(10)["data"]]
    assert {"PENDING_APPROVAL", "APPROVED", "REJECTED"} <= set(statuses)


def test_tender_completed_load_is_blocked():
    lid = run("SELECT load_id FROM {p}loads WHERE load_status = 'COMPLETED' ORDER BY load_id LIMIT 1")[0]["load_id"]
    opts = carrier.evaluate_load_options(lid)["options"]
    out = tender.tender_load(lid, opts[0]["carrier_id"], _ctx())["data"]
    assert out["status"] == "BLOCKED"
