CREATE TABLE IF NOT EXISTS `YOUR_PROJECT.mclane_tms.customers` (
  customer_id STRING NOT NULL OPTIONS(description='Customer code, e.g. CUS0001.'),
  customer_name STRING OPTIONS(description='Customer (chain) name.'),
  segment STRING OPTIONS(description='RETAIL_CONVENIENCE | RETAIL_GROCERY | RESTAURANT_QSR | RESTAURANT_CASUAL | MILITARY.'),
  business_unit STRING OPTIONS(description='GROCERY (retail supply) or FOODSERVICE (restaurant supply).'),
  service_tier STRING OPTIONS(description='PLATINUM | GOLD | SILVER. Drives on-time targets and penalties.'),
  on_time_target_pct FLOAT64 OPTIONS(description='Contracted on-time delivery target, e.g. 0.97.'),
  late_penalty_per_stop NUMERIC OPTIONS(description='Contractual chargeback in USD per late stop.'),
  payment_terms_days INT64 OPTIONS(description='Invoice payment terms in days.'),
  hq_state STRING OPTIONS(description='Two letter state of the customer HQ.')
)
OPTIONS(description='Bill-to customers: convenience retail, grocery, QSR and casual-dining restaurant chains. TMW: company (cmp_billto = \'Y\')');

CREATE TABLE IF NOT EXISTS `YOUR_PROJECT.mclane_tms.locations` (
  location_id STRING NOT NULL OPTIONS(description='Location code, e.g. DC01, STR00042, RST00117.'),
  location_name STRING OPTIONS(description='Display name.'),
  location_type STRING OPTIONS(description='DC | STORE | RESTAURANT | VENDOR.'),
  customer_id STRING OPTIONS(description='Owning customer for STORE / RESTAURANT locations, NULL for DCs and vendors.'),
  dc_id STRING OPTIONS(description='Servicing distribution center (DC location_id) for stores and restaurants.'),
  city STRING OPTIONS(description='City.'),
  state STRING OPTIONS(description='Two letter state.'),
  latitude FLOAT64 OPTIONS(description='Latitude.'),
  longitude FLOAT64 OPTIONS(description='Longitude.'),
  dock_open_hour INT64 OPTIONS(description='Receiving window open hour (0-23, local).'),
  dock_close_hour INT64 OPTIONS(description='Receiving window close hour (0-23, local).'),
  avg_unload_minutes INT64 OPTIONS(description='Typical unload time in minutes.'),
  requires_liftgate BOOL OPTIONS(description='Delivery needs a liftgate / small-format trailer.'),
  padd_region STRING OPTIONS(description='DOE fuel region (PADD1..PADD5) used for fuel surcharge.')
)
OPTIONS(description='Every physical place: distribution centers (DC), stores, restaurants, vendors and terminals. TMW: company (shipper / consignee / terminal rows)');

CREATE TABLE IF NOT EXISTS `YOUR_PROJECT.mclane_tms.carriers` (
  carrier_id STRING NOT NULL OPTIONS(description='Carrier code. MCLN is the private (asset) fleet.'),
  carrier_name STRING OPTIONS(description='Carrier name.'),
  scac STRING OPTIONS(description='Standard Carrier Alpha Code.'),
  carrier_type STRING OPTIONS(description='PRIVATE_FLEET | CONTRACT | BROKER.'),
  equipment_types STRING OPTIONS(description='Comma separated equipment the carrier runs: DRY_53, REEFER_53, MULTI_TEMP_53.'),
  safety_rating STRING OPTIONS(description='FMCSA style rating: SATISFACTORY | CONDITIONAL | UNRATED.'),
  insurance_expiry_date DATE OPTIONS(description='Cargo / liability insurance expiry.'),
  contract_rate_per_mile NUMERIC OPTIONS(description='Contracted linehaul USD per loaded mile.'),
  home_state STRING OPTIONS(description='Carrier home state.')
)
OPTIONS(description='McLane private fleet plus contract carriers and brokers used for overflow and long-haul. TMW: carrier');

