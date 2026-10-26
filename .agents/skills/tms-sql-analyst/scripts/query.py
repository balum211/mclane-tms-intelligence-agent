#!/usr/bin/env python3
"""Run a guarded read-only query against the TMS database, or print the schema.

Usage:
  query.py "SELECT ..."            run SQL (guarded, max 50 rows by default)
  query.py --schema [table ...]    print schema context for the active backend
  query.py --as-of                 print the dataset 'today'
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from tms_agent.db import get_backend  # noqa: E402
from tms_agent.schema import schema_context  # noqa: E402
from tms_agent.sql_guard import UnsafeSQLError, ensure_read_only, with_limit  # noqa: E402
from tms_agent.tools.common import as_of  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sql", nargs="?")
    ap.add_argument("--schema", nargs="*", metavar="TABLE")
    ap.add_argument("--as-of", action="store_true")
    ap.add_argument("--max-rows", type=int, default=50)
    ap.add_argument("--json", action="store_true", help="print rows as JSON")
    a = ap.parse_args()
    b = get_backend()

    if a.as_of:
        print(as_of().isoformat())
        return 0
    if a.schema is not None:
        text = schema_context(prefix=b.prefix.replace("`", ""), dialect=b.dialect)
        if a.schema:
            pfx = b.prefix.replace("`", "")
            text = "\n\n".join(blk for blk in text.split("\n\n")
                               if blk.startswith("VIEWS") or any(blk.startswith(f"TABLE {pfx}{t} ") for t in a.schema))
        print(text)
        return 0
    if not a.sql:
        ap.print_help()
        return 2
    try:
        sql = ensure_read_only(a.sql)
    except UnsafeSQLError as e:
        print(f"Rejected by SQL guard: {e}", file=sys.stderr)
        return 1
    rows = b.query(with_limit(sql, a.max_rows), max_rows=a.max_rows)
    if a.json or not rows:
        print(json.dumps(rows, indent=2, default=str))
        return 0
    cols = list(rows[0])
    print(" | ".join(cols))
    print(" | ".join("---" for _ in cols))
    for r in rows:
        print(" | ".join(str(r[c]) for c in cols))
    print(f"\n{len(rows)} row(s), backend={b.dialect}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
