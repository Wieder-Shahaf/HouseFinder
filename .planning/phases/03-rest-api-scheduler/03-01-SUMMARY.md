---
phase: 03-rest-api-scheduler
plan: 01
subsystem: backend/scheduler
tags: [apscheduler, fastapi, lifespan, health-endpoint, testing]
requirements: [SCHED-01, SCHED-02, SCHED-03]

dependency_graph:
  requires:
    - Phase 02 Yad2 scraper (run_yad2_scraper function)
    - Phase 02 database module (async_session_factory)
  provides:
    - APScheduler embedded in FastAPI process (SCHED-03)
    - Periodic Yad2 scrape job firing immediately on startup (SCHED-01, D-01)
    - Job concurrency lock via max_instances=1 (SCHED-02)
    - GET /api/health with per-source last_run, listings_inserted, success data
    - Test infrastructure: scheduler mocked in conftest, seed_listings fixture
  affects:
    - backend/app/main.py (lifespan, health endpoint)
    - backend/tests/conftest.py (client fixture, new seed_listings fixture)
    - backend/tests/test_api.py (health endpoint assertions updated)

tech_stack:
  added:
    - APScheduler 3.x AsyncIOScheduler (embedded in FastAPI process)
  patterns:
    - Deferred imports in scheduler job to avoid circular dependencies
    - Module-level _health dict for in-memory state (resets on restart per D-02)
    - lifespan context manager for scheduler start/stop lifecycle
    - unittest.mock.patch on app.scheduler.scheduler in test fixtures

key_files:
  created:
    - backend/app/scheduler.py
    - backend/tests/test_scheduler.py
  modified:
    - backend/app/main.py
    - backend/app/config.py
    - backend/tests/conftest.py
    - backend/tests/test_api.py

decisions:
  - "Deferred imports (from app.database import async_session_factory) inside run_yad2_scrape_job to avoid module-level circular imports at startup"
  - "Patch app.scheduler.scheduler (not app.main.scheduler) in conftest to intercept lifespan add_job/start/shutdown calls correctly"
  - "test_api.py health test updated to assert scrapers.yad2 keys exist rather than exact equality, future-proofing for additional fields"
  - "test_run.py pre-existing script at backend root excluded from test runs — use pytest tests/ not pytest . to avoid DB connection error"

metrics:
  duration: "8 minutes"
  completed_date: "2026-04-02"
  tasks_completed: 2
  files_created: 2
  files_modified: 4
---

# Phase 03 Plan 01: APScheduler + Health Endpoint Summary

APScheduler embedded in FastAPI lifespan with immediate first Yad2 scrape, max_instances=1 job lock, and per-source health state exposed via GET /api/health.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create scheduler module + update config | 55195fe | backend/app/scheduler.py, backend/app/config.py |
| 2 | Wire scheduler into lifespan + enhance health endpoint + update tests | 78ecc43 | backend/app/main.py, backend/tests/conftest.py, backend/tests/test_scheduler.py, backend/tests/test_api.py |

## What Was Built

- **`backend/app/scheduler.py`**: AsyncIOScheduler instance, module-level `_health` dict (yad2=None initially), `get_health_state()` reader, `run_yad2_scrape_job()` job function with deferred imports
- **`backend/app/main.py`**: Updated lifespan starts/stops scheduler; job registered with `max_instances=1`, `coalesce=True`, `next_run_time=datetime.now(UTC)` for immediate first fire; health endpoint returns `{"status": "ok", "scrapers": {"yad2": {...}}}`
- **`backend/app/config.py`**: Added `scrape_interval_hours: int = 2` to Settings
- **`backend/tests/test_scheduler.py`**: 5 tests covering SCHED-01/02/03, health state initial, success + failure paths
- **`backend/tests/conftest.py`**: client fixture now mocks scheduler and overrides DB; new `seed_listings` fixture with 4 test listings
- **`backend/tests/test_api.py`**: Updated health assertions to match new response shape

## Verification Results

```
tests/test_scheduler.py: 5 passed
tests/ (full suite): 22 passed
imports OK
config OK
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_api.py health assertion to match new response shape**
- **Found during:** Task 2
- **Issue:** Existing `test_health_endpoint` asserted `response.json() == {"status": "ok"}` (exact match); new endpoint returns `{"status": "ok", "scrapers": {...}}` — would have caused test failure
- **Fix:** Updated assertion to check `data["status"] == "ok"` and verify presence of `scrapers.yad2` keys
- **Files modified:** backend/tests/test_api.py
- **Commit:** 78ecc43

**2. [Rule 3 - Blocking] Fixed test_job_config_in_lifespan to use absolute path**
- **Found during:** Task 2
- **Issue:** Plan's template used `open("app/main.py")` which is a relative path; pytest runs from `backend/tests/` or `backend/` depending on invocation — would cause FileNotFoundError
- **Fix:** Used `os.path.dirname(__file__)` to construct absolute path to `app/main.py`
- **Files modified:** backend/tests/test_scheduler.py
- **Commit:** 78ecc43

## Known Stubs

None. All health data flows from live `_health` dict updated by `run_yad2_scrape_job`. Initial state (None values) is intentional per D-02 spec.

## Self-Check: PASSED
