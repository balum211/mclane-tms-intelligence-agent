CREATE SCHEMA IF NOT EXISTS tms;

CREATE TABLE IF NOT EXISTS tms.customers (
  customer_id TEXT NOT NULL,
  customer_name TEXT,
  segment TEXT,
  business_unit TEXT,
  service_tier TEXT,
  on_time_target_pct DOUBLE PRECISION,
  late_penalty_per_stop NUMERIC(14,2),
  payment_terms_days INTEGER,
  hq_state TEXT,
  PRIMARY KEY (customer_id)
);

COMMENT ON TABLE tms.customers IS 'Bill-to customers: convenience retail, grocery, QSR and casual-dining restaurant chains.';
COMMENT ON COLUMN tms.customers.customer_id IS 'Customer code, e.g. CUS0001.';
COMMENT ON COLUMN tms.customers.customer_name IS 'Customer (chain) name.';
COMMENT ON COLUMN tms.customers.segment IS 'RETAIL_CONVENIENCE | RETAIL_GROCERY | RESTAURANT_QSR | RESTAURANT_CASUAL | MILITARY.';
COMMENT ON COLUMN tms.customers.business_unit IS 'GROCERY (retail supply) or FOODSERVICE (restaurant supply).';
COMMENT ON COLUMN tms.customers.service_tier IS 'PLATINUM | GOLD | SILVER. Drives on-time targets and penalties.';
COMMENT ON COLUMN tms.customers.on_time_target_pct IS 'Contracted on-time delivery target, e.g. 0.97.';
COMMENT ON COLUMN tms.customers.late_penalty_per_stop IS 'Contractual chargeback in USD per late stop.';
COMMENT ON COLUMN tms.customers.payment_terms_days IS 'Invoice payment terms in days.';
COMMENT ON COLUMN tms.customers.hq_state IS 'Two letter state of the customer HQ.';

CREATE TABLE IF NOT EXISTS tms.locations (
  location_id TEXT NOT NULL,
  location_name TEXT,
  location_type TEXT,
  customer_id TEXT,
  dc_id TEXT,
  city TEXT,
  state TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  dock_open_hour INTEGER,
  dock_close_hour INTEGER,
  avg_unload_minutes INTEGER,
  requires_liftgate BOOLEAN,
  padd_region TEXT,
  PRIMARY KEY (location_id)
);

COMMENT ON TABLE tms.locations IS 'Every physical place: distribution centers (DC), stores, restaurants, vendors and terminals.';
COMMENT ON COLUMN tms.locations.location_id IS 'Location code, e.g. DC01, STR00042, RST00117.';
COMMENT ON COLUMN tms.locations.location_name IS 'Display name.';
COMMENT ON COLUMN tms.locations.location_type IS 'DC | STORE | RESTAURANT | VENDOR.';
COMMENT ON COLUMN tms.locations.customer_id IS 'Owning customer for STORE / RESTAURANT locations, NULL for DCs and vendors.';
COMMENT ON COLUMN tms.locations.dc_id IS 'Servicing distribution center (DC location_id) for stores and restaurants.';
COMMENT ON COLUMN tms.locations.city IS 'City.';
COMMENT ON COLUMN tms.locations.state IS 'Two letter state.';
COMMENT ON COLUMN tms.locations.latitude IS 'Latitude.';
COMMENT ON COLUMN tms.locations.longitude IS 'Longitude.';
COMMENT ON COLUMN tms.locations.dock_open_hour IS 'Receiving window open hour (0-23, local).';
COMMENT ON COLUMN tms.locations.dock_close_hour IS 'Receiving window close hour (0-23, local).';
COMMENT ON COLUMN tms.locations.avg_unload_minutes IS 'Typical unload time in minutes.';
COMMENT ON COLUMN tms.locations.requires_liftgate IS 'Delivery needs a liftgate / small-format trailer.';
COMMENT ON COLUMN tms.locations.padd_region IS 'DOE fuel region (PADD1..PADD5) used for fuel surcharge.';
CREATE INDEX IF NOT EXISTS ix_locations_customer_id ON tms.locations (customer_id);
CREATE INDEX IF NOT EXISTS ix_locations_dc_id ON tms.locations (dc_id);

CREATE TABLE IF NOT EXISTS tms.carriers (
  carrier_id TEXT NOT NULL,
  carrier_name TEXT,
  scac TEXT,
  carrier_type TEXT,
  equipment_types TEXT,
  safety_rating TEXT,
  insurance_expiry_date DATE,
  contract_rate_per_mile NUMERIC(14,2),
  home_state TEXT,
  PRIMARY KEY (carrier_id)
);

