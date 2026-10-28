# uv is the default (codelab workflow). Without uv: make PY=python RUN= install-pip data test
RUN ?= uv run
PY ?= python

.PHONY: install install-pip data test evals web serve pdfs ddl

install:
	uv sync

install-pip:
	$(PY) -m pip install -e ".[dev]"

data:
	$(RUN) $(PY) -m tms_data.generate
	$(RUN) $(PY) -m tms_data.load --target duckdb

test:
	$(RUN) $(PY) -m pytest -q

evals:
	$(RUN) $(PY) evals/run_offline_evals.py

web:
	$(RUN) adk web .

serve:
	$(RUN) $(PY) server.py

pdfs:
	$(RUN) $(PY) -m tms_data.sample_invoices

ddl:
	$(RUN) $(PY) -m tms_data.ddl --dialect bigquery --dataset YOUR_PROJECT.mclane_tms > sql/bigquery_schema.sql
	$(RUN) $(PY) -m tms_data.ddl --dialect alloydb > sql/alloydb_schema.sql