CREATE TABLE IF NOT EXISTS `YOUR_PROJECT.mclane_tms.drivers` (
  driver_id STRING NOT NULL OPTIONS(description='Driver code.'),
  driver_name STRING OPTIONS(description='Driver full name (synthetic).'),
  home_dc_id STRING OPTIONS(description='Home distribution center.'),
  driver_type STRING OPTIONS(description='COMPANY | TEAM | OWNER_OPERATOR.'),
  hire_date DATE OPTIONS(description='Hire date.'),
  hazmat_endorsed BOOL OPTIONS(description='Has hazmat endorsement.'),
  status STRING OPTIONS(description='ACTIVE | ON_LEAVE | TERMINATED.'),
  safety_score INT64 OPTIONS(description='0-100 telematics safety score (higher is safer).'),
  hos_drive_hours_remaining FLOAT64 OPTIONS(description='Hours of driving left today under the 11 hour rule.'),
  hos_cycle_hours_remaining FLOAT64 OPTIONS(description='Hours left in the 70 hour / 8 day cycle.')
)
OPTIONS(description='Private fleet drivers with hours-of-service (HOS) status. TMW: manpowerprofile');

CREATE TABLE IF NOT EXISTS `YOUR_PROJECT.mclane_tms.tractors` (
  tractor_id STRING NOT NULL OPTIONS(description='Tractor unit number.'),
  home_dc_id STRING OPTIONS(description='Home distribution center.'),
  make STRING OPTIONS(description='Manufacturer.'),
  model_year INT64 OPTIONS(description='Model year.'),
  fuel_type STRING OPTIONS(description='DIESEL | CNG | ELECTRIC.'),
  odometer_miles INT64 OPTIONS(description='Current odometer.'),
  avg_mpg FLOAT64 OPTIONS(description='Rolling average miles per gallon.'),
  status STRING OPTIONS(description='IN_SERVICE | SHOP | OUT_OF_SERVICE.'),
  next_pm_due_date DATE OPTIONS(description='Next preventive maintenance due date.')
)
OPTIONS(description='Private fleet power units. TMW: tractorprofile');

CREATE TABLE IF NOT EXISTS `YOUR_PROJECT.mclane_tms.trailers` (
  trailer_id STRING NOT NULL OPTIONS(description='Trailer number.'),
  home_dc_id STRING OPTIONS(description='Home distribution center.'),
  trailer_type STRING OPTIONS(description='DRY_53 | REEFER_53 | MULTI_TEMP_53 | PUP_28.'),
  model_year INT64 OPTIONS(description='Model year.'),
  reefer_unit_age_years INT64 OPTIONS(description='Age of the refrigeration unit, NULL for dry trailers.'),
  status STRING OPTIONS(description='IN_SERVICE | SHOP | OUT_OF_SERVICE.')
)
OPTIONS(description='Private fleet trailers. Multi-temp trailers carry dry, chilled and frozen in one trip. TMW: trailerprofile');

