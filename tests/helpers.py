"""Helpers shared by the tests: write raw files into a temporary directory."""
from watcher.rawstore import write_raw


def lever_raw(source, ids, titles=None, employer=None):
    titles = titles or {}
    postings = [{"id": i, "text": titles.get(i, f"Title {i}"), "categories": {"location": "Dallas, TX"},
                 "hostedUrl": f"https://jobs.example.com/{source}/{i}", "createdAt": 1762732800000}
                for i in ids]
    return {"source": source, "employer": employer or source.title(), "ats": "lever",
            "meta": {"company": source}, "fetched_at": "2026-01-01T07:00:00+00:00",
            "count": len(postings), "postings": postings}


def put(raw_dir, date, source, ids, **kw):
    raw = lever_raw(source, ids, **kw)
    raw["fetched_at"] = f"{date}T07:00:00+00:00"
    write_raw(raw_dir, date, raw)
