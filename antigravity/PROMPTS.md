# Antigravity prompt pack: TMS Intelligence (use case 2)

Ready-to-paste prompts for Google Antigravity, in order. They follow the codelabs *Getting Started
with Antigravity*, *Building with Antigravity*, *Spec-Driven ADK Agent Development with Antigravity
and Spec-kit*, *Beyond vibe coding* and *Antigravity Skills*. **IDE install and sign-in steps are
skipped**: start from an open Antigravity workspace.

How to use this file:

- Open this repo folder as the workspace. Antigravity picks up `AGENTS.md`, `.agents/rules/`,
  `.agents/skills/` and the spec-kit slash commands in `.agents/workflows/` automatically.
- Use the **Agent Manager** in **Planning** mode for anything that changes code, so you get a task
  list and implementation plan to review before it writes files. Use **Fast** mode for questions.
- Review each artifact (plan, task list, walkthrough) and comment on it before you accept it.
- Track A uses the finished code in this repo (fastest path to a demo). Track B rebuilds it
  spec-first from an empty folder with spec-kit, which is what the judges want to see. Track C adds
  the McLane delivery signals (PC*MILER, dwell time change, Retail / Restaurant OTD, geofences and geo
  locations) spec-first, the way `specs/002-mclane-delivery-signals/` was built.
- Commands follow the codelab starter: `uv sync`, `uv run adk web .`, `uv run python server.py`.
- If you work in your own clone of the codelab starter (your sdd-adk-agents-agy project) instead of
  this repo, run A0b first.

### A0. One-time MCP setup (ADK docs server from the spec-kit codelab)

Merge `antigravity/mcp_config.example.json` into `$HOME/.gemini/config/mcp_config.json` (Agent
Manager → MCP servers → Manage → View raw config), then refresh. It needs `uv` on your PATH. The
agent can then look up ADK APIs in `https://adk.dev/llms.txt` instead of guessing.

### A0b. Bring this agent into your sdd-adk-agents-agy project

```text
Run scripts/install_into_sdd_starter.sh <path to my sdd-adk-agents-agy clone> from this repo. Then,
in that project, run the uv add commands it prints, uv sync, and uv run pytest -q. Review
AGENTS.tms.md and tools.tms.yaml it wrote, and merge them into AGENTS.md / tools.yaml with my
approval. Do not overwrite the starter's existing skills or rules.
```

Then in that workspace: "Use the repo-research skill to update .agents/rules/project-context.md
for the TMS agent now in this repository." (The installer backs up the old file first.)

---

## Track A: run, extend and demo this repo

### A1. Orient the agent

```text
Read AGENTS.md, .agents/rules/project-context.md, .specify/memory/constitution.md and
specs/001-tms-intelligence/spec.md and specs/002-mclane-delivery-signals/spec.md. Then give me a
one-page summary of: the 5 capabilities plus the McLane delivery signals, the
ADK agent tree in tms_agent/agent.py, the data backends, and the guardrails. List the assumptions
and open questions from docs/SOLUTION_DESIGN.md section 0. Do not change any files.
```

### A2. Set up and prove it works locally

```text
Run uv sync, then uv run python -m tms_data.generate and
uv run python -m tms_data.load --target duckdb. Run uv run pytest -q and
uv run python evals/run_offline_evals.py. Report the test count, audit precision/recall and delay AUC/lift.
If anything fails, show the error and propose a fix before changing code.
```

### A3. Try the skills

```text
Use the tms-sql-analyst skill: how many stops did we deliver to TacoTrail restaurants from
2026-10-20 to 2026-10-26 and what was the average dwell? Show the SQL and the result.
```

```text
Use the freight-invoice-audit skill: summarize carrier overbilling for the last 90 days by
carrier, then explain invoice CINV0000069 with the contract evidence.
```

```text
Use the mclane-delivery-signals skill: compare Retail vs Restaurant OTD for the last 28 days by DC,
show where dwell time changed in the last 21 days vs the prior 8 weeks, list locations whose
geofence arrivals are mostly manual with a suggested geocode fix, and rank DC08 drivers by
out-of-route miles against PC*MILER practical miles. Say which miles are PC*MILER and which are
estimates.
```

### A4. Run the agent with the ADK web UI

```text
Copy .env.example to .env and tms_agent/.env.example to tms_agent/.env. Keep
GOOGLE_GENAI_USE_ENTERPRISE=True and GOOGLE_CLOUD_LOCATION=global, set GOOGLE_CLOUD_PROJECT=<my project>
and TMS_DB_BACKEND=duckdb. Start `uv run adk web .` in a terminal and open http://localhost:8000 in the browser agent. Select
tms_agent and ask: "Give me this morning's TMS brief." Then ask "How is Retail vs Restaurant
on-time delivery, and where did dwell time change?" Take a screenshot of the answer and add it to
the walkthrough.
```

