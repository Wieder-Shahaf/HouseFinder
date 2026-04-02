---
phase: 03-rest-api-scheduler
plan: 02
subsystem: backend/api
tags: [fastapi, listings-api, filters, sqlalchemy, testing]
requirements: [SCHED-01, SCHED-02, SCHED-03]

dependency_graph:
  requires:
    - Phase 03 Plan 01 (scheduler, conftest fixtures, seed_listings)
    - Phase 02 Listing model and ListingResponse schema
    - backend/app/config.py (llm_confidence_threshold, database settings)
  provides:
    - GET /api/listings with price_min, price_max, rooms_min, rooms_max, neighborhood, is_seen, is_favorited, since_hours filters
    - PUT /api/listings/{id}/seen - mark listing as seen
    - PUT /api/listings/{id}/favorited - mark listing as favorited
    - 404 responses with Hebrew detail "מודעה לא נמצאה"
    - Full Phase 3 REST API surface for Phase 4 (Map Web UI) consumption
  affects:
    - backend/app/routers/listings.py (full implementation replacing stub)
    - backend/tests/test_api.py (14 comprehensive endpoint tests)

tech_stack:
  added: []
  patterns:
    - SQLAlchemy async select with and_(*filters) for dynamic filter composition
    - ilike() for case-insensitive Hebrew address substring matching (D-05)
    - db.get(Listing, id) for primary key lookup before PUT mutations
    - Base filters always applied (is_active=True, llm_confidence >= threshold)
    - Optional[bool] Query params for is_seen/is_favorited tri-state (None/True/False)

key_files:
  created: []
  modified:
    - backend/app/routers/listings.py
    - backend/tests/test_api.py

decisions:
  - "NULL llm_confidence rows excluded by >= comparison (SQLAlchemy NULL semantics return NULL/falsy) — desired per D-04"
  - "ilike neighborhood filter is provisional per D-05 — will be replaced by coordinate-based Haifa neighborhood polygon matching in Phase 5"
  - "noqa: E712 on Listing.is_active == True — SQLAlchemy column expressions require == not 'is' keyword"
  - "test_run.py at backend root excluded from pytest runs — pre-existing manual debug script; use pytest tests/ not pytest ."

metrics:
  duration: "2 minutes"
  completed_date: "2026-04-02"
  tasks_completed: 2
  files_created: 0
  files_modified: 2
---

# Phase 03 Plan 02: REST API Listings Endpoints Summary

Full GET /listings filter API with price, rooms, neighborhood, recency, seen, favorited params plus PUT seen/favorited mutations; 14 comprehensive tests covering all endpoint behaviors including Hebrew 404 details.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement GET /listings filters + PUT seen/favorited | 2c30dd8 | backend/app/routers/listings.py |
| 2 | Expand test_api.py with comprehensive endpoint tests | 5bbd2b4 | backend/tests/test_api.py |

## What Was Built

- **`backend/app/routers/listings.py`**: Full implementation replacing the stub. `GET /` with 8 query params; base filters always apply `is_active=True` and `llm_confidence >= settings.llm_confidence_threshold`. Dynamic filter list built with `and_(*filters)` then ordered by `created_at.desc()`. `PUT /{id}/seen` and `PUT /{id}/favorited` use `db.get()` for O(1) PK lookup, return 404 with Hebrew detail on miss, commit + refresh on hit.

- **`backend/tests/test_api.py`**: 14 test functions replacing single stub test. Covers: default filter behavior (D-03/D-04), price_max filter, neighborhood ilike filter (D-05), is_seen tri-state filter, rooms_min filter, ordering, mark seen/favorited mutations, 404 Hebrew error detail, GET /health never-run state, GET /health with populated scraper state.

## Verification Results

```
tests/test_api.py tests/test_scheduler.py: 19 passed
tests/ (full suite): 35 passed
routes OK: ['/api/listings/', '/api/listings/{listing_id}/seen', '/api/listings/{listing_id}/favorited']
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. All filter logic is fully implemented. Neighborhood matching via `ilike` is intentionally provisional per D-05 (to be replaced in Phase 5 with coordinate-based polygon matching) — this is a documented design choice, not a stub.

## Self-Check: PASSED
