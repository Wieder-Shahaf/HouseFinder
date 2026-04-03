"""Unit tests for Phase 7 notification pipeline.

Tests cover:
- run_notification_job sends push when new listings exist (NOTF-03)
- run_notification_job does NOT send push when no new listings
- Exactly one push per run regardless of listing count (NOTF-04)
- notified_at is stamped on all notified listings after successful push
- No exception when push_subscription.json is missing (log warning + return)
- No exception when webpush() raises WebPushException
- send_whatsapp() stub is importable and returns None (NOTF-01)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.models.listing import Listing


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_SUBSCRIPTION = json.dumps(
    {
        "endpoint": "https://push.example.com/push/abc",
        "keys": {"p256dh": "test-p256dh", "auth": "test-auth"},
    }
)

RUN_START = datetime(2026, 4, 1, 10, 0, 0, tzinfo=timezone.utc)


def _make_listing(db_session, source_id: str, created_at=None, notified_at=None):
    """Create a listing with notified_at=None (new listing awaiting notification)."""
    listing = Listing(
        source="yad2",
        source_id=source_id,
        llm_confidence=0.9,
        is_active=True,
        created_at=created_at or RUN_START,
        updated_at=RUN_START,
        notified_at=notified_at,
    )
    db_session.add(listing)
    return listing


# ---------------------------------------------------------------------------
# Test: sends push when new listings exist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sends_push_when_new_listings(db_session):
    """NOTF-03: run_notification_job sends push when new listings with notified_at IS NULL exist."""
    from app.notifier import run_notification_job

    _make_listing(db_session, "listing-a")
    _make_listing(db_session, "listing-b")
    await db_session.commit()

    with (
        patch("app.notifier.webpush") as mock_webpush,
        patch("pathlib.Path.read_text", return_value=FAKE_SUBSCRIPTION),
    ):
        await run_notification_job(db_session, RUN_START)

    mock_webpush.assert_called_once()
    call_kwargs = mock_webpush.call_args
    # Payload must include Hebrew count message
    payload_data = call_kwargs.kwargs.get("data") or call_kwargs.args[1] if call_kwargs.args else call_kwargs.kwargs.get("data")
    assert "2 דירות חדשות" in payload_data


@pytest.mark.asyncio
async def test_no_push_when_no_new_listings(db_session):
    """NOTF-03 negative: no push when no new listings found."""
    from app.notifier import run_notification_job

    # No listings added — empty DB
    with (
        patch("app.notifier.webpush") as mock_webpush,
        patch("pathlib.Path.read_text", return_value=FAKE_SUBSCRIPTION),
    ):
        await run_notification_job(db_session, RUN_START)

    mock_webpush.assert_not_called()


@pytest.mark.asyncio
async def test_single_push_per_run(db_session):
    """NOTF-04: exactly one webpush() call even with 5 new listings."""
    from app.notifier import run_notification_job

    for i in range(5):
        _make_listing(db_session, f"listing-{i}")
    await db_session.commit()

    with (
        patch("app.notifier.webpush") as mock_webpush,
        patch("pathlib.Path.read_text", return_value=FAKE_SUBSCRIPTION),
    ):
        await run_notification_job(db_session, RUN_START)

    assert mock_webpush.call_count == 1


@pytest.mark.asyncio
async def test_notified_at_stamped(db_session):
    """NOTF-03: notified_at is set on all notified listings after successful push."""
    from app.notifier import run_notification_job
    from sqlalchemy import select

    listings = [_make_listing(db_session, f"stamp-{i}") for i in range(3)]
    await db_session.commit()

    with (
        patch("app.notifier.webpush"),
        patch("pathlib.Path.read_text", return_value=FAKE_SUBSCRIPTION),
    ):
        await run_notification_job(db_session, RUN_START)

    # Refresh and check
    from app.models.listing import Listing

    result = await db_session.execute(
        select(Listing).where(Listing.source_id.in_(["stamp-0", "stamp-1", "stamp-2"]))
    )
    updated = result.scalars().all()
    assert len(updated) == 3
    for listing in updated:
        assert listing.notified_at is not None, f"notified_at not stamped on {listing.source_id}"


@pytest.mark.asyncio
async def test_no_error_when_subscription_missing(db_session):
    """NOTF-03: no exception when push_subscription.json is missing — logs warning and returns."""
    from app.notifier import run_notification_job

    _make_listing(db_session, "no-sub-listing")
    await db_session.commit()

    with (
        patch("app.notifier.webpush") as mock_webpush,
        patch("pathlib.Path.read_text", side_effect=FileNotFoundError("File not found")),
    ):
        # Must not raise
        await run_notification_job(db_session, RUN_START)

    mock_webpush.assert_not_called()


@pytest.mark.asyncio
async def test_no_error_when_webpush_fails(db_session):
    """NOTF-03: no exception when webpush() raises WebPushException — catches and logs."""
    from app.notifier import run_notification_job
    from pywebpush import WebPushException
    from sqlalchemy import select

    _make_listing(db_session, "fail-push-listing")
    await db_session.commit()

    with (
        patch("app.notifier.webpush", side_effect=WebPushException("push failed")),
        patch("pathlib.Path.read_text", return_value=FAKE_SUBSCRIPTION),
    ):
        # Must not raise
        await run_notification_job(db_session, RUN_START)

    # notified_at must NOT be stamped when push failed
    result = await db_session.execute(
        select(Listing).where(Listing.source_id == "fail-push-listing")
    )
    listing = result.scalars().first()
    assert listing.notified_at is None, "notified_at should NOT be set when push failed"


def test_whatsapp_stub_importable():
    """NOTF-01: send_whatsapp stub is importable and returns None (inactive stub)."""
    from app.notifier import send_whatsapp

    result = send_whatsapp(5, "http://example.com")
    assert result is None


def test_whatsapp_stub_full_signature():
    """NOTF-02: send_whatsapp accepts full NOTF-02 params for future activation."""
    from app.notifier import send_whatsapp

    result = send_whatsapp(
        count=3,
        url="http://example.com",
        price=3500,
        rooms=3.0,
        neighborhood="כרמל",
    )
    assert result is None
