"""Integration tests for run_dedup_pass using an in-memory SQLite session.

Tests verify the fingerprint-grouping, canonical-selection, and is_active=False
behavior without requiring a running server or real scraped data.
"""
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.geocoding import make_dedup_fingerprint, run_dedup_pass
from app.models.listing import Listing
from app.database import Base


@pytest_asyncio.fixture
async def session():
    """In-memory SQLite async session with fresh schema per test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _make_listing(
    source: str,
    source_id: str,
    price: int,
    rooms: float,
    lat: float,
    lng: float,
    fingerprint: str,
    is_active: bool = True,
    llm_confidence: float = 1.0,
) -> Listing:
    return Listing(
        source=source,
        source_id=source_id,
        price=price,
        rooms=rooms,
        lat=lat,
        lng=lng,
        dedup_fingerprint=fingerprint,
        is_active=is_active,
        llm_confidence=llm_confidence,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


SHARED_FP = make_dedup_fingerprint(3000, 3.0, 32.8191, 34.9998)


class TestRunDedupPass:
    @pytest.mark.asyncio
    async def test_no_listings_does_not_crash(self, session: AsyncSession):
        """Empty table — dedup pass runs without error."""
        await run_dedup_pass(session)  # should not raise

    @pytest.mark.asyncio
    async def test_single_listing_stays_active(self, session: AsyncSession):
        """One listing with a fingerprint — nothing to dedup."""
        listing = _make_listing("yad2", "yad2-1", 3000, 3.0, 32.8191, 34.9998, SHARED_FP)
        session.add(listing)
        await session.commit()

        await run_dedup_pass(session)

        await session.refresh(listing)
        assert listing.is_active is True

    @pytest.mark.asyncio
    async def test_duplicate_pair_deactivates_later_inserted(self, session: AsyncSession):
        """Two listings with same fingerprint — later id is deactivated."""
        listing1 = _make_listing("yad2", "yad2-1", 3000, 3.0, 32.8191, 34.9998, SHARED_FP)
        listing2 = _make_listing("madlan", "madl-1", 3000, 3.0, 32.8191, 34.9998, SHARED_FP)
        session.add_all([listing1, listing2])
        await session.commit()

        await run_dedup_pass(session)

        await session.refresh(listing1)
        await session.refresh(listing2)
        # Lower id = canonical = stays active
        assert listing1.is_active is True
        assert listing2.is_active is False

    @pytest.mark.asyncio
    async def test_three_duplicates_only_canonical_stays_active(self, session: AsyncSession):
        """Three listings sharing one fingerprint — only id=1 stays active."""
        listings = [
            _make_listing("yad2", f"yad2-{i}", 3000, 3.0, 32.8191, 34.9998, SHARED_FP)
            for i in range(3)
        ]
        session.add_all(listings)
        await session.commit()

        await run_dedup_pass(session)

        for lst in listings:
            await session.refresh(lst)

        active = [l for l in listings if l.is_active]
        assert len(active) == 1
        assert active[0].id == min(l.id for l in listings)

    @pytest.mark.asyncio
    async def test_different_fingerprints_both_stay_active(self, session: AsyncSession):
        """Two listings with different fingerprints — both remain active."""
        fp1 = make_dedup_fingerprint(3000, 3.0, 32.8191, 34.9998)
        fp2 = make_dedup_fingerprint(4000, 4.0, 32.825, 35.015)
        listing1 = _make_listing("yad2", "yad2-1", 3000, 3.0, 32.8191, 34.9998, fp1)
        listing2 = _make_listing("madlan", "madl-1", 4000, 4.0, 32.825, 35.015, fp2)
        session.add_all([listing1, listing2])
        await session.commit()

        await run_dedup_pass(session)

        await session.refresh(listing1)
        await session.refresh(listing2)
        assert listing1.is_active is True
        assert listing2.is_active is True

    @pytest.mark.asyncio
    async def test_already_inactive_listing_is_ignored(self, session: AsyncSession):
        """Listing already inactive is not selected for dedup (query filters is_active=True)."""
        listing1 = _make_listing("yad2", "yad2-1", 3000, 3.0, 32.8191, 34.9998, SHARED_FP)
        listing2 = _make_listing(
            "madlan", "madl-1", 3000, 3.0, 32.8191, 34.9998, SHARED_FP, is_active=False
        )
        session.add_all([listing1, listing2])
        await session.commit()

        await run_dedup_pass(session)

        await session.refresh(listing1)
        # listing1 is the only active one — stays active
        assert listing1.is_active is True

    @pytest.mark.asyncio
    async def test_listing_without_fingerprint_is_skipped(self, session: AsyncSession):
        """Listing with NULL fingerprint is not touched by dedup pass."""
        listing = _make_listing("yad2", "yad2-1", 3000, 3.0, 32.8191, 34.9998, SHARED_FP)
        listing_no_fp = Listing(
            source="madlan",
            source_id="madl-no-fp",
            price=3000,
            rooms=3.0,
            lat=32.8191,
            lng=34.9998,
            dedup_fingerprint=None,  # NULL fingerprint
            is_active=True,
            llm_confidence=1.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add_all([listing, listing_no_fp])
        await session.commit()

        await run_dedup_pass(session)

        await session.refresh(listing)
        await session.refresh(listing_no_fp)
        assert listing.is_active is True
        assert listing_no_fp.is_active is True  # not touched
