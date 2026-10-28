---
name: mclane-delivery-signals
description: Analyze McLane delivery operations signals - Retail vs Restaurant on-time delivery (OTD), dwell time changes at stores and restaurants, geofence arrivals and bad geocodes, PC*MILER miles vs billed or odometer miles, and out-of-route drivers. Use for any OTD, dwell, geofence, geolocation, PC*MILER or out-of-route question or code change.
---

# McLane delivery signals

The tools live in `tms_agent/tools/delivery.py` (OTD, dwell, geofence, live tracking) and
`tms_agent/tools/miles.py` (PC*MILER check, out-of-route). The PC*MILER client is
`tms_agent/mileage.py`. This skill runs them from the command line and explains the rules.

## Run

```bash
S=.agents/skills/mclane-delivery-signals/scripts/signals.py
uv run python $S otd --days 28 --group-by channel          # or dc | customer | carrier | week, --channel RESTAURANT
uv run python $S dwell --recent-days 21 --baseline-days 56 # receivers whose dwell moved
uv run python $S geofence --days 30                        # auto-arrival %, locations with bad geocodes + fix
uv run python $S track LGH0005441                          # last ELD ping, next stop, projected arrival
uv run python $S pcmiler LGH0000088                        # PC*MILER practical/shortest vs billed vs odometer
uv run python $S oor --days 90 --group-by driver           # out-of-route miles vs PC*MILER
```

## Business rules

| Signal | Rule | Where |
|---|---|---|
| Retail OTD | On time = arrival not after the appointment window end | `v_stop_service.otd_flag`, `otd_channel = 'RETAIL'` |
| Restaurant OTD | Also not more than 15 min before the window start (restaurants are often not staffed early) | `otd_channel = 'RESTAURANT'`, `RESTAURANT_EARLY_GRACE_MIN` |
| Dwell change | Recent window average dwell vs baseline window, per customer / location / DC; groups under `min_stops` are LOW_SAMPLE | `get_dwell_time_changes` |
| Geofence | Tracked arrivals should be `arrival_source = 'GEOFENCE'`; a location missed >= 50% of the time is a likely bad geocode (`geocode_quality = 'ZIP_CENTROID'`) | `get_geofence_compliance` |
| PC*MILER | TMW planned miles are PC*MILER practical (`loads.total_miles`, `stops.pcmiler_leg_miles`); billed miles > practical + 2% is MILES_INFLATED | `check_pcmiler_miles`, audit rules |
| Out-of-route | Odometer miles / PC*MILER practical miles - 1; flagged above `TMS_OOR_FLAG_PCT` (8%) | `get_out_of_route_miles` |

**Flag, don't guess.** Without `PCMILER_API_KEY`, re-routed miles are labelled
`ESTIMATE_HAVERSINE` and must never be presented as PC*MILER miles. A location without enough
stationary ELD pings gets `NEEDS_REVIEW` instead of suggested coordinates.

## Configuration

| Variable | Default | Used by |
|---|---|---|
| `PCMILER_API_KEY` | unset | live PC*MILER route miles (Trimble Maps API key) |
| `PCMILER_BASE_URL` | `https://pcmiler.alk.com/apis/rest/v1.0/Service.svc` | PC*MILER client |
| `PCMILER_EXTRA_PARAMS` | unset | account-specific route options (verify in the Trimble Maps docs) |
| `TMS_TRUCK_HOUR_COST_USD` | 85 | $ impact of dwell changes |
| `TMS_OOR_FLAG_PCT` | 0.08 | out-of-route flag |

## Planted stories in the synthetic data

Fresh Basket Grocers dwell up ~28 min in the last 3 weeks (new receiving process); Cluck & Co
Chicken dwell down ~16 min (after-hours key drops); DC07 private fleet drivers arrive early at
restaurants (Restaurant OTD hit while "not late" looks fine); ~6% of stores and restaurants have
ZIP_CENTROID geocodes 1.5-4 km off; four DC08 drivers run ~13% out-of-route miles.
`tests/test_mclane_signals.py` asserts each one.
