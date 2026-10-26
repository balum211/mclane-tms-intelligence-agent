# Tasks: TMS Intelligence layer for Trimble TMW

All tasks are complete in this branch. [P] = can run in parallel.

## Phase 1: Setup
- [x] T001 Project skeleton, `pyproject.toml`, `tms_agent/` ADK package, `.env.example`
- [x] T002 Canonical schema `tms_agent/schema.py` (18 tables, 3 views, TMW mapping)
- [x] T003 [P] DDL renderer `tms_data/ddl.py` for BigQuery / AlloyDB / DuckDB
- [x] T004 [P] Backends `tms_agent/db.py` with `{p}` prefix, `:param` rewriting, `week()` / `dow()` hooks

## Phase 2: Foundational data
- [x] T005 Synthetic generator `tms_data/generate.py` with 8 planted stories + invoice ground truth
- [x] T006 Loaders `tms_data/load.py` (DuckDB, BigQuery, AlloyDB COPY)
- [x] T007 Data tests: PK/FK integrity, totals, planted stories (`tests/test_data.py`)

## Phase 3: US1 Ask the TMS anything (P1)
- [x] T008 SQL guard + tests (`sql_guard.py`, `tests/test_sql_guard.py`)
- [x] T009 `get_tms_schema`, `run_tms_sql`; tms_data_analyst agent
- [x] T010 [P] Exceptions, cost, carrier, fleet, KPI tools + tests

## Phase 4: US2 Freight invoice audit (P1)
- [x] T011 `carrier_rates`, `carrier_invoices` in schema + generator (errors, scans, spot loads)
- [x] T012 Audit rules + NEEDS_REVIEW handling (`tools/audit.py`)
- [x] T013 Gemini PDF extraction `extract_and_audit_invoice_document` + offline test of the audit path
- [x] T014 Sample invoice PDFs (`tms_data/sample_invoices.py`)

## Phase 5: US3 Carrier recommendation + guardrailed tender (P1)
- [x] T015 `recommend_carrier_for_load` (contract / spot / private fleet cost, capacity, confidence)
- [x] T016 `tender_load` with ADK `request_confirmation` + decision log
- [x] T017 Runner test: `adk_request_confirmation` emitted above the cap

## Phase 6: US4 Delay prediction (P2)
- [x] T018 Explainable model with leave-one-out receiver risk (`tools/predict.py`)
- [x] T019 Model card on a time-based holdout; BigQuery ML version (`sql/bigquery_ml_delay_model.sql`)

## Phase 7: US5 Weekly insights (P3)
- [x] T020 `get_weekly_insights_pack`, `get_spot_vs_contract_premium`

## Phase 8: Polish
- [x] T021 Coordinator prompt, recommendation contract, AgentTool wiring (`agent.py`, `prompts.py`)
- [x] T022 ADK eval set + offline evals (`evals/`)
- [x] T023 Deployment scripts (Agent Engine, Cloud Run, Gemini Enterprise)
- [x] T024 Docs: solution design, data story, demo script, deployment; Antigravity prompts + skills
