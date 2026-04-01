---
phase: 01-foundation
plan: 02
subsystem: infra
tags: [react, vite, tailwind, docker, nginx, certbot, rtl, hebrew]

# Dependency graph
requires:
  - phase: 01-foundation plan 01
    provides: backend Dockerfile and FastAPI project structure that docker-compose.yml builds from
provides:
  - React 19 + Vite 8 + Tailwind v4 frontend scaffold with Hebrew RTL
  - Docker Compose multi-file setup (base + dev + prod) that starts the full stack
  - Nginx reverse proxy configs for dev (forward proxy) and prod (SSL termination + Certbot)
affects: [phase-04-map-ui, phase-07-notifications, phase-08-facebook]

# Tech tracking
tech-stack:
  added:
    - React 19.x
    - Vite 8.x
    - Tailwind CSS v4 (CSS-based config, @import "tailwindcss" + @theme)
    - @tailwindcss/vite plugin
    - react-leaflet v5
    - leaflet v1.9
    - TanStack Query v5
    - react-router-dom v7
    - Docker Compose multi-file strategy
    - Nginx 1.27-alpine
    - Certbot for Let's Encrypt SSL
  patterns:
    - Tailwind v4 CSS-based config (no tailwind.config.js, no postcss.config.js)
    - lang=he dir=rtl on <html> element for browser-native RTL
    - Noto Sans Hebrew from Google Fonts CDN
    - Multi-stage Dockerfile: node:22-alpine builder -> nginx:1.27-alpine serve
    - Docker Compose multi-file: base (shared) + dev (hot-reload) + prod (nginx+certbot)
    - Volume mount ./backend:/app for FastAPI hot-reload in dev

key-files:
  created:
    - frontend/index.html
    - frontend/src/main.jsx
    - frontend/src/App.jsx
    - frontend/src/index.css
    - frontend/vite.config.js
    - frontend/package.json
    - frontend/package-lock.json
    - frontend/Dockerfile
    - frontend/nginx.conf
    - docker-compose.yml
    - docker-compose.dev.yml
    - docker-compose.prod.yml
    - nginx/nginx.dev.conf
    - nginx/nginx.prod.conf
  modified: []

key-decisions:
  - "Used React 19 + Vite 8 + Tailwind v4 (not the older versions in CLAUDE.md which are a floor not ceiling)"
  - "Tailwind v4 CSS-based config: @import 'tailwindcss' + @theme block — no tailwind.config.js or postcss.config.js"
  - "Docker Compose multi-file: base defines services/volumes/network; dev adds hot-reload; prod adds Nginx+Certbot"
  - "frontend/nginx.conf is SPA fallback for the built container; nginx/nginx.prod.conf is the edge reverse proxy"

patterns-established:
  - "Pattern: Docker Compose is invoked as multi-file merge: docker compose -f docker-compose.yml -f docker-compose.dev.yml"
  - "Pattern: Frontend container in prod serves static files via nginx; nginx edge proxy handles SSL and /api/ routing"
  - "Pattern: RTL via lang=he dir=rtl on <html>, Tailwind rtl: variants, ms-/me- logical margin utilities"

requirements-completed: [INFRA-03]

# Metrics
duration: 2min
completed: 2026-04-01
---

# Phase 01 Plan 02: Frontend Scaffold + Docker Compose Summary

**React 19 + Vite 8 + Tailwind v4 frontend scaffold with Hebrew RTL, plus three-file Docker Compose strategy (base/dev/prod) and Nginx reverse proxy configs for dev hot-reload and prod SSL termination**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-01T16:31:31Z
- **Completed:** 2026-04-01T16:33:31Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments

- Frontend scaffold builds successfully (Vite 8, React 19, Tailwind v4 CSS-based config, Hebrew RTL from day one)
- Docker Compose validates for both dev (`--reload` hot-reload) and prod (Nginx + Certbot SSL) configurations
- Nginx prod config proxies `/api/` to `backend:8000` with SPA fallback for the React app

## Task Commits

Each task was committed atomically:

1. **Task 1: React 19 + Vite 8 + Tailwind v4 frontend scaffold** - `db11e1f` (feat)
2. **Task 2: Docker Compose files + Nginx configs** - `2e775e3` (feat)

## Files Created/Modified

- `frontend/index.html` - HTML entry point with lang=he, dir=rtl, Noto Sans Hebrew font, ApartmentFinder title
- `frontend/src/main.jsx` - React 19 root render with StrictMode
- `frontend/src/App.jsx` - Minimal Hebrew placeholder (דירות להשכרה בחיפה)
- `frontend/src/index.css` - Tailwind v4 entry: `@import "tailwindcss"` + `@theme` font override
- `frontend/vite.config.js` - Vite 8 config with @vitejs/plugin-react and @tailwindcss/vite plugins
- `frontend/package.json` - React 19, react-leaflet v5, TanStack Query v5, react-router-dom v7
- `frontend/Dockerfile` - Multi-stage: node:22-alpine builder + nginx:1.27-alpine serve
- `frontend/nginx.conf` - SPA fallback for the static-file container
- `docker-compose.yml` - Base: backend + frontend services, sqlite_data volume, app_network
- `docker-compose.dev.yml` - Dev overrides: uvicorn --reload, volume mounts, ports 8000+5173
- `docker-compose.prod.yml` - Prod overrides: Nginx 1.27-alpine, Certbot auto-renewal, certbot volumes
- `nginx/nginx.dev.conf` - Dev reverse proxy: /api/ -> backend:8000, / -> frontend:5173 (WebSocket upgrade)
- `nginx/nginx.prod.conf` - Prod: HTTP->HTTPS redirect, ACME challenge, SSL termination, /api/ proxy, SPA fallback

## Decisions Made

- Used React 19 + Vite 8 + Tailwind v4 — CLAUDE.md versions are a floor not a ceiling; research confirmed these are the current stable versions and react-leaflet v5 requires React 19
- Tailwind v4 uses CSS-based config exclusively: `@import "tailwindcss"` + `@theme` directives in index.css. No `tailwind.config.js` or `postcss.config.js` needed or created
- `frontend/nginx.conf` is distinct from `nginx/nginx.prod.conf`: the former is the SPA fallback inside the built frontend container; the latter is the edge reverse proxy that also handles SSL and API routing

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `.env` file did not exist (only `.env.example`), causing `docker compose config` to fail on `env_file: .env`. Resolved by copying `.env.example` to `.env` locally. The `.env` file is gitignored (correct — it contains secrets), so users must create their own `.env` from `.env.example` before running compose.

## User Setup Required

None for this plan — no external services configured. Users need to create `.env` from `.env.example` before running `docker compose up`.

## Next Phase Readiness

- Frontend scaffold is ready for Phase 4 (Map UI) to build the interactive map on top of
- Docker Compose validates for both dev and prod — `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` will start backend + frontend with hot-reload
- Prod config has placeholder domain `yourdomain.me` in nginx.prod.conf — update when domain is registered (Phase 1 Plan 3)
- No blockers for Phase 2 (Yad2 scraper)

---
*Phase: 01-foundation*
*Completed: 2026-04-01*
