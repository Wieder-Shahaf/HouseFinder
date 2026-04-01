# Phase 1: Foundation - Research

**Researched:** 2026-04-01
**Domain:** Project scaffold, database schema, Docker Compose, VPS provisioning, Twilio WhatsApp setup
**Confidence:** MEDIUM-HIGH (most areas HIGH; DigitalOcean Israel region is a blocking gap — see Open Questions)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Use the full schema in the Phase 1 migration — include all listing data columns alongside the ROADMAP-required infrastructure columns. Do not defer listing fields to Phase 2.
- **D-02:** Infrastructure columns: `source`, `source_id`, `lat`, `lng`, `is_seen`, `is_favorited`, `raw_data`, `llm_confidence`, `dedup_fingerprint`
- **D-03:** Listing data columns: `title`, `price`, `rooms`, `size_sqm`, `address`, `contact_info`, `post_date`, `url`, `source_badge`
- **D-04:** Standard metadata columns: `created_at`, `updated_at` (timestamps), `is_active` (soft-delete flag)
- **D-05:** UNIQUE constraint on (`source`, `source_id`) — enforced at DB level
- **D-06:** Separate Compose files: `docker-compose.yml` (base) + `docker-compose.dev.yml` (hot-reload) + `docker-compose.prod.yml` (Nginx, optimized builds)
- **D-07:** Dev invocation: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up`
- **D-08:** FastAPI in dev: `uvicorn --reload` with source mounted as a volume
- **D-09:** Phase 1 is not complete until the app is accessible at a public URL — VPS provisioning is in-scope
- **D-10:** Claim GitHub Student Pack $200 DigitalOcean credit — no existing account yet
- **D-11:** Register free Namecheap `.me` domain via Student Pack — no existing domain yet
- **D-12:** Provision DigitalOcean droplet in **Israeli region** (required for Phase 8 Facebook Marketplace geo-filtering — INFRA-02) — **BLOCKED, see Open Questions**
- **D-13:** Deploy Docker stack on VPS with Nginx as reverse proxy + SSL termination
- **D-14:** Phase 1 plan includes a manual human-action task for Twilio setup
- **D-15:** Steps: create Twilio account, verify phone number, enable WhatsApp sandbox, obtain sandbox credentials, submit message template for Meta approval
- **D-16:** Template: `"{{count}} new listings found in Haifa. Open app: {{url}}"`
- **D-17:** Credentials in `.env` under `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`

### Claude's Discretion

- SQLAlchemy async model class design and column type choices (String lengths, etc.)
- Alembic migration naming and versioning conventions
- Exact Docker image versions (within the ranges in CLAUDE.md)
- Nginx config details (worker processes, SSL cert tool — Certbot is standard)
- `.env.example` structure and organization

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | All listings stored in SQLite database with normalized schema | SQLAlchemy 2.0 async + aiosqlite; full schema with 17 columns defined in D-01 through D-05 |
| DATA-02 | Same-source deduplication: listing already stored by its source ID is not inserted again | UNIQUE constraint on (source, source_id) at DB level via Alembic; SQLite enforces this natively |
| INFRA-01 | App deployed to a public URL accessible via smartphone browser | DigitalOcean droplet + Nginx + Let's Encrypt SSL via Certbot (Docker Compose prod config) |
| INFRA-02 | Server hosted in Israel (required for Facebook Marketplace geo-filtering) | **BLOCKED** — DigitalOcean has no Israeli region; see Open Questions for resolution path |
| INFRA-03 | Backend and frontend run via Docker Compose for simple deployment | Multi-file Compose strategy (D-06); FastAPI + Vite multi-stage build + Nginx confirmed pattern |
| INFRA-04 | No authentication required — single user, direct access to app URL | No auth middleware — Nginx serves app publicly; no FastAPI auth dependencies |
</phase_requirements>

---

## Summary

Phase 1 establishes the project skeleton: directory layout, Python backend with FastAPI + SQLAlchemy async + Alembic, React + Vite + Tailwind CSS v4 frontend scaffold, Docker Compose multi-file dev/prod setup, DigitalOcean VPS deployment with Nginx SSL, and a manual Twilio WhatsApp account setup with template submission. This is the foundation every later phase builds on — the decisions made here about schema, service names, network topology, and environment variables are inherited by all 7 subsequent phases.

The most critical finding is that **DigitalOcean does not have an Israeli datacenter** (confirmed as of March 2026: 14 datacenters across 11 regions, none in Israel or the Middle East). Decision D-12 as written cannot be fulfilled with DigitalOcean. The closest DigitalOcean regions are Amsterdam (AMS) and Frankfurt (FRA). For Facebook Marketplace geo-targeting of Haifa results (Phase 8), an Israeli IP is required. Resolution options are documented in Open Questions below — the planner must surface this as a decision checkpoint before the VPS provisioning task.

A second critical finding: the frontend library ecosystem has moved significantly past the versions documented in CLAUDE.md. React 19 (not 18.x), Vite 8 (not 5.x), Tailwind CSS v4 (not 3.4+), and react-leaflet v5 (not 4.2+) are all current as of April 2026. These are major version bumps with real breaking changes. The planner must use the current versions — CLAUDE.md specs are a floor, not a ceiling, and starting fresh on these versions is easier than starting on older ones and migrating later. The one complication: Tailwind v4 has a fundamentally different config system (CSS-based `@theme` directives instead of `tailwind.config.js`).

**Primary recommendation:** Use the stack as specified in CLAUDE.md for backend (confirmed current). For frontend, use React 19 + Vite 8 + Tailwind CSS v4 + react-leaflet v5 — all are stable, current, and mutually compatible. Resolve the DigitalOcean/Israel region gap before writing the VPS provisioning task.

---

## Standard Stack

### Backend (Python)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12 (Docker image: `python:3.12-slim`) | Primary runtime | Specified in CLAUDE.md; install via Docker — system Python 3.9 on dev Mac is irrelevant |
| FastAPI | 0.135.2 | REST API server | Latest stable; 0.111+ required by CLAUDE.md; async-native |
| uvicorn[standard] | 0.30.6 | ASGI server | Pairs with FastAPI; `--reload` flag for dev |
| SQLAlchemy | 2.0.48 | ORM + async sessions | Latest 2.x; async engine with aiosqlite dialect |
| aiosqlite | 0.22.1 | SQLite async driver | Required by SQLAlchemy async for SQLite |
| Alembic | 1.18.4 | Schema migrations | Latest; use `alembic init -t async` for async-aware env.py |
| pydantic | 2.11.5 | Data validation + settings | FastAPI-native v2; use `BaseSettings` from `pydantic-settings` for .env loading |
| pydantic-settings | 2.x | `.env` file loading | Separate package from pydantic v2; required for `BaseSettings` |
| APScheduler | 3.11.2 | Periodic scheduler (Phase 3) | Import now, wire up in Phase 3; define `AsyncIOScheduler` |
| python-dotenv | 1.x | `.env` loading fallback | Standard in FastAPI setups alongside pydantic-settings |

**Installation:**
```bash
pip install fastapi==0.135.2 uvicorn[standard]==0.30.6 sqlalchemy==2.0.48 aiosqlite==0.22.1 alembic==1.18.4 pydantic==2.11.5 pydantic-settings apscheduler==3.11.2 python-dotenv
```

### Frontend (Node)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19.2.4 | UI framework | Current major version; react-leaflet v5 requires React 19 |
| react-dom | 19.2.4 | DOM renderer | Paired with React 19 |
| Vite | 8.0.3 | Build tool + dev server | Current stable; Rolldown-based bundler |
| @vitejs/plugin-react | 6.0.1 | Vite React JSX transform | Required with Vite 8 |
| Tailwind CSS | 4.2.2 | Utility CSS | Current major; CSS-based config (no tailwind.config.js); `@tailwindcss/vite` plugin replaces PostCSS setup |
| @tailwindcss/vite | 4.x | Tailwind v4 Vite plugin | Required for Tailwind v4 + Vite integration (no PostCSS needed) |
| react-leaflet | 5.0.0 | Map component | Current; requires React 19 (matches our version) |
| leaflet | 1.9.x | Underlying map library | Peer dep of react-leaflet v5 |
| @types/leaflet | 1.9.x | TypeScript types for leaflet | If using TypeScript |
| @tanstack/react-query | 5.96.1 | Server-state management | Current v5; hooks API stable |
| react-router-dom | 7.13.2 | Client-side routing | Current v7 |

**Installation:**
```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install react-leaflet leaflet @tanstack/react-query react-router-dom
npm install -D tailwindcss @tailwindcss/vite
```

### Version verification (performed 2026-04-01):
- `react`: 19.2.4
- `vite`: 8.0.3
- `tailwindcss`: 4.2.2
- `react-leaflet`: 5.0.0 (peer requires react ^19.0.0)
- `@tanstack/react-query`: 5.96.1
- `react-router-dom`: 7.13.2
- `fastapi`: 0.135.2 (PyPI)
- `sqlalchemy`: 2.0.48 (PyPI)
- `alembic`: 1.18.4 (PyPI)
- `aiosqlite`: 0.22.1 (PyPI)
- `apscheduler`: 3.11.2 (PyPI)

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Tailwind v4 | Tailwind v3 | v3 is EOL-approaching; v4 has better performance and native logical properties. Starting fresh on v4 is simpler than migrating later. |
| React 19 | React 18 | react-leaflet v5 requires React 19 as peer dep; pinning React 18 means pinning react-leaflet to v4 which has no React 19 support |
| Vite 8 | Vite 5 | No reason to use outdated version for a greenfield project; Vite 8's Rolldown bundler is stable |
| aiosqlite (async) | sqlite3 (sync) | SQLAlchemy async ORM requires an async-capable driver; aiosqlite is the standard choice for SQLite |

---

## Architecture Patterns

### Recommended Project Structure

```
ApartmentFinder/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app factory
│   │   ├── database.py          # Async engine, session factory, Base
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── listing.py       # Listing SQLAlchemy model
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── listing.py       # Pydantic request/response schemas
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   └── listings.py      # /api/listings endpoints (stub for Phase 1)
│   │   └── config.py            # pydantic-settings BaseSettings (reads .env)
│   ├── alembic/
│   │   ├── env.py               # async-aware migration environment
│   │   ├── versions/
│   │   │   └── 0001_initial_schema.py
│   │   └── alembic.ini
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── main.jsx             # React 19 entry point
│   │   ├── App.jsx              # Root component
│   │   ├── index.css            # @import "tailwindcss"; (v4 style)
│   │   └── components/          # Empty for Phase 1
│   ├── index.html               # lang="he" dir="rtl" set here
│   ├── vite.config.js           # @tailwindcss/vite plugin
│   ├── package.json
│   └── Dockerfile               # Multi-stage: node build → nginx:alpine
├── nginx/
│   ├── nginx.dev.conf           # Dev: proxy /api to backend:8000
│   └── nginx.prod.conf          # Prod: serve /dist, proxy /api, SSL
├── docker-compose.yml           # Base: service definitions, shared network
├── docker-compose.dev.yml       # Overrides: volumes, --reload, port 5173
├── docker-compose.prod.yml      # Overrides: built image, Nginx, certbot
├── .env.example                 # Template with all required var names
├── .env                         # Gitignored; actual secrets
└── .gitignore
```

### Pattern 1: SQLAlchemy Async Engine + Session Dependency

**What:** Single async engine created at startup; async_sessionmaker provides sessions to routes via FastAPI dependency injection.

**When to use:** All database access in FastAPI routes.

```python
# Source: SQLAlchemy 2.0 asyncio docs — docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
# backend/app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = "sqlite+aiosqlite:///./data/listings.db"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
```

### Pattern 2: Alembic Async Migration Environment

**What:** Alembic initialized with `-t async` template uses `run_sync` to execute migrations synchronously within an async context. Required for aiosqlite.

**When to use:** All schema migrations.

```python
# Source: Alembic asyncio cookbook — alembic.sqlalchemy.org/en/latest/cookbook.html
# alembic/env.py (key section)
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

