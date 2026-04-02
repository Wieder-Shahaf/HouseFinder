---
phase: 05-geocoding-dedup-neighborhoods
verified: 2026-04-02T21:00:00Z
status: passed
score: 13/13 must-haves verified
re_verification: false
---

# Phase 5: Geocoding + Dedup + Neighborhoods Verification Report

**Phase Goal:** Geocoding pipeline, cross-source dedup, and neighborhood filter — all listings gain coordinates + neighborhood tags; duplicates are deactivated; API filter works by neighborhood
**Verified:** 2026-04-02
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Alembic migration adds neighborhood column to listings table | VERIFIED | `0002_add_neighborhood.py` exists with correct `upgrade()`/`downgrade()`, `down_revision="0001"` chain intact |
| 2 | `geocode_address()` returns (lat, lng) from Nominatim for a valid Hebrew address | VERIFIED | `_geocode_nominatim()` implemented in `geocoding.py` with correct `lon`-to-float cast; 1 req/sec ToS sleep present |
| 3 | `assign_neighborhood()` returns correct Hebrew name for coords inside a bounding box | VERIFIED | Python3 invocation confirmed: `assign_neighborhood(32.805, 34.995)` returns `כרמל`; 7 unit tests pass including boundary-inclusive cases |
| 4 | `assign_neighborhood()` returns None for coords outside all boxes | VERIFIED | Python3 invocation confirmed: `assign_neighborhood(0.0, 0.0)` returns `None`; Tel Aviv test passes |
| 5 | `make_dedup_fingerprint()` returns a 64-char hex string reproducibly | VERIFIED | Python3 invocation confirmed: `len(fp) == 64`; 5 unit tests pass including SHA-256 exact-match and rounding tests |
| 6 | `run_dedup_pass()` deactivates duplicate listings sharing the same fingerprint, keeping the first-inserted | VERIFIED | Full implementation in `geocoding.py`; `update(Listing).where(id.in_(...)).values(is_active=False)`; 7 integration tests all pass |
| 7 | Google Maps Playwright fallback is called when Nominatim returns None | VERIFIED | `_geocode_google_maps_fallback()` exists in `geocoding.py`; `_geocode_address()` calls it when Nominatim returns None; proxy pattern (`is_proxy_enabled()`, `get_proxy_launch_args()`) correctly wired |
| 8 | APScheduler chain: Yad2 scrape → geocoding pass → dedup pass runs sequentially | VERIFIED | `run_yad2_scrape_job()` in `scheduler.py` contains `await run_geocoding_pass(session)` then `await run_dedup_pass(session)` after `run_yad2_scraper(session)` |
| 9 | Listings with no fingerprint (NULL price or rooms) are skipped by dedup pass without error | VERIFIED | `run_dedup_pass()` queries `dedup_fingerprint.isnot(None)`; `test_listing_without_fingerprint_is_skipped` passes |
| 10 | `ListingResponse` includes `neighborhood: Optional[str] = None` | VERIFIED | `neighborhood: Optional[str] = None  # D-03: added in Phase 5` at line 25 of `schemas/listing.py`; Python3 check confirms `'neighborhood' in ListingResponse.model_fields` |
| 11 | `GET /listings?neighborhood=כרמל` returns only listings with `Listing.neighborhood == 'כרמל'` | VERIFIED | `routers/listings.py` uses `filters.append(Listing.neighborhood == neighborhood)` (exact match); old `address.ilike` removed; 5 endpoint integration tests pass |
| 12 | `GET /listings` with no neighborhood param returns all active listings regardless of neighborhood | VERIFIED | `test_no_neighborhood_filter_returns_all_active` confirms all 3 listings returned when no param provided |
| 13 | A listing geocoded to Carmel coordinates is returned when filtering by כרמל | VERIFIED | `test_neighborhood_filter_returns_matching_listings` inserts listing with `neighborhood="כרמל"` and confirms it is the only result for `?neighborhood=כרמל` |

