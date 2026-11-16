"""Read and write the compressed raw files: data/raw/<UTC date>/<source>.json.gz"""
import gzip
import json
import re
import shutil
from pathlib import Path

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def raw_path(raw_dir, date, source):
    return Path(raw_dir) / date / f"{source}.json.gz"


def write_raw(raw_dir, date, raw):
    """Write one raw file (gzip with a fixed timestamp so equal data gives equal bytes)."""
    path = raw_path(raw_dir, date, raw["source"])
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with open(path, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0, compresslevel=9) as gz:
            gz.write(data)
    return path


def read_raw(path):
    with gzip.open(path, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def clear_day(raw_dir, date):
    """Remove one day's raw files (a second run on the same day replaces them)."""
    shutil.rmtree(Path(raw_dir) / date, ignore_errors=True)


def list_days(raw_dir):
    """{date: {source: path}} for every raw file, dates in ascending order."""
    root = Path(raw_dir)
    days = {}
    if not root.is_dir():
        return days
    for day_dir in sorted(root.iterdir()):
        if not (day_dir.is_dir() and DATE_RE.match(day_dir.name)):
            continue
        files = {p.name[: -len(".json.gz")]: p for p in sorted(day_dir.glob("*.json.gz"))}
        if files:
            days[day_dir.name] = files
    return days