COMMENT ON TABLE tms.carriers IS 'McLane private fleet plus contract carriers and brokers used for overflow and long-haul.';
COMMENT ON COLUMN tms.carriers.carrier_id IS 'Carrier code. MCLN is the private (asset) fleet.';
COMMENT ON COLUMN tms.carriers.carrier_name IS 'Carrier name.';
COMMENT ON COLUMN tms.carriers.scac IS 'Standard Carrier Alpha Code.';
COMMENT ON COLUMN tms.carriers.carrier_type IS 'PRIVATE_FLEET | CONTRACT | BROKER.';
COMMENT ON COLUMN tms.carriers.equipment_types IS 'Comma separated equipment the carrier runs: DRY_53, REEFER_53, MULTI_TEMP_53.';
COMMENT ON COLUMN tms.carriers.safety_rating IS 'FMCSA style rating: SATISFACTORY | CONDITIONAL | UNRATED.';
COMMENT ON COLUMN tms.carriers.insurance_expiry_date IS 'Cargo / liability insurance expiry.';
COMMENT ON COLUMN tms.carriers.contract_rate_per_mile IS 'Contracted linehaul USD per loaded mile.';
COMMENT ON COLUMN tms.carriers.home_state IS 'Carrier home state.';

CREATE TABLE IF NOT EXISTS tms.drivers (
  driver_id TEXT NOT NULL,
  driver_name TEXT,
  home_dc_id TEXT,
  driver_type TEXT,
  hire_date DATE,
  hazmat_endorsed BOOLEAN,
  status TEXT,
  safety_score INTEGER,
  hos_drive_hours_remaining DOUBLE PRECISION,
  hos_cycle_hours_remaining DOUBLE PRECISION,
  PRIMARY KEY (driver_id)
);

COMMENT ON TABLE tms.drivers IS 'Private fleet drivers with hours-of-service (HOS) status.';
COMMENT ON COLUMN tms.drivers.driver_id IS 'Driver code.';
COMMENT ON COLUMN tms.drivers.driver_name IS 'Driver full name (synthetic).';
COMMENT ON COLUMN tms.drivers.home_dc_id IS 'Home distribution center.';
COMMENT ON COLUMN tms.drivers.driver_type IS 'COMPANY | TEAM | OWNER_OPERATOR.';
COMMENT ON COLUMN tms.drivers.hire_date IS 'Hire date.';
COMMENT ON COLUMN tms.drivers.hazmat_endorsed IS 'Has hazmat endorsement.';
COMMENT ON COLUMN tms.drivers.status IS 'ACTIVE | ON_LEAVE | TERMINATED.';
COMMENT ON COLUMN tms.drivers.safety_score IS '0-100 telematics safety score (higher is safer).';
COMMENT ON COLUMN tms.drivers.hos_drive_hours_remaining IS 'Hours of driving left today under the 11 hour rule.';
COMMENT ON COLUMN tms.drivers.hos_cycle_hours_remaining IS 'Hours left in the 70 hour / 8 day cycle.';

CREATE TABLE IF NOT EXISTS tms.tractors (
  tractor_id TEXT NOT NULL,
  home_dc_id TEXT,
  make TEXT,
  model_year INTEGER,
  fuel_type TEXT,
  odometer_miles INTEGER,
  avg_mpg DOUBLE PRECISION,
  status TEXT,
  next_pm_due_date DATE,
  PRIMARY KEY (tractor_id)
);

COMMENT ON TABLE tms.tractors IS 'Private fleet power units.';
COMMENT ON COLUMN tms.tractors.tractor_id IS 'Tractor unit number.';
COMMENT ON COLUMN tms.tractors.home_dc_id IS 'Home distribution center.';
COMMENT ON COLUMN tms.tractors.make IS 'Manufacturer.';
COMMENT ON COLUMN tms.tractors.model_year IS 'Model year.';
COMMENT ON COLUMN tms.tractors.fuel_type IS 'DIESEL | CNG | ELECTRIC.';
COMMENT ON COLUMN tms.tractors.odometer_miles IS 'Current odometer.';
COMMENT ON COLUMN tms.tractors.avg_mpg IS 'Rolling average miles per gallon.';
COMMENT ON COLUMN tms.tractors.status IS 'IN_SERVICE | SHOP | OUT_OF_SERVICE.';
COMMENT ON COLUMN tms.tractors.next_pm_due_date IS 'Next preventive maintenance due date.';

CREATE TABLE IF NOT EXISTS tms.trailers (
  trailer_id TEXT NOT NULL,
  home_dc_id TEXT,
  trailer_type TEXT,
  model_year INTEGER,
  reefer_unit_age_years INTEGER,
  status TEXT,
  PRIMARY KEY (trailer_id)
);

COMMENT ON TABLE tms.trailers IS 'Private fleet trailers. Multi-temp trailers carry dry, chilled and frozen in one trip.';
COMMENT ON COLUMN tms.trailers.trailer_id IS 'Trailer number.';
COMMENT ON COLUMN tms.trailers.home_dc_id IS 'Home distribution center.';
COMMENT ON COLUMN tms.trailers.trailer_type IS 'DRY_53 | REEFER_53 | MULTI_TEMP_53 | PUP_28.';
COMMENT ON COLUMN tms.trailers.model_year IS 'Model year.';
COMMENT ON COLUMN tms.trailers.reefer_unit_age_years IS 'Age of the refrigeration unit, NULL for dry trailers.';
COMMENT ON COLUMN tms.trailers.status IS 'IN_SERVICE | SHOP | OUT_OF_SERVICE.';

