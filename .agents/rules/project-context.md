---
trigger: always_on
---

# Project Context: mclane-tms-intelligence-agent

**Last Updated**: 2026-10-28
**Updated By**: Feature 002-mclane-delivery-signals

## Project Identity

- **Name**: mclane-tms-intelligence-agent
- **Type**: Google ADK multi-agent app (Python package `tms_agent`) plus data tooling (`tms_data`)
- **Purpose**: AI layer on top of a Trimble TMW TMS: carrier recommendation with guardrailed
  auto-tender, 24h delay prediction, freight invoice audit, NL-to-SQL, weekly insights, and McLane
  delivery signals (Retail vs Restaurant OTD, dwell time change, geofences, PC*MILER miles)
- **Domain**: US grocery / convenience and restaurant (foodservice) distribution. 8 DCs, private
  fleet (carrier `MCLN`) plus contract carriers and brokers. Synthetic data only.

## Technology Stack

### Languages & Versions
- Python: >= 3.11 (3.12 / 3.13 tested; the codelab starter uses 3.12)

### Frameworks & Libraries
- google-adk 2.x (LlmAgent, AgentTool, ToolContext, tool confirmation), google-genai
- uvicorn + ADK `get_fast_api_app` (`server.py`)
- MCP Toolbox for Databases (`tools.yaml`, optional)

### Storage
- BigQuery (recommended with Agent Engine) or AlloyDB for PostgreSQL; DuckDB for local dev and tests

### Testing
- pytest + pytest-asyncio (offline on DuckDB), optional PostgreSQL integration (`TMS_TEST_PG_DSN`),
  ADK eval set in `evals/`

## Project Structure

```
tms_agent/            ADK agent package (root_agent in agent.py), prompts, schema, db backends,
                      sql_guard, decision_log, mileage (PC*MILER client), tools/
tms_data/             generate.py (synthetic TMW data), load.py, ddl.py, sample_invoices.py
tests/                pytest suites (tools, data stories, guard, ADK runner, McLane signals, layout)
evals/                ADK eval set + offline capability evals
sql/                  generated BigQuery / AlloyDB DDL, BigQuery ML delay model, sample NL->SQL
deployment/           setup_gcp.sh, deploy_agent_engine.sh, deploy_cloud_run.sh, register_gemini_enterprise.sh
scripts/              install_into_sdd_starter.sh (copy this agent into an sdd-adk-agents-agy clone)
antigravity/          PROMPTS.md (ready-to-paste prompts), mcp_config.example.json
.agents/              rules/ (this file), skills/ (8 skills), workflows/ (spec-kit slash commands)
.specify/, specs/     spec-kit constitution, templates, scripts and feature specs 001, 002
server.py, tools.yaml, pyproject.toml, uv.lock, .env.example
```

## API Surface

| Method | Path | Purpose |
|--------|------|---------|
| GET | /list-apps | ADK: agent apps found under the repo root (`tms_agent`) |
| POST | /run_sse | ADK: stream agent events for a session (server.py / adk web / Cloud Run) |
| POST | /run | ADK: run a turn and return all events |
| GET/POST | /apps/{app}/users/{user}/sessions/... | ADK session management |
| GET | /dev-ui | ADK web UI (when `web=True`) |

## Runtime Dependency Graph

```
Browser / Gemini Enterprise -> uvicorn :8080 (server.py) or Agent Engine -> ADK root_agent (tms_intelligence)
  -> 7 specialist agents (AgentTool) -> Python tools -> BigQuery | AlloyDB | DuckDB (data/tms.duckdb)
  -> Gemini (Vertex AI, GOOGLE_CLOUD_LOCATION=global)
  -> PC*MILER Web Services (optional, PCMILER_API_KEY)
  -> decision log: JSONL + Cloud Logging (+ BigQuery / AlloyDB table)
Optional: MCP Toolbox :5000 (tools.yaml) -> AlloyDB / BigQuery
```

## Local Dev Runbook

1. `uv sync` (or `pip install -e ".[dev]"`)
2. `uv run python -m tms_data.generate && uv run python -m tms_data.load --target duckdb`
3. `uv run pytest -q`
4. `cp tms_agent/.env.example tms_agent/.env` and set `GOOGLE_CLOUD_PROJECT`
5. `uv run adk web .` and open http://localhost:8000 (or `uv run uvicorn server:app --port 8080`)

## Data Model Overview

### Entities (Cross-Feature)
- **loads** (TMW legheader): trip from a DC; PC*MILER practical `total_miles`, `pcmiler_shortest_miles`,
  `actual_odometer_miles`; relationships: carrier, driver, tractor, trailer, stops
- **stops** (TMW stops): appointment window, arrival / departure, `minutes_late`, `minutes_early`,
  `dwell_minutes`, `detention_minutes`, `arrival_source` (GEOFENCE / DRIVER_MANUAL / CARRIER_EDI214),
  `pcmiler_leg_miles`
