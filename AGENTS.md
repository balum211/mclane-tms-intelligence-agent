# AGENTS.md: rules for coding agents (Antigravity, Gemini CLI, Claude Code)

This repo is a Google ADK (Python) multi-agent system that adds intelligence on top of a Trimble TMW
TMS: carrier recommendation with guardrailed auto-tender, 24h delay prediction, freight invoice
audit, NL-to-SQL and weekly insights. Data lives in BigQuery or AlloyDB (DuckDB locally).

Read first: `.specify/memory/constitution.md` (non-negotiable principles) and
`specs/001-tms-intelligence/spec.md`.

## Commands

```bash
pip install -e ".[dev]"
python -m tms_data.generate && python -m tms_data.load --target duckdb   # local data
pytest -q                                                                # must stay green
python evals/run_offline_evals.py                                        # audit + delay metrics
adk web .                                                                # pick tms_agent
```

## Rules

1. **Grounded only.** Agents state numbers that come from tool results. Missing or illegible data
   is returned as `NEEDS_REVIEW` with a reason. Never estimate it ("flag, don't guess").
2. **Recommendation contract.** Tools that recommend return `reasoning`, `confidence`, `impact`
   (USD) and the data window. Prompts in `tms_agent/prompts.py` require the model to show them.
3. **Guardrails live in code.** `tender_load` is the only action tool. It recomputes cost and
   confidence and uses `tool_context.request_confirmation` above `TMS_AUTO_TENDER_MAX_USD` or below
   `TMS_AUTO_TENDER_MIN_CONFIDENCE`. Do not move these checks into prompts.
4. **Log every decision** with `tms_agent.decision_log.log_decision`.
5. **One schema.** Add or change columns only in `tms_agent/schema.py` (with a description), then
   regenerate DDL with `python -m tms_data.ddl`. Never hand-edit `sql/*_schema.sql`.
6. **Portable SQL.** Use `{p}` for the table prefix and `:name` parameters. No dialect-specific
   date functions in tools: use `Backend.week()` / `Backend.dow()` and Python date windows.
7. **Tools** are plain functions with type hints and a docstring (ADK builds the declaration from
   them), wrapped with `@safe`, returning `ok(...)` / `fail(...)` from `tools/common.py`.
8. **Every new tool gets a test** in `tests/test_tools.py` (and a planted-story assertion in
   `tests/test_capabilities.py` when it backs a demo claim).
9. Generated SQL from the model always goes through `sql_guard.ensure_read_only`.
10. Synthetic data only. No real customer, carrier or driver names.
