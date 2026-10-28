"""Canonical TMS data model, modelled on Trimble TMW Suite / TMWSuite tables.

This module is the single source of truth for:
  * DDL rendering for BigQuery, AlloyDB (PostgreSQL) and DuckDB (local dev)
  * the synthetic data generator column order
  * the schema context that grounds the NL-to-SQL agent

Each table records the TMW table it is modelled on so analysts who know TMW
(orderheader, legheader, stops, carrier, manpowerprofile, ...) can map it back.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Column:
    name: str
    type: str  # STRING | INT | FLOAT | NUMERIC | BOOL | DATE | TIMESTAMP
    description: str
    nullable: bool = True


@dataclass(frozen=True)
class Table:
    name: str
    tmw_equivalent: str
    description: str
    columns: tuple[Column, ...]
    primary_key: str | None = None
    foreign_keys: dict[str, str] = field(default_factory=dict)

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]


def _c(name: str, type_: str, description: str, nullable: bool = True) -> Column:
    return Column(name, type_, description, nullable)


TABLES: tuple[Table, ...] = (
    Table(
        name="customers",
        tmw_equivalent="company (cmp_billto = 'Y')",
        description="Bill-to customers: convenience retail, grocery, QSR and casual-dining restaurant chains.",
        primary_key="customer_id",
        columns=(
            _c("customer_id", "STRING", "Customer code, e.g. CUS0001.", False),
            _c("customer_name", "STRING", "Customer (chain) name."),
            _c("segment", "STRING", "RETAIL_CONVENIENCE | RETAIL_GROCERY | RESTAURANT_QSR | RESTAURANT_CASUAL | MILITARY."),
            _c("business_unit", "STRING", "GROCERY (retail supply) or FOODSERVICE (restaurant supply)."),
            _c("service_tier", "STRING", "PLATINUM | GOLD | SILVER. Drives on-time targets and penalties."),
            _c("on_time_target_pct", "FLOAT", "Contracted on-time delivery target, e.g. 0.97."),
            _c("late_penalty_per_stop", "NUMERIC", "Contractual chargeback in USD per late stop."),
            _c("payment_terms_days", "INT", "Invoice payment terms in days."),
            _c("hq_state", "STRING", "Two letter state of the customer HQ."),
        ),
    ),
    Table(
        name="locations",
        tmw_equivalent="company (shipper / consignee / terminal rows)",
        description="Every physical place: distribution centers (DC), stores, restaurants, vendors and terminals.",
        primary_key="location_id",
        foreign_keys={"customer_id": "customers.customer_id"},
        columns=(
            _c("location_id", "STRING", "Location code, e.g. DC01, STR00042, RST00117.", False),
            _c("location_name", "STRING", "Display name."),
            _c("location_type", "STRING", "DC | STORE | RESTAURANT | VENDOR."),
            _c("customer_id", "STRING", "Owning customer for STORE / RESTAURANT locations, NULL for DCs and vendors."),
            _c("dc_id", "STRING", "Servicing distribution center (DC location_id) for stores and restaurants."),
            _c("city", "STRING", "City."),
            _c("state", "STRING", "Two letter state."),
            _c("latitude", "FLOAT", "Latitude."),
            _c("longitude", "FLOAT", "Longitude."),
            _c("dock_open_hour", "INT", "Receiving window open hour (0-23, local)."),
            _c("dock_close_hour", "INT", "Receiving window close hour (0-23, local)."),
            _c("avg_unload_minutes", "INT", "Typical unload time in minutes."),
            _c("requires_liftgate", "BOOL", "Delivery needs a liftgate / small-format trailer."),
            _c("geocode_quality", "STRING", "ROOFTOP | STREET | ZIP_CENTROID. ZIP_CENTROID coordinates are approximate and break geofences."),
            _c("geofence_radius_m", "INT", "Radius in meters of the circular geofence used for automatic arrive / depart."),
            _c("padd_region", "STRING", "DOE fuel region (PADD1..PADD5) used for fuel surcharge."),
        ),
    ),
    Table(
        name="carriers",
        tmw_equivalent="carrier",
        description="McLane private fleet plus contract carriers and brokers used for overflow and long-haul.",
        primary_key="carrier_id",
        columns=(
            _c("carrier_id", "STRING", "Carrier code. MCLN is the private (asset) fleet.", False),
            _c("carrier_name", "STRING", "Carrier name."),
            _c("scac", "STRING", "Standard Carrier Alpha Code."),
            _c("carrier_type", "STRING", "PRIVATE_FLEET | CONTRACT | BROKER."),
            _c("equipment_types", "STRING", "Comma separated equipment the carrier runs: DRY_53, REEFER_53, MULTI_TEMP_53."),
            _c("safety_rating", "STRING", "FMCSA style rating: SATISFACTORY | CONDITIONAL | UNRATED."),
            _c("insurance_expiry_date", "DATE", "Cargo / liability insurance expiry."),
            _c("contract_rate_per_mile", "NUMERIC", "Contracted linehaul USD per loaded mile."),
            _c("home_state", "STRING", "Carrier home state."),
        ),
    ),
    Table(
        name="drivers",
        tmw_equivalent="manpowerprofile",
        description="Private fleet drivers with hours-of-service (HOS) status.",
        primary_key="driver_id",
        foreign_keys={"home_dc_id": "locations.location_id"},
        columns=(
            _c("driver_id", "STRING", "Driver code.", False),
            _c("driver_name", "STRING", "Driver full name (synthetic)."),
            _c("home_dc_id", "STRING", "Home distribution center."),
            _c("driver_type", "STRING", "COMPANY | TEAM | OWNER_OPERATOR."),
            _c("hire_date", "DATE", "Hire date."),
            _c("hazmat_endorsed", "BOOL", "Has hazmat endorsement."),
            _c("status", "STRING", "ACTIVE | ON_LEAVE | TERMINATED."),
            _c("safety_score", "INT", "0-100 telematics safety score (higher is safer)."),
            _c("hos_drive_hours_remaining", "FLOAT", "Hours of driving left today under the 11 hour rule."),
            _c("hos_cycle_hours_remaining", "FLOAT", "Hours left in the 70 hour / 8 day cycle."),
        ),
    ),
    Table(
        name="tractors",
        tmw_equivalent="tractorprofile",
        description="Private fleet power units.",
        primary_key="tractor_id",
        foreign_keys={"home_dc_id": "locations.location_id"},
        columns=(
            _c("tractor_id", "STRING", "Tractor unit number.", False),
            _c("home_dc_id", "STRING", "Home distribution center."),
            _c("make", "STRING", "Manufacturer."),
            _c("model_year", "INT", "Model year."),
            _c("fuel_type", "STRING", "DIESEL | CNG | ELECTRIC."),
            _c("odometer_miles", "INT", "Current odometer."),
            _c("avg_mpg", "FLOAT", "Rolling average miles per gallon."),
            _c("status", "STRING", "IN_SERVICE | SHOP | OUT_OF_SERVICE."),
            _c("next_pm_due_date", "DATE", "Next preventive maintenance due date."),
        ),
    ),
    Table(
        name="trailers",
        tmw_equivalent="trailerprofile",
        description="Private fleet trailers. Multi-temp trailers carry dry, chilled and frozen in one trip.",
        primary_key="trailer_id",
        foreign_keys={"home_dc_id": "locations.location_id"},
        columns=(
            _c("trailer_id", "STRING", "Trailer number.", False),
            _c("home_dc_id", "STRING", "Home distribution center."),
            _c("trailer_type", "STRING", "DRY_53 | REEFER_53 | MULTI_TEMP_53 | PUP_28."),
            _c("model_year", "INT", "Model year."),
            _c("reefer_unit_age_years", "INT", "Age of the refrigeration unit, NULL for dry trailers."),
            _c("status", "STRING", "IN_SERVICE | SHOP | OUT_OF_SERVICE."),
        ),
    ),
    Table(
        name="orders",
        tmw_equivalent="orderheader + freightdetail",
        description="Customer delivery orders. One order = one store/restaurant delivery from a DC.",
        primary_key="order_id",
        foreign_keys={
            "customer_id": "customers.customer_id",
            "origin_location_id": "locations.location_id",
            "dest_location_id": "locations.location_id",
            "load_id": "loads.load_id",
        },
        columns=(
            _c("order_id", "STRING", "Order number (ord_hdrnumber).", False),
            _c("customer_id", "STRING", "Bill-to customer."),
            _c("origin_location_id", "STRING", "Shipping DC."),
            _c("dest_location_id", "STRING", "Delivery store / restaurant."),
            _c("load_id", "STRING", "Load (trip) the order was planned on. NULL if cancelled before planning."),
            _c("order_date", "DATE", "Date the order was entered."),
            _c("requested_delivery_date", "DATE", "Requested delivery date."),
            _c("commodity", "STRING", "DRY_GROCERY | TOBACCO_CANDY | CHILLED | FROZEN | FOODSERVICE_MIXED."),
            _c("temperature_class", "STRING", "AMBIENT | CHILLED | FROZEN | MULTI."),
            _c("cases", "INT", "Ordered cases."),
            _c("weight_lbs", "INT", "Gross weight in pounds."),
            _c("cube_ft", "INT", "Cube in cubic feet."),
            _c("revenue_linehaul", "NUMERIC", "Billed linehaul / delivery fee USD."),
            _c("revenue_fuel_surcharge", "NUMERIC", "Billed fuel surcharge USD."),
            _c("revenue_accessorial", "NUMERIC", "Billed accessorials USD (detention, lumper, liftgate...)."),
            _c("total_revenue", "NUMERIC", "Sum of all billed revenue USD."),
            _c("order_status", "STRING", "PLANNED | DISPATCHED | IN_TRANSIT | DELIVERED | CANCELLED."),
        ),
    ),
    Table(
        name="loads",
        tmw_equivalent="legheader",
        description="A trip (route) from one DC covering one or more delivery stops, run by a driver/tractor/trailer or a carrier.",
        primary_key="load_id",
        foreign_keys={
            "origin_dc_id": "locations.location_id",
            "carrier_id": "carriers.carrier_id",
            "driver_id": "drivers.driver_id",
            "tractor_id": "tractors.tractor_id",
            "trailer_id": "trailers.trailer_id",
        },
        columns=(
            _c("load_id", "STRING", "Load / leg number (lgh_number).", False),
            _c("origin_dc_id", "STRING", "Origin DC."),
            _c("carrier_id", "STRING", "Carrier that ran the load. MCLN = private fleet."),
            _c("driver_id", "STRING", "Driver for private fleet loads, NULL for outside carriers."),
            _c("tractor_id", "STRING", "Tractor for private fleet loads."),
            _c("trailer_id", "STRING", "Trailer for private fleet loads."),
            _c("equipment_type", "STRING", "DRY_53 | REEFER_53 | MULTI_TEMP_53 | PUP_28."),
            _c("load_date", "DATE", "Dispatch date of the load. Use this for date filtering."),
            _c("planned_start_ts", "TIMESTAMP", "Planned departure from DC."),
            _c("actual_start_ts", "TIMESTAMP", "Actual departure from DC."),
            _c("planned_end_ts", "TIMESTAMP", "Planned return / final stop departure."),
            _c("actual_end_ts", "TIMESTAMP", "Actual return / final stop departure. NULL while in transit."),
            _c("stop_count", "INT", "Number of delivery stops."),
            _c("loaded_miles", "FLOAT", "Miles driven with freight."),
            _c("empty_miles", "FLOAT", "Deadhead / return miles."),
            _c("total_miles", "FLOAT", "loaded_miles + empty_miles. Planned route miles from PC*MILER (practical route)."),
            _c("mileage_source", "STRING", "Where planned miles came from: PCMILER_PRACTICAL (TMW PC*MILER interface) or MANUAL."),
            _c("pcmiler_shortest_miles", "FLOAT", "PC*MILER shortest-route miles for the same stop sequence (lower bound, used in rate disputes)."),
            _c("actual_odometer_miles", "FLOAT", "ELD / odometer miles actually driven (private fleet only, NULL for carriers or loads not completed)."),
            _c("dest_region_state", "STRING", "State of the final stop, used to define lanes (origin DC -> state)."),
            _c("load_status", "STRING", "PLANNED | DISPATCHED | IN_TRANSIT | COMPLETED | CANCELLED."),
            _c("total_revenue", "NUMERIC", "Sum of revenue of orders on the load USD."),
            _c("total_cost", "NUMERIC", "Sum of load_costs USD."),
        ),
    ),
    Table(
        name="stops",
        tmw_equivalent="stops",
        description="Each delivery stop on a load with appointment window, actual arrival and service outcome.",
        primary_key="stop_id",
        foreign_keys={
            "load_id": "loads.load_id",
            "order_id": "orders.order_id",
            "location_id": "locations.location_id",
        },
        columns=(
            _c("stop_id", "STRING", "Stop number (stp_number).", False),
            _c("load_id", "STRING", "Load."),
            _c("order_id", "STRING", "Order delivered at this stop."),
            _c("stop_sequence", "INT", "1-based sequence on the route."),
            _c("location_id", "STRING", "Delivery location."),
            _c("delivery_date", "DATE", "Scheduled delivery date."),
            _c("appt_window_start_ts", "TIMESTAMP", "Appointment window start."),
            _c("appt_window_end_ts", "TIMESTAMP", "Appointment window end."),
            _c("arrival_ts", "TIMESTAMP", "Actual arrival. NULL if not yet arrived."),
            _c("departure_ts", "TIMESTAMP", "Actual departure."),
            _c("on_time_flag", "BOOL", "TRUE when arrival <= appt_window_end_ts."),
            _c("minutes_late", "INT", "Minutes after window end (0 if on time)."),
            _c("minutes_early", "INT", "Minutes before window start (0 if not early). Restaurants count arrivals more than 15 min early as an OTD miss."),
            _c("arrival_source", "STRING", "How arrival was recorded: GEOFENCE (automatic) | DRIVER_MANUAL (keyed on the ELD) | CARRIER_EDI214."),
            _c("pcmiler_leg_miles", "FLOAT", "PC*MILER practical miles from the previous stop (or the DC) to this stop."),
            _c("dwell_minutes", "INT", "Minutes from arrival to departure."),
            _c("detention_minutes", "INT", "Billable wait beyond the 2 hour free time."),
            _c("cases_delivered", "INT", "Cases delivered."),
            _c("cases_short", "INT", "Cases short (not delivered)."),
            _c("cases_damaged", "INT", "Cases damaged."),
            _c("refused_flag", "BOOL", "Receiver refused all or part of the delivery."),
        ),
    ),
    Table(
        name="load_costs",
        tmw_equivalent="paydetail + carrier invoice (assetassignment)",
        description="Cost lines per load: driver pay, fuel, carrier linehaul, accessorials paid out, tolls, maintenance allocation.",
        primary_key="cost_id",
        foreign_keys={"load_id": "loads.load_id"},
        columns=(
            _c("cost_id", "STRING", "Cost line id.", False),
            _c("load_id", "STRING", "Load."),
            _c("cost_type", "STRING", "DRIVER_PAY | FUEL | CARRIER_LINEHAUL | DETENTION_PAID | LUMPER | LAYOVER | TOLLS | MAINTENANCE_ALLOC."),
            _c("amount", "NUMERIC", "USD."),
            _c("cost_date", "DATE", "Accrual date."),
        ),
    ),
    Table(
        name="invoices",
        tmw_equivalent="invoiceheader + invoicedetail",
        description="Customer invoices per order including accessorial charges actually billed.",
        primary_key="invoice_id",
        foreign_keys={"order_id": "orders.order_id", "customer_id": "customers.customer_id"},
        columns=(
            _c("invoice_id", "STRING", "Invoice number.", False),
            _c("order_id", "STRING", "Order."),
            _c("customer_id", "STRING", "Bill-to customer."),
            _c("invoice_date", "DATE", "Invoice date."),
            _c("linehaul_amount", "NUMERIC", "Linehaul billed USD."),
            _c("fuel_surcharge_amount", "NUMERIC", "Fuel surcharge billed USD."),
            _c("detention_billed", "NUMERIC", "Detention billed to customer USD."),
            _c("other_accessorial_billed", "NUMERIC", "Other accessorials billed USD."),
            _c("late_penalty_amount", "NUMERIC", "Chargeback deducted by customer for late delivery USD (negative revenue)."),
            _c("total_amount", "NUMERIC", "Net invoice total USD."),
            _c("paid_flag", "BOOL", "Invoice paid."),
            _c("days_to_pay", "INT", "Days from invoice to payment, NULL if unpaid."),
        ),
    ),
    Table(
        name="carrier_tenders",
        tmw_equivalent="carrier tender / load offer history",
        description="Load tenders offered to outside carriers and their response.",
        primary_key="tender_id",
        foreign_keys={"load_id": "loads.load_id", "carrier_id": "carriers.carrier_id"},
        columns=(
            _c("tender_id", "STRING", "Tender id.", False),
            _c("load_id", "STRING", "Load offered."),
            _c("carrier_id", "STRING", "Carrier offered to."),
            _c("tender_ts", "TIMESTAMP", "When the tender was sent."),
            _c("tender_date", "DATE", "Date the tender was sent."),
            _c("offered_rate", "NUMERIC", "Offered linehaul USD."),
            _c("response", "STRING", "ACCEPTED | REJECTED | EXPIRED."),
            _c("response_minutes", "INT", "Minutes to respond."),
        ),
    ),
    Table(
        name="carrier_rates",
        tmw_equivalent="carrier rate tables (tariff / contract rates)",
        description="Contracted rates per outside carrier, lane (origin DC -> destination state) and equipment, with accessorial rules.",
        primary_key="rate_id",
        foreign_keys={"carrier_id": "carriers.carrier_id", "origin_dc_id": "locations.location_id"},
        columns=(
            _c("rate_id", "STRING", "Rate contract line id.", False),
            _c("carrier_id", "STRING", "Carrier."),
            _c("origin_dc_id", "STRING", "Origin DC."),
            _c("dest_state", "STRING", "Destination state."),
            _c("equipment_type", "STRING", "DRY_53 | REEFER_53 | MULTI_TEMP_53 | PUP_28."),
            _c("rate_per_mile", "NUMERIC", "Contracted linehaul USD per total mile."),
            _c("stop_charge", "NUMERIC", "USD per delivery stop."),
            _c("min_charge", "NUMERIC", "Minimum linehaul USD per load."),
            _c("fsc_base_price", "FLOAT", "Fuel surcharge: DOE price at which surcharge is zero (USD/gal)."),
            _c("fsc_mpg", "FLOAT", "Fuel surcharge: mpg divisor. FSC per mile = (DOE price - base) / mpg."),
            _c("detention_rate_per_hr", "NUMERIC", "Detention USD per hour after free time."),
            _c("free_time_minutes", "INT", "Free time at each stop before detention applies."),
            _c("lumper_requires_receipt", "BOOL", "Lumper is only payable with a receipt."),
            _c("effective_date", "DATE", "Contract start."),
            _c("expiry_date", "DATE", "Contract end."),
        ),
    ),
    Table(
        name="carrier_invoices",
        tmw_equivalent="carrier freight bill / EDI 210 (settlement & freight audit)",
        description="Freight bills received from outside carriers, to be audited against carrier_rates, stops and fuel_prices.",
        primary_key="carrier_invoice_id",
        foreign_keys={"load_id": "loads.load_id", "carrier_id": "carriers.carrier_id"},
        columns=(
            _c("carrier_invoice_id", "STRING", "Carrier invoice (freight bill) number.", False),
            _c("load_id", "STRING", "Load billed."),
            _c("carrier_id", "STRING", "Billing carrier."),
            _c("invoice_date", "DATE", "Invoice date."),
            _c("source", "STRING", "EDI_210 | PDF_SCAN | EMAIL."),
            _c("document_uri", "STRING", "Location of the invoice document (scanned PDF) when source is PDF_SCAN/EMAIL."),
            _c("billed_rate_per_mile", "NUMERIC", "Rate per mile shown on the invoice. NULL when not legible."),
            _c("billed_miles", "FLOAT", "Miles billed."),
            _c("billed_linehaul", "NUMERIC", "Linehaul billed USD."),
            _c("billed_fuel_surcharge", "NUMERIC", "Fuel surcharge billed USD. NULL when missing on the document."),
            _c("billed_detention", "NUMERIC", "Detention billed USD."),
            _c("billed_lumper", "NUMERIC", "Lumper billed USD."),
            _c("lumper_receipt_attached", "BOOL", "Lumper receipt attached."),
            _c("billed_other", "NUMERIC", "Other accessorials USD (layover, tolls, TONU)."),
            _c("billed_total", "NUMERIC", "Invoice total USD."),
            _c("invoice_status", "STRING", "RECEIVED | APPROVED | PAID | DISPUTED."),
        ),
    ),
    Table(
        name="check_calls",
        tmw_equivalent="checkcall",
        description="Telematics / ELD pings for loads, including reefer temperature and ETA.",
        primary_key="check_call_id",
        foreign_keys={"load_id": "loads.load_id"},
        columns=(
            _c("check_call_id", "STRING", "Ping id.", False),
            _c("load_id", "STRING", "Load."),
            _c("event_ts", "TIMESTAMP", "Ping time."),
            _c("latitude", "FLOAT", "Latitude."),
            _c("longitude", "FLOAT", "Longitude."),
            _c("speed_mph", "FLOAT", "Speed."),
            _c("reefer_temp_f", "FLOAT", "Reefer return air temperature F, NULL for dry."),
            _c("reefer_setpoint_f", "FLOAT", "Reefer setpoint F, NULL for dry."),
            _c("eta_next_stop_ts", "TIMESTAMP", "ETA to next stop computed by telematics."),
        ),
    ),
    Table(
        name="geofence_events",
        tmw_equivalent="checkcall (geofence arrive / depart auto-status from the telematics provider)",
        description="Automatic ENTER / EXIT events when a tracked truck crosses a location geofence. Missing events at a stop usually mean a bad geocode.",
        primary_key="geofence_event_id",
        foreign_keys={"load_id": "loads.load_id", "stop_id": "stops.stop_id", "location_id": "locations.location_id"},
        columns=(
            _c("geofence_event_id", "STRING", "Event id.", False),
            _c("load_id", "STRING", "Load."),
            _c("stop_id", "STRING", "Stop the event was matched to."),
            _c("location_id", "STRING", "Location whose geofence was crossed."),
            _c("event_type", "STRING", "ENTER | EXIT."),
            _c("event_ts", "TIMESTAMP", "When the truck crossed the geofence."),
            _c("event_date", "DATE", "Date of the event."),
            _c("latitude", "FLOAT", "Truck latitude at the event."),
            _c("longitude", "FLOAT", "Truck longitude at the event."),
            _c("distance_from_location_m", "INT", "Distance from the stored location coordinates in meters."),
        ),
    ),
    Table(
        name="exceptions",
        tmw_equivalent="expiration / event log (custom)",
        description="Operational exceptions raised on loads and stops.",
        primary_key="exception_id",
        foreign_keys={"load_id": "loads.load_id", "stop_id": "stops.stop_id"},
        columns=(
            _c("exception_id", "STRING", "Exception id.", False),
            _c("load_id", "STRING", "Load."),
            _c("stop_id", "STRING", "Stop, when stop specific."),
            _c("exception_type", "STRING", "LATE_ARRIVAL | DETENTION | REEFER_TEMP_EXCURSION | BREAKDOWN | HOS_RISK | REFUSED_DELIVERY | SHORTAGE | DAMAGE | WEATHER_DELAY."),
            _c("severity", "STRING", "LOW | MEDIUM | HIGH | CRITICAL."),
            _c("event_ts", "TIMESTAMP", "When raised."),
            _c("event_date", "DATE", "Date raised."),
            _c("root_cause", "STRING", "TRAFFIC | DOCK_CONGESTION | LATE_DISPATCH | EQUIPMENT | DRIVER | WEATHER | CUSTOMER | PICKING_ERROR."),
            _c("description", "STRING", "Free text."),
            _c("resolved_flag", "BOOL", "Resolved."),
            _c("cost_impact", "NUMERIC", "Estimated USD impact."),
        ),
    ),
    Table(
        name="agent_decision_log",
        tmw_equivalent="(new) AI decision audit trail",
        description="Every recommendation / auto-action taken by the agent: what, why, data used, confidence, $ impact, approval.",
        primary_key="decision_id",
        columns=(
            _c("decision_id", "STRING", "Decision id.", False),
            _c("decision_ts", "TIMESTAMP", "When the decision was logged (UTC)."),
            _c("decision_type", "STRING", "CARRIER_TENDER | INVOICE_DISPUTE | DELAY_MITIGATION | OTHER."),
            _c("load_id", "STRING", "Load, when applicable."),
            _c("carrier_id", "STRING", "Carrier, when applicable."),
            _c("amount_usd", "NUMERIC", "Dollar value of the action."),
            _c("confidence", "FLOAT", "Model confidence 0-1."),
            _c("status", "STRING", "AUTO_EXECUTED | PENDING_APPROVAL | APPROVED | REJECTED | BLOCKED."),
            _c("actor", "STRING", "agent or the approving user."),
            _c("rationale", "STRING", "Reasoning shown to the user."),
            _c("data_used", "STRING", "JSON describing the evidence used."),
        ),
    ),
    Table(
        name="fuel_prices",
        tmw_equivalent="fuelprice (DOE index)",
        description="Weekly DOE diesel price by PADD region, drives fuel surcharge.",
        primary_key=None,
        columns=(
            _c("week_start_date", "DATE", "Monday of the week.", False),
            _c("padd_region", "STRING", "PADD1 East Coast | PADD2 Midwest | PADD3 Gulf | PADD4 Rockies | PADD5 West."),
            _c("diesel_price_per_gal", "FLOAT", "USD per gallon."),
        ),
    ),
)

TABLES_BY_NAME = {t.name: t for t in TABLES}

# Portable views. `{p}` is replaced by the dataset/schema prefix for the target.
# Only ANSI constructs shared by BigQuery, PostgreSQL and DuckDB are used.
VIEWS: dict[str, str] = {
    "v_load_profitability": """
