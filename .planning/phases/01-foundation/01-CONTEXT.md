# Phase 1: Foundation - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver a fully reproducible development environment with: the complete SQLite database schema and Alembic migrations, Docker Compose setup for dev and prod, FastAPI + React/Vite project skeleton, a live deployment at a public URL (DigitalOcean, Israeli region, custom domain), and Twilio WhatsApp account + template submission to start the Meta approval clock before Phase 7 needs it.

</domain>

<decisions>
## Implementation Decisions

### Database Schema
- **D-01:** Use the **full schema** in the Phase 1 migration — include all listing data columns alongside the ROADMAP-required infrastructure columns. Do not defer listing fields to Phase 2.
- **D-02:** Infrastructure columns (ROADMAP-required): `source`, `source_id`, `lat`, `lng`, `is_seen`, `is_favorited`, `raw_data`, `llm_confidence`, `dedup_fingerprint`
- **D-03:** Listing data columns (pre-defined for scrapers): `title`, `price`, `rooms`, `size_sqm`, `address`, `contact_info`, `post_date`, `url`, `source_badge`
- **D-04:** Standard metadata columns: `created_at`, `updated_at` (timestamps), `is_active` (soft-delete flag for stale listings)
- **D-05:** Same-source deduplication UNIQUE constraint on (`source`, `source_id`) — enforced at DB level (per ROADMAP success criterion)

### Docker Compose Strategy
- **D-06:** **Separate Compose files:** `docker-compose.yml` (base, shared services) + `docker-compose.dev.yml` (hot-reload, volume mounts) + `docker-compose.prod.yml` (Nginx, optimized builds)
- **D-07:** Dev invocation: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up`
- **D-08:** FastAPI backend in dev: run `uvicorn --reload` with source mounted as a volume — save file, server restarts automatically, no container rebuild needed

### VPS Provisioning (In Phase 1 Scope)
- **D-09:** Phase 1 is **not complete until the app is accessible at a public URL** — provisioning is in-scope, not manual post-phase work
- **D-10:** Claim GitHub Student Pack $200 DigitalOcean credit at education.github.com/pack — no existing account yet
- **D-11:** Register free Namecheap `.me` domain via Student Pack — no existing domain yet
- **D-12:** Provision DigitalOcean droplet in **Israeli region** (required for Phase 8 Facebook Marketplace geo-filtering — INFRA-02)
- **D-13:** Deploy Docker stack on VPS with Nginx as reverse proxy + SSL termination

### Twilio WhatsApp Setup (Manual Task in Phase 1)
- **D-14:** Phase 1 plan includes a **manual human-action task** for Twilio setup — not automated code, but a checklist step the user must complete
- **D-15:** Steps to include: create Twilio account (no existing account), verify phone number, enable WhatsApp sandbox, obtain sandbox credentials (add to `.env`), submit message template for Meta approval
- **D-16:** Template to submit: `"{{count}} new listings found in Haifa. Open app: {{url}}"` (from STATE.md)
- **D-17:** Credentials go into `.env` / `.env.example` under `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`

### Claude's Discretion
- SQLAlchemy async model class design and column type choices (String lengths, etc.)
- Alembic migration naming and versioning conventions
- Exact Docker image versions (within the ranges in CLAUDE.md)
- Nginx config details (worker processes, SSL cert tool — Certbot is standard)
- `.env.example` structure and organization

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Requirements
- `.planning/REQUIREMENTS.md` — DATA-01, DATA-02, INFRA-01, INFRA-02, INFRA-03, INFRA-04 (Phase 1 requirement IDs)

### Stack Decisions
- `CLAUDE.md` — Full technology stack with exact versions (SQLAlchemy 2.0+, Alembic 1.13+, FastAPI 0.111+, React 18.x, Vite 5.x, Tailwind 3.4+, Python 3.12, Nginx 1.26+); deployment guidance (DigitalOcean vs. Railway tradeoffs); Facebook/Playwright constraints (read entire doc)

### Roadmap
- `.planning/ROADMAP.md` — Phase 1 success criteria (the 5 checkpoints that define done), note about Twilio template submission

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — blank-slate project. No existing components, hooks, or utilities.

### Established Patterns
- None yet — Phase 1 establishes the patterns all subsequent phases inherit.

### Integration Points
- Phase 1 creates the `listings` table that every future phase reads/writes
- Phase 1 defines the `.env` pattern that all scrapers and the API will extend
- Phase 1 establishes the Docker service names and network that Phase 3 (scheduler) and Phase 4 (frontend) depend on

</code_context>

<specifics>
## Specific Ideas

- ROADMAP note: "Submit the Twilio WhatsApp message template for Meta approval during Phase 1 setup. Template approval takes days to weeks and blocks Phase 7."
- STATE.md pending action: "ACTION REQUIRED: Submit Twilio WhatsApp message template to Meta for approval during Phase 1 — approval takes days to weeks and blocks Phase 7. Template: '{{count}} new listings found in Haifa. Open app: {{url}}'"
- Israeli datacenter region is a hard requirement (not preference) — needed for Facebook Marketplace geo-filtering in Phase 8 (INFRA-02)
- GitHub Student Pack provides: $200 DigitalOcean credit (~33 months free on $6/mo droplet), free Namecheap .me domain, GitHub Copilot, Railway credits

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-04-01*