CREATE TABLE IF NOT EXISTS `YOUR_PROJECT.mclane_tms.orders` (
  order_id STRING NOT NULL OPTIONS(description='Order number (ord_hdrnumber).'),
  customer_id STRING OPTIONS(description='Bill-to customer.'),
  origin_location_id STRING OPTIONS(description='Shipping DC.'),
  dest_location_id STRING OPTIONS(description='Delivery store / restaurant.'),
  load_id STRING OPTIONS(description='Load (trip) the order was planned on. NULL if cancelled before planning.'),
  order_date DATE OPTIONS(description='Date the order was entered.'),
  requested_delivery_date DATE OPTIONS(description='Requested delivery date.'),
  commodity STRING OPTIONS(description='DRY_GROCERY | TOBACCO_CANDY | CHILLED | FROZEN | FOODSERVICE_MIXED.'),
  temperature_class STRING OPTIONS(description='AMBIENT | CHILLED | FROZEN | MULTI.'),
  cases INT64 OPTIONS(description='Ordered cases.'),
  weight_lbs INT64 OPTIONS(description='Gross weight in pounds.'),
  cube_ft INT64 OPTIONS(description='Cube in cubic feet.'),
  revenue_linehaul NUMERIC OPTIONS(description='Billed linehaul / delivery fee USD.'),
  revenue_fuel_surcharge NUMERIC OPTIONS(description='Billed fuel surcharge USD.'),
  revenue_accessorial NUMERIC OPTIONS(description='Billed accessorials USD (detention, lumper, liftgate...).'),
  total_revenue NUMERIC OPTIONS(description='Sum of all billed revenue USD.'),
  order_status STRING OPTIONS(description='PLANNED | DISPATCHED | IN_TRANSIT | DELIVERED | CANCELLED.')
)
PARTITION BY requested_delivery_date
CLUSTER BY customer_id
OPTIONS(description='Customer delivery orders. One order = one store/restaurant delivery from a DC. TMW: orderheader + freightdetail');

CREATE TABLE IF NOT EXISTS `YOUR_PROJECT.mclane_tms.loads` (
  load_id STRING NOT NULL OPTIONS(description='Load / leg number (lgh_number).'),
  origin_dc_id STRING OPTIONS(description='Origin DC.'),
  carrier_id STRING OPTIONS(description='Carrier that ran the load. MCLN = private fleet.'),
  driver_id STRING OPTIONS(description='Driver for private fleet loads, NULL for outside carriers.'),
  tractor_id STRING OPTIONS(description='Tractor for private fleet loads.'),
  trailer_id STRING OPTIONS(description='Trailer for private fleet loads.'),
  equipment_type STRING OPTIONS(description='DRY_53 | REEFER_53 | MULTI_TEMP_53 | PUP_28.'),
  load_date DATE OPTIONS(description='Dispatch date of the load. Use this for date filtering.'),
  planned_start_ts TIMESTAMP OPTIONS(description='Planned departure from DC.'),
  actual_start_ts TIMESTAMP OPTIONS(description='Actual departure from DC.'),
  planned_end_ts TIMESTAMP OPTIONS(description='Planned return / final stop departure.'),
  actual_end_ts TIMESTAMP OPTIONS(description='Actual return / final stop departure. NULL while in transit.'),
  stop_count INT64 OPTIONS(description='Number of delivery stops.'),
  loaded_miles FLOAT64 OPTIONS(description='Miles driven with freight.'),
  empty_miles FLOAT64 OPTIONS(description='Deadhead / return miles.'),
  total_miles FLOAT64 OPTIONS(description='loaded_miles + empty_miles.'),
  dest_region_state STRING OPTIONS(description='State of the final stop, used to define lanes (origin DC -> state).'),
  load_status STRING OPTIONS(description='PLANNED | DISPATCHED | IN_TRANSIT | COMPLETED | CANCELLED.'),
  total_revenue NUMERIC OPTIONS(description='Sum of revenue of orders on the load USD.'),
  total_cost NUMERIC OPTIONS(description='Sum of load_costs USD.')
)
PARTITION BY load_date
CLUSTER BY origin_dc_id, carrier_id
OPTIONS(description='A trip (route) from one DC covering one or more delivery stops, run by a driver/tractor/trailer or a carrier. TMW: legheader');

