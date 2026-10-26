---
name: adk-tool-author
description: Add or change a Google ADK function tool or sub-agent in the tms_agent package (portable SQL, recommendation contract, guardrails, tests). Use when implementing a new TMS capability, a new analytics question type, or wiring a tool into an agent.
---

# Authoring ADK tools for tms_agent

## Tool checklist

1. Put the function in the right module under `tms_agent/tools/` (exceptions, cost, carrier,
   audit, predict, fleet, kpi, insights, tender, analytics).
2. Signature: plain JSON types with defaults, plus `tool_context: ToolContext` only if you need
   state or confirmation (ADK hides it from the model). The docstring becomes the tool description:
   say when to use it, each arg, and what it returns.
3. Decorate with `@safe` and return `ok(data, window=[start, end], ...)` or `fail("what to fix")`
   from `tools/common.py`.
4. SQL: `{p}` before every table, `:name` parameters, `1.0 * a / NULLIF(b, 0)`, `SUM(CASE ...)`,
   `get_backend().week(col)` / `.dow(col)` for dates. Compute date windows in Python with `window(days)`.
   Round floats in Python, not SQL (PostgreSQL has no `round(double, int)`).
5. Recommendations must return `reasoning`, `confidence` (0-1) and `impact` in USD.
6. Anything that acts (tender, dispute, short-pay) must:
   - recompute amounts from data, never trust chat input,
   - check `TMS_AUTO_TENDER_MAX_USD` / `TMS_AUTO_TENDER_MIN_CONFIDENCE`,
   - call `tool_context.request_confirmation(hint=..., payload=...)` when outside the guardrails,
   - call `log_decision(...)` on every path (executed, pending, approved, rejected, blocked).
   Copy the pattern in `tools/tender.py`.
7. Register it: add it to the specialist's `tools=[...]` in `tms_agent/agent.py` and mention it in
   that agent's instruction in `prompts.py`.
8. Test it: add a call to `CALLS` in `tests/test_tools.py` (runs on DuckDB), and an assertion in
   `tests/test_capabilities.py` if it backs a demo story. Run `pytest -q`. If you have PostgreSQL,
   also `TMS_TEST_PG_DSN=postgresql://... pytest tests/test_postgres.py`.

## Adding a specialist agent

Create an `LlmAgent` in `build_root_agent()` with a narrow instruction and 3-6 tools, then expose
it to the coordinator with `AgentTool(agent=...)`. Add a routing line to `COORDINATOR_INSTRUCTION`
and a scripted-model test in `tests/test_agent_e2e.py`.
