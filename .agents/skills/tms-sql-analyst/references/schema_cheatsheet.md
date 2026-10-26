# TMS schema cheat sheet

Full column descriptions: `scripts/query.py --schema`. Source of truth: `tms_agent/schema.py`.

| Table | TMW equivalent | Grain | Key columns |
|---|---|---|---|
| customers | company (bill-to) | customer chain | customer_id, customer_name, segment, service_tier, on_time_target_pct, late_penalty_per_stop |
| locations | company (DC / store / restaurant) | place | location_id, location_type (DC, STORE, RESTAURANT...), customer_id, dc_id, state, padd_region, dock hours |
| carriers | carrier | carrier | carrier_id (MCLN = private fleet), carrier_type, equipment_types, safety_rating, insurance_expiry_date |
| drivers / tractors / trailers | manpowerprofile / tractorprofile / trailerprofile | asset | hos_drive_hours_remaining, next_pm_due_date, reefer_unit_age_years |
| orders | orderheader + freightdetail | delivery order | order_id, customer_id, dest_location_id, load_id, commodity, revenue columns |
| loads | legheader | trip from a DC | load_id, origin_dc_id, carrier_id, equipment_type, load_date, load_status, stop_count, miles, dest_region_state |
| stops | stops | delivery stop | stop_id, load_id, order_id, appt window, arrival_ts, on_time_flag, minutes_late, dwell_minutes, detention_minutes, cases_short |
| load_costs | paydetail | cost line | load_id, cost_type, amount |
| invoices | invoiceheader | customer invoice | order_id, detention_billed, other_accessorial_billed, late_penalty_amount |
| carrier_tenders | tender history | tender offer | load_id, carrier_id, response (ACCEPTED / REJECTED / EXPIRED) |
| carrier_rates | rate tables | carrier x lane x equipment | rate_per_mile, stop_charge, fsc_base_price, fsc_mpg, detention_rate_per_hr, free_time_minutes |
| carrier_invoices | freight bills / EDI 210 | carrier bill | load_id, carrier_id, source, billed_* columns, lumper_receipt_attached |
| fuel_prices | DOE diesel index | week x PADD | week_start_date, padd_region, diesel_price_per_gal |
| check_calls | checkcall | telematics ping | load_id, event_ts, reefer_temp_f, reefer_setpoint_f |
| exceptions | | exception event | load_id, stop_id, exception_type, severity, root_cause, resolved_flag, cost_impact |
| agent_decision_log | (new) | agent decision | decision_type, status, amount_usd, confidence, rationale, data_used |

## Views (use these first)

- `v_stop_service`: one row per arrived stop with customer, DC and carrier context. On-time, dwell, detention, shortage.
- `v_load_profitability`: one row per COMPLETED load. `lane` is `'DC01->TX'`. Revenue, cost, margin, margin_pct, empty miles.
- `v_carrier_scorecard`: all-time per carrier. Loads, on_time_pct, avg_minutes_late, claims_case_rate.

## Joins

- `stops.load_id = loads.load_id`, `stops.order_id = orders.order_id`, `stops.location_id = locations.location_id`
- `locations.customer_id = customers.customer_id`, `invoices.order_id = orders.order_id`
- Contract rate for a carrier bill: `carrier_invoices → loads` then `carrier_rates` on
  `carrier_id, origin_dc_id, dest_state = loads.dest_region_state, equipment_type`
- Fuel index: `locations.padd_region` of the origin DC and the week of `load_date`

## Gotchas

- Dataset "today" is 2026-10-27 (`query.py --as-of`). Never use `CURRENT_DATE`.
- `loads.driver_id` is NULL for outside carriers. `load_status` is PLANNED, DISPATCHED, IN_TRANSIT, COMPLETED or CANCELLED.
- Booleans (`on_time_flag`, `resolved_flag`, `lumper_receipt_attached`) are true booleans.
- Some carrier invoices have NULL fuel surcharge or rate on purpose (messy input). Report them, don't impute.