def run_migrations_online():
    connectable = create_async_engine(config.get_main_option("sqlalchemy.url"))
    async def run_async_migrations():
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    asyncio.run(run_async_migrations())
```

### Pattern 3: Tailwind v4 Setup with Vite Plugin

**What:** Tailwind v4 replaces `tailwind.config.js` with CSS-based `@theme` directives. The `@tailwindcss/vite` plugin eliminates the need for a PostCSS config file. RTL is handled via `dir="rtl"` on `<html>` and logical property utilities.

**When to use:** All frontend styling.

```js
// Source: tailwindcss.com/docs — Vite installation guide
// vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
})
```

```css
/* src/index.css — entire file */
@import "tailwindcss";
```

```html
<!-- index.html — RTL Hebrew from day one -->
<!DOCTYPE html>
<html lang="he" dir="rtl">
  <head>
    <meta charset="UTF-8" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Hebrew:wght@400;500;700&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

### Pattern 4: Docker Compose Multi-File Strategy

**What:** Base file defines services; dev and prod overlays override only what differs. Compose merges files in order.

**When to use:** All container orchestration in this project (locked decision D-06).

```yaml
# docker-compose.yml (base — shared service definitions)
services:
  backend:
    build:
      context: ./backend
    environment:
      - DATABASE_URL=sqlite+aiosqlite:////data/listings.db
    env_file: .env
    volumes:
      - sqlite_data:/data
    networks:
      - app_network
  frontend:
    build:
      context: ./frontend
    networks:
      - app_network

volumes:
  sqlite_data:

networks:
  app_network:
```

