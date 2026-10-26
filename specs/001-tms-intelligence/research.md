# Research: TMS Intelligence

## Decision: Google ADK `AgentTool` composition (not sub-agent transfer)
**Rationale**: The coordinator must combine several specialists' answers ("margin drop" needs cost
and exceptions). `AgentTool` returns results to the coordinator. Transfer would hand off control.
**Alternatives**: `sub_agents` transfer (loses synthesis), a single agent with 30 tools (tool selection degrades).

## Decision: BigQuery primary, AlloyDB supported, DuckDB local
**Rationale**: BigQuery needs no networking from Agent Engine and has partitioning plus BQML. AlloyDB
fits teams that already replicate TMW (SQL Server) into PostgreSQL and want low-latency operational
queries (columnar engine). DuckDB makes the whole project runnable and testable offline.

## Decision: deterministic audit rules + Gemini only for document extraction
**Rationale**: Finance needs explainable, reproducible findings with evidence. The LLM reads documents
(nulls for illegible fields) but never decides the dollar amount.

## Decision: guardrails enforced in code, approvals through ADK tool confirmation
**Rationale**: Prompts can be ignored. Code cannot. `ToolContext.request_confirmation` is ADK's native
human-in-the-loop. `adk web` renders it, and the runner emits `adk_request_confirmation`.

## Decision: TMW-shaped synthetic data with planted stories and ground truth
**Rationale**: No real data is available at the hackathon. Planted stories make the demo deterministic
and let the tests assert that the agent's tools find them. Invoice errors carry ground truth for
precision / recall.

## Trimble TMW integration notes
- Source tables: orderheader, legheader, stops, freightdetail, company, carrier, manpowerprofile,
  tractorprofile, trailerprofile, paydetail, invoiceheader, checkcall.
- Replication options: Datastream (SQL Server CDC) → BigQuery, or Database Migration Service → AlloyDB.
- Write-back (future): EDI 204 tenders and TMW APIs, behind the same `tender_load` guardrails.