CREATE TABLE IF NOT EXISTS tms.orders (
  order_id TEXT NOT NULL,
  customer_id TEXT,
  origin_location_id TEXT,
  dest_location_id TEXT,
  load_id TEXT,
  order_date DATE,
  requested_delivery_date DATE,
  commodity TEXT,
  temperature_class TEXT,
  cases INTEGER,
  weight_lbs INTEGER,
  cube_ft INTEGER,
  revenue_linehaul NUMERIC(14,2),
  revenue_fuel_surcharge NUMERIC(14,2),
  revenue_accessorial NUMERIC(14,2),
  total_revenue NUMERIC(14,2),
  order_status TEXT,
  PRIMARY KEY (order_id)
);

COMMENT ON TABLE tms.orders IS 'Customer delivery orders. One order = one store/restaurant delivery from a DC.';
COMMENT ON COLUMN tms.orders.order_id IS 'Order number (ord_hdrnumber).';
COMMENT ON COLUMN tms.orders.customer_id IS 'Bill-to customer.';
COMMENT ON COLUMN tms.orders.origin_location_id IS 'Shipping DC.';
COMMENT ON COLUMN tms.orders.dest_location_id IS 'Delivery store / restaurant.';
COMMENT ON COLUMN tms.orders.load_id IS 'Load (trip) the order was planned on. NULL if cancelled before planning.';
COMMENT ON COLUMN tms.orders.order_date IS 'Date the order was entered.';
COMMENT ON COLUMN tms.orders.requested_delivery_date IS 'Requested delivery date.';
COMMENT ON COLUMN tms.orders.commodity IS 'DRY_GROCERY | TOBACCO_CANDY | CHILLED | FROZEN | FOODSERVICE_MIXED.';
COMMENT ON COLUMN tms.orders.temperature_class IS 'AMBIENT | CHILLED | FROZEN | MULTI.';
COMMENT ON COLUMN tms.orders.cases IS 'Ordered cases.';
COMMENT ON COLUMN tms.orders.weight_lbs IS 'Gross weight in pounds.';
COMMENT ON COLUMN tms.orders.cube_ft IS 'Cube in cubic feet.';
COMMENT ON COLUMN tms.orders.revenue_linehaul IS 'Billed linehaul / delivery fee USD.';
COMMENT ON COLUMN tms.orders.revenue_fuel_surcharge IS 'Billed fuel surcharge USD.';
COMMENT ON COLUMN tms.orders.revenue_accessorial IS 'Billed accessorials USD (detention, lumper, liftgate...).';
COMMENT ON COLUMN tms.orders.total_revenue IS 'Sum of all billed revenue USD.';
COMMENT ON COLUMN tms.orders.order_status IS 'PLANNED | DISPATCHED | IN_TRANSIT | DELIVERED | CANCELLED.';
CREATE INDEX IF NOT EXISTS ix_orders_customer_id ON tms.orders (customer_id);
CREATE INDEX IF NOT EXISTS ix_orders_load_id ON tms.orders (load_id);

CREATE TABLE IF NOT EXISTS tms.loads (
  load_id TEXT NOT NULL,
  origin_dc_id TEXT,
  carrier_id TEXT,
  driver_id TEXT,
  tractor_id TEXT,
  trailer_id TEXT,
  equipment_type TEXT,
  load_date DATE,
  planned_start_ts TIMESTAMP,
  actual_start_ts TIMESTAMP,
  planned_end_ts TIMESTAMP,
  actual_end_ts TIMESTAMP,
  stop_count INTEGER,
  loaded_miles DOUBLE PRECISION,
  empty_miles DOUBLE PRECISION,
  total_miles DOUBLE PRECISION,
  dest_region_state TEXT,
  load_status TEXT,
  total_revenue NUMERIC(14,2),
  total_cost NUMERIC(14,2),
  PRIMARY KEY (load_id)
);