### A5. Browser-test the demo script

```text
Using the browser agent on the running adk web UI, run every question in docs/DEMO_SCRIPT.md in
order, in one session. For each, record pass/fail against the expected numbers in the script. For
"Actually, tender it to CR006", confirm the UI shows an approval request, reject it, then ask
"show the decision log" and confirm PENDING_APPROVAL and REJECTED entries. Produce a walkthrough
artifact with screenshots.
```

### A6. Move to BigQuery (or AlloyDB)

```text
Use the tms-synthetic-data skill to load the dataset into BigQuery project <my project>, dataset
mclane_tms (uv run python -m tms_data.load --target bigquery ...). Then switch tms_agent/.env to
TMS_DB_BACKEND=bigquery with TMS_BQ_PROJECT and TMS_BQ_DATASET, and re-run the A4 brief question.
Also run sql/bigquery_ml_delay_model.sql with bq and report the model's ROC AUC.
```

AlloyDB variant:

```text
Use the tms-synthetic-data skill to load AlloyDB through the auth proxy at 127.0.0.1:5432, create a
read-only tms_reader role as described in docs/DEPLOYMENT.md, set TMS_DB_BACKEND=alloydb and
TMS_ALLOYDB_DSN for tms_reader, then run TMS_TEST_PG_DSN=<dsn> uv run pytest tests/test_postgres.py.
```

MCP Toolbox variant (from the spec-kit codelab):

```text
Use the mcp-toolbox-postgres skill. Start MCP Toolbox for Databases with the tools.yaml in this repo
(set ALLOYDB_PASSWORD and REGION in .env), list the tools it serves, and call otd_by_channel and
dwell_by_customer for the last 28 days. Compare the results with the get_otd_scorecard tool.
```

### A7. Deploy and publish

```text
Use the adk-agent-deploy skill. Run the pre-flight checks, then deploy tms_agent to Vertex AI Agent
Engine in <my project>, us-central1. Smoke test it with "Give me this morning's TMS brief." Then
give me the exact Gemini Enterprise console steps to add it as a custom agent, with the description
text from deployment/register_gemini_enterprise.sh. Stop and ask before any step that creates
billable resources other than the Agent Engine.
```

### A8. Extend with a new capability (spec-first, small)

```text
/speckit.specify Add a "carrier QBR pack" capability: for one carrier and a date range, return
on-time %, tender acceptance, overbilling $, claims rate, lanes served and 3 negotiation points,
each with data used and $ impact. Reuse existing tools where possible.
```

Then `/speckit.clarify`, `/speckit.plan`, `/speckit.tasks`, `/speckit.analyze`, `/speckit.implement`
with the prompts from Track B (B4 to B8), and tell it to follow the `adk-tool-author` skill.

---

## Track B: rebuild it spec-driven from an empty folder

Start in an empty workspace folder, or a fresh clone of the codelab starter. Copy `.agents/workflows/`, `.specify/templates/`,
`.specify/scripts/` and `.agents/skills/` from this repo (or from the
`alphinside/sdd-adk-antigravity-starter` template used in the codelab). Each step below is one prompt.

### B0. Context first (the brief's tip: assumptions and open questions first)

```text
You are helping me build a hackathon MVP for a US grocery and foodservice distributor (convenience
stores, grocery, QSR and casual-dining restaurants) running Trimble TMW as its TMS. Before writing
anything, list your assumptions about TMW data (orderheader, legheader, stops, carrier, paydetail,
checkcall, freight bills / EDI 210, rate tables, DOE fuel index) and the open questions you would
ask the business. Keep it to one page. Do not create files yet.
```

### B1. Constitution

```text
/speckit.constitution Create the constitution for a Google ADK (Python) multi-agent "TMS
Intelligence" system. Principles:
1. Grounded answers only: every number comes from a tool result; missing or illegible data is
   flagged NEEDS_REVIEW, never guessed.
2. Recommendation contract: every recommendation shows reasoning, data used, confidence and $ impact,
   computed by tools.
3. Read-only by default: generated SQL is guarded (single SELECT/WITH, no DML/DDL/file functions,
   row cap). The only action is tender_load. It auto-executes only at or below $2,500 and at or
   above 80% confidence (env-configurable), otherwise it requires human approval through ADK tool
   confirmation. Every decision is logged.
4. One schema, three backends: a single Python schema definition generates BigQuery, AlloyDB and
   DuckDB DDL; tool SQL is portable.
5. Test-first, offline-first: every tool is tested on a synthetic DuckDB dataset with no cloud
   credentials; agent wiring is tested through the ADK Runner with a scripted model.
6. Synthetic data only, reproducible with a seed.
Stack: Python 3.11, google-adk, Gemini on Vertex AI, BigQuery or AlloyDB, Vertex AI Agent Engine,
Gemini Enterprise.
```

