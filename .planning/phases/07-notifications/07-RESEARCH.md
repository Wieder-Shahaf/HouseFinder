# Phase 7: Notifications - Research

**Researched:** 2026-04-03
**Domain:** Web Push (VAPID), pywebpush 2.x, service workers, Alembic column migration
**Confidence:** HIGH

## Summary

Phase 7 adds Web Push notifications to the existing FastAPI + React stack. The backend sends a push after each scraper run if new listings are found, using pywebpush 2.3.0 (latest as of 2026-04). The frontend registers a service worker (`sw.js` served from `public/`), requests permission on first load, subscribes via `PushManager.subscribe()`, and POSTs the subscription JSON to a new `/api/push/subscribe` endpoint.

New listing detection uses a nullable `notified_at` DATETIME column on the existing `listings` table — identical to the Phase 5 `neighborhood` column migration pattern (`op.batch_alter_table` + `sa.Column(..., nullable=True)`). The push subscription is stored in a JSON file at `/data/push_subscription.json` on the volume mount — no new DB table required for single-user use.

WhatsApp via Twilio is deferred. A stub module with a `send_whatsapp()` function is wired but inactive. The Twilio config fields (`twilio_account_sid`, `twilio_auth_token`, `twilio_whatsapp_from`) already exist in `backend/app/config.py`.

**Primary recommendation:** Use `pywebpush 2.3.0` with the `webpush()` one-call function (no class instantiation needed). Store VAPID keys as base64url-encoded strings in `.env`. Generate keys once via `npx web-push generate-vapid-keys`. Wire notification dispatch at the end of each scraper job in `scheduler.py` using the existing deferred-import pattern.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Web Push only for this phase. WhatsApp (Twilio) is deferred.
- Twilio stub: implement `send_whatsapp()` but leave inactive — no actual Twilio calls this phase.
- Hebrew content only: title `"{N} דירות חדשות"`, body `"לחץ לפתיחת המפה"`.
- Link target: `settings.app_url`.
- One push notification per scraper run batch (NOTF-04 — not per individual listing).
- `notified_at` nullable DATETIME column on `listings` table via Alembic migration.
- Query pattern: `WHERE notified_at IS NULL AND created_at >= {run_start_time}`.
- After sending: `UPDATE listings SET notified_at = now() WHERE id IN ({ids})`.
- `run_start_time` passed into notification function by scheduler (same pattern as scraper jobs).
- Auto-prompt on first app load (not gated behind a button click).
- Service worker file at `frontend/public/sw.js`.
- `navigator.serviceWorker.register('/sw.js')` in frontend.
- Push subscription stored as JSON file at `/data/push_subscription.json`.
- No new DB table for subscription storage.
- VAPID keys: generate once with `npx web-push generate-vapid-keys`, store in `.env` as `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY`; expose `VITE_VAPID_PUBLIC_KEY` to frontend.
- Use `pywebpush` Python library.
- New API endpoints: `POST /api/push/subscribe`, `GET /api/push/vapid-public-key`.
- Scheduler wiring: `run_notification_job(run_start_time)` called after each of `run_yad2_scrape_job()` and `run_madlan_scrape_job()`.

### Claude's Discretion
- Exact file/module layout for notifier code within the backend.
- Whether `run_notification_job` is async or sync (async preferred to match existing jobs).
- Error handling strategy for push send failures (log + continue, never raise from scheduler).
- iOS "Add to Home Screen" advisory copy in the frontend permission prompt.

