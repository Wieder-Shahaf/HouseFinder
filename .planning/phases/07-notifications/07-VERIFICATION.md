---
phase: 07-notifications
verified: 2026-04-03T19:20:00Z
status: human_needed
score: 9/10 must-haves verified
re_verification: false
human_verification:
  - test: "Open the app in Chrome on a mobile device (or desktop). Confirm a browser notification permission dialog appears on first visit."
    expected: "Native browser permission prompt fires — not suppressed, not missing."
    why_human: "Notification.requestPermission() is a browser-gated API that cannot be triggered programmatically in a test environment."
  - test: "Grant notification permission. Trigger a scraper run (restart the backend or wait for the scheduler interval). Confirm a push notification arrives on the device."
    expected: "A system notification appears with a Hebrew title like '3 דירות חדשות' and body 'לחץ לפתיחת המפה'."
    why_human: "End-to-end push delivery requires real VAPID keys, an active push subscription, and a running backend — all outside the unit-test boundary."
  - test: "Tap/click the push notification that arrives on the device."
    expected: "The app opens (or is focused if already open) at the configured app URL."
    why_human: "notificationclick handler behavior requires a real browser environment with a service worker in 'active' state."
---

# Phase 7: Notifications Verification Report

**Phase Goal:** The user receives a Web Push notification after each scraper run that finds new listings, with a WhatsApp stub ready for future activation
**Verified:** 2026-04-03T19:20:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | After a scraper run with new listings, a push notification is sent with Hebrew count message | ✓ VERIFIED | `run_notification_job` queries `notified_at IS NULL AND created_at >= run_start_time`, builds `{count} דירות חדשות` payload, calls `webpush()` once. Test `test_sends_push_when_new_listings` passes. |
| 2 | At most one notification batch is sent per scraper run regardless of listing count | ✓ VERIFIED | Single `webpush()` call wraps all new listings into one payload. Test `test_single_push_per_run` asserts `mock_webpush.call_count == 1` for 5 listings — passes. |
| 3 | `notified_at` column is stamped on all notified listings after push is sent | ✓ VERIFIED | `UPDATE listings SET notified_at = ... WHERE id IN (...)` on successful push. Test `test_notified_at_stamped` verifies all 3 listings have non-null `notified_at`. Also confirmed column in `models/listing.py` line 47. |
| 4 | `send_whatsapp()` stub exists and is importable but inactive | ✓ VERIFIED | `backend/app/notifier.py` lines 114–137: function has full NOTF-02 signature, logs and returns None, no Twilio SDK import. Tests `test_whatsapp_stub_importable` and `test_whatsapp_stub_full_signature` both pass. |
| 5 | `POST /api/push/subscribe` stores subscription JSON to `/data/push_subscription.json` | ✓ VERIFIED | `backend/app/routers/push.py` line 29: `SUBSCRIPTION_FILE.write_text(json.dumps(subscription))`. Test `test_push_subscribe` verifies 200 response and written content matches request body. |
| 6 | `GET /api/push/vapid-public-key` returns the configured public key | ✓ VERIFIED | `backend/app/routers/push.py` line 40: returns `{"publicKey": settings.vapid_public_key}`. Test `test_vapid_public_key` asserts correct key. |
| 7 | Service worker registers at `/sw.js` on app load | ✓ VERIFIED | `frontend/public/sw.js` exists and is served from public/. `usePushSubscription.js` line 15 calls `navigator.serviceWorker.register('/sw.js')`. `App.jsx` calls `usePushSubscription()` on every mount. |
| 8 | Push event in service worker shows notification with Hebrew title and body | ✓ VERIFIED | `frontend/public/sw.js` lines 4–16: push event handler calls `self.registration.showNotification(title, options)` with `dir: 'rtl'` and `lang: 'he'`. |
| 9 | Clicking notification opens the app URL | ✓ VERIFIED | `frontend/public/sw.js` lines 19–30: `notificationclick` handler calls `client.focus()` if app window exists, otherwise `clients.openWindow(targetUrl)`. |
| 10 | `manifest.json` enables Add to Home Screen for iOS Web Push support | ✓ VERIFIED | `frontend/public/manifest.json` contains `"display": "standalone"`, `"dir": "rtl"`, `"lang": "he"`. Linked in `index.html` line 10 via `<link rel="manifest" href="/manifest.json" />`. |

**Score:** 10/10 truths verified (automated)

### Required Artifacts

