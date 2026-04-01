---
phase: 2
slug: yad2-scraper-llm-pipeline
status: active
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-02
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | backend/pytest.ini or pyproject.toml — Wave 0 installs |
| **Quick run command** | `cd backend && python -m pytest tests/test_yad2_scraper.py tests/test_llm_verifier.py -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_yad2_scraper.py tests/test_llm_verifier.py -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 0 | YAD2-01 | unit | `pytest tests/test_yad2_scraper.py -x -q` | ❌ W0 | ⬜ pending |
| 2-01-02 | 01 | 1 | YAD2-02 | unit | `pytest tests/test_yad2_scraper.py::test_scraper_extracts_all_required_fields -x -q` | ❌ W0 | ⬜ pending |
| 2-01-03 | 01 | 1 | YAD2-03 | unit | `pytest tests/test_yad2_scraper.py::test_playwright_fallback_on_httpx_403 -x -q` | ❌ W0 | ⬜ pending |
| 2-01-04 | 01 | 2 | YAD2-04 | unit | `pytest tests/test_yad2_scraper.py::test_scraper_error_isolation_returns_scraper_result -x -q` | ❌ W0 | ⬜ pending |
| 2-02-01 | 03 | 0 | LLM-01 | unit | `pytest tests/test_llm_verifier.py -x -q` | ❌ W0 | ⬜ pending |
| 2-02-02 | 03 | 1 | LLM-02 | unit | `pytest tests/test_llm_verifier.py::test_extracts_structured_fields_from_hebrew -x -q` | ❌ W0 | ⬜ pending |
| 2-02-03 | 03 | 1 | LLM-03 | unit | `pytest tests/test_llm_verifier.py::test_confidence_below_threshold_flagged_not_deleted -x -q` | ❌ W0 | ⬜ pending |
| 2-02-04 | 03 | 2 | LLM-04 | unit | `pytest tests/test_llm_verifier.py::test_llm_fields_supplement_scraper_fields -x -q` | ❌ W0 | ⬜ pending |
| 2-02-05 | 03 | 2 | LLM-05 | unit | `pytest tests/test_llm_verifier.py::test_batch_verify_uses_gather -x -q` | ❌ W0 | ⬜ pending |
| 2-02-06 | 03 | 2 | LLM-06 | unit | `pytest tests/test_llm_verifier.py::test_model_is_configurable_default_haiku -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_yad2_scraper.py` — stubs for YAD2-01, YAD2-02, YAD2-03, YAD2-04
- [ ] `backend/tests/test_llm_verifier.py` — stubs for LLM-01 through LLM-06
- [ ] `backend/tests/conftest.py` — shared fixtures (mock httpx responses, mock Anthropic client)
- [ ] pytest installed in backend dev dependencies

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Yad2 API endpoint discovery | YAD2-01 | Requires browser DevTools inspection of live site — cannot automate | Open yad2.co.il/realestate/rent in browser, open DevTools Network tab, filter XHR, note URL and query params. Also check for neighborhood filter params. |
| End-to-end scraper → DB flow | LLM-06 | Requires live Yad2 API + live Anthropic API | Run `python -m backend.scrapers.yad2_scraper`, verify rows in SQLite via `sqlite3 dev.db "SELECT COUNT(*) FROM listings WHERE source='yad2'"` |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending execution
