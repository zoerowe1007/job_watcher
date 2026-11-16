"""The daily run: failed sources, same-day reruns, status, issue text."""
import json
from datetime import datetime, timezone

import pytest

from watcher import run as runmod
from watcher.history import read_csv
from watcher.issues import build_issue
from watcher.rawstore import list_days

SRC_A = {"name": "acme", "employer": "Acme", "ats": "lever", "company": "acme"}
SRC_B = {"name": "beta", "employer": "Beta", "ats": "greenhouse", "board": "beta"}


def fake_http(boards, fail=()):
    """boards: {url fragment: payload}"""
    def http(url, data=None, headers=None):
        for frag in fail:
            if frag in url:
                raise RuntimeError("boom")
        for frag, payload in boards.items():
            if frag in url:
                return payload
        raise RuntimeError("no such board")
    return http


def lever(ids):
    return [{"id": i, "text": f"Data Analyst {i}", "categories": {"location": "Plano"},
             "hostedUrl": f"https://x/{i}", "createdAt": 1762732800000} for i in ids]


def gh(ids):
    return {"jobs": [{"id": i, "title": f"Job {i}", "location": {"name": "Dallas"},
                      "absolute_url": f"https://y/{i}"} for i in ids]}


def at(day, hour=7):
    return datetime(2026, 11, day, hour, 0, 5, tzinfo=timezone.utc)


def do_run(root, day, http, hour=7):
    return runmod.run(root, now=at(day, hour), sources=[SRC_A, SRC_B], http=http, pause=0,
                      issue=False, log=lambda *_: None)


def test_failed_source_writes_no_raw_file_and_run_still_finishes(tmp_path):
    http = fake_http({"api.lever.co": lever(["1", "2"])}, fail=["greenhouse"])
    status = do_run(tmp_path, 1, http)
    files = list_days(tmp_path / "data" / "raw")["2026-11-01"]
    assert list(files) == ["acme"]
    by_name = {s["name"]: s for s in status["sources"]}
    assert by_name["acme"] == {"name": "acme", "ok": True, "count": 2}
    assert by_name["beta"]["ok"] is False and by_name["beta"]["count"] == 0
    assert "boom" in by_name["beta"]["error"]
    assert (tmp_path / "data" / "history.csv").exists()
    log = json.loads((tmp_path / "data" / "run_log.json").read_text())
    assert [s["ok"] for s in log["2026-11-01"]] == [True, False]


def test_status_fields(tmp_path):
    do_run(tmp_path, 1, fake_http({"api.lever.co": lever(["1", "2"]), "greenhouse": gh(["a"])}))
    status = do_run(tmp_path, 2, fake_http({"api.lever.co": lever(["1", "3"]), "greenhouse": gh(["a"])}))
    assert status["run_time"] == "2026-11-02T07:00:05Z"
    assert status["first_run_date"] == "2026-11-01"
    assert status["days_with_success"] == 2
    assert status["open"] == 3          # acme 1, 3 and beta a
    assert status["new_today"] == 1     # acme 3 (first-run postings are not new)
    assert status["removed_today"] == 1  # acme 2
    assert set(status) == {"run_time", "first_run_date", "days_with_success", "open",
                           "new_today", "removed_today", "sources"}
    on_disk = json.loads((tmp_path / "data" / "status.json").read_text())
    assert on_disk == status


def test_first_run_postings_are_not_new(tmp_path):
    status = do_run(tmp_path, 1, fake_http({"api.lever.co": lever(["1", "2"]), "greenhouse": gh(["a"])}))
    assert status["new_today"] == 0 and status["open"] == 3


def test_same_day_rerun_replaces_the_day(tmp_path):
    do_run(tmp_path, 1, fake_http({"api.lever.co": lever(["1", "2"]), "greenhouse": gh(["a"])}), hour=7)
    do_run(tmp_path, 2, fake_http({"api.lever.co": lever(["1", "2"]), "greenhouse": gh(["a"])}), hour=7)
    s1 = do_run(tmp_path, 2, fake_http({"api.lever.co": lever(["1"]), "greenhouse": gh(["a"])}), hour=19)
    assert s1["days_with_success"] == 2                      # the day counts once
    assert s1["removed_today"] == 1
    rows = {r["posting_id"]: r for r in read_csv(tmp_path / "data" / "history.csv")}
    assert rows["acme:2"]["removed_date"] == "2026-11-02"
    assert len(list_days(tmp_path / "data" / "raw")) == 2
    # the rerun is the only record for that day: a source that fails on the rerun has no file
    do_run(tmp_path, 2, fake_http({"api.lever.co": lever(["1"])}, fail=["greenhouse"]), hour=22)
    assert list(list_days(tmp_path / "data" / "raw")["2026-11-02"]) == ["acme"]


def test_empty_board_after_a_nonempty_day_is_a_failure(tmp_path):
    do_run(tmp_path, 1, fake_http({"api.lever.co": lever(["1", "2"]), "greenhouse": gh(["a"])}))
    s = do_run(tmp_path, 2, fake_http({"api.lever.co": [], "greenhouse": gh(["a"])}))
    acme = next(x for x in s["sources"] if x["name"] == "acme")
    assert acme["ok"] is False
    assert s["removed_today"] == 0                      # nothing was wrongly marked removed
    rows = {r["posting_id"]: r for r in read_csv(tmp_path / "data" / "history.csv")}
    assert rows["acme:1"]["status"] == "open"


def test_all_sources_failing_still_finishes(tmp_path):
    s = do_run(tmp_path, 1, fake_http({}, fail=["lever", "greenhouse"]))
    assert all(not x["ok"] for x in s["sources"])
    assert s["days_with_success"] == 0 and s["first_run_date"] == ""


def test_duplicate_source_names_rejected(tmp_path):
    p = tmp_path / "sources.json"
    p.write_text(json.dumps({"sources": [SRC_A, SRC_A]}))
    with pytest.raises(ValueError):
        runmod.load_sources(p)


def test_issue_text(tmp_path):
    rows = [
        {"employer": "Acme", "title": "Data Analyst", "location": "Plano", "url": "https://x/1",
         "in_role": True, "source_id": "1"},
        {"employer": "Acme", "title": "Cashier", "location": "Plano", "url": "https://x/2",
         "in_role": False, "source_id": "2"},
    ]
    status = {"run_time": "2026-11-02T07:00:05Z", "open": 5, "new_today": 2, "removed_today": 0,
              "first_run_date": "2026-11-01"}
    results = [{"name": "acme", "ok": True, "count": 3}, {"name": "beta", "ok": False, "count": 0, "error": "boom"}]
    title, body = build_issue("2026-11-02", rows, [], results, status, "https://example.github.io/job_watcher/")
    assert title == "2026-11-02"
    assert "## New postings (2)" in body and "[Data Analyst](https://x/1)" in body
    assert "## Removed postings (0)" in body and "None." in body
    assert "beta: boom" in body
    assert body.index("Data Analyst") < body.index("Cashier")   # in-role first


def test_issue_body_is_trimmed_when_huge():
    rows = [{"employer": "Acme", "title": f"Job {i} " + "x" * 80, "location": "Plano",
             "url": f"https://x/{i}", "in_role": False, "source_id": str(i)} for i in range(2000)]
    status = {"run_time": "t", "open": 1, "new_today": 2000, "removed_today": 0, "first_run_date": "2026-01-01"}
    _, body = build_issue("2026-11-02", rows, [], [], status)
    assert len(body) < 65000 and "…and" in body
