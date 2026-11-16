"""data/status.json: a description of the latest run."""
import json
from pathlib import Path

from .rawstore import list_days


def build_status(rows, results, now, raw_dir):
    """Status for the run at `now` (UTC datetime).

    rows     history rows (after the build)
    results  [{name, ok, count[, error]}] one per source, from this run
    """
    today = now.strftime("%Y-%m-%d")
    days = list_days(raw_dir)
    return {
        "run_time": now.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "first_run_date": min(days) if days else "",
        "days_with_success": len(days),
        "open": sum(1 for r in rows if r["status"] == "open"),
        "new_today": sum(1 for r in rows if r["first_seen"] == today and not r["first_run"]),
        "removed_today": sum(1 for r in rows if r["removed_date"] == today),
        "sources": [
            {"name": s["name"], "ok": bool(s["ok"]), "count": int(s["count"]),
             **({"error": s["error"]} if s.get("error") else {})}
            for s in results
        ],
    }


def write_status(status, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def update_run_log(path, date, results):
    """Keep every day's per-source outcome (failures leave no raw file, so record them here).
    A second run on the same day replaces that day's entry."""
    path = Path(path)
    log = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    log[date] = results
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(log.items())), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
