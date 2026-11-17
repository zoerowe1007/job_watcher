"""Paging, search-term and size-limit behaviour of the fetchers (no network)."""
import pytest

from watcher import fetchers
from watcher.fetchers import FetchError, fetch_oracle, fetch_source, fetch_workday


def workday_http(total, per_page=20, calls=None):
    def http(url, data=None, headers=None):
        calls.append((url, data))
        off, lim = data["offset"], data["limit"]
        items = [{"title": f"T{i}", "externalPath": f"/job/p{i}", "bulletFields": [f"R{i}"]}
                 for i in range(off, min(off + lim, total))]
        # Workday often reports the total only on the first page
        return {"total": total if off == 0 else 0, "jobPostings": items}
    return http


WD = {"name": "acme", "employer": "Acme", "ats": "workday", "host": "acme.wd5.myworkdayjobs.com",
      "tenant": "acme", "site": "Ext"}


def test_workday_pages_until_total():
    calls = []
    got = fetch_workday(WD, http=workday_http(45, calls=calls), pause=0)
    assert len(got) == 45
    assert [c[1]["offset"] for c in calls] == [0, 20, 40]
    assert calls[0][0] == "https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/Ext/jobs"
    assert calls[0][1]["searchText"] == ""


def test_workday_sends_search_term():
    calls = []
    fetch_workday({**WD, "search": "analyst"}, http=workday_http(5, calls=calls), pause=0)
    assert calls[0][1]["searchText"] == "analyst"


def test_workday_big_board_needs_search_term():
    with pytest.raises(FetchError, match="search"):
        fetch_workday(WD, http=workday_http(5001, calls=[]), pause=0)


def test_workday_big_board_ok_with_search_term():
    calls = []
    got = fetch_workday({**WD, "search": "analyst"}, http=workday_http(5001, calls=calls), pause=0)
    assert len(got) == 5001


def test_workday_stops_when_pages_repeat():
    def http(url, data=None, headers=None):
        return {"total": 1000, "jobPostings": [{"externalPath": "/same"}]}
    assert len(fetch_workday(WD, http=http, pause=0)) == 1


def oracle_http(total, calls):
    def http(url, data=None, headers=None):
        calls.append(url)
        off = int(url.split("offset%3D")[-1].split("&")[0].split(",")[0]) if "offset%3D" in url else \
            int(url.split("offset=")[1].split(",")[0].split("&")[0])
        items = [{"Id": str(i), "Title": f"T{i}"} for i in range(off, min(off + 25, total))]
        return {"items": [{"TotalJobsCount": total, "requisitionList": items}]}
    return http


OR = {"name": "jpm", "employer": "JPM", "ats": "oracle", "host": "jpmc.fa.oraclecloud.com", "site": "CX_1001"}


def test_oracle_pages_and_url():
    calls = []
    got = fetch_oracle(OR, http=oracle_http(60, calls), pause=0)
    assert len(got) == 60
    assert len(calls) == 3
    assert calls[0].startswith("https://jpmc.fa.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList.workLocation,")
    assert "finder=findReqs;siteNumber=CX_1001,limit=25,offset=0" in calls[0]
    assert "keyword" not in calls[0]


def test_oracle_asks_for_the_posting_list():
    calls = []
    fetch_oracle(OR, http=oracle_http(3, calls), pause=0)
    assert "expand=requisitionList" in calls[0]


def test_oracle_total_without_postings_is_a_failure():
    def http(url, data=None, headers=None):
        return {"items": [{"TotalJobsCount": 918}]}
    with pytest.raises(FetchError):
        fetch_oracle(OR, http=http, pause=0)


def test_workday_total_without_postings_is_a_failure():
    def http(url, data=None, headers=None):
        return {"total": 50, "jobPostings": []}
    with pytest.raises(FetchError):
        fetch_workday(WD, http=http, pause=0)


def test_oracle_search_term_in_url():
    calls = []
    fetch_oracle({**OR, "search": "analyst"}, http=oracle_http(3, calls), pause=0)
    assert "keyword=analyst" in calls[0]


def test_oracle_big_board_needs_search_term():
    with pytest.raises(FetchError):
        fetch_oracle(OR, http=oracle_http(9000, []), pause=0)


def test_fetch_source_builds_raw_file():
    from datetime import datetime, timezone
    now = datetime(2026, 11, 16, 7, 5, 9, 123, tzinfo=timezone.utc)
    raw = fetch_source({**WD, "search": "analyst"}, http=workday_http(3, calls=[]), now=now, pause=0)
    assert raw["source"] == "acme" and raw["ats"] == "workday" and raw["count"] == 3
    assert raw["fetched_at"] == "2026-11-16T07:05:09+00:00"
    assert raw["meta"]["host"] == "acme.wd5.myworkdayjobs.com"
    assert raw["meta"]["search"] == "analyst"
    assert len(raw["postings"]) == 3


def test_one_call_boards():
    gh = fetchers.fetch_greenhouse({"board": "acme"}, http=lambda url, **k: {"jobs": [{"id": 1}]})
    assert gh == [{"id": 1}]
    lv = fetchers.fetch_lever({"company": "acme"}, http=lambda url, **k: [{"id": "a"}])
    assert lv == [{"id": "a"}]
    ab = fetchers.fetch_ashby({"board": "acme"}, http=lambda url, **k: {"jobs": [{"id": "x"}]})
    assert ab == [{"id": "x"}]


def test_smartrecruiters_pages():
    def http(url, **k):
        off = int(url.split("offset=")[1].split("&")[0])
        items = [{"id": str(i)} for i in range(off, min(off + 100, 230))]
        return {"totalFound": 230, "content": items}
    got = fetchers.fetch_smartrecruiters({"company": "Acme"}, http=http, pause=0)
    assert len(got) == 230


def test_unknown_ats_fails():
    with pytest.raises(FetchError):
        fetch_source({"name": "x", "employer": "X", "ats": "nope"})
