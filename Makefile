PY ?= python

.PHONY: install data test evals web pdfs ddl

install:
	$(PY) -m pip install -e ".[dev]"

data:
	$(PY) -m tms_data.generate
	$(PY) -m tms_data.load --target duckdb

test:
	$(PY) -m pytest -q

evals:
	$(PY) evals/run_offline_evals.py

web:
	adk web .

pdfs:
	$(PY) -m tms_data.sample_invoices

ddl:
	$(PY) -m tms_data.ddl --dialect bigquery --dataset YOUR_PROJECT.mclane_tms > sql/bigquery_schema.sql
	$(PY) -m tms_data.ddl --dialect alloydb > sql/alloydb_schema.sql
