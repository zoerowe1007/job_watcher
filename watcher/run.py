"""The daily run:  python -m watcher.run

1. call every source, save each result as data/raw/<UTC date>/<source>.json.gz
   (a failed source writes no raw file; every result goes in the run log)
2. build data/history.csv from the raw files
3. write data/status.json
4. open the day's GitHub Issue and close the previous one
Committing is done by the workflow (.github/workflows/daily.yml).
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .adapters import convert
from .fetchers import fetch_source
from .history import build_history
from .http import request_json
from .rawstore import clear_day, list_days, read_raw, write_raw
from .status import build_status, update_run_log, write_status


def load_sources(path):
    sources = json.loads(Path(path).read_text(encoding="utf-8"))["sources"]
    names = [s["name"] for s in sources]
    if len(names) != len(set(names)):
        raise ValueError("duplicate source names in sources.json")
    return sources


def previous_count(raw_dir, today, name):
    """Posting count in the source's most recent raw file before today (None if there is none)."""
    for date, files in reversed(list(list_days(raw_dir).items())):
        if date < today and name in files:
            return read_raw(files[name]).get("count")
    return None


def run_sources(sources, raw_dir, now, http=request_json, pause=0.15, log=print):
    """Fetch every source; one failing never stops the others. Returns the result list."""
    today = now.strftime("%Y-%m-%d")
    clear_day(raw_dir, today)   # a second run on the same day replaces that day's raw files
    results = []
    for src in sources:
        name = src["name"]
        try:
            raw = fetch_source(src, http=http, now=now, pause=pause)
            if raw["count"] == 0 and (previous_count(raw_dir, today, name) or 0) > 0:
                raise RuntimeError("board returned no postings although it had some before; treated as a failure")
            write_raw(raw_dir, today, raw)
            results.append({"name": name, "ok": True, "count": len(convert(raw))})
            log(f"  ok    {name}: {results[-1]['count']} postings")
        except Exception as e:  # noqa: BLE001 - any failure is recorded, never raised
            msg = f"{type(e).__name__}: {e}"[:300]
            results.append({"name": name, "ok": False, "count": 0, "error": msg})
            log(f"  FAIL  {name}: {msg}")
    return results


def run(root=".", now=None, sources=None, http=request_json, pause=0.15, issue=True, log=print):
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    raw_dir = root / "data" / "raw"
    sources = sources if sources is not None else load_sources(root / "sources.json")
    log(f"Job Watcher run {today}: {len(sources)} sources")
    results = run_sources(sources, raw_dir, now, http=http, pause=pause, log=log)
    rows = build_history(raw_dir, root / "data" / "history.csv")
    status = build_status(rows, results, now, raw_dir)
    write_status(status, root / "data" / "status.json")
    update_run_log(root / "data" / "run_log.json", today, results)
    log(f"history: {len(rows)} postings; open {status['open']}, new {status['new_today']}, "
        f"removed {status['removed_today']}")
    if issue:
        try:
            from .issues import build_issue, publish
            new_rows = [r for r in rows if r["first_seen"] == today and not r["first_run"]]
            removed_rows = [r for r in rows if r["removed_date"] == today]
            repo = os.environ.get("GITHUB_REPOSITORY", "")
            site = f"https://{repo.split('/')[0]}.github.io/{repo.split('/')[1]}/" if "/" in repo else ""
            title, body = build_issue(today, new_rows, removed_rows, results, status, site)
            number = publish(title, body)
            log(f"issue #{number} '{title}' updated")
        except Exception as e:  # noqa: BLE001 - a failed issue must not fail the run
            log(f"issue step failed: {e}")
    return status


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run the daily job watcher.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--no-issue", action="store_true", help="skip the GitHub Issue step")
    args = ap.parse_args(argv)
    run(args.root, issue=not args.no_issue)
    return 0


if __name__ == "__main__":
    sys.exit(main())
