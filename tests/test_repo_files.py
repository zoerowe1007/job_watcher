"""The configuration and site files are in place and consistent."""
import json
from pathlib import Path

from watcher.fetchers import FETCHERS

ROOT = Path(__file__).resolve().parent.parent
NEEDS = {"workday": ["host", "tenant", "site"], "oracle": ["host", "site"], "greenhouse": ["board"],
         "lever": ["company"], "ashby": ["board"], "smartrecruiters": ["company"]}


def test_sources_are_well_formed():
    sources = json.loads((ROOT / "sources.json").read_text())["sources"]
    names = [s["name"] for s in sources]
    assert len(names) == len(set(names))
    for s in sources:
        assert s["ats"] in FETCHERS
        assert s["employer"]
        for key in NEEDS[s["ats"]]:
            assert s.get(key), f"{s['name']} lacks {key}"


def test_candidates_file_parses():
    c = json.loads((ROOT / "tools" / "candidates.json").read_text())["candidates"]
    assert len(c) >= 15 and all(x["guesses"] for x in c)


def test_site_files_exist_and_share_navigation():
    for page in ("index.html", "browse.html", "market.html"):
        html = (ROOT / page).read_text()
        for link in ('href="index.html"', 'href="browse.html"', 'href="market.html"',
                     'assets/style.css', 'manifest.webmanifest'):
            assert link in html, f"{page} lacks {link}"
        assert 'aria-current="page"' in html
    manifest = json.loads((ROOT / "manifest.webmanifest").read_text())
    assert manifest["start_url"] and manifest["display"] == "standalone"
    sizes = {i["sizes"] for i in manifest["icons"]}
    assert {"192x192", "512x512"} <= sizes
    for icon in manifest["icons"]:
        assert (ROOT / icon["src"]).exists()
    assert "fetch" in (ROOT / "sw.js").read_text()
