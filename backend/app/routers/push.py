"""Push notification API endpoints for Phase 7.

Endpoints:
- POST /api/push/subscribe  — store browser push subscription JSON to /data/push_subscription.json
- GET  /api/push/vapid-public-key — return VAPID public key for frontend subscription setup
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/api/push", tags=["push"])

# Subscription file path — must be on the /data volume mount so it survives container restarts
SUBSCRIPTION_FILE = Path("/data/push_subscription.json")


@router.post("/subscribe")
async def subscribe(subscription: dict) -> dict:
    """Store the browser push subscription JSON to the volume-mounted file.

    The frontend POSTs the PushSubscription.toJSON() object here after
    requesting push permission. Single-user app — one subscription file is enough.
    """
    SUBSCRIPTION_FILE.write_text(json.dumps(subscription), encoding="utf-8")
    return {"status": "ok"}


@router.get("/vapid-public-key")
async def vapid_public_key() -> dict:
    """Return the VAPID public key for the frontend to use in PushManager.subscribe().

    The frontend converts this base64url string to a Uint8Array before passing
    it as `applicationServerKey`. See frontend/src/hooks/usePushSubscription.js.
    """
    return {"publicKey": settings.vapid_public_key}
