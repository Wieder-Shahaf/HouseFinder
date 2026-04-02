---
phase: 04-map-web-ui
plan: 02
subsystem: frontend
tags: [react, bottom-sheet, tanstack-query, mutations, filter, rtl, vitest]
dependency_graph:
  requires:
    - frontend/src/hooks/useListings.js
    - frontend/src/components/ListingPin.jsx
    - frontend/src/pages/MapView.jsx
    - vitest test infrastructure
  provides:
    - frontend/src/hooks/useListingMutations.js
    - frontend/src/components/SourceBadge.jsx
    - frontend/src/components/ListingSheet.jsx
    - frontend/src/components/FilterSheet.jsx
  affects:
    - frontend/src/pages/MapView.jsx
tech_stack:
  added: []
  patterns:
    - TanStack Query useMutation with cache invalidation on success
    - Bottom sheet pattern (fixed 60vh, backdrop overlay for dismiss)
    - Live filter state driven by useState + apiParams derivation
    - Vitest + testing-library component tests with vi.mock
key_files:
  created:
    - frontend/src/hooks/useListingMutations.js
    - frontend/src/components/SourceBadge.jsx
    - frontend/src/components/ListingSheet.jsx
    - frontend/src/components/FilterSheet.jsx
    - frontend/tests/ListingSheet.test.jsx
    - frontend/tests/FilterSheet.test.jsx
  modified:
    - frontend/src/pages/MapView.jsx
decisions:
  - MapView now owns all filter/sheet state internally (selectedListing, showFilters, filters) — MapView accepts no external props for these
  - apiParams derived from filters state in MapView render; single API call per filter change; multiple room selections use rooms_min/max range (omits rooms_max when 3.5+ selected)
  - Multiple neighborhood selections result in no neighborhood filter (API takes single value)
metrics:
  duration: 5min
  completed: 2026-04-02
  tasks_completed: 2
  files_created: 6
  files_modified: 1
---

# Phase 04 Plan 02: Bottom Sheets and Filter UI Summary

**One-liner:** ListingSheet (60vh bottom sheet with seen/favorite mutations) + FilterSheet (price slider, room toggles, neighborhood toggles, new-only toggle) wired into MapView with live TanStack Query refetch on filter change.

## What Was Built

### Task 1: Mutation Hooks + SourceBadge + ListingSheet

- **`useListingMutations.js`**: Exports `useMarkSeen()` and `useMarkFavorited()` — each uses `useMutation`, PUTs to `/api/listings/{id}/seen` and `/api/listings/{id}/favorited` respectively, and invalidates `['listings']` query cache on success.
- **`SourceBadge.jsx`**: Renders `source_badge` field (e.g. "יד2", "מדלן") as a small rounded slate pill.
- **`ListingSheet.jsx`**: Fixed 60vh bottom sheet with backdrop overlay. Displays: title, price (₪ formatted), rooms, size_sqm, address, contact_info, post_date, source_badge, and link to original post. Two action buttons — "ראיתי" calls `markSeen.mutate(id)` then `onClose()`, "שמור" calls `markFavorited.mutate(id)`. All buttons use `min-h-[44px]` for touch target compliance (MAP-08).
- **5 tests** in `ListingSheet.test.jsx`: null render, listing details display, backdrop dismiss, seen mutation, favorite mutation — all passing.

### Task 2: FilterSheet + MapView Wiring

- **`FilterSheet.jsx`**: Bottom sheet with four filter sections:
  - Price slider (₪2,000–₪4,500, step 100, live display of value)
  - Room toggles: 2.5 / 3 / 3.5+ (multi-select, toggle active/inactive)
  - Neighborhood toggles: כרמל / מרכז העיר / נווה שאנן (multi-select)
  - New-only toggle: sends `since_hours=24` when active
  - Each control calls `onFilterChange` immediately — no "Apply" button (per D-05)
- **`MapView.jsx`** updated:
  - Added `selectedListing`, `showFilters`, `filters` state
  - Derives `apiParams` from `filters` state on each render
  - Passes `apiParams` to `useListings(apiParams)` for live refetch
  - Filter icon button (`SlidersHorizontal`) in top-right corner, `aria-label="סנן מודעות"`
  - Renders `<ListingSheet>` and `<FilterSheet>` at bottom of component tree
- **6 tests** in `FilterSheet.test.jsx`: closed state, open controls render, price slider, room toggle activate, room toggle deactivate, new-only toggle — all passing.

## Acceptance Criteria Check

| Criteria | Status |
|----------|--------|
| useListingMutations.js exports useMarkSeen and useMarkFavorited | PASS |
| useListingMutations.js contains "invalidateQueries" | PASS |
| useListingMutations.js contains "/api/listings/" | PASS |
| SourceBadge.jsx renders source prop text | PASS |
| ListingSheet.jsx contains "60vh" | PASS |
| ListingSheet.jsx contains "ראיתי" | PASS |
| ListingSheet.jsx contains "שמור" | PASS |
| ListingSheet.jsx contains "פתח מודעה מקורית" | PASS |
| ListingSheet.jsx contains "onClose" | PASS |
| ListingSheet.jsx contains "min-h-[44px]" | PASS |
| ListingSheet.test.jsx has 5 test cases all passing | PASS |
| FilterSheet.jsx contains "מחיר מקסימלי" | PASS |
| FilterSheet.jsx contains "חדרים" | PASS |
| FilterSheet.jsx contains "שכונה" | PASS |
| FilterSheet.jsx contains "חדשות בלבד" | PASS |
| FilterSheet.jsx contains "כרמל" and "מרכז העיר" and "נווה שאנן" | PASS |
| FilterSheet.jsx contains "min-h-[44px]" | PASS |
| FilterSheet.jsx contains "onFilterChange" prop usage | PASS |
| MapView.jsx contains "selectedListing" state | PASS |
| MapView.jsx contains "showFilters" state | PASS |
| MapView.jsx contains "ListingSheet" import and render | PASS |
| MapView.jsx contains "FilterSheet" import and render | PASS |
| MapView.jsx contains "SlidersHorizontal" | PASS |
| MapView.jsx contains aria-label "סנן מודעות" | PASS |
| MapView.jsx contains "since_hours" | PASS |
| MapView.jsx contains "price_max" | PASS |
| FilterSheet.test.jsx has 6 test cases all passing | PASS |
| npx vitest run exits 0 (19 tests pass) | PASS |
| npx vite build succeeds | PASS |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all components are wired to real API endpoints and live query state.

## Self-Check: PASSED
