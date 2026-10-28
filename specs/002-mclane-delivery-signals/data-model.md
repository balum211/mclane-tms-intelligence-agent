# Data Model: McLane delivery signals

## New columns

| Table | Column | Type | Meaning |
|---|---|---|---|
| loads | mileage_source | STRING | PCMILER_PRACTICAL (TMW PC*MILER interface) or MANUAL |
| loads | pcmiler_shortest_miles | FLOAT | PC*MILER shortest route for the same stops |
| loads | actual_odometer_miles | FLOAT | ELD / odometer miles (private fleet, completed loads) |
| stops | minutes_early | INT | Minutes before window start |
| stops | arrival_source | STRING | GEOFENCE, DRIVER_MANUAL or CARRIER_EDI214 |
| stops | pcmiler_leg_miles | FLOAT | PC*MILER practical miles from the previous stop |
| locations | geocode_quality | STRING | ROOFTOP, STREET or ZIP_CENTROID |
| locations | geofence_radius_m | INT | Geofence radius (DC 400 m, store 200 m, restaurant 150 m) |

## New table: geofence_events
`geofence_event_id` (PK), `load_id`, `stop_id`, `location_id`, `event_type` (ENTER / EXIT), `event_ts`,
`event_date`, `latitude`, `longitude`, `distance_from_location_m`. BigQuery: partitioned by
`event_date`, clustered by `location_id, load_id`. AlloyDB: indexes on `stop_id`, `location_id`, `event_date`.

## View changes: v_stop_service
Adds `minutes_early`, `arrival_source`, `pcmiler_leg_miles`, `otd_channel` (RETAIL when business unit is
GROCERY, RESTAURANT when FOODSERVICE) and `otd_flag`.
