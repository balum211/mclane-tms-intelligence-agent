# Implementation Plan: McLane delivery signals

**Branch**: `002-mclane-delivery-signals` | **Spec**: [spec.md](spec.md)

## Summary
Extend the TMW-shaped schema with PC*MILER, geofence and OTD fields, generate them in a separate
post-pass of the synthetic generator (so the 001 stories keep their numbers), add six tools and a
`delivery_performance_analyst` specialist, and surface the signals in the KPI snapshot and weekly pack.

## Technical Context
- Python 3.11+, google-adk 2.x, BigQuery / AlloyDB / DuckDB through `tms_agent/db.py`
- Portable SQL only (`{p}` prefix, `:name` params, `Backend.week()`); timestamp equality joins are portable
- PC*MILER Web Services REST (`route/routeReports`, `reports=Mileage`, API key) behind `tms_agent/mileage.py`

## Constitution Check
- Grounded answers: all numbers come from tools; estimates are labelled ✔
- Recommendation contract: tools return reasoning, $ impact and windows ✔
- Read-only: all new tools are SELECT ✔
- One schema: columns added only in `schema.py`, DDL regenerated ✔
- Test-first: `tests/test_mclane_signals.py`, new CALLS in `tests/test_tools.py` (also run on PostgreSQL) ✔

## Design

| Component | Change |
|---|---|
| `tms_agent/schema.py` | 8 new columns, `geofence_events` table, `otd_channel` / `otd_flag` in `v_stop_service` |
| `tms_data/generate.py` | `build_mclane_signals()` post-pass on `rng2`; route-time consistency fix |
| `tms_agent/mileage.py` | PC*MILER client + labelled great-circle estimate |
| `tms_agent/tools/delivery.py` | `get_otd_scorecard`, `get_dwell_time_changes`, `get_geofence_compliance`, `track_load` |
| `tms_agent/tools/miles.py` | `check_pcmiler_miles`, `get_out_of_route_miles` |
| `tms_agent/agent.py`, `prompts.py` | `delivery_performance_analyst`; audit and fleet specialists get the mileage tools |
| `tools/kpi.py`, `tools/insights.py` | Retail / Restaurant OTD, dwell, out-of-route, geocode fixes |
| `tools.yaml` | Toolbox tools `otd_by_channel`, `dwell_by_customer`, `geofence_misses` |
| `.agents/skills/mclane-delivery-signals` | Skill + CLI script |
