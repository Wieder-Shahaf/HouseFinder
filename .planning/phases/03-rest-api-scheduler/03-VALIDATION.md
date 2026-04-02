---
phase: 3
slug: rest-api-scheduler
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-02
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | `backend/pytest.ini` (`asyncio_mode = auto`) |
| **Quick run command** | `cd backend && pytest tests/test_api.py tests/test_scheduler.py -x -q` |
| **Full suite command** | `cd backend && pytest -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/test_api.py tests/test_scheduler.py -x -q`
- **After every plan wave:** Run `cd backend && pytest -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 0 | SCHED-01 | unit | `cd backend && pytest tests/test_scheduler.py::test_job_registered_with_correct_interval -x` | ❌ W0 | ⬜ pending |
| 3-01-02 | 01 | 0 | SCHED-02 | unit | `cd backend && pytest tests/test_scheduler.py::test_job_max_instances_is_one -x` | ❌ W0 | ⬜ pending |
| 3-01-03 | 01 | 0 | SCHED-03 | integration | `cd backend && pytest tests/test_scheduler.py::test_scheduler_lifecycle -x` | ❌ W0 | ⬜ pending |
| 3-02-01 | 02 | 0 | API | unit | `cd backend && pytest tests/test_api.py::test_get_listings_default -x` | ❌ W0 | ⬜ pending |
| 3-02-02 | 02 | 0 | API | unit | `cd backend && pytest tests/test_api.py::test_get_listings_price_filter -x` | ❌ W0 | ⬜ pending |
| 3-02-03 | 02 | 0 | API | unit | `cd backend && pytest tests/test_api.py::test_get_listings_neighborhood_filter -x` | ❌ W0 | ⬜ pending |
| 3-02-04 | 02 | 0 | API | unit | `cd backend && pytest tests/test_api.py::test_get_listings_excludes_low_confidence -x` | ❌ W0 | ⬜ pending |
| 3-03-01 | 03 | 0 | API | unit | `cd backend && pytest tests/test_api.py::test_mark_seen -x` | ❌ W0 | ⬜ pending |
| 3-03-02 | 03 | 0 | API | unit | `cd backend && pytest tests/test_api.py::test_mark_favorited -x` | ❌ W0 | ⬜ pending |
| 3-03-03 | 03 | 0 | API | unit | `cd backend && pytest tests/test_api.py::test_mark_seen_not_found -x` | ❌ W0 | ⬜ pending |
| 3-04-01 | 04 | 0 | API | unit | `cd backend && pytest tests/test_api.py::test_health_with_scraper_state -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_scheduler.py` — stubs for SCHED-01, SCHED-02, SCHED-03 (scheduler unit tests with mocked job function)
- [ ] `backend/tests/test_api.py` — expand from current 1-test stub to full listings filter + mutation + health tests
- [ ] `backend/tests/conftest.py` — client fixture needs scheduler mock to prevent real job execution during tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| First scrape fires immediately on startup | D-01 | Requires live process observation | Start backend, check logs within 5s for "yad2 scrape started" |
| Scheduler respects 2-hour interval in production | SCHED-01 | Long-running time test impractical | Verify APScheduler job config: `hours=2`, `next_run_time=datetime.now()` in code review |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
