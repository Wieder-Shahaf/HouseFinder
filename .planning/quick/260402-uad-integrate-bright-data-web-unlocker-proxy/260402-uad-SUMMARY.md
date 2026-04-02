---
phase: quick
plan: 260402-uad
subsystem: backend/scrapers
tags: [proxy, bright-data, playwright, yad2, captcha-bypass]
dependency_graph:
  requires: []
  provides: [proxy-config-module, yad2-proxy-integration]
  affects: [backend/app/scrapers/yad2.py, backend/app/config.py]
tech_stack:
  added: []
  patterns: [optional-env-var-feature-flag, kwargs-unpacking-for-zero-cost-abstraction]
key_files:
  created:
    - backend/app/scrapers/proxy.py
  modified:
    - backend/app/config.py
    - backend/app/scrapers/yad2.py
decisions:
  - "Proxy helper returns empty dict when unconfigured — unpacks to nothing in Playwright kwargs, so no conditional branches needed at call sites"
  - "http:// scheme substitution scoped to Playwright browser path only — httpx API path unchanged"
  - "Captcha retry block also receives proxy args — proxy must persist across both Playwright contexts"
metrics:
  duration: 5min
  completed: "2026-04-02"
  tasks: 2
  files: 3
---

# Quick Task 260402-uad: Integrate Bright Data Web Unlocker Proxy — Summary

**One-liner:** Optional Bright Data Web Unlocker proxy wired into Yad2 Playwright fallback via shared `proxy.py` helper, with http:// scheme auto-conversion and graceful no-op when env vars absent.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add proxy config to Settings and create shared proxy helper | fd7607e | backend/app/config.py, backend/app/scrapers/proxy.py |
| 2 | Wire proxy into Yad2 Playwright fallback and use http:// scheme | 9f341c7 | backend/app/scrapers/yad2.py |

## What Was Built

### `backend/app/scrapers/proxy.py` (new)

Shared proxy config module with two functions:

- `get_proxy_launch_args() -> dict` — returns `{"proxy": {...}}` when all three Bright Data env vars are set, empty dict otherwise. Designed to be unpacked directly into `launch_persistent_context(**get_proxy_launch_args())` — zero cost when proxy is disabled.
- `is_proxy_enabled() -> bool` — boolean check for conditional logic (e.g. URL scheme conversion).

### `backend/app/config.py` (modified)

Three new optional `Settings` fields (all default to empty string):
- `bright_data_host` — proxy server address, e.g. `brd.superproxy.io:33335`
- `bright_data_user` — proxy username
- `bright_data_pass` — proxy password

Set via environment variables `BRIGHT_DATA_HOST`, `BRIGHT_DATA_USER`, `BRIGHT_DATA_PASS`.

### `backend/app/scrapers/yad2.py` (modified)

- Imports `get_proxy_launch_args` and `is_proxy_enabled` from `app.scrapers.proxy`
- Both `launch_persistent_context` calls (initial fetch + captcha retry) now unpack `**get_proxy_launch_args()`
- URL scheme downgraded from `https://` to `http://` when proxy is active (Web Unlocker SSL termination requirement)
- Proxy status logged at browser launch time
- httpx path (`fetch_yad2_api`) untouched — proxy only needed for the browser/CAPTCHA path

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all wiring is complete. Proxy activates automatically when env vars are present.

## Verification Results

All three plan verification checks passed:
1. `get_proxy_launch_args()` returns `{}` when no env vars set
2. `from app.scrapers.yad2 import run_yad2_scraper` — no import errors
3. AST parse clean on both `yad2.py` and `proxy.py`

## Self-Check: PASSED

Files exist:
- `/Users/shahafwieder/HouseFinder/backend/app/scrapers/proxy.py` — FOUND
- `/Users/shahafwieder/HouseFinder/backend/app/config.py` — FOUND (modified)
- `/Users/shahafwieder/HouseFinder/backend/app/scrapers/yad2.py` — FOUND (modified)

Commits exist:
- `fd7607e` — FOUND
- `9f341c7` — FOUND