### Deferred Ideas (OUT OF SCOPE)
- WhatsApp via Twilio (template not approved).
- Notification history / log in the UI.
- Per-listing push notifications.
- Notification preferences UI.
- Push subscription management (unsubscribe, re-subscribe).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NOTF-01 | WhatsApp message sent to user when new listing found (Twilio WhatsApp API) | Locked as deferred — stub `send_whatsapp()` only; Twilio SDK not called this phase |
| NOTF-02 | WhatsApp message includes price, rooms, neighborhood, link | Deferred to post-template-approval; stub accepts these params for future use |
| NOTF-03 | Web Push notification sent as fallback (or simultaneously) for new listings | Primary active channel this phase: pywebpush 2.3.0 `webpush()`, VAPID, sw.js push event |
| NOTF-04 | Notifications rate-limited — no more than one batch per scraper run | Enforced by `notified_at` stamp: query only `notified_at IS NULL AND created_at >= run_start_time`; one push call per job invocation |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pywebpush | 2.3.0 | Send Web Push from Python backend | Official web-push-libs library; wraps VAPID JWT signing + AES128GCM encryption |
| web-push (npm) | latest (npx only) | VAPID key generation one-time CLI | Canonical JS key generator; output is directly consumable by pywebpush |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| twilio (Python SDK) | 9.x (already in CLAUDE.md) | WhatsApp stub — inactive this phase | Import and define stub; do not call |
| json (stdlib) | — | Persist push subscription to `/data/push_subscription.json` | Single-user, no DB table needed |
| pathlib (stdlib) | — | Safe path handling for subscription file | Docker volume path `/data/` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pywebpush | py-vapid + manual HTTP | pywebpush wraps py-vapid; no reason to use raw py-vapid directly |
| JSON file for subscription | SQLite push_subscriptions table | Table is overkill for single subscription; JSON file is simpler and survives container restart via volume |
| `npx web-push generate-vapid-keys` | Python `py-vapid` CLI or `openssl` | `npx web-push` is the most widely documented single command; project already has Node.js |

**Installation (backend):**
```bash
pip install pywebpush==2.3.0
```

**Version verification:** `pip index versions pywebpush` confirmed 2.3.0 is the latest (2026-02-09 release).

## Architecture Patterns

### Recommended Project Structure (additions only)
```
backend/
├── app/
│   ├── notifier.py           # push send logic + Twilio stub
│   └── routers/
│       └── push.py           # POST /api/push/subscribe, GET /api/push/vapid-public-key
frontend/
├── public/
│   └── sw.js                 # service worker — push event handler + notificationclick
└── src/
    └── hooks/
        └── usePushSubscription.js  # useEffect registration + subscribe + POST to backend
```

### Pattern 1: Backend — Send Web Push with pywebpush 2.3.0
**What:** One-call `webpush()` function signs a VAPID JWT, encrypts the payload (AES128GCM), and sends via HTTP to the browser push service.
**When to use:** After detecting new listings in `run_notification_job()`.
**Example:**
```python
# Source: https://github.com/web-push-libs/pywebpush/blob/main/README.md
from pywebpush import webpush, WebPushException

def send_push(subscription_info: dict, title: str, body: str, url: str) -> None:
    import json
    payload = json.dumps({"title": title, "body": body, "url": url})
    webpush(
        subscription_info=subscription_info,   # {"endpoint": "...", "keys": {"p256dh": "...", "auth": "..."}}
        data=payload,
        vapid_private_key=settings.vapid_private_key,   # base64url-encoded DER string
        vapid_claims={"sub": f"mailto:{settings.vapid_contact_email}"},
    )
```

**Important:** `vapid_claims` dict is mutated by pywebpush after the call. Pass a fresh dict or copy each time. The `"aud"` and `"exp"` keys are auto-filled from the subscription endpoint if omitted.

### Pattern 2: Alembic Migration — Add `notified_at` Column
**What:** Matches the existing Phase 5 pattern in `0002_add_neighborhood.py`. Use `op.batch_alter_table` (required for SQLite — `render_as_batch=True` is already set in `alembic/env.py`).
**Example:**
```python
# Follows pattern from backend/alembic/versions/0002_add_neighborhood.py
revision = "0003"
down_revision = "0002"

def upgrade() -> None:
    with op.batch_alter_table("listings") as batch_op:
        batch_op.add_column(sa.Column("notified_at", sa.DateTime(), nullable=True))

def downgrade() -> None:
    with op.batch_alter_table("listings") as batch_op:
        batch_op.drop_column("notified_at")
```

Also add to `Listing` model:
```python
notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
```

### Pattern 3: Scheduler Wiring — Notification Job
**What:** Call `run_notification_job(run_start_time)` at the end of each scraper job body, inside the same try/except block scope, using deferred imports (existing pattern).
**When to use:** After `run_geocoding_pass` and `run_dedup_pass` in both `run_yad2_scrape_job` and `run_madlan_scrape_job`.
**Example:**
```python
# Follows deferred import pattern from backend/app/scheduler.py
async def run_yad2_scrape_job() -> None:
    from app.notifier import run_notification_job   # deferred import
    started_at = datetime.now(timezone.utc)
    try:
        async with async_session_factory() as session:
            result = await run_yad2_scraper(session)
            await run_geocoding_pass(session)
            await run_dedup_pass(session)
            await run_notification_job(session, started_at)  # <-- new
    except Exception as exc:
        ...
```

