# Feature Specification: McLane delivery signals (PC*MILER, geofences, dwell change, Retail vs Restaurant OTD)

**Feature Branch**: `002-mclane-delivery-signals`
**Created**: 2026-10-28
**Status**: Implemented
**Input**: "McLane uses PC*MILER, Dwell Time Change, Retail & Restaurant On-time Delivery (OTD), Geofence,
Geo locations. Add them to the TMS Intelligence agent."

## Clarifications

- Q: How is OTD measured for Retail vs Restaurant? → A: Retail (grocery / convenience, business unit
  GROCERY) is on time when it does not arrive after the appointment window end. Restaurant
  (FOODSERVICE) must also not arrive more than 15 minutes before the window start.
- Q: Where do planned miles come from? → A: TMW's PC*MILER interface (practical route). Shortest-route
  miles are kept for disputes. Live PC*MILER calls are optional and need an API key.
- Q: What is a dwell time change? → A: The recent average dwell per receiver (default 21 days) versus a
  baseline window (default 56 days before it), costed at a configurable truck-hour rate ($85).
- Q: How are geofence problems detected? → A: Tracked arrivals should be recorded by geofence. A location
  where most tracked arrivals were keyed manually likely has wrong coordinates; stationary ELD pings at
  the manual arrival suggest the corrected coordinates.

## User Scenarios & Testing

### User Story 1 - Retail and Restaurant OTD (Priority: P1)
An operations leader asks "How is OTD for retail vs restaurants?" and gets both channels against
target, with early and late misses split, by DC, customer, carrier or week.

**Acceptance Scenarios**:
1. **Given** the dataset, **When** OTD is requested, **Then** Retail OTD equals its not-late rate and Restaurant OTD is lower because early arrivals count as misses.
2. **Given** restaurant OTD by DC, **When** compared, **Then** DC07 has the highest early-miss rate (planted).

### User Story 2 - Dwell time changes (Priority: P1)
A planner asks "Where did dwell time change?" and sees receivers with the biggest recent change,
truck hours and annualized $.

**Acceptance Scenarios**:
1. **Given** recent vs baseline windows, **When** run, **Then** Fresh Basket Grocers shows an INCREASE of ≥ 15 min and Cluck & Co Chicken a DECREASE.
2. **Given** a group with few stops, **When** run, **Then** it is listed as LOW_SAMPLE, not ranked.

### User Story 3 - Geofences and geolocations (Priority: P2)
Operations sees the geofence auto-arrival rate, locations whose geofence never fires, and suggested
coordinates. A dispatcher can ask where a truck is and when it will arrive.

**Acceptance Scenarios**:
1. **Given** tracked arrivals, **When** compliance runs, **Then** flagged locations are ZIP_CENTROID geocodes with suggested coordinates more than 1 km away.
2. **Given** an in-transit load with pings, **When** track_load runs, **Then** it returns the next stop, remaining miles with their source and a projected arrival.
3. **Given** no PC*MILER key, **When** miles are re-routed, **Then** they are labelled ESTIMATE_HAVERSINE.

### User Story 4 - PC*MILER miles in audit and fleet (Priority: P2)
Freight audit compares billed miles to PC*MILER practical miles; fleet managers see out-of-route miles.

**Acceptance Scenarios**:
1. **Given** a carrier bill with inflated miles, **When** check_pcmiler_miles runs, **Then** the verdict is MILES_INFLATED with PC*MILER evidence.
2. **Given** odometer miles, **When** out-of-route runs, **Then** the four planted DC08 drivers are flagged HIGH_OUT_OF_ROUTE with $ impact.

### Edge Cases
- PC*MILER call fails → fall back to the estimate and say why.
- Location without enough stationary pings → NEEDS_REVIEW instead of suggested coordinates.
- Load with no telematics → NO_TELEMATICS review flag.

## Requirements

### Functional Requirements
- **FR-101**: `v_stop_service` exposes `otd_channel` and `otd_flag` with the rules above.
- **FR-102**: `get_otd_scorecard` groups by channel, dc, customer, carrier or week, with target gap and penalty exposure.
- **FR-103**: `get_dwell_time_changes` compares windows by customer, location, dc or channel with $ impact.
- **FR-104**: `get_geofence_compliance` reports the arrival-source mix and suspect geocodes with suggested fixes.
- **FR-105**: `track_load` projects arrival from the latest ELD ping.
- **FR-106**: `check_pcmiler_miles` and `get_out_of_route_miles` compare PC*MILER, billed and odometer miles.
- **FR-107**: `tms_agent/mileage.py` calls PC*MILER Web Services when `PCMILER_API_KEY` is set and labels estimates otherwise.
- **FR-108**: KPI snapshot and weekly insights include Retail / Restaurant OTD, dwell changes, out-of-route and geocode fixes.

### Key Entities
New columns: `loads.mileage_source`, `loads.pcmiler_shortest_miles`, `loads.actual_odometer_miles`,
`stops.minutes_early`, `stops.arrival_source`, `stops.pcmiler_leg_miles`, `locations.geocode_quality`,
`locations.geofence_radius_m`. New table: `geofence_events` (see `data-model.md`).

## Success Criteria
- **SC-101**: `tests/test_mclane_signals.py` passes offline; the new tools pass on PostgreSQL.
- **SC-102**: Every planted story is found by its tool.
- **SC-103**: No estimate is ever presented as PC*MILER miles.
