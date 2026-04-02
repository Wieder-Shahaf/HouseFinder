"""
Dev seed script — inserts test listings into the local SQLite database.
Run inside the backend container:
  docker compose -f docker-compose.yml -f docker-compose.dev.yml exec backend python seed_dev.py
"""
import asyncio
from datetime import datetime

from sqlalchemy import text

from app.database import engine, Base
from app.models.listing import Listing
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

SEED_LISTINGS = [
    {
        "source": "yad2",
        "source_id": "seed-001",
        "title": "דירה 3 חדרים בכרמל עם נוף לים",
        "price": 3500,
        "rooms": 3.0,
        "size_sqm": 75,
        "address": "רחוב הנשיא 15, כרמל, חיפה",
        "contact_info": "ישראל ישראלי",
        "lat": 32.7940,
        "lng": 34.9896,
        "llm_confidence": 0.92,
        "source_badge": "yad2",
        "url": "https://www.yad2.co.il/item/seed-001",
        "post_date": datetime(2026, 4, 1),
    },
    {
        "source": "yad2",
        "source_id": "seed-002",
        "title": "דירת 2.5 חדרים במרכז העיר",
        "price": 2800,
        "rooms": 2.5,
        "size_sqm": 55,
        "address": "רחוב הרצל 10, מרכז העיר, חיפה",
        "contact_info": "רחל כהן",
        "lat": 32.8156,
        "lng": 34.9894,
        "llm_confidence": 0.85,
        "source_badge": "yad2",
        "url": "https://www.yad2.co.il/item/seed-002",
        "post_date": datetime(2026, 4, 1),
    },
    {
        "source": "facebook",
        "source_id": "seed-003",
        "title": "להשכרה דירה 4 חדרים נווה שאנן",
        "price": 4200,
        "rooms": 4.0,
        "size_sqm": 95,
        "address": "רחוב בר יהודה 8, נווה שאנן, חיפה",
        "contact_info": "דוד לוי",
        "lat": 32.7823,
        "lng": 35.0134,
        "llm_confidence": 0.88,
        "source_badge": "facebook",
        "url": "https://www.facebook.com/groups/seed-003",
        "post_date": datetime(2026, 3, 30),
    },
    {
        "source": "madlan",
        "source_id": "seed-004",
        "title": "דירה 3.5 חדרים הדר",
        "price": 3800,
        "rooms": 3.5,
        "size_sqm": 85,
        "address": "רחוב מוריה 5, הדר, חיפה",
        "contact_info": "שרה מזרחי",
        "lat": 32.8089,
        "lng": 34.9987,
        "llm_confidence": 0.79,
        "source_badge": "madlan",
        "url": "https://www.madlan.co.il/listing/seed-004",
        "post_date": datetime(2026, 4, 2),
    },
    {
        "source": "yad2",
        "source_id": "seed-005",
        "title": "סטודיו מרוהט לחלוטין קרית אליעזר",
        "price": 2200,
        "rooms": 1.0,
        "size_sqm": 35,
        "address": "רחוב יפו 120, קרית אליעזר, חיפה",
        "contact_info": "מיכל גל",
        "lat": 32.8241,
        "lng": 34.9712,
        "llm_confidence": 0.91,
        "source_badge": "yad2",
        "url": "https://www.yad2.co.il/item/seed-005",
        "post_date": datetime(2026, 4, 2),
    },
]


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        inserted = 0
        skipped = 0
        for data in SEED_LISTINGS:
            existing = await session.execute(
                text("SELECT id FROM listings WHERE source=:s AND source_id=:sid"),
                {"s": data["source"], "sid": data["source_id"]},
            )
            if existing.fetchone():
                skipped += 1
                continue
            listing = Listing(**data)
            session.add(listing)
            inserted += 1
        await session.commit()
        print(f"Seed complete: {inserted} inserted, {skipped} skipped (already exist).")


if __name__ == "__main__":
    asyncio.run(seed())
