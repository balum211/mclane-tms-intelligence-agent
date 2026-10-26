---
name: tms-synthetic-data
description: Generate, reload or extend the synthetic Trimble TMW-style dataset (DCs, customers, carriers, loads, stops, freight bills, rates, telematics, exceptions) and load it into DuckDB, BigQuery or AlloyDB. Use when data is missing, a new column or planted story is needed, or the demo numbers must be reproduced.
---

# TMS synthetic data

All data is fictional and reproducible (seed 42, as-of 2026-10-27, 120 days).

## Build and load

```bash
python -m tms_data.generate                                   # -> data/generated/*.csv (+ _truth_invoice_errors.csv)
python -m tms_data.load --target duckdb                       # -> data/tms.duckdb (local, tests, adk web)
python -m tms_data.load --target bigquery --project $GOOGLE_CLOUD_PROJECT --dataset mclane_tms
python -m tms_data.load --target alloydb --dsn "postgresql://postgres:$PW@127.0.0.1:5432/postgres"
python -m tms_data.sample_invoices                            # 3 demo PDFs in data/sample_invoices/
python -m tms_data.ddl --dialect bigquery --dataset my-proj.mclane_tms > sql/bigquery_schema.sql
python -m tms_data.ddl --dialect alloydb > sql/alloydb_schema.sql
```

Options: `--days`, `--loads-per-dc-day`, `--seed`, `--as-of`. Tests build their own small dataset
(60 days, seed 7) in a temp folder, so they never depend on `data/`.

## Planted stories (do not break them)

Redline (CR006) is the worst carrier and overbills; BurgerBarn detention is mostly unbilled;
lane DC05→NV loses money; 9+ year reefer units cause excursions; DC03 is late on Mondays; diesel
spike with a lagging surcharge at DC06; drivers near HOS limits; tobacco/candy shortages at DC02;
210 planted invoice errors with ground truth. Details and tool mapping: `docs/DATA_STORY.md`.
`tests/test_capabilities.py` asserts each story.

## Adding a column or table

1. Add it to `tms_agent/schema.py` with a business description (the NL-to-SQL agent reads it).
2. Populate it in `tms_data/generate.py`. Keep it deterministic: use the seeded `rng`, never
   `hash()` or the wall clock.
3. Regenerate the DDL files, reload DuckDB, run `pytest -q`.
4. If it creates a new story, add a row to `docs/DATA_STORY.md` and an assertion in `tests/test_capabilities.py`.

## Messy data on purpose

Some freight bills have NULL fuel surcharge, NULL rate (illegible scans) or no lane contract (spot).
Keep these: they prove the agent flags instead of guessing.