COMMENT ON TABLE tms.loads IS 'A trip (route) from one DC covering one or more delivery stops, run by a driver/tractor/trailer or a carrier.';
COMMENT ON COLUMN tms.loads.load_id IS 'Load / leg number (lgh_number).';
COMMENT ON COLUMN tms.loads.origin_dc_id IS 'Origin DC.';
COMMENT ON COLUMN tms.loads.carrier_id IS 'Carrier that ran the load. MCLN = private fleet.';
COMMENT ON COLUMN tms.loads.driver_id IS 'Driver for private fleet loads, NULL for outside carriers.';
COMMENT ON COLUMN tms.loads.tractor_id IS 'Tractor for private fleet loads.';
COMMENT ON COLUMN tms.loads.trailer_id IS 'Trailer for private fleet loads.';
COMMENT ON COLUMN tms.loads.equipment_type IS 'DRY_53 | REEFER_53 | MULTI_TEMP_53 | PUP_28.';
COMMENT ON COLUMN tms.loads.load_date IS 'Dispatch date of the load. Use this for date filtering.';
COMMENT ON COLUMN tms.loads.planned_start_ts IS 'Planned departure from DC.';
COMMENT ON COLUMN tms.loads.actual_start_ts IS 'Actual departure from DC.';
COMMENT ON COLUMN tms.loads.planned_end_ts IS 'Planned return / final stop departure.';
COMMENT ON COLUMN tms.loads.actual_end_ts IS 'Actual return / final stop departure. NULL while in transit.';
COMMENT ON COLUMN tms.loads.stop_count IS 'Number of delivery stops.';
COMMENT ON COLUMN tms.loads.loaded_miles IS 'Miles driven with freight.';
COMMENT ON COLUMN tms.loads.empty_miles IS 'Deadhead / return miles.';
COMMENT ON COLUMN tms.loads.total_miles IS 'loaded_miles + empty_miles.';
COMMENT ON COLUMN tms.loads.dest_region_state IS 'State of the final stop, used to define lanes (origin DC -> state).';
COMMENT ON COLUMN tms.loads.load_status IS 'PLANNED | DISPATCHED | IN_TRANSIT | COMPLETED | CANCELLED.';
COMMENT ON COLUMN tms.loads.total_revenue IS 'Sum of revenue of orders on the load USD.';
COMMENT ON COLUMN tms.loads.total_cost IS 'Sum of load_costs USD.';
CREATE INDEX IF NOT EXISTS ix_loads_load_date ON tms.loads (load_date);
CREATE INDEX IF NOT EXISTS ix_loads_origin_dc_id ON tms.loads (origin_dc_id);
CREATE INDEX IF NOT EXISTS ix_loads_carrier_id ON tms.loads (carrier_id);
CREATE INDEX IF NOT EXISTS ix_loads_load_status ON tms.loads (load_status);

CREATE TABLE IF NOT EXISTS tms.stops (
  stop_id TEXT NOT NULL,
  load_id TEXT,
  order_id TEXT,
  stop_sequence INTEGER,
  location_id TEXT,
  delivery_date DATE,
  appt_window_start_ts TIMESTAMP,
  appt_window_end_ts TIMESTAMP,
  arrival_ts TIMESTAMP,
  departure_ts TIMESTAMP,
  on_time_flag BOOLEAN,
  minutes_late INTEGER,
  dwell_minutes INTEGER,
  detention_minutes INTEGER,
  cases_delivered INTEGER,
  cases_short INTEGER,
  cases_damaged INTEGER,
  refused_flag BOOLEAN,
  PRIMARY KEY (stop_id)
);

COMMENT ON TABLE tms.stops IS 'Each delivery stop on a load with appointment window, actual arrival and service outcome.';
COMMENT ON COLUMN tms.stops.stop_id IS 'Stop number (stp_number).';
COMMENT ON COLUMN tms.stops.load_id IS 'Load.';
COMMENT ON COLUMN tms.stops.order_id IS 'Order delivered at this stop.';
COMMENT ON COLUMN tms.stops.stop_sequence IS '1-based sequence on the route.';
COMMENT ON COLUMN tms.stops.location_id IS 'Delivery location.';
COMMENT ON COLUMN tms.stops.delivery_date IS 'Scheduled delivery date.';
COMMENT ON COLUMN tms.stops.appt_window_start_ts IS 'Appointment window start.';
COMMENT ON COLUMN tms.stops.appt_window_end_ts IS 'Appointment window end.';
COMMENT ON COLUMN tms.stops.arrival_ts IS 'Actual arrival. NULL if not yet arrived.';
COMMENT ON COLUMN tms.stops.departure_ts IS 'Actual departure.';
COMMENT ON COLUMN tms.stops.on_time_flag IS 'TRUE when arrival <= appt_window_end_ts.';
COMMENT ON COLUMN tms.stops.minutes_late IS 'Minutes after window end (0 if on time).';
COMMENT ON COLUMN tms.stops.dwell_minutes IS 'Minutes from arrival to departure.';
COMMENT ON COLUMN tms.stops.detention_minutes IS 'Billable wait beyond the 2 hour free time.';
COMMENT ON COLUMN tms.stops.cases_delivered IS 'Cases delivered.';
COMMENT ON COLUMN tms.stops.cases_short IS 'Cases short (not delivered).';
COMMENT ON COLUMN tms.stops.cases_damaged IS 'Cases damaged.';
COMMENT ON COLUMN tms.stops.refused_flag IS 'Receiver refused all or part of the delivery.';
CREATE INDEX IF NOT EXISTS ix_stops_load_id ON tms.stops (load_id);
CREATE INDEX IF NOT EXISTS ix_stops_location_id ON tms.stops (location_id);
CREATE INDEX IF NOT EXISTS ix_stops_delivery_date ON tms.stops (delivery_date);

