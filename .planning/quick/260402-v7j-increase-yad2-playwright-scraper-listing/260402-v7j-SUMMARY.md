---
phase: quick
plan: 260402-v7j
subsystem: backend/scrapers
tags: [yad2, playwright, scraping, scroll, lazy-load]
dependency_graph:
  requires: []
  provides: [yad2-scroll-to-load]
  affects: [fetch_yad2_browser]
tech_stack:
  added: []
  patterns: [incremental-scroll-to-load, early-exit-on-stable-height]
key_files:
  modified:
    - backend/app/scrapers/yad2.py
decisions:
  - "Initial wait reduced from 5000ms to 3000ms; scrolling handles subsequent content loads"
  - "MAX_SCROLLS=10, SCROLL_PAUSE_MS=2000, INITIAL_WAIT_MS=3000 as local constants in function body"
  - "Early exit when document.body.scrollHeight unchanged between iterations"
metrics:
  duration: "3min"
  completed: "2026-04-02"
  tasks: 1
  files: 1
---

# Phase quick Plan 260402-v7j: Increase Yad2 Playwright Scraper Listing Yield Summary

**One-liner:** Added incremental scroll-to-bottom loop (max 10 iterations, 2s pause, early exit on stable height) to `fetch_yad2_browser` to trigger Yad2's lazy-loaded infinite-scroll listings instead of capturing only the ~3 above-the-fold items.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Add scroll-to-load loop to fetch_yad2_browser | 00c47a2 | backend/app/scrapers/yad2.py |

## What Was Built

The `fetch_yad2_browser` function in `backend/app/scrapers/yad2.py` was modified to scroll the Yad2 SPA page incrementally before capturing the rendered HTML:

1. After `page.goto()`, waits 3 seconds for initial JS hydration (was 5 seconds).
2. Runs a scroll loop up to `MAX_SCROLLS = 10` times:
   - Evaluates `document.body.scrollHeight` before each scroll.
   - Executes `window.scrollTo(0, document.body.scrollHeight)`.
   - Waits `SCROLL_PAUSE_MS = 2000`ms for new content to render.
   - Compares new height to previous — breaks early if unchanged.
   - Logs progress: `[yad2] Scroll {i}: page height {prev} -> {new}`.
3. Scrolls back to top and waits 1 second for final render settle.
4. Calls `page.content()` to capture the fully-loaded HTML.

All existing captcha detection, `__NEXT_DATA__` parsing, `_parse_html_listings`, and all other functions remain unchanged.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- Modified file exists: backend/app/scrapers/yad2.py - FOUND
- Commit 00c47a2 exists - FOUND
- Syntax check: PASSED
- Scroll constants present (MAX_SCROLLS, SCROLL_PAUSE_MS, INITIAL_WAIT_MS): CONFIRMED
- scrollTo and scrollHeight present: CONFIRMED
- Captcha block and _parse_html_listings untouched: CONFIRMED
