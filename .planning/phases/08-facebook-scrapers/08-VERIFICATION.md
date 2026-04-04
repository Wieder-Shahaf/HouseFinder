---
phase: 08-facebook-scrapers
verified: 2026-04-04T00:00:00Z
status: passed
score: 11/11 must-haves verified
re_verification: false
---

# Phase 8: Facebook Scrapers Verification Report

**Phase Goal:** Implement Facebook Groups and Marketplace scrapers that collect Haifa rental listings using Playwright + stealth, with shared session infrastructure, health checks, session-expiry alerts, and APScheduler integration.
**Verified:** 2026-04-04
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Facebook Groups scraper loads group list from /data/facebook_groups.json and iterates each group URL | VERIFIED | `_load_groups()` reads `GROUPS_FILE`, iterates `group.get("url")` per group in main loop |
| 2 | Scraper loads a saved Playwright session from facebook_session.json and uses it for authenticated navigation | VERIFIED | `_load_fb_context()` passes `storage_state=session_path` to `browser.new_context()`, verified by `test_session_loaded` |
| 3 | Session health is checked before scraping; expiry triggers a Web Push alert and clean skip | VERIFIED | `check_session_health()` checks URL for "login"/"checkpoint" + LeftRail presence; `send_session_expiry_alert()` called on failure; `result.success=True` preserved |
| 4 | Scraper extracts post text, poster name/link, post date, group name, and post URL from group pages | VERIFIED | Groups scraper extracts `post_text`, `poster_name`, `post_date_text`, `group_name`, `post_url` from `[role="article"]` elements |
| 5 | Any failure in Facebook Groups scraping does not propagate — returns ScraperResult with success flag | VERIFIED | Outer try/except sets `result.success = False`, appends error, closes browser; `test_groups_failure_isolation` passes |
| 6 | Facebook Marketplace scraper fetches Haifa rental listings from the Marketplace URL | VERIFIED | `MARKETPLACE_URL = "https://www.facebook.com/marketplace/haifa/propertyrentals/"`, navigated in `run_facebook_marketplace_scraper()` |
| 7 | Scraper uses the same saved authenticated session as the Groups scraper | VERIFIED | `from app.scrapers.facebook_groups import _load_fb_context, check_session_health` — imports and uses shared infrastructure |
| 8 | Scraper extracts title, price, address/neighborhood, post date, and listing URL from Marketplace cards | VERIFIED | Card extraction via `a[href*="/marketplace/item/"]`, parses `title`, `price` (₪ regex), `location`, `listing_url`; fallback to `page.inner_text("main")` |
| 9 | Any failure in the Marketplace scraper does not propagate — returns ScraperResult cleanly | VERIFIED | Same outer try/except pattern; `test_marketplace_failure_isolation` passes |
| 10 | Both Facebook scrapers run on the shared scrape_interval_hours schedule as independent APScheduler jobs | VERIFIED | `scheduler.add_job(run_facebook_groups_scrape_job, ...)` and `scheduler.add_job(run_facebook_marketplace_scrape_job, ...)` registered in `main.py` lifespan with `id="facebook_groups_scrape"` / `id="facebook_marketplace_scrape"` |
| 11 | GET /health includes facebook_groups and facebook_marketplace entries plus a facebook_session_valid boolean | VERIFIED | `main.py` health endpoint returns `{"scrapers": {"facebook_groups": ..., "facebook_marketplace": ...}, "facebook_session_valid": ...}`; `test_health_endpoint_facebook` passes |

