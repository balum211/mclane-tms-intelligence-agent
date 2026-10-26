# TMS Intelligence agent for Trimble TMW

An AI layer on top of a Trimble TMW transportation management system for a US grocery and
foodservice distributor (convenience retail, grocery and QSR / casual-dining restaurants). It's a
**Google ADK** multi-agent system over **BigQuery** or **AlloyDB**, deployable to **Vertex AI Agent
Engine** and registered in **Gemini Enterprise**. It's built spec-first with **Google Antigravity +
spec-kit** (prompts, spec and skills are included).

Use case 2 of 3 for the McLane hackathon (Oct 27-28, 2026).

| Capability (from the hackathon brief) | How it works | Where |
|---|---|---|
| 1. Best carrier per load, auto-tender within guardrails | Scores lane on-time, contract cost + DOE fuel, tender acceptance, safety and private-fleet capacity. It auto-tenders only when the cost is ≤ $2,500 and confidence is ≥ 80%. Otherwise it pauses for human approval (ADK tool confirmation) | `tools/carrier.py`, `tools/tender.py` |
| 2. Predict delays 24h ahead and suggest mitigations | Explainable model trained on completed loads. It lists the risk drivers and a mitigation for each load. A BigQuery ML version is in `sql/` | `tools/predict.py`, `sql/bigquery_ml_delay_model.sql` |
| 3. Audit freight invoices against contracts | 8 deterministic rules (rate, miles, fuel table, detention evidence, duplicates, lumper receipts). Gemini reads scanned PDFs. Messy data is flagged, never guessed | `tools/audit.py` |
| 4. Natural-language questions answered with SQL | Schema-grounded NL-to-SQL with a read-only guard. The agent shows the SQL it ran | `tools/analytics.py` |
| 5. Weekly insights | KPIs vs the prior week, worst lanes, carrier flags, overbilling, accessorial leakage, spot premium and tomorrow's at-risk loads | `tools/insights.py` |
| Audit log of every decision | JSONL, Cloud Logging, plus an optional BigQuery / AlloyDB `agent_decision_log` table | `decision_log.py` |

The full design (use-case prioritization, data model, agents with evaluation metrics, demo, business
impact) is in [docs/SOLUTION_DESIGN.md](docs/SOLUTION_DESIGN.md).

## Architecture

```mermaid
flowchart LR
  U[Planner / Freight audit / Procurement / Ops leader] -->|chat| GE[Gemini Enterprise]
  GE --> AE[Vertex AI Agent Engine]
  subgraph ADK["ADK agent: tms_intelligence (coordinator)"]
    C[Coordinator<br/>KPI snapshot, weekly pack,<br/>tender_load, decision log]
    C --> S1[service_exceptions_analyst<br/>on-time, detention, at-risk,<br/>24h delay prediction]
    C --> S2[freight_audit_analyst<br/>invoice audit, PDF extraction,<br/>dispute recommendations]
    C --> S3[freight_cost_analyst<br/>lane margin, fuel recovery,<br/>leakage, spot premium]
    C --> S4[carrier_performance_analyst<br/>scorecards, tenders,<br/>per-load recommendation]
    C --> S5[fleet_operations_analyst<br/>HOS, utilization, PM]
    C --> S6[tms_data_analyst<br/>NL-to-SQL, read-only]
  end
  AE --> ADK
  S1 & S2 & S3 & S4 & S5 & S6 --> DB[(BigQuery or AlloyDB<br/>TMW-shaped warehouse)]
  S2 --> GM[Gemini multimodal<br/>invoice PDFs in GCS]
  C --> LOG[(agent_decision_log<br/>+ Cloud Logging)]
  TMW[Trimble TMW<br/>orderheader, legheader, stops,<br/>carrier, paydetail, checkcall] -.nightly / CDC.-> DB
```

## Quick start (local, no cloud needed)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

python -m tms_data.generate          # synthetic TMW data -> data/generated/*.csv (as-of 2026-10-27)
python -m tms_data.load --target duckdb   # -> data/tms.duckdb
pytest -q                            # 67 tests (2 PostgreSQL tests run when TMS_TEST_PG_DSN is set)