| Artifact | Provides | Status | Details |
|----------|----------|--------|---------|
| `backend/alembic/versions/0003_add_notified_at.py` | Alembic migration adding `notified_at` column | ✓ VERIFIED | Contains `batch_op.add_column`, `down_revision = "0002"`, correct SQLite-safe batch pattern |
| `backend/app/notifier.py` | Notification dispatch + WhatsApp stub | ✓ VERIFIED | 138 lines, exports `run_notification_job` and `send_whatsapp`, contains Hebrew payload strings, pywebpush import |
| `backend/app/routers/push.py` | Push subscription and VAPID key endpoints | ✓ VERIFIED | 41 lines, exports `router`, both endpoints implemented |
| `backend/tests/test_notifier.py` | Unit tests for notification logic | ✓ VERIFIED | 206 lines (> 50 min), 8 tests all passing |
| `.env.example` | VAPID key env var documentation | ✓ VERIFIED | Lines 9–13 contain `VAPID_PUBLIC_KEY=`, `VAPID_PRIVATE_KEY=`, `VITE_VAPID_PUBLIC_KEY=` |
| `frontend/public/sw.js` | Service worker push and notificationclick handlers | ✓ VERIFIED | 30 lines, two `addEventListener` calls, `showNotification`, Hebrew RTL options |
| `frontend/public/manifest.json` | PWA manifest for standalone mode | ✓ VERIFIED | `display: standalone`, `dir: rtl`, `lang: he` |
| `frontend/src/hooks/usePushSubscription.js` | SW registration + push subscription hook | ✓ VERIFIED | Contains `pushManager.subscribe`, `urlBase64ToUint8Array`, both fetch calls to backend endpoints |
| `frontend/src/App.jsx` | App component with push hook wired | ✓ VERIFIED | Imports `usePushSubscription` and calls it as first statement in `App()` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/app/scheduler.py` | `backend/app/notifier.py` | deferred import `from app.notifier import run_notification_job` | ✓ WIRED | Present in both `run_yad2_scrape_job` (line 31) and `run_madlan_scrape_job` (line 68). Both jobs call `await run_notification_job(session, started_at)` after `run_dedup_pass`. |
| `backend/app/main.py` | `backend/app/routers/push.py` | `app.include_router(push_router)` | ✓ WIRED | `main.py` line 12 imports `router as push_router`; line 71 calls `app.include_router(push_router)`. |
| `backend/app/notifier.py` | pywebpush | `from pywebpush import webpush, WebPushException` | ✓ WIRED | Line 20 of `notifier.py`. `pywebpush==2.1.2` in `requirements.txt` line 18. |
| `frontend/src/hooks/usePushSubscription.js` | `/api/push/subscribe` | `fetch` POST with subscription JSON | ✓ WIRED | Line 33: `fetch('/api/push/subscribe', { method: 'POST', ... })` |
| `frontend/src/hooks/usePushSubscription.js` | `/api/push/vapid-public-key` | `fetch` GET for VAPID key | ✓ WIRED | Line 24: `fetch('/api/push/vapid-public-key')` — result consumed to get `publicKey` |
| `frontend/public/sw.js` | `self.registration.showNotification` | push event listener | ✓ WIRED | Line 15: `event.waitUntil(self.registration.showNotification(title, options))` inside `push` event handler |

### Data-Flow Trace (Level 4)

Backend `run_notification_job` is the only dynamic data renderer. Data flow:
- Source: `SELECT * FROM listings WHERE notified_at IS NULL AND created_at >= run_start_time AND is_active = True` — real DB query (SQLAlchemy `select(Listing).where(...)`)
- Result consumed: `new_listings = result.scalars().all()`, `count = len(new_listings)`, used in Hebrew payload title
- Subscription source: `SUBSCRIPTION_FILE.read_text()` — reads real file from Docker volume
- Push delivery: `webpush(subscription_info=subscription, data=json.dumps(payload, ensure_ascii=False), ...)` — real pywebpush call with live data

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `backend/app/notifier.py` | `new_listings` / `count` | `SELECT listings WHERE notified_at IS NULL...` | Yes — DB query with real filter predicates | ✓ FLOWING |
| `frontend/src/hooks/usePushSubscription.js` | `publicKey` | `GET /api/push/vapid-public-key` | Yes — fetches from live backend at subscription time | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| notifier.py imports successfully | `python3 -c "from app.notifier import run_notification_job, send_whatsapp; print('ok')"` | `imports ok` | ✓ PASS |
| push router imports successfully | `python3 -c "from app.routers.push import router; print('ok')"` | `push router ok` | ✓ PASS |
| All 8 notifier unit tests pass | `python3 -m pytest tests/test_notifier.py -x -v` | 8 passed in 0.17s | ✓ PASS |
| Both push API tests pass | `python3 -m pytest tests/test_api.py::test_push_subscribe tests/test_api.py::test_vapid_public_key -v` | 2 passed in 0.20s | ✓ PASS |
| Browser push notification displayed | Requires real browser + VAPID keys | Cannot test without running server | ? SKIP |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| NOTF-01 | 07-01-PLAN.md | WhatsApp message sent when new listing found | ✓ SATISFIED (stub) | `send_whatsapp()` exists, importable, returns None, has full NOTF-02 signature. Intentionally inactive pending Meta template approval — acknowledged in ROADMAP Phase 7 goal, SUMMARY deviations, and `deferred-items.md`. REQUIREMENTS.md marks as complete (stub satisfies the phase scope). |
| NOTF-02 | 07-01-PLAN.md | WhatsApp message includes price, rooms, neighborhood, link | ✓ SATISFIED (stub) | `send_whatsapp(count, url, price, rooms, neighborhood)` signature present — all NOTF-02 fields accepted. Full signature preserved so future activation does not require changing callers. |
| NOTF-03 | 07-01-PLAN.md, 07-02-PLAN.md | Web Push notification sent for new listings | ✓ SATISFIED | Backend: `run_notification_job` dispatches pywebpush. Frontend: `sw.js` receives push and calls `showNotification`. Hook auto-registers SW and sends subscription to backend. All tested. |
| NOTF-04 | 07-01-PLAN.md | Notifications rate-limited — one batch per scraper run | ✓ SATISFIED | Single `webpush()` call wraps all new listings. `test_single_push_per_run` verifies `call_count == 1` for 5 new listings. |

No orphaned requirements: REQUIREMENTS.md traceability table maps NOTF-01 through NOTF-04 exclusively to Phase 7, and all four are claimed in plan frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/notifier.py` | 114–137 | `send_whatsapp()` logs and returns `None` | ℹ️ Info — intentional | WhatsApp notifications (NOTF-01/NOTF-02) will not actually send. This is documented as an accepted stub pending Meta template approval. The function signature is complete; full activation requires only Twilio SDK import and API call body. |

