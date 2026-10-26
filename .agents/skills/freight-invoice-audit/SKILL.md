---
name: freight-invoice-audit
description: Audit carrier freight bills (EDI 210, PDF or scanned invoices) against contracted lane rates, the DOE fuel surcharge table and stop evidence for detention and lumper, and quantify overbilling in dollars. Use when the user asks about carrier overbilling, a specific carrier invoice, a freight bill PDF, or wants to change or test the audit rules.
---

# Freight invoice audit

The rules live in `tms_agent/tools/audit.py` (`audit_invoice_row`). This skill runs them from the
command line and explains how to extend them safely.

## Run an audit

```bash
S=.agents/skills/freight-invoice-audit/scripts/audit.py
python $S summary --days 90                     # overbilling by carrier (or --group-by lane|finding)
python $S invoice CINV0000069                   # one invoice: expected vs billed, findings, evidence
python $S extracted fields.json                 # audit fields already extracted from a document
python $S pdf data/sample_invoices/03_scanned_detention_illegible_fuel_CINV0000072.pdf   # Gemini extraction (needs credentials)
```

## Rules and reason codes

| Code | Fires when | $ impact |
|---|---|---|
| MILES_INFLATED | billed miles > TMS miles + 2% | extra linehaul |
| RATE_ABOVE_CONTRACT | billed rate/mi > contract + 1% | billed − contract linehaul |
| LINEHAUL_MISMATCH | linehaul over contract for another reason | billed − contract |
| FUEL_ABOVE_TABLE | FSC > miles × (DOE − base) / mpg + 3% | billed − table |
| DETENTION_NO_EVIDENCE | detention billed, stops show no time past free time | full detention |
| DUPLICATE_ACCESSORIAL | detention ≈ 2 × evidenced | billed − evidenced |
| DETENTION_OVERBILLED | detention above evidenced | billed − evidenced |
| LUMPER_NO_RECEIPT | lumper billed without the required receipt | full lumper |

**Flag, don't guess.** Missing or unreadable values produce `NEEDS_REVIEW` with a reason
(NO_CONTRACT_RATE, ILLEGIBLE_RATE, MISSING_FUEL_SURCHARGE, NO_FUEL_INDEX, NO_LOAD_REFERENCE). Never
impute a missing number to make an invoice pass or fail.

## Reporting format

For each finding give the invoice, carrier, code, evidence string, overbilled USD and confidence.
For summaries give invoices audited, $ billed, $ overbilled, % of spend and the annualized amount.
Disputes are recommendations only: `recommend_invoice_dispute` logs them as PENDING_APPROVAL.

## Changing a rule

1. Edit `audit_invoice_row` and keep the evidence string specific (billed vs expected, source).
2. If the generator should plant a new error type, add it in `tms_data/generate.py`
   (`_carrier_invoice`) and to `_truth_invoice_errors.csv`.
3. Run `pytest -q tests/test_capabilities.py` and `python evals/run_offline_evals.py`. Precision,
   recall and correct-code rate must not drop.