- **locations** (TMW company): DCs, stores, restaurants with lat/lon, `geocode_quality`, `geofence_radius_m`
- **geofence_events**: ENTER / EXIT per tracked stop
- **customers**: segment, business_unit (GROCERY = Retail, FOODSERVICE = Restaurant), OTD target, penalty
- **carrier_invoices / carrier_rates / fuel_prices**: freight audit inputs
- **check_calls** (TMW checkcall): ELD pings with reefer temperature
- **agent_decision_log**: every recommendation and action
- Views: `v_stop_service` (incl. `otd_channel`, `otd_flag`), `v_load_profitability`, `v_carrier_scorecard`

### Tool Definitions
- Python tools: 36 across `tms_agent/tools/*.py` (all SELECT except `tender_load` and
  `recommend_invoice_dispute`, which write only to the decision log)
- `tools.yaml` (MCP Toolbox): otd_by_channel, dwell_by_customer, geofence_misses, open_exceptions,
  invoices_above_contract (AlloyDB, SELECT); carrier_scorecard_bq, lane_profitability_bq (BigQuery, SELECT)

## Domain Glossary

| Term | Definition |
|------|-----------|
| TMW | Trimble TMW Suite / TMWSuite, the TMS of record |
| PC*MILER | Trimble mileage and routing engine; TMW stores PC*MILER practical miles per load and stop |
| OTD | On-time delivery. Retail: not after window end. Restaurant: also not > 15 min early |
| Dwell | Minutes from arrival to departure at a stop; detention is dwell beyond 120 free minutes |
| Geofence | Circle around a location; crossing it auto-records arrive / depart |
| ZIP_CENTROID | Approximate geocode; usually breaks the geofence |
| Out-of-route (OOR) | Odometer miles above PC*MILER practical miles |
| AgentTool | ADK wrapper that lets the coordinator call a specialist agent as a tool |
| ToolContext | ADK object for session state and `request_confirmation` (human approval) |

## External Integrations

- **Vertex AI Gemini**: all agents and PDF extraction. Auth: ADC (`gcloud auth application-default login`)
- **BigQuery / AlloyDB**: data. Auth: ADC / `tms_reader` role through the AlloyDB Auth Proxy
- **PC*MILER Web Services**: optional route miles. Auth: API key (`PCMILER_API_KEY`)
- **Gemini Enterprise**: front end for business users, calling the Agent Engine deployment

## Development Workflow

- **Branch Strategy**: spec-kit feature branches `###-feature-name`; specs in `specs/<branch>/`
- **Build Command**: `uv sync`
- **Test Command**: `uv run pytest -q`; `uv run python evals/run_offline_evals.py`
- **Lint Command**: none enforced; keep the existing style

## Architecture Patterns

- **Code Organization**: one module per domain under `tms_agent/tools/`; one specialist agent per domain
- **Error Handling**: tools return `ok(...)` / `fail(...)` dicts via the `@safe` decorator; never raise to the model
- **State Management**: ADK session state through ToolContext; decisions in `agent_decision_log`
- **Naming Conventions**: snake_case tools named `get_*`, `recommend_*`, `audit_*`, `check_*`

## Recent Features

- 001-tms-intelligence: carrier recommendation + guardrailed tender, delay prediction, invoice audit, NL-to-SQL, weekly insights
- 002-mclane-delivery-signals: Retail vs Restaurant OTD, dwell time change, geofences / geocodes, PC*MILER miles, out-of-route

## Configuration

- **Config Files**: `.env` (root, scripts / Toolbox), `tms_agent/.env` (agent runtime), `tools.yaml`, `pyproject.toml`

### Environment Variable Dependency Chain

| Variable | Consumed By | What Breaks If Missing |
|----------|-------------|----------------------|
| GOOGLE_CLOUD_PROJECT | ADK / google-genai, deployment scripts | Gemini calls fail |
| GOOGLE_CLOUD_LOCATION | google-genai | Default `global`; a region without the model returns 404 |
| GOOGLE_GENAI_USE_ENTERPRISE / _VERTEXAI | google-genai | Falls back to the Gemini API key path |
| TMS_DB_BACKEND | tms_agent/db.py | Defaults to duckdb at data/tms.duckdb |
| TMS_BQ_PROJECT / TMS_BQ_DATASET | BigQuery backend | BigQuery backend cannot start |
| TMS_ALLOYDB_DSN | AlloyDB backend | AlloyDB backend cannot start |
| TMS_AUTO_TENDER_MAX_USD / _MIN_CONFIDENCE | tools/tender.py | Defaults $2,500 / 0.80 |
| PCMILER_API_KEY | tms_agent/mileage.py | Re-routed miles are labelled estimates |
| REGION, ALLOYDB_PASSWORD, TOOLBOX_URL | scripts, tools.yaml | Toolbox / AlloyDB setup fails |

## Known Constraints

- BigQuery path is portable SQL but has not been run against a live project in CI.
- The TMW tender write is simulated (EDI 204 not sent); disputes are recommendations only.
- PC*MILER live calls need an account-specific API key and route options.

<!-- MANUAL ADDITIONS START -->
- Follow `AGENTS.md` and `.specify/memory/constitution.md`. Run `uv run pytest -q` before claiming a task is done.
- No auto-action above $2,500 or below 80% confidence without human approval; every decision is logged;
  messy inputs are flagged, never guessed.
<!-- MANUAL ADDITIONS END -->
