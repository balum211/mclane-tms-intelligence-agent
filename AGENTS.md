# AGENTS.md: rules for coding agents (Antigravity, Gemini CLI, Claude Code)

This repo is a Google ADK (Python) multi-agent system that adds intelligence on top of a Trimble TMW
TMS: carrier recommendation with guardrailed auto-tender, 24h delay prediction, freight invoice
audit, NL-to-SQL, weekly insights and McLane delivery signals (Retail vs Restaurant OTD, dwell time
change, geofences / geo locations, PC*MILER miles and out-of-route).
Data lives in BigQuery or AlloyDB (DuckDB locally).

Read first: `.specify/memory/constitution.md` (non-negotiable principles) and
`specs/001-tms-intelligence/spec.md`, `specs/002-mclane-delivery-signals/spec.md`. Project context
for Antigravity is in `.agents/rules/project-context.md`; reusable procedures are in `.agents/skills/`.

## Commands

```bash
uv sync                                                                  # or: pip install -e ".[dev]"
uv run python -m tms_data.generate && uv run python -m tms_data.load --target duckdb   # local data
uv run pytest -q                                                         # must stay green
uv run python evals/run_offline_evals.py                                 # audit + delay metrics
uv run adk web .                                                         # pick tms_agent
uv run python server.py                                                  # ADK FastAPI app on :8080
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
11. **McLane rules.** OTD comes from `v_stop_service.otd_flag` (Retail: not after the window end;
    Restaurant: also not more than 15 min early). `loads.total_miles` is PC*MILER practical. Never
    label an estimate as PC*MILER miles: `mileage.route_miles` returns the `source` to show.
12. **Generator changes keep the stories.** New signals in `tms_data/generate.py` use `self.rng2` in a
    post-pass so the base random stream (and every existing story) is unchanged. Re-run `tests/test_capabilities.py` and
    `tests/test_mclane_signals.py` after any change.
13. **Ask, don't assume.** When a requirement is ambiguous (a window, a threshold, a customer), ask the
    user (Antigravity `ask_question`) before writing code.
