"""Builds the ADK eval set for TMS Intelligence (run after changing cases).

    python evals/build_evalset.py
    adk eval tms_agent evals/tms_core.evalset.json --config_file_path evals/test_config.json

Trajectory scoring ignores free-text arguments and checks that the coordinator routed to the
right specialists / tools in order; a rubric-based LLM judge scores the final answer.
"""

import json
from pathlib import Path

from google.adk.evaluation.eval_config import EvalConfig
from google.adk.evaluation.eval_set import EvalSet

HERE = Path(__file__).parent

CASES = [
    ("morning_brief", "Give me this morning's TMS brief.", ["get_ops_kpi_snapshot"],
     "Leads with network KPIs vs prior week (on-time %, margin %, cost per mile) and lists open critical/high exceptions."),
    ("worst_carrier", "Which carrier is hurting our on-time performance the most in the last 90 days?",
     ["carrier_performance_analyst"],
     "Names Redline Freight Brokers (CR006) with its on-time % versus the private fleet, and mentions low tender acceptance or the conditional safety rating."),
    ("invoice_overbilling", "How much are carriers overbilling us and which carriers are the worst?",
     ["freight_audit_analyst"],
     "Reports overbilled dollars and annualized savings, names Redline Freight Brokers as the largest source, and lists the main finding types."),
    ("contract_rate_lanes", "Which lanes exceeded contract rate last month and why?", ["freight_audit_analyst"],
     "Lists lanes with RATE_ABOVE_CONTRACT or MILES_INFLATED findings and explains billed versus contract rate."),
    ("accessorial_leakage", "Where are we leaving accessorial revenue on the table?", ["freight_cost_analyst"],
     "Names BurgerBarn with unbilled detention, gives the recoverable and annualized amounts and recommends detention billing automation."),
    ("unprofitable_lane", "What is our least profitable lane and why?", ["freight_cost_analyst"],
     "Identifies DC05->NV with negative margin and explains high empty miles (deadhead) as the driver."),
    ("tomorrow_risk", "Which loads departing in the next 24 hours are likely to be late?", ["service_exceptions_analyst"],
     "Lists loads with late probability, confidence, risk drivers and a mitigation for each."),
    ("dc03_mondays", "Why is DC03 late on Mondays?", ["service_exceptions_analyst"],
     "Shows DC03 Monday on-time well below other days and attributes it to late dispatch."),
    ("reefer", "Are reefer temperature excursions related to equipment age?", ["service_exceptions_analyst"],
     "Shows excursion rate for 9+ year refrigeration units is many times higher and recommends replacing / repairing the worst trailers."),
    ("adhoc_sql", "How many stops did we deliver to TacoTrail restaurants last week and what was the average dwell time?",
     ["tms_data_analyst"], "Gives a stop count and an average dwell in minutes and shows the SQL it ran."),
]

RUBRICS = [
    ("grounded", "Every number in the response appears to come from tool output; nothing is invented."),
    ("recommendation_contract", "Recommendations state reasoning, data used, a confidence level and a dollar or service impact."),
    ("actionable", "The response ends with at least one concrete next action with an owner."),
]


def build():
    cases = []
    for eval_id, question, tools, expected in CASES:
        cases.append({
            "eval_id": eval_id,
            "conversation": [{
                "invocation_id": f"{eval_id}-1",
                "user_content": {"role": "user", "parts": [{"text": question}]},
                "final_response": {"role": "model", "parts": [{"text": expected}]},
                "intermediate_data": {"tool_uses": [{"name": t, "args": {}} for t in tools]},
            }],
            "session_input": {"app_name": "tms_agent", "user_id": "eval_user", "state": {}},
        })
    eval_set = EvalSet.model_validate({"eval_set_id": "tms_core", "name": "TMS Intelligence core questions",
                                       "eval_cases": cases})
    (HERE / "tms_core.evalset.json").write_text(eval_set.model_dump_json(indent=2, exclude_none=True))
    config = {
        "criteria": {
            "tool_trajectory_avg_score": {"threshold": 0.8, "match_type": "IN_ORDER", "ignore_args": True},
            "rubric_based_final_response_quality_v1": {
                "threshold": 0.7,
                "rubrics": [{"rubric_id": rid, "rubric_content": {"text_property": text}} for rid, text in RUBRICS],
            },
        }
    }
    EvalConfig.model_validate(config)
    (HERE / "test_config.json").write_text(json.dumps(config, indent=2))
    print(f"wrote {len(cases)} eval cases")


if __name__ == "__main__":
    build()
