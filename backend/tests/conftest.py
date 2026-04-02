from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.database import Base
from app.models.listing import Listing


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite://", echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.close()


@pytest_asyncio.fixture
async def client(db_engine):
    """HTTP test client with scheduler mocked out and DB overridden."""
    from app.database import get_db
    from app.main import app

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with patch("app.scheduler.scheduler") as mock_scheduler:
        mock_scheduler.start = MagicMock()
        mock_scheduler.shutdown = MagicMock()
        mock_scheduler.add_job = MagicMock()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seed_listings(db_engine):
    """Insert test listings into the in-memory DB for API tests."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        listings = [
            Listing(
                source="yad2", source_id="active-high-conf",
                price=3500, rooms=3.0, size_sqm=75,
                address="רחוב הנשיא 15, כרמל, חיפה",
                llm_confidence=0.92, is_active=True,
                is_seen=False, is_favorited=False,
                created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
                updated_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            ),
            Listing(
                source="yad2", source_id="active-low-conf",
                price=2800, rooms=2.5, size_sqm=55,
                address="רחוב הרצל 10, מרכז העיר, חיפה",
                llm_confidence=0.45, is_active=True,
                is_seen=False, is_favorited=False,
                created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
                updated_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            ),
            Listing(
                source="yad2", source_id="inactive",
                price=4000, rooms=3.5, size_sqm=90,
                address="רחוב מוריה 5, כרמל, חיפה",
                llm_confidence=0.88, is_active=False,
                is_seen=False, is_favorited=False,
                created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
                updated_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            ),
            Listing(
                source="yad2", source_id="seen-listing",
                price=3000, rooms=3.0, size_sqm=65,
                address="רחוב בר יהודה 8, נווה שאנן, חיפה",
                llm_confidence=0.85, is_active=True,
                is_seen=True, is_favorited=False,
                created_at=datetime(2026, 3, 30, tzinfo=timezone.utc),
                updated_at=datetime(2026, 3, 30, tzinfo=timezone.utc),
            ),
        ]
        session.add_all(listings)
        await session.commit()


# ---------------------------------------------------------------------------
# Phase 2 shared fixtures — Yad2 scraper and LLM verifier tests
# ---------------------------------------------------------------------------


@pytest.fixture
def yad2_api_response_fixture():
    """Mock Yad2 XHR API response with one valid Haifa rental listing in a target neighborhood."""
    return {
        "feed": {
            "feed_items": [
                {
                    "id": "abc123",
                    "title_1": "דירה 3 חדרים בכרמל",
                    "price": "3,500 ₪",
                    "row_4": [{"value": "3"}],  # rooms
                    "row_3": [{"value": '75 מ"ר'}],  # size
                    "city": "חיפה",
                    "neighborhood": "כרמל",
                    "street": "רחוב הנשיא 15",
                    "contact_name": "ישראל ישראלי",
                    "date": "2026-04-01",
                    "link_token": "abc123",
                }
            ]
        }
    }


@pytest.fixture
def llm_valid_rental_response():
    """Mock Anthropic SDK response for a verified rental listing."""
    return {
        "is_rental": True,
        "rejection_reason": None,
        "confidence": 0.92,
        "price": 3500,
        "rooms": 3.0,
        "size_sqm": 75,
        "address": "רחוב הנשיא 15, כרמל, חיפה",
        "contact_info": "ישראל ישראלי",
    }


@pytest.fixture
def llm_rejected_response():
    """Mock response for a 'looking for apartment' post."""
    return {
        "is_rental": False,
        "rejection_reason": "מחפש דירה - not a rental listing",
        "confidence": 0.95,
        "price": None,
        "rooms": None,
        "size_sqm": None,
        "address": None,
        "contact_info": None,
    }


@pytest.fixture
def llm_low_confidence_response():
    """Mock response with confidence below 0.7 threshold."""
    return {
        "is_rental": True,
        "rejection_reason": None,
        "confidence": 0.45,
        "price": 3000,
        "rooms": None,
        "size_sqm": None,
        "address": "חיפה",
        "contact_info": None,
    }
