"""Regenerate tests/fixtures/market_history.csv and market_expected.json.

    python tests/make_market_fixture.py

Simulates 30 days of three job boards (with churn, a failed day, a source that
starts late and relisted postings), builds the history the normal way, and
records the Python reference numbers. tests/market_check.mjs checks that the
page's JavaScript gets the same numbers from the same CSV.
"""
import json
import random
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from helpers import put  # noqa: E402
from watcher import history, market  # noqa: E402

TITLES = ["Financial Analyst", "Data Analyst", "Store Associate", "Credit Analyst", "Truck Driver",
          "Supply Chain Analyst", "Nurse", "BI Developer, \"Reporting\""]


def main():
    rng = random.Random(42)
    start = date(2026, 10, 1)
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw"
        live = {"acme": set(range(40)), "beta": set(range(100, 130)), "gamma": set(range(200, 220))}
        nxt = {"acme": 40, "beta": 130, "gamma": 220}
        for day in range(30):
            d = (start + timedelta(days=day)).isoformat()
            for s in live:
                if s == "gamma" and day < 9:
                    continue                       # gamma starts late
                if s == "beta" and day in (12, 13):
                    continue                       # beta fails two days
                live[s] = {i for i in live[s] if rng.random() > 0.08}
                for _ in range(rng.randint(0, 6)):
                    live[s].add(nxt[s]); nxt[s] += 1
                if rng.random() < 0.3 and nxt[s] > 5:
                    live[s].add(rng.randint(0, nxt[s] - 1))   # an old posting comes back
                titles = {i: TITLES[i % len(TITLES)] for i in range(nxt[s])}
                put(raw, d, s, sorted(str(i) for i in live[s]), titles={str(k): v for k, v in titles.items()})
        rows = history.build_rows(raw)
        out_dir = ROOT / "tests" / "fixtures"
        out_dir.mkdir(exist_ok=True)
        history.write_csv(rows, out_dir / "market_history.csv")
    back = history.read_csv(out_dir / "market_history.csv")
    (out_dir / "market_expected.json").write_text(
        json.dumps(market.compute(back), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{len(rows)} postings")


if __name__ == "__main__":
    main()