CREATE TABLE IF NOT EXISTS tms.load_costs (
  cost_id TEXT NOT NULL,
  load_id TEXT,
  cost_type TEXT,
  amount NUMERIC(14,2),
  cost_date DATE,
  PRIMARY KEY (cost_id)
);

COMMENT ON TABLE tms.load_costs IS 'Cost lines per load: driver pay, fuel, carrier linehaul, accessorials paid out, tolls, maintenance allocation.';
COMMENT ON COLUMN tms.load_costs.cost_id IS 'Cost line id.';
COMMENT ON COLUMN tms.load_costs.load_id IS 'Load.';
COMMENT ON COLUMN tms.load_costs.cost_type IS 'DRIVER_PAY | FUEL | CARRIER_LINEHAUL | DETENTION_PAID | LUMPER | LAYOVER | TOLLS | MAINTENANCE_ALLOC.';
COMMENT ON COLUMN tms.load_costs.amount IS 'USD.';
COMMENT ON COLUMN tms.load_costs.cost_date IS 'Accrual date.';
CREATE INDEX IF NOT EXISTS ix_load_costs_load_id ON tms.load_costs (load_id);

CREATE TABLE IF NOT EXISTS tms.invoices (
  invoice_id TEXT NOT NULL,
  order_id TEXT,
  customer_id TEXT,
  invoice_date DATE,
  linehaul_amount NUMERIC(14,2),
  fuel_surcharge_amount NUMERIC(14,2),
  detention_billed NUMERIC(14,2),
  other_accessorial_billed NUMERIC(14,2),
  late_penalty_amount NUMERIC(14,2),
  total_amount NUMERIC(14,2),
  paid_flag BOOLEAN,
  days_to_pay INTEGER,
  PRIMARY KEY (invoice_id)
);

COMMENT ON TABLE tms.invoices IS 'Customer invoices per order including accessorial charges actually billed.';
COMMENT ON COLUMN tms.invoices.invoice_id IS 'Invoice number.';
COMMENT ON COLUMN tms.invoices.order_id IS 'Order.';
COMMENT ON COLUMN tms.invoices.customer_id IS 'Bill-to customer.';
COMMENT ON COLUMN tms.invoices.invoice_date IS 'Invoice date.';
COMMENT ON COLUMN tms.invoices.linehaul_amount IS 'Linehaul billed USD.';
COMMENT ON COLUMN tms.invoices.fuel_surcharge_amount IS 'Fuel surcharge billed USD.';
COMMENT ON COLUMN tms.invoices.detention_billed IS 'Detention billed to customer USD.';
COMMENT ON COLUMN tms.invoices.other_accessorial_billed IS 'Other accessorials billed USD.';
COMMENT ON COLUMN tms.invoices.late_penalty_amount IS 'Chargeback deducted by customer for late delivery USD (negative revenue).';
COMMENT ON COLUMN tms.invoices.total_amount IS 'Net invoice total USD.';
COMMENT ON COLUMN tms.invoices.paid_flag IS 'Invoice paid.';
COMMENT ON COLUMN tms.invoices.days_to_pay IS 'Days from invoice to payment, NULL if unpaid.';
CREATE INDEX IF NOT EXISTS ix_invoices_order_id ON tms.invoices (order_id);
CREATE INDEX IF NOT EXISTS ix_invoices_customer_id ON tms.invoices (customer_id);

CREATE TABLE IF NOT EXISTS tms.carrier_tenders (
  tender_id TEXT NOT NULL,
  load_id TEXT,
  carrier_id TEXT,
  tender_ts TIMESTAMP,
  tender_date DATE,
  offered_rate NUMERIC(14,2),
  response TEXT,
  response_minutes INTEGER,
  PRIMARY KEY (tender_id)
);

COMMENT ON TABLE tms.carrier_tenders IS 'Load tenders offered to outside carriers and their response.';
COMMENT ON COLUMN tms.carrier_tenders.tender_id IS 'Tender id.';
COMMENT ON COLUMN tms.carrier_tenders.load_id IS 'Load offered.';
COMMENT ON COLUMN tms.carrier_tenders.carrier_id IS 'Carrier offered to.';
COMMENT ON COLUMN tms.carrier_tenders.tender_ts IS 'When the tender was sent.';
COMMENT ON COLUMN tms.carrier_tenders.tender_date IS 'Date the tender was sent.';
COMMENT ON COLUMN tms.carrier_tenders.offered_rate IS 'Offered linehaul USD.';
COMMENT ON COLUMN tms.carrier_tenders.response IS 'ACCEPTED | REJECTED | EXPIRED.';
COMMENT ON COLUMN tms.carrier_tenders.response_minutes IS 'Minutes to respond.';
CREATE INDEX IF NOT EXISTS ix_carrier_tenders_load_id ON tms.carrier_tenders (load_id);
CREATE INDEX IF NOT EXISTS ix_carrier_tenders_carrier_id ON tms.carrier_tenders (carrier_id);

