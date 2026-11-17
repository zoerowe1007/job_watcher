"""Find out which employer job boards answer with JSON and no login.

This is a setup helper, not part of the daily pipeline. It tries the guesses in
tools/candidates.json and writes what worked to data/probe.json, so that
sources.json can be filled with boards that are known to respond.

    python tools/probe.py                    # candidates that have not answered yet
    python tools/probe.py walmart jpmorgan   # only these names
    python tools/probe.py --all              # everything again

(It reads a company's front page only to learn the Workday site name from the
redirect address. The pipeline itself never reads HTML.)
"""
import json
import re
import sys
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from watcher.fetchers import oracle_url  # noqa: E402
from watcher.http import USER_AGENT, request_json  # noqa: E402

WD_NUMBERS = [1, 5, 3, 12, 2, 501, 4, 103]
COMMON_SITES = ["External", "Careers", "ExternalCareers", "External_Career_Site", "jobs", "Jobs", "ExternalSite"]
LOCALE = re.compile(r"^[a-z]{2}(-[A-Za-z]{2})?$")


CTX = threading.local()


def note_error(url, exc):
    """Remember why a request failed, so a silent miss can be explained later."""
    errs = getattr(CTX, "errors", None)
    if errs is not None and len(errs) < 4:
        errs.append(f"{url.split('?')[0][:110]} -> {str(exc)[:90]}")