### B2. Specify

```text
/speckit.specify Build a TMS Intelligence layer on top of Trimble TMW that:
(1) recommends the best carrier or mode per load and auto-tenders within guardrails;
(2) predicts delays and flags at-risk loads 24 hours ahead with a suggested mitigation;
(3) audits carrier freight invoices against contracted rates and accessorial rules (fuel surcharge
from the DOE table, detention after free time, lumper receipts) and flags overbilling with $ impact;
(4) answers natural-language questions with SQL-backed, cited answers;
(5) produces weekly insights: lane and carrier performance, spend variance and savings.
Every recommendation shows reasoning, data used, confidence and $ impact. No auto-action above
$2,500 or below 80% confidence without human approval. Log all decisions for audit. Handle messy
inputs (missing fuel surcharge, illegible rate on a scanned PDF, spot loads with no contract):
flag, don't guess. Users: transportation planners, freight audit, carrier procurement, ops leaders.
```

### B3. Clarify

```text
/speckit.clarify
```

Suggested answers when it asks: guardrail defaults $2,500 / 0.80 and never a CONDITIONAL-rated
carrier; delay = any stop arriving after its appointment window; dataset "today" is 2026-10-27;
detention $65/hr after 120 free minutes; lumper only with a receipt; spot loads are checked against
a company-standard schedule and the rate goes to NEEDS_REVIEW.

### B4. Plan

```text
/speckit.plan Use Google ADK 2.x in Python. One coordinator LlmAgent ("tms_intelligence") that
calls specialist agents through AgentTool: service_exceptions_analyst, freight_audit_analyst,
freight_cost_analyst, carrier_performance_analyst, fleet_operations_analyst and tms_data_analyst
(NL-to-SQL). Tools are plain Python functions with docstrings. Data access through a Backend class
with DuckDB, BigQuery (parameterized queries, maximum_bytes_billed) and AlloyDB (psycopg pool,
READ ONLY transactions) implementations chosen by TMS_DB_BACKEND. Tables modelled on TMW: customers,
locations, carriers, drivers, tractors, trailers, orders, loads, stops, load_costs, invoices,
carrier_tenders, carrier_rates, carrier_invoices, check_calls, exceptions, fuel_prices,
agent_decision_log, plus views v_load_profitability, v_stop_service, v_carrier_scorecard.
Delay model: explainable smoothed target encoding over pre-dispatch features, with a BigQuery ML
alternative. Invoice audit: deterministic rules plus Gemini structured extraction for PDFs.
tender_load uses tool_context.request_confirmation outside guardrails. Decision log to JSONL,
Cloud Logging and optionally BigQuery/AlloyDB. Deploy with adk deploy agent_engine and register
in Gemini Enterprise. Write research.md, data-model.md and quickstart.md too.
```

### B5. Tasks

```text
/speckit.tasks Order the tasks so each user story is independently testable: synthetic data
generator with planted stories first, then backends and SQL guard, then tools per capability with
tests, then agents and prompts, then evals, then deployment scripts and docs. Mark tasks that can
run in parallel.
```

### B6. Analyze

```text
/speckit.analyze Check spec, plan and tasks for gaps against the constitution, especially: every
capability has an eval metric, every action path is logged, and every messy-input case has a
NEEDS_REVIEW reason code.
```

### B7. Implement in slices

Run `/speckit.implement` once per phase so you can review each walkthrough:

```text
/speckit.implement Phase 1 and 2 only (data generator, schema, DDL, loaders, backends, SQL guard).
Use the tms-synthetic-data skill. Plant these stories so the agent has something to find: one
broker carrier that is late and overbills, a restaurant chain with mostly unbilled detention, one
money-losing lane with high empty miles, old reefer units with temperature excursions, one DC late
on Mondays, a diesel spike with a lagging surcharge, drivers near HOS limits, and about 200 planted
invoice errors with a ground-truth CSV. Run pytest -q at the end.
```

```text
/speckit.implement The tool phases for the 5 capabilities. Follow the adk-tool-author skill for
every tool. Recommendations return reasoning, confidence and impact. Run pytest -q after each phase.
```