```yaml
# docker-compose.dev.yml (dev overrides)
services:
  backend:
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./backend:/app     # live code reload
    ports:
      - "8000:8000"
  frontend:
    command: npm run dev -- --host
    volumes:
      - ./frontend:/app
      - /app/node_modules  # anonymous volume prevents host node_modules overwrite
    ports:
      - "5173:5173"
```

### Pattern 5: Nginx Reverse Proxy + SSL in Production

**What:** Nginx container serves Vite static build and proxies `/api/*` to the FastAPI container. Certbot container manages Let's Encrypt certificates via webroot challenge.

```nginx
# nginx/nginx.prod.conf (key sections)
server {
    listen 80;
    server_name yourdomain.me;
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    location / { return 301 https://$host$request_uri; }
}

server {
    listen 443 ssl;
    server_name yourdomain.me;
    ssl_certificate /etc/letsencrypt/live/yourdomain.me/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.me/privkey.pem;

    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
    }

    location / {
        try_files $uri $uri/ /index.html;   # SPA fallback
    }
}
```

### Anti-Patterns to Avoid

- **Using `tailwind.config.js` with Tailwind v4:** v4 removed this file. Config is done via CSS `@theme` directives in the main CSS file. Running `npx tailwindcss init` will not work as expected.
- **Using PostCSS config for Tailwind v4 + Vite:** The `@tailwindcss/vite` plugin makes PostCSS config unnecessary. Adding a `postcss.config.js` alongside it can cause conflicts.
- **Mixing physical Tailwind utilities with RTL:** Use `ms-`, `me-`, `ps-`, `pe-` (logical) instead of `ml-`, `mr-`, `pl-`, `pr-` (physical). Physical utilities ignore `dir="rtl"`.
- **Running Alembic migrations without `run_sync`:** Direct async migration calls fail with SQLite+aiosqlite. Always use the `run_sync` pattern from the async template.
- **SQLite batch migrations missing `render_as_batch=True`:** SQLite cannot ALTER columns. Alembic batch operations must be enabled in `env.py` for any future column changes to work. Set `render_as_batch=True` in `context.configure()`.
- **Storing the SQLite file inside the container image:** The database file must be on a named volume or host mount to survive container restarts and image rebuilds.
- **Committing `.env` to git:** All secrets go in `.env` (gitignored). Only `.env.example` with placeholder values is committed.
- **Using the Twilio Sandbox with a custom template:** Sandbox supports only pre-approved Twilio templates for testing. Custom templates require a production-approved sender. The Phase 7 implementation will use the approved template; Phase 1 just submits it and saves sandbox credentials for smoke testing.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema migrations | Manual SQL ALTER scripts | Alembic | SQLite ALTER limitations; Alembic batch handles column changes safely |
| `.env` file loading | `os.environ.get()` scattered everywhere | `pydantic-settings BaseSettings` | Type-safe, validated at startup, auto-reads from `.env` |
| Async session lifecycle | Manual session open/close in routes | FastAPI `Depends(get_db)` + async generator | Guarantees session cleanup even on exceptions |
| SSL certificate management | Manual openssl + cron renewal | Certbot + Let's Encrypt (Docker Compose service) | Auto-renewal, no downtime, zero cost |
| Reverse proxy config | FastAPI serving static files directly | Nginx | Static file serving, SSL termination, compression — FastAPI is not optimized for this |
| React server state | `useState` + `useEffect` for API calls | TanStack Query | Caching, background refetch, loading/error states — re-implementing this is days of work |