**Note:** `run_notification_job` receives the already-open session and `run_start_time` so it can query `notified_at IS NULL AND created_at >= run_start_time` in one DB round-trip.

### Pattern 4: Service Worker — push + notificationclick Events
**What:** `frontend/public/sw.js` handles two events: `push` (show notification) and `notificationclick` (open app URL, focus if already open).
**Example:**
```javascript
// Source: MDN Web Docs — ServiceWorkerGlobalScope: push event
self.addEventListener('push', event => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'ApartmentFinder';
  const options = {
    body: data.body || '',
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    data: { url: data.url || '/' },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

// Source: MDN Web Docs — ServiceWorkerGlobalScope: notificationclick event
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clientList => {
      for (const client of clientList) {
        if (client.url === targetUrl && 'focus' in client) return client.focus();
      }
      if (clients.openWindow) return clients.openWindow(targetUrl);
    })
  );
});
```

### Pattern 5: Frontend — Push Subscription Registration
**What:** `useEffect` in `App.jsx` (or a custom hook) runs on mount, requests permission, subscribes, and POSTs subscription to backend.
**When to use:** Once on app load (no user button click required per locked decision).
**Example:**
```javascript
// Source: MDN Web Docs — PushManager: subscribe()
useEffect(() => {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;

  const register = async () => {
    const reg = await navigator.serviceWorker.register('/sw.js');
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') return;

    // Convert VAPID public key from base64url to Uint8Array
    const urlBase64ToUint8Array = (base64String) => {
      const padding = '='.repeat((4 - base64String.length % 4) % 4);
      const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
      const rawData = window.atob(base64);
      return Uint8Array.from([...rawData].map(c => c.charCodeAt(0)));
    };

    const subscription = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(import.meta.env.VITE_VAPID_PUBLIC_KEY),
    });

    await fetch('/api/push/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(subscription.toJSON()),
    });
  };

  register().catch(err => console.warn('Push registration failed:', err));
}, []);
```

**Important:** `applicationServerKey` must be a `Uint8Array`, not a raw base64 string. The `urlBase64ToUint8Array` helper is required.

### Anti-Patterns to Avoid
- **Calling `webpush()` with the same `vapid_claims` dict multiple times:** The dict is mutated. Create a fresh dict per call.
- **Calling `webpush()` outside try/except:** Throws `WebPushException` if push service returns 4xx/5xx. Always catch and log; never let it propagate to crash the scheduler job.
- **Storing subscription in memory only:** The scheduler process can restart between scrape runs. The `/data/push_subscription.json` file survives Docker container restarts because `/data/` is a volume mount.
- **Sending one push per listing:** Violates NOTF-04. Always send a single batched notification per run.
- **Using `headless` VAPID key format for `applicationServerKey`:** Must convert base64url to `Uint8Array` before passing to `pushManager.subscribe()`.
- **Registering sw.js at a subpath (e.g., `/src/sw.js`):** Service worker scope is limited to its path. Must be at `/sw.js` (served from `public/`) for full-app coverage. Vite serves `public/` as-is at `/`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| VAPID JWT signing + payload encryption | Custom crypto + JWT lib | `pywebpush.webpush()` | AES128GCM + EC key derivation are non-trivial; pywebpush handles RFC 8291 + RFC 8292 |
| VAPID key generation | `openssl ecparam` + manual base64 encoding | `npx web-push generate-vapid-keys` | One command, correct format, no manual encoding errors |
| Push payload encoding | `cryptography` lib directly | `pywebpush` (wraps it) | Correct encryption scheme (aes128gcm) requires exact parameter setup |

**Key insight:** Web Push encryption (RFC 8291) involves EC Diffie-Hellman key agreement + HKDF + AES-128-GCM. `pywebpush` handles this entirely. The application layer only needs to call `webpush(subscription_info, data, vapid_private_key, vapid_claims)`.

## Common Pitfalls

