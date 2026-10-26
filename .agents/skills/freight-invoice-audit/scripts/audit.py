#!/usr/bin/env python3
"""Run the freight invoice audit rules from the command line.

  audit.py summary [--days 90] [--carrier CR006] [--group-by carrier|lane|finding]
  audit.py invoice CINV0000069
  audit.py extracted fields.json     # {"load_id": ..., "billed_linehaul": ..., "illegible_fields": [...]}
  audit.py pdf path/or/gs://uri.pdf  # Gemini extraction, needs Vertex AI or GOOGLE_API_KEY
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from tms_agent.tools import audit  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("summary")
    s.add_argument("--days", type=int, default=90)
    s.add_argument("--carrier", default="")
    s.add_argument("--group-by", default="carrier", choices=["carrier", "lane", "finding"])
    s.add_argument("--limit", type=int, default=15)
    sub.add_parser("invoice").add_argument("carrier_invoice_id")
    sub.add_parser("extracted").add_argument("json_file")
    sub.add_parser("pdf").add_argument("document_uri")
    a = ap.parse_args()

    if a.cmd == "summary":
        out = audit.audit_carrier_invoices(days=a.days, carrier_id=a.carrier, group_by=a.group_by, limit=a.limit)
    elif a.cmd == "invoice":
        out = audit.get_invoice_audit_detail(a.carrier_invoice_id)
    elif a.cmd == "extracted":
        out = audit.audit_extracted_invoice(json.loads(Path(a.json_file).read_text()))
    else:
        out = audit.extract_and_audit_invoice_document(a.document_uri)
    print(json.dumps(out, indent=2, default=str))
    return 0 if out.get("status") != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
