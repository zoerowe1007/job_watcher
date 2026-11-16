# Job Watcher

[![tests](https://github.com/zoerowe1007/job_watcher/actions/workflows/tests.yml/badge.svg)](https://github.com/zoerowe1007/job_watcher/actions/workflows/tests.yml)
[![daily run](https://github.com/zoerowe1007/job_watcher/actions/workflows/daily.yml/badge.svg)](https://github.com/zoerowe1007/job_watcher/actions/workflows/daily.yml)

A tool that watches the job market for me. Every day GitHub Actions reads the open positions at large employers in
**Dallas–Fort Worth and Northwest Arkansas**, compares them with the day before, records what is new and what is gone,
opens a GitHub Issue with the changes, and publishes the result to a website.

**My role:** analyst roles in finance and data (financial analyst, FP&A, data analyst, business intelligence,
credit analyst, supply chain analyst and similar).

**Site:** https://zoerowe1007.github.io/job_watcher/ (Today, Browse, Market; installable as an app)

## How it works

1. `python -m watcher.run` calls every source's public JSON endpoint (no login, no HTML) and saves what each returns,
   compressed, in `data/raw/<UTC date>/<source>.json.gz`. A source that fails writes no raw file that day; the result
   of every source (ok or failed, with the error) goes into `data/status.json` and `data/run_log.json`.
2. The history file is **built from the raw files alone** (`watcher/history.py`).
3. `data/status.json` describes the latest run.
4. An Issue titled with the date lists the new and removed postings with links; the previous day's Issue is closed.
5. The workflow commits the raw files, `data/history.csv`, `data/status.json` and `data/run_log.json`.

A run is successful when it finishes and commits, even if some sources failed. A second run on the same UTC day
replaces that day's raw files, rebuilds the history and updates that day's Issue, so each day counts once.

### Rebuild the history from the raw files

```
python -m watcher.history
```

This reads every file in `data/raw/` and rewrites `data/history.csv`. Running it again gives byte-identical output, and a
change to the title rule applies to every day of the history.

### Run the tests

```
pip install -r requirements.txt
python -m pytest
node tests/market_check.mjs
```

## History rules

* A posting seen for the first time gets that day as `first_seen`; `first_run` is true when it was listed in the first
  raw file of its source (its real start date is unknown).
* Every posting a source lists on a day gets that day as `last_seen`.
* An open posting is marked `removed` with that day's date when its source has a raw file for that day and no longer lists
  it. A day on which a source failed (no raw file) changes nothing for that source.
* A removed posting that is listed again becomes `open`, `removed_date` is cleared and `first_seen` is unchanged.
* Every posting the board returns is kept, in my role or not. Rows are sorted by `posting_id` (`<source>:<source id>`).
* If a board suddenly returns zero postings after having had some, that run treats the source as failed rather than
  marking everything removed.

## The title rule

A posting is `in_role` when its title (ignoring case) **matches at least one INCLUDE pattern and none of the EXCLUDE
patterns**. The patterns live in `watcher/titlerule.py`.

* INCLUDE: `analyst`, `analysts`, `analytics`, `FP&A` / `FP and A`, `financial planning`, `business intelligence`,
  `BI developer|engineer|specialist` (whole words).
* EXCLUDE: senior leadership (`director`, `vice president`, `VP`, `SVP`, `AVP`, `head of`, `chief`, `manager`,
  `principal`); other fields (`cyber`, `cybersecurity`, `security`, `network`, `infrastructure`, `devops`, `software`,
  `nurse`, `nursing`, `clinical`, `pharmacist`, `technician`, `driver`, `mechanic`); and `SOC`, `help desk`, `QA` or
  `test` analysts.

## Sources

Each source is one employer job board read through the applicant tracking system (ATS) that hosts it. They are listed in
`sources.json`; adding an employer is one more entry there (no code changes). A board that lists more than 5,000
postings is requested with a search term (last column); the pipeline refuses to read such a board without one.

<!-- sources:start -->
| Employer | Source | ATS | Board | Search term |
|---|---|---|---|---|
| Fidelity Investments | `fidelity` | Workday | `fmr.wd1.myworkdayjobs.com / FidelityCareers` | — |
| JPMorgan Chase | `jpmorgan` | Oracle Recruiting Cloud | `jpmc.fa.oraclecloud.com / CX_1001` | `analyst` |
| Capital One | `capitalone` | Workday | `capitalone.wd12.myworkdayjobs.com / Capital_One` | — |
| AT&T | `att` | Workday | `att.wd1.myworkdayjobs.com / ATTGeneral` | — |
| McKesson | `mckesson` | Workday | `mckesson.wd3.myworkdayjobs.com / External_Careers` | — |
| J.B. Hunt | `jbhunt` | Workday | `jbhunt.wd501.myworkdayjobs.com / Careers` | — |
| Procter & Gamble | `pg` | Workday | `pg.wd5.myworkdayjobs.com / 1000` | — |
| Kimberly-Clark | `kimberlyclark` | Workday | `kimberlyclark.wd1.myworkdayjobs.com / GLOBAL` | — |
| Wells Fargo | `wellsfargo` | Workday | `wf.wd1.myworkdayjobs.com / WellsFargoJobs` | — |
| Southwest Airlines | `southwest` | Workday | `swa.wd1.myworkdayjobs.com / External` | — |
<!-- sources:end -->

Endpoints used (all public, no login):

* **Workday:** `POST https://<host>/wday/cxs/<tenant>/<site>/jobs` with `limit`, `offset`, `searchText`
* **Oracle Recruiting Cloud:** `GET https://<host>/hcmRestApi/resources/latest/recruitingCEJobRequisitions?finder=findReqs;siteNumber=<site>,...`
* **Greenhouse, Lever, Ashby, SmartRecruiters:** converters and fetchers are included and tested; used when a watched
  employer is on one of them.

`tools/probe.py` (run from the **probe sources** workflow) checks which employer boards answer; it is a setup helper and
is not part of the daily pipeline.

## Files

| File | What it does |
|---|---|
| `watcher/run.py` | The daily run: fetch every source, write raw files, build history, write status, open the Issue |
| `watcher/fetchers.py` | Calls each ATS's JSON endpoint, pages through results, enforces the 5,000-posting search rule |
| `watcher/http.py` | JSON over HTTP with retries (standard library only) |
| `watcher/adapters.py` | Converts each ATS's raw postings to the common columns |
| `watcher/common.py` | The common columns and text helpers |
| `watcher/titlerule.py` | The title rule (`in_role`) |
| `watcher/rawstore.py` | Reads and writes `data/raw/<date>/<source>.json.gz` |
| `watcher/history.py` | Builds `data/history.csv` from the raw files (`python -m watcher.history`) |
| `watcher/status.py` | Writes `data/status.json` and `data/run_log.json` |
| `watcher/issues.py` | Opens the day's GitHub Issue and closes the previous one |
| `watcher/market.py` | Python reference for the Market numbers (used in tests) |
| `sources.json` | The watch list |
| `tools/probe.py`, `tools/candidates.json` | Setup helper that tests candidate job boards |
| `tests/` | pytest suite (conversion per source, title rule, first/last-seen/removed logic, run, Market) and `market_check.mjs` |
| `.github/workflows/daily.yml` | Daily schedule: run the pipeline and commit the data |
| `.github/workflows/tests.yml` | Runs the tests on every push |
| `.github/workflows/probe.yml` | Manual: test candidate job boards |
| `data/raw/<date>/<source>.json.gz` | What each source returned each day |
| `data/history.csv` | One row per posting (columns below) |
| `data/status.json` | Latest run: time, counts, per-source status |
| `data/run_log.json` | Every day's per-source result, including failures |
| `index.html` | Today page: last run, source status, counts, new and removed postings |
| `browse.html` | Browse page: filters, search, sort, apply links, starred shortlist |
| `market.html` | Market page: six sections computed in the browser from `history.csv` |
| `assets/style.css`, `assets/common.js`, `assets/charts.js`, `assets/market-calc.js` | Shared look, helpers, SVG charts, Market calculations |
| `manifest.webmanifest`, `sw.js`, `assets/icons/` | Make the site installable and usable offline |

### `data/history.csv` columns

`posting_id, source, source_id, employer, title, location, department, posted_date, url, in_role, first_run,
first_seen, last_seen, status, removed_date`. Dates are UTC `YYYY-MM-DD`. Columns a source does not provide (for example
`department` for Workday) are empty.

## Market definitions

Postings with `first_run = true` were already open when watching started, so their start date is unknown and they are left
out where noted: new postings per day, days open, and the seven-day share. Median days open = median of
`removed_date − first_seen` over removed postings that are not first-run. Share removed within seven days = among
non-first-run postings first seen at least seven days before the last run, the share whose `removed_date − first_seen ≤ 7`.
`tests/market_check.mjs` checks that the page's JavaScript gets the same numbers as the Python reference.

## Setup notes

Settings → Actions → General → Workflow permissions: **Read and write**. Settings → Pages: deploy from branch `main`, folder `/ (root)`.