CREATE TABLE IF NOT EXISTS tms.carrier_rates (
  rate_id TEXT NOT NULL,
  carrier_id TEXT,
  origin_dc_id TEXT,
  dest_state TEXT,
  equipment_type TEXT,
  rate_per_mile NUMERIC(14,2),
  stop_charge NUMERIC(14,2),
  min_charge NUMERIC(14,2),
  fsc_base_price DOUBLE PRECISION,
  fsc_mpg DOUBLE PRECISION,
  detention_rate_per_hr NUMERIC(14,2),
  free_time_minutes INTEGER,
  lumper_requires_receipt BOOLEAN,
  effective_date DATE,
  expiry_date DATE,
  PRIMARY KEY (rate_id)
);

COMMENT ON TABLE tms.carrier_rates IS 'Contracted rates per outside carrier, lane (origin DC -> destination state) and equipment, with accessorial rules.';
COMMENT ON COLUMN tms.carrier_rates.rate_id IS 'Rate contract line id.';
COMMENT ON COLUMN tms.carrier_rates.carrier_id IS 'Carrier.';
COMMENT ON COLUMN tms.carrier_rates.origin_dc_id IS 'Origin DC.';
COMMENT ON COLUMN tms.carrier_rates.dest_state IS 'Destination state.';
COMMENT ON COLUMN tms.carrier_rates.equipment_type IS 'DRY_53 | REEFER_53 | MULTI_TEMP_53 | PUP_28.';
COMMENT ON COLUMN tms.carrier_rates.rate_per_mile IS 'Contracted linehaul USD per total mile.';
COMMENT ON COLUMN tms.carrier_rates.stop_charge IS 'USD per delivery stop.';
COMMENT ON COLUMN tms.carrier_rates.min_charge IS 'Minimum linehaul USD per load.';
COMMENT ON COLUMN tms.carrier_rates.fsc_base_price IS 'Fuel surcharge: DOE price at which surcharge is zero (USD/gal).';
COMMENT ON COLUMN tms.carrier_rates.fsc_mpg IS 'Fuel surcharge: mpg divisor. FSC per mile = (DOE price - base) / mpg.';
COMMENT ON COLUMN tms.carrier_rates.detention_rate_per_hr IS 'Detention USD per hour after free time.';
COMMENT ON COLUMN tms.carrier_rates.free_time_minutes IS 'Free time at each stop before detention applies.';
COMMENT ON COLUMN tms.carrier_rates.lumper_requires_receipt IS 'Lumper is only payable with a receipt.';
COMMENT ON COLUMN tms.carrier_rates.effective_date IS 'Contract start.';
COMMENT ON COLUMN tms.carrier_rates.expiry_date IS 'Contract end.';

CREATE TABLE IF NOT EXISTS tms.carrier_invoices (
  carrier_invoice_id TEXT NOT NULL,
  load_id TEXT,
  carrier_id TEXT,
  invoice_date DATE,
  source TEXT,
  document_uri TEXT,
  billed_rate_per_mile NUMERIC(14,2),
  billed_miles DOUBLE PRECISION,
  billed_linehaul NUMERIC(14,2),
  billed_fuel_surcharge NUMERIC(14,2),
  billed_detention NUMERIC(14,2),
  billed_lumper NUMERIC(14,2),
  lumper_receipt_attached BOOLEAN,
  billed_other NUMERIC(14,2),
  billed_total NUMERIC(14,2),
  invoice_status TEXT,
  PRIMARY KEY (carrier_invoice_id)
);

COMMENT ON TABLE tms.carrier_invoices IS 'Freight bills received from outside carriers, to be audited against carrier_rates, stops and fuel_prices.';
COMMENT ON COLUMN tms.carrier_invoices.carrier_invoice_id IS 'Carrier invoice (freight bill) number.';
COMMENT ON COLUMN tms.carrier_invoices.load_id IS 'Load billed.';
COMMENT ON COLUMN tms.carrier_invoices.carrier_id IS 'Billing carrier.';
COMMENT ON COLUMN tms.carrier_invoices.invoice_date IS 'Invoice date.';
COMMENT ON COLUMN tms.carrier_invoices.source IS 'EDI_210 | PDF_SCAN | EMAIL.';
COMMENT ON COLUMN tms.carrier_invoices.document_uri IS 'Location of the invoice document (scanned PDF) when source is PDF_SCAN/EMAIL.';
COMMENT ON COLUMN tms.carrier_invoices.billed_rate_per_mile IS 'Rate per mile shown on the invoice. NULL when not legible.';
COMMENT ON COLUMN tms.carrier_invoices.billed_miles IS 'Miles billed.';
COMMENT ON COLUMN tms.carrier_invoices.billed_linehaul IS 'Linehaul billed USD.';
COMMENT ON COLUMN tms.carrier_invoices.billed_fuel_surcharge IS 'Fuel surcharge billed USD. NULL when missing on the document.';
COMMENT ON COLUMN tms.carrier_invoices.billed_detention IS 'Detention billed USD.';
COMMENT ON COLUMN tms.carrier_invoices.billed_lumper IS 'Lumper billed USD.';
COMMENT ON COLUMN tms.carrier_invoices.lumper_receipt_attached IS 'Lumper receipt attached.';
COMMENT ON COLUMN tms.carrier_invoices.billed_other IS 'Other accessorials USD (layover, tolls, TONU).';
COMMENT ON COLUMN tms.carrier_invoices.billed_total IS 'Invoice total USD.';
COMMENT ON COLUMN tms.carrier_invoices.invoice_status IS 'RECEIVED | APPROVED | PAID | DISPUTED.';

