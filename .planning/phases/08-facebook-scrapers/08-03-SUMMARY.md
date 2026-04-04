---
phase: 08-facebook-scrapers
plan: "03"
subsystem: backend/scheduler
tags: [facebook, scheduler, apscheduler, health-endpoint, session-management]
dependency_graph:
  requires:
    - backend/app/scrapers/facebook_groups.py (run_facebook_groups_scraper — Plan 01)
    - backend/app/scrapers/facebook_marketplace.py (run_facebook_marketplace_scraper — Plan 02)
    - backend/app/scheduler.py (run_yad2_scrape_job, run_madlan_scrape_job patterns)
    - backend/app/main.py (lifespan, health endpoint)
  provides:
    - backend/app/scheduler.py (run_facebook_groups_scrape_job, run_facebook_marketplace_scrape_job)
    - backend/app/main.py (facebook_groups_scrape + facebook_marketplace_scrape jobs, facebook_session_valid in /health)
    - backend/scripts/generate_facebook_session.py (one-time manual login session generator)
  affects:
    - GET /api/health (now returns facebook_session_valid + two new scraper entries)
tech-stack:
  added: []
  patterns:
    - Deferred import pattern for APScheduler job functions (circular import avoidance)
    - facebook_session_valid bool field in _health dict — shared between both Facebook jobs
    - Independent APScheduler jobs (facebook_groups failure never blocks facebook_marketplace)
key-files:
  created:
    - backend/scripts/generate_facebook_session.py
  modified:
    - backend/app/scheduler.py (two new job functions + extended _health dict)
    - backend/app/main.py (job registration in lifespan + facebook_session_valid in health)
    - backend/tests/test_facebook_scrapers.py (5 integration tests appended)
decisions:
  - "facebook_session_valid is a shared bool at the _health top level — updated by whichever Facebook job ran most recently (D-12)"
  - "Both Facebook jobs use next_run_time=datetime.now(timezone.utc) — fire immediately on startup (consistent with Yad2/Madlan)"
  - "Pre-existing test failures (11 tests) are unrelated to Plan 03 changes — confirmed by stash/unstash comparison"
metrics:
  duration: "4 minutes"
  completed_date: "2026-04-04"
  tasks: 2
  files_changed: 4
---

# Phase 08 Plan 03: Scheduler Integration + Health Endpoint Summary

**Both Facebook scrapers wired as independent APScheduler jobs with health endpoint tracking and a manual session generation script.**

## What Was Built

**Task 1: Scheduler jobs + health endpoint + login script (commit `bdf653c`)**

- `backend/app/scheduler.py` — extended with:
  - `_health` dict: added `"facebook_groups": None`, `"facebook_marketplace": None`, `"facebook_session_valid": None`
  - `run_facebook_groups_scrape_job()` — deferred-import APScheduler job following madlan pattern; updates `_health["facebook_groups"]` and `_health["facebook_session_valid"]` after each run
  - `run_facebook_marketplace_scrape_job()` — identical pattern for Marketplace; also updates `_health["facebook_session_valid"]`

- `backend/app/main.py` — updated with:
  - Import of both new job functions from scheduler
  - Two `scheduler.add_job()` calls in lifespan (interval=scrape_interval_hours, max_instances=1, coalesce=True, next_run_time=now)
  - `/api/health` endpoint updated to expose `facebook_session_valid` at top level, skipping it from the `scrapers` dict loop

- `backend/scripts/generate_facebook_session.py` — standalone one-time script:
  - Opens visible Chromium (`headless=False`) to facebook.com/login
  - Waits for user to log in manually and press Enter
  - Saves `storage_state` (cookies + localStorage) to `/data/facebook_session.json`
  - Both scrapers load this file at runtime

**Task 2: Integration tests (commit `d852bda`)**

5 tests appended to `backend/tests/test_facebook_scrapers.py` (28 total):

- `test_scheduler_health_keys` — verifies all three new keys exist in `_health`
- `test_scheduler_health_updated` — mocked job run populates `_health["facebook_groups"]` with correct fields
- `test_scheduler_session_valid_updated` — session_expired error sets `facebook_session_valid=False`; clean run sets it `True`
- `test_health_endpoint_facebook` — `GET /api/health` returns `facebook_groups`/`facebook_marketplace` in `scrapers` and `facebook_session_valid` at top level
- `test_jobs_independent` — groups job failure does not prevent marketplace job from running (D-10)

## Decisions Made

1. `facebook_session_valid` lives at the top level of the `_health` dict (not nested inside each scraper entry) — it is a shared signal updated by whichever job ran most recently
2. Both Facebook jobs fire immediately on startup (`next_run_time=datetime.now(timezone.utc)`) — consistent with existing Yad2/Madlan behavior
3. Pre-existing suite failures (11 tests) are confirmed pre-existing and out of scope — verified by git stash comparison before and after changes

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. All scheduler wiring is complete. The `generate_facebook_session.py` script requires a human to run it once (by design — Facebook login cannot be automated safely). This is not a stub; it is the intended manual step documented in the plan.

## Self-Check: PASSED

- FOUND: backend/app/scheduler.py (run_facebook_groups_scrape_job, run_facebook_marketplace_scrape_job)
- FOUND: backend/app/main.py (facebook_groups_scrape, facebook_marketplace_scrape jobs, facebook_session_valid)
- FOUND: backend/scripts/generate_facebook_session.py
- FOUND: backend/tests/test_facebook_scrapers.py (28 tests, all passing)
- FOUND: commit bdf653c (feat: Task 1)
- FOUND: commit d852bda (test: Task 2)
