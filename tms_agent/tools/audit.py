"""Freight invoice audit: carrier freight bills vs contracted rates, accessorial rules and evidence.

Rules (deterministic, explainable):
  MILES_INFLATED         billed miles > TMS planned miles + 2%
  RATE_ABOVE_CONTRACT    billed rate per mile > contract rate + 1%
  LINEHAUL_MISMATCH      billed linehaul above contract linehaul for another reason
  FUEL_ABOVE_TABLE       fuel surcharge > (DOE price for the load week - base) / mpg * miles + 3%
  DETENTION_NO_EVIDENCE  detention billed but stops show no time beyond free time
  DUPLICATE_ACCESSORIAL  detention billed ~2x the evidenced detention
  DETENTION_OVERBILLED   detention billed above evidenced detention
  LUMPER_NO_RECEIPT      lumper billed without receipt where contract requires one
Data problems are flagged NEEDS_REVIEW (never guessed): NO_CONTRACT_RATE, MISSING_FUEL_SURCHARGE,
ILLEGIBLE_RATE, NO_FUEL_INDEX. Spot loads (no contract) are still checked for miles, fuel, detention
and lumper using the company-standard schedule.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict

from google.adk.tools import ToolContext

from tms_agent.db import get_backend
from tms_agent.decision_log import log_decision
from tms_agent.tools.common import fail, ok, run, safe, window

TOL_USD = 5.0


def _audit_sql(where: str, from_loads: bool = False) -> str:
    """Invoice + contract + DOE + stop evidence. from_loads=True starts from loads (for extracted documents)."""
    wk = get_backend().week("l.load_date")
    if from_loads:
        src, car = "{p}loads l\n    LEFT JOIN {p}carrier_invoices ci ON ci.load_id = l.load_id", "l.carrier_id"
    else:
        src, car = "{p}carrier_invoices ci\n    JOIN {p}loads l ON l.load_id = ci.load_id", "ci.carrier_id"
    return f"""
    WITH det AS (
        SELECT load_id, SUM(COALESCE(detention_minutes, 0)) AS detention_minutes FROM {{p}}stops GROUP BY load_id
    )
    SELECT ci.carrier_invoice_id, l.load_id, {car} AS carrier_id, c.carrier_name, ci.invoice_date, ci.source,
           ci.document_uri, ci.invoice_status, ci.billed_rate_per_mile, ci.billed_miles, ci.billed_linehaul,
           ci.billed_fuel_surcharge, ci.billed_detention, ci.billed_lumper, ci.lumper_receipt_attached,
           ci.billed_other, ci.billed_total,
           l.load_date, l.origin_dc_id, l.dest_region_state, l.equipment_type, l.total_miles, l.stop_count,
           l.origin_dc_id || '->' || l.dest_region_state AS lane,
           r.rate_id, r.rate_per_mile AS contract_rate_per_mile, r.stop_charge, r.min_charge, r.fsc_base_price,
           r.fsc_mpg, r.detention_rate_per_hr, r.lumper_requires_receipt,
           fp.diesel_price_per_gal, det.detention_minutes
    FROM {src}
    JOIN {{p}}carriers c ON c.carrier_id = {car}
    JOIN {{p}}locations dc ON dc.location_id = l.origin_dc_id
    LEFT JOIN {{p}}carrier_rates r ON r.carrier_id = {car} AND r.origin_dc_id = l.origin_dc_id
         AND r.dest_state = l.dest_region_state AND r.equipment_type = l.equipment_type
    LEFT JOIN {{p}}fuel_prices fp ON fp.padd_region = dc.padd_region AND fp.week_start_date = {wk}
    LEFT JOIN det ON det.load_id = l.load_id
    WHERE {where}
    """


def _f(v) -> float:
    return float(v) if v is not None else 0.0


# Company-standard accessorial schedule used when a load moved without a lane contract (spot).
DEFAULT_TERMS = {"fsc_base_price": 1.25, "fsc_mpg": 6.0, "detention_rate_per_hr": 65.0, "lumper_requires_receipt": True}


def audit_invoice_row(r: dict) -> dict:
    """Apply the audit rules to one invoice row (DB row or Gemini-extracted document joined to the load)."""
    findings, review = [], []
    miles = _f(r.get("total_miles"))
    expected = {}
    has_contract = r.get("contract_rate_per_mile") is not None
    terms = {k: (r.get(k) if has_contract and r.get(k) is not None else v) for k, v in DEFAULT_TERMS.items()}
    if r.get("billed_rate_per_mile") is None:
        review.append("ILLEGIBLE_RATE: rate per mile missing on the document.")
    if has_contract:
        rate = _f(r["contract_rate_per_mile"])
        exp_lh = max(_f(r["min_charge"]), miles * rate + _f(r["stop_charge"]) * int(r.get("stop_count") or 0))
        expected["linehaul"] = round(exp_lh, 2)
        over = _f(r.get("billed_linehaul")) - exp_lh
        if over > TOL_USD:
            if _f(r.get("billed_miles")) > miles * 1.02:
                code = "MILES_INFLATED"
                ev = f"billed {r['billed_miles']} mi vs {miles} mi planned in TMS"
            elif r.get("billed_rate_per_mile") is not None and _f(r["billed_rate_per_mile"]) > rate * 1.01:
                code = "RATE_ABOVE_CONTRACT"
                ev = f"billed ${_f(r['billed_rate_per_mile']):.3f}/mi vs contract ${rate:.3f}/mi ({r['rate_id']})"
            else:
                code = "LINEHAUL_MISMATCH"
                ev = f"billed linehaul ${_f(r['billed_linehaul']):,.2f} vs contract ${exp_lh:,.2f}"
            findings.append({"code": code, "overbilled_usd": round(over, 2), "evidence": ev})
    else:
        review.append("NO_CONTRACT_RATE: spot load, rate not verifiable against a contract; route to procurement.")
        if _f(r.get("billed_miles")) > miles * 1.02 and r.get("billed_rate_per_mile") is not None:
            findings.append({"code": "MILES_INFLATED",
                             "overbilled_usd": round((_f(r["billed_miles"]) - miles) * _f(r["billed_rate_per_mile"]), 2),
                             "evidence": f"billed {r['billed_miles']} mi vs {miles} mi planned in TMS"})
    diesel = r.get("diesel_price_per_gal")
    if diesel is None:
        review.append("NO_FUEL_INDEX: DOE price missing for the load week.")
    else:
        exp_fsc = miles * max(0.0, (_f(diesel) - _f(terms["fsc_base_price"])) / _f(terms["fsc_mpg"]))
        expected["fuel_surcharge"] = round(exp_fsc, 2)
        if r.get("billed_fuel_surcharge") is None:
            review.append("MISSING_FUEL_SURCHARGE: fuel surcharge not readable on the document; do not pay until confirmed.")
        elif _f(r["billed_fuel_surcharge"]) > exp_fsc * 1.03 + 2:
            findings.append({"code": "FUEL_ABOVE_TABLE",
                             "overbilled_usd": round(_f(r["billed_fuel_surcharge"]) - exp_fsc, 2),
                             "evidence": f"billed FSC ${_f(r['billed_fuel_surcharge']):,.2f} vs DOE table "
                                         f"${exp_fsc:,.2f} (DOE ${_f(diesel):.3f}/gal)"})
    exp_det = _f(r.get("detention_minutes")) / 60 * _f(terms["detention_rate_per_hr"])
    expected["detention"] = round(exp_det, 2)
    bdet = _f(r.get("billed_detention"))
    if bdet > exp_det + TOL_USD:
        if exp_det < 1:
            code, ev = "DETENTION_NO_EVIDENCE", f"${bdet:,.2f} detention billed; stop records show 0 min beyond free time"
        elif abs(bdet - 2 * exp_det) < TOL_USD:
            code, ev = "DUPLICATE_ACCESSORIAL", f"detention billed twice (${bdet:,.2f} vs ${exp_det:,.2f} evidenced)"
        else:
            code, ev = "DETENTION_OVERBILLED", f"billed ${bdet:,.2f} vs ${exp_det:,.2f} evidenced by stop times"
        findings.append({"code": code, "overbilled_usd": round(bdet - exp_det, 2), "evidence": ev})
    if _f(r.get("billed_lumper")) > 0 and terms["lumper_requires_receipt"] is not False \
            and not r.get("lumper_receipt_attached"):
        findings.append({"code": "LUMPER_NO_RECEIPT", "overbilled_usd": round(_f(r["billed_lumper"]), 2),
                         "evidence": "lumper billed without receipt; receipt required by policy"})
    over_total = round(sum(f["overbilled_usd"] for f in findings), 2)
    verdict = "OVERBILLED" if findings else ("NEEDS_REVIEW" if review else "PASS")
    return {
        "carrier_invoice_id": r.get("carrier_invoice_id"), "load_id": r.get("load_id"), "carrier_id": r.get("carrier_id"),
        "carrier_name": r.get("carrier_name"), "lane": r.get("lane"), "invoice_date": r.get("invoice_date"),
        "source": r.get("source"), "invoice_status": r.get("invoice_status"), "billed_total": r.get("billed_total"),
        "expected": expected, "verdict": verdict, "overbilled_usd": over_total, "findings": findings,
        "needs_review": review,
        "confidence": 0.95 if findings and not review else (0.6 if review else 0.9),
    }


@safe
def audit_carrier_invoices(days: int = 30, carrier_id: str = "", group_by: str = "carrier", limit: int = 15) -> dict:
    """Audits carrier freight bills against contract rates, DOE fuel table and stop evidence.

    Args:
        days: Invoices dated in the last N days.
        carrier_id: Optional carrier filter, e.g. 'CR006'.
        group_by: Summary dimension: carrier, lane or finding (error code).
        limit: Max flagged invoices to return (largest $ first).

    Returns:
        summary (invoices audited, billed $, flagged count, overbilled $, catch rate), a breakdown by
        group_by, and the top flagged invoices with evidence, expected amounts and confidence.
    """
    if group_by not in ("carrier", "lane", "finding"):
        return fail("group_by must be carrier, lane or finding")
    start, end = window(days)
    rows = run(_audit_sql("ci.invoice_date BETWEEN :start AND :end AND (:carrier_id = '' OR ci.carrier_id = :carrier_id)"),
               {"start": start, "end": end, "carrier_id": carrier_id.upper()}, max_rows=100000)
    audited = [audit_invoice_row(r) for r in rows]
    flagged = [a for a in audited if a["verdict"] != "PASS"]
    over = round(sum(a["overbilled_usd"] for a in audited), 2)
    billed = round(sum(_f(a["billed_total"]) for a in audited), 2)
    groups: dict[str, dict] = defaultdict(lambda: {"invoices": 0, "flagged": 0, "overbilled_usd": 0.0, "billed_usd": 0.0})
    for a in audited:
        keys = [f["code"] for f in a["findings"]] or ([] if group_by == "finding" else [None])
        if group_by == "carrier":
            keys = [f"{a['carrier_id']} {a['carrier_name']}"]
        elif group_by == "lane":
            keys = [a["lane"]]
        for k in keys:
            g = groups[k]
            g["invoices"] += 1
            g["billed_usd"] += _f(a["billed_total"])
            if a["verdict"] == "OVERBILLED":
                g["flagged"] += 1
                g["overbilled_usd"] += a["overbilled_usd"] if group_by != "finding" else sum(
                    f["overbilled_usd"] for f in a["findings"] if f["code"] == k)
    breakdown = sorted(({group_by: k, **{kk: round(vv, 2) for kk, vv in v.items()}} for k, v in groups.items()),
                       key=lambda x: -x["overbilled_usd"])
    flagged.sort(key=lambda a: -a["overbilled_usd"])
    days_n = (end - start).days + 1
    return ok({
        "summary": {
            "invoices_audited": len(audited), "billed_usd": billed,
            "overbilled_invoices": sum(a["verdict"] == "OVERBILLED" for a in audited),
            "needs_review_invoices": sum(a["verdict"] == "NEEDS_REVIEW" for a in audited),
            "overbilled_usd": over, "overbilled_pct_of_spend": round(over / billed, 4) if billed else None,
            "annualized_savings_usd": round(over * 365 / days_n, 0),
        },
        "breakdown": breakdown[:15],
        "top_flagged": flagged[: int(limit)],
    }, window=[str(start), str(end)])


@safe
def get_invoice_audit_detail(carrier_invoice_id: str) -> dict:
    """Full audit of one carrier invoice: billed vs expected line by line, findings and evidence.

    Args:
        carrier_invoice_id: Freight bill number, e.g. 'CINV0000123'.
    """
    rows = run(_audit_sql("ci.carrier_invoice_id = :id"), {"id": carrier_invoice_id.upper()})
    if not rows:
        return fail(f"Invoice {carrier_invoice_id} not found")
    r = rows[0]
    return ok({"invoice": {k: r[k] for k in r if k.startswith("billed_") or k in (
        "carrier_invoice_id", "load_id", "carrier_id", "carrier_name", "invoice_date", "source", "document_uri",
        "invoice_status", "lumper_receipt_attached")},
        "tms_evidence": {"lane": r["lane"], "equipment_type": r["equipment_type"], "planned_miles": r["total_miles"],
                         "stops": r["stop_count"], "evidenced_detention_minutes": r["detention_minutes"],
                         "contract": r["rate_id"], "contract_rate_per_mile": r["contract_rate_per_mile"],
                         "doe_diesel": r["diesel_price_per_gal"]},
        "audit": audit_invoice_row(r)})


@safe
def recommend_invoice_dispute(carrier_invoice_id: str, tool_context: ToolContext) -> dict:
    """Re-audits an invoice and logs a dispute recommendation (short-pay to the contract amount).

    Disputes are recommendations for freight audit to approve; nothing is sent to the carrier.

    Args:
        carrier_invoice_id: Freight bill number.
    """
    detail = get_invoice_audit_detail(carrier_invoice_id)
    if detail["status"] != "success":
        return detail
    a = detail["data"]["audit"]
    if a["verdict"] == "PASS":
        return ok({"carrier_invoice_id": a["carrier_invoice_id"], "action": "NONE", "reason": "Invoice passes audit."})
    rec = log_decision(
        "INVOICE_DISPUTE", "PENDING_APPROVAL",
        "; ".join(f"{f['code']}: {f['evidence']}" for f in a["findings"]) or "; ".join(a["needs_review"]),
        load_id=a["load_id"], carrier_id=a["carrier_id"], amount_usd=a["overbilled_usd"], confidence=a["confidence"],
        data_used={"invoice": a["carrier_invoice_id"], "expected": a["expected"]},
    )
    tool_context.state["last_decision_id"] = rec["decision_id"]
    return ok({"decision": rec, "short_pay_usd": a["overbilled_usd"], "audit": a})


_EXTRACT_PROMPT = """Extract the carrier freight invoice fields from this document as JSON.
Use null for any field that is missing or not clearly legible. Never guess numbers."""

_EXTRACT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "carrier_invoice_id": {"type": "STRING", "nullable": True},
        "carrier_name": {"type": "STRING", "nullable": True},
        "scac": {"type": "STRING", "nullable": True},
        "load_id": {"type": "STRING", "nullable": True, "description": "Shipper load / PRO / BOL reference, e.g. LGH0001234"},
        "invoice_date": {"type": "STRING", "nullable": True},
        "billed_rate_per_mile": {"type": "NUMBER", "nullable": True},
        "billed_miles": {"type": "NUMBER", "nullable": True},
        "billed_linehaul": {"type": "NUMBER", "nullable": True},
        "billed_fuel_surcharge": {"type": "NUMBER", "nullable": True},
        "billed_detention": {"type": "NUMBER", "nullable": True},
        "billed_lumper": {"type": "NUMBER", "nullable": True},
        "lumper_receipt_attached": {"type": "BOOLEAN", "nullable": True},
        "billed_other": {"type": "NUMBER", "nullable": True},
        "billed_total": {"type": "NUMBER", "nullable": True},
        "illegible_fields": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
}


@safe
def extract_and_audit_invoice_document(document_uri: str) -> dict:
    """Reads a scanned / PDF carrier invoice with Gemini, then audits it against TMS data.

    Args:
        document_uri: gs://bucket/path.pdf (Vertex AI) or a local file path to a PDF / image.

    Returns:
        The extracted fields (null where illegible), the matched load, and the audit verdict.
    """
    from google import genai
    from google.genai import types

    client = genai.Client()
    mime = "application/pdf" if document_uri.lower().endswith(".pdf") else "image/png"
    if document_uri.startswith("gs://"):
        part = types.Part.from_uri(file_uri=document_uri, mime_type=mime)
    else:
        with open(document_uri, "rb") as fh:
            part = types.Part.from_bytes(data=fh.read(), mime_type=mime)
    resp = client.models.generate_content(
        model=os.getenv("TMS_DOC_MODEL", os.getenv("TMS_MODEL", "gemini-3.5-flash")),
        contents=[part, _EXTRACT_PROMPT],
        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=_EXTRACT_SCHEMA,
                                           temperature=0),
    )
    doc = json.loads(resp.text)
    return audit_extracted_invoice(doc)


def audit_extracted_invoice(doc: dict) -> dict:
    """Audit an extracted invoice dict against the referenced load (testable without Gemini)."""
    if not doc.get("load_id"):
        return ok({"extracted": doc, "verdict": "NEEDS_REVIEW",
                   "needs_review": ["NO_LOAD_REFERENCE: cannot match the invoice to a TMS load."]})
    base = run(_audit_sql("l.load_id = :lid", from_loads=True), {"lid": doc["load_id"].upper()})
    if not base:
        return ok({"extracted": doc, "verdict": "NEEDS_REVIEW", "needs_review": [f"Load {doc['load_id']} not found in TMS."]})
    row = dict(base[0])
    for k, v in doc.items():
        if k.startswith("billed_") or k in ("lumper_receipt_attached", "carrier_invoice_id"):
            row[k] = v
    result = audit_invoice_row(row)
    if doc.get("illegible_fields"):
        result["needs_review"].append(f"Illegible on document: {', '.join(doc['illegible_fields'])}")
        if result["verdict"] == "PASS":
            result["verdict"] = "NEEDS_REVIEW"
    return ok({"extracted": doc, "audit": result})
