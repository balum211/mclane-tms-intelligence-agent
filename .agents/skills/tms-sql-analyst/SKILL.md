---
name: tms-sql-analyst
description: Answer business questions about TMS / Trimble TMW transportation data (loads, stops, carriers, on-time, detention, freight cost, invoices) by writing and running guarded read-only SQL against the project database (DuckDB, BigQuery or AlloyDB). Use when the user asks a data question, wants a KPI checked, or needs SQL for the TMS schema.
---

# TMS SQL analyst

Use this skill to answer a question with numbers from the TMS database, or to write and verify SQL
for `tms_agent` tools, evals or demos.

## Steps

1. Read `references/schema_cheatsheet.md` for the table map and join keys. For full column
   descriptions run `uv run python .agents/skills/tms-sql-analyst/scripts/query.py --schema`
   (or `--schema loads stops` for a subset).
2. Use the dataset "today" (`as_of`), never the wall clock: the script prints it with `--as-of`.
3. Prefer the views. `v_stop_service` for on-time / dwell / detention, `v_load_profitability` for
   revenue / cost / margin, `v_carrier_scorecard` for carrier KPIs.
4. Write ONE `SELECT` or `WITH` query in portable SQL: `1.0 * a / NULLIF(b, 0)` for ratios,
   `SUM(CASE WHEN ... THEN 1 ELSE 0 END)` for counts, explicit date literals instead of `CURRENT_DATE`.
5. Run it: `uv run python .agents/skills/tms-sql-analyst/scripts/query.py "SELECT ..."`. The script applies
   the same guard as the agent (`tms_agent/sql_guard.py`) and caps rows.
6. Answer with a short table, then the SQL in a code block, then the time window used. If a needed
   field is empty or missing, say so. Do not estimate it.

## Backend

The script uses `TMS_DB_BACKEND` (default `duckdb` at `data/tms.duckdb`). Build the local database
first if it is missing: `uv run python -m tms_data.generate && uv run python -m tms_data.load --target duckdb`.
For BigQuery use fully qualified names `` `project.dataset.table` `` as printed by `--schema`.

## Examples

See `references/examples.md` (verified answers on the default dataset).
