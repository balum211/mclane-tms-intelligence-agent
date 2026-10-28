#!/usr/bin/env python3
"""Run the McLane delivery-signal tools from the command line and print JSON.

  signals.py otd [--days 28] [--group-by channel|dc|customer|carrier|week] [--channel RETAIL|RESTAURANT]
  signals.py dwell [--recent-days 21] [--baseline-days 56] [--group-by customer|location|dc|channel]
  signals.py geofence [--days 30] [--dc DC04]
  signals.py track LOAD_ID
  signals.py pcmiler LOAD_ID
  signals.py oor [--days 90] [--group-by driver|dc]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from tms_agent.tools import delivery, miles  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("otd")
    o.add_argument("--days", type=int, default=28)
    o.add_argument("--group-by", default="channel")
    o.add_argument("--channel", default="")
    d = sub.add_parser("dwell")
    d.add_argument("--recent-days", type=int, default=21)
    d.add_argument("--baseline-days", type=int, default=56)
    d.add_argument("--group-by", default="customer")
    g = sub.add_parser("geofence")
    g.add_argument("--days", type=int, default=30)
    g.add_argument("--dc", default="")
    sub.add_parser("track").add_argument("load_id")
    sub.add_parser("pcmiler").add_argument("load_id")
    r = sub.add_parser("oor")
    r.add_argument("--days", type=int, default=90)
    r.add_argument("--group-by", default="driver")
    a = ap.parse_args()

    if a.cmd == "otd":
        out = delivery.get_otd_scorecard(days=a.days, group_by=a.group_by, channel=a.channel)
    elif a.cmd == "dwell":
        out = delivery.get_dwell_time_changes(recent_days=a.recent_days, baseline_days=a.baseline_days,
                                              group_by=a.group_by)
    elif a.cmd == "geofence":
        out = delivery.get_geofence_compliance(days=a.days, dc_id=a.dc)
    elif a.cmd == "track":
        out = delivery.track_load(a.load_id)
    elif a.cmd == "pcmiler":
        out = miles.check_pcmiler_miles(a.load_id)
    else:
        out = miles.get_out_of_route_miles(days=a.days, group_by=a.group_by)
    print(json.dumps(out, indent=2, default=str))
    return 0 if out.get("status") != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