CREATE TABLE IF NOT EXISTS `YOUR_PROJECT.mclane_tms.stops` (
  stop_id STRING NOT NULL OPTIONS(description='Stop number (stp_number).'),
  load_id STRING OPTIONS(description='Load.'),
  order_id STRING OPTIONS(description='Order delivered at this stop.'),
  stop_sequence INT64 OPTIONS(description='1-based sequence on the route.'),
  location_id STRING OPTIONS(description='Delivery location.'),
  delivery_date DATE OPTIONS(description='Scheduled delivery date.'),
  appt_window_start_ts TIMESTAMP OPTIONS(description='Appointment window start.'),
  appt_window_end_ts TIMESTAMP OPTIONS(description='Appointment window end.'),
  arrival_ts TIMESTAMP OPTIONS(description='Actual arrival. NULL if not yet arrived.'),
  departure_ts TIMESTAMP OPTIONS(description='Actual departure.'),
  on_time_flag BOOL OPTIONS(description='TRUE when arrival <= appt_window_end_ts.'),
  minutes_late INT64 OPTIONS(description='Minutes after window end (0 if on time).'),
  dwell_minutes INT64 OPTIONS(description='Minutes from arrival to departure.'),
  detention_minutes INT64 OPTIONS(description='Billable wait beyond the 2 hour free time.'),
  cases_delivered INT64 OPTIONS(description='Cases delivered.'),
  cases_short INT64 OPTIONS(description='Cases short (not delivered).'),
  cases_damaged INT64 OPTIONS(description='Cases damaged.'),
  refused_flag BOOL OPTIONS(description='Receiver refused all or part of the delivery.')
)
PARTITION BY delivery_date
CLUSTER BY location_id, load_id
OPTIONS(description='Each delivery stop on a load with appointment window, actual arrival and service outcome. TMW: stops');

CREATE TABLE IF NOT EXISTS `YOUR_PROJECT.mclane_tms.load_costs` (
  cost_id STRING NOT NULL OPTIONS(description='Cost line id.'),
  load_id STRING OPTIONS(description='Load.'),
  cost_type STRING OPTIONS(description='DRIVER_PAY | FUEL | CARRIER_LINEHAUL | DETENTION_PAID | LUMPER | LAYOVER | TOLLS | MAINTENANCE_ALLOC.'),
  amount NUMERIC OPTIONS(description='USD.'),
  cost_date DATE OPTIONS(description='Accrual date.')
)
PARTITION BY cost_date
CLUSTER BY load_id, cost_type
OPTIONS(description='Cost lines per load: driver pay, fuel, carrier linehaul, accessorials paid out, tolls, maintenance allocation. TMW: paydetail + carrier invoice (assetassignment)');

CREATE TABLE IF NOT EXISTS `YOUR_PROJECT.mclane_tms.invoices` (
  invoice_id STRING NOT NULL OPTIONS(description='Invoice number.'),
  order_id STRING OPTIONS(description='Order.'),
  customer_id STRING OPTIONS(description='Bill-to customer.'),
  invoice_date DATE OPTIONS(description='Invoice date.'),
  linehaul_amount NUMERIC OPTIONS(description='Linehaul billed USD.'),
  fuel_surcharge_amount NUMERIC OPTIONS(description='Fuel surcharge billed USD.'),
  detention_billed NUMERIC OPTIONS(description='Detention billed to customer USD.'),
  other_accessorial_billed NUMERIC OPTIONS(description='Other accessorials billed USD.'),
  late_penalty_amount NUMERIC OPTIONS(description='Chargeback deducted by customer for late delivery USD (negative revenue).'),
  total_amount NUMERIC OPTIONS(description='Net invoice total USD.'),
  paid_flag BOOL OPTIONS(description='Invoice paid.'),
  days_to_pay INT64 OPTIONS(description='Days from invoice to payment, NULL if unpaid.')
)
PARTITION BY invoice_date
CLUSTER BY customer_id
OPTIONS(description='Customer invoices per order including accessorial charges actually billed. TMW: invoiceheader + invoicedetail');

