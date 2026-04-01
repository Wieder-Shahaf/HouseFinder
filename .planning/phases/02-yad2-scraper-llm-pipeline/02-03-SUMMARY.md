---
phase: 02-yad2-scraper-llm-pipeline
plan: 03
subsystem: llm
tags: [python, anthropic, llm, async, tdd, hebrew, testing]

# Dependency graph
requires:
  - phase: 02-yad2-scraper-llm-pipeline
    plan: 01
    provides: Settings.llm_model, Settings.llm_api_key, Settings.llm_confidence_threshold, conftest fixtures, app.llm package
provides:
  - backend/app/llm/verifier.py — verify_listing, batch_verify_listings, merge_llm_fields, LISTING_SCHEMA, VERIFY_PROMPT
  - All 6 LLM requirements verified and passing (LLM-01 through LLM-06)
affects:
  - 02-04 (API integration — can import and call batch_verify_listings after scraping)

# Tech tracking
tech-stack:
  added:
    - anthropic==0.88.0 (Anthropic Python SDK, installed to local dev environment)
  patterns:
    - get_llm_client() factory pattern — AsyncAnthropic client extracted as a function for easy patching in tests
    - asyncio.gather(return_exceptions=True) — partial failure handling for batch LLM calls
    - json_schema structured output via output_config.format — eliminates retry logic
    - scraper-wins merge strategy — non-null scraper fields take precedence over LLM

key-files:
  created:
    - backend/app/llm/verifier.py
  modified:
    - backend/tests/test_llm_verifier.py

key-decisions:
  - "get_llm_client() factory function extracted for mockability — tests patch this instead of anthropic module directly"
  - "AsyncAnthropic (not sync Anthropic) used to avoid blocking event loop inside asyncio.gather"
  - "output_config.format json_schema used for structured output — no retry logic needed, guaranteed valid JSON"
  - "batch_verify_listings exceptions converted to rejection dicts inline — callers receive list of same length as input"

# Metrics
duration: ~10min
completed: 2026-04-02
---

# Phase 2 Plan 03: LLM Verifier Summary

**AsyncAnthropic-based LLM verifier using json_schema structured output and asyncio.gather batch processing for Hebrew rental listing classification and field extraction**

## Performance

- **Duration:** ~10 min
- **Completed:** 2026-04-02
- **Tasks:** 1 of 1 complete
- **Files modified:** 2

## Accomplishments

- Implemented `backend/app/llm/verifier.py` with all required exports: `verify_listing`, `batch_verify_listings`, `merge_llm_fields`, `LISTING_SCHEMA`, `VERIFY_PROMPT`, `get_llm_client`
- All 6 LLM requirement tests pass (LLM-01 through LLM-06)
- `verify_listing()` calls Claude with Hebrew-aware prompt and json_schema structured output via `output_config.format`
- `batch_verify_listings()` uses `asyncio.gather(return_exceptions=True)` for concurrent LLM calls; exceptions are converted to rejection dicts without aborting the batch
- `merge_llm_fields()` implements scraper-wins precedence: non-null scraper fields preserved, LLM fills nulls, `llm_confidence` always set
- Error handling: LLM exceptions produce a safe rejection dict with `is_rental=False` and error message in `rejection_reason`
- TDD flow followed: RED (tests written, skipped due to missing module) → GREEN (implementation, all 6 pass)

## Task Commits

1. **RED: Failing tests for LLM verifier** - `2e2c32a` (test)
2. **GREEN: LLM verifier implementation** - `27b99ba` (feat)

## Files Created/Modified

- `backend/app/llm/verifier.py` — Full LLM pipeline: `verify_listing`, `batch_verify_listings`, `merge_llm_fields`, `LISTING_SCHEMA`, `VERIFY_PROMPT`, `get_llm_client`
- `backend/tests/test_llm_verifier.py` — All 6 tests implemented (replaced stub implementations)

## Decisions Made

- `get_llm_client()` extracted as a factory function — this enables `@patch("app.llm.verifier.get_llm_client")` in tests without patching deep into the anthropic module
- `AsyncAnthropic` (async client) used instead of synchronous `Anthropic` — avoids blocking the event loop when multiple LLM calls are gathered concurrently (Pitfall 3 from RESEARCH.md)
- `output_config.format` with `json_schema` guarantees valid JSON responses — no retry logic or JSON parsing error handling needed
- Exceptions in `batch_verify_listings` converted to rejection dicts inline: callers always receive a list of the same length as input, with no exceptions to handle

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all functions are fully implemented. `verify_listing` makes real Anthropic API calls (mocked in tests). No hardcoded placeholder data.

## Next Phase Readiness

- Plan 04 (API endpoint integration) can import `batch_verify_listings` and `merge_llm_fields` directly
- The verifier is APScheduler-compatible: `run_yad2_scraper` (Plan 02) can call `batch_verify_listings` after collecting raw listings
- `settings.llm_confidence_threshold` (0.7) is respected in batch logging; the caller (Plan 04) uses `result["confidence"]` to set `llm_confidence` on Listing rows

---
*Phase: 02-yad2-scraper-llm-pipeline*
*Completed: 2026-04-02*
