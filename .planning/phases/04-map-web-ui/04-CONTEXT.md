# Phase 4: Map Web UI - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver the complete mobile-first web UI: a React-Leaflet interactive map showing Haifa rental listings as pins, a bottom-sheet listing card, a filter panel, seen/favorites interactions, a /favorites route, and full Hebrew RTL layout. Phase 4 is done when all MAP-01–MAP-08 success criteria are met.

</domain>

<decisions>
## Implementation Decisions

### Pin → Card Interaction
- **D-01:** Tapping a pin opens a **bottom sheet** that slides up from the bottom of the screen. The map remains visible behind it. This is the primary listing detail surface.
- **D-02:** The bottom sheet is a **fixed single height** — all listing fields (price, rooms, size, address, contact info, post date, source badge, link to original post) are visible without dragging.
- **D-03:** Tapping the map background (anywhere outside the sheet) **dismisses** the sheet. No explicit close button required.

### Filter Panel
- **D-04:** The filter panel lives in a **bottom sheet/drawer** opened via a filter button (icon in the top bar). Keeps the map full-screen until the user needs filters. Consistent with the listing card bottom sheet pattern.
- **D-05:** Filters apply **live/instantly** — pins update immediately as each filter is toggled. No "Apply" button. TanStack Query refetches `GET /listings` with the updated params.
- **D-06:** Filter controls to implement: price range slider (max 4,500₪), room count toggles (2.5 / 3 / 3.5+), neighborhood toggles (כרמל / מרכז העיר / נווה שאנן), "חדשות בלבד" toggle.
- **D-07:** The "new only" toggle is a **simple on/off, 24h hardcoded**. No 24h/48h picker needed.

### Favorites View
- **D-08:** Favorites are accessible via a **separate `/favorites` route** — a dedicated page with favorited listings rendered as a vertical card list.
- **D-09:** Navigation uses a **bottom navigation bar** with two tabs: 🗺 Map (default landing) | ♥ Favorites. Persistent across both views.

### New Listing Visual Treatment
- **D-10:** Three distinct pin states:
  - **Unseen (new):** Bright blue pin — default for all listings not yet marked seen
  - **Seen:** Faded/grey pin — reduced visual weight, hidden from default map view
  - **Favorited:** Red heart pin (distinct icon) — stands out from both unseen and seen
- **D-11:** Data refresh via **TanStack Query `staleTime`**: refetch on window focus + every 5 minutes while active. No manual refresh button needed.

### Claude's Discretion
- Exact Tailwind color values for pin states (blue, grey, red) and their hover/active variants
- Whether to use Leaflet's `DivIcon` or `Icon` for custom pin rendering
- Exact API query param names when calling `GET /listings` from the frontend (match Phase 3 contract)
- Loading skeleton or spinner while listings fetch
- Error state UI (API unavailable, no listings found)
- Exact layout of the favorites card list items (same fields as bottom sheet or condensed)
- Mobile viewport meta tag and index.html `dir="rtl"` `lang="he"` setup

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 4 Requirements
- `.planning/REQUIREMENTS.md` — MAP-01 through MAP-08 (all 8 map UI requirements for this phase)

### Stack Decisions
- `CLAUDE.md` — Full technology stack: React 19, React-Leaflet 5.0, Leaflet 1.9, TanStack Query 5, React Router 7, Tailwind CSS 4, Vite 8; RTL guidance (`dir="rtl"` on `<html>`, `lang="he"`, Noto Sans Hebrew, Tailwind `rtl:` variants); mobile-first constraints

### Roadmap
- `.planning/ROADMAP.md` — Phase 4 success criteria (5 checkpoints that define done)

### API Contract (Phase 3)
- `.planning/phases/03-rest-api-scheduler/03-CONTEXT.md` — D-03, D-04: `GET /listings` default visibility rules (active listings, low-confidence excluded); filter params (price, rooms, neighborhood, recency, seen, favorited); seen/favorited mutation endpoints
- `backend/app/schemas/listing.py` — `ListingResponse` schema (all fields the frontend receives)
- `backend/app/routers/listings.py` — Implemented endpoint with exact query param names

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/index.css` — Noto Sans Hebrew already loaded as default font via `@theme { --font-family-sans }`. No font setup needed.
- `frontend/package.json` — All required packages already installed: react-leaflet 5.0, leaflet 1.9, @tanstack/react-query 5, react-router-dom 7, tailwindcss 4. No new dependencies needed.
- `frontend/src/App.jsx` — Placeholder skeleton. Phase 4 replaces this entirely.

### Established Patterns
- Tailwind CSS v4 (`@import "tailwindcss"` syntax, not v3 config file). Use `@theme` block for customization.
- Noto Sans Hebrew is the default sans font — all Hebrew text renders correctly without extra class names.

### Integration Points
- `App.jsx` becomes the router root (`<BrowserRouter>`) with two routes: `/` (Map view) and `/favorites` (Favorites view)
- Bottom nav bar is a shared component rendered in App.jsx, visible on both routes
- TanStack Query `QueryClientProvider` wraps the app at the root level
- `index.html` must have `dir="rtl"` and `lang="he"` on the `<html>` element — not yet applied in the skeleton

</code_context>

<specifics>
## Specific Ideas

- Bottom nav: 🗺 Map tab | ♥ Favorites tab — two tabs only, no other nav elements
- Pin mockup from discussion:
  - New (unseen): 🟦 Blue pin ← default
  - Seen: ◦ Faded/grey pin
  - Favorited: ❤️ Red/heart pin (distinct icon)
- Filter panel sketch: מחיר slider (2,000₪–4,500₪), חדרים toggles [2.5][3][3.5+], שכונה toggles [כרמל][מרכז][נש], חדשות בלבד toggle
- Favorites page header: "הדירות השמורות שלי"
- Map defaults to Haifa viewport (MAP-03 — center on Haifa, zoom to show Carmel / Downtown / Neve Shanan)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 04-map-web-ui*
*Context gathered: 2026-04-02*
