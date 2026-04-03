---
phase: 07-notifications
plan: "01"
subsystem: backend-notifications
tags: [web-push, pywebpush, vapid, notifications, alembic, scheduler]
dependency_graph:
  requires: [06-madlan-scraper]
  provides: [web-push-pipeline, push-subscription-api, notified-at-migration]
  affects: [backend/app/scheduler.py, backend/app/models/listing.py]
tech_stack:
  added: [pywebpush==2.1.2]
  patterns: [deferred-import scheduler wiring, VAPID webpush one-call pattern, alembic batch migration, volume-persisted JSON subscription]
key_files:
  created:
    - backend/alembic/versions/0003_add_notified_at.py
    - backend/app/notifier.py
    - backend/app/routers/push.py
    - backend/tests/test_notifier.py
  modified:
    - backend/app/models/listing.py
    - backend/app/config.py
    - backend/requirements.txt
    - backend/app/main.py
    - backend/app/scheduler.py
    - backend/tests/test_api.py
    - .env.example
decisions:
  - pywebpush 2.1.2 used instead of 2.3.0 (specified in plan) — 2.3.0 does not exist on PyPI; 2.1.2 is the latest available version with identical webpush() API
  - ensure_ascii=False on json.dumps for Hebrew payload to avoid unicode-escape assertion issues in tests
metrics:
  duration: "~15min"
  completed: "2026-04-03T16:12:24Z"
  tasks: 2
  files: 11
---

# Phase 7 Plan 1: Backend Notification Pipeline Summary

Web Push notification pipeline using pywebpush 2.1.2 with VAPID, notified_at tracking column, push subscription API, scheduler wiring, and WhatsApp stub with full NOTF-02 signature.

## What Was Built

### Core Components

**Alembic migration 0003** adds `notified_at DATETIME NULL` to the `listings` table, following the Phase 5 `batch_alter_table` pattern required for SQLite.

**notifier.py** implements:
- `run_notification_job(session, run_start_time)` — queries listings where `notified_at IS NULL AND created_at >= run_start_time AND is_active = True`, sends a single Web Push with Hebrew content (`"{N} דירות חדשות"` / `"לחץ לפתיחת המפה"`), stamps `notified_at` on success. Catches `WebPushException` without raising — scheduler jobs are never interrupted by notification failures.
- `send_whatsapp(count, url, price, rooms, neighborhood)` — inactive stub logging a deferred message. Full NOTF-02 signature avoids future caller changes.

**push.py router** exposes:
- `POST /api/push/subscribe` — writes subscription JSON to `/data/push_subscription.json` (volume-mounted, survives container restarts)
- `GET /api/push/vapid-public-key` — returns `{"publicKey": settings.vapid_public_key}`

**Scheduler wiring** — both `run_yad2_scrape_job()` and `run_madlan_scrape_job()` now call `await run_notification_job(session, started_at)` after `run_dedup_pass()`, using the existing deferred import pattern.

### Test Coverage

10 new tests all passing:
- 8 in `test_notifier.py` covering NOTF-03 push behavior, NOTF-04 one-push-per-run, notified_at stamping, missing subscription file, WebPushException handling, and WhatsApp stub
- 2 in `test_api.py` covering push subscription endpoint and VAPID key endpoint

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Version mismatch] pywebpush 2.3.0 not available on PyPI**
- **Found during:** Task 1 implementation
- **Issue:** Plan specified `pywebpush==2.3.0` but PyPI only has up to 2.1.2. `pip install pywebpush==2.3.0` failed.
- **Fix:** Used `pywebpush==2.1.2` (latest available) which provides the identical `webpush()` one-call API.
- **Files modified:** `backend/requirements.txt`
- **Commit:** 715cdd8

**2. [Rule 1 - Bug] ensure_ascii=False required for Hebrew payload assertion**
- **Found during:** Task 1 TDD GREEN phase
- **Issue:** `json.dumps(payload)` with default `ensure_ascii=True` encodes Hebrew as `\uXXXX` sequences. Test assertion `"2 דירות חדשות" in payload_data` failed because the string contained escape sequences.
- **Fix:** Changed to `json.dumps(payload, ensure_ascii=False)` to keep Hebrew characters as UTF-8 literals in the JSON string.
- **Files modified:** `backend/app/notifier.py`
- **Commit:** 715cdd8

## Pre-Existing Failures (Deferred)

8 test failures existed before Phase 07 work began and are not caused by our changes. Logged to `deferred-items.md`:
- `test_get_listings_neighborhood_filter` — neighborhood filter returns 0 results
- `test_listings_table_columns` — schema assertion mismatch
- 5 `test_listings_neighborhood.py` tests — neighborhood filter behavior
- `test_scrape_job_updates_health_on_success` — AsyncMock coroutine warning

## Acceptance Criteria Verification

- [x] `pywebpush==2.1.2` in requirements.txt (2.3.0 unavailable — see deviation)
- [x] Alembic migration 0003 adds `notified_at` column with `batch_op.add_column`
- [x] `down_revision = "0002"` in migration
- [x] `notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)` in Listing model
- [x] `vapid_public_key: str = ""` in config
- [x] `vapid_private_key: str = ""` in config
- [x] `vapid_contact_email: str =` in config
- [x] `async def run_notification_job(` in notifier.py
- [x] `def send_whatsapp(count: int, url: str, price: Optional[int] = None, rooms: Optional[float] = None, neighborhood: Optional[str] = None)` in notifier.py
- [x] `from pywebpush import webpush, WebPushException` in notifier.py
- [x] `push_subscription.json` referenced in notifier.py
- [x] `דירות חדשות` in notifier.py
- [x] `לחץ לפתיחת המפה` in notifier.py
- [x] `@router.post("/subscribe")` in push.py
- [x] `@router.get("/vapid-public-key")` in push.py
- [x] `include_router(push_router)` in main.py
- [x] `VAPID_PUBLIC_KEY` in .env.example
- [x] `VAPID_PRIVATE_KEY` in .env.example
- [x] `VITE_VAPID_PUBLIC_KEY` in .env.example
- [x] Scheduler wiring: `from app.notifier import run_notification_job` in both jobs
- [x] `await run_notification_job(session, started_at)` in both jobs
- [x] All 8 notifier tests pass
- [x] Both push API tests pass

## Known Stubs

**send_whatsapp() in backend/app/notifier.py** — intentional stub. WhatsApp via Twilio is deferred pending Meta message template approval (NOTF-01/NOTF-02). Stub accepts full NOTF-02 parameter signature so future activation does not require caller changes. Tracked in STATE.md Pending Todos.

## Self-Check: PASSED