CREATE TABLE IF NOT EXISTS tms.check_calls (
  check_call_id TEXT NOT NULL,
  load_id TEXT,
  event_ts TIMESTAMP,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  speed_mph DOUBLE PRECISION,
  reefer_temp_f DOUBLE PRECISION,
  reefer_setpoint_f DOUBLE PRECISION,
  eta_next_stop_ts TIMESTAMP,
  PRIMARY KEY (check_call_id)
);

COMMENT ON TABLE tms.check_calls IS 'Telematics / ELD pings for loads, including reefer temperature and ETA.';
COMMENT ON COLUMN tms.check_calls.check_call_id IS 'Ping id.';
COMMENT ON COLUMN tms.check_calls.load_id IS 'Load.';
COMMENT ON COLUMN tms.check_calls.event_ts IS 'Ping time.';
COMMENT ON COLUMN tms.check_calls.latitude IS 'Latitude.';
COMMENT ON COLUMN tms.check_calls.longitude IS 'Longitude.';
COMMENT ON COLUMN tms.check_calls.speed_mph IS 'Speed.';
COMMENT ON COLUMN tms.check_calls.reefer_temp_f IS 'Reefer return air temperature F, NULL for dry.';
COMMENT ON COLUMN tms.check_calls.reefer_setpoint_f IS 'Reefer setpoint F, NULL for dry.';
COMMENT ON COLUMN tms.check_calls.eta_next_stop_ts IS 'ETA to next stop computed by telematics.';
CREATE INDEX IF NOT EXISTS ix_check_calls_load_id ON tms.check_calls (load_id);

CREATE TABLE IF NOT EXISTS tms.exceptions (
  exception_id TEXT NOT NULL,
  load_id TEXT,
  stop_id TEXT,
  exception_type TEXT,
  severity TEXT,
  event_ts TIMESTAMP,
  event_date DATE,
  root_cause TEXT,
  description TEXT,
  resolved_flag BOOLEAN,
  cost_impact NUMERIC(14,2),
  PRIMARY KEY (exception_id)
);

COMMENT ON TABLE tms.exceptions IS 'Operational exceptions raised on loads and stops.';
COMMENT ON COLUMN tms.exceptions.exception_id IS 'Exception id.';
COMMENT ON COLUMN tms.exceptions.load_id IS 'Load.';
COMMENT ON COLUMN tms.exceptions.stop_id IS 'Stop, when stop specific.';
COMMENT ON COLUMN tms.exceptions.exception_type IS 'LATE_ARRIVAL | DETENTION | REEFER_TEMP_EXCURSION | BREAKDOWN | HOS_RISK | REFUSED_DELIVERY | SHORTAGE | DAMAGE | WEATHER_DELAY.';
COMMENT ON COLUMN tms.exceptions.severity IS 'LOW | MEDIUM | HIGH | CRITICAL.';
COMMENT ON COLUMN tms.exceptions.event_ts IS 'When raised.';
COMMENT ON COLUMN tms.exceptions.event_date IS 'Date raised.';
COMMENT ON COLUMN tms.exceptions.root_cause IS 'TRAFFIC | DOCK_CONGESTION | LATE_DISPATCH | EQUIPMENT | DRIVER | WEATHER | CUSTOMER | PICKING_ERROR.';
COMMENT ON COLUMN tms.exceptions.description IS 'Free text.';
COMMENT ON COLUMN tms.exceptions.resolved_flag IS 'Resolved.';
COMMENT ON COLUMN tms.exceptions.cost_impact IS 'Estimated USD impact.';
CREATE INDEX IF NOT EXISTS ix_exceptions_load_id ON tms.exceptions (load_id);
CREATE INDEX IF NOT EXISTS ix_exceptions_event_date ON tms.exceptions (event_date);
CREATE INDEX IF NOT EXISTS ix_exceptions_exception_type ON tms.exceptions (exception_type);

CREATE TABLE IF NOT EXISTS tms.agent_decision_log (
  decision_id TEXT NOT NULL,
  decision_ts TIMESTAMP,
  decision_type TEXT,
  load_id TEXT,
  carrier_id TEXT,
  amount_usd NUMERIC(14,2),
  confidence DOUBLE PRECISION,
  status TEXT,
  actor TEXT,
  rationale TEXT,
  data_used TEXT,
  PRIMARY KEY (decision_id)
);

