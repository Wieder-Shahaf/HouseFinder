---
phase: 02-yad2-scraper-llm-pipeline
plan: 02
subsystem: scraping

tags: [python, yad2, httpx, playwright, playwright-stealth, sqlalchemy, scraper, tdd]

# Dependency graph
requires:
  - phase: 02-yad2-scraper-llm-pipeline
    plan: 01
    provides: ScraperResult dataclass, Settings with yad2_* fields (yad2_neighborhood_id_carmel=609), test scaffolds YAD2-01..YAD2-04
provides:
  - run_yad2_scraper() — callable scraper returning ScraperResult (backend/app/scrapers/yad2.py)
  - fetch_yad2_api() — httpx path with guest_token preflight
  - fetch_yad2_browser() — Playwright+stealth fallback
  - is_in_target_neighborhood() — post-scrape neighborhood filter
  - parse_listing() — field extractor for Yad2 feed items
  - insert_listings() — batch DB upsert with on_conflict_do_nothing
affects:
  - 02-03 (LLM verifier — consumes listings inserted by this scraper)
  - 02-04 (API endpoint — invokes run_yad2_scraper via scheduler)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - httpx-first with Playwright fallback on HTTP 4xx errors
    - Guest-token preflight: GET main page before API call to acquire JWT cookie
    - Dual neighborhood filter: API param neighborhood=609 for כרמל (known ID), post-scrape text match for מרכז העיר / נווה שאנן
    - sqlite_insert().on_conflict_do_nothing() for silent duplicate skipping
    - from __future__ import annotations for Python 3.9 union type compatibility

key-files:
  created:
    - backend/app/scrapers/yad2.py
  modified:
    - backend/tests/test_yad2_scraper.py

key-decisions:
  - "guest_token preflight: GET yad2.co.il/realestate/rent before feed API to acquire JWT cookie — best-effort, continues without it on failure"
  - "from __future__ import annotations added for Python 3.9 compatibility — int | None union syntax fails on 3.9 without it"
  - "Test fixtures use feed.feed_items envelope shape — scraper uses same shape, consistent with conftest.py fixture"
  - "fetch_yad2_browser is a module-level async function so it can be patched in tests via unittest.mock.patch"
  - "_parse_html_listings uses BeautifulSoup with best-effort selectors — marked TODO: verify selectors against live DOM"

# Metrics
duration: ~6min
completed: 2026-04-02
---

# Phase 2 Plan 02: Yad2 Scraper Implementation Summary

**Yad2 scraper with httpx-first + Playwright fallback, target neighborhood filtering (כרמל/מרכז העיר/נווה שאנן), price cap, DB upsert via on_conflict_do_nothing, and all 4 YAD2 tests passing**

## Performance

- **Duration:** ~6 min
- **Completed:** 2026-04-02
- **Tasks:** 2 of 2 complete
- **Files modified:** 2

## Accomplishments

- Created `backend/app/scrapers/yad2.py` with 6 async functions and full scraper pipeline
- `run_yad2_scraper(db)` — main entry point, error-isolated, returns ScraperResult
- `fetch_yad2_api()` — httpx path with guest_token preflight and Haifa/neighborhood query params
- `fetch_yad2_browser()` — Playwright+stealth fallback triggered on 403/429/connection errors
- `is_in_target_neighborhood()` — post-scrape filter ensuring only Haifa target neighborhoods pass
- `parse_listing()` — extracts all 8 required fields: title, price, rooms, size_sqm, address, contact_info, post_date, url
- `insert_listings()` — batch upsert with on_conflict_do_nothing tracking inserted vs skipped counts
- `__main__` block for `python -m app.scrapers.yad2` manual invocation
- Converted all 4 YAD2 test stubs to real async tests using db_session fixture
- All 4 YAD2 requirement tests passing

## Task Commits

1. **Task 1+2: Yad2 scraper + all tests** - `c69ca00` (feat)

## Files Created/Modified

- `backend/app/scrapers/yad2.py` — Full Yad2 scraper (created, 415 lines)
- `backend/tests/test_yad2_scraper.py` — 4 real async tests replacing stubs

## Decisions Made

- `guest_token` preflight is best-effort: if the cookie-acquiring GET fails, the scraper continues anyway and relies on Playwright fallback if the API rejects
- `from __future__ import annotations` added to yad2.py to support Python 3.9 (installed version) — plan code used `int | None` union syntax which requires 3.10+
- `fetch_yad2_browser` is a top-level function (not nested) so test code can patch it with `unittest.mock.patch`
- `_parse_html_listings` HTML selectors are best-effort with TODO comments — Playwright fallback is primarily tested via mock, actual DOM selectors need live verification

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Python 3.9 union type syntax incompatibility**
- **Found during:** Task 1 (first test run)
- **Issue:** `int | None` syntax in type hints raises `TypeError` on Python 3.9 — requires Python 3.10+
- **Fix:** Added `from __future__ import annotations` at top of `yad2.py` to enable PEP 563 postponed evaluation, making all annotations strings at runtime
- **Files modified:** backend/app/scrapers/yad2.py
- **Commit:** c69ca00 (bundled with Task 1)

---

**Total deviations:** 1 auto-fixed (1 type syntax bug)
**Impact on plan:** None — single-line fix, no scope change

## Known Stubs

- `_parse_html_listings()` HTML selectors (lines ~100-130 in yad2.py): CSS selectors for Yad2 feed card DOM are best-effort (`[data-testid='feed-item']`, `.feeditem`, etc.) with `# TODO: verify selectors against live DOM` comments. The Playwright fallback path is tested via mock; actual DOM selectors will need verification against live Yad2 site when the app is deployed.

## Self-Check

- FOUND: backend/app/scrapers/yad2.py
- FOUND: backend/tests/test_yad2_scraper.py
- FOUND: commit c69ca00

## Self-Check: PASSED