**Key insight:** For infrastructure (SSL, reverse proxy, migrations) and data-fetching patterns, the ecosystem has solved these problems comprehensively. Custom solutions introduce bugs and maintenance burden with no upside.

---

## Common Pitfalls

### Pitfall 1: SQLite ALTER COLUMN fails in Alembic

**What goes wrong:** Alembic auto-generates a migration that uses `ALTER COLUMN` to change a column type or add a constraint. SQLite does not support `ALTER COLUMN`. Migration fails with `OperationalError`.

**Why it happens:** Alembic's default migration mode generates ALTER statements. SQLite requires "move and copy" — create new table, copy data, drop old.

**How to avoid:** In `alembic/env.py`, set `render_as_batch=True` in `context.configure()`. This activates Alembic's batch operations mode, which handles SQLite's limitations transparently.

```python
# In env.py context.configure() call
context.configure(
    connection=connection,
    target_metadata=target_metadata,
    render_as_batch=True,  # Required for SQLite
)
```

**Warning signs:** `OperationalError: near "ALTER": syntax error` during migration.

### Pitfall 2: Tailwind v4 config confusion

**What goes wrong:** Developer creates `tailwind.config.js` (v3 habit), adds `content` array, wonders why classes are not applied. Or installs PostCSS plugin expecting it to work.

