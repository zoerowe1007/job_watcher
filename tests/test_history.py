"""First-seen, last-seen, removed and re-opened logic of the history build."""
import hashlib

from helpers import put
from watcher import history
from watcher.common import COLUMNS


def rows_by_id(raw_dir):
    return {r["posting_id"]: r for r in history.build_rows(raw_dir)}


def test_first_day_marks_first_run_and_dates(tmp_path):
    put(tmp_path, "2026-11-01", "acme", ["a", "b"])
    r = rows_by_id(tmp_path)
    assert set(r) == {"acme:a", "acme:b"}
    for row in r.values():
        assert row["first_run"] is True
        assert row["first_seen"] == row["last_seen"] == "2026-11-01"
        assert row["status"] == "open" and row["removed_date"] == ""


def test_new_posting_later_is_not_first_run(tmp_path):
    put(tmp_path, "2026-11-01", "acme", ["a"])
    put(tmp_path, "2026-11-02", "acme", ["a", "c"])
    r = rows_by_id(tmp_path)
    assert r["acme:c"]["first_run"] is False
    assert r["acme:c"]["first_seen"] == "2026-11-02"
    assert r["acme:a"]["first_run"] is True
    assert r["acme:a"]["last_seen"] == "2026-11-02"


def test_last_seen_updates_for_every_listed_posting(tmp_path):
    for d in ("2026-11-01", "2026-11-02", "2026-11-03"):
        put(tmp_path, d, "acme", ["a"])
    assert rows_by_id(tmp_path)["acme:a"]["last_seen"] == "2026-11-03"


def test_removed_when_source_has_file_and_posting_missing(tmp_path):
    put(tmp_path, "2026-11-01", "acme", ["a", "b"])
    put(tmp_path, "2026-11-02", "acme", ["a"])
    r = rows_by_id(tmp_path)
    assert r["acme:b"]["status"] == "removed"
    assert r["acme:b"]["removed_date"] == "2026-11-02"
    assert r["acme:b"]["last_seen"] == "2026-11-01"
    assert r["acme:a"]["status"] == "open"


def test_removed_date_is_not_moved_by_later_days(tmp_path):
    put(tmp_path, "2026-11-01", "acme", ["a", "b"])
    put(tmp_path, "2026-11-02", "acme", ["a"])
    put(tmp_path, "2026-11-03", "acme", ["a"])
    assert rows_by_id(tmp_path)["acme:b"]["removed_date"] == "2026-11-02"


def test_failed_source_day_changes_nothing(tmp_path):
    put(tmp_path, "2026-11-01", "acme", ["a", "b"])
    put(tmp_path, "2026-11-01", "beta", ["x"])
    # 11-02: acme failed (no raw file), beta ran and lost x
    put(tmp_path, "2026-11-02", "beta", [])
    r = rows_by_id(tmp_path)
    assert r["acme:a"]["status"] == "open" and r["acme:b"]["status"] == "open"
    assert r["acme:a"]["last_seen"] == "2026-11-01"
    assert r["beta:x"]["status"] == "removed" and r["beta:x"]["removed_date"] == "2026-11-02"


def test_relisted_posting_opens_again(tmp_path):
    put(tmp_path, "2026-11-01", "acme", ["a", "b"])
    put(tmp_path, "2026-11-02", "acme", ["a"])
    put(tmp_path, "2026-11-04", "acme", ["a", "b"])
    b = rows_by_id(tmp_path)["acme:b"]
    assert b["status"] == "open"
    assert b["removed_date"] == ""
    assert b["first_seen"] == "2026-11-01"
    assert b["last_seen"] == "2026-11-04"
    assert b["first_run"] is True


def test_can_be_removed_again_after_relisting(tmp_path):
    put(tmp_path, "2026-11-01", "acme", ["a", "b"])
    put(tmp_path, "2026-11-02", "acme", ["a"])
    put(tmp_path, "2026-11-03", "acme", ["a", "b"])
    put(tmp_path, "2026-11-05", "acme", ["a"])
    b = rows_by_id(tmp_path)["acme:b"]
    assert b["status"] == "removed" and b["removed_date"] == "2026-11-05"
    assert b["first_seen"] == "2026-11-01"


def test_first_run_is_per_source(tmp_path):
    put(tmp_path, "2026-11-01", "acme", ["a"])
    put(tmp_path, "2026-11-03", "beta", ["x"])      # beta starts two days later
    put(tmp_path, "2026-11-04", "beta", ["x", "y"])
    r = rows_by_id(tmp_path)
    assert r["beta:x"]["first_run"] is True
    assert r["beta:x"]["first_seen"] == "2026-11-03"
    assert r["beta:y"]["first_run"] is False


def test_same_id_in_two_sources_stays_separate(tmp_path):
    put(tmp_path, "2026-11-01", "acme", ["1"])
    put(tmp_path, "2026-11-01", "beta", ["1"])
    assert set(rows_by_id(tmp_path)) == {"acme:1", "beta:1"}


def test_rows_sorted_by_posting_id(tmp_path):
    put(tmp_path, "2026-11-01", "beta", ["z", "a"])
    put(tmp_path, "2026-11-01", "acme", ["m"])
    ids = [r["posting_id"] for r in history.build_rows(tmp_path)]
    assert ids == sorted(ids)


def test_latest_listing_refreshes_title_and_updates_role(tmp_path):
    put(tmp_path, "2026-11-01", "acme", ["a"], titles={"a": "Store Associate"})
    put(tmp_path, "2026-11-02", "acme", ["a"], titles={"a": "Financial Analyst"})
    a = rows_by_id(tmp_path)["acme:a"]
    assert a["title"] == "Financial Analyst" and a["in_role"] is True


def test_empty_directory_gives_no_rows(tmp_path):
    assert history.build_rows(tmp_path / "missing") == []


def test_csv_layout(tmp_path):
    put(tmp_path, "2026-11-01", "acme", ["a"], titles={"a": "Data Analyst, \"Finance\""})
    out = tmp_path / "history.csv"
    history.build_history(tmp_path, out)
    text = out.read_text(encoding="utf-8")
    assert text.splitlines()[0] == ",".join(COLUMNS)
    back = history.read_csv(out)
    assert back[0]["title"] == 'Data Analyst, "Finance"'
    assert back[0]["in_role"] is True and back[0]["first_run"] is True
    assert back[0]["department"] == "" and back[0]["removed_date"] == ""
    assert ",true," in text  # lower-case booleans


def test_rebuild_is_identical_and_rule_change_applies_to_all_days(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    put(raw, "2026-11-01", "acme", ["a", "b"], titles={"a": "Data Analyst", "b": "Cashier"})
    put(raw, "2026-11-02", "acme", ["a", "b", "c"], titles={"a": "Data Analyst", "b": "Cashier", "c": "Credit Analyst"})
    out = tmp_path / "history.csv"
    history.build_history(raw, out)
    first = hashlib.sha256(out.read_bytes()).hexdigest()
    history.build_history(raw, out)
    assert hashlib.sha256(out.read_bytes()).hexdigest() == first
    # a changed rule changes every day's rows the next time the history is built
    monkeypatch.setattr(history, "in_role", lambda title: "Cashier" in title)
    history.build_history(raw, out)
    flags = {r["posting_id"]: r["in_role"] for r in history.read_csv(out)}
    assert flags == {"acme:a": False, "acme:b": True, "acme:c": False}
