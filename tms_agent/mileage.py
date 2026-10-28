"""Route miles from Trimble PC*MILER Web Services, with a clearly labelled offline estimate.

TMW gets planned miles from its PC*MILER interface, so the warehouse already holds PC*MILER practical
miles (`loads.total_miles`, `stops.pcmiler_leg_miles`). This module is for miles the warehouse does not
have yet: a carrier bill with a different stop list, a what-if re-sequence, or a spot quote.

    PCMILER_API_KEY=...            enables live calls (Trimble Maps API key)
    PCMILER_BASE_URL=...           default https://pcmiler.alk.com/apis/rest/v1.0/Service.svc
    PCMILER_EXTRA_PARAMS=...       optional extra query string, e.g. a routing-type option for your account

Without a key the result is a great-circle estimate times a circuity factor, labelled
ESTIMATE_HAVERSINE so an agent never presents it as PC*MILER miles ("flag, don't guess").
Check the Trimble Maps developer guide for your account's route options before relying on live calls.
"""

from __future__ import annotations

import json
import math
import os
import urllib.parse
import urllib.request

CIRCUITY = 1.22  # road miles / great-circle miles; matches the synthetic data generator
DEFAULT_BASE_URL = "https://pcmiler.alk.com/apis/rest/v1.0/Service.svc"


def haversine_miles(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def estimate_miles(points: list[tuple[float, float]]) -> float:
    return sum(haversine_miles(points[i], points[i + 1]) for i in range(len(points) - 1)) * CIRCUITY


def _pcmiler_miles(points: list[tuple[float, float]], api_key: str) -> float:
    stops = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in points)  # PC*MILER wants lon,lat
    query = {"stops": stops, "reports": "Mileage", "authToken": api_key}
    url = f"{os.getenv('PCMILER_BASE_URL', DEFAULT_BASE_URL)}/route/routeReports?{urllib.parse.urlencode(query)}"
    if extra := os.getenv("PCMILER_EXTRA_PARAMS"):
        url += "&" + extra.lstrip("&")
    req = urllib.request.Request(url, headers={"Authorization": api_key, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 (fixed https host)
        body = json.load(resp)
    reports = body if isinstance(body, list) else [body]
    for report in reports:
        lines = report.get("ReportLines") or []
        if lines:
            return float(str(lines[-1].get("TMiles", "")).replace(",", ""))
    raise ValueError("No ReportLines / TMiles in the PC*MILER response.")


def route_miles(points: list[tuple[float, float]]) -> dict:
    """Miles for an ordered list of (lat, lon) stops.

    Returns {"miles", "source", "note"} where source is PCMILER_PRACTICAL, ESTIMATE_HAVERSINE, or
    ESTIMATE_HAVERSINE with a note explaining why the live call failed.
    """
    if len(points) < 2:
        return {"miles": 0.0, "source": "NONE", "note": "Need at least two stops."}
    key = os.getenv("PCMILER_API_KEY")
    if key:
        try:
            return {"miles": round(_pcmiler_miles(points, key), 1), "source": "PCMILER_PRACTICAL", "note": ""}
        except Exception as e:  # network, auth or format problem: fall back, but say so
            return {"miles": round(estimate_miles(points), 1), "source": "ESTIMATE_HAVERSINE",
                    "note": f"PC*MILER call failed ({type(e).__name__}); great-circle x {CIRCUITY} estimate shown."}
    return {"miles": round(estimate_miles(points), 1), "source": "ESTIMATE_HAVERSINE",
            "note": f"PCMILER_API_KEY not set; great-circle x {CIRCUITY} estimate, not PC*MILER miles."}
