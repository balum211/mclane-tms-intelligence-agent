# Tasks: McLane delivery signals

All tasks are complete in this branch. [P] = can run in parallel.

## Phase 1: Data
- [x] T101 Schema columns, `geofence_events`, `v_stop_service` OTD columns (`tms_agent/schema.py`)
- [x] T102 DDL layout for `geofence_events` (`tms_data/ddl.py`), regenerate `sql/*_schema.sql`
- [x] T103 Generator post-pass `build_mclane_signals()` on a separate RNG + route-time consistency
- [x] T104 Planted stories: Fresh Basket dwell up, Cluck & Co dwell down, DC07 early restaurant arrivals, ZIP_CENTROID geocodes, DC08 out-of-route drivers

## Phase 2: Tools (US1-US4)
- [x] T105 [P] `get_otd_scorecard` (US1)
- [x] T106 [P] `get_dwell_time_changes` (US2)
- [x] T107 [P] `get_geofence_compliance`, `track_load` (US3)
- [x] T108 [P] `tms_agent/mileage.py`, `check_pcmiler_miles`, `get_out_of_route_miles` (US4)
- [x] T109 MILES_INFLATED evidence cites PC*MILER

## Phase 3: Agents and surfaces
- [x] T110 `delivery_performance_analyst`; mileage tools on audit and fleet specialists; prompts
- [x] T111 KPI snapshot and weekly insights pack
- [x] T112 Toolbox tools in `tools.yaml`; `mclane-delivery-signals` skill

## Phase 4: Verification
- [x] T113 `tests/test_mclane_signals.py`, new CALLS in `tests/test_tools.py` (DuckDB + PostgreSQL)
- [x] T114 Eval cases and docs (DATA_STORY, DEMO_SCRIPT, SOLUTION_DESIGN)
