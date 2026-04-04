---
phase: 08-facebook-scrapers
plan: "01"
subsystem: backend/scrapers
tags: [facebook, playwright, stealth, session-management, llm-verification, web-push]
dependency_graph:
  requires:
    - backend/app/llm/verifier.py (batch_verify_listings, merge_llm_fields)
    - backend/app/notifier.py (webpush via pywebpush)
    - backend/app/scrapers/base.py (ScraperResult)
    - backend/app/scrapers/proxy.py (get_proxy_launch_args)
    - backend/app/config.py (Settings)
    - backend/app/models/listing.py (Listing)
  provides:
    - backend/app/scrapers/facebook_groups.py (run_facebook_groups_scraper, check_session_health, _load_fb_context)
    - backend/app/notifier.py send_session_expiry_alert function
    - backend/app/config.py facebook_session_path setting
  affects:
    - backend/app/scheduler.py (will register facebook_groups source in Phase 8 plan 3)
tech_stack:
  added:
    - playwright-stealth (Stealth().apply_stealth_async) for Facebook bot detection evasion
  patterns:
    - Playwright persistent session (storage_state) for authenticated Facebook access
    - Session health check before scraping with Web Push expiry alert
    - LLM verification pipeline (batch_verify_listings + merge_llm_fields) for free-form Hebrew posts
    - sqlite_insert.on_conflict_do_nothing for source/source_id deduplication
key_files:
  created:
    - backend/app/scrapers/facebook_groups.py
    - backend/tests/test_facebook_scrapers.py
  modified:
    - backend/app/config.py (added facebook_session_path)
    - backend/app/notifier.py (added send_session_expiry_alert)
decisions:
  - "Facebook scraper uses headless=True locally for Docker; production deployment on VPS must use Xvfb + headless=False for stealth"
  - "FACEBOOK_VERIFY_PROMPT is a local copy of VERIFY_PROMPT with Facebook-specific preamble — avoids modifying shared verifier.py"
  - "Session health check uses dual signals: URL contains 'login'/'checkpoint' OR LeftRail element count > 0"
  - "source_id fallback is sha256[:32] of post_text[:200] — sufficient entropy, no collision risk for same-group posts"
  - "Flagged listings (low LLM confidence) are inserted rather than dropped — keeps data for user review"
metrics:
  duration: "4 minutes"
  completed_date: "2026-04-04"
  tasks: 2
  files_changed: 4
---

# Phase 08 Plan 01: Facebook Groups Scraper Summary

Facebook Groups scraper with Playwright stealth session management, health-check expiry alerting, and LLM verification pipeline for free-form Hebrew rental posts.

## What Was Built

**Task 1: Scraper module + config + notifier (commit `64c51db`)**

- `backend/app/scrapers/facebook_groups.py` — full scraper matching Yad2/Madlan pattern:
  - `_load_groups()` — reads `/data/facebook_groups.json`, returns list of `{url, name}` dicts; gracefully returns `[]` on missing/empty file
  - `_load_fb_context()` — launches Chromium with saved `storage_state`, Hebrew locale, viewport, and `playwright-stealth` applied
  - `check_session_health()` — navigates to facebook.com, checks for login/checkpoint redirect + LeftRail element presence
  - `extract_post_source_id()` — extracts numeric post ID from permalink/posts URL pattern; falls back to sha256[:32] hash
  - `run_facebook_groups_scraper()` — main scraper: loads groups, checks session, iterates groups with 5-15s inter-group delay, scrolls 3-5x per group, extracts `[role="article"]` elements, runs LLM batch verification, inserts with dedup
- `backend/app/config.py` — added `facebook_session_path: str = "/data/facebook_session.json"` (Phase 8)
- `backend/app/notifier.py` — added `send_session_expiry_alert()` sending Hebrew Web Push ("פייסבוק דורש התחברות מחדש")

**Task 2: Unit tests (commit `d9434f5`)**

- `backend/tests/test_facebook_scrapers.py` — 16 tests covering:
  - Group config loading (missing/empty/valid file)
  - Session loading (storage_state, stealth, locale)
  - Session health check (login redirect, checkpoint redirect, valid session)
  - Post URL parsing (permalink ID, posts ID, fallback hash, determinism)
  - Session expiry clean return path (success=True, alert sent)
  - Session file missing handling
  - Failure isolation (unhandled error → success=False)
  - Empty groups graceful handling (D-03)

## Decisions Made

1. `headless=True` in Docker for dev; production VPS needs `headless=False + Xvfb` — documented as known difference
2. `FACEBOOK_VERIFY_PROMPT` is a local copy of `VERIFY_PROMPT` adapted for informal Facebook posts — avoids coupling to verifier.py's Yad2-specific prompt
3. Session health check uses two signals: URL contains `login`/`checkpoint` OR LeftRail element missing
4. Fallback `source_id` = `sha256[:32]` of `post_text[:200]` — deterministic, sufficient entropy
5. Low-confidence verified rentals are inserted (not dropped) to preserve data for user review

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — scraper is complete. The scheduler integration (registering `facebook_groups` as a source) is deferred to Phase 8 plan 3 (scheduler integration plan), which is the correct separation of concerns.

## Self-Check: PASSED
