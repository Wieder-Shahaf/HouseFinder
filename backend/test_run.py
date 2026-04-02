import asyncio
import os
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_listings.db")

from app.database import async_session_factory, engine
from app.models.listing import Base
from app.scrapers.yad2 import run_yad2_scraper

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as db:
        result = await run_yad2_scraper(db)
        print(result)

asyncio.run(main())