CREATE TABLE IF NOT EXISTS `YOUR_PROJECT.mclane_tms.carrier_tenders` (
  tender_id STRING NOT NULL OPTIONS(description='Tender id.'),
  load_id STRING OPTIONS(description='Load offered.'),
  carrier_id STRING OPTIONS(description='Carrier offered to.'),
  tender_ts TIMESTAMP OPTIONS(description='When the tender was sent.'),
  tender_date DATE OPTIONS(description='Date the tender was sent.'),
  offered_rate NUMERIC OPTIONS(description='Offered linehaul USD.'),
  response STRING OPTIONS(description='ACCEPTED | REJECTED | EXPIRED.'),
  response_minutes INT64 OPTIONS(description='Minutes to respond.')
)
PARTITION BY tender_date
CLUSTER BY carrier_id
OPTIONS(description='Load tenders offered to outside carriers and their response. TMW: carrier tender / load offer history');

CREATE TABLE IF NOT EXISTS `YOUR_PROJECT.mclane_tms.carrier_rates` (
  rate_id STRING NOT NULL OPTIONS(description='Rate contract line id.'),
  carrier_id STRING OPTIONS(description='Carrier.'),
  origin_dc_id STRING OPTIONS(description='Origin DC.'),
  dest_state STRING OPTIONS(description='Destination state.'),
  equipment_type STRING OPTIONS(description='DRY_53 | REEFER_53 | MULTI_TEMP_53 | PUP_28.'),
  rate_per_mile NUMERIC OPTIONS(description='Contracted linehaul USD per total mile.'),
  stop_charge NUMERIC OPTIONS(description='USD per delivery stop.'),
  min_charge NUMERIC OPTIONS(description='Minimum linehaul USD per load.'),
  fsc_base_price FLOAT64 OPTIONS(description='Fuel surcharge: DOE price at which surcharge is zero (USD/gal).'),
  fsc_mpg FLOAT64 OPTIONS(description='Fuel surcharge: mpg divisor. FSC per mile = (DOE price - base) / mpg.'),
  detention_rate_per_hr NUMERIC OPTIONS(description='Detention USD per hour after free time.'),
  free_time_minutes INT64 OPTIONS(description='Free time at each stop before detention applies.'),
  lumper_requires_receipt BOOL OPTIONS(description='Lumper is only payable with a receipt.'),
  effective_date DATE OPTIONS(description='Contract start.'),
  expiry_date DATE OPTIONS(description='Contract end.')
)
OPTIONS(description='Contracted rates per outside carrier, lane (origin DC -> destination state) and equipment, with accessorial rules. TMW: carrier rate tables (tariff / contract rates)');

CREATE TABLE IF NOT EXISTS `YOUR_PROJECT.mclane_tms.carrier_invoices` (
  carrier_invoice_id STRING NOT NULL OPTIONS(description='Carrier invoice (freight bill) number.'),
  load_id STRING OPTIONS(description='Load billed.'),
  carrier_id STRING OPTIONS(description='Billing carrier.'),
  invoice_date DATE OPTIONS(description='Invoice date.'),
  source STRING OPTIONS(description='EDI_210 | PDF_SCAN | EMAIL.'),
  document_uri STRING OPTIONS(description='Location of the invoice document (scanned PDF) when source is PDF_SCAN/EMAIL.'),
  billed_rate_per_mile NUMERIC OPTIONS(description='Rate per mile shown on the invoice. NULL when not legible.'),
  billed_miles FLOAT64 OPTIONS(description='Miles billed.'),
  billed_linehaul NUMERIC OPTIONS(description='Linehaul billed USD.'),
  billed_fuel_surcharge NUMERIC OPTIONS(description='Fuel surcharge billed USD. NULL when missing on the document.'),
  billed_detention NUMERIC OPTIONS(description='Detention billed USD.'),
  billed_lumper NUMERIC OPTIONS(description='Lumper billed USD.'),
  lumper_receipt_attached BOOL OPTIONS(description='Lumper receipt attached.'),
  billed_other NUMERIC OPTIONS(description='Other accessorials USD (layover, tolls, TONU).'),
  billed_total NUMERIC OPTIONS(description='Invoice total USD.'),
  invoice_status STRING OPTIONS(description='RECEIVED | APPROVED | PAID | DISPUTED.')
)
OPTIONS(description='Freight bills received from outside carriers, to be audited against carrier_rates, stops and fuel_prices. TMW: carrier freight bill / EDI 210 (settlement & freight audit)');

