"""Convert what each applicant tracking system (ATS) returns into the common
columns. Converters read only the raw file, never the network, so the history
can be rebuilt from data/raw alone.

A raw file is a dict:
    source, employer, ats, meta (ATS identifiers), fetched_at (UTC ISO),
    count, postings (the items exactly as the ATS returned them)
"""
import re
from datetime import datetime, timedelta, timezone

from .common import clean, make_posting


def _fetch_date(raw):
    return datetime.strptime(raw["fetched_at"][:10], "%Y-%m-%d").date()


# ---------------------------------------------------------------- Workday
_WD_DAYS = re.compile(r"posted\s+(\d+)\+?\s+days?\s+ago", re.IGNORECASE)


def workday_posted_date(text, fetched):
    """'Posted Today' / 'Posted 3 Days Ago' -> date. '30+' is open-ended: ''."""
    text = clean(text).lower()
    if not text:
        return ""
    if text == "posted today":
        return fetched.isoformat()
    if text == "posted yesterday":
        return (fetched - timedelta(days=1)).isoformat()
    m = _WD_DAYS.search(text)
    if m and "+" not in text:
        return (fetched - timedelta(days=int(m.group(1)))).isoformat()
    return ""


def convert_workday(raw):
    meta = raw["meta"]
    base = f"https://{meta['host']}/en-US/{meta['site']}"
    fetched = _fetch_date(raw)
    out = []
    for p in raw["postings"]:
        path = clean(p.get("externalPath"))
        bullets = [clean(b) for b in (p.get("bulletFields") or []) if clean(b)]
        sid = bullets[0] if bullets and " " not in bullets[0] and len(bullets[0]) <= 40 else path
        if not sid:
            continue
        out.append(make_posting(
            sid, p.get("title"), p.get("locationsText"), "",
            workday_posted_date(p.get("postedOn"), fetched),
            base + path if path else "",
        ))
    return out


# ----------------------------------------------------------------- Oracle
def convert_oracle(raw):
    meta = raw["meta"]
    out = []
    for p in raw["postings"]:
        sid = clean(p.get("Id"))
        if not sid:
            continue
        dept = p.get("Department") or p.get("JobFamily") or p.get("JobFunction") or ""
        out.append(make_posting(
            sid, p.get("Title"), p.get("PrimaryLocation"), dept,
            clean(p.get("PostedDate"))[:10],
            f"https://{meta['host']}/hcmUI/CandidateExperience/en/sites/{meta['site']}/job/{sid}",
        ))
    return out


# ------------------------------------------------------------- Greenhouse
def convert_greenhouse(raw):
    out = []
    for p in raw["postings"]:
        depts = ", ".join(clean(d.get("name")) for d in (p.get("departments") or []) if d.get("name"))
        out.append(make_posting(
            p.get("id"), p.get("title"), (p.get("location") or {}).get("name"), depts,
            clean(p.get("first_published"))[:10], p.get("absolute_url"),
        ))
    return [x for x in out if x["source_id"]]


# ------------------------------------------------------------------ Lever
def _ms_to_date(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return ""


def convert_lever(raw):
    out = []
    for p in raw["postings"]:
        cats = p.get("categories") or {}
        out.append(make_posting(
            p.get("id"), p.get("text"), cats.get("location"),
            cats.get("department") or cats.get("team"),
            _ms_to_date(p.get("createdAt")), p.get("hostedUrl"),
        ))
    return [x for x in out if x["source_id"]]


# ------------------------------------------------------------------ Ashby
def convert_ashby(raw):
    out = []
    for p in raw["postings"]:
        if p.get("isListed") is False:
            continue
        out.append(make_posting(
            p.get("id"), p.get("title"), p.get("location"),
            p.get("department") or p.get("team"),
            clean(p.get("publishedAt"))[:10], p.get("jobUrl"),
        ))
    return [x for x in out if x["source_id"]]


# --------------------------------------------------------- SmartRecruiters
def convert_smartrecruiters(raw):
    meta = raw["meta"]
    out = []
    for p in raw["postings"]:
        loc = p.get("location") or {}
        parts = [clean(loc.get("city")), clean(loc.get("region")).upper(), clean(loc.get("country")).upper()]
        sid = clean(p.get("id"))
        if not sid:
            continue
        out.append(make_posting(
            sid, p.get("name"), ", ".join(x for x in parts if x),
            (p.get("department") or {}).get("label"),
            clean(p.get("releasedDate"))[:10],
            f"https://jobs.smartrecruiters.com/{meta['company']}/{sid}",
        ))
    return out


CONVERTERS = {
    "workday": convert_workday,
    "oracle": convert_oracle,
    "greenhouse": convert_greenhouse,
    "lever": convert_lever,
    "ashby": convert_ashby,
    "smartrecruiters": convert_smartrecruiters,
}


def convert(raw):
    """Convert one raw file to common-column postings (duplicates by source_id dropped)."""
    seen, out = set(), []
    for p in CONVERTERS[raw["ats"]](raw):
        if p["source_id"] in seen:
            continue
        seen.add(p["source_id"])
        out.append(p)
    return out
