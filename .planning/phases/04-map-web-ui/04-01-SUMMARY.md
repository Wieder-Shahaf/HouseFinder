---
phase: 04-map-web-ui
plan: 01
subsystem: frontend
tags: [react, leaflet, tanstack-query, testing, vitest, map, rtl]
dependency_graph:
  requires: []
  provides:
    - frontend/src/pages/MapView.jsx
    - frontend/src/components/ListingPin.jsx
    - frontend/src/hooks/useListings.js
    - frontend test infrastructure (vitest + jsdom + testing-library)
  affects:
    - frontend/src/main.jsx
    - frontend/src/App.jsx
    - frontend/index.html
    - frontend/vite.config.js
    - frontend/src/index.css
tech_stack:
  added:
    - lucide-react (icon library)
    - vitest + jsdom + @testing-library/react + @testing-library/jest-dom
    - @vitest/ui
  patterns:
    - TanStack Query useQuery hook for API data fetching
    - Leaflet DivIcon for custom map pins
    - React-Leaflet MapContainer + TileLayer + Marker
    - BrowserRouter + Routes for client-side routing
key_files:
  created:
    - frontend/src/pages/MapView.jsx
    - frontend/src/components/ListingPin.jsx
    - frontend/src/hooks/useListings.js
    - frontend/tests/setup.js
    - frontend/tests/MapView.test.jsx
    - frontend/tests/layout.test.jsx
  modified:
    - frontend/src/main.jsx (QueryClientProvider wrapping)
    - frontend/src/App.jsx (BrowserRouter + MapView route)
    - frontend/index.html (viewport-fit=cover, font weight 600)
    - frontend/vite.config.js (proxy + test config)
    - frontend/src/index.css (leaflet CSS import)
    - frontend/package.json (vitest scripts + deps)
decisions:
  - Leaflet zoomControl prop passed to react-leaflet mock warns in tests — acceptable; not a real DOM issue
  - Empty state shown as absolute overlay on map container (z-index 1000) rather than replacing map — map still renders behind
metrics:
  duration: 3min
  completed: 2026-04-02
  tasks_completed: 2
  files_created: 6
  files_modified: 6
---

# Phase 04 Plan 01: Map Web UI Foundation Summary

**One-liner:** Leaflet map centered on Haifa with 3-state DivIcon pins (blue/grey/red), TanStack Query data fetching, Vitest test infrastructure, and iOS-safe viewport config.

## What Was Built

### Task 1: Test Infrastructure + Deps + Config

- Installed `lucide-react`, `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`
- Updated `vite.config.js` with `/api` proxy to `localhost:8000` and `test: { environment: 'jsdom' }` block
- Updated `index.html` viewport meta to `viewport-fit=cover` for iOS safe area support
- Updated Google Fonts link to include weight 600 (semibold) per UI-SPEC typography
- Added `@import "leaflet/dist/leaflet.css"` to `index.css` (after tailwindcss import)
- Created `frontend/tests/setup.js` with `@testing-library/jest-dom`
- Added `"test": "vitest run"` script to `package.json`

### Task 2: Core UI Components

- **`useListings.js`**: TanStack Query hook with `['listings', filterParams]` query key, `staleTime: 300000`, `refetchInterval: 300000`, `refetchOnWindowFocus: true`
- **`ListingPin.jsx`**: Exports `createListingIcon(listing)` returning `L.divIcon` with 3 states: favorited (red #EF4444 heart SVG), seen (grey #94A3B8 circle, opacity 0.5), unseen (blue #2563EB circle)
- **`MapView.jsx`**: Full-screen Leaflet map centered on Haifa [32.7940, 34.9896] zoom 13, `calc(100dvh - 56px)` height, Hebrew loading/error/empty states, `onPinClick` prop wired to Marker eventHandlers
- **`main.jsx`**: Wrapped `<App>` in `<QueryClientProvider>` with `<StrictMode>` as outermost
- **`App.jsx`**: BrowserRouter + Routes with `<Route path="/" element={<MapView />} />`
- **Tests**: 7 tests across 2 files, all passing

## Acceptance Criteria Check

| Criteria | Status |
|----------|--------|
| lucide-react in dependencies | PASS |
| vitest in devDependencies | PASS |
| @testing-library/react in devDependencies | PASS |
| "test": "vitest run" script | PASS |
| vite proxy /api → localhost:8000 | PASS |
| test: environment jsdom block | PASS |
| viewport-fit=cover in index.html | PASS |
| wght@400;600;700 in fonts link | PASS |
| dir="rtl" and lang="he" in html | PASS |
| tests/setup.js with jest-dom | PASS |
| leaflet/dist/leaflet.css in index.css | PASS |
| useListings exports staleTime: 300000 | PASS |
| useListings refetchOnWindowFocus: true | PASS |
| useListings ['listings' query key | PASS |
| createListingIcon with divIcon | PASS |
| #2563EB blue unseen pin | PASS |
| #94A3B8 grey seen pin | PASS |
| #EF4444 red favorited pin | PASS |
| MapView contains 32.7940 and 34.9896 | PASS |
| MapView calc(100dvh - 56px) | PASS |
| MapView tile.openstreetmap.org | PASS |
| main.jsx QueryClientProvider | PASS |
| App.jsx BrowserRouter + MapView | PASS |
| All 7 tests pass | PASS |
| vite build succeeds | PASS |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — MapView renders live data from `/api/listings` via TanStack Query. No hardcoded data stubs.

## Self-Check: PASSED
