---
phase: 07
slug: notifications
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-03
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | backend/pytest.ini (or pyproject.toml [tool.pytest.ini_options]) |
| **Quick run command** | `cd /Users/shahafwieder/HouseFinder/backend && python -m pytest tests/test_notifier.py -x` |
| **Full suite command** | `cd /Users/shahafwieder/HouseFinder/backend && python -m pytest tests/ -x` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd /Users/shahafwieder/HouseFinder/backend && python -m pytest tests/test_notifier.py -x`
- **After every plan wave:** Run `cd /Users/shahafwieder/HouseFinder/backend && python -m pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | NOTF-01, NOTF-02, NOTF-03, NOTF-04 | unit + import smoke | `cd /Users/shahafwieder/HouseFinder/backend && python -c "from app.notifier import run_notification_job, send_whatsapp; print('ok')" && python -c "from app.routers.push import router; print('ok')"` | ❌ W0 | ⬜ pending |
| 07-01-02 | 01 | 1 | NOTF-01, NOTF-02, NOTF-04 | unit (pytest) | `cd /Users/shahafwieder/HouseFinder/backend && python -m pytest tests/test_notifier.py tests/test_api.py -x -v 2>&1 \| tail -30` | ❌ W0 | ⬜ pending |
| 07-02-01 | 02 | 2 | NOTF-03 | static file check | `cd /Users/shahafwieder/HouseFinder/frontend && grep -c "addEventListener" public/sw.js && python3 -c "import json; d=json.load(open('public/manifest.json')); assert d['display']=='standalone'; print('ok')" && grep -c "usePushSubscription" src/App.jsx` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_notifier.py` — created in Plan 01 Task 2 as part of the TDD cycle; no pre-existing file
- [ ] `backend/tests/conftest.py` — must already exist from prior phases (provides `db_session` fixture); verify before running tests

*Plan 01 Task 2 creates the test file as part of its TDD action. No separate Wave 0 plan needed — the task itself is the scaffold.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Browser permission dialog appears on first visit | NOTF-03 | Requires real browser interaction; cannot be automated in pytest | Open app in Chrome mobile or desktop, confirm native permission prompt appears |
| Push notification appears on device screen | NOTF-03 | Requires real device + valid VAPID keys + active push subscription | After granting permission and triggering a scraper run, confirm notification appears on phone |
| Clicking notification opens app URL | NOTF-03 | Requires real device interaction | Tap received notification, confirm app opens at correct URL |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify commands
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0: test files created by Plan 01 Task 2 TDD cycle (no MISSING stubs needed in advance)
- [x] No watch-mode flags in any verify command
- [x] Feedback latency < 30s (pytest runs in ~10s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-03
