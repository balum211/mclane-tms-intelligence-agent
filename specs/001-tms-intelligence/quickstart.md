# Quickstart: validate the feature

```bash
pip install -e ".[dev]"
python -m tms_data.generate && python -m tms_data.load --target duckdb
pytest -q                              # all user stories' acceptance tests
python evals/run_offline_evals.py      # SC-002, SC-003
adk web .                              # walk through docs/DEMO_SCRIPT.md (SC-005)
```
