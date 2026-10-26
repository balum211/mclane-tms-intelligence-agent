"""Read-only guard for model generated SQL (defence in depth on top of read-only DB credentials)."""

from __future__ import annotations

import re

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE|CALL|EXECUTE|EXPORT|COPY|ATTACH|"
    r"DETACH|PRAGMA|INSTALL|LOAD|SET|VACUUM|REPLACE\s+INTO|DECLARE|BEGIN|COMMIT|ROLLBACK)\b",
    re.IGNORECASE,
)
_FORBIDDEN_FUNCS = re.compile(r"\b(read_\w+|pg_read_file|pg_sleep|lo_import|dblink\w*|EXTERNAL_QUERY)\s*\(", re.I)
_COMMENTS = re.compile(r"(--[^\n]*|/\*.*?\*/)", re.S)
_STRINGS = re.compile(r"'(?:[^']|'')*'")


class UnsafeSQLError(ValueError):
    pass


def ensure_read_only(sql: str) -> str:
    """Return a cleaned single SELECT statement or raise UnsafeSQLError."""
    cleaned = _COMMENTS.sub(" ", sql).strip().rstrip(";").strip()
    if not cleaned:
        raise UnsafeSQLError("Empty SQL.")
    probe = _STRINGS.sub("''", cleaned)  # keywords inside string literals are fine
    if ";" in probe:
        raise UnsafeSQLError("Only a single statement is allowed.")
    if not re.match(r"^\s*(SELECT|WITH)\b", probe, re.I):
        raise UnsafeSQLError("Only SELECT / WITH queries are allowed.")
    m = _FORBIDDEN.search(probe) or _FORBIDDEN_FUNCS.search(probe)
    if m:
        raise UnsafeSQLError(f"Forbidden keyword or function: {m.group(0).strip()}")
    return cleaned


def with_limit(sql: str, max_rows: int) -> str:
    return f"SELECT * FROM (\n{sql}\n) AS agent_q LIMIT {int(max_rows)}"