### Pitfall 1: `vapid_claims` Dict Mutation
**What goes wrong:** pywebpush mutates the `vapid_claims` dict to add `aud` and `exp`. On a second call with the same dict, `exp` may be in the past (if same object reused across runs).
**Why it happens:** Library modifies the input dict in place (design of pywebpush 2.x).
**How to avoid:** Construct a fresh `{"sub": "mailto:..."}` dict inside the send function on every call.
**Warning signs:** `WebPushException` with 401 or "exp" error after first successful send.

### Pitfall 2: iOS Requires "Add to Home Screen"
**What goes wrong:** Web Push on iOS (Safari, Chrome, Edge on iOS 16.4+) only works when the app is installed as a PWA on the Home Screen. Browsing in Safari will not allow subscriptions — `pushManager.subscribe()` will fail silently or throw.
**Why it happens:** Apple's implementation requires standalone PWA mode for push permissions.
**How to avoid:** For single-user use, add a one-time advisory in the UI: "For notifications, add to Home Screen first." Include a `manifest.json` with `"display": "standalone"`. No need for a full PWA setup otherwise.
**Warning signs:** `pushManager` is undefined or `subscribe()` rejects on iOS browser (not standalone).

### Pitfall 3: sw.js Not Served from Root
**What goes wrong:** If `sw.js` is placed anywhere other than `frontend/public/sw.js`, Vite will not serve it at `/sw.js`, and `navigator.serviceWorker.register('/sw.js')` will 404.
**Why it happens:** Vite treats files in `src/` as bundled modules (not static). Files in `public/` are copied verbatim to `dist/` root at build time.
**How to avoid:** Always place `sw.js` in `frontend/public/`. Confirm with `curl http://localhost:5173/sw.js` during dev.
**Warning signs:** `ServiceWorker registration failed: A bad HTTP response code (404) was received`.

### Pitfall 4: Nginx Missing `Service-Worker-Allowed` Header
**What goes wrong:** In production (Nginx container), a service worker registered at `/sw.js` has scope `/` by default. If Nginx strips headers or adds CSP that blocks service workers, push notifications silently fail.
**Why it happens:** Nginx default config has no explicit service worker header handling.
**How to avoid:** The existing `nginx.conf` uses `try_files $uri $uri/ /index.html` which serves `/sw.js` correctly as a static file. No additional header needed for default `/` scope. Verify after deploy.
**Warning signs:** Console error "The path of the provided scope is not under the max scope allowed".

### Pitfall 5: Subscription JSON File Not on Volume
**What goes wrong:** `push_subscription.json` written to a path inside the container (not `/data/`) is lost on container restart. Backend starts, tries to send push, file is missing — silent failure.
**Why it happens:** Docker containers are ephemeral; only volume-mounted paths persist.
**How to avoid:** Write subscription to `/data/push_subscription.json`. The `/data/` directory is the existing volume mount (same as `listings.db`). Confirm path in `docker-compose.yml`.
**Warning signs:** Push works once after container start, then fails after any restart.

### Pitfall 6: `notified_at` in Listing Model Not Reflected in DB
**What goes wrong:** Adding the SQLAlchemy column without running the Alembic migration causes `OperationalError: table listings has no column named notified_at`.
**Why it happens:** SQLAlchemy model and DB schema are independent. `Base.metadata.create_all(checkfirst=True)` in `main.py` lifespan does NOT alter existing tables.
**How to avoid:** Always run `alembic upgrade head` after adding `notified_at` to the model. Migration file `0003_add_notified_at.py` must exist.
**Warning signs:** `OperationalError` on first `notified_at IS NULL` query.

## Code Examples

### VAPID Key Generation (one-time setup)
```bash
# Source: https://www.npmjs.com/package/web-push
npx web-push generate-vapid-keys

# Output:
# Public Key: BAwUJxIa7mJZMqu78Tfy2vqbp1tFuj4KwX3gRuF2e_5WGB0tGnvCBGtvVDEa6YdjnjAors3E1WBlcCTow6pGg
# Private Key: Mmi54fYPtCgTQB1_8-QoH0xJOq3H6z8nBUG71t0ezCA

# Add to .env:
# VAPID_PUBLIC_KEY=BAwUJx...
# VAPID_PRIVATE_KEY=Mmi54f...
# VITE_VAPID_PUBLIC_KEY=BAwUJx...
```