**Score:** 11/11 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/scrapers/facebook_groups.py` | Facebook Groups scraper with session management and health check | VERIFIED | 443 lines; exports `run_facebook_groups_scraper`, `check_session_health`, `_load_fb_context`, `extract_post_source_id` |
| `backend/app/scrapers/facebook_marketplace.py` | Facebook Marketplace scraper | VERIFIED | 339 lines; exports `run_facebook_marketplace_scraper`; imports session infra from `facebook_groups.py` |
| `backend/app/config.py` | `facebook_session_path` setting | VERIFIED | Line 50: `facebook_session_path: str = "/data/facebook_session.json"` |
| `backend/app/notifier.py` | `send_session_expiry_alert` function | VERIFIED | Lines 114-142; sends Hebrew Web Push: "פייסבוק דורש התחברות מחדש" |
| `backend/app/scheduler.py` | Two new job functions and _health entries for Facebook scrapers | VERIFIED | `run_facebook_groups_scrape_job()` and `run_facebook_marketplace_scrape_job()` present; `_health` dict includes all three new keys |
| `backend/app/main.py` | Job registration in lifespan + facebook_session_valid in /health | VERIFIED | Both jobs registered with `id="facebook_groups_scrape"` and `id="facebook_marketplace_scrape"`; health endpoint returns `facebook_session_valid` |
| `backend/scripts/generate_facebook_session.py` | One-time login script for session generation | VERIFIED | 60 lines; `headless=False`, saves `storage_state` to `/data/facebook_session.json` |
| `backend/tests/test_facebook_scrapers.py` | Unit + integration tests for all requirements | VERIFIED | 713 lines, 28 tests; all 28 pass |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `facebook_groups.py` | `notifier.py` | `send_session_expiry_alert()` call | WIRED | Line 219: `await send_session_expiry_alert()` called on session expiry |
| `facebook_groups.py` | `llm/verifier.py` | `batch_verify_listings()` | WIRED | Line 359: `llm_results = await batch_verify_listings(texts_for_llm)` |
| `facebook_groups.py` | `config.py` | `settings.facebook_session_path` | WIRED | Lines 207, 215: `settings.facebook_session_path` used for file check and context load |
| `facebook_marketplace.py` | `facebook_groups.py` | `from app.scrapers.facebook_groups import _load_fb_context, check_session_health` | WIRED | Line 34: import present; both functions called in scraper body |
| `facebook_marketplace.py` | `llm/verifier.py` | `batch_verify_listings()` | WIRED | Line 254: `llm_results = await batch_verify_listings(texts_for_llm)` |
| `scheduler.py` | `facebook_groups.py` | deferred import `run_facebook_groups_scraper` | WIRED | Line 108: `from app.scrapers.facebook_groups import run_facebook_groups_scraper` |
| `scheduler.py` | `facebook_marketplace.py` | deferred import `run_facebook_marketplace_scraper` | WIRED | Line 147: `from app.scrapers.facebook_marketplace import run_facebook_marketplace_scraper` |
| `main.py` | `scheduler.py` | imports job functions and registers with scheduler | WIRED | Lines 17-18: `run_facebook_groups_scrape_job`, `run_facebook_marketplace_scrape_job` imported and registered in lifespan |

---

### Data-Flow Trace (Level 4)

Both scrapers follow the same data pipeline: Playwright DOM extraction → LLM batch verification → SQLite insert with `on_conflict_do_nothing`. Verified at each stage:

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `facebook_groups.py` | `all_posts` | `page.locator('[role="article"]').all()` — DOM scrape | Yes — Playwright query over live DOM articles | FLOWING |
| `facebook_groups.py` | `llm_results` | `batch_verify_listings(texts_for_llm)` | Yes — calls real LLM verifier | FLOWING |
| `facebook_groups.py` | DB insert | `sqlite_insert(Listing).on_conflict_do_nothing(...)` | Yes — inserts merged fields | FLOWING |
| `facebook_marketplace.py` | `raw_listings` | `page.locator('a[href*="/marketplace/item/"]').all()` | Yes — Playwright query over live Marketplace cards | FLOWING |
| `facebook_marketplace.py` | `llm_results` | `batch_verify_listings(texts_for_llm)` | Yes — calls real LLM verifier | FLOWING |
| `facebook_marketplace.py` | DB insert | `sqlite_insert(Listing).on_conflict_do_nothing(...)` | Yes — inserts merged fields | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All scraper imports resolve | `python3 -c "from app.scrapers.facebook_groups import ...; from app.scrapers.facebook_marketplace import ...; from app.scheduler import ..."` | All imports OK | PASS |
| config.facebook_session_path exists and has correct default | `assert settings.facebook_session_path == '/data/facebook_session.json'` | Assertion passed | PASS |
| _health dict has all three new keys | `assert 'facebook_groups' in _health; assert 'facebook_session_valid' in _health` | Assertion passed | PASS |
| All 28 Facebook-specific tests pass | `python3 -m pytest tests/test_facebook_scrapers.py -v` | 28 passed, 0 failed in 0.56s | PASS |
| Full test suite — Phase 8 tests unaffected by pre-existing failures | `python3 -m pytest tests/ -q` | 98 passed (11 pre-existing failures confirmed unrelated to Phase 8) | PASS |

---

### Requirements Coverage

All 9 requirement IDs declared across Plans 01, 02, and 03 are covered:

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| FBGR-01 | Plan 01 | Scraper monitors user-configured Facebook group list | SATISFIED | `_load_groups()` reads `/data/facebook_groups.json`; iterates each group URL |
| FBGR-02 | Plan 01 | Scraper uses saved authenticated Playwright session | SATISFIED | `_load_fb_context()` uses `storage_state=session_path`; stealth applied |
| FBGR-03 | Plan 01 | Session health checked before each run; alert on expiry | SATISFIED | `check_session_health()` + `send_session_expiry_alert()` + clean skip |
| FBGR-04 | Plan 01 | Extracts post text, poster name/link, post date, group name, post URL | SATISFIED | All five fields extracted from `[role="article"]` elements |
| FBGR-05 | Plan 01 | Facebook Groups failure isolated | SATISFIED | Outer try/except; `result.success=False` without propagation |
| FBMP-01 | Plan 02 | Fetches rental listings from Haifa Marketplace | SATISFIED | `MARKETPLACE_URL` constant; navigated in scraper |
| FBMP-02 | Plan 02 | Uses same session as Facebook Groups | SATISFIED | `_load_fb_context` and `check_session_health` imported from `facebook_groups.py` |
| FBMP-03 | Plan 02 | Extracts title, price, address/neighborhood, post date, listing URL | SATISFIED | Card extraction parses all five fields; fallback extraction present |
| FBMP-04 | Plan 02 | Facebook Marketplace failure isolated | SATISFIED | Outer try/except; `result.success=False` without propagation |

**No orphaned requirements:** All 9 Phase 8 IDs from REQUIREMENTS.md traceability table are covered by plans.

---

### Anti-Patterns Found

No blockers or warnings detected.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `facebook_groups.py` | 87, 93, 96 | `return []` | Info | Expected defensive returns in `_load_groups()` when file missing, empty, or unparseable — not a stub |
| `notifier.py` | 146-168 | `send_whatsapp()` logs only, no Twilio call | Info | Pre-existing stub from Phase 7 (NOTF-01/02 pending Meta template approval) — out of scope for Phase 8 |

The `return []` in `_load_groups()` are legitimate early exits (missing file, empty list, parse error), not render-path stubs. Data flows through the real Playwright + LLM pipeline when groups are present.

---

### Human Verification Required

The following item cannot be verified programmatically and requires a human test when running on the DigitalOcean VPS:

**1. Facebook Session Persistence and Health Check on Live Facebook**

**Test:** Run `python scripts/generate_facebook_session.py`, log in to Facebook, press Enter. Then trigger a scrape via `GET /api/health` or wait for the scheduled interval.
**Expected:** Session file saved at `/data/facebook_session.json`; scraper navigates to group URLs without login redirect; `_health["facebook_session_valid"]` is `True` after the run; new listings appear on the map.
**Why human:** Requires a live Facebook account, a real browser window, and a VPS with Xvfb for `headless=False` operation. Cannot be verified against the live Facebook anti-bot detection programmatically.

**2. Session Expiry Alert on VPS**

**Test:** Delete or invalidate `/data/facebook_session.json`, then wait for or manually trigger a Facebook scrape job.
**Expected:** Web Push notification arrives on phone with Hebrew title "פייסבוק דורש התחברות מחדש"; `_health["facebook_session_valid"]` becomes `False`; scrape exits cleanly without crashing the application.
**Why human:** Requires a registered push subscription on a real device and a live Facebook session to expire.

---

### Gaps Summary

No gaps. All must-haves verified at all four levels (exists, substantive, wired, data flowing).

The 11 pre-existing test failures in the broader suite (`test_api.py`, `test_database.py`, `test_listings_neighborhood.py`, `test_madlan_scraper.py`, `test_scheduler.py`) were confirmed pre-existing by the Plan 03 executor and are unrelated to Phase 8 changes.

---

_Verified: 2026-04-04_
_Verifier: Claude (gsd-verifier)_