cp tms_agent/.env.example tms_agent/.env   # set GOOGLE_CLOUD_PROJECT (Vertex AI) or GOOGLE_API_KEY
adk web .                            # open http://localhost:8000 and pick tms_agent
```

Try these questions:

- "Give me this morning's TMS brief."
- "Which loads departing in the next 24 hours are likely to be late, and what should we do?"
- "Recommend a carrier for load LGH0005494 and tender it."
- "Tender LGH0005494 to CR006." (Redline is blocked by the guardrails, so the agent asks you to approve)
- "How much are carriers overbilling us? Which lanes exceeded contract rate last month and why?"
- "Audit the invoice data/sample_invoices/03_scanned_detention_illegible_fuel_CINV0000072.pdf"
- "Where are we leaving accessorial revenue on the table?"
- "Why is DC03 late on Mondays?"
- "How many stops did we deliver to TacoTrail last week and what was the average dwell?" (NL-to-SQL)
- "Give me the weekly insights."

## Use BigQuery or AlloyDB

```bash
# BigQuery (recommended for Agent Engine)
python -m tms_data.load --target bigquery --project $GOOGLE_CLOUD_PROJECT --dataset mclane_tms
# then in tms_agent/.env: TMS_DB_BACKEND=bigquery, TMS_BQ_PROJECT=..., TMS_BQ_DATASET=mclane_tms

# AlloyDB for PostgreSQL (through the AlloyDB Auth Proxy)
python -m tms_data.load --target alloydb --dsn "postgresql://postgres:$PW@127.0.0.1:5432/postgres"
# then: TMS_DB_BACKEND=alloydb, TMS_ALLOYDB_DSN=...
```

The DDL is generated from one schema definition (`tms_agent/schema.py`). For BigQuery it adds
column descriptions, partitioning and clustering (`sql/bigquery_schema.sql`). For AlloyDB it adds
comments, primary keys and indexes, and the columnar engine is enabled (`sql/alloydb_schema.sql`).
Every tool was tested on DuckDB and on PostgreSQL 16. BigQuery uses the same portable SQL plus
dialect hooks (`db.py`), but it has not been run against a live BigQuery project yet.

## Deploy to Agent Engine and Gemini Enterprise

```bash
PROJECT_ID=my-proj ./deployment/setup_gcp.sh bigquery      # APIs, service account, data, BQML model
PROJECT_ID=my-proj ./deployment/deploy_agent_engine.sh     # adk deploy agent_engine
PROJECT_ID=my-proj PROJECT_NUMBER=... APP_ID=... REASONING_ENGINE=projects/.../reasoningEngines/... \
  ./deployment/register_gemini_enterprise.sh               # or console: Agents > Add agent > Agent Engine
```

Details, IAM and the Cloud Run alternative are in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Build it with Antigravity

- [antigravity/PROMPTS.md](antigravity/PROMPTS.md): ready-to-paste prompts in order (context, spec-kit
  `/speckit.constitution` → `/speckit.implement`, skills, testing, deploy, demo). IDE install steps are skipped.
- `.agents/skills/`: 5 Antigravity skills (TMS SQL analyst, freight invoice audit, synthetic data, ADK tool authoring, ADK deploy).
- `.agents/rules/project-context.md` and `AGENTS.md`: project rules the agent always follows.
- `.specify/memory/constitution.md` and `specs/001-tms-intelligence/`: the spec-kit constitution, spec,
  plan, data model, research and tasks this code implements.

## Repository layout

```
tms_agent/            ADK agent package (adk web / adk deploy target)
  agent.py            root_agent = coordinator + 6 specialists (30 tools)
  prompts.py          system instructions
  schema.py           canonical TMW-style data model (18 tables, 3 views)
  db.py               BigQuery / AlloyDB / DuckDB backends
  sql_guard.py        read-only guard for generated SQL
  decision_log.py     audit trail sinks
  tools/              analytics, exceptions, predict, audit, cost, carrier, tender, fleet, kpi, insights
tms_data/             generate.py (synthetic data), ddl.py, load.py, sample_invoices.py
sql/                  generated BigQuery + AlloyDB DDL, BigQuery ML delay model, sample NL->SQL answers
evals/                ADK eval set (10 cases) + config, offline capability evals
deployment/           GCP setup, Agent Engine, Cloud Run, Gemini Enterprise registration
toolbox/              optional MCP Toolbox for Databases tools.yaml
antigravity/          Antigravity prompt pack
.agents/              Antigravity rules + skills
.specify/, specs/     spec-kit constitution and feature spec
docs/                 solution design, data story, demo script, deployment
```

## Synthetic data

There are 120 days of history, 8 DCs, 18 fictional customer chains and 10 carriers (private fleet
plus contract and broker carriers). That's 5.5k loads, 30k stops, 1.5k carrier freight bills,
telematics pings and exceptions, with 8 operational stories planted for the agent to find. See
[docs/DATA_STORY.md](docs/DATA_STORY.md). Every customer, carrier, driver and document is fictional.