**Why it happens:** Tailwind v4 fundamentally changed the configuration model. The `tailwind.config.js` file is not read by default.

**How to avoid:** Use `@tailwindcss/vite` plugin in `vite.config.js`. Import Tailwind with `@import "tailwindcss"` in CSS. Customize via `@theme` in CSS file, not JS config.

**Warning signs:** Tailwind utility classes produce no output; build succeeds but styles are absent.

### Pitfall 3: react-leaflet v5 requires React 19

**What goes wrong:** Developer installs `react-leaflet@5` alongside `react@18` — peer dependency conflict, or silent rendering failures.

**Why it happens:** react-leaflet v5 added React 19 as a hard peer dep. The `MapContainer` and hooks rely on React 19's ref API changes.

**How to avoid:** Install `react@19` and `react-dom@19` alongside `react-leaflet@5`. Both are current as of April 2026 and this is the supported combination.

**Warning signs:** `npm warn peer react@^19.0.0` during install; map renders blank.

### Pitfall 4: DigitalOcean has no Israeli region

**What goes wrong:** Developer provisions a DigitalOcean droplet in Amsterdam or Frankfurt expecting Facebook Marketplace to show Israeli listings. Facebook Marketplace geo-filters by IP — results will show European listings, not Israeli ones.

**Why it happens:** DigitalOcean does not operate a datacenter in Israel or the Middle East (as of April 2026). Decision D-12 as written cannot be fulfilled with DigitalOcean.

**How to avoid:** Use Kamatera (has 5 Israeli datacenters, ~$4/month, 30-day/$100 free trial) or VPSServer.com (has Tel Aviv, Haifa locations) for the VPS. DigitalOcean's $200 Student Pack credit cannot be used for an Israeli IP droplet — this is a hard constraint.

**Warning signs:** Facebook Marketplace scraper returns listings in Amsterdam or no results. Only detectable during Phase 8 testing.

### Pitfall 5: Twilio legacy templates sunset

**What goes wrong:** Developer submits template using the old legacy template interface or assumes the approval flow from pre-2025 tutorials is still current.

**Why it happens:** Twilio accounts created after July 17, 2024 must use the Content Template Builder / Content API. Legacy WhatsApp templates reached end-of-life on April 1, 2025.

**How to avoid:** Use the Content Template Builder in the Twilio Console to create and submit the template. Do not use legacy `/Messages/Templates` API endpoints shown in older tutorials.

**Warning signs:** Template submission UI looks different from tutorials; error about "legacy template" on submission.

### Pitfall 6: SQLite file lost on container rebuild

**What goes wrong:** Running `docker compose build` or `docker compose down -v` wipes the database.

**Why it happens:** If the SQLite file path is inside the container filesystem (not a volume), it is deleted when the container is removed.

**How to avoid:** Mount a named volume (or a host directory) to the directory containing the SQLite file. In `docker-compose.yml`, define `volumes: sqlite_data:` and mount it to `/data` inside the backend container. Set `DATABASE_URL` to `sqlite+aiosqlite:////data/listings.db`.

---

## Code Examples

Verified patterns from official sources:

