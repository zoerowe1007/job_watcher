"""Python reference for the Market page numbers (assets/market-calc.js).

The page computes these in the browser from data/history.csv. This module does
the same arithmetic in Python so the tests can check that the two agree.
"""
from datetime import date, timedelta
from statistics import median


def _d(s):
    return date.fromisoformat(s)


def _tally(items):
    counts = {}
    for k in items:
        counts[k] = counts.get(k, 0) + 1
    return sorted(([k, v] for k, v in counts.items()), key=lambda kv: (-kv[1], kv[0]))


def compute(rows):
    """rows: history rows (in_role / first_run as bool)."""
    out = {"lastRun": None, "firstDate": None, "days": [], "newAll": [], "newRole": [], "removed": [],
           "openByEmployer": [], "daysOpen": [], "medianDaysOpen": None,
           "share7": {"num": 0, "den": 0, "share": None}, "topLocations": [], "openCount": 0}
    if not rows:
        return out
    last = max(d for r in rows for d in (r["first_seen"], r["last_seen"], r["removed_date"]) if d)
    first = min(r["first_seen"] for r in rows)
    out["lastRun"], out["firstDate"] = last, first
    n = (_d(last) - _d(first)).days + 1
    out["days"] = [(_d(first) + timedelta(days=i)).isoformat() for i in range(n)]
    idx = {d: i for i, d in enumerate(out["days"])}
    out["newAll"], out["newRole"], out["removed"] = [0] * n, [0] * n, [0] * n
    for r in rows:
        if not r["first_run"]:
            out["newAll"][idx[r["first_seen"]]] += 1
            if r["in_role"]:
                out["newRole"][idx[r["first_seen"]]] += 1
        if r["removed_date"]:
            out["removed"][idx[r["removed_date"]]] += 1
    open_rows = [r for r in rows if r["status"] == "open"]
    out["openCount"] = len(open_rows)
    out["openByEmployer"] = _tally(r["employer"] for r in open_rows)
    out["topLocations"] = _tally(r["location"] or "(not listed)" for r in open_rows)[:10]
    out["daysOpen"] = [(_d(r["removed_date"]) - _d(r["first_seen"])).days
                       for r in rows if not r["first_run"] and r["removed_date"]]
    out["medianDaysOpen"] = median(out["daysOpen"]) if out["daysOpen"] else None
    for r in rows:
        if r["first_run"] or (_d(last) - _d(r["first_seen"])).days < 7:
            continue
        out["share7"]["den"] += 1
        if r["removed_date"] and (_d(r["removed_date"]) - _d(r["first_seen"])).days <= 7:
            out["share7"]["num"] += 1
    if out["share7"]["den"]:
        out["share7"]["share"] = out["share7"]["num"] / out["share7"]["den"]
    return out