def once(url, data=None, timeout=20):
    try:
        return request_json(url, data=data, retries=1, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        note_error(url, exc)
        raise


WORKDAY_LINK = re.compile(
    r"https?://([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:wday/cxs/[a-z0-9-]+/)?(?:[a-z]{2}-[A-Za-z]{2}/)?([A-Za-z0-9_.-]+)", re.I)
ORACLE_LINK = re.compile(r"https?://([a-z0-9-]+\.fa(?:\.[a-z0-9]+)?\.oraclecloud\.com)(?:/hcmUI/CandidateExperience/[a-z]{2}(?:-[A-Z]{2})?)?(?:/sites/([A-Za-z0-9_]+))?", re.I)
SKIP_SITES = {"wday", "assets", "favicon.ico", "login", "en-us", "en"}


def scrape_links(url, timeout=25):
    """Read one public careers page and return the applicant-system addresses it mentions."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read(2_500_000).decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        note_error(url, exc)
        return []
    text = text.replace("\\/", "/").replace("&#x2F;", "/")
    found, seen = [], set()
    for tenant, wd, site in WORKDAY_LINK.findall(text):
        if site.lower() in SKIP_SITES:
            continue
        key = ("workday", tenant.lower(), wd.lower(), site)
        if key not in seen:
            seen.add(key)
            found.append({"ats": "workday", "host": f"{tenant}.{wd}.myworkdayjobs.com", "tenant": tenant, "site": site})
    for host, site in ORACLE_LINK.findall(text):
        key = ("oracle", host.lower(), site)
        if key not in seen:
            seen.add(key)
            found.append({"ats": "oracle", "host": host, "site": site or ""})
    return found[:8]


def sites_from_redirect(host, timeout=15):
    """Workday sends the bare host to /<locale>/<site>; read the site from the final address."""
    try:
        req = urllib.request.Request(f"https://{host}/", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            path = resp.geturl().split(host, 1)[-1].split("?")[0]
    except Exception:  # noqa: BLE001
        return []
    parts = [p for p in path.split("/") if p]
    if parts and LOCALE.match(parts[0]):
        parts = parts[1:]
    return [parts[0]] if parts else []


def try_workday(host, tenant, site, search=""):
    data = once(f"https://{host}/wday/cxs/{tenant}/{site}/jobs",
                {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": search})
    return int(data.get("total") or 0), [p.get("title") for p in (data.get("jobPostings") or [])[:3]]


def probe_workday(guess):
    found = []
    sites_extra = guess.get("sites", [])
    for tenant in guess["tenants"]:
        for wd in guess.get("wds", WD_NUMBERS):
            host = f"{tenant}.wd{wd}.myworkdayjobs.com"
            sites = list(dict.fromkeys(sites_extra + sites_from_redirect(host) + COMMON_SITES + [tenant]))
            for site in sites:
                try:
                    total, sample = try_workday(host, tenant, site)
                except Exception:  # noqa: BLE001
                    continue
                try:
                    analyst, _ = try_workday(host, tenant, site, "analyst")
                except Exception:  # noqa: BLE001
                    analyst = None
                found.append({"ats": "workday", "host": host, "tenant": tenant, "site": site,
                              "total": total, "total_with_search_analyst": analyst, "sample": sample})
                break
            if found:
                return found
    return found


def probe_oracle(guess):
    found = []
    for host in guess["hosts"]:
        for site in guess.get("sites", ["CX_1001", "CX_1", "CX_1002", "CX"]):
            url = oracle_url(host, site, 3, 0)
            try:
                block = (once(url).get("items") or [{}])[0]
            except Exception:  # noqa: BLE001
                continue
            if "TotalJobsCount" in block and (not int(block.get("TotalJobsCount") or 0) or block.get("requisitionList")):
                found.append({"ats": "oracle", "host": host, "site": site,
                              "total": int(block.get("TotalJobsCount") or 0),
                              "sample": [r.get("Title") for r in (block.get("requisitionList") or [])[:3]]})
                return found
    return found


def probe_simple(guess):
    ats = guess["ats"]
    out = []
    for slug in guess["slugs"]:
        try:
            if ats == "greenhouse":
                jobs = once(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs").get("jobs") or []
                key = "board"
            elif ats == "lever":
                jobs = once(f"https://api.lever.co/v0/postings/{slug}?mode=json")
                key = "company"
            elif ats == "ashby":
                jobs = once(f"https://api.ashbyhq.com/posting-api/job-board/{slug}").get("jobs") or []
                key = "board"
            else:
                data = once(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=3")
                jobs, key = data.get("content") or [], "company"
                if "totalFound" in data:
                    out.append({"ats": ats, key: slug, "total": int(data["totalFound"]), "sample": []})
                    return out
        except Exception:  # noqa: BLE001
            continue
        if jobs:
            out.append({"ats": ats, key: slug, "total": len(jobs), "sample": []})
            return out
    return out


def probe_exact(link):
    """Test one address that was read from a careers page."""
    if link["ats"] == "workday":
        total, sample = try_workday(link["host"], link["tenant"], link["site"])
        try:
            analyst, _ = try_workday(link["host"], link["tenant"], link["site"], "analyst")
        except Exception:  # noqa: BLE001
            analyst = None
        return [dict(link, total=total, total_with_search_analyst=analyst, sample=sample)]
    sites = ([link["site"]] if link.get("site") else []) + ["CX_1001", "CX_1", "CX_1002", "CX"]
    return probe_oracle({"hosts": [link["host"]], "sites": sites})


def probe_candidate(cand):
    CTX.errors = []
    working = []
    for link in cand.get("exact", []):
        try:
            working += probe_exact(link)
        except Exception:  # noqa: BLE001
            continue
        if working:
            break
    if not working:
        for page in cand.get("pages", []):
            for link in scrape_links(page):
                try:
                    working += probe_exact(link)
                except Exception:  # noqa: BLE001
                    continue
                if working:
                    break
            if working:
                break
    if not working:
        for guess in cand.get("guesses", []):
            ats = guess["ats"]
            if ats == "workday":
                working += probe_workday(guess)
            elif ats == "oracle":
                working += probe_oracle(guess)
            else:
                working += probe_simple(guess)
            if working:
                break
    out = {"name": cand["name"], "employer": cand["employer"], "found": working}
    if not working:
        out["errors"] = list(CTX.errors)
    return out


def main(argv):
    """With no names, retry only the candidates that have not answered yet (--all redoes everything)."""
    cands = json.loads((ROOT / "tools" / "candidates.json").read_text(encoding="utf-8"))["candidates"]
    out_path = ROOT / "data" / "probe.json"
    previous = {}
    if out_path.exists():
        try:
            previous = {r["name"]: r for r in json.loads(out_path.read_text(encoding="utf-8"))["results"]}
        except Exception:  # noqa: BLE001
            previous = {}
    redo_all = "--all" in argv
    names = [a for a in argv if not a.startswith("--")]
    if names:
        todo = [c for c in cands if c["name"] in names]
    elif redo_all:
        todo = cands
    else:
        todo = [c for c in cands if not previous.get(c["name"], {}).get("found")]
    with ThreadPoolExecutor(max_workers=6) as pool:
        fresh = {r["name"]: r for r in pool.map(probe_candidate, todo)}
    results = []
    for c in cands:
        results.append(fresh.get(c["name"]) or previous.get(c["name"]) or {"name": c["name"], "employer": c["employer"], "found": []})
    out = {"run_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "results": results}
    (ROOT / "data").mkdir(exist_ok=True)
    out_path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for r in results:
        if r["found"]:
            f = r["found"][0]
            where = f.get("host") or f.get("board") or f.get("company")
            print(f"OK    {r['name']:18} {f['ats']:10} {where} {f.get('site', '')}  total={f['total']}")
        else:
            print(f"--    {r['name']:18} nothing answered  {'; '.join(r.get('errors', []))[:200]}")
    print(f"{sum(1 for r in results if r['found'])}/{len(results)} candidates answered")


if __name__ == "__main__":
    main(sys.argv[1:])
