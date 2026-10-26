"""Synthetic Trimble TMW-style TMS data for a US grocery + foodservice distributor.

Generates CSVs (one per table in tms_agent.schema.TABLES) with realistic
multi-stop DC routes and a set of *planted* operational stories the agent
should discover (see docs/DATA_STORY.md):

  1. Broker "Redline Freight Brokers" runs ~20 pts below fleet on-time and rejects tenders.
  2. BurgerBarn restaurants (Midwest, DC04) have tight docks -> heavy detention,
     and most of that detention is never billed (accessorial leakage).
  3. Lane DC05->NV (Salt Lake City to Nevada) has long empty returns -> negative margin.
  4. Reefer temperature excursions cluster on trailers with old (>= 9 yr) reefer units.
  5. Monday late deliveries spike at DC03 (Concord NC) due to late dispatch.
  6. A diesel spike in the last 4 weeks (PADD3, PADD5) while the surcharge lags 2 weeks.
  7. Several in-transit loads today have drivers close to their HOS limits.
  8. Tobacco/candy shortages concentrate at DC02 (picking errors).

Usage:
    python -m tms_data.generate --out data/generated --days 120 --seed 42
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from tms_agent.schema import TABLES_BY_NAME

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

DCS = [
    # id, name, city, state, lat, lon, padd, service states
    ("DC01", "Temple TX DC", "Temple", "TX", 31.10, -97.34, "PADD3", ["TX", "OK", "LA"]),
    ("DC02", "Dothan AL DC", "Dothan", "AL", 31.22, -85.39, "PADD3", ["AL", "GA", "FL", "MS"]),
    ("DC03", "Concord NC DC", "Concord", "NC", 35.41, -80.58, "PADD1", ["NC", "SC", "VA"]),
    ("DC04", "Danville IL DC", "Danville", "IL", 40.12, -87.63, "PADD2", ["IL", "IN", "OH", "MI"]),
    ("DC05", "Salt Lake City UT DC", "Salt Lake City", "UT", 40.76, -111.89, "PADD4", ["UT", "ID", "NV", "WY"]),
    ("DC06", "Stockton CA DC", "Stockton", "CA", 37.96, -121.29, "PADD5", ["CA"]),
    ("DC07", "Ocala FL DC", "Ocala", "FL", 29.19, -82.14, "PADD1", ["FL", "GA"]),
    ("DC08", "Kansas City MO DC", "Kansas City", "MO", 39.10, -94.58, "PADD2", ["MO", "KS", "NE", "IA"]),
]

STATE_CENTROIDS = {
    "TX": (31.0, -97.5), "OK": (35.5, -97.5), "LA": (31.0, -92.0), "AL": (32.8, -86.8),
    "GA": (32.7, -83.4), "FL": (28.6, -82.4), "MS": (32.7, -89.7), "NC": (35.5, -79.4),
    "SC": (33.9, -80.9), "VA": (37.5, -78.8), "IL": (40.0, -89.2), "IN": (39.9, -86.3),
    "OH": (40.3, -82.8), "MI": (43.3, -84.5), "UT": (40.2, -111.7), "ID": (43.6, -114.6),
    "NV": (36.6, -116.0), "WY": (42.9, -107.5), "CA": (37.2, -120.5), "OR": (44.6, -122.6),
    "MO": (38.5, -92.4), "KS": (38.5, -97.0), "NE": (41.2, -97.5), "IA": (41.9, -93.4),
}

STATE_CITIES = {
    "TX": ["Waco", "Austin", "Killeen", "Round Rock", "Bryan", "Temple", "Georgetown"],
    "OK": ["Norman", "Lawton", "Ardmore"], "LA": ["Shreveport", "Alexandria", "Lafayette"],
    "AL": ["Montgomery", "Enterprise", "Troy", "Ozark"], "GA": ["Albany", "Valdosta", "Macon", "Tifton"],
    "FL": ["Gainesville", "Tallahassee", "Lakeland", "Leesburg", "Panama City"],
    "MS": ["Hattiesburg", "Meridian"], "NC": ["Charlotte", "Greensboro", "Salisbury", "Gastonia"],
    "SC": ["Rock Hill", "Columbia", "Spartanburg"], "VA": ["Danville", "Roanoke", "Lynchburg"],
    "IL": ["Champaign", "Decatur", "Springfield", "Bloomington"], "IN": ["Lafayette", "Indianapolis", "Terre Haute"],
    "OH": ["Dayton", "Columbus", "Lima"], "MI": ["Lansing", "Kalamazoo"],
    "UT": ["Provo", "Ogden", "Logan"], "ID": ["Boise", "Twin Falls", "Pocatello"],
    "NV": ["Elko", "Winnemucca", "Ely", "Las Vegas"], "WY": ["Evanston", "Rock Springs"],
    "CA": ["Modesto", "Fresno", "Sacramento", "Merced"], "OR": ["Medford", "Eugene"],
    "MO": ["Columbia", "Springfield", "Joplin"], "KS": ["Topeka", "Lawrence", "Wichita"],
    "NE": ["Omaha", "Lincoln"], "IA": ["Des Moines", "Ames"],
}

# Fictional chains only.
CUSTOMERS = [
    # name, segment, business unit, tier, hq
    ("QuickStop Markets", "RETAIL_CONVENIENCE", "GROCERY", "PLATINUM", "TX"),
    ("Lone Star Fuel & Food", "RETAIL_CONVENIENCE", "GROCERY", "GOLD", "TX"),
    ("Sunrise Convenience", "RETAIL_CONVENIENCE", "GROCERY", "GOLD", "GA"),
    ("Blue Ridge Pantry", "RETAIL_CONVENIENCE", "GROCERY", "SILVER", "NC"),
    ("Great Plains Travel Centers", "RETAIL_CONVENIENCE", "GROCERY", "PLATINUM", "MO"),
    ("Pacific Pump & Go", "RETAIL_CONVENIENCE", "GROCERY", "GOLD", "CA"),
    ("Wasatch Corner Stores", "RETAIL_CONVENIENCE", "GROCERY", "SILVER", "UT"),
    ("Fresh Basket Grocers", "RETAIL_GROCERY", "GROCERY", "PLATINUM", "FL"),
    ("Prairie Foods", "RETAIL_GROCERY", "GROCERY", "GOLD", "IL"),
    ("Hometown Value Mart", "RETAIL_GROCERY", "GROCERY", "SILVER", "AL"),
    ("BurgerBarn", "RESTAURANT_QSR", "FOODSERVICE", "PLATINUM", "IL"),
    ("TacoTrail", "RESTAURANT_QSR", "FOODSERVICE", "GOLD", "TX"),
    ("Cluck & Co Chicken", "RESTAURANT_QSR", "FOODSERVICE", "GOLD", "GA"),
    ("Slice Station Pizza", "RESTAURANT_QSR", "FOODSERVICE", "SILVER", "OH"),
    ("Sunset Grill & Bar", "RESTAURANT_CASUAL", "FOODSERVICE", "GOLD", "FL"),
    ("Harvest Table Kitchens", "RESTAURANT_CASUAL", "FOODSERVICE", "SILVER", "NC"),
    ("Desert Rose Diner", "RESTAURANT_CASUAL", "FOODSERVICE", "SILVER", "NV"),
    ("Base Exchange Commissary", "MILITARY", "GROCERY", "PLATINUM", "TX"),
]

TIER_TARGET = {"PLATINUM": 0.97, "GOLD": 0.95, "SILVER": 0.92}
TIER_PENALTY = {"PLATINUM": 150.0, "GOLD": 100.0, "SILVER": 50.0}

CARRIERS = [
    # id, name, scac, type, equipment, safety, rate/mi, home
    ("MCLN", "McLane Private Fleet", "MCLN", "PRIVATE_FLEET", "DRY_53,REEFER_53,MULTI_TEMP_53,PUP_28", "SATISFACTORY", 0.0, "TX"),
    ("CR001", "Heartland Express Lines", "HTLX", "CONTRACT", "DRY_53,REEFER_53,PUP_28", "SATISFACTORY", 2.35, "IA"),
    ("CR002", "Gulf Coast Reefer", "GCRF", "CONTRACT", "REEFER_53,MULTI_TEMP_53", "SATISFACTORY", 2.65, "LA"),
    ("CR003", "Summit Mountain Transport", "SMTT", "CONTRACT", "DRY_53,REEFER_53,MULTI_TEMP_53", "SATISFACTORY", 2.55, "UT"),
    ("CR004", "Carolina Cold Chain", "CCCH", "CONTRACT", "REEFER_53,MULTI_TEMP_53", "SATISFACTORY", 2.60, "NC"),
    ("CR005", "Golden State Freight", "GSFT", "CONTRACT", "DRY_53,REEFER_53,MULTI_TEMP_53,PUP_28", "SATISFACTORY", 2.80, "CA"),
    ("CR006", "Redline Freight Brokers", "RDLB", "BROKER", "DRY_53,REEFER_53,MULTI_TEMP_53", "CONDITIONAL", 2.15, "TX"),
    ("CR007", "Prairie Wind Logistics", "PWLG", "BROKER", "DRY_53,REEFER_53,MULTI_TEMP_53", "SATISFACTORY", 2.45, "KS"),
    ("CR008", "Peach State Carriers", "PSCR", "CONTRACT", "DRY_53,REEFER_53,PUP_28", "SATISFACTORY", 2.40, "GA"),
    ("CR009", "Great Lakes Haulers", "GLHL", "CONTRACT", "DRY_53,REEFER_53,MULTI_TEMP_53,PUP_28", "UNRATED", 2.50, "OH"),
]
BAD_CARRIER = "CR006"
LEAKY_CUSTOMER = "BurgerBarn"
REGIONAL_CARRIERS = {
    "DC01": ["CR006", "CR002", "CR001"], "DC02": ["CR008", "CR002", "CR006"], "DC03": ["CR004", "CR008"],
    "DC04": ["CR009", "CR001", "CR006"], "DC05": ["CR003", "CR007"], "DC06": ["CR005", "CR003", "CR007"],
    "DC07": ["CR008", "CR004", "CR006"], "DC08": ["CR007", "CR001", "CR009"],
}

FIRST = ["James", "Maria", "Robert", "Linda", "Carlos", "Aisha", "Wei", "Priya", "Tom", "Keisha", "Luis", "Emily",
         "Darnell", "Sofia", "Ahmed", "Grace", "Hector", "Nina", "Owen", "Tara", "Victor", "Yuki", "Zane", "Rosa"]
LAST = ["Smith", "Garcia", "Johnson", "Nguyen", "Patel", "Williams", "Brown", "Lopez", "Kim", "Davis", "Martinez",
        "Wilson", "Anderson", "Thomas", "Moore", "Jackson", "Clark", "Lewis", "Walker", "Young", "Hall", "Allen"]

COMMODITY_BY_SEGMENT = {
    "RETAIL_CONVENIENCE": [("DRY_GROCERY", 0.45), ("TOBACCO_CANDY", 0.35), ("CHILLED", 0.12), ("FROZEN", 0.08)],
    "RETAIL_GROCERY": [("DRY_GROCERY", 0.5), ("CHILLED", 0.25), ("FROZEN", 0.25)],
    "RESTAURANT_QSR": [("FOODSERVICE_MIXED", 0.7), ("FROZEN", 0.3)],
    "RESTAURANT_CASUAL": [("FOODSERVICE_MIXED", 0.8), ("CHILLED", 0.2)],
    "MILITARY": [("DRY_GROCERY", 0.6), ("TOBACCO_CANDY", 0.2), ("FROZEN", 0.2)],
}
TEMP_CLASS = {"DRY_GROCERY": "AMBIENT", "TOBACCO_CANDY": "AMBIENT", "CHILLED": "CHILLED",
              "FROZEN": "FROZEN", "FOODSERVICE_MIXED": "MULTI"}

FUEL_BASE = {"PADD1": 3.72, "PADD2": 3.58, "PADD3": 3.42, "PADD4": 3.86, "PADD5": 4.55}
SPIKE_REGIONS = {"PADD3", "PADD5"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def haversine_miles(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def road_miles(a, b) -> float:
    return haversine_miles(a, b) * 1.22


def weighted(rng: random.Random, pairs):
    r, acc = rng.random(), 0.0
    for value, w in pairs:
        acc += w
        if r <= acc:
            return value
    return pairs[-1][0]


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def ts(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


def money(x: float) -> float:
    return round(x, 2)


class Gen:
    def __init__(self, days: int, as_of: date, seed: int, loads_per_dc_day: int):
        self.rng = random.Random(seed)
        self.days = days
        self.as_of = as_of
        self.start = as_of - timedelta(days=days - 1)
        self.loads_per_dc_day = loads_per_dc_day
        self.rows: dict[str, list[dict]] = defaultdict(list)
        self.ids = defaultdict(int)

    def nid(self, prefix: str, width: int = 6) -> str:
        self.ids[prefix] += 1
        return f"{prefix}{self.ids[prefix]:0{width}d}"

    # -- master data -------------------------------------------------------
    def build_master(self):
        rng = self.rng
        self.dc = {}
        for dc_id, name, city, st, lat, lon, padd, states in DCS:
            self.dc[dc_id] = dict(name=name, state=st, lat=lat, lon=lon, padd=padd, states=states)
            self.rows["locations"].append(dict(
                location_id=dc_id, location_name=name, location_type="DC", customer_id=None, dc_id=dc_id,
                city=city, state=st, latitude=lat, longitude=lon, dock_open_hour=0, dock_close_hour=23,
                avg_unload_minutes=45, requires_liftgate=False, padd_region=padd))

        self.customers = {}
        for i, (name, seg, bu, tier, hq) in enumerate(CUSTOMERS, 1):
            cid = f"CUS{i:04d}"
            self.customers[cid] = dict(name=name, segment=seg, bu=bu, tier=tier, hq=hq)
            self.rows["customers"].append(dict(
                customer_id=cid, customer_name=name, segment=seg, business_unit=bu, service_tier=tier,
                on_time_target_pct=TIER_TARGET[tier], late_penalty_per_stop=TIER_PENALTY[tier],
                payment_terms_days=rng.choice([15, 30, 30, 45]), hq_state=hq))
        self.leaky_cid = next(c for c, v in self.customers.items() if v["name"] == LEAKY_CUSTOMER)

        # Stores / restaurants: each customer present in a few DC regions.
        self.dest_by_dc: dict[str, list[str]] = defaultdict(list)
        self.loc = {}
        for cid, cu in self.customers.items():
            home_dcs = [d for d, v in self.dc.items() if cu["hq"] in v["states"]] or [rng.choice(list(self.dc))]
            extra = rng.sample([d for d in self.dc if d not in home_dcs], k=rng.randint(1, 3))
            if cu["name"] == LEAKY_CUSTOMER:
                home_dcs, extra = ["DC04"], ["DC08"]
            if cu["name"] == "Desert Rose Diner":
                home_dcs, extra = ["DC05", "DC06"], []
            for dc_id in home_dcs + extra:
                n = rng.randint(25, 45) if dc_id in home_dcs else rng.randint(8, 18)
                for _ in range(n):
                    self._add_dest(cid, cu, dc_id)
        # Make sure DC05 serves plenty of remote Nevada stops (the unprofitable lane).
        nv_cust = [c for c, v in self.customers.items() if v["name"] in ("Desert Rose Diner", "Wasatch Corner Stores")]
        for _ in range(30):
            cid = rng.choice(nv_cust)
            self._add_dest(cid, self.customers[cid], "DC05", force_state="NV")

        for car in CARRIERS:
            cid, name, scac, ctype, equip, safety, rate, home = car
            self.rows["carriers"].append(dict(
                carrier_id=cid, carrier_name=name, scac=scac, carrier_type=ctype, equipment_types=equip,
                safety_rating=safety,
                insurance_expiry_date=(self.as_of + timedelta(days=rng.randint(-10, 400))).isoformat(),
                contract_rate_per_mile=rate, home_state=home))

        self.rates = {}
        for dc_id, carriers in REGIONAL_CARRIERS.items():
            for cid in carriers:
                car = next(x for x in CARRIERS if x[0] == cid)
                for st in self.dc[dc_id]["states"]:
                    for equip in car[4].split(","):
                        r = dict(rate_id=self.nid("RATE", 5), carrier_id=cid, origin_dc_id=dc_id, dest_state=st,
                                 equipment_type=equip, rate_per_mile=round(car[6] * rng.uniform(0.94, 1.08), 3),
                                 stop_charge=40.0, min_charge=350.0, fsc_base_price=1.25, fsc_mpg=6.0,
                                 detention_rate_per_hr=65.0, free_time_minutes=120, lumper_requires_receipt=True,
                                 effective_date=(self.as_of - timedelta(days=200)).isoformat(),
                                 expiry_date=(self.as_of + timedelta(days=165)).isoformat())
                        self.rates[(cid, dc_id, st, equip)] = r
                        self.rows["carrier_rates"].append(r)

        self.drivers_by_dc = defaultdict(list)
        self.tractors_by_dc = defaultdict(list)
        self.trailers_by_dc = defaultdict(lambda: defaultdict(list))
        self.driver = {}
        self.tractor = {}
        self.trailer = {}
        for dc_id in self.dc:
            for _ in range(40):
                did = self.nid("DRV", 5)
                d = dict(driver_id=did, driver_name=f"{rng.choice(FIRST)} {rng.choice(LAST)}", home_dc_id=dc_id,
                         driver_type=weighted(rng, [("COMPANY", 0.82), ("TEAM", 0.1), ("OWNER_OPERATOR", 0.08)]),
                         hire_date=(self.as_of - timedelta(days=rng.randint(60, 6000))).isoformat(),
                         hazmat_endorsed=rng.random() < 0.3,
                         status=weighted(rng, [("ACTIVE", 0.93), ("ON_LEAVE", 0.05), ("TERMINATED", 0.02)]),
                         safety_score=int(min(100, max(40, rng.gauss(84, 9)))),
                         hos_drive_hours_remaining=round(rng.uniform(4, 11), 1),
                         hos_cycle_hours_remaining=round(rng.uniform(15, 70), 1))
                self.rows["drivers"].append(d)
                self.driver[did] = d
                if d["status"] == "ACTIVE":
                    self.drivers_by_dc[dc_id].append(did)
            for _ in range(36):
                tid = self.nid("TRC", 5)
                year = rng.randint(2016, 2026)
                t = dict(tractor_id=tid, home_dc_id=dc_id, make=rng.choice(["Freightliner", "Kenworth", "Peterbilt", "Volvo", "International"]),
                         model_year=year, fuel_type=weighted(rng, [("DIESEL", 0.9), ("CNG", 0.07), ("ELECTRIC", 0.03)]),
                         odometer_miles=int((2027 - year) * rng.uniform(85000, 115000)),
                         avg_mpg=round(rng.uniform(6.2, 7.6) - (2026 - year) * 0.05, 2),
                         status=weighted(rng, [("IN_SERVICE", 0.9), ("SHOP", 0.08), ("OUT_OF_SERVICE", 0.02)]),
                         next_pm_due_date=(self.as_of + timedelta(days=rng.randint(-15, 90))).isoformat())
                self.rows["tractors"].append(t)
                self.tractor[tid] = t
                self.tractors_by_dc[dc_id].append(tid)
            for ttype, n in (("DRY_53", 14), ("REEFER_53", 14), ("MULTI_TEMP_53", 16), ("PUP_28", 6)):
                for _ in range(n):
                    trl = self.nid("TRL", 5)
                    year = rng.randint(2012, 2026)
                    reefer_age = None if ttype in ("DRY_53", "PUP_28") else max(0, 2026 - year + rng.randint(-1, 2))
                    t = dict(trailer_id=trl, home_dc_id=dc_id, trailer_type=ttype, model_year=year,
                             reefer_unit_age_years=reefer_age,
                             status=weighted(rng, [("IN_SERVICE", 0.92), ("SHOP", 0.06), ("OUT_OF_SERVICE", 0.02)]))
                    self.rows["trailers"].append(t)
                    self.trailer[trl] = t
                    self.trailers_by_dc[dc_id][ttype].append(trl)

    def _add_dest(self, cid, cu, dc_id, force_state=None):
        rng = self.rng
        st = force_state or rng.choice(self.dc[dc_id]["states"])
        clat, clon = STATE_CENTROIDS[st]
        dlat, dlon = self.dc[dc_id]["lat"], self.dc[dc_id]["lon"]
        # Pull stores toward the DC so routes are regional (except the remote NV lane).
        pull = 0.15 if force_state == "NV" else rng.uniform(0.35, 0.7)
        lat = clat + (dlat - clat) * pull + rng.uniform(-0.9, 0.9)
        lon = clon + (dlon - clon) * pull + rng.uniform(-0.9, 0.9)
        is_rest = cu["segment"].startswith("RESTAURANT")
        prefix = "RST" if is_rest else "STR"
        lid = self.nid(prefix, 5)
        if cu["name"] == LEAKY_CUSTOMER:
            open_h, close_h, unload = 6, 10, 75
        elif is_rest:
            open_h, close_h, unload = rng.choice([5, 6, 7]), rng.choice([10, 11, 14]), rng.randint(35, 55)
        else:
            open_h, close_h, unload = rng.choice([0, 4, 5, 6]), rng.choice([14, 18, 22, 23]), rng.randint(20, 45)
        city = rng.choice(STATE_CITIES[st])
        liftgate = is_rest and rng.random() < 0.3
        # Some receivers are chronically congested (a learnable signal for delay prediction).
        congestion = min(0.45, rng.betavariate(0.6, 9))
        self.loc[lid] = dict(cid=cid, dc=dc_id, lat=lat, lon=lon, state=st, open=open_h, close=close_h, unload=unload,
                             liftgate=liftgate, congestion=congestion)
        self.dest_by_dc[dc_id].append(lid)
        self.rows["locations"].append(dict(
            location_id=lid, location_name=f"{cu['name']} #{self.ids[prefix]} {city}",
            location_type="RESTAURANT" if is_rest else "STORE", customer_id=cid, dc_id=dc_id, city=city, state=st,
            latitude=round(lat, 5), longitude=round(lon, 5), dock_open_hour=open_h, dock_close_hour=close_h,
            avg_unload_minutes=unload, requires_liftgate=liftgate, padd_region=self.dc[dc_id]["padd"]))

    # -- fuel ---------------------------------------------------------------
    def build_fuel(self):
        rng = self.rng
        self.fuel = {}
        w = monday(self.start) - timedelta(weeks=3)
        last = monday(self.as_of + timedelta(days=7))
        price = dict(FUEL_BASE)
        spike_start = monday(self.as_of) - timedelta(weeks=4)
        while w <= last:
            for padd in FUEL_BASE:
                price[padd] = max(2.8, price[padd] + rng.gauss(0, 0.035))
                p = price[padd]
                if padd in SPIKE_REGIONS and w >= spike_start:
                    weeks_in = (w - spike_start).days // 7 + 1
                    p += min(0.68, 0.17 * weeks_in)
                self.fuel[(w, padd)] = round(p, 3)
                self.rows["fuel_prices"].append(dict(week_start_date=w.isoformat(), padd_region=padd,
                                                     diesel_price_per_gal=round(p, 3)))
            w += timedelta(weeks=1)

    def diesel(self, d: date, padd: str, lag_weeks: int = 0) -> float:
        return self.fuel[(monday(d) - timedelta(weeks=lag_weeks), padd)]

    # -- transactions -------------------------------------------------------
    def build_loads(self):
        rng = self.rng
        weather_days = {(rng.choice(list(self.dc)), self.start + timedelta(days=rng.randint(0, self.days - 1)))
                        for _ in range(max(3, self.days // 10))}
        for day_offset in range(self.days + 1):  # +1 = tomorrow's planned loads
            d = self.start + timedelta(days=day_offset)
            is_future = d > self.as_of
            is_today = d == self.as_of
            dow = d.weekday()
            if dow == 6:  # light Sunday
                vol = max(1, self.loads_per_dc_day // 3)
            else:
                vol = self.loads_per_dc_day + (1 if dow in (0, 3) else 0)
            for dc_id in self.dc:
                used_drivers, used_tractors, used_trailers = set(), set(), set()
                for _ in range(vol):
                    self._make_load(dc_id, d, is_today, is_future, (dc_id, d) in weather_days,
                                    used_drivers, used_tractors, used_trailers)

    def _make_load(self, dc_id, d, is_today, is_future, weather, used_d, used_t, used_tr):
        rng = self.rng
        dc = self.dc[dc_id]
        padd = dc["padd"]
        nv_lane = dc_id == "DC05" and rng.random() < 0.18
        dests = self.dest_by_dc[dc_id]
        if nv_lane:
            pool = [l for l in dests if self.loc[l]["state"] == "NV"]
            n_stops = rng.randint(2, 4)
        else:
            anchor = self.loc[rng.choice(dests)]
            pool = sorted(dests, key=lambda l: (self.loc[l]["lat"] - anchor["lat"]) ** 2 + (self.loc[l]["lon"] - anchor["lon"]) ** 2)[:14]
            n_stops = rng.randint(3, 8)
        stops = rng.sample(pool, k=min(n_stops, len(pool)))
        # Nearest-neighbour sequencing from the DC.
        seq, cur = [], (dc["lat"], dc["lon"])
        remaining = list(stops)
        while remaining:
            nxt = min(remaining, key=lambda l: haversine_miles(cur, (self.loc[l]["lat"], self.loc[l]["lon"])))
            seq.append(nxt)
            remaining.remove(nxt)
            cur = (self.loc[nxt]["lat"], self.loc[nxt]["lon"])

        # Commodity mix decides equipment.
        orders = []
        for lid in seq:
            cu = self.customers[self.loc[lid]["cid"]]
            com = weighted(rng, COMMODITY_BY_SEGMENT[cu["segment"]])
            orders.append((lid, com))
        temps = {TEMP_CLASS[c] for _, c in orders}
        if len(temps) > 1 or "MULTI" in temps:
            equip = "MULTI_TEMP_53"
        elif temps & {"CHILLED", "FROZEN"}:
            equip = "REEFER_53"
        else:
            equip = "PUP_28" if len(seq) <= 3 and self.rng.random() < 0.5 else "DRY_53"

        private = rng.random() < 0.72
        carrier_id = "MCLN"
        driver_id = tractor_id = trailer_id = None
        if private:
            free_d = [x for x in self.drivers_by_dc[dc_id] if x not in used_d]
            free_t = [x for x in self.tractors_by_dc[dc_id] if x not in used_t and self.tractor[x]["status"] == "IN_SERVICE"]
            free_tr = [x for x in self.trailers_by_dc[dc_id][equip] if x not in used_tr]
            if free_d and free_t and free_tr:
                driver_id, tractor_id, trailer_id = rng.choice(free_d), rng.choice(free_t), rng.choice(free_tr)
                used_d.add(driver_id); used_t.add(tractor_id); used_tr.add(trailer_id)
            else:
                private = False
        if not private:
            options = [c for c in REGIONAL_CARRIERS[dc_id]
                       if equip in next(x for x in CARRIERS if x[0] == c)[4]] or REGIONAL_CARRIERS[dc_id]
            carrier_id = rng.choice(options)
            if rng.random() < 0.1:
                # Contract carriers rejected: load moves on the spot market with a broker that has no lane contract.
                carrier_id = "CR007" if "CR007" not in REGIONAL_CARRIERS[dc_id] else "CR006"

        load_id = self.nid("LGH", 7)
        planned_start = datetime.combine(d, datetime.min.time()) + timedelta(hours=rng.choice([2, 3, 3, 4, 5, 6]), minutes=rng.choice([0, 15, 30, 45]))

        # Dispatch delay: Monday DC03 late dispatch story.
        dispatch_delay = max(-10, rng.gauss(5, 12))
        late_dispatch = dc_id == "DC03" and d.weekday() == 0 and rng.random() < 0.65
        if late_dispatch:
            dispatch_delay += rng.uniform(60, 150)
        actual_start = planned_start + timedelta(minutes=dispatch_delay)

        carrier_penalty = 0.0
        if carrier_id == BAD_CARRIER:
            carrier_penalty = rng.choice([0, 0, 25, 50, 80, 120])
        elif carrier_id != "MCLN":
            carrier_penalty = rng.choice([0, 0, 0, 10, 20])

        n_arrived = len(seq)
        if is_future:
            n_arrived = 0
        elif is_today:
            n_arrived = rng.randint(0, len(seq) - 1) if rng.random() < 0.85 else len(seq)

        stop_rows, order_rows = [], []
        cur = (dc["lat"], dc["lon"])
        plan_t, act_t = planned_start, actual_start
        loaded_miles = 0.0
        load_detention_paid = 0.0
        load_lumper = 0.0
        last_arrival = None
        for i, (lid, com) in enumerate(orders, 1):
            loc = self.loc[lid]
            cu = self.customers[loc["cid"]]
            leg = road_miles(cur, (loc["lat"], loc["lon"]))
            loaded_miles += leg
            drive_min = leg / 47 * 60
            plan_t = plan_t + timedelta(minutes=drive_min)
            # Snap planned arrival into the dock window.
            open_dt = datetime.combine(plan_t.date(), datetime.min.time()) + timedelta(hours=loc["open"])
            if plan_t < open_dt:
                plan_t = open_dt
            window_start = plan_t - timedelta(minutes=30)
            window_end = plan_t + timedelta(minutes=90)

            traffic = rng.gauss(-4, 14)
            weather_delay = rng.uniform(30, 120) if weather else 0
            act_t = act_t + timedelta(minutes=drive_min + traffic + carrier_penalty / max(1, len(seq)) * 1.5 + weather_delay / len(seq))
            if act_t < window_start - timedelta(minutes=20):
                act_t = window_start - timedelta(minutes=rng.uniform(0, 20))

            cases = int(max(20, rng.gauss(140 if cu["segment"] != "RETAIL_GROCERY" else 320, 45)))
            weight = int(cases * rng.uniform(18, 28))
            cube = int(cases * rng.uniform(1.1, 1.8))
            order_id = self.nid("ORD", 7)
            stop_id = self.nid("STP", 8)
            arrived = i <= n_arrived
            row = dict(stop_id=stop_id, load_id=load_id, order_id=order_id, stop_sequence=i, location_id=lid,
                       delivery_date=window_start.date().isoformat(), appt_window_start_ts=ts(window_start),
                       appt_window_end_ts=ts(window_end), arrival_ts=None, departure_ts=None, on_time_flag=None,
                       minutes_late=None, dwell_minutes=None, detention_minutes=None, cases_delivered=None,
                       cases_short=None, cases_damaged=None, refused_flag=None)
            if arrived:
                minutes_late = max(0, int((act_t - window_end).total_seconds() // 60))
                dwell = loc["unload"] * rng.uniform(0.8, 1.4) + max(0, rng.gauss(0, 15))
                if loc["cid"] == self.leaky_cid:
                    dwell += rng.uniform(40, 130)  # dock congestion at BurgerBarn
                elif rng.random() < loc["congestion"]:
                    dwell += rng.uniform(60, 150)  # receiver congestion (location specific)
                elif minutes_late > 60:
                    dwell += rng.uniform(10, 60)  # missed slot, wait for a door
                dwell = int(dwell)
                detention = max(0, dwell - 120)
                short_p = 0.022
                if com == "TOBACCO_CANDY" and dc_id == "DC02":
                    short_p = 0.28
                cases_short = rng.randint(1, 12) if rng.random() < short_p else 0
                damaged = rng.randint(1, 6) if rng.random() < (0.035 if carrier_id == BAD_CARRIER else 0.01) else 0
                refused = rng.random() < (0.006 + (0.04 if minutes_late > 120 else 0))
                departure = act_t + timedelta(minutes=dwell)
                row.update(arrival_ts=ts(act_t), departure_ts=ts(departure), on_time_flag=minutes_late == 0,
                           minutes_late=minutes_late, dwell_minutes=dwell, detention_minutes=detention,
                           cases_delivered=cases - cases_short, cases_short=cases_short, cases_damaged=damaged,
                           refused_flag=refused)
                if carrier_id != "MCLN" and detention:
                    load_detention_paid += detention / 60 * 65
                if loc["cid"] == self.leaky_cid and carrier_id != "MCLN" and rng.random() < 0.4:
                    load_lumper += rng.choice([75, 100, 125])
                last_arrival = departure
                act_t = departure
                self._stop_exceptions(load_id, row, com, cu, late_dispatch, weather)
            else:
                act_t = act_t + timedelta(minutes=loc["unload"])
            # Planners budget extra dock time at known congested receivers.
            plan_t = plan_t + timedelta(minutes=loc["unload"] + (85 if loc["cid"] == self.leaky_cid else 0))
            cur = (loc["lat"], loc["lon"])
            stop_rows.append(row)
            order_rows.append(dict(order_id=order_id, customer_id=loc["cid"], origin_location_id=dc_id,
                                   dest_location_id=lid, load_id=load_id,
                                   order_date=(d - timedelta(days=rng.randint(1, 4))).isoformat(),
                                   requested_delivery_date=window_start.date().isoformat(), commodity=com,
                                   temperature_class=TEMP_CLASS[com], cases=cases, weight_lbs=weight, cube_ft=cube,
                                   _arrived=arrived, _row=row, _cust=cu, _loc=loc))

        empty_miles = road_miles(cur, (dc["lat"], dc["lon"]))
        if nv_lane:
            empty_miles *= 1.15  # no backhaul available out of rural Nevada
        total_miles = loaded_miles + empty_miles
        planned_end = plan_t + timedelta(minutes=empty_miles / 47 * 60)
        if is_future:
            status = rng.choice(["PLANNED", "DISPATCHED"])
            actual_start_v = None
            actual_end = None
        elif n_arrived < len(seq):
            status = "IN_TRANSIT"
            actual_start_v = actual_start
            actual_end = None
        else:
            status = "COMPLETED"
            actual_start_v = actual_start
            actual_end = last_arrival + timedelta(minutes=empty_miles / 47 * 60)

        # ---- revenue (billed on loaded miles + stop fees, fuel surcharge lags 2 weeks) ----
        fsc_per_mile = max(0.0, (self.diesel(d, padd, lag_weeks=2) - 1.25) / 6.0)
        total_cases = sum(o["cases"] for o in order_rows)
        tier_mult = {"PLATINUM": 0.96, "GOLD": 1.0, "SILVER": 1.06}
        load_revenue = 0.0
        for o in order_rows:
            share = o["cases"] / total_cases
            cu, loc, srow = o.pop("_cust"), o.pop("_loc"), o.pop("_row")
            arrived = o.pop("_arrived")
            linehaul = (loaded_miles * 1.36 * share + 52 + o["cases"] * 0.24) * tier_mult[cu["tier"]]
            fsc = total_miles * share * fsc_per_mile
            liftgate = 35.0 if loc["liftgate"] else 0.0
            det_billed = 0.0
            if arrived and srow["detention_minutes"]:
                bill_p = 0.25 if loc["cid"] == self.leaky_cid else 0.7
                if rng.random() < bill_p:
                    det_billed = srow["detention_minutes"] / 60 * 75
            other_acc = (25.0 if rng.random() < 0.1 else 0.0) + liftgate
            acc = det_billed + other_acc
            total = linehaul + fsc + acc
            o.update(revenue_linehaul=money(linehaul), revenue_fuel_surcharge=money(fsc),
                     revenue_accessorial=money(acc), total_revenue=money(total))
            if is_future:
                o["order_status"] = "PLANNED" if status == "PLANNED" else "DISPATCHED"
            elif arrived:
                o["order_status"] = "DELIVERED"
            else:
                o["order_status"] = "IN_TRANSIT"
            load_revenue += total
            self.rows["orders"].append(o)
            if arrived and status == "COMPLETED":
                late_pen = 0.0
                if not srow["on_time_flag"] and srow["minutes_late"] > 15 and rng.random() < 0.6:
                    late_pen = TIER_PENALTY[cu["tier"]]
                paid = d < self.as_of - timedelta(days=20) or rng.random() < 0.3
                self.rows["invoices"].append(dict(
                    invoice_id=self.nid("INV", 7), order_id=o["order_id"], customer_id=o["customer_id"],
                    invoice_date=(d + timedelta(days=1)).isoformat(), linehaul_amount=money(linehaul),
                    fuel_surcharge_amount=money(fsc), detention_billed=money(det_billed),
                    other_accessorial_billed=money(other_acc), late_penalty_amount=money(late_pen),
                    total_amount=money(total - late_pen), paid_flag=paid,
                    days_to_pay=rng.randint(10, 50) if paid else None))

        # ---- cost ----
        costs = []
        if not is_future:
            diesel_now = self.diesel(d, padd)
            if carrier_id == "MCLN":
                mpg = self.tractor[tractor_id]["avg_mpg"]
                costs += [("DRIVER_PAY", total_miles * 0.64 + len(seq) * 28),
                          ("FUEL", total_miles / mpg * diesel_now),
                          ("MAINTENANCE_ALLOC", total_miles * 0.19)]
                if (actual_end or planned_end) - actual_start > timedelta(hours=14):
                    costs.append(("LAYOVER", 150.0))
            else:
                rate_row = self.rates.get((carrier_id, dc_id, self.loc[seq[-1]]["state"], equip))
                # No contract for this lane/equipment = spot load at a ~35% premium (audit flags NO_CONTRACT_RATE).
                rate = float(rate_row["rate_per_mile"]) if rate_row else next(x for x in CARRIERS if x[0] == carrier_id)[6] * 1.35
                linehaul_cost = max(350.0, total_miles * rate + len(seq) * 40)
                fuel_cost = total_miles * max(0.0, (diesel_now - 1.25) / 6.0)
                costs += [("CARRIER_LINEHAUL", linehaul_cost), ("FUEL", fuel_cost)]
                if load_detention_paid:
                    costs.append(("DETENTION_PAID", load_detention_paid))
                if load_lumper:
                    costs.append(("LUMPER", load_lumper))
            if rng.random() < 0.12:
                costs.append(("TOLLS", rng.uniform(12, 65)))
            if carrier_id != "MCLN" and status == "COMPLETED":
                self._carrier_invoice(load_id, carrier_id, d, total_miles, rate, linehaul_cost, fuel_cost,
                                      load_detention_paid, load_lumper, has_contract=rate_row is not None)
        total_cost = 0.0
        for ctype, amt in costs:
            total_cost += amt
            self.rows["load_costs"].append(dict(cost_id=self.nid("CST", 8), load_id=load_id, cost_type=ctype,
                                                amount=money(amt), cost_date=d.isoformat()))

        self.rows["loads"].append(dict(
            load_id=load_id, origin_dc_id=dc_id, carrier_id=carrier_id, driver_id=driver_id, tractor_id=tractor_id,
            trailer_id=trailer_id, equipment_type=equip, load_date=d.isoformat(), planned_start_ts=ts(planned_start),
            actual_start_ts=ts(actual_start_v), planned_end_ts=ts(planned_end), actual_end_ts=ts(actual_end),
            stop_count=len(seq), loaded_miles=round(loaded_miles, 1), empty_miles=round(empty_miles, 1),
            total_miles=round(total_miles, 1), dest_region_state=self.loc[seq[-1]]["state"], load_status=status,
            total_revenue=money(load_revenue), total_cost=money(total_cost)))
        self.rows["stops"].extend(stop_rows)

        if carrier_id != "MCLN":
            self._tenders(load_id, dc_id, carrier_id, d, total_miles, equip)
        if not is_future:
            self._load_events(load_id, dc_id, d, carrier_id, driver_id, tractor_id, trailer_id, equip,
                              actual_start, seq, status, weather)

    def _tenders(self, load_id, dc_id, final_carrier, d, miles, equip):
        rng = self.rng
        tender_t = datetime.combine(d - timedelta(days=1), datetime.min.time()) + timedelta(hours=rng.randint(8, 17))
        equip_of = {c[0]: c[4] for c in CARRIERS}
        others = [c for c in REGIONAL_CARRIERS[dc_id] if c not in (final_carrier, BAD_CARRIER) and equip in equip_of[c]]
        attempts = rng.sample(others, k=min(len(others), rng.choice([0, 0, 0, 1])))
        if final_carrier != BAD_CARRIER and BAD_CARRIER in REGIONAL_CARRIERS[dc_id] and rng.random() < 0.6:
            attempts.insert(0, BAD_CARRIER)  # Redline offered first (cheapest) and often rejects
        rate_of = {c[0]: c[6] for c in CARRIERS}
        for c in attempts:
            resp = weighted(rng, [("REJECTED", 0.75), ("EXPIRED", 0.25)])
            self.rows["carrier_tenders"].append(dict(
                tender_id=self.nid("TND", 7), load_id=load_id, carrier_id=c, tender_ts=ts(tender_t),
                tender_date=tender_t.date().isoformat(), offered_rate=money(miles * rate_of[c]), response=resp,
                response_minutes=rng.randint(30, 240) if resp == "REJECTED" else 240))
            tender_t += timedelta(minutes=rng.randint(30, 240))
        self.rows["carrier_tenders"].append(dict(
            tender_id=self.nid("TND", 7), load_id=load_id, carrier_id=final_carrier, tender_ts=ts(tender_t),
            tender_date=tender_t.date().isoformat(), offered_rate=money(miles * rate_of[final_carrier]),
            response="ACCEPTED", response_minutes=rng.randint(5, 90)))

    def _carrier_invoice(self, load_id, carrier_id, d, miles, rate, linehaul, fuel, detention, lumper, has_contract=True):
        """Freight bill as the carrier sends it, with realistic overbilling errors to audit."""
        rng = self.rng
        billed = dict(rate=rate, miles=miles, linehaul=linehaul, fuel=fuel, detention=detention, lumper=lumper,
                      receipt=lumper > 0, other=0.0)
        err_p = 0.26 if carrier_id == BAD_CARRIER else 0.07
        if rng.random() < err_p:
            err = weighted(rng, [("RATE_ABOVE_CONTRACT", 0.3), ("MILES_INFLATED", 0.15), ("FUEL_ABOVE_TABLE", 0.15),
                                 ("DETENTION_NO_EVIDENCE", 0.15), ("DUPLICATE_ACCESSORIAL", 0.1),
                                 ("LUMPER_NO_RECEIPT", 0.15)])
            if err == "RATE_ABOVE_CONTRACT" and not has_contract:
                err = "MILES_INFLATED"  # spot load: no contract rate to exceed
            if err == "DUPLICATE_ACCESSORIAL" and not detention:
                err = "DETENTION_NO_EVIDENCE"  # nothing to duplicate: carrier invents detention instead
            self.rows["_truth_invoice_errors"].append({"carrier_invoice_id": f"CINV{self.ids['CINV'] + 1:07d}",
                                                       "error_code": err})
            if err == "RATE_ABOVE_CONTRACT":
                billed["rate"] = rate * rng.uniform(1.06, 1.16)
                billed["linehaul"] = linehaul - miles * rate + miles * billed["rate"]
            elif err == "MILES_INFLATED":
                billed["miles"] = miles * rng.uniform(1.08, 1.2)
                billed["linehaul"] = linehaul + (billed["miles"] - miles) * rate
            elif err == "FUEL_ABOVE_TABLE":
                billed["fuel"] = fuel * rng.uniform(1.2, 1.45)
            elif err == "DETENTION_NO_EVIDENCE" or (err == "DUPLICATE_ACCESSORIAL" and not detention):
                billed["detention"] = detention + rng.choice([2, 2.5, 3]) * 65
            elif err == "DUPLICATE_ACCESSORIAL":
                billed["detention"] = detention * 2
            elif err == "LUMPER_NO_RECEIPT":
                billed["lumper"] = lumper + rng.choice([75, 100, 125])
                billed["receipt"] = False
        if rng.random() < 0.05:
            billed["other"] = rng.choice([45.0, 75.0])  # tolls / misc, legitimately billable
        source = weighted(rng, [("EDI_210", 0.7), ("PDF_SCAN", 0.25), ("EMAIL", 0.05)])
        inv_id = self.nid("CINV", 7)
        fsc = billed["fuel"]
        if source == "PDF_SCAN" and rng.random() < 0.08:
            fsc = None  # illegible / missing on the scan: must be flagged, not guessed
        total = billed["linehaul"] + (fsc or 0) + billed["detention"] + billed["lumper"] + billed["other"]
        inv_date = d + timedelta(days=rng.randint(1, 5))
        status = "PAID" if inv_date < self.as_of - timedelta(days=30) else rng.choice(["RECEIVED", "RECEIVED", "APPROVED"])
        self.rows["carrier_invoices"].append(dict(
            carrier_invoice_id=inv_id, load_id=load_id, carrier_id=carrier_id, invoice_date=inv_date.isoformat(),
            source=source,
            document_uri=f"gs://YOUR_BUCKET/carrier-invoices/{inv_id}.pdf" if source != "EDI_210" else None,
            billed_rate_per_mile=round(billed["rate"], 3) if not (source == "PDF_SCAN" and fsc is None) else None,
            billed_miles=round(billed["miles"], 1), billed_linehaul=money(billed["linehaul"]),
            billed_fuel_surcharge=money(fsc) if fsc is not None else None, billed_detention=money(billed["detention"]),
            billed_lumper=money(billed["lumper"]), lumper_receipt_attached=billed["receipt"],
            billed_other=money(billed["other"]), billed_total=money(total), invoice_status=status))

    def _exception(self, load_id, stop_id, etype, sev, when, cause, desc, cost):
        resolved = when.date() < self.as_of - timedelta(days=1) or self.rng.random() < 0.3
        self.rows["exceptions"].append(dict(
            exception_id=self.nid("EXC", 7), load_id=load_id, stop_id=stop_id, exception_type=etype, severity=sev,
            event_ts=ts(when), event_date=when.date().isoformat(), root_cause=cause, description=desc,
            resolved_flag=resolved, cost_impact=money(cost)))

    def _stop_exceptions(self, load_id, row, com, cu, late_dispatch, weather):
        rng = self.rng
        when = datetime.strptime(row["arrival_ts"], "%Y-%m-%d %H:%M:%S")
        late = row["minutes_late"]
        if late > 30:
            sev = "CRITICAL" if late > 180 else "HIGH" if late > 90 else "MEDIUM"
            cause = ("LATE_DISPATCH" if late_dispatch else "WEATHER" if weather
                     else weighted(rng, [("TRAFFIC", 0.45), ("DOCK_CONGESTION", 0.2), ("DRIVER", 0.15), ("EQUIPMENT", 0.1), ("CUSTOMER", 0.1)]))
            self._exception(load_id, row["stop_id"], "LATE_ARRIVAL", sev, when, cause,
                            f"Arrived {late} min after window end at {row['location_id']}", TIER_PENALTY[cu["tier"]])
        if row["detention_minutes"] > 60:
            self._exception(load_id, row["stop_id"], "DETENTION", "MEDIUM" if row["detention_minutes"] < 120 else "HIGH",
                            when, "DOCK_CONGESTION", f"{row['detention_minutes']} min detention at receiver",
                            row["detention_minutes"] / 60 * 75)
        if row["cases_short"]:
            self._exception(load_id, row["stop_id"], "SHORTAGE", "HIGH" if com == "TOBACCO_CANDY" else "LOW", when,
                            "PICKING_ERROR", f"{row['cases_short']} cases short ({com})",
                            row["cases_short"] * (180 if com == "TOBACCO_CANDY" else 35))
        if row["cases_damaged"]:
            self._exception(load_id, row["stop_id"], "DAMAGE", "LOW", when, "DRIVER",
                            f"{row['cases_damaged']} cases damaged", row["cases_damaged"] * 40)
        if row["refused_flag"]:
            self._exception(load_id, row["stop_id"], "REFUSED_DELIVERY", "HIGH", when, "CUSTOMER",
                            "Receiver refused delivery", 350)

    def _load_events(self, load_id, dc_id, d, carrier_id, driver_id, tractor_id, trailer_id, equip, start, seq,
                     status, weather):
        rng = self.rng
        reefer = equip in ("REEFER_53", "MULTI_TEMP_53")
        old_reefer = bool(trailer_id and (self.trailer[trailer_id]["reefer_unit_age_years"] or 0) >= 9)
        excursion = reefer and rng.random() < (0.16 if old_reefer else 0.012)
        if excursion:
            self._exception(load_id, None, "REEFER_TEMP_EXCURSION", "CRITICAL" if old_reefer else "HIGH",
                            start + timedelta(hours=rng.uniform(1, 5)), "EQUIPMENT",
                            f"Return air above setpoint by >8F on trailer {trailer_id or 'carrier-owned'}",
                            rng.uniform(800, 4500))
        if tractor_id and self.tractor[tractor_id]["model_year"] <= 2018 and rng.random() < 0.02:
            self._exception(load_id, None, "BREAKDOWN", "HIGH", start + timedelta(hours=rng.uniform(1, 6)),
                            "EQUIPMENT", f"Roadside breakdown tractor {tractor_id}", rng.uniform(600, 2500))
        if weather and rng.random() < 0.6:
            self._exception(load_id, None, "WEATHER_DELAY", "MEDIUM", start + timedelta(hours=1), "WEATHER",
                            "Severe weather on route", 0)
        hos_risk = False
        if status == "IN_TRANSIT" and driver_id and rng.random() < 0.35:
            self.driver[driver_id]["hos_drive_hours_remaining"] = round(rng.uniform(0.3, 1.8), 1)
            hos_risk = True
            self._exception(load_id, None, "HOS_RISK", "HIGH", datetime.combine(self.as_of, datetime.min.time()) + timedelta(hours=9),
                            "DRIVER", f"Driver {driver_id} has <2h drive time left with stops remaining", 0)

        # Telematics pings only for the last 7 days (keeps volume small).
        if d < self.as_of - timedelta(days=6):
            return
        dc = self.dc[dc_id]
        pts = [(dc["lat"], dc["lon"])] + [(self.loc[l]["lat"], self.loc[l]["lon"]) for l in seq]
        setpoint = -5.0 if equip == "REEFER_53" else 34.0
        t = start
        horizon = datetime.combine(self.as_of, datetime.min.time()) + timedelta(hours=11)
        for k in range(len(pts) - 1):
            a, b = pts[k], pts[k + 1]
            n = max(1, int(road_miles(a, b) / 40))
            for j in range(n):
                if t > horizon:
                    return
                f = j / n
                temp = None
                if reefer:
                    temp = setpoint + rng.gauss(0, 1.2)
                    if excursion and k >= 1:
                        temp += rng.uniform(8, 14)
                eta = t + timedelta(minutes=(n - j) * 51 + (rng.uniform(20, 90) if hos_risk else 0))
                self.rows["check_calls"].append(dict(
                    check_call_id=self.nid("CHK", 8), load_id=load_id, event_ts=ts(t),
                    latitude=round(a[0] + (b[0] - a[0]) * f, 5), longitude=round(a[1] + (b[1] - a[1]) * f, 5),
                    speed_mph=round(max(0, rng.gauss(52, 9)), 1), reefer_temp_f=round(temp, 1) if temp is not None else None,
                    reefer_setpoint_f=setpoint if reefer else None, eta_next_stop_ts=ts(eta)))
                t += timedelta(minutes=rng.uniform(45, 60))
            t += timedelta(minutes=45)

    # -- output ------------------------------------------------------------
    def write(self, out: Path):
        out.mkdir(parents=True, exist_ok=True)
        counts = {}
        for name, table in TABLES_BY_NAME.items():
            path = out / f"{name}.csv"
            with path.open("w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(table.column_names)
                for r in self.rows[name]:
                    w.writerow([_fmt(r.get(c)) for c in table.column_names])
            counts[name] = len(self.rows[name])
        (out / "_as_of.txt").write_text(self.as_of.isoformat() + "\n")
        # Ground truth for evaluating the invoice audit (not loaded into the database).
        with (out / "_truth_invoice_errors.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["carrier_invoice_id", "error_code"])
            w.writeheader()
            w.writerows(self.rows["_truth_invoice_errors"])
        return counts


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    return v


# Fixed default "today" so every teammate (and the sample invoice PDFs) see identical data.
DEFAULT_AS_OF = date(2026, 10, 27)


def generate(out: str | Path = "data/generated", days: int = 120, as_of: date | None = None, seed: int = 42,
             loads_per_dc_day: int = 6) -> dict[str, int]:
    g = Gen(days=days, as_of=as_of or DEFAULT_AS_OF, seed=seed, loads_per_dc_day=loads_per_dc_day)
    g.build_master()
    g.build_fuel()
    g.build_loads()
    return g.write(Path(out))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/generated")
    ap.add_argument("--days", type=int, default=120, help="History length in days.")
    ap.add_argument("--as-of", type=date.fromisoformat, default=None, help="'Today' for the dataset (default: 2026-10-27, the hackathon day).")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--loads-per-dc-day", type=int, default=6)
    a = ap.parse_args()
    counts = generate(a.out, a.days, a.as_of, a.seed, a.loads_per_dc_day)
    for k, v in counts.items():
        print(f"{k:16s} {v:>8,d}")


if __name__ == "__main__":
    main()
