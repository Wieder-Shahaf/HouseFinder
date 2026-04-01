import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.models.listing import Listing


async def test_listings_table_columns(db_engine):
    """Verify all 22 expected columns exist in the listings table."""
    expected_columns = {
        "id",
        "source",
        "source_id",
        "lat",
        "lng",
        "is_seen",
        "is_favorited",
        "raw_data",
        "llm_confidence",
        "dedup_fingerprint",
        "title",
        "price",
        "rooms",
        "size_sqm",
        "address",
        "contact_info",
        "post_date",
        "url",
        "source_badge",
        "created_at",
        "updated_at",
        "is_active",
    }

    async with db_engine.connect() as conn:
        column_names = await conn.run_sync(
            lambda sync_conn: {
                col["name"] for col in inspect(sync_conn).get_columns("listings")
            }
        )

    assert expected_columns == column_names, (
        f"Column mismatch. Missing: {expected_columns - column_names}, "
        f"Extra: {column_names - expected_columns}"
    )


async def test_dedup_constraint(db_session):
    """Inserting a duplicate (source, source_id) pair must raise IntegrityError."""
    listing1 = Listing(source="yad2", source_id="123")
    db_session.add(listing1)
    await db_session.commit()

    listing2 = Listing(source="yad2", source_id="123")
    db_session.add(listing2)

    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_nullable_fields(db_session):
    """Insert a Listing with only source and source_id — all other fields nullable."""
    listing = Listing(source="madlan", source_id="abc-001")
    db_session.add(listing)
    await db_session.commit()
    await db_session.refresh(listing)

    assert listing.id is not None
    assert listing.title is None
    assert listing.price is None
    assert listing.lat is None