CREATE TABLE IF NOT EXISTS `YOUR_PROJECT.mclane_tms.check_calls` (
  check_call_id STRING NOT NULL OPTIONS(description='Ping id.'),
  load_id STRING OPTIONS(description='Load.'),
  event_ts TIMESTAMP OPTIONS(description='Ping time.'),
  latitude FLOAT64 OPTIONS(description='Latitude.'),
  longitude FLOAT64 OPTIONS(description='Longitude.'),
  speed_mph FLOAT64 OPTIONS(description='Speed.'),
  reefer_temp_f FLOAT64 OPTIONS(description='Reefer return air temperature F, NULL for dry.'),
  reefer_setpoint_f FLOAT64 OPTIONS(description='Reefer setpoint F, NULL for dry.'),
  eta_next_stop_ts TIMESTAMP OPTIONS(description='ETA to next stop computed by telematics.')
)
PARTITION BY DATE(event_ts)
CLUSTER BY load_id
OPTIONS(description='Telematics / ELD pings for loads, including reefer temperature and ETA. TMW: checkcall');

CREATE TABLE IF NOT EXISTS `YOUR_PROJECT.mclane_tms.exceptions` (
  exception_id STRING NOT NULL OPTIONS(description='Exception id.'),
  load_id STRING OPTIONS(description='Load.'),
  stop_id STRING OPTIONS(description='Stop, when stop specific.'),
  exception_type STRING OPTIONS(description='LATE_ARRIVAL | DETENTION | REEFER_TEMP_EXCURSION | BREAKDOWN | HOS_RISK | REFUSED_DELIVERY | SHORTAGE | DAMAGE | WEATHER_DELAY.'),
  severity STRING OPTIONS(description='LOW | MEDIUM | HIGH | CRITICAL.'),
  event_ts TIMESTAMP OPTIONS(description='When raised.'),
  event_date DATE OPTIONS(description='Date raised.'),
  root_cause STRING OPTIONS(description='TRAFFIC | DOCK_CONGESTION | LATE_DISPATCH | EQUIPMENT | DRIVER | WEATHER | CUSTOMER | PICKING_ERROR.'),
  description STRING OPTIONS(description='Free text.'),
  resolved_flag BOOL OPTIONS(description='Resolved.'),
  cost_impact NUMERIC OPTIONS(description='Estimated USD impact.')
)
PARTITION BY event_date
CLUSTER BY exception_type, severity
OPTIONS(description='Operational exceptions raised on loads and stops. TMW: expiration / event log (custom)');

CREATE TABLE IF NOT EXISTS `YOUR_PROJECT.mclane_tms.agent_decision_log` (
  decision_id STRING NOT NULL OPTIONS(description='Decision id.'),
  decision_ts TIMESTAMP OPTIONS(description='When the decision was logged (UTC).'),
  decision_type STRING OPTIONS(description='CARRIER_TENDER | INVOICE_DISPUTE | DELAY_MITIGATION | OTHER.'),
  load_id STRING OPTIONS(description='Load, when applicable.'),
  carrier_id STRING OPTIONS(description='Carrier, when applicable.'),
  amount_usd NUMERIC OPTIONS(description='Dollar value of the action.'),
  confidence FLOAT64 OPTIONS(description='Model confidence 0-1.'),
  status STRING OPTIONS(description='AUTO_EXECUTED | PENDING_APPROVAL | APPROVED | REJECTED | BLOCKED.'),
  actor STRING OPTIONS(description='agent or the approving user.'),
  rationale STRING OPTIONS(description='Reasoning shown to the user.'),
  data_used STRING OPTIONS(description='JSON describing the evidence used.')
)
OPTIONS(description='Every recommendation / auto-action taken by the agent: what, why, data used, confidence, $ impact, approval. TMW: (new) AI decision audit trail');

