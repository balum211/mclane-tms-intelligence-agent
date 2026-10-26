"""Capability evals that need no LLM: invoice-audit accuracy against planted ground truth and the
delay model card on a time-based holdout.

    python -m tms_data.generate && python -m tms_data.load --target duckdb
    python evals/run_offline_evals.py
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tms_agent.tools import audit, predict  # noqa: E402
from tms_agent.tools.common import run  # noqa: E402


def invoice_audit(truth_path: Path) -> dict:
    truth = {r["carrier_invoice_id"]: r["error_code"] for r in csv.DictReader(truth_path.open())}
    results = [audit.audit_invoice_row(r) for r in run(audit._audit_sql("1=1"), max_rows=1_000_000)]
    flagged = {a["carrier_invoice_id"]: [f["code"] for f in a["findings"]] for a in results if a["verdict"] == "OVERBILLED"}
    tp = set(flagged) & set(truth)
    return {
        "invoices": len(results), "planted_errors": len(truth), "flagged": len(flagged),
        "precision": round(len(tp) / max(1, len(flagged)), 3), "recall": round(len(tp) / max(1, len(truth)), 3),
        "correct_reason_code": round(sum(truth[k] in flagged[k] for k in tp) / max(1, len(tp)), 3),
        "missed_by_type": dict(Counter(truth[k] for k in truth if k not in flagged)),
        "needs_review": sum(a["verdict"] == "NEEDS_REVIEW" for a in results),
    }


if __name__ == "__main__":
    out = {
        "invoice_audit": invoice_audit(Path("data/generated/_truth_invoice_errors.csv")),
        "delay_model": predict.get_delay_model_card()["data"],
    }
    print(json.dumps(out, indent=2))