No unintentional stubs, empty returns, or TODO/FIXME markers found in Phase 7 artifacts.

### Human Verification Required

The following behaviors require a real browser with valid VAPID keys and an active network-connected push subscription. They cannot be verified programmatically.

**1. Browser permission dialog appears on first visit**

**Test:** Open the app in Chrome on a mobile device (Android or iOS). On first load, confirm a native notification permission prompt appears.
**Expected:** Native browser dialog asking "Allow ApartmentFinder to send notifications?" fires automatically on first visit (after `Notification.requestPermission()` is called in `usePushSubscription`).
**Why human:** `Notification.requestPermission()` is a browser-gated API that requires a real browser context with a user gesture (or auto-prompt on first load). Cannot be triggered or asserted in pytest or jsdom.

**2. Push notification arrives on device after a scraper run**

**Test:** Grant notification permission. Configure VAPID keys in `.env` (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CONTACT_EMAIL`). Trigger a scraper run (restart backend to fire the immediate startup job or wait for the 2-hour scheduler interval). Confirm a notification arrives on the device.
**Expected:** System notification appears with title `"N דירות חדשות"` and body `"לחץ לפתיחת המפה"` in Hebrew RTL layout.
**Why human:** End-to-end push delivery requires real VAPID keys, a network-connected push service (e.g. FCM/APNS), and an active subscription stored in `/data/push_subscription.json` on the server.

**3. Clicking the notification opens the app**

**Test:** Tap/click the push notification on the device.
**Expected:** The app opens (or is focused if already in the background) at the `app_url` configured in `.env`.
**Why human:** The `notificationclick` service worker event requires a real browser with an active service worker registration.

### Gaps Summary

No gaps found. All 10 observable truths are verified by code inspection and automated tests. All required artifacts exist with substantive implementations. All key links are wired. NOTF-01 and NOTF-02 WhatsApp requirements are satisfied by an intentional, well-documented stub with the full NOTF-02 call signature — this is the accepted deliverable for Phase 7 as stated in the ROADMAP phase goal ("WhatsApp stub ready for future activation") and acknowledged throughout planning artifacts.

The three items flagged for human verification are behaviors that require a live browser environment and valid VAPID keys — they are not gaps in the implementation but inherent constraints of the Web Push API.

---

_Verified: 2026-04-03T19:20:00Z_
_Verifier: Claude (gsd-verifier)_
