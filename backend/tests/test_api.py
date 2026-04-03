"""API endpoint tests for Phase 3: GET /listings filters, PUT seen/favorited, GET /health."""
from __future__ import annotations

import pytest

from app.scheduler import _health


# ────────────────────────────────────────────
# GET /listings — default behavior
# ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_listings_default(client, seed_listings):
    """D-03 + D-04: Default response includes active + high-confidence only."""
    response = await client.get("/api/listings/")
    assert response.status_code == 200
    data = response.json()
    source_ids = {item["source_id"] for item in data}
    # active-high-conf (conf=0.92, active=True) and seen-listing (conf=0.85, active=True) included
    assert "active-high-conf" in source_ids
    assert "seen-listing" in source_ids
    # active-low-conf (conf=0.45) excluded by D-04
    assert "active-low-conf" not in source_ids
    # inactive excluded by D-03
    assert "inactive" not in source_ids


@pytest.mark.asyncio
async def test_get_listings_excludes_low_confidence(client, seed_listings):
    """D-04: Listings with llm_confidence < 0.7 are excluded from default response."""
    response = await client.get("/api/listings/")
    data = response.json()
    for item in data:
        assert item["llm_confidence"] >= 0.7


@pytest.mark.asyncio
async def test_get_listings_excludes_inactive(client, seed_listings):
    """D-03: Listings with is_active=False are excluded."""
    response = await client.get("/api/listings/")
    data = response.json()
    for item in data:
        assert item["is_active"] is True


# ────────────────────────────────────────────
# GET /listings — filter params
# ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_listings_price_filter(client, seed_listings):
    """price_max=3200 returns only listings with price <= 3200."""
    response = await client.get("/api/listings/", params={"price_max": 3200})
    assert response.status_code == 200
    data = response.json()
    for item in data:
        assert item["price"] <= 3200
    # seen-listing has price=3000, should be included
    source_ids = {item["source_id"] for item in data}
    assert "seen-listing" in source_ids
    # active-high-conf has price=3500, should be excluded
    assert "active-high-conf" not in source_ids