### Config additions (backend/app/config.py)
```python
# Source: CONTEXT.md locked decisions
vapid_public_key: str = ""
vapid_private_key: str = ""
vapid_contact_email: str = "admin@example.com"  # sub claim; any valid contact
```

### New listing detection query
```python
# Source: CONTEXT.md locked decisions — notified_at pattern
from sqlalchemy import select, and_, update
from app.models.listing import Listing

async def get_unnotified_listings(session, run_start_time):
    stmt = select(Listing).where(
        and_(
            Listing.notified_at.is_(None),
            Listing.created_at >= run_start_time,
            Listing.is_active == True,
        )
    )
    result = await session.execute(stmt)
    return result.scalars().all()

async def stamp_notified(session, listing_ids):
    from datetime import datetime, timezone
    stmt = (
        update(Listing)
        .where(Listing.id.in_(listing_ids))
        .values(notified_at=datetime.now(timezone.utc))
    )
    await session.execute(stmt)
    await session.commit()
```

### FastAPI push router skeleton
```python
# Source: patterns from backend/app/routers/listings.py
from fastapi import APIRouter
from pathlib import Path
import json

router = APIRouter(prefix="/api/push", tags=["push"])
SUBSCRIPTION_FILE = Path("/data/push_subscription.json")

@router.post("/subscribe")
async def subscribe(subscription: dict):
    SUBSCRIPTION_FILE.write_text(json.dumps(subscription))
    return {"status": "ok"}

@router.get("/vapid-public-key")
async def vapid_public_key():
    from app.config import settings
    return {"publicKey": settings.vapid_public_key}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `aesgcm` content encoding | `aes128gcm` (RFC 8188) | pywebpush 1.x → 2.x | Default changed; old encoding deprecated but still supported |
| GCM/FCM direct support | FCM legacy GCM disabled | June 2024 | Chrome Android push still works via FCM v1 (pywebpush handles automatically) |
| Separate `py-vapid` install | Bundled in pywebpush | 2.0.0+ | No need for `pip install py-vapid` separately |

**Deprecated/outdated:**
- `send_web_push()` function name: pywebpush 2.x uses `webpush()` as the primary one-call function. Some older docs show `send_web_push()` which is a community alias — use `webpush()`.
- FCM/GCM legacy support: removed June 2024. Chrome push still works via modern FCM endpoint (transparent).

## Open Questions

1. **iOS "Add to Home Screen" UX**
   - What we know: iOS 16.4+ supports Web Push but only in standalone PWA mode. The app currently has no `manifest.json`.
   - What's unclear: Does the planner want a full `manifest.json` + icons, or just a minimal advisory toast in the UI?
   - Recommendation: Include creating a minimal `manifest.json` (no icons required, just `"display": "standalone"` and `"start_url": "/"`) in Wave 1 tasks. This unblocks iOS without becoming a large task.

2. **VAPID contact email config field**
   - What we know: `vapid_claims` requires a `"sub"` field which must be a `mailto:` email. Not currently in `config.py`.
   - What's unclear: Whether to hardcode a placeholder or add a proper config field.
   - Recommendation: Add `vapid_contact_email: str = "admin@localhost"` to `Settings` class and `.env`. Low risk.

3. **Notification icon**
   - What we know: `showNotification()` accepts an `icon` path. No app icon currently exists in `frontend/public/`.
   - What's unclear: Does the user want a custom icon, or is a default browser icon acceptable?
   - Recommendation: Plan a minimal `icon-192.png` placeholder (can be a simple generated PNG). Not a blocker for the notification to fire.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js / npx | VAPID key generation (one-time) | Run in Docker or local | Already used by frontend | `openssl ecparam` + manual base64 encoding |
| pywebpush | Backend push sender | Not yet installed | 2.3.0 (pip install needed) | — |
| Docker + volume at `/data/` | Subscription file persistence | Already exists (listings.db uses it) | — | — |
| Browser Push API | Frontend subscription | Standard in Chrome/Firefox/Safari iOS 16.4+ | — | Graceful degradation if not available |

**Missing dependencies with no fallback:**
- `pywebpush==2.3.0` must be added to `backend/requirements.txt` and Docker image.

**Missing dependencies with fallback:**
- VAPID key generation: primary is `npx web-push generate-vapid-keys`; fallback is `openssl ecparam -name prime256v1 -genkey -noout | openssl pkcs8 -topk8 -nocrypt` + manual base64url encoding.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio (backend); vitest 4.x (frontend) |
| Config file | `backend/pytest.ini` or inline `pyproject.toml` |
| Quick run command | `pytest backend/tests/test_notifier.py -x` |
| Full suite command | `pytest backend/tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| NOTF-03 | `run_notification_job` sends push when new listings exist | unit | `pytest backend/tests/test_notifier.py::test_sends_push_when_new_listings -x` | Wave 0 |
| NOTF-03 | `run_notification_job` does NOT send push when no new listings | unit | `pytest backend/tests/test_notifier.py::test_no_push_when_no_new_listings -x` | Wave 0 |
| NOTF-04 | Only one push sent per job run (batch, not per listing) | unit | `pytest backend/tests/test_notifier.py::test_single_push_per_run -x` | Wave 0 |
| NOTF-03 | `notified_at` is stamped after successful push | unit | `pytest backend/tests/test_notifier.py::test_notified_at_stamped -x` | Wave 0 |
| NOTF-03 | `POST /api/push/subscribe` stores subscription JSON | integration | `pytest backend/tests/test_api.py::test_push_subscribe -x` | Wave 0 |
| NOTF-03 | `GET /api/push/vapid-public-key` returns public key | integration | `pytest backend/tests/test_api.py::test_vapid_public_key -x` | Wave 0 |
| NOTF-01 | Twilio `send_whatsapp()` stub exists and is importable | unit | `pytest backend/tests/test_notifier.py::test_whatsapp_stub_importable -x` | Wave 0 |
| NOTF-03 | Alembic migration 0003 adds `notified_at` column | smoke | `alembic upgrade head` in Docker — manual check | manual |