### SQLAlchemy Async Model (Mapped types, v2.0 style)
```python
# Source: SQLAlchemy 2.0 ORM docs — docs.sqlalchemy.org/en/20/orm/
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, Boolean, Integer, Text, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Infrastructure columns (D-02)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_seen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_favorited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dedup_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Listing data columns (D-03)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    price: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rooms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    size_sqm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    contact_info: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    post_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    source_badge: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Metadata columns (D-04)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # D-05: same-source dedup constraint
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_listing_source_source_id"),
    )
```

### Alembic env.py (async, SQLite batch mode)
```python
# Source: alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic
import asyncio
from logging.config import fileConfig
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

config = context.config
fileConfig(config.config_file_name)

# Import all models so autogenerate detects them
from app.models.listing import Listing  # noqa
from app.database import Base
target_metadata = Base.metadata

def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,   # Required for SQLite
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    url = config.get_main_option("sqlalchemy.url")
    connectable = create_async_engine(url)

    async def run_async_migrations():
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
        await connectable.dispose()

    asyncio.run(run_async_migrations())

run_migrations_online()
```

### pydantic-settings BaseSettings for .env
```python
# Source: docs.pydantic.dev/latest/concepts/pydantic_settings/
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:////data/listings.db"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""
    llm_api_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

### FastAPI minimal startup (Phase 1 skeleton)
```python
# backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .database import engine, Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tables created by Alembic, not here — but engine check on startup
    yield

app = FastAPI(title="ApartmentFinder API", lifespan=lifespan)

@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