@pytest.mark.asyncio
async def test_get_listings_neighborhood_filter(client, seed_listings):
    """D-05: neighborhood=כרמל returns only listings whose address contains כרמל."""
    response = await client.get("/api/listings/", params={"neighborhood": "כרמל"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert "כרמל" in data[0]["address"]
    assert data[0]["source_id"] == "active-high-conf"


@pytest.mark.asyncio
async def test_get_listings_seen_filter(client, seed_listings):
    """is_seen=true returns only seen listings; is_seen=false excludes them."""
    # Only seen
    response = await client.get("/api/listings/", params={"is_seen": True})
    data = response.json()
    assert all(item["is_seen"] is True for item in data)
    assert len(data) == 1
    assert data[0]["source_id"] == "seen-listing"

    # Only unseen
    response = await client.get("/api/listings/", params={"is_seen": False})
    data = response.json()
    assert all(item["is_seen"] is False for item in data)


@pytest.mark.asyncio
async def test_get_listings_rooms_filter(client, seed_listings):
    """rooms_min=3.0 returns only listings with rooms >= 3.0."""
    response = await client.get("/api/listings/", params={"rooms_min": 3.0})
    data = response.json()
    for item in data:
        assert item["rooms"] >= 3.0


@pytest.mark.asyncio
async def test_get_listings_ordered_by_created_at_desc(client, seed_listings):
    """Results are ordered by created_at descending (newest first)."""
    response = await client.get("/api/listings/")
    data = response.json()
    if len(data) > 1:
        dates = [item["created_at"] for item in data]
        assert dates == sorted(dates, reverse=True)


# ────────────────────────────────────────────
# PUT /listings/{id}/seen and /favorited
# ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mark_seen(client, seed_listings):
    """PUT /listings/{id}/seen returns 200 with is_seen=True."""
    # First get a listing to find its id
    response = await client.get("/api/listings/")
    listing_id = response.json()[0]["id"]

    response = await client.put(f"/api/listings/{listing_id}/seen")
    assert response.status_code == 200
    data = response.json()
    assert data["is_seen"] is True
    assert data["id"] == listing_id


@pytest.mark.asyncio
async def test_mark_favorited(client, seed_listings):
    """PUT /listings/{id}/favorited returns 200 with is_favorited=True."""
    response = await client.get("/api/listings/")
    listing_id = response.json()[0]["id"]

    response = await client.put(f"/api/listings/{listing_id}/favorited")
    assert response.status_code == 200
    data = response.json()
    assert data["is_favorited"] is True
    assert data["id"] == listing_id


@pytest.mark.asyncio
async def test_mark_seen_not_found(client, seed_listings):
    """PUT /listings/99999/seen returns 404 with Hebrew detail."""
    response = await client.put("/api/listings/99999/seen")
    assert response.status_code == 404
    assert response.json()["detail"] == "מודעה לא נמצאה"


@pytest.mark.asyncio
async def test_mark_favorited_not_found(client, seed_listings):
    """PUT /listings/99999/favorited returns 404 with Hebrew detail."""
    response = await client.put("/api/listings/99999/favorited")
    assert response.status_code == 404
    assert response.json()["detail"] == "מודעה לא נמצאה"


# ────────────────────────────────────────────
# GET /health
# ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_never_run(client):
    """GET /health with no prior runs returns yad2 with null fields."""
    # Ensure clean state
    _health["yad2"] = None
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "scrapers" in data
    assert data["scrapers"]["yad2"]["last_run"] is None
    assert data["scrapers"]["yad2"]["success"] is None


@pytest.mark.asyncio
async def test_health_with_scraper_state(client):
    """GET /health with prior run data returns populated scraper state."""
    _health["yad2"] = {
        "last_run": "2026-04-01T12:00:00+00:00",
        "listings_found": 10,
        "listings_inserted": 5,
        "listings_rejected": 2,
        "listings_flagged": 1,
        "success": True,
        "errors": [],
    }
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["scrapers"]["yad2"]["last_run"] == "2026-04-01T12:00:00+00:00"
    assert data["scrapers"]["yad2"]["listings_inserted"] == 5
    assert data["scrapers"]["yad2"]["success"] is True
    # Reset
    _health["yad2"] = None


# ────────────────────────────────────────────
# Phase 7: Push notification endpoints
# ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_push_subscribe(client):
    """POST /api/push/subscribe stores subscription JSON and returns {"status": "ok"}."""
    from unittest.mock import patch, MagicMock

    subscription_body = {
        "endpoint": "https://push.example.com/push/abc",
        "keys": {"p256dh": "test-p256dh-key", "auth": "test-auth-key"},
    }

    written_content = {}

    def mock_write_text(content, encoding="utf-8"):
        written_content["data"] = content

    with patch("app.routers.push.SUBSCRIPTION_FILE") as mock_path:
        mock_path.write_text = mock_write_text
        response = await client.post("/api/push/subscribe", json=subscription_body)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify written content matches the request body
    import json
    assert written_content.get("data") is not None
    stored = json.loads(written_content["data"])
    assert stored["endpoint"] == subscription_body["endpoint"]
    assert stored["keys"]["p256dh"] == subscription_body["keys"]["p256dh"]
    assert stored["keys"]["auth"] == subscription_body["keys"]["auth"]


@pytest.mark.asyncio
async def test_vapid_public_key(client):
    """GET /api/push/vapid-public-key returns {"publicKey": "<configured key>"}."""
    from unittest.mock import patch

    with patch("app.routers.push.settings") as mock_settings:
        mock_settings.vapid_public_key = "test-key-123"
        response = await client.get("/api/push/vapid-public-key")

    assert response.status_code == 200
    assert response.json() == {"publicKey": "test-key-123"}