### Sampling Rate
- **Per task commit:** `pytest backend/tests/test_notifier.py -x`
- **Per wave merge:** `pytest backend/tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_notifier.py` — unit tests for notification logic (NOTF-03, NOTF-04)
- [ ] `backend/app/notifier.py` — module under test (created in Wave 1, test file created in Wave 0)

*(Existing `backend/tests/test_api.py` will be extended with push endpoint tests — file exists.)*

## Sources

### Primary (HIGH confidence)
- [pywebpush PyPI page](https://pypi.org/project/pywebpush/) — version 2.3.0 confirmed, `webpush()` function signature
- [pywebpush README](https://github.com/web-push-libs/pywebpush/blob/main/README.md) — full API with VAPID params, subscription_info format
- [MDN — PushManager.subscribe()](https://developer.mozilla.org/en-US/docs/Web/API/PushManager/subscribe) — applicationServerKey format, userVisibleOnly requirement
- [MDN — ServiceWorkerRegistration.showNotification()](https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerRegistration/showNotification) — options object, push event pattern
- [MDN — notificationclick event](https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerGlobalScope/notificationclick_event) — clients.openWindow + focus pattern
- `backend/alembic/versions/0002_add_neighborhood.py` — local migration pattern verified
- `backend/app/scheduler.py` — local deferred-import and job structure verified
- `backend/app/config.py` — existing Twilio fields and `app_url` verified

### Secondary (MEDIUM confidence)
- [web-push npm](https://www.npmjs.com/package/web-push) — `npx web-push generate-vapid-keys` output format confirmed
- [Apple Developer — Web Push for iOS](https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers) — iOS 16.4+ standalone PWA requirement
- Vite static assets documentation — `public/` directory served at root path, sw.js placement confirmed

### Tertiary (LOW confidence)
- Community blog posts re: `vapid_claims` dict mutation behavior in pywebpush 2.x — reported by multiple sources, not explicitly in official docs; flag for verification during implementation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pywebpush 2.3.0 version confirmed via `pip index versions`, API verified via official README
- Architecture: HIGH — follows established project patterns (migration, scheduler, deferred imports) verified from codebase
- Pitfalls: HIGH for iOS/sw.js placement (official docs); MEDIUM for vapid_claims mutation (community sources)
- Validation architecture: HIGH — follows existing pytest pattern in codebase

**Research date:** 2026-04-03
**Valid until:** 2026-05-03 (pywebpush is stable; Web Push browser APIs are stable)
