---
phase: 2
slug: yad2-scraper-llm-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| **Quick run command** | `cd backend && python -m pytest tests/test_yad2.py tests/test_llm_pipeline.py -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_yad2.py tests/test_llm_pipeline.py -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 0 | YAD2-01 | unit | `pytest tests/test_yad2.py -x -q` | ❌ W0 | ⬜ pending |
| 2-01-02 | 01 | 1 | YAD2-02 | unit | `pytest tests/test_yad2.py::test_fetch -x -q` | ❌ W0 | ⬜ pending |
| 2-01-03 | 01 | 1 | YAD2-03 | unit | `pytest tests/test_yad2.py::test_filter -x -q` | ❌ W0 | ⬜ pending |
| 2-01-04 | 01 | 2 | YAD2-04 | unit | `pytest tests/test_yad2.py::test_error_handling -x -q` | ❌ W0 | ⬜ pending |
| 2-02-01 | 02 | 0 | LLM-01 | unit | `pytest tests/test_llm_pipeline.py -x -q` | ❌ W0 | ⬜ pending |
| 2-02-02 | 02 | 1 | LLM-02 | unit | `pytest tests/test_llm_pipeline.py::test_extraction -x -q` | ❌ W0 | ⬜ pending |
| 2-02-03 | 02 | 1 | LLM-03 | unit | `pytest tests/test_llm_pipeline.py::test_rejection -x -q` | ❌ W0 | ⬜ pending |
| 2-02-04 | 02 | 2 | LLM-04 | unit | `pytest tests/test_llm_pipeline.py::test_confidence -x -q` | ❌ W0 | ⬜ pending |
| 2-02-05 | 02 | 2 | LLM-05 | unit | `pytest tests/test_llm_pipeline.py::test_batch -x -q` | ❌ W0 | ⬜ pending |
| 2-02-06 | 02 | 2 | LLM-06 | manual | Manual: run scraper end-to-end, verify listings appear | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_yad2.py` — stubs for YAD2-01, YAD2-02, YAD2-03, YAD2-04
- [ ] `backend/tests/test_llm_pipeline.py` — stubs for LLM-01 through LLM-06
- [ ] `backend/tests/conftest.py` — shared fixtures (mock httpx responses, mock Anthropic client)
- [ ] pytest installed in backend dev dependencies

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Yad2 API endpoint discovery | YAD2-01 | Requires browser DevTools inspection of live site — cannot automate | Open yad2.co.il/realestate/rent in browser, open DevTools Network tab, filter XHR, note URL and query params |
| End-to-end scraper → DB flow | LLM-06 | Requires live Yad2 API + live Anthropic API | Run `python -m backend.scrapers.yad2_scraper`, verify rows in SQLite via `sqlite3 dev.db "SELECT COUNT(*) FROM listings WHERE source='yad2'"` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
