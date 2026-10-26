"""NL-to-SQL tools: schema grounding and guarded read-only SQL execution."""

from __future__ import annotations

from google.adk.tools import ToolContext

from tms_agent.db import get_backend
from tms_agent.schema import TABLES_BY_NAME, schema_context
from tms_agent.sql_guard import UnsafeSQLError, ensure_read_only, with_limit
from tms_agent.tools.common import as_of, fail, ok, safe


@safe
def get_tms_schema(table_names: list[str] | None = None) -> dict:
    """Returns the TMS database schema (tables, columns, joins, views) and SQL dialect.

    Call this before writing SQL. The data is modelled on Trimble TMW tables
    (orderheader -> orders, legheader -> loads, stops, carrier, manpowerprofile -> drivers).

    Args:
        table_names: Optional list of table names to limit the output. Omit for all tables.

    Returns:
        dict with 'dialect', 'table_prefix', 'as_of_date' (dataset 'today') and 'schema' text.
    """
    b = get_backend()
    text = schema_context(prefix=b.prefix.replace("`", ""), dialect=b.dialect)
    if table_names:
        wanted = {t.lower() for t in table_names}
        unknown = wanted - set(TABLES_BY_NAME) - {"v_load_profitability", "v_stop_service", "v_carrier_scorecard"}
        pfx = b.prefix.replace("`", "")
        blocks = [blk for blk in text.split("\n\n")
                  if blk.startswith("VIEWS") or any(blk.startswith(f"TABLE {pfx}{t} ") for t in wanted)]
        text = "\n\n".join(blocks) or text
        if unknown:
            text += f"\n\nUnknown tables ignored: {sorted(unknown)}"
    return ok(
        {"dialect": b.dialect, "table_prefix": b.prefix, "as_of_date": as_of().isoformat(), "schema": text}
    )


@safe
def run_tms_sql(sql: str, tool_context: ToolContext, max_rows: int = 100) -> dict:
    """Runs a single read-only SELECT query against the TMS database and returns rows.

    Rules: SELECT/WITH only, one statement, fully qualified table names exactly as
    returned by get_tms_schema. Results are capped at max_rows (<= 500).

    Args:
        sql: The SQL query to run.
        max_rows: Maximum rows to return (default 100, max 500).

    Returns:
        dict with 'columns', 'rows', 'row_count' and the executed 'sql', or an error_message
        that explains what to fix.
    """
    try:
        cleaned = ensure_read_only(sql)
    except UnsafeSQLError as e:
        return fail(f"Rejected by SQL guard: {e}")
    max_rows = max(1, min(int(max_rows or 100), 500))
    rows = get_backend().query(with_limit(cleaned, max_rows + 1), max_rows=max_rows + 1)
    truncated = len(rows) > max_rows
    rows = rows[:max_rows]
    tool_context.state["last_sql"] = cleaned
    return ok(
        {"columns": list(rows[0].keys()) if rows else [], "rows": rows},
        row_count=len(rows),
        truncated=truncated,
        sql=cleaned,
    )
