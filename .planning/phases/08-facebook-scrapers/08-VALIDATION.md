---
phase: 8
slug: facebook-scrapers
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-04
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | `backend/pytest.ini` (`asyncio_mode = auto`) |
| **Quick run command** | `cd backend && python -m pytest tests/test_facebook_scrapers.py -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_facebook_scrapers.py -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 08-W0-01 | 01 | 0 | FBGR-01..FBMP-04 | unit stubs | `cd backend && python -m pytest tests/test_facebook_scrapers.py -x -q` | ❌ W0 | ⬜ pending |
| 08-W0-02 | 01 | 0 | D-08 | unit | `cd backend && python -m pytest tests/test_api.py::test_health_facebook_session_valid -x` | ❌ W0 | ⬜ pending |
| FBGR-01a | 01 | 1 | FBGR-01 | unit | `pytest tests/test_facebook_scrapers.py::test_groups_config_loaded -x` | ✅ W0 | ⬜ pending |
| FBGR-01b | 01 | 1 | FBGR-01 | unit | `pytest tests/test_facebook_scrapers.py::test_groups_missing_file -x` | ✅ W0 | ⬜ pending |
| FBGR-02 | 01 | 1 | FBGR-02 | unit | `pytest tests/test_facebook_scrapers.py::test_session_loaded -x` | ✅ W0 | ⬜ pending |
| FBGR-03a | 01 | 1 | FBGR-03 | unit | `pytest tests/test_facebook_scrapers.py::test_session_health_expired -x` | ✅ W0 | ⬜ pending |
| FBGR-03b | 01 | 1 | FBGR-03 | unit | `pytest tests/test_facebook_scrapers.py::test_session_expiry_returns_clean -x` | ✅ W0 | ⬜ pending |
| FBGR-04 | 01 | 1 | FBGR-04 | unit | `pytest tests/test_facebook_scrapers.py::test_parse_fb_post -x` | ✅ W0 | ⬜ pending |
| FBGR-05 | 01 | 1 | FBGR-05 | unit | `pytest tests/test_facebook_scrapers.py::test_groups_failure_isolation -x` | ✅ W0 | ⬜ pending |
| FBMP-01 | 02 | 2 | FBMP-01 | unit | `pytest tests/test_facebook_scrapers.py::test_marketplace_url -x` | ✅ W0 | ⬜ pending |
| FBMP-03 | 02 | 2 | FBMP-03 | unit | `pytest tests/test_facebook_scrapers.py::test_parse_marketplace -x` | ✅ W0 | ⬜ pending |
| FBMP-04 | 02 | 2 | FBMP-04 | unit | `pytest tests/test_facebook_scrapers.py::test_marketplace_failure_isolation -x` | ✅ W0 | ⬜ pending |
| D-08 | 03 | 3 | D-08 | unit | `pytest tests/test_api.py::test_health_facebook_session_valid -x` | ✅ W0 | ⬜ pending |
| D-12 | 03 | 3 | D-12 | unit | `pytest tests/test_facebook_scrapers.py::test_scheduler_health_updated -x` | ✅ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_facebook_scrapers.py` — stubs for all FBGR-01..FBMP-04 + D-12
- [ ] `backend/tests/test_api.py` — extend with `test_health_facebook_session_valid` stub

*Existing `conftest.py`, `pytest.ini`, and test infrastructure cover all fixtures needed — no new framework install required.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| DOM selectors for Facebook Groups posts (`role="article"`) extract correct text/URL | FBGR-04 | Facebook renders obfuscated HTML; selector validity requires a live authenticated session on Israeli IP | Run Wave 0 DOM inspection task: save `/tmp/fb_groups_debug.html`, manually verify `role="article"` nodes contain post text and hrefs |
| Facebook Marketplace Haifa URL returns rental listings | FBMP-01 | Requires live session and Israeli IP | Navigate to `https://www.facebook.com/marketplace/haifa/propertyrentals/` in headed session, confirm listings render |
| Session health check fires Web Push notification on expiry | FBGR-03 | Requires an actual expired session file | Replace `facebook_session.json` with empty/invalid JSON and trigger a manual scrape run; verify push received on device |
| Stealth mode prevents bot detection | FBGR-02 | Cannot automate bot-detection outcome | Monitor for login redirects / CAPTCHAs during first live run |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
