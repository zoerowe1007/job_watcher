"""Call each applicant tracking system's public JSON endpoint (no login).

Every fetcher returns a raw-file dict (see adapters.py). Boards with more than
MAX_POSTINGS postings must be requested with a search term (source["search"]);
otherwise the source fails with a message saying so.
"""
import time
from datetime import datetime, timezone
from urllib.parse import quote

from .http import request_json

MAX_POSTINGS = 5000
PAUSE = 0.15  # polite pause between page requests, in seconds


class FetchError(Exception):
    pass


def _check_size(total, source):
    if total > MAX_POSTINGS and not source.get("search"):
        raise FetchError(
            f"board lists {total} postings (> {MAX_POSTINGS}); set a 'search' term for this source")


# ---------------------------------------------------------------- Workday
def fetch_workday(source, http=request_json, pause=PAUSE):
    host, tenant, site = source["host"], source["tenant"], source["site"]
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    search = source.get("search") or ""
    limit, offset, total = 20, 0, 0
    postings, seen = [], set()
    for _ in range(600):
        data = http(url, data={"appliedFacets": {}, "limit": limit, "offset": offset, "searchText": search})
        items = data.get("jobPostings") or []
        if offset == 0:
            total = int(data.get("total") or 0)
            _check_size(total, source)
        added = 0
        for it in items:
            key = it.get("externalPath") or repr(sorted(it.items()))
            if key not in seen:
                seen.add(key)
                postings.append(it)
                added += 1
        offset += limit
        if not items or added == 0 or (total and offset >= total):
            break
        pause and time.sleep(pause)
    return postings


# ----------------------------------------------------------------- Oracle
def fetch_oracle(source, http=request_json, pause=PAUSE):
    host, site = source["host"], source["site"]
    search = source.get("search") or ""
    limit, offset, total = 25, 0, 0
    postings, seen = [], set()
    for _ in range(600):
        finder = f"findReqs;siteNumber={site},limit={limit},offset={offset},sortBy=POSTING_DATES_DESC"
        if search:
            finder += f",keyword={search}"
        url = (f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
               f"?onlyData=true&finder={quote(finder, safe=';,=')}")
        data = http(url)
        block = (data.get("items") or [{}])[0]
        items = block.get("requisitionList") or []
        if offset == 0:
            total = int(block.get("TotalJobsCount") or 0)
            _check_size(total, source)
        added = 0
        for it in items:
            key = it.get("Id")
            if key not in seen:
                seen.add(key)
                postings.append(it)
                added += 1
        offset += limit
        if not items or added == 0 or (total and offset >= total):
            break
        pause and time.sleep(pause)
    return postings


# --------------------------------------------------------- one-call boards
def fetch_greenhouse(source, http=request_json, pause=PAUSE):
    data = http(f"https://boards-api.greenhouse.io/v1/boards/{source['board']}/jobs")
    return data.get("jobs") or []


def fetch_lever(source, http=request_json, pause=PAUSE):
    host = "api.eu.lever.co" if source.get("region") == "eu" else "api.lever.co"
    data = http(f"https://{host}/v0/postings/{source['company']}?mode=json")
    return data if isinstance(data, list) else []


def fetch_ashby(source, http=request_json, pause=PAUSE):
    data = http(f"https://api.ashbyhq.com/posting-api/job-board/{source['board']}")
    return data.get("jobs") or []


def fetch_smartrecruiters(source, http=request_json, pause=PAUSE):
    postings, offset, limit = [], 0, 100
    for _ in range(100):
        url = (f"https://api.smartrecruiters.com/v1/companies/{source['company']}/postings"
               f"?limit={limit}&offset={offset}")
        if source.get("search"):
            url += f"&q={quote(source['search'])}"
        data = http(url)
        items = data.get("content") or []
        if offset == 0:
            _check_size(int(data.get("totalFound") or 0), source)
        postings.extend(items)
        offset += limit
        if not items or offset >= int(data.get("totalFound") or 0):
            break
        pause and time.sleep(pause)
    return postings


FETCHERS = {
    "workday": fetch_workday,
    "oracle": fetch_oracle,
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "smartrecruiters": fetch_smartrecruiters,
}

# Which keys of a source entry identify the board (stored in the raw file so the
# history can be built from the raw files alone).
META_KEYS = ("host", "tenant", "site", "board", "company", "region", "search")


def fetch_source(source, http=request_json, now=None, pause=PAUSE):
    """Fetch one source and return its raw-file dict. Raises on any failure."""
    ats = source["ats"]
    if ats not in FETCHERS:
        raise FetchError(f"unknown ATS '{ats}'")
    now = now or datetime.now(timezone.utc)
    postings = FETCHERS[ats](source, http=http, pause=pause)
    return {
        "source": source["name"],
        "employer": source["employer"],
        "ats": ats,
        "meta": {k: source[k] for k in META_KEYS if k in source},
        "fetched_at": now.replace(microsecond=0).isoformat(),
        "count": len(postings),
        "postings": postings,
    }
