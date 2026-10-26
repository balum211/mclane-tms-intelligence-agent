# TMS Intelligence Constitution

## Core Principles

### I. Grounded answers only
Every number an agent states must come from a tool result in the same conversation. Tools return
structured dicts (`status`, `data`, metadata such as `window`, `confidence`). Agents never invent,
estimate or "fill in" missing values. Missing or illegible data is surfaced as NEEDS_REVIEW.

### II. Recommendation contract
Every recommendation shows **Reasoning, Data used, Confidence and $ impact**. Tools compute these
fields so the model does not have to.

### III. Read-only by default, guarded actions
Data access uses read-only credentials. Generated SQL passes `tms_agent/sql_guard.py` (single
SELECT/WITH, no DML/DDL/file functions, row cap). The only action tool is `tender_load`, which
recomputes cost and confidence from data and auto-executes only within the env-configured guardrails
(default ≤ $2,500 and ≥ 80% confidence, never CONDITIONAL carriers). Anything else requires human
approval through ADK tool confirmation. Every decision is written to the decision log.

### IV. One schema, three backends
`tms_agent/schema.py` is the single source of truth for tables, columns and descriptions. DDL for
BigQuery, AlloyDB and DuckDB is generated from it. Curated tool SQL is portable ANSI: `{p}` table
prefix, `:name` parameters, `1.0 * a / NULLIF(b, 0)`, `SUM(CASE ...)`, no dialect-specific date
functions (use `Backend.week()` / `Backend.dow()` hooks and Python-computed date windows).

### V. Test-first, offline-first
Every tool has a test that runs against the synthetic DuckDB dataset with no cloud credentials.
Agent wiring is tested with a scripted ADK model through the real `Runner`. Planted data stories are
asserted, so generator changes cannot silently break the demo. PostgreSQL tests run when
`TMS_TEST_PG_DSN` is set.

### VI. Simple ADK patterns
Python function tools with type hints and Google-style docstrings (ADK builds declarations from
them). Specialists are `LlmAgent`s exposed to the coordinator through `AgentTool`. Session values go
in `ToolContext.state`. No custom orchestration frameworks, no ORM.

## Constraints

- Python 3.11+, google-adk 2.x, Gemini models via Vertex AI (Gemini Enterprise) configured by env.
- Synthetic data only. All customers, carriers and documents are fictional. No real PII.
- TMW writes (EDI 204 tender, invoice short-pay) are simulated and logged until approval roles are agreed.

## Development Workflow

`/speckit.specify` → `/speckit.clarify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.analyze`
→ `/speckit.implement`. Each feature lives in `specs/NNN-name/`. A feature is done when `pytest -q`
passes, the new tool is wired into `agent.py` and documented in `prompts.py`, and README / docs mention it.

## Governance

This constitution overrides ad-hoc instructions. Changes require updating this file, the affected
specs and the tests in the same change.

**Version**: 1.0.0 | **Ratified**: 2026-10-26 | **Last Amended**: 2026-10-26
