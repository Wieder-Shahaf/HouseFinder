---
phase: 4
slug: map-web-ui
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-02
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest (installed in Wave 0) |
| **Config file** | `frontend/vite.config.js` — add `test` block in Wave 0 |
| **Quick run command** | `cd frontend && npx vitest run --reporter=dot` |
| **Full suite command** | `cd frontend && npx vitest run` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npx vitest run --reporter=dot`
- **After every plan wave:** Run `cd frontend && npx vitest run`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 0 | MAP-01, MAP-03 | unit | `cd frontend && npx vitest run tests/MapView.test.jsx` | ❌ W0 | ⬜ pending |
| 4-01-02 | 01 | 0 | MAP-02, MAP-05 | unit | `cd frontend && npx vitest run tests/ListingSheet.test.jsx` | ❌ W0 | ⬜ pending |
| 4-01-03 | 01 | 0 | MAP-04 | unit | `cd frontend && npx vitest run tests/FilterSheet.test.jsx` | ❌ W0 | ⬜ pending |
| 4-01-04 | 01 | 0 | MAP-06 | unit | `cd frontend && npx vitest run tests/FavoritesView.test.jsx` | ❌ W0 | ⬜ pending |
| 4-01-05 | 01 | 0 | MAP-08 | unit | `cd frontend && npx vitest run tests/layout.test.jsx` | ❌ W0 | ⬜ pending |
| 4-xx-xx | — | 1+ | MAP-07 | manual | Manual browser check: dir="rtl" lang="he" visible in DOM | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/tests/setup.js` — jsdom + @testing-library/react setup
- [ ] `frontend/tests/MapView.test.jsx` — stubs for MAP-01, MAP-03
- [ ] `frontend/tests/ListingSheet.test.jsx` — stubs for MAP-02, MAP-05
- [ ] `frontend/tests/FilterSheet.test.jsx` — stubs for MAP-04
- [ ] `frontend/tests/FavoritesView.test.jsx` — stubs for MAP-06
- [ ] `frontend/tests/layout.test.jsx` — stubs for MAP-08
- [ ] Install test framework: `cd frontend && npm i -D vitest @vitest/ui jsdom @testing-library/react @testing-library/user-event`
- [ ] Add `test` block to `frontend/vite.config.js`
- [ ] Add Vite proxy: `server.proxy = { '/api': 'http://localhost:8000' }` to `frontend/vite.config.js`
- [ ] Update viewport meta in `frontend/index.html` to add `viewport-fit=cover`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| HTML dir="rtl" lang="he"; text flows RTL | MAP-07 | Visual layout requires browser rendering; DOM assertions can verify attributes but not visual RTL flow | Open app in mobile browser, verify text/buttons/cards flow right-to-left; inspect `<html>` for `dir="rtl" lang="he"` |
| Map pins visible on Haifa viewport at load | MAP-01 | Map tile rendering and pin placement require a real browser with Leaflet canvas | Open app, verify map centers on Haifa (32.7940, 34.9896 zoom 13), verify listing pins appear |
| Touch targets >= 44px (feel test) | MAP-08 | CSS px assertions cover spec; actual finger usability requires device testing | Tap buttons/pins on a real phone, verify no missed taps |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