### Frontend multi-stage Dockerfile
```dockerfile
# frontend/Dockerfile
# Stage 1: build
FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: serve
FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `tailwind.config.js` | `@theme` in CSS file | Tailwind v4 (Jan 2025) | Config approach is completely different; no JS config file |
| PostCSS for Tailwind in Vite | `@tailwindcss/vite` plugin | Tailwind v4 (Jan 2025) | PostCSS config file not needed; simpler setup |
| `forwardRef` for ref passing | Ref as a prop (React 19) | React 19 (Dec 2024) | `forwardRef` still works but no longer needed for function components |
| Rollup/esbuild in Vite | Rolldown (Rust-based) | Vite 8 (Mar 2026) | `build.rollupOptions` deprecated → `build.rolldownOptions`; compat layer exists |
| Twilio legacy template API | Content Template Builder | April 2025 | Legacy templates EOL; new accounts must use Content Template Builder |
| `LeafletProvider` in react-leaflet | Removed in v5 | react-leaflet v5 (Dec 2024) | `MapContainer` handles context internally; do not import `LeafletProvider` |
| `whenCreated` prop on `MapContainer` | Use `ref` on `MapContainer` | react-leaflet v5 | `whenCreated` removed; use standard React ref pattern |

**Deprecated/outdated:**
- `tailwind.config.js`: Not used in v4. Will be silently ignored or cause errors.
- `LeafletProvider` from react-leaflet: Removed in v5. Do not import.
- Twilio legacy WhatsApp templates: EOL April 1, 2025. Do not use.
- React `propTypes`: Silently ignored in React 19. Use TypeScript or omit.

---

## Open Questions

1. **DigitalOcean has no Israeli datacenter — D-12 is blocked**
   - What we know: DigitalOcean operates 14 datacenters in 11 regions (Canada, Germany, India, Netherlands, Singapore, UK, USA). No Israel or Middle East. Confirmed as of March 2026.
   - What's unclear: Can the $200 Student Pack credit be used on an alternative provider (Kamatera, VPSServer.com) for the Israeli-IP requirement while still using DigitalOcean for other infra? Or should the entire deployment move to an Israeli provider?
   - Recommendation: The planner must insert a decision checkpoint before the VPS provisioning task. Two options: (A) Use Kamatera Israel VPS ($4/mo, 30-day free trial — not Student Pack but affordable) for the single droplet; forfeit DigitalOcean credits for this project. (B) Provision DigitalOcean droplet (Amsterdam/Frankfurt, using $200 credit) for app hosting + plan to use a residential Israeli proxy/IP specifically for Phase 8 Facebook Marketplace scraping. Option B preserves Student Pack value but introduces proxy complexity in Phase 8. Option A is simpler end-to-end. This decision should be surfaced to the user as a checklist item in the VPS provisioning plan.

2. **Twilio template approval timeline uncertainty**
   - What we know: Meta now approves most templates "within minutes" via machine-learning review (as of 2025), up to 48 hours in edge cases. Legacy templates are EOL (April 2025). New accounts use Content Template Builder.
   - What's unclear: The CONTEXT.md note says "days to weeks" — this was accurate pre-2025 but may be outdated. Current approval is typically much faster.
   - Recommendation: Plan still includes template submission as an urgent Phase 1 task (it can only help to submit early), but the planner note about "blocking Phase 7" may be less critical than originally thought. Submit immediately; expect same-day approval.

3. **Python 3.12 on dev machine vs Docker**
   - What we know: Dev Mac has Python 3.9.6. CLAUDE.md requires Python 3.12. Docker image will use `python:3.12-slim` — this is correct and consistent.
   - What's unclear: Whether the developer wants to also install Python 3.12 locally (for running tests outside Docker).
   - Recommendation: All Python work runs inside Docker containers. Local Python version is irrelevant for this project. Do not add a local Python upgrade task to the plan.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | Container orchestration | Yes | 29.2.1 | — |
| Docker Compose | Multi-container dev/prod | Yes | v5.0.2 | — |
| Node.js | Frontend build (local) | Yes | 24.6.0 | — |
| npm | Package installation | Yes | 11.5.1 | — |
| Python 3.12 | Backend runtime | No (3.9.6 installed) | — | Use `python:3.12-slim` Docker image — all backend work runs in Docker |
| Git | Version control | Yes | 2.50.1 | — |
| Certbot | SSL certificates | No | — | Run as Docker Compose service (standard pattern); no local install needed |
| doctl (DigitalOcean CLI) | VPS provisioning automation | No | — | Use DigitalOcean web console; doctl is optional |

**Missing dependencies with no fallback:**
- None that block execution — all missing tools either run in Docker or have web console alternatives.

**Missing dependencies with fallback:**
- Python 3.12: Use `python:3.12-slim` Docker image. All `pip install`, `alembic`, `uvicorn` commands run via `docker compose exec backend`.
- Certbot: Run as a dedicated container in `docker-compose.prod.yml` (standard letsencrypt-docker pattern).
- doctl: Use DigitalOcean or Kamatera web console for droplet creation.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio (Wave 0 setup required) |
| Config file | `backend/pytest.ini` — Wave 0 gap |
| Quick run command | `docker compose exec backend pytest tests/ -x -q` |
| Full suite command | `docker compose exec backend pytest tests/ -v` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | SQLite DB created at `DATABASE_URL` path on app startup | unit | `pytest tests/test_database.py::test_db_file_created -x` | Wave 0 |
| DATA-01 | Listings table exists with all 19 required columns | unit | `pytest tests/test_database.py::test_listings_table_columns -x` | Wave 0 |
| DATA-02 | Inserting duplicate (source, source_id) raises IntegrityError | unit | `pytest tests/test_database.py::test_dedup_constraint -x` | Wave 0 |
| INFRA-01 | `/api/health` endpoint returns 200 | smoke | `pytest tests/test_api.py::test_health_endpoint -x` | Wave 0 |
| INFRA-02 | VPS IP resolves to Israeli geolocation | manual | `curl https://ipinfo.io/json` on droplet — check `"country": "IL"` | manual |
| INFRA-03 | `docker compose up` starts without errors on clean machine | smoke | `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d && docker compose ps` | manual |
| INFRA-04 | App accessible at public URL without auth prompt | manual | Browser access to `http://yourdomain.me` — no login screen | manual |

### Sampling Rate
- **Per task commit:** `docker compose exec backend pytest tests/ -x -q`
- **Per wave merge:** `docker compose exec backend pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/__init__.py` — make tests directory a package
- [ ] `backend/tests/conftest.py` — shared async test fixtures (engine, session)
- [ ] `backend/tests/test_database.py` — covers DATA-01, DATA-02
- [ ] `backend/tests/test_api.py` — covers INFRA-01 (health endpoint)
- [ ] `backend/pytest.ini` — configure asyncio_mode = auto for pytest-asyncio
- [ ] Framework install: `pip install pytest pytest-asyncio httpx` in `requirements.txt`

---

## Project Constraints (from CLAUDE.md)

The following directives from CLAUDE.md are binding on all planning and implementation:

