# Quickstart: validate the feature

```bash
uv sync   # or: pip install -e ".[dev]"
uv run python -m tms_data.generate && uv run python -m tms_data.load --target duckdb
uv run pytest -q                              # all user stories' acceptance tests
uv run python evals/run_offline_evals.py      # SC-002, SC-003
uv run adk web .                              # walk through docs/DEMO_SCRIPT.md (SC-005)
```