SELECT l.load_id, l.load_date, l.origin_dc_id, dc.location_name AS origin_dc_name,
       l.dest_region_state, l.origin_dc_id || '->' || l.dest_region_state AS lane,
       l.carrier_id, c.carrier_type, l.equipment_type, l.stop_count,
       l.loaded_miles, l.empty_miles, l.total_miles,
       l.total_revenue, l.total_cost, l.total_revenue - l.total_cost AS margin,
       1.0 * (l.total_revenue - l.total_cost) / NULLIF(l.total_revenue, 0) AS margin_pct,
       1.0 * l.total_cost / NULLIF(l.total_miles, 0) AS cost_per_mile,
       1.0 * l.total_revenue / NULLIF(l.total_miles, 0) AS revenue_per_mile
FROM {p}loads l
JOIN {p}locations dc ON dc.location_id = l.origin_dc_id
JOIN {p}carriers c ON c.carrier_id = l.carrier_id
WHERE l.load_status = 'COMPLETED'
""",
    "v_stop_service": """
SELECT s.stop_id, s.load_id, s.order_id, s.delivery_date, s.location_id, loc.location_name,
       loc.customer_id, cu.customer_name, cu.segment, cu.business_unit, l.origin_dc_id, l.carrier_id,
       s.on_time_flag, s.minutes_late, s.minutes_early, s.dwell_minutes, s.detention_minutes,
       s.cases_delivered, s.cases_short, s.cases_damaged, s.refused_flag, s.arrival_source, s.pcmiler_leg_miles,
       CASE WHEN cu.business_unit = 'FOODSERVICE' THEN 'RESTAURANT' ELSE 'RETAIL' END AS otd_channel,
       CASE WHEN s.minutes_late > 0 THEN FALSE
            WHEN cu.business_unit = 'FOODSERVICE' AND s.minutes_early > 15 THEN FALSE
            ELSE TRUE END AS otd_flag
