"""Guardrailed tender action with human-in-the-loop approval and a full audit trail.

Policy (env configurable): auto-tender only when expected cost <= TMS_AUTO_TENDER_MAX_USD (default
$2,500), confidence >= TMS_AUTO_TENDER_MIN_CONFIDENCE (default 0.80) and the carrier is not
CONDITIONAL. Anything else pauses for human approval via ADK tool confirmation. Every outcome is
written to the decision log. The TMW write itself (EDI 204 load tender / TMW API) is simulated.
"""

from __future__ import annotations

from google.adk.tools import ToolContext

from tms_agent.decision_log import log_decision, read_decisions
from tms_agent.tools.carrier import _guardrails, evaluate_load_options, recommend_carrier_for_load
from tms_agent.tools.common import fail, ok, safe


@safe
def tender_load(load_id: str, carrier_id: str, tool_context: ToolContext) -> dict:
    """Tenders a load to a carrier, automatically when within guardrails, otherwise after human approval.

    Cost and confidence are recomputed from data; they are never taken from the conversation.

    Args:
        load_id: Load to tender, e.g. 'LGH0005498'.
        carrier_id: Carrier to tender to, e.g. 'CR003' (or 'MCLN' to assign the private fleet).

    Returns:
        status AUTO_EXECUTED | PENDING_APPROVAL | APPROVED | REJECTED | BLOCKED with the decision record.
    """
    carrier_id = carrier_id.upper()
    rec = recommend_carrier_for_load(load_id)
    if rec["status"] != "success":
        return rec
    ev = evaluate_load_options(load_id)
    option = next((o for o in ev["options"] if o["carrier_id"] == carrier_id), None)
    if option is None:
        return fail(f"{carrier_id} is not an eligible carrier for {load_id} (equipment / capacity / history).")
    status_ld = ev["load"]["load_status"]
    if status_ld not in ("PLANNED", "DISPATCHED"):
        out = log_decision("CARRIER_TENDER", "BLOCKED", f"Load is {status_ld}; only planned loads can be tendered.",
                           load_id=load_id, carrier_id=carrier_id, amount_usd=option["expected_cost_usd"])
        return ok({"status": "BLOCKED", "decision": out})
    is_top = rec["data"]["recommended"]["carrier_id"] == carrier_id
    confidence = rec["data"]["confidence"] if is_top else round(rec["data"]["confidence"] * 0.7, 2)
    max_usd, min_conf = _guardrails()
    blockers = []
    if option["expected_cost_usd"] > max_usd:
        blockers.append(f"cost ${option['expected_cost_usd']:,.0f} above ${max_usd:,.0f} cap")
    if confidence < min_conf:
        blockers.append(f"confidence {confidence:.0%} below {min_conf:.0%}")
    if option["safety_rating"] == "CONDITIONAL":
        blockers.append("CONDITIONAL safety rating")
    if not is_top:
        blockers.append(f"not the top recommendation ({rec['data']['recommended']['carrier_id']})")
    rationale = (f"{option['carrier_name']}: on-time {option['on_time_pct']:.1%} ({option['basis']}), expected "
                 f"${option['expected_cost_usd']:,.2f} ({option['cost_basis']}), score {option['score']}.")
    evidence = {"option": option, "guardrails": {"max_usd": max_usd, "min_confidence": min_conf}, "blockers": blockers}
    common = dict(load_id=load_id, carrier_id=carrier_id, amount_usd=option["expected_cost_usd"],
                  confidence=confidence, data_used=evidence)

    if not blockers:
        out = log_decision("CARRIER_TENDER", "AUTO_EXECUTED", rationale + " Within guardrails: EDI 204 tender sent (simulated).", **common)
        return ok({"status": "AUTO_EXECUTED", "decision": out})

    confirmation = tool_context.tool_confirmation
    if confirmation is None:
        tool_context.request_confirmation(
            hint=f"Approve tender of {load_id} to {carrier_id} for ~${option['expected_cost_usd']:,.0f}? "
                 f"Needs approval because: {'; '.join(blockers)}.",
            payload={"load_id": load_id, "carrier_id": carrier_id},
        )
        out = log_decision("CARRIER_TENDER", "PENDING_APPROVAL", rationale + " Blocked by: " + "; ".join(blockers), **common)
        return ok({"status": "PENDING_APPROVAL", "decision": out, "blockers": blockers})
    if confirmation.confirmed:
        out = log_decision("CARRIER_TENDER", "APPROVED", rationale + " Approved by user: EDI 204 tender sent (simulated).",
                           actor="user", **common)
        return ok({"status": "APPROVED", "decision": out})
    out = log_decision("CARRIER_TENDER", "REJECTED", rationale + " Rejected by user.", actor="user", **common)
    return ok({"status": "REJECTED", "decision": out})


@safe
def get_decision_log(limit: int = 20) -> dict:
    """Returns the most recent agent decisions (tenders, invoice disputes) from the audit log.

    Args:
        limit: Number of recent decisions.
    """
    return ok(read_decisions(limit))