```text
/speckit.implement The agent, prompts, eval set and deployment phases. Add an end-to-end test that
runs the real ADK Runner with a scripted model and asserts that tendering to a low-confidence
carrier emits adk_request_confirmation. Run pytest -q and python evals/run_offline_evals.py.
```

### B8. Verify like a reviewer

```text
Act as a skeptical reviewer. Compare the implementation against specs/001-tms-intelligence/spec.md
acceptance scenarios one by one and report pass/fail with evidence (test name or command output).
Try to break the SQL guard with 5 injection attempts. Try to make tender_load auto-execute above
$2,500. Fix anything that fails, then rerun the full test suite.
```

### B9. Docs for the judges

```text
Write docs/SOLUTION_DESIGN.md in exactly this structure: 0) assumptions and open questions,
1) use-case prioritization (value vs effort table), 2) data model and pipeline, 3) models/agents per
capability with eval metrics and results, 4) demo: NL question → SQL → answer, an invoice audit
example and a carrier recommendation example, 5) expected business impact with assumptions. Use
only numbers produced by the tools or evals in this repo, and say they come from synthetic data.
Then write a 5-minute docs/DEMO_SCRIPT.md.
```

Then deploy with A7.

---

## Track C: add the McLane delivery signals spec-first

Use this on top of a working Track A or B workspace. It produces `specs/002-*` and the code in
`tms_agent/tools/delivery.py`, `tms_agent/tools/miles.py` and `tms_agent/mileage.py`.

### C1. Specify

```text
/speckit.specify Add McLane delivery signals to the TMS Intelligence agent:
(1) Retail vs Restaurant on-time delivery: Retail (grocery / convenience) is on time when it arrives
no later than the window end; Restaurant (foodservice) also must not arrive more than 15 minutes
before the window start. Scorecard by channel, DC, customer, carrier and week vs customer targets.
(2) Dwell time change: recent window vs baseline per customer, location, DC and channel, with the
annualized truck-hour cost of the change.
(3) Geofences and geo locations: where arrivals come from (geofence, driver manual, carrier EDI 214),
which locations have bad geocodes (ZIP centroid) and a suggested corrected point from ELD pings;
live load tracking with ETA to the next stop.
(4) PC*MILER miles: TMW plans with PC*MILER practical miles; compare carrier billed miles and private
fleet odometer miles (out-of-route) against them, and call PC*MILER Web Services when an API key
is configured. Estimates are always labelled, never shown as PC*MILER miles.
```

### C2. Clarify, plan, tasks

```text
/speckit.clarify
```

Suggested answers: restaurant early grace 15 minutes; dwell recent 21 days vs 56-day baseline,
minimum 20 stops; truck-hour cost $85; out-of-route flag above 8%; billed miles more than 2% over
PC*MILER practical = MILES_INFLATED; PC*MILER key comes from PCMILER_API_KEY.

```text
/speckit.plan Add columns in tms_agent/schema.py (stops.minutes_early, arrival_source,
pcmiler_leg_miles; loads.pcmiler_shortest_miles, actual_odometer_miles, mileage_source;
locations.geocode_quality, geofence_radius_m), a geofence_events table, otd_channel / otd_flag in
v_stop_service. Generate the new signals in a post-pass of tms_data/generate.py with a separate
random stream so existing stories keep their shape. New delivery_performance_analyst agent;
PC*MILER client in tms_agent/mileage.py using only the standard library.
```

```text
/speckit.tasks
```

### C3. Implement and verify

```text
/speckit.implement Follow the adk-tool-author skill. Plant: restaurant early arrivals at DC07, a
dwell increase at one grocery customer and a decrease at one restaurant chain, ~6% ZIP-centroid
geocodes, and four DC08 drivers with ~13% out-of-route miles. Add tests in
tests/test_mclane_signals.py for each, plus a test that mocks the PC*MILER HTTP call. Then create a
mclane-delivery-signals skill with a scripts/signals.py CLI. Run uv run pytest -q.
```

Use `/plan` style review (Planning mode) before C3, and the browser agent to run the C1 questions in
`uv run adk web .` afterwards.

---

## Creating a new skill (from the Skills codelab)

```text
Create a new workspace skill in .agents/skills/lane-rate-benchmark/ with a SKILL.md (name and
description frontmatter, the description says when to use it), a scripts/benchmark.py that compares
a carrier's contract rate per mile on each lane against the median of all carriers on that lane
using the project database through tms_agent.db.get_backend(), and a references/README.md with
example output. Test the script, then show me how you would trigger the skill with a prompt.
```
