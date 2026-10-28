# Quickstart: McLane delivery signals

```bash
uv run python -m tms_data.generate && uv run python -m tms_data.load --target duckdb
uv run pytest -q tests/test_mclane_signals.py
python .agents/skills/mclane-delivery-signals/scripts/signals.py otd --group-by dc --channel RESTAURANT
uv run adk web .   # "How is OTD for retail vs restaurants this month?"
```
