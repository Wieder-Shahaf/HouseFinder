---
phase: "07"
name: notifications
status: discussed
discussed: "2026-04-03"
---

# Phase 7: Notifications — Context

## Domain

The user receives a Web Push notification on their phone after each scraper run that finds new matching listings. WhatsApp (Twilio) is deferred until the Meta message template is approved — the code stub will be wired but inactive.

## Decisions

### Notification Channel

**Web Push only for this phase. WhatsApp (Twilio) is deferred.**

- Twilio WhatsApp template has NOT been submitted to Meta yet. Template approval takes days–weeks and is a hard blocker for WhatsApp.
- Config already has `twilio_account_sid`, `twilio_auth_token`, `twilio_whatsapp_from` in `backend/app/config.py`.
- Planner SHOULD stub out the Twilio send function (class or module with a `send_whatsapp()` method) but leave it disabled/inactive — no actual Twilio calls in this phase.
- Web Push is the primary and only active notification channel for Phase 7.

### Message Content & Language

**Hebrew, count + link only.**

- Title: `"{N} דירות חדשות"` (N new apartments)
- Body: `"לחץ לפתיחת המפה"` (tap to open the map)
- No per-neighborhood breakdown — keep it simple
- Link target: `settings.app_url` (already a config value)
- One push notification per scraper run batch — NOTF-04 rate limit applies

### New Listing Detection — `notified_at` column

**Add a nullable `notified_at` timestamp column to the listings table.**

- Alembic migration required: `ALTER TABLE listings ADD COLUMN notified_at DATETIME NULL`
- After each scraper run, query: `SELECT * FROM listings WHERE notified_at IS NULL AND created_at >= {run_start_time}`
- If any results: send push, then `UPDATE listings SET notified_at = now() WHERE id IN ({ids})`
- This is persistent across process restarts — no missed notifications from reboot between scrape and notify
- `run_start_time` is passed into the notification function by the scheduler (same pattern as existing scraper jobs)

### Web Push Frontend Subscription

**Auto-prompt on first app load.**

- On first visit, browser shows native permission dialog
- If granted: call `navigator.serviceWorker.register('/sw.js')` → get `PushSubscription` → POST to `POST /api/push/subscribe`
- Backend stores the subscription (JSON) — for single-user simplicity, a JSON file (`push_subscription.json`) in `/data/` volume mount is acceptable; no new DB table required
- Service worker file (`sw.js`) must be served from the frontend root (Vite `public/` directory)
- Service worker handles `push` events: shows notification using `self.registration.showNotification()`

### VAPID Keys

- Generate once: `npx web-push generate-vapid-keys`
- Store in `.env`: `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY`
- Add to `backend/app/config.py` as `vapid_public_key: str = ""` and `vapid_private_key: str = ""`
- Frontend needs `VITE_VAPID_PUBLIC_KEY` exposed via Vite env

### Backend Push Sender

- Use `pywebpush` Python library for sending Web Push from the backend
- `POST /api/push/subscribe` — stores subscription JSON
- `GET /api/push/vapid-public-key` — returns public key for frontend subscription setup
- Notification sending is called at the end of each scheduler job (after scrape + dedup + notify flag update)

### Scheduler Wiring

- After `run_yad2_scrape_job()` and `run_madlan_scrape_job()` complete, call a shared `run_notification_job(run_start_time)` function
- This function: detects new listings → sends push if any found → stamps `notified_at`
- Both scrapers share the same notification pass — one push for all new listings from that run, regardless of source

## What's Out of Scope for This Phase

- Sending actual WhatsApp messages (Twilio deferred — template not approved)
- Per-listing push notifications (violates NOTF-04)
- Notification preferences UI (single-user, always-on is sufficient)
- Push subscription management (unsubscribe, re-subscribe) — not needed for single-user

## Deferred Ideas

- WhatsApp via Twilio — implement after Meta template approval; stub code is in place
- Notification history / log in the UI

## Canonical Refs

- `.planning/REQUIREMENTS.md` — NOTF-01, NOTF-02, NOTF-03, NOTF-04
- `backend/app/config.py` — existing Twilio config fields + `app_url`; VAPID keys to be added
- `backend/app/scheduler.py` — APScheduler job wiring pattern (deferred imports + try/except isolation)
- `backend/app/scrapers/madlan.py` — scraper isolation pattern to follow for notifier
- `.env` — VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VITE_VAPID_PUBLIC_KEY to be added
- `frontend/public/sw.js` — new service worker file (does not yet exist)
