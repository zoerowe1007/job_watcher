"""Build data/history.csv from the raw files alone.

    python -m watcher.history            # rebuild data/history.csv from data/raw

The build is a pure function of the raw files and the title rule: running it
again gives the same file, and a change to the title rule applies to every day.
"""
import argparse
import csv
from pathlib import Path

from .adapters import convert
from .common import COLUMNS
from .rawstore import list_days, read_raw
from .titlerule import in_role

# Fields refreshed from the newest listing of a posting.
_REFRESH = ("employer", "title", "location", "department", "posted_date", "url")


def build_rows(raw_dir):
    """Walk the raw files day by day and return the history rows sorted by posting_id."""
    state = {}            # posting_id -> row dict
    by_source = {}        # source -> set of posting_ids ever seen (to find open ones)
    seen_sources = set()  # sources that already had a raw file
    for date, files in list_days(raw_dir).items():
        for source, path in files.items():
            raw = read_raw(path)
            first_file = source not in seen_sources
            seen_sources.add(source)
            listed = set()
            for p in convert(raw):
                pid = f"{source}:{p['source_id']}"
                listed.add(pid)
                row = state.get(pid)
                if row is None:
                    row = state[pid] = {
                        "posting_id": pid, "source": source, "source_id": p["source_id"],
                        "first_run": first_file, "first_seen": date,
                        "status": "open", "removed_date": "",
                    }
                    by_source.setdefault(source, set()).add(pid)
                row["employer"] = raw["employer"]
                for k in ("title", "location", "department", "posted_date", "url"):
                    row[k] = p[k]
                row["last_seen"] = date
                if row["status"] == "removed":          # listed again: open again
                    row["status"] = "open"
                    row["removed_date"] = ""
            for pid in by_source.get(source, ()):
                row = state[pid]
                if row["status"] == "open" and pid not in listed:
                    row["status"] = "removed"
                    row["removed_date"] = date
    rows = []
    for pid in sorted(state):
        r = state[pid]
        r["in_role"] = in_role(r["title"])
        rows.append(r)
    return rows


def _cell(v):
    if v is True:
        return "true"
    if v is False:
        return "false"
    return v


def write_csv(rows, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(COLUMNS)
        for r in rows:
            w.writerow([_cell(r[c]) for c in COLUMNS])


def read_csv(path):
    """Read history.csv back into dicts (booleans as bool)."""
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["in_role"] = r["in_role"] == "true"
        r["first_run"] = r["first_run"] == "true"
    return rows


def build_history(raw_dir="data/raw", out="data/history.csv"):
    rows = build_rows(raw_dir)
    write_csv(rows, out)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rebuild data/history.csv from data/raw.")
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--out", default="data/history.csv")
    args = ap.parse_args(argv)
    rows = build_history(args.raw, args.out)
    print(f"wrote {args.out}: {len(rows)} postings")


if __name__ == "__main__":
    main()
