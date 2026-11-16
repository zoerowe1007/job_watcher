"""Shared definitions: the common columns and small helpers."""
import re

# Columns of data/history.csv, in order.
COLUMNS = [
    "posting_id", "source", "source_id", "employer", "title", "location",
    "department", "posted_date", "url", "in_role", "first_run",
    "first_seen", "last_seen", "status", "removed_date",
]

# Columns every ATS converter must fill (empty string when the source has none).
BASE_FIELDS = ["source_id", "title", "location", "department", "posted_date", "url"]

_WS = re.compile(r"\s+")


def clean(value):
    """Return value as a single-line, trimmed string ('' for None)."""
    if value is None:
        return ""
    return _WS.sub(" ", str(value)).strip()


def make_posting(source_id, title, location="", department="", posted_date="", url=""):
    """One posting in the common columns (before source/employer are added)."""
    return {
        "source_id": clean(source_id),
        "title": clean(title),
        "location": clean(location),
        "department": clean(department),
        "posted_date": clean(posted_date),
        "url": clean(url),
    }
