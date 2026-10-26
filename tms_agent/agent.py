"""TMS Intelligence: a Google ADK multi-agent system over Trimble TMW-style data.

    coordinator (root_agent)
      ├── get_ops_kpi_snapshot, get_weekly_insights_pack, get_decision_log   (direct tools)
      ├── tender_load                  guardrailed auto-tender / human approval (ADK tool confirmation)
      ├── service_exceptions_analyst   (AgentTool) late / detention / at-risk / 24h delay prediction
      ├── freight_audit_analyst        (AgentTool) invoice audit vs contract / DOE / stop evidence, PDFs
      ├── freight_cost_analyst         (AgentTool) lane margin / fuel / accessorial leakage / spot premium
      ├── carrier_performance_analyst  (AgentTool) scorecards / tenders / per-load recommendation
      ├── fleet_operations_analyst     (AgentTool) HOS / utilization / maintenance
      └── tms_data_analyst             (AgentTool) NL-to-SQL over BigQuery / AlloyDB / DuckDB

Run locally:  adk web .     (from the repo root)   or   adk run tms_agent
"""

from __future__ import annotations

import os

from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from google.genai import types

from tms_agent import prompts
from tms_agent.tools.analytics import get_tms_schema, run_tms_sql
from tms_agent.tools.audit import (
    audit_carrier_invoices,
    extract_and_audit_invoice_document,
    get_invoice_audit_detail,
    recommend_invoice_dispute,
)
from tms_agent.tools.carrier import (
    get_carrier_scorecard,
    get_tender_acceptance,
    recommend_carrier_for_load,
    recommend_carriers,
)
from tms_agent.tools.cost import (
    get_accessorial_leakage,
    get_cost_breakdown,
    get_fuel_surcharge_recovery,
    get_lane_profitability,
    get_load_margin_outliers,
)
from tms_agent.tools.exceptions import (
    get_at_risk_loads,
    get_detention_hotspots,
    get_late_delivery_summary,
    get_open_exceptions,
    get_reefer_excursions,
)
from tms_agent.tools.fleet import get_driver_hos_status, get_fleet_utilization, get_maintenance_due
from tms_agent.tools.insights import get_spot_vs_contract_premium, get_weekly_insights_pack
from tms_agent.tools.kpi import get_ops_kpi_snapshot
from tms_agent.tools.predict import get_delay_model_card, predict_load_delays
from tms_agent.tools.tender import get_decision_log, tender_load

MODEL = os.getenv("TMS_MODEL", "gemini-3.5-flash")
SQL_MODEL = os.getenv("TMS_SQL_MODEL", MODEL)


def build_root_agent(model=MODEL, sql_model=SQL_MODEL) -> LlmAgent:
    """Builds the agent tree. `model` may be a model name or an ADK BaseLlm instance."""
    analyst_cfg = types.GenerateContentConfig(temperature=0.1)

    service_exceptions_analyst = LlmAgent(
        name="service_exceptions_analyst",
        model=model,
        description="Late deliveries, on-time %, detention, open exceptions, at-risk in-transit loads, HOS risk, "
        "reefer temperature excursions and shortages.",
        instruction=prompts.EXCEPTIONS_INSTRUCTION,
        tools=[get_open_exceptions, get_late_delivery_summary, get_detention_hotspots, get_at_risk_loads,
               get_reefer_excursions, predict_load_delays, get_delay_model_card],
        generate_content_config=analyst_cfg,
    )

    freight_cost_analyst = LlmAgent(
        name="freight_cost_analyst",
        model=model,
        description="Lane profitability, cost per mile, margin outliers, fuel surcharge recovery and "
        "accessorial billing leakage.",
        instruction=prompts.COST_INSTRUCTION,
        tools=[get_lane_profitability, get_load_margin_outliers, get_accessorial_leakage,
               get_fuel_surcharge_recovery, get_cost_breakdown, get_spot_vs_contract_premium],
        generate_content_config=analyst_cfg,
    )

    carrier_performance_analyst = LlmAgent(
        name="carrier_performance_analyst",
        model=model,
        description="Carrier scorecards, tender acceptance and the best carrier for a lane or a specific load.",
        instruction=prompts.CARRIER_INSTRUCTION,
        tools=[get_carrier_scorecard, get_tender_acceptance, recommend_carriers, recommend_carrier_for_load],
        generate_content_config=analyst_cfg,
    )

    freight_audit_analyst = LlmAgent(
        name="freight_audit_analyst",
        model=model,
        description="Audits carrier freight invoices against contract rates, DOE fuel table and stop evidence; "
        "flags overbilling with $ impact; reads scanned invoice PDFs; drafts disputes.",
        instruction=prompts.AUDIT_INSTRUCTION,
        tools=[audit_carrier_invoices, get_invoice_audit_detail, recommend_invoice_dispute,
               extract_and_audit_invoice_document],
        generate_content_config=analyst_cfg,
    )

    fleet_operations_analyst = LlmAgent(
        name="fleet_operations_analyst",
        model=model,
        description="Private fleet: driver hours of service, utilization by DC and preventive maintenance due.",
        instruction=prompts.FLEET_INSTRUCTION,
        tools=[get_driver_hos_status, get_fleet_utilization, get_maintenance_due],
        generate_content_config=analyst_cfg,
    )

    tms_data_analyst = LlmAgent(
        name="tms_data_analyst",
        model=sql_model,
        description="Answers any ad-hoc TMS data question by writing and running read-only SQL.",
        instruction=prompts.SQL_INSTRUCTION,
        tools=[get_tms_schema, run_tms_sql],
        generate_content_config=types.GenerateContentConfig(temperature=0.0),
    )

    return LlmAgent(
        name="tms_intelligence",
        model=model,
        description="TMS Intelligence for Trimble TMW: service, cost, carrier and fleet insights for "
        "grocery and foodservice distribution.",
        global_instruction=prompts.GLOBAL_INSTRUCTION,
        instruction=prompts.COORDINATOR_INSTRUCTION,
        tools=[
            get_ops_kpi_snapshot,
            get_weekly_insights_pack,
            tender_load,
            get_decision_log,
            AgentTool(agent=service_exceptions_analyst),
            AgentTool(agent=freight_audit_analyst),
            AgentTool(agent=freight_cost_analyst),
            AgentTool(agent=carrier_performance_analyst),
            AgentTool(agent=fleet_operations_analyst),
            AgentTool(agent=tms_data_analyst),
        ],
        generate_content_config=types.GenerateContentConfig(temperature=0.2),
    )


root_agent = build_root_agent()
