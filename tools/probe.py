"""Find out which employer job boards answer with JSON and no login.

This is a setup helper, not part of the daily pipeline. It tries the guesses in
tools/candidates.json and writes what worked to data/probe.json, so that
sources.json can be filled with boards that are known to respond.

    python tools/probe.py                 # all candidates
    python tools/probe.py walmart jpmorgan   # only these names

(It reads a company's front page only to learn the Workday site name from the
redirect address. The pipeline itself never reads HTML.)
"""
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from watcher.http import USER_AGENT, request_json  # noqa: E402

WD_NUMBERS = [1, 5, 3, 12, 2, 501, 4, 103]
COMMON_SITES = ["External", "Careers", "ExternalCareers", "External_Career_Site", "jobs", "Jobs", "ExternalSite"]
LOCALE = re.compile(r"^[a-z]{2}(-[A-Za-z]{2})?$")


def once(url, data=None, timeout=20):
    return request_json(url, data=data, retries=1, timeout=timeout)


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
            url = (f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
                   f"?onlyData=true&finder=findReqs;siteNumber={site},limit=3,offset=0")
            try:
                block = (once(url).get("items") or [{}])[0]
            except Exception:  # noqa: BLE001
                continue
            if "TotalJobsCount" in block:
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


def probe_candidate(cand):
    working = []
    for guess in cand["guesses"]:
        ats = guess["ats"]
        if ats == "workday":
            working += probe_workday(guess)
        elif ats == "oracle":
            working += probe_oracle(guess)
        else:
            working += probe_simple(guess)
        if working:
            break
    return {"name": cand["name"], "employer": cand["employer"], "found": working}


def main(argv):
    cands = json.loads((ROOT / "tools" / "candidates.json").read_text(encoding="utf-8"))["candidates"]
    if argv:
        cands = [c for c in cands if c["name"] in argv]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(probe_candidate, cands))
    out = {"run_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "results": results}
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "probe.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for r in results:
        if r["found"]:
            f = r["found"][0]
            where = f.get("host") or f.get("board") or f.get("company")
            print(f"OK    {r['name']:18} {f['ats']:10} {where} {f.get('site', '')}  total={f['total']}")
        else:
            print(f"--    {r['name']:18} nothing answered")
    print(f"{sum(1 for r in results if r['found'])}/{len(results)} candidates answered")


if __name__ == "__main__":
    main(sys.argv[1:])
