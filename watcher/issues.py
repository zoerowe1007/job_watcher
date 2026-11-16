"""Open one GitHub Issue per day titled with the date, list the new and removed
postings with links, and close the previous day's issue (uses the `gh` CLI)."""
import json
import os
import subprocess

LABEL = "job-watcher"
MAX_BODY = 60000  # GitHub allows 65,536 characters


def _line(r):
    bits = [x for x in (r["employer"], r["location"]) if x]
    star = "⭐ " if r["in_role"] else ""
    return f"- {star}[{r['title'] or r['source_id']}]({r['url']}) — {' · '.join(bits)}" if r["url"] else \
        f"- {star}{r['title'] or r['source_id']} — {' · '.join(bits)}"


def _section(title, rows, budget):
    rows = sorted(rows, key=lambda r: (not r["in_role"], r["employer"], r["title"]))
    out, used = [f"## {title} ({len(rows)})", ""], 0
    if not rows:
        out.append("None.")
    for i, r in enumerate(rows):
        line = _line(r)
        if used + len(line) > budget:
            out.append(f"- …and {len(rows) - i} more (see the site)")
            break
        out.append(line)
        used += len(line) + 1
    return "\n".join(out)


def build_issue(date, new_rows, removed_rows, results, status, site_url=""):
    """Return (title, body). The title is the date."""
    ok = [s for s in results if s["ok"]]
    bad = [s for s in results if not s["ok"]]
    head = [
        f"Run {status['run_time']} · {len(ok)}/{len(results)} sources ok · "
        f"{status['open']} open · **{len(new_rows)} new** · **{len(removed_rows)} removed**",
        "",
    ]
    if site_url:
        head += [f"Site: {site_url}", ""]
    if status["new_today"] == 0 and status["first_run_date"] == date:
        head += ["_First run: the postings already open are the baseline, so nothing counts as new yet._", ""]
    if bad:
        head += ["## Sources that failed", ""] + [f"- {s['name']}: {s.get('error', 'failed')}" for s in bad] + [""]
    head_text = "\n".join(head)
    budget = (MAX_BODY - len(head_text)) // 2 - 200
    body = head_text + "\n" + _section("New postings", new_rows, budget) + "\n\n" + \
        _section("Removed postings", removed_rows, budget) + "\n\n_⭐ = matches my role (title rule)._\n"
    return date, body


def _gh(*args, input_text=None):
    res = subprocess.run(["gh", *args], input=input_text, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])} failed: {res.stderr.strip() or res.stdout.strip()}")
    return res.stdout


def publish(title, body, repo=None):
    """Create (or update) the issue titled `title` and close every other open job-watcher issue."""
    repo = repo or os.environ.get("GITHUB_REPOSITORY")
    base = ["--repo", repo] if repo else []
    _gh("label", "create", LABEL, "--color", "0e8a7d", "--description", "Daily job watcher report",
        "--force", *base)
    found = json.loads(_gh("issue", "list", "--state", "all", "--label", LABEL, "--limit", "200",
                           "--json", "number,title,state", *base) or "[]")
    mine = [i for i in found if i["title"] == title]
    if mine:
        number = mine[0]["number"]
        _gh("issue", "edit", str(number), "--body-file", "-", *base, input_text=body)
        if mine[0]["state"] != "OPEN":
            _gh("issue", "reopen", str(number), *base)
    else:
        out = _gh("issue", "create", "--title", title, "--body-file", "-", "--label", LABEL, *base,
                  input_text=body)
        number = int(out.strip().rsplit("/", 1)[-1])
    for i in found:
        if i["state"] == "OPEN" and i["title"] != title:
            _gh("issue", "close", str(i["number"]), "--comment", f"Superseded by the {title} report.", *base)
    return number
