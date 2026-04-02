---
phase: 05-geocoding-dedup-neighborhoods
plan: 05-03
subsystem: backend/api
tags: [schema, router, filter, neighborhood, tests, end-to-end]
depends_on: [05-01, 05-02]
provides: [ListingResponse.neighborhood, neighborhood-exact-filter, neighborhood-test-suite]
affects: [frontend-map-filter]
tech_stack:
  patterns: [exact-match-filter, pydantic-from_attributes, asyncio-testclient]
key_files:
  modified:
    - backend/app/schemas/listing.py
    - backend/app/routers/listings.py
  created:
    - backend/tests/test_listings_neighborhood.py
decisions:
  - "from __future__ import annotations added to test file for Python 3.9 str|None union syntax compatibility"
  - "neighborhood filter comment updated to not reference address.ilike to keep verification assertions clean"
metrics:
  duration: "~4 min"
  completed_date: "2026-04-02"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 3
status: complete
---

# Phase 05 Plan 03: Router + Schema Update + End-to-End Verification Summary

**One-liner:** ListingResponse exposes `neighborhood` field; `GET /listings?neighborhood=X` now uses exact-match on geocoded `Listing.neighborhood` column; 5 integration tests verify all filter behaviors; end-to-end pipeline confirmed working in Docker.

## Tasks Completed

### Task 1: Update ListingResponse schema + neighborhood filter (commit: c34dde0)

Added `neighborhood: Optional[str] = None` to `ListingResponse` in `backend/app/schemas/listing.py` after the `address` field. Replaced the provisional `Listing.address.ilike(f"%{neighborhood}%")` filter in `backend/app/routers/listings.py` with `Listing.neighborhood == neighborhood` exact match.

**Files modified:**
- `backend/app/schemas/listing.py` — added `neighborhood: Optional[str] = None  # D-03: added in Phase 5`
- `backend/app/routers/listings.py` — replaced `address.ilike` filter block with exact-match on `Listing.neighborhood`

**Verification passed:**
- `'neighborhood' in ListingResponse.model_fields` → `True`
- `'Listing.neighborhood ==' in src` → `exact match filter present`
- `'address.ilike' not in src` → `old filter removed`

### Task 2: Neighborhood filter integration tests (commit: e4d3d2f)

Created `backend/tests/test_listings_neighborhood.py` with 5 async integration tests using `httpx.AsyncClient` + `ASGITransport` against an in-memory SQLite database.

**Tests:**
1. `test_neighborhood_filter_returns_matching_listings` — filter returns only matching neighborhood
2. `test_no_neighborhood_filter_returns_all_active` — no param returns all 3 active listings
3. `test_neighborhood_filter_no_match_returns_empty` — filter on absent neighborhood returns `[]`
4. `test_neighborhood_field_present_in_response` — `neighborhood` key present in JSON response
5. `test_null_neighborhood_listing_not_returned_when_filtering` — NULL neighborhood excluded from filtered results

**All 28 tests pass** (16 geocoding + 7 dedup + 5 neighborhood).

### Task 3: End-to-end manual verification checkpoint (APPROVED)

Human verified the full Phase 5 pipeline end-to-end:

- Migration 0002 applied successfully on the running Docker DB
- `neighborhood` field confirmed present in API response JSON
- `GET /listings?neighborhood=כרמל` returns 200 (empty result expected — geocoders fail in Docker environment but pipeline handles it gracefully per D-06)
- Geocoding pass ran cleanly with graceful fallback (lat stays NULL, retry next pass when network is available)

**Outcome:** Pipeline is correct. Geocoders cannot resolve addresses inside Docker without internet access, but the error-handling path is confirmed working and listings are not lost.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Python 3.9 union type syntax incompatibility**
- **Found during:** Task 2 test collection
- **Issue:** Plan template used `str | None` union syntax (Python 3.10+); system runs Python 3.9.6
- **Fix:** Added `from __future__ import annotations` import at top of test file (enables PEP 604 syntax in annotations for Python 3.9)
- **Files modified:** `backend/tests/test_listings_neighborhood.py`
- **Commit:** e4d3d2f

**2. [Rule 1 - Bug] Comment in router contained 'address.ilike' string**
- **Found during:** Task 1 verification
- **Issue:** Plan's verification script asserts `'address.ilike' not in src`; the replacement comment text in the plan contained `address.ilike` in the comment text
- **Fix:** Updated comment to say "replaces provisional text search" instead
- **Files modified:** `backend/app/routers/listings.py`
- **Commit:** c34dde0

## Known Stubs

None — all fields are wired to the ORM model. The `neighborhood` field in `ListingResponse` maps via `from_attributes=True` to `Listing.neighborhood` which is populated by the geocoding pass from Plan 05-02.

## Self-Check: PASSED

- `backend/app/schemas/listing.py` — exists, `neighborhood` field present
- `backend/app/routers/listings.py` — exists, exact-match filter in place
- `backend/tests/test_listings_neighborhood.py` — exists, 5 tests
- Commits c34dde0 and e4d3d2f confirmed in git log
- Task 3 checkpoint approved by human

---
*Phase: 05-geocoding-dedup-neighborhoods*
*Completed: 2026-04-02*
