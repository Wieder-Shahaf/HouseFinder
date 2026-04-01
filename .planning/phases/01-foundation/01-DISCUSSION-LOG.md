# Phase 1: Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-01
**Phase:** 01-foundation
**Areas discussed:** DB schema completeness, Docker dev/prod strategy, VPS provisioning scope, Twilio pre-setup

---

## DB Schema Completeness

| Option | Description | Selected |
|--------|-------------|----------|
| Full schema now | Add all listing data columns in Phase 1 migration. Avoids mid-phase schema additions when Phase 2 scrapers need them. | ✓ |
| Minimal schema now | Only ROADMAP-required infrastructure columns in Phase 1. Scraper data columns added in Phase 2. | |

**User's choice:** Full schema now
**Notes:** Pre-define all listing data columns (title, price, rooms, size_sqm, address, contact_info, post_date, url, source_badge) alongside infrastructure columns.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — add timestamps + is_active | created_at for sorting new listings, updated_at for dedup/merge tracking, is_active to soft-delete stale listings. | ✓ |
| Timestamps only, no is_active | created_at + updated_at only. | |
| No extras — ROADMAP columns only | Stick to only what ROADMAP specifies. | |

**User's choice:** Yes — add timestamps + is_active
**Notes:** Standard timestamps plus is_active for soft-delete support.

---

## Docker Dev/Prod Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Separate files | docker-compose.yml (base) + docker-compose.dev.yml (hot-reload) + docker-compose.prod.yml (Nginx, optimized build). | ✓ |
| Single file with profiles | One docker-compose.yml using Docker Compose profiles. Simpler but less separation. | |

**User's choice:** Separate files
**Notes:** Cleaner separation between dev and prod concerns.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Uvicorn --reload in container | Mount backend source as volume, run uvicorn with --reload. Save file, server restarts automatically. | ✓ |
| Run backend outside Docker in dev | Only DB in Docker during dev; FastAPI and React run natively. | |

**User's choice:** Uvicorn --reload in container
**Notes:** Zero-friction development reload.

---

## VPS Provisioning Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Inside Phase 1 | Phase 1 only complete when app is live at a real URL. Provision DigitalOcean + DNS setup. | ✓ |
| Local-first, deploy manually after | Phase 1 delivers working Docker Compose locally. VPS provisioning done manually by user outside the plan. | |

**User's choice:** Inside Phase 1
**Notes:** Matches the literal Phase 1 success criterion ("accessible at public URL").

---

| Option | Description | Selected |
|--------|-------------|----------|
| Neither — include Student Pack setup steps | Claim $200 DigitalOcean credit, register free .me domain on Namecheap, create droplet in Israeli region. | ✓ |
| Have DigitalOcean, need domain | Already have DigitalOcean. Phase 1 includes domain registration but not account creation. | |
| Have both already | Both DigitalOcean account and domain are ready. | |

**User's choice:** Neither — include Student Pack setup steps
**Notes:** Fresh start — both account and domain need to be obtained via GitHub Student Pack.

---

## Twilio Pre-Setup

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — include as a Phase 1 manual task | Phase 1 plan includes: create Twilio account, enable WhatsApp sandbox, submit message template for Meta approval. Coded as manual human-action task. | ✓ |
| No — track in STATE.md only | Keep Twilio reminder in STATE.md. Phase 1 plan focuses on Docker/schema/deployment only. | |

**User's choice:** Yes — include as a Phase 1 manual task
**Notes:** Starts the Meta approval clock early.

---

| Option | Description | Selected |
|--------|-------------|----------|
| No account — include creation steps | Create Twilio account, verify phone number, enable WhatsApp sandbox, get sandbox credentials, submit approval template. | ✓ |
| Have account, need sandbox setup | Already have Twilio. Phase 1 covers enabling sandbox and submitting template. | |

**User's choice:** No account — include creation steps
**Notes:** Full Twilio onboarding from scratch.

---

## Claude's Discretion

- SQLAlchemy async model design and column type choices
- Alembic migration naming conventions
- Exact Docker image versions (within CLAUDE.md version ranges)
- Nginx config details (worker processes, SSL cert tooling)
- `.env.example` structure and organization

## Deferred Ideas

None — discussion stayed within phase scope.
