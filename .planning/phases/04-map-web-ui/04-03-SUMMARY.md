---
phase: 04-map-web-ui
plan: "03"
subsystem: frontend
tags: [favorites, navigation, routing, react, tailwind, rtl]
dependency_graph:
  requires: ["04-01"]
  provides: [favorites-view, bottom-nav, favorites-routing]
  affects: [frontend/src/App.jsx]
tech_stack:
  added: []
  patterns: [react-router-dom-v6, tanstack-query, tailwind-utility-classes]
key_files:
  created:
    - frontend/src/components/FavoriteCard.jsx
    - frontend/src/pages/FavoritesView.jsx
    - frontend/src/components/BottomNav.jsx
    - frontend/tests/FavoritesView.test.jsx
  modified:
    - frontend/src/App.jsx
decisions:
  - "FavoritesView fetches data via useListings({ is_favorited: true }) — same hook as MapView, no new query pattern needed"
  - "BottomNav uses env(safe-area-inset-bottom) inline style for iOS safe area — not a Tailwind class since v4 does not expose it"
  - "BottomNav rendered outside Routes in App.jsx so it persists across all route transitions"
metrics:
  duration: 5min
  completed_date: "2026-04-02"
  tasks: 1
  files: 5
---

# Phase 04 Plan 03: FavoritesView + BottomNav + Routing Summary

## One-liner

Favorites page with Hebrew card list, 2-tab bottom nav (מפה/שמורים), /favorites route wired in App.jsx, 4 passing tests.

## What Was Built

### FavoriteCard component (`frontend/src/components/FavoriteCard.jsx`)
Renders a single favorited listing card showing: title, price (formatted with ₪ and toLocaleString), rooms + size, address, post date (he-IL locale), SourceBadge, and an external link with 44px touch target.

### FavoritesView page (`frontend/src/pages/FavoritesView.jsx`)
Fetches favorited listings via `useListings({ is_favorited: true })`. Handles three states:
- Loading spinner
- Error message in Hebrew
- Empty state "עוד לא שמרת דירות" when no favorites
Maps listings to FavoriteCard components with `pb-16` bottom padding for BottomNav clearance.

### BottomNav component (`frontend/src/components/BottomNav.jsx`)
Fixed bottom navigation with 2 tabs: מפה (Map icon) and שמורים (Heart icon). Active tab highlighted in `text-blue-600`, inactive in `text-slate-500`. Height `h-14` (56px). iOS safe area handled via inline style `env(safe-area-inset-bottom, 0px)`. Touch targets `min-h-[44px]`.

### App.jsx routing update
Added `/favorites` route pointing to FavoritesView. BottomNav rendered outside Routes so it persists on all pages.

### Tests (`frontend/tests/FavoritesView.test.jsx`)
4 tests: renders header, renders cards with prices, shows empty state, verifies `useListings` called with `{ is_favorited: true }`.

## Verification Results

- All 23 tests pass (5 test files)
- `npx vite build` succeeds — 433KB bundle, 173ms
- `grep "is_favorited" frontend/src/pages/FavoritesView.jsx` — confirmed
- `grep "BottomNav" frontend/src/App.jsx` — confirmed
- `grep "/favorites" frontend/src/App.jsx` — confirmed

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — FavoritesView fetches real data from `/api/listings?is_favorited=true`, which is the live backend endpoint built in Phase 03.

## Self-Check: PASSED

- frontend/src/components/FavoriteCard.jsx — FOUND
- frontend/src/pages/FavoritesView.jsx — FOUND
- frontend/src/components/BottomNav.jsx — FOUND
- frontend/tests/FavoritesView.test.jsx — FOUND
- Commit e6969e6 — FOUND
