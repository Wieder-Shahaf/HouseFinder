---
phase: 05-geocoding-dedup-neighborhoods
plan: 05-02
subsystem: backend/geocoding
tags: [geocoding, dedup, scheduler, playwright, google-maps]
dependency_graph:
  requires: [05-01]
  provides: [full-geocoding-module, dedup-pass, scheduler-chain]
  affects: [backend/app/geocoding.py, backend/app/scheduler.py]
tech_stack:
  added: []
  patterns: [playwright-fallback-geocoder, fingerprint-dedup, apscheduler-chain]
key_files:
  created: [backend/tests/test_dedup.py]
  modified: [backend/app/geocoding.py, backend/app/scheduler.py]
decisions:
  - Google Maps Playwright fallback uses http:// when Bright Data proxy is enabled (proxy handles SSL termination)
  - Dedup canonical is first-inserted (lowest id) per D-09 — deterministic, stable across reruns
  - run_dedup_pass uses bulk UPDATE via sqlalchemy update() — single round-trip to DB regardless of duplicate count
metrics:
  duration: 3min
  completed_date: "2026-04-02"
  tasks_completed: 3
  files_changed: 3
---

# Phase 05 Plan 02: Google Maps Fallback + Dedup Pass + Scheduler Chain Summary

## One-liner

Playwright/Google Maps geocoding fallback, fingerprint-based cross-source dedup pass, and APScheduler sequential chain wiring completing the geocoding module.

## What Was Built

### Task 1: Google Maps Playwright Fallback
Added `_geocode_google_maps_fallback(address)` to `backend/app/geocoding.py`. It launches a headless Chromium browser via Playwright, navigates to `google.com/maps/search/`, waits for the URL to rewrite with `@lat,lng`, and extracts coordinates via regex. Integrates with the Bright Data proxy pattern: uses `http://` target when `is_proxy_enabled()` is true. Updated `_geocode_address()` to call this fallback when Nominatim returns None, completing the cascade: Nominatim → Google Maps → None (retry next pass).

### Task 2: Full run_dedup_pass Implementation
Replaced the stub `run_dedup_pass` with a full implementation: queries all active listings with non-NULL `dedup_fingerprint`, `lat`, and `lng`; groups by fingerprint; keeps the lowest-id (first-inserted) listing as canonical per group; bulk-deactivates all others using `sqlalchemy.update()`. Created `backend/tests/test_dedup.py` with 7 integration tests using an in-memory SQLite engine — all pass.

### Task 3: Scheduler Chain Wiring
Extended `run_yad2_scrape_job()` in `backend/app/scheduler.py` to sequentially await `run_geocoding_pass(session)` and `run_dedup_pass(session)` after the Yad2 scrape completes. Imports are deferred (inside the job function) to avoid circular dependencies, consistent with existing patterns.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | fc7a0a0 | feat(05-02): add Google Maps Playwright fallback geocoder |
| 2 | fa890dc | feat(05-02): implement run_dedup_pass and dedup integration tests |
| 3 | 2306c37 | feat(05-02): wire geocoding and dedup passes into Yad2 APScheduler job chain |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all plan goals fully implemented.

## Self-Check: PASSED

- backend/app/geocoding.py exists: FOUND
- backend/app/scheduler.py exists: FOUND
- backend/tests/test_dedup.py exists: FOUND
- Commit fc7a0a0: FOUND
- Commit fa890dc: FOUND
- Commit 2306c37: FOUND
- All 23 tests (test_geocoding.py + test_dedup.py): PASSED