COMMENT ON TABLE tms.agent_decision_log IS 'Every recommendation / auto-action taken by the agent: what, why, data used, confidence, $ impact, approval.';
COMMENT ON COLUMN tms.agent_decision_log.decision_id IS 'Decision id.';
COMMENT ON COLUMN tms.agent_decision_log.decision_ts IS 'When the decision was logged (UTC).';
COMMENT ON COLUMN tms.agent_decision_log.decision_type IS 'CARRIER_TENDER | INVOICE_DISPUTE | DELAY_MITIGATION | OTHER.';
COMMENT ON COLUMN tms.agent_decision_log.load_id IS 'Load, when applicable.';
COMMENT ON COLUMN tms.agent_decision_log.carrier_id IS 'Carrier, when applicable.';
COMMENT ON COLUMN tms.agent_decision_log.amount_usd IS 'Dollar value of the action.';
COMMENT ON COLUMN tms.agent_decision_log.confidence IS 'Model confidence 0-1.';
COMMENT ON COLUMN tms.agent_decision_log.status IS 'AUTO_EXECUTED | PENDING_APPROVAL | APPROVED | REJECTED | BLOCKED.';
COMMENT ON COLUMN tms.agent_decision_log.actor IS 'agent or the approving user.';
COMMENT ON COLUMN tms.agent_decision_log.rationale IS 'Reasoning shown to the user.';
COMMENT ON COLUMN tms.agent_decision_log.data_used IS 'JSON describing the evidence used.';

CREATE TABLE IF NOT EXISTS tms.fuel_prices (
  week_start_date DATE NOT NULL,
  padd_region TEXT,
  diesel_price_per_gal DOUBLE PRECISION
);

COMMENT ON TABLE tms.fuel_prices IS 'Weekly DOE diesel price by PADD region, drives fuel surcharge.';
COMMENT ON COLUMN tms.fuel_prices.week_start_date IS 'Monday of the week.';
COMMENT ON COLUMN tms.fuel_prices.padd_region IS 'PADD1 East Coast | PADD2 Midwest | PADD3 Gulf | PADD4 Rockies | PADD5 West.';
COMMENT ON COLUMN tms.fuel_prices.diesel_price_per_gal IS 'USD per gallon.';

CREATE OR REPLACE VIEW tms.v_load_profitability AS
SELECT l.load_id, l.load_date, l.origin_dc_id, dc.location_name AS origin_dc_name,
       l.dest_region_state, l.origin_dc_id || '->' || l.dest_region_state AS lane,
       l.carrier_id, c.carrier_type, l.equipment_type, l.stop_count,
       l.loaded_miles, l.empty_miles, l.total_miles,
       l.total_revenue, l.total_cost, l.total_revenue - l.total_cost AS margin,
       1.0 * (l.total_revenue - l.total_cost) / NULLIF(l.total_revenue, 0) AS margin_pct,
       1.0 * l.total_cost / NULLIF(l.total_miles, 0) AS cost_per_mile,
       1.0 * l.total_revenue / NULLIF(l.total_miles, 0) AS revenue_per_mile
FROM tms.loads l
JOIN tms.locations dc ON dc.location_id = l.origin_dc_id
JOIN tms.carriers c ON c.carrier_id = l.carrier_id
WHERE l.load_status = 'COMPLETED';

CREATE OR REPLACE VIEW tms.v_stop_service AS
SELECT s.stop_id, s.load_id, s.order_id, s.delivery_date, s.location_id, loc.location_name,
       loc.customer_id, cu.customer_name, cu.segment, cu.business_unit, l.origin_dc_id, l.carrier_id,
       s.on_time_flag, s.minutes_late, s.dwell_minutes, s.detention_minutes,
       s.cases_delivered, s.cases_short, s.cases_damaged, s.refused_flag
FROM tms.stops s
JOIN tms.loads l ON l.load_id = s.load_id
JOIN tms.locations loc ON loc.location_id = s.location_id
JOIN tms.customers cu ON cu.customer_id = loc.customer_id
WHERE s.arrival_ts IS NOT NULL;

CREATE OR REPLACE VIEW tms.v_carrier_scorecard AS
SELECT c.carrier_id, c.carrier_name, c.carrier_type, c.safety_rating,
       COUNT(DISTINCT l.load_id) AS loads,
       1.0 * SUM(CASE WHEN s.on_time_flag THEN 1 ELSE 0 END) / NULLIF(COUNT(s.stop_id), 0) AS on_time_pct,
       AVG(s.minutes_late) AS avg_minutes_late,
       1.0 * SUM(s.cases_damaged + s.cases_short) / NULLIF(SUM(s.cases_delivered + s.cases_short), 0) AS claims_case_rate
FROM tms.carriers c
JOIN tms.loads l ON l.carrier_id = c.carrier_id AND l.load_status = 'COMPLETED'
JOIN tms.stops s ON s.load_id = l.load_id
GROUP BY c.carrier_id, c.carrier_name, c.carrier_type, c.safety_rating;

