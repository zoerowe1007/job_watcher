"""Market numbers: definitions checked by hand, and the Python reference equals the saved fixture."""
import json
from pathlib import Path

from watcher import history, market

FIX = Path(__file__).parent / "fixtures"


def row(pid, first, removed="", first_run=False, in_role=False, status=None, employer="Acme",
        location="Plano, TX", last=None):
    return {"posting_id": pid, "source": "acme", "source_id": pid, "employer": employer, "title": "t",
            "location": location, "department": "", "posted_date": "", "url": "", "in_role": in_role,
            "first_run": first_run, "first_seen": first, "last_seen": last or removed or "2026-11-20",
            "status": status or ("removed" if removed else "open"), "removed_date": removed}


def test_definitions_by_hand():
    rows = [
        row("a", "2026-11-10", first_run=True),                                   # baseline, open
        row("b", "2026-11-10", removed="2026-11-12", first_run=True),             # baseline, removed
        row("c", "2026-11-11", removed="2026-11-14", in_role=True),               # 3 days open
        row("d", "2026-11-11", removed="2026-11-19"),                             # 8 days open
        row("e", "2026-11-12", in_role=True, employer="Beta", location="Dallas, TX"),   # still open
        row("f", "2026-11-18", removed="2026-11-20"),                             # 2 days; too recent for share
    ]
    m = market.compute(rows)
    assert m["lastRun"] == "2026-11-20" and m["firstDate"] == "2026-11-10"
    assert m["days"][0] == "2026-11-10" and len(m["days"]) == 11
    i = {d: k for k, d in enumerate(m["days"])}
    # new per day leaves out the first-run postings a and b
    assert m["newAll"][i["2026-11-10"]] == 0
    assert m["newAll"][i["2026-11-11"]] == 2 and m["newRole"][i["2026-11-11"]] == 1
    assert m["newAll"][i["2026-11-12"]] == 1 and m["newRole"][i["2026-11-12"]] == 1
    assert sum(m["newAll"]) == 4 and sum(m["newRole"]) == 2
    # removed per day counts every removed posting, first-run ones included
    assert m["removed"][i["2026-11-12"]] == 1 and m["removed"][i["2026-11-14"]] == 1
    assert m["removed"][i["2026-11-19"]] == 1 and m["removed"][i["2026-11-20"]] == 1
    assert sum(m["removed"]) == 4
    # open per employer / top locations
    assert m["openByEmployer"] == [["Acme", 1], ["Beta", 1]]
    assert m["topLocations"] == [["Dallas, TX", 1], ["Plano, TX", 1]]
    # days open: removed, not first-run: c=3, d=8, f=2 -> median 3
    assert sorted(m["daysOpen"]) == [2, 3, 8] and m["medianDaysOpen"] == 3
    # share removed within 7 days: not first-run and first seen >= 7 days before 11-20 -> c (11-11), d (11-11), e (11-12)
    assert m["share7"] == {"num": 1, "den": 3, "share": 1 / 3}


def test_median_of_even_count():
    rows = [row("a", "2026-11-01", removed="2026-11-03"), row("b", "2026-11-01", removed="2026-11-05")]
    assert market.compute(rows)["medianDaysOpen"] == 3


def test_not_enough_data():
    rows = [row("a", "2026-11-10", first_run=True)]
    m = market.compute(rows)
    assert m["medianDaysOpen"] is None and m["share7"]["share"] is None
    assert market.compute([])["lastRun"] is None


def test_exactly_seven_days_counts_as_within_seven():
    rows = [row("a", "2026-11-01", removed="2026-11-08"), row("b", "2026-11-01", removed="2026-11-09"),
            row("z", "2026-11-15", last="2026-11-15")]
    s = market.compute(rows)["share7"]
    assert s["den"] == 2 and s["num"] == 1


def test_python_reference_matches_saved_fixture():
    rows = history.read_csv(FIX / "market_history.csv")
    expected = json.loads((FIX / "market_expected.json").read_text())
    assert json.loads(json.dumps(market.compute(rows))) == expected
