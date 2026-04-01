from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers.listings import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # No table creation here — Alembic handles schema migrations
    yield


app = FastAPI(title="ApartmentFinder API", lifespan=lifespan)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


app.include_router(router)
