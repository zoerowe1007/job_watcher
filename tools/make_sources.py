"""Build sources.json and the README sources table from data/probe.json.

Setup helper (not part of the daily pipeline):

    python tools/make_sources.py

Every candidate whose board answered becomes a source. A board that lists more than
5,000 postings gets the search term "analyst", as the pipeline requires.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_POSTINGS = 5000
SEARCH_TERM = "analyst"
ATS_NAMES = {"workday": "Workday", "oracle": "Oracle Recruiting Cloud", "greenhouse": "Greenhouse",
             "lever": "Lever", "ashby": "Ashby", "smartrecruiters": "SmartRecruiters"}
KEYS = {"workday": ("host", "tenant", "site"), "oracle": ("host", "site"), "greenhouse": ("board",),
        "lever": ("company",), "ashby": ("board",), "smartrecruiters": ("company",)}


def build(probe):
    sources = []
    for result in probe["results"]:
        if not result.get("found"):
            continue
        found = result["found"][0]
        entry = {"name": result["name"], "employer": result["employer"], "ats": found["ats"]}
        for key in KEYS[found["ats"]]:
            entry[key] = found[key]
        if int(found.get("total") or 0) > MAX_POSTINGS:
            entry["search"] = SEARCH_TERM
        sources.append(entry)
    return sources


def board(src):
    where = src.get("host") or src.get("board") or src.get("company")
    extra = src.get("site") or ""
    return f"`{where} / {extra}`" if extra else f"`{where}`"


def table(sources):
    lines = ["| Employer | Source | ATS | Board | Search term |", "|---|---|---|---|---|"]
    for s in sources:
        term = f"`{s['search']}`" if s.get("search") else "—"
        lines.append(f"| {s['employer']} | `{s['name']}` | {ATS_NAMES[s['ats']]} | {board(s)} | {term} |")
    return "\n".join(lines)


def main():
    probe = json.loads((ROOT / "data" / "probe.json").read_text(encoding="utf-8"))
    sources = build(probe)
    out = "{\n  \"sources\": [\n" + ",\n".join("    " + json.dumps(s, ensure_ascii=False) for s in sources) + "\n  ]\n}\n"
    (ROOT / "sources.json").write_text(out, encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    block = f"<!-- sources:start -->\n{table(sources)}\n<!-- sources:end -->"
    if "<!-- sources:start -->" in readme:
        readme = re.sub(r"<!-- sources:start -->.*?<!-- sources:end -->", lambda _m: block, readme, flags=re.S)
    else:
        readme = re.sub(r"\| Employer \| Source \| ATS \| Board \| Search term \|\n(?:\|.*\n)+", lambda _m: block + "\n", readme, count=1)
    (ROOT / "README.md").write_text(readme, encoding="utf-8")
    print(f"{len(sources)} sources written")
    for s in sources:
        print(" ", s["name"], s["ats"], s.get("search", ""))


if __name__ == "__main__":
    main()