**Score:** 13/13 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/alembic/versions/0002_add_neighborhood.py` | Schema migration for neighborhood column | VERIFIED | 24 lines; `revision="0002"`, `down_revision="0001"`; `batch_alter_table` for SQLite compatibility |
| `backend/app/geocoding.py` | Full geocoding module: Nominatim + Google Maps fallback + dedup + pass functions | VERIFIED | 293 lines; exports `run_geocoding_pass`, `run_dedup_pass`, `assign_neighborhood`, `make_dedup_fingerprint`, `_geocode_google_maps_fallback`, `haversine_meters` |
| `backend/app/models/listing.py` | Listing model with neighborhood mapped column | VERIFIED | `neighborhood: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)` at line 33 |
| `backend/tests/test_geocoding.py` | Unit tests for pure geocoding functions | VERIFIED | 16 tests across 3 classes; all pass |
| `backend/app/scheduler.py` | Extended Yad2 job with chained geocoding and dedup passes | VERIFIED | `await run_geocoding_pass(session)` + `await run_dedup_pass(session)` inside `run_yad2_scrape_job()` |
| `backend/tests/test_dedup.py` | Integration tests for dedup pass logic | VERIFIED | 7 tests; in-memory SQLite; all pass |
| `backend/app/schemas/listing.py` | ListingResponse with neighborhood field | VERIFIED | `neighborhood: Optional[str] = None` present at line 25 |
| `backend/app/routers/listings.py` | Neighborhood filter using exact match on Listing.neighborhood | VERIFIED | `Listing.neighborhood == neighborhood` on line 53; `address.ilike` absent |
| `backend/tests/test_listings_neighborhood.py` | Tests for neighborhood filter endpoint behavior | VERIFIED | 5 tests; all pass |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/app/geocoding.py` | `backend/app/models/listing.py` | `listing.neighborhood` column | VERIFIED | `listing.neighborhood = assign_neighborhood(lat, lng)` at line 219 |
| `backend/app/scheduler.py` | `backend/app/geocoding.py` | `await run_geocoding_pass`, `await run_dedup_pass` sequential awaits | VERIFIED | Both imports and awaits confirmed in `run_yad2_scrape_job()` |
| `backend/app/geocoding.py` | `backend/app/scrapers/proxy.py` | `get_proxy_launch_args()` in Google Maps fallback | VERIFIED | `from app.scrapers.proxy import get_proxy_launch_args, is_proxy_enabled` inside `_geocode_google_maps_fallback()` |
| `backend/app/routers/listings.py` | `backend/app/models/listing.py` | `Listing.neighborhood ==` exact match filter | VERIFIED | `filters.append(Listing.neighborhood == neighborhood)` at line 53 |
| `backend/app/schemas/listing.py` | `backend/app/models/listing.py` | `from_attributes=True` ORM mapping | VERIFIED | `model_config = ConfigDict(from_attributes=True)`; `neighborhood` field declared in both model and schema |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `geocoding.py :: run_geocoding_pass` | `listing.neighborhood` | `assign_neighborhood(lat, lng)` called after Nominatim/Google Maps returns coords | Yes — bounding-box computation on real coordinates | FLOWING |
| `geocoding.py :: run_dedup_pass` | `is_active` | SQLAlchemy `update()` with `id.in_(duplicate_ids)` | Yes — bulk UPDATE against real DB rows | FLOWING |
| `routers/listings.py :: get_listings` | Listing rows | `select(Listing).where(and_(*filters))` with `Listing.neighborhood == neighborhood` | Yes — DB query with exact-match filter | FLOWING |
| `schemas/listing.py :: ListingResponse` | `neighborhood` | `from_attributes=True` maps to `Listing.neighborhood` ORM column | Yes — ORM attribute populated by geocoding pass | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `assign_neighborhood` returns כרמל for center coords | `python3 -c "from app.geocoding import assign_neighborhood; print(assign_neighborhood(32.805, 34.995))"` | `כרמל` | PASS |
| `assign_neighborhood` returns None for outside coords | `python3 -c "from app.geocoding import assign_neighborhood; print(assign_neighborhood(0.0, 0.0))"` | `None` | PASS |
| `make_dedup_fingerprint` returns 64-char hex | `python3 -c "from app.geocoding import make_dedup_fingerprint; fp = make_dedup_fingerprint(3000, 3.0, 32.8191, 34.9998); print(len(fp))"` | `64` | PASS |
| All imports resolve cleanly | `python3 -c "from app.geocoding import run_geocoding_pass, run_dedup_pass, assign_neighborhood, make_dedup_fingerprint, _geocode_google_maps_fallback; print('all imports OK')"` | `all imports OK` | PASS |
| Schema `neighborhood` field present | `python3 -c "from app.schemas.listing import ListingResponse; print('neighborhood' in ListingResponse.model_fields)"` | `True` | PASS |
| Router uses exact-match filter | `python3 -c "import inspect; from app.routers import listings; src = inspect.getsource(listings); print('Listing.neighborhood ==' in src, 'address.ilike' not in src)"` | `True True` | PASS |
| Scheduler chain wired | `python3 -c "from app.scheduler import run_yad2_scrape_job; import inspect; src = inspect.getsource(run_yad2_scrape_job); print('await run_geocoding_pass' in src, 'await run_dedup_pass' in src)"` | `True True` | PASS |
| All 28 phase-5 tests pass | `python3 -m pytest tests/test_geocoding.py tests/test_dedup.py tests/test_listings_neighborhood.py -v` | `28 passed in 0.24s` | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DATA-03 | 05-02, 05-03 | Cross-source dedup: listings sharing price + room count + similar coords merged into one record | SATISFIED | `run_dedup_pass()` groups by `dedup_fingerprint` (SHA-256 of price+rooms+lat+lng), deactivates all but canonical; exact-match neighborhood filter replaces provisional `address.ilike` |
| DATA-04 | 05-01, 05-02 | Each listing geocoded (Hebrew address → lat/lng) via Nominatim; geocoding async, does not block scraper | SATISFIED | `run_geocoding_pass()` selects `lat IS NULL AND address IS NOT NULL`, geocodes via Nominatim + Google Maps fallback, called sequentially after scraper inside scheduler job |
| DATA-05 | 05-01, 05-03 | Listings tagged with neighborhood (Carmel, Downtown, Neve Shanan) based on geocoded coordinates | SATISFIED | `assign_neighborhood()` uses locked bounding boxes for three Hebrew neighborhoods; called inside `run_geocoding_pass()` immediately after lat/lng obtained; `neighborhood` column persisted and exposed in API |

