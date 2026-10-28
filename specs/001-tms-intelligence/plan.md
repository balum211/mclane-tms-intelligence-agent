# Implementation Plan: TMS Intelligence layer for Trimble TMW

**Branch**: `001-tms-intelligence` | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)

## Summary
A Google ADK coordinator with six specialist `LlmAgent`s (exposed through `AgentTool`) and 30
Python function tools over a TMW-shaped warehouse in BigQuery or AlloyDB (DuckDB locally). Synthetic
data with planted stories drives the demo and the tests. It deploys to Vertex AI Agent Engine and is
registered in Gemini Enterprise.

## Technical Context
**Language/Version**: Python 3.11+
**Primary Dependencies**: google-adk 2.x, google-genai, google-cloud-bigquery, psycopg 3 + psycopg-pool, duckdb
**Storage**: BigQuery dataset `mclane_tms` or AlloyDB schema `tms`. DuckDB file for local / tests
**Testing**: pytest + pytest-asyncio; scripted `BaseLlm` through `google.adk.runners.Runner`; ADK eval set
**Target Platform**: Vertex AI Agent Engine (primary), Cloud Run (alternative), Gemini Enterprise UI
**Performance Goals**: Curated tools < 2 s on BigQuery for 90-day windows; delay model trains in < 1 s in-process
**Constraints**: Read-only data access; 5 GB max bytes billed per BigQuery query; 30 s AlloyDB statement timeout
**Scale/Scope**: Synthetic 5.5k loads / 30k stops, linear to production volume via partitioned tables

## Constitution Check
- Grounded answers: tools return structured data with windows ✅
- Recommendation contract: `reasoning`, `confidence`, `impact`, `window` fields ✅
- Read-only + guarded actions: sql_guard, read-only transactions, tender guardrails + ADK confirmation ✅
- One schema, three backends: `schema.py` → `ddl.py`; portable SQL + `week()` / `dow()` hooks ✅
- Test-first, offline-first: 67 offline tests, 2 PostgreSQL tests ✅

## Project Structure
```
tms_agent/  agent.py prompts.py schema.py db.py sql_guard.py decision_log.py
            tools/{analytics,exceptions,predict,audit,cost,carrier,tender,fleet,kpi,insights,common}.py
tms_data/   generate.py ddl.py load.py sample_invoices.py
tests/      conftest.py test_data.py test_tools.py test_capabilities.py test_agent_e2e.py test_sql_guard.py test_ddl.py test_postgres.py
evals/      build_evalset.py tms_core.evalset.json test_config.json run_offline_evals.py
deployment/ setup_gcp.sh deploy_agent_engine.sh deploy_cloud_run.sh register_gemini_enterprise.sh
sql/        bigquery_schema.sql alloydb_schema.sql bigquery_ml_delay_model.sql sample_questions.sql
```

## Agent design
| Agent | Tools |
|---|---|
| tms_intelligence (root) | get_ops_kpi_snapshot, get_weekly_insights_pack, tender_load, get_decision_log, 6 x AgentTool |
| service_exceptions_analyst | get_open_exceptions, get_late_delivery_summary, get_detention_hotspots, get_at_risk_loads, get_reefer_excursions, predict_load_delays, get_delay_model_card |
| freight_audit_analyst | audit_carrier_invoices, get_invoice_audit_detail, recommend_invoice_dispute, extract_and_audit_invoice_document |
| freight_cost_analyst | get_lane_profitability, get_load_margin_outliers, get_accessorial_leakage, get_fuel_surcharge_recovery, get_cost_breakdown, get_spot_vs_contract_premium |
| carrier_performance_analyst | get_carrier_scorecard, get_tender_acceptance, recommend_carriers, recommend_carrier_for_load |
| fleet_operations_analyst | get_driver_hos_status, get_fleet_utilization, get_maintenance_due |
| tms_data_analyst | get_tms_schema, run_tms_sql |

`tender_load` lives on the root agent so the ADK confirmation request reaches the user directly.

## Complexity Tracking
| Choice | Why | Simpler alternative rejected |
|---|---|---|
| Explainable target-encoding delay model in-process | Runs on any backend with zero infra, explains every prediction | Vertex AutoML: better accuracy, but needs training infra (BQML path provided) |
| Python tools rather than MCP Toolbox only | Audit / scoring logic does not fit in SQL templates | `tools.yaml` (MCP Toolbox) is still provided for Antigravity / Gemini CLI use |