FROM {p}stops s
JOIN {p}loads l ON l.load_id = s.load_id
JOIN {p}locations loc ON loc.location_id = s.location_id
JOIN {p}customers cu ON cu.customer_id = loc.customer_id
WHERE s.arrival_ts IS NOT NULL
""",
    "v_carrier_scorecard": """
SELECT c.carrier_id, c.carrier_name, c.carrier_type, c.safety_rating,
       COUNT(DISTINCT l.load_id) AS loads,
       1.0 * SUM(CASE WHEN s.on_time_flag THEN 1 ELSE 0 END) / NULLIF(COUNT(s.stop_id), 0) AS on_time_pct,
       AVG(s.minutes_late) AS avg_minutes_late,
       1.0 * SUM(s.cases_damaged + s.cases_short) / NULLIF(SUM(s.cases_delivered + s.cases_short), 0) AS claims_case_rate
FROM {p}carriers c
JOIN {p}loads l ON l.carrier_id = c.carrier_id AND l.load_status = 'COMPLETED'
JOIN {p}stops s ON s.load_id = l.load_id
GROUP BY c.carrier_id, c.carrier_name, c.carrier_type, c.safety_rating
""",
}


def schema_context(prefix: str = "", dialect: str = "bigquery") -> str:
    """Compact, LLM-friendly description of every table, column and join."""
    lines = [f"SQL dialect: {dialect}. Qualify tables as `{prefix}<table>`." if prefix else f"SQL dialect: {dialect}."]
    for t in TABLES:
        lines.append(f"\nTABLE {prefix}{t.name}  -- {t.description} (TMW: {t.tmw_equivalent})")
        for col in t.columns:
            lines.append(f"  {col.name} {col.type}: {col.description}")
        if t.foreign_keys:
            joins = ", ".join(f"{k} -> {v}" for k, v in t.foreign_keys.items())
            lines.append(f"  JOINS: {joins}")
    lines.append("\nVIEWS (prefer these for common questions):")
    for name, desc in VIEW_DESCRIPTIONS.items():
        lines.append(f"  {prefix}{name}: {desc}")
    return "\n".join(lines)


VIEW_DESCRIPTIONS = {
    "v_load_profitability": (
        "one row per COMPLETED load: load_id, load_date, origin_dc_id, origin_dc_name, dest_region_state, lane "
        "('DC01->TX'), carrier_id, carrier_type, equipment_type, stop_count, loaded_miles, empty_miles, total_miles, "
        "total_revenue, total_cost, margin, margin_pct, cost_per_mile, revenue_per_mile."
    ),
    "v_stop_service": (
        "one row per arrived stop with customer context: stop_id, load_id, order_id, delivery_date, location_id, "
        "location_name, customer_id, customer_name, segment, business_unit, origin_dc_id, carrier_id, on_time_flag, "
        "minutes_late, minutes_early, dwell_minutes, detention_minutes, cases_delivered, cases_short, cases_damaged, "
        "refused_flag, arrival_source, pcmiler_leg_miles, otd_channel (RETAIL | RESTAURANT) and otd_flag (McLane OTD: "
        "Retail = not after the window end; Restaurant = also not more than 15 min before the window start). Use otd_flag for OTD questions."
    ),
    "v_carrier_scorecard": (
        "all-time per carrier: carrier_id, carrier_name, carrier_type, safety_rating, loads, on_time_pct, "
        "avg_minutes_late, claims_case_rate."
    ),
}