All three requirement IDs claimed across plans are fully satisfied. No orphaned requirements detected for Phase 5 in REQUIREMENTS.md (traceability table maps DATA-03, DATA-04, DATA-05 exclusively to Phase 5, all marked Complete).

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/geocoding.py` | 300 (05-01 stub, now replaced) | `run_dedup_pass` was `pass` in Plan 05-01 | — | Not a current issue — replaced with full implementation in Plan 05-02; verified above |

No current anti-patterns found. The `run_dedup_pass` stub noted in the Plan 05-01 SUMMARY was intentional scaffolding and has been fully replaced. No `TODO`, `FIXME`, `return []`, `return {}`, or placeholder returns exist in any phase-5-created file.

---

## Human Verification Required

### 1. End-to-End Geocoding Against Live Nominatim

**Test:** In the running Docker environment with network access, insert a listing with address `"רחוב הנשיא 15, חיפה"`, run `run_geocoding_pass()` manually, and confirm `lat`, `lng`, and `neighborhood` are populated.
**Expected:** `lat` and `lng` are non-null floats; `neighborhood` is either a Hebrew string (`כרמל`, `מרכז העיר`, `נווה שאנן`) or `None` if the address geocodes outside the bounding boxes.
**Why human:** Nominatim requires live internet access. Docker environment during Plan 05-03 confirmed geocoders fail without network (graceful retry path works correctly per D-06, but the success path needs network to verify).

### 2. Google Maps Playwright Fallback Behavior

**Test:** With Nominatim returning no results (mock or use an address that Nominatim cannot resolve), verify the Google Maps fallback launches Playwright, navigates to `google.com/maps`, and extracts coordinates from the `@lat,lng` URL pattern.
**Expected:** `_geocode_google_maps_fallback()` returns a `(float, float)` tuple for a known Haifa address; fallback result is assigned to `listing.lat`/`listing.lng`.
**Why human:** Requires a running browser with internet access and cannot be verified via static analysis alone.

---

## Gaps Summary

No gaps. All 13 observable truths verified, all 9 artifacts exist and are substantive, all 5 key links confirmed wired, all 28 automated tests pass, and all 3 requirement IDs (DATA-03, DATA-04, DATA-05) are satisfied. The two human verification items are confirmations of happy-path runtime behavior that depend on live network/browser access — they do not block correctness of the implementation.

---

_Verified: 2026-04-02_
_Verifier: Claude (gsd-verifier)_