1. **Language/RTL:** Full Hebrew/RTL required throughout the UI — `dir="rtl"` and `lang="he"` on `<html>` from day one, Noto Sans Hebrew font.
2. **Mobile-first:** App must be usable on a smartphone browser (responsive, touch-friendly).
3. **Python backend required:** FastAPI + SQLite + SQLAlchemy 2.0 + Alembic — no alternatives.
4. **Playwright for Facebook only:** Do not use facebook-scraper library (broken since 2024). Keep Playwright with playwright-stealth.
5. **Crawl4AI for Yad2/Madlan:** Use Crawl4AI (not raw Playwright+BS4) for structured sources.
6. **React + Vite (not Next.js):** No SSR needed; Next.js forbidden by CLAUDE.md alternatives table.
7. **Leaflet + OSM (not Google Maps):** Google Maps requires billing; Leaflet with OpenStreetMap is mandated.
8. **APScheduler (not Celery):** Embedded scheduler only; no broker infrastructure.
9. **SQLite (not PostgreSQL):** Single-user scale; Postgres adds ops overhead.
10. **Twilio WhatsApp API:** Official SDK `twilio` Python 9.x.
11. **DigitalOcean preferred for VPS:** Student Pack $200 credit. However, no Israeli region exists — this constraint conflicts with INFRA-02 (see Open Questions).
12. **Docker + Docker Compose for deployment:** `docker compose up` is the canonical deploy command.
13. **GSD workflow enforcement:** All code changes must go through a GSD command entry point (`/gsd:execute-phase`, `/gsd:quick`, `/gsd:debug`).

---

## Sources

### Primary (HIGH confidence)
- SQLAlchemy asyncio docs — https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- Alembic asyncio cookbook — https://alembic.sqlalchemy.org/en/latest/cookbook.html
- Alembic batch migrations (SQLite) — https://alembic.sqlalchemy.org/en/latest/batch.html
- Tailwind CSS v4 release notes — https://tailwindcss.com/blog/tailwindcss-v4
- Tailwind CSS upgrade guide (v3→v4) — https://tailwindcss.com/docs/upgrade-guide
- react-leaflet v5.0.0 release — https://github.com/PaulLeCam/react-leaflet/releases/tag/v5.0.0
- React 19 release blog — https://react.dev/blog/2024/12/05/react-19
- Vite 8 announcement — https://vite.dev/blog/announcing-vite8
- npm registry (verified 2026-04-01): react 19.2.4, vite 8.0.3, tailwindcss 4.2.2, react-leaflet 5.0.0, @tanstack/react-query 5.96.1, react-router-dom 7.13.2
- PyPI (verified 2026-04-01): fastapi 0.135.2, sqlalchemy 2.0.48, alembic 1.18.4, aiosqlite 0.22.1, apscheduler 3.11.2

### Secondary (MEDIUM confidence)
- DigitalOcean regional availability — https://docs.digitalocean.com/platform/regional-availability/ (no Israel region confirmed)
- DigitalOcean Israel region question (community) — https://www.digitalocean.com/community/questions/which-region-i-need-to-choose-if-im-live-in-israel
- Kamatera Israel datacenters — https://www.kamatera.com/cloud-vps/israel-vps-hosting/
- Twilio WhatsApp sandbox — https://www.twilio.com/docs/whatsapp/sandbox
- Twilio template approvals — https://www.twilio.com/docs/whatsapp/tutorial/message-template-approvals-statuses
- FastAPI Docker guide — https://fastapi.tiangolo.com/deployment/docker/
- Vite 8 migration guide — https://vite.dev/guide/migration

### Tertiary (LOW confidence)
- Twilio legacy template EOL (April 2025) — reported by multiple sources but verified via Twilio support article https://support.twilio.com/hc/en-us/articles/360039246774

---

## Metadata

**Confidence breakdown:**
- Standard stack (backend): HIGH — versions verified via PyPI on 2026-04-01
- Standard stack (frontend): HIGH — versions verified via npm registry on 2026-04-01; peer dep compatibility confirmed
- Architecture patterns: HIGH — patterns from official SQLAlchemy, Alembic, Tailwind, FastAPI docs
- Docker Compose multi-file strategy: HIGH — confirmed standard pattern; multiple official examples
- DigitalOcean Israel region: HIGH (confirmed absent) — DigitalOcean docs + community Q&A
- Twilio template process: MEDIUM — Twilio docs confirm Content Template Builder requirement; approval timing estimate from official support article
- Pitfalls: HIGH — each verified against official source or regression-tested community reports

**Research date:** 2026-04-01
**Valid until:** 2026-05-01 (30 days — relatively stable libraries except Facebook-related items)
