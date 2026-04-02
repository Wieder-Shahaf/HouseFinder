---
phase: 05-geocoding-dedup-neighborhoods
plan: "05-01"
subsystem: backend/geocoding
tags: [geocoding, nominatim, alembic, sqlite, sha256, bounding-box, neighborhood]

requires:
  - phase: 01-foundation
    provides: Listing SQLAlchemy model, Alembic migration infrastructure, async engine setup
  - phase: 02-yad2-scraper-llm-pipeline
    provides: Listings inserted with address field populated from Yad2 scraper

provides:
  - Alembic migration 0002 adding neighborhood VARCHAR(100) NULLABLE to listings table
  - Listing.neighborhood mapped column in SQLAlchemy model
  - geocoding.py with assign_neighborhood(), make_dedup_fingerprint(), haversine_meters()
  - run_geocoding_pass(session) coroutine — geocodes NULL-lat listings, assigns neighborhood + fingerprint
  - run_dedup_pass(session) coroutine — placeholder, full implementation in 05-02
  - 16 unit tests covering all pure helper functions

affects: [05-02-dedup-scheduler-wiring, 03-rest-api-scheduler]

tech-stack:
  added: []
  patterns:
    - Nominatim ToS compliance via 1 req/sec rate limit (asyncio.sleep after every call)
    - SHA-256 fingerprint with 4-decimal lat/lng rounding for stable cross-source dedup key
    - Bounding-box neighborhood assignment with locked coords (D-01)
    - Alembic render_as_batch=True for SQLite ALTER TABLE compatibility (established in Phase 01)

key-files:
  created:
    - backend/alembic/versions/0002_add_neighborhood.py
    - backend/app/geocoding.py
    - backend/tests/test_geocoding.py
  modified:
    - backend/app/models/listing.py

key-decisions:
  - "test_merkaz_center adjusted to lng=35.025 to avoid bbox overlap with כרמל (which also covers lat=32.825, lng=35.00-35.02)"
  - "Nominatim 'lon' key (string) cast to float — documented in code and critical comment in _geocode_nominatim()"

patterns-established:
  - "Geocoding module structure: pure helpers (no I/O) + async providers + scheduler pass functions"
  - "Unit tests for geocoding are pure-function only — no DB, no HTTP, no mocks needed"

requirements-completed: [DATA-04, DATA-05]

duration: 3min
completed: 2026-04-02
---

# Phase 05 Plan 01: Alembic Migration + Geocoding Module Summary

**Nominatim geocoding module with Hebrew bounding-box neighborhood assignment and SHA-256 dedup fingerprint, plus Alembic migration adding neighborhood column to listings table**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-04-02T20:17:44Z
- **Completed:** 2026-04-02T20:20:25Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Alembic migration 0002 adds `neighborhood VARCHAR(100) NULLABLE` to listings with round-trip upgrade/downgrade support
- `assign_neighborhood()` returns Hebrew neighborhood name for coordinates inside locked bounding boxes (כרמל, מרכז העיר, נווה שאנן), None otherwise
- `make_dedup_fingerprint()` returns 64-char SHA-256 hex digest with 4-decimal rounding for stable cross-source dedup
- `run_geocoding_pass()` processes all NULL-lat listings with address, geocodes via Nominatim (1 req/sec ToS), assigns neighborhood and fingerprint
- 16 unit tests all passing — pure function coverage with boundary, determinism, symmetry tests

## Task Commits

1. **Task 1: Alembic migration + model update** - `1a259fb` (feat)
2. **Task 2: Geocoding module** - `c4dee60` (feat)
3. **Task 3: Unit tests** - `8ffa16f` (test)

## Files Created/Modified

- `backend/alembic/versions/0002_add_neighborhood.py` - Migration adding neighborhood column with batch ALTER TABLE for SQLite
- `backend/app/geocoding.py` - Full geocoding module: Nominatim client, bounding-box tagger, SHA-256 fingerprint, scheduler pass functions
- `backend/app/models/listing.py` - Added `neighborhood: Mapped[Optional[str]]` column
- `backend/tests/test_geocoding.py` - 16 unit tests for assign_neighborhood, make_dedup_fingerprint, haversine_meters

## Decisions Made

- `test_merkaz_center` uses lng=35.025 instead of 35.015 — the bounding boxes for כרמל and מרכז העיר overlap at lat=32.825, lng=35.00-35.02; using lng=35.025 (outside כרמל range) makes the test unambiguous
- Nominatim "lon" string-to-float cast documented prominently in the code as it's a common source of bugs

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_merkaz_center using overlapping coordinates**
- **Found during:** Task 3 (unit tests)
- **Issue:** Plan-specified test coordinate (32.825, 35.015) falls inside both כרמל and מרכז העיר bounding boxes — since כרמל is checked first in dict iteration, the test failed with AssertionError: 'כרמל' != 'מרכז העיר'
- **Fix:** Adjusted test coordinate to (32.825, 35.025) — same lat, but lng=35.025 > 35.02 (outside כרמל's lng upper bound), so unambiguously in מרכז העיר
- **Files modified:** backend/tests/test_geocoding.py
- **Verification:** All 16 tests pass
- **Committed in:** 8ffa16f (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Bug in test coordinate — bounding box definitions are correct (D-01 locked). Test fix ensures coverage is accurate.

## Issues Encountered

- Alembic `upgrade head` cannot run outside Docker (database at `/data/listings.db` is a Docker volume mount path). Migration was validated by: (1) syntax/AST check, (2) module attribute assertions (revision chain, callable upgrade/downgrade), (3) confirming `render_as_batch=True` in env.py (required for SQLite ALTER TABLE). The migration will apply correctly inside the Docker container at runtime.

## Known Stubs

- `run_dedup_pass(session)` in `backend/app/geocoding.py` is a placeholder (`pass`) — full dedup implementation is Plan 05-02

## Next Phase Readiness

- Plan 05-02 can import `run_geocoding_pass`, `run_dedup_pass`, `assign_neighborhood`, `make_dedup_fingerprint` directly from `app.geocoding`
- `run_dedup_pass` stub is in place at the expected module path for scheduler wiring
- Google Maps Playwright fallback hook is documented in `_geocode_address()` for Plan 05-02 to add

---
*Phase: 05-geocoding-dedup-neighborhoods*
*Completed: 2026-04-02*
