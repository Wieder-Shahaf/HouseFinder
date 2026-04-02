"""Integration tests for neighborhood filter in GET /listings.

Uses FastAPI TestClient + in-memory SQLite. Verifies that the Phase 5
neighborhood exact-match filter (replacing address.ilike) works correctly.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models.listing import Listing


TEST_ENGINE = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
TestSessionFactory = async_sessionmaker(TEST_ENGINE, expire_on_commit=False)


async def override_get_db():
    async with TestSessionFactory() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def _listing(source_id: str, neighborhood: str | None, price: int = 3000) -> Listing:
    return Listing(
        source="yad2",
        source_id=source_id,
        price=price,
        rooms=3.0,
        lat=32.805 if neighborhood == "כרמל" else 32.82,
        lng=34.99 if neighborhood == "כרמל" else 35.02,
        neighborhood=neighborhood,
        is_active=True,
        llm_confidence=1.0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
async def test_neighborhood_filter_returns_matching_listings():
    """GET /listings?neighborhood=כרמל returns only כרמל listings."""
    async with TestSessionFactory() as session:
        session.add_all([
            _listing("karmel-1", "כרמל"),
            _listing("merkaz-1", "מרכז העיר"),
            _listing("none-1", None),
        ])
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/listings?neighborhood=כרמל")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["neighborhood"] == "כרמל"
    assert data[0]["source_id"] == "karmel-1"


@pytest.mark.asyncio
async def test_no_neighborhood_filter_returns_all_active():
    """GET /listings (no neighborhood param) returns all active listings."""
    async with TestSessionFactory() as session:
        session.add_all([
            _listing("karmel-1", "כרמל"),
            _listing("merkaz-1", "מרכז העיר"),
            _listing("none-1", None),
        ])
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/listings")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3


@pytest.mark.asyncio
async def test_neighborhood_filter_no_match_returns_empty():
    """Filtering by a neighborhood with no listings returns empty list."""
    async with TestSessionFactory() as session:
        session.add(_listing("karmel-1", "כרמל"))
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/listings?neighborhood=נווה שאנן")

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_neighborhood_field_present_in_response():
    """ListingResponse includes neighborhood field (not missing from schema)."""
    async with TestSessionFactory() as session:
        session.add(_listing("karmel-1", "כרמל"))
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/listings")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert "neighborhood" in data[0]
    assert data[0]["neighborhood"] == "כרמל"


@pytest.mark.asyncio
async def test_null_neighborhood_listing_not_returned_when_filtering():
    """Listing with neighborhood=NULL is excluded when a neighborhood filter is active."""
    async with TestSessionFactory() as session:
        session.add_all([
            _listing("karmel-1", "כרמל"),
            _listing("no-hood", None),
        ])
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/listings?neighborhood=כרמל")

    assert resp.status_code == 200
    data = resp.json()
    assert all(d["neighborhood"] == "כרמל" for d in data)
    assert not any(d["source_id"] == "no-hood" for d in data)
