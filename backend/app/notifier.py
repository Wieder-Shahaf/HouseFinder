"""Notification dispatch module for Phase 7.

Provides:
- run_notification_job: async function called by scheduler after each scrape run.
  Detects new listings (notified_at IS NULL + created_at >= run_start_time),
  sends a single Web Push notification with Hebrew content, then stamps notified_at.

- send_whatsapp: stub for future Twilio WhatsApp notifications (NOTF-01/NOTF-02).
  Inactive this phase — Meta template approval pending.
  Full NOTF-02 signature is present so future activation does not require changing callers.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pywebpush import WebPushException, webpush
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.listing import Listing

logger = logging.getLogger(__name__)

# Path to persisted push subscription JSON (Docker volume mount — survives restarts)
SUBSCRIPTION_FILE = Path("/data/push_subscription.json")


async def run_notification_job(session: AsyncSession, run_start_time: datetime) -> None:
    """Send a single Web Push notification if new listings were found in this scrape run.

    Query pattern: notified_at IS NULL AND created_at >= run_start_time AND is_active = True.
    One push per run (NOTF-04) — never per-listing.
    Stamps notified_at on all notified listings only after a successful push send.

    Errors are caught and logged — this function never raises to the caller so scheduler
    jobs continue even if notification delivery fails.
    """
    # 1. Query for new listings created during this scrape run that have not been notified yet
    stmt = select(Listing).where(
        and_(
            Listing.notified_at.is_(None),
            Listing.created_at >= run_start_time,
            Listing.is_active == True,  # noqa: E712
        )
    )
    result = await session.execute(stmt)
    new_listings = result.scalars().all()

    if not new_listings:
        logger.info("Notification job: no new listings to notify — skipping push")
        return

    count = len(new_listings)
    listing_ids = [listing.id for listing in new_listings]
    logger.info("Notification job: %d new listing(s) found — preparing push", count)

    # 2. Load push subscription from volume-mounted JSON file
    try:
        subscription_raw = SUBSCRIPTION_FILE.read_text(encoding="utf-8")
        subscription = json.loads(subscription_raw)
    except FileNotFoundError:
        logger.warning(
            "Notification job: no push subscription found at %s — skipping notification",
            SUBSCRIPTION_FILE,
        )
        return
    except Exception as exc:
        logger.warning("Notification job: failed to read push subscription: %s", exc)
        return

    # 3. Build Hebrew payload (NOTF-03)
    payload = {
        "title": f"{count} דירות חדשות",
        "body": "לחץ לפתיחת המפה",
        "url": settings.app_url,
    }

    # 4. Send Web Push via pywebpush (one call per run — NOTF-04)
    #    IMPORTANT: Create a fresh vapid_claims dict on every call.
    #    pywebpush mutates the dict in-place (adds 'aud' and 'exp'); reusing the
    #    same dict across runs causes 401 errors (see Research pitfall 1).
    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": f"mailto:{settings.vapid_contact_email}"},
        )
        logger.info("Notification job: push sent successfully for %d listings", count)
    except WebPushException as exc:
        logger.error(
            "Notification job: webpush() failed — %s. Push not delivered; notified_at NOT stamped.",
            exc,
        )
        # Do NOT stamp notified_at — listings will be retried on the next scrape run
        return

    # 5. Stamp notified_at on all successfully notified listings
    stamp_stmt = (
        update(Listing)
        .where(Listing.id.in_(listing_ids))
        .values(notified_at=datetime.now(timezone.utc))
    )
    await session.execute(stamp_stmt)
    await session.commit()
    logger.info("Notification job: stamped notified_at on listing IDs %s", listing_ids)


def send_whatsapp(
    count: int,
    url: str,
    price: Optional[int] = None,
    rooms: Optional[float] = None,
    neighborhood: Optional[str] = None,
) -> None:
    """Stub for future Twilio WhatsApp notifications (NOTF-01, NOTF-02).

    Inactive this phase — Meta message template approval is pending.
    Full NOTF-02 signature (price, rooms, neighborhood) is included so future
    activation does not require changes to callers.

    Do NOT import the Twilio SDK here. Do NOT make any API calls.
    """
    logger.info(
        "WhatsApp notifications deferred — Twilio template not yet approved "
        "(count=%d, url=%s, price=%s, rooms=%s, neighborhood=%s)",
        count,
        url,
        price,
        rooms,
        neighborhood,
    )
