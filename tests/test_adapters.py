"""Conversion of each source type to the common columns."""
from watcher.adapters import convert, workday_posted_date
from watcher.common import BASE_FIELDS
from datetime import date


def raw(ats, postings, meta=None, fetched="2026-11-16T07:00:00+00:00"):
    return {"source": "x", "employer": "X", "ats": ats, "meta": meta or {},
            "fetched_at": fetched, "count": len(postings), "postings": postings}


def check_columns(rows):
    for r in rows:
        assert list(r.keys()) == BASE_FIELDS
        assert all(isinstance(v, str) for v in r.values())


def test_workday():
    r = raw("workday", [
        {"title": "Financial  Analyst II", "externalPath": "/job/Plano-TX/Financial-Analyst-II_R-100",
         "locationsText": "Plano, TX", "postedOn": "Posted 3 Days Ago", "bulletFields": ["R-100"]},
        {"title": "Store Manager", "externalPath": "/job/Dallas-TX/Store-Manager_R-101",
         "locationsText": "2 Locations", "postedOn": "Posted 30+ Days Ago", "bulletFields": ["Dallas, TX"]},
        {"title": "No path", "locationsText": "X"},
    ], {"host": "acme.wd5.myworkdayjobs.com", "site": "Ext"})
    rows = convert(r)
    check_columns(rows)
    assert len(rows) == 2
    a, b = rows
    assert a["source_id"] == "R-100"
    assert a["title"] == "Financial Analyst II"
    assert a["location"] == "Plano, TX"
    assert a["posted_date"] == "2026-11-13"
    assert a["url"] == "https://acme.wd5.myworkdayjobs.com/en-US/Ext/job/Plano-TX/Financial-Analyst-II_R-100"
    assert a["department"] == ""
    # a bullet field that is not an id falls back to the path; 30+ days has no date
    assert b["source_id"] == "/job/Dallas-TX/Store-Manager_R-101"
    assert b["posted_date"] == ""


def test_workday_posted_text():
    d = date(2026, 11, 16)
    assert workday_posted_date("Posted Today", d) == "2026-11-16"
    assert workday_posted_date("Posted Yesterday", d) == "2026-11-15"
    assert workday_posted_date("Posted 1 Day Ago", d) == "2026-11-15"
    assert workday_posted_date("Posted 30+ Days Ago", d) == ""
    assert workday_posted_date("", d) == ""
    assert workday_posted_date(None, d) == ""


def test_oracle():
    r = raw("oracle", [
        {"Id": "210123", "Title": "Data Analyst", "PostedDate": "2026-11-10",
         "PrimaryLocation": "Plano, TX, United States", "JobFamily": "Finance"},
        {"Id": "210124", "Title": "Credit Analyst", "PostedDate": "2026-11-11T00:00:00Z",
         "PrimaryLocation": "Dallas, TX, United States", "Department": "Risk"},
        {"Title": "No id"},
    ], {"host": "jpmc.fa.oraclecloud.com", "site": "CX_1001"})
    rows = convert(r)
    check_columns(rows)
    assert len(rows) == 2
    assert rows[0]["source_id"] == "210123"
    assert rows[0]["department"] == "Finance"
    assert rows[0]["url"] == "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210123"
    assert rows[1]["posted_date"] == "2026-11-11"
    assert rows[1]["department"] == "Risk"


def test_greenhouse():
    r = raw("greenhouse", [
        {"id": 4001, "title": "FP&A Analyst", "location": {"name": "Dallas, TX"},
         "absolute_url": "https://boards.greenhouse.io/acme/jobs/4001",
         "departments": [{"name": "Finance"}, {"name": "Strategy"}], "first_published": "2026-11-01T10:00:00-05:00"},
        {"id": 4002, "title": "Recruiter", "location": None, "absolute_url": "u"},
    ])
    rows = convert(r)
    check_columns(rows)
    assert rows[0]["source_id"] == "4001"
    assert rows[0]["department"] == "Finance, Strategy"
    assert rows[0]["posted_date"] == "2026-11-01"
    assert rows[1]["location"] == ""
    assert rows[1]["posted_date"] == ""


def test_lever():
    r = raw("lever", [
        {"id": "abc-1", "text": "Data Analyst", "categories": {"location": "Plano", "team": "Data"},
         "createdAt": 1762732800000, "hostedUrl": "https://jobs.lever.co/acme/abc-1"},
        {"id": "abc-2", "text": "Other", "categories": {}, "hostedUrl": "u"},
    ])
    rows = convert(r)
    check_columns(rows)
    assert rows[0]["posted_date"] == "2025-11-10"
    assert rows[0]["department"] == "Data"
    assert rows[1]["posted_date"] == ""


def test_ashby_skips_unlisted():
    r = raw("ashby", [
        {"id": "a1", "title": "BI Analyst", "location": "Dallas", "department": "Data",
         "publishedAt": "2026-11-02T15:00:00.000+00:00", "jobUrl": "https://jobs.ashbyhq.com/acme/a1"},
        {"id": "a2", "title": "Hidden", "isListed": False, "jobUrl": "u"},
    ])
    rows = convert(r)
    check_columns(rows)
    assert [x["source_id"] for x in rows] == ["a1"]
    assert rows[0]["posted_date"] == "2026-11-02"


def test_smartrecruiters():
    r = raw("smartrecruiters", [
        {"id": "7430", "name": "Supply Chain Analyst",
         "location": {"city": "Fort Worth", "region": "tx", "country": "us"},
         "department": {"label": "Logistics"}, "releasedDate": "2026-11-05T12:00:00.000Z"},
        {"name": "no id"},
    ], {"company": "Acme"})
    rows = convert(r)
    check_columns(rows)
    assert len(rows) == 1
    assert rows[0]["location"] == "Fort Worth, TX, US"
    assert rows[0]["department"] == "Logistics"
    assert rows[0]["url"] == "https://jobs.smartrecruiters.com/Acme/7430"


def test_duplicates_within_a_file_keep_the_first():
    r = raw("lever", [
        {"id": "z", "text": "First", "categories": {}, "hostedUrl": "u1"},
        {"id": "z", "text": "Second", "categories": {}, "hostedUrl": "u2"},
    ])
    rows = convert(r)
    assert len(rows) == 1 and rows[0]["title"] == "First"