CREATE TABLE IF NOT EXISTS `YOUR_PROJECT.mclane_tms.fuel_prices` (
  week_start_date DATE NOT NULL OPTIONS(description='Monday of the week.'),
  padd_region STRING OPTIONS(description='PADD1 East Coast | PADD2 Midwest | PADD3 Gulf | PADD4 Rockies | PADD5 West.'),
  diesel_price_per_gal FLOAT64 OPTIONS(description='USD per gallon.')
)
OPTIONS(description='Weekly DOE diesel price by PADD region, drives fuel surcharge. TMW: fuelprice (DOE index)');

CREATE OR REPLACE VIEW `YOUR_PROJECT.mclane_tms.v_load_profitability` AS
SELECT l.load_id, l.load_date, l.origin_dc_id, dc.location_name AS origin_dc_name,
       l.dest_region_state, l.origin_dc_id || '->' || l.dest_region_state AS lane,
       l.carrier_id, c.carrier_type, l.equipment_type, l.stop_count,
       l.loaded_miles, l.empty_miles, l.total_miles,
       l.total_revenue, l.total_cost, l.total_revenue - l.total_cost AS margin,
       1.0 * (l.total_revenue - l.total_cost) / NULLIF(l.total_revenue, 0) AS margin_pct,
       1.0 * l.total_cost / NULLIF(l.total_miles, 0) AS cost_per_mile,
       1.0 * l.total_revenue / NULLIF(l.total_miles, 0) AS revenue_per_mile
FROM `YOUR_PROJECT.mclane_tms.loads` l
JOIN `YOUR_PROJECT.mclane_tms.locations` dc ON dc.location_id = l.origin_dc_id
JOIN `YOUR_PROJECT.mclane_tms.carriers` c ON c.carrier_id = l.carrier_id
WHERE l.load_status = 'COMPLETED';

CREATE OR REPLACE VIEW `YOUR_PROJECT.mclane_tms.v_stop_service` AS
SELECT s.stop_id, s.load_id, s.order_id, s.delivery_date, s.location_id, loc.location_name,
       loc.customer_id, cu.customer_name, cu.segment, cu.business_unit, l.origin_dc_id, l.carrier_id,
       s.on_time_flag, s.minutes_late, s.dwell_minutes, s.detention_minutes,
       s.cases_delivered, s.cases_short, s.cases_damaged, s.refused_flag
FROM `YOUR_PROJECT.mclane_tms.stops` s
JOIN `YOUR_PROJECT.mclane_tms.loads` l ON l.load_id = s.load_id
JOIN `YOUR_PROJECT.mclane_tms.locations` loc ON loc.location_id = s.location_id
JOIN `YOUR_PROJECT.mclane_tms.customers` cu ON cu.customer_id = loc.customer_id
WHERE s.arrival_ts IS NOT NULL;

CREATE OR REPLACE VIEW `YOUR_PROJECT.mclane_tms.v_carrier_scorecard` AS
SELECT c.carrier_id, c.carrier_name, c.carrier_type, c.safety_rating,
       COUNT(DISTINCT l.load_id) AS loads,
       1.0 * SUM(CASE WHEN s.on_time_flag THEN 1 ELSE 0 END) / NULLIF(COUNT(s.stop_id), 0) AS on_time_pct,
       AVG(s.minutes_late) AS avg_minutes_late,
       1.0 * SUM(s.cases_damaged + s.cases_short) / NULLIF(SUM(s.cases_delivered + s.cases_short), 0) AS claims_case_rate
FROM `YOUR_PROJECT.mclane_tms.carriers` c
JOIN `YOUR_PROJECT.mclane_tms.loads` l ON l.carrier_id = c.carrier_id AND l.load_status = 'COMPLETED'
JOIN `YOUR_PROJECT.mclane_tms.stops` s ON s.load_id = l.load_id
GROUP BY c.carrier_id, c.carrier_name, c.carrier_type, c.safety_rating;

