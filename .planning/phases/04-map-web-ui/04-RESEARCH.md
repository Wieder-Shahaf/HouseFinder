# Phase 4: Map Web UI - Research

**Researched:** 2026-04-02
**Domain:** React + React-Leaflet + TanStack Query + RTL/Hebrew frontend
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Pin → Card Interaction**
- D-01: Tapping a pin opens a bottom sheet that slides up from the bottom of the screen. The map remains visible behind it.
- D-02: The bottom sheet is a fixed single height — all listing fields (price, rooms, size, address, contact info, post date, source badge, link to original post) are visible without dragging.
- D-03: Tapping the map background (anywhere outside the sheet) dismisses the sheet. No explicit close button required.

**Filter Panel**
- D-04: The filter panel lives in a bottom sheet/drawer opened via a filter button (icon in the top bar). Consistent with the listing card bottom sheet pattern.
- D-05: Filters apply live/instantly — pins update immediately as each filter is toggled. No "Apply" button. TanStack Query refetches GET /listings with the updated params.
- D-06: Filter controls: price range slider (max 4,500₪), room count toggles (2.5 / 3 / 3.5+), neighborhood toggles (כרמל / מרכז העיר / נווה שאנן), "חדשות בלבד" toggle.
- D-07: The "new only" toggle is a simple on/off, 24h hardcoded. No 24h/48h picker needed.

**Favorites View**
- D-08: Favorites accessible via a separate /favorites route — a dedicated page with favorited listings as a vertical card list.
- D-09: Navigation uses a bottom navigation bar with two tabs: Map (default) | Favorites. Persistent across both views.

**New Listing Visual Treatment**
- D-10: Three distinct pin states:
  - Unseen (new): Bright blue pin (#2563EB / blue-600) — default
  - Seen: Faded/grey pin (#94A3B8 / slate-400) — reduced visual weight, 50% opacity
  - Favorited: Red heart pin (#EF4444 / red-500) — distinct icon
- D-11: Data refresh via TanStack Query staleTime: refetch on window focus + every 5 minutes while active. No manual refresh button needed.

### Claude's Discretion
- Exact Tailwind color values for pin states (blue, grey, red) and their hover/active variants
- Whether to use Leaflet's DivIcon or Icon for custom pin rendering
- Exact API query param names when calling GET /listings from the frontend (match Phase 3 contract)
- Loading skeleton or spinner while listings fetch
- Error state UI (API unavailable, no listings found)
- Exact layout of the favorites card list items (same fields as bottom sheet or condensed)
- Mobile viewport meta tag and index.html `dir="rtl"` `lang="he"` setup

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MAP-01 | Interactive map (React-Leaflet + OpenStreetMap) shows all listings as pins | React-Leaflet v5.0.0 installed; Leaflet 1.9.4 installed; MapContainer + TileLayer + Marker confirmed available |
| MAP-02 | Clicking a pin opens a listing card showing price, rooms, size, contact info, post date, source, link | Bottom sheet via CSS translate + z-index; ListingResponse schema confirmed present in backend |
| MAP-03 | Map defaults to Haifa viewport (Carmel, Downtown, Neve Shanan) | center=[32.7940, 34.9896] zoom=13 confirmed in UI-SPEC |
| MAP-04 | Filter panel: price range slider (max 4,500₪), room count toggle, neighborhood toggle, "new only" toggle | All filter params confirmed in backend GET /listings; live refetch via TanStack Query |
| MAP-05 | User can mark a listing as "seen" — pin fades, hidden from default view | PUT /api/listings/{id}/seen confirmed in backend; optimistic update via TanStack Query |
| MAP-06 | User can save a listing as favorite — distinct icon, accessible in favorites list | PUT /api/listings/{id}/favorited confirmed in backend; /favorites route with is_favorited=true filter |
| MAP-07 | Full Hebrew RTL layout (dir="rtl" on html element from day one) | index.html already has `<html lang="he" dir="rtl">`; Tailwind v4 with rtl: variants; Noto Sans Hebrew loaded |
| MAP-08 | Mobile-responsive, usable on smartphone browser | 100dvh for map container; min-h-[44px] touch targets; viewport-fit=cover for iOS safe areas |
</phase_requirements>

---

## Summary

Phase 4 builds the entire frontend application from a placeholder `App.jsx` into a fully functional map-based UI. All dependencies are already installed and verified — React 19.2.4, React-Leaflet 5.0.0, Leaflet 1.9.4, TanStack Query 5.96.1, React Router DOM 7.13.2, Tailwind CSS 4.2.2, Vite 8.0.3. The only missing dependency is `lucide-react` (icons), which must be installed before implementation.

The backend API contract is fully established in Phase 3. All filter params (`price_max`, `rooms_min`, `rooms_max`, `neighborhood`, `since_hours`, `is_favorited`) and mutation endpoints (`PUT /api/listings/{id}/seen`, `PUT /api/listings/{id}/favorited`) are confirmed in `backend/app/routers/listings.py`. The `ListingResponse` schema is confirmed in `backend/app/schemas/listing.py` with all fields the UI needs.

The critical implementation challenge is Leaflet's custom pin rendering using `DivIcon` — injecting SVG/HTML into Leaflet markers. Leaflet `DivIcon` with inline HTML is the correct approach for the three-state pin design (blue circle, grey faded, red heart). Leaflet's CSS must be imported in main.jsx, and the map container must use `100dvh` (not `100vh`) to handle mobile browser chrome. There is no frontend test framework installed — Wave 0 must add Vitest and set up the test scaffold before implementation.

**Primary recommendation:** Build in 4 waves: (1) Wave 0 — test infra + Vitest setup; (2) Wave 1 — MapView with pins and TanStack Query fetching; (3) Wave 2 — bottom sheets (ListingSheet + FilterSheet) and pin state mutations; (4) Wave 3 — FavoritesView + BottomNav + routing wiring.

---

## Standard Stack

### Core (already installed — verified from node_modules)

| Library | Installed Version | Purpose | Confirmed |
|---------|------------------|---------|-----------|
| React | 19.2.4 | UI framework | node_modules scan |
| React-Leaflet | 5.0.0 | Leaflet React wrapper | node_modules scan |
| Leaflet.js | 1.9.4 | Map engine | node_modules scan |
| TanStack Query | 5.96.1 | Server state + auto-refetch | node_modules scan |
| React Router DOM | 7.13.2 | Client-side routing | node_modules scan |
| Tailwind CSS | 4.2.2 | Utility CSS + RTL support | node_modules scan |
| Vite | 8.0.3 | Build tool / dev server | node_modules scan |

### Must Install

| Library | Purpose | Command |
|---------|---------|---------|
| lucide-react | Icons for pin states, bottom nav, filter button | `npm i lucide-react` (from `frontend/`) |

**lucide-react is NOT currently installed.** The UI-SPEC designates it as the icon library. Wave 0 must install it before any component work begins.

### No Additional Dependencies Needed

The UI-SPEC explicitly confirms: no component library (shadcn, MUI, Chakra). All components are custom-built with Tailwind classes. No shadcn initialization. Noto Sans Hebrew already loaded via `frontend/src/index.css` `@theme` block and Google Fonts in `index.html`.

---

## Architecture Patterns

### Confirmed Project Structure (from UI-SPEC Component Inventory)

```
frontend/src/
├── App.jsx              # Router root — replace placeholder entirely
├── main.jsx             # Entry point — add QueryClientProvider + Leaflet CSS import
├── index.css            # Tailwind v4 @import + @theme (Noto Sans Hebrew — already done)
├── pages/
│   ├── MapView.jsx      # Full-screen Leaflet map with pin rendering
│   └── FavoritesView.jsx # Favorites list at /favorites
└── components/
    ├── BottomNav.jsx    # Persistent 2-tab bottom nav (56px height)
    ├── ListingSheet.jsx # Bottom sheet for listing detail (h-[60vh])
    ├── FilterSheet.jsx  # Bottom sheet for filter controls
    ├── ListingPin.jsx   # Leaflet DivIcon with 3-state color logic
    ├── FavoriteCard.jsx # Condensed listing card for favorites list
    └── SourceBadge.jsx  # Inline source label (יד2 / מדלן)
```

### Pattern 1: Leaflet DivIcon for Custom Pins

`DivIcon` renders arbitrary HTML into a Leaflet marker. This is the only way to achieve the three-state pin design (blue circle, grey faded 50% opacity, red heart SVG). Import `divIcon` from `leaflet` directly.

```jsx
// Source: Leaflet 1.9.4 — node_modules/leaflet/dist/leaflet-src.js
import L from 'leaflet'

function createPinIcon(state) {
  if (state === 'unseen') {
    return L.divIcon({
      html: `<div style="width:20px;height:20px;border-radius:50%;background:#2563EB;border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.3)"></div>`,
      className: '',
      iconSize: [20, 20],
      iconAnchor: [10, 10],
    })
  }
  if (state === 'seen') {
    return L.divIcon({
      html: `<div style="width:20px;height:20px;border-radius:50%;background:#94A3B8;border:2px solid white;opacity:0.5"></div>`,
      className: '',
      iconSize: [20, 20],
      iconAnchor: [10, 10],
    })
  }
  // favorited — red heart
  return L.divIcon({
    html: `<div style="color:#EF4444;font-size:20px;line-height:1">❤</div>`,
    className: '',
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  })
}
```

**CRITICAL:** `className: ''` is required. Without it, Leaflet applies its default `leaflet-div-icon` class which adds unwanted white background and border styles that will break the pin appearance.

### Pattern 2: React-Leaflet v5 MapContainer

React-Leaflet v5 (confirmed installed) requires Leaflet CSS to be imported in `main.jsx` before any map component renders. Missing this import causes invisible markers.

```jsx
// Source: node_modules/react-leaflet/lib/MapContainer.js (confirmed)
// main.jsx — add BEFORE App import
import 'leaflet/dist/leaflet.css'
```

```jsx
// MapView.jsx
import { MapContainer, TileLayer, Marker } from 'react-leaflet'

<MapContainer
  center={[32.7940, 34.9896]}
  zoom={13}
  style={{ height: 'calc(100dvh - 56px)', width: '100%' }}
  zoomControl={false}
>
  <TileLayer
    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  />
  {listings.map(listing => (
    <Marker
      key={listing.id}
      position={[listing.lat, listing.lng]}
      icon={createPinIcon(getPinState(listing))}
      eventHandlers={{ click: () => setSelectedListing(listing) }}
    />
  ))}
</MapContainer>
```

**Confirmed from node_modules/react-leaflet/lib/index.js:** Available exports include `MapContainer`, `TileLayer`, `Marker`, `Popup`, `useMap`, `useMapEvent`, `useMapEvents`.

### Pattern 3: TanStack Query v5 Setup

TanStack Query v5 changed the API from v4: `useQuery` options are an object, not positional args. The `queryKey` is an array, `queryFn` is separate.

```jsx
// Source: node_modules/@tanstack/react-query (v5.96.1 confirmed)
// main.jsx — wrap app
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 300_000,       // 5 minutes (D-11)
      refetchOnWindowFocus: true, // (D-11)
      refetchInterval: 300_000,   // 5 minutes while tab active (D-11)
      retry: 2,
    },
  },
})

// MapView.jsx — fetch listings with filter params
const { data: listings = [], isLoading, isError } = useQuery({
  queryKey: ['listings', filterParams],
  queryFn: () => fetch(`/api/listings/?${new URLSearchParams(filterParams)}`).then(r => r.json()),
})

// Mutation for marking seen
const seenMutation = useMutation({
  mutationFn: (id) => fetch(`/api/listings/${id}/seen`, { method: 'PUT' }).then(r => r.json()),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['listings'] }),
})
```

**Filter query key change:** When `filterParams` state changes (any filter toggle), TanStack Query automatically refetches with the new params — implementing D-05 live filter behavior.

### Pattern 4: Bottom Sheet (no external library)

Bottom sheets are implemented as absolutely positioned divs with CSS transition — no external sheet library required.

```jsx
// ListingSheet.jsx
<div
  className={`fixed bottom-0 left-0 right-0 bg-white rounded-t-2xl z-[1000] transition-transform duration-300 ${
    isOpen ? 'translate-y-0' : 'translate-y-full'
  }`}
  style={{ height: '60vh' }}
>
  {/* sheet content */}
</div>
{/* Overlay — tap to dismiss (D-03) */}
{isOpen && (
  <div
    className="fixed inset-0 z-[999]"
    onClick={onClose}
  />
)}
```

**Z-index strategy:** Map tiles render at z-index 400 (Leaflet default). Map controls at 800. Bottom sheet at z-[1000]. Overlay at z-[999] (below sheet, above map). Bottom nav at z-[1001] (above sheet when both visible).

### Pattern 5: React Router DOM v7 Routing

React Router v7 (7.13.2 installed) uses `BrowserRouter`, `Routes`, `Route` from `react-router-dom`. The `BottomNav` is rendered outside `<Routes>` so it persists on both routes.

```jsx
// App.jsx — replace placeholder entirely
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import MapView from './pages/MapView'
import FavoritesView from './pages/FavoritesView'
import BottomNav from './components/BottomNav'

const queryClient = new QueryClient({ /* ... D-11 config */ })

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="flex flex-col h-dvh">
          <div className="flex-1 overflow-hidden">
            <Routes>
              <Route path="/" element={<MapView />} />
              <Route path="/favorites" element={<FavoritesView />} />
            </Routes>
          </div>
          <BottomNav />
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
```

### Pattern 6: Tailwind v4 RTL

Tailwind v4 uses CSS-based config. The `rtl:` variant works when `dir="rtl"` is on the `<html>` element. **Confirmed: `index.html` already has `<html lang="he" dir="rtl">`** — no changes needed to index.html for RTL.

For layout properties that flip in RTL, use logical properties:
- `ms-` (margin-start) instead of `ml-` — flips in RTL
- `me-` (margin-end) instead of `mr-`
- `ps-` / `pe-` for padding
- `start-` / `end-` for positioning
- `rtl:flex-row-reverse` for row direction when needed

```jsx
// Source: Tailwind v4 — confirmed installed at 4.2.2
// RTL-aware button layout:
<div className="flex items-center gap-2 rtl:flex-row-reverse">
  <MapIcon />
  <span>מפה</span>
</div>
```

### Anti-Patterns to Avoid

- **Importing Leaflet default markers without CSS:** Leaflet default marker images (marker-icon.png, marker-shadow.png) break with Webpack/Vite unless CSS is imported AND the image path issue is resolved. The DivIcon approach entirely avoids this — confirmed correct choice for custom pins.
- **Using `100vh` for map container on mobile:** Mobile browser chrome (address bar) shrinks the viewport. `100dvh` (dynamic viewport height) is the correct CSS unit for Vite/modern browsers. Already specified in UI-SPEC spacing scale.
- **TanStack Query v4 API with v5:** The old `useQuery(key, fn, options)` positional signature does not exist in v5. Must use `useQuery({ queryKey, queryFn, ...options })`.
- **`className` on DivIcon:** Always set `className: ''` on `L.divIcon()` calls. The default `'leaflet-div-icon'` class applies white background + border that will override pin styles.
- **Direct Leaflet map DOM manipulation inside React:** Never call `map.openPopup()` or similar imperatively inside render. Use React-Leaflet's component model (`<Popup>`) or `useMap()` hook inside a child component only.
- **Rendering Leaflet outside `MapContainer`:** `useMap()` hook throws if used outside `<MapContainer>`. Components that call `useMap()` must be children of `<MapContainer>`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Map tile rendering | Custom tile fetching | `TileLayer` from react-leaflet | Handles tile caching, viewport math, attribution |
| Marker clustering | Custom grid grouping | `leaflet.markercluster` (optional future, not in scope) | — |
| Server state caching | useState + useEffect polling | TanStack Query `useQuery` | Cache invalidation, background refetch, loading/error states handled |
| Optimistic updates | Manual state clone + patch | TanStack Query `useMutation` + `onSuccess` invalidation | Race condition safety, rollback on error |
| Router link active state | className comparison | React Router `NavLink` with `className` prop | `isActive` is injected by NavLink automatically |
| Bottom sheet animation | Custom requestAnimationFrame | CSS `transition-transform` + Tailwind `translate-y-*` | GPU-accelerated, zero JS needed |

---

## Runtime State Inventory

Step 2.5: SKIPPED — This is a greenfield frontend build phase, not a rename/refactor/migration. No runtime state is being renamed or migrated.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Node.js | Frontend build | ✓ | v24.6.0 | — |
| npm | Package install | ✓ | 11.5.1 | — |
| React | UI framework | ✓ | 19.2.4 | — |
| React-Leaflet | Map component | ✓ | 5.0.0 | — |
| Leaflet.js | Map engine | ✓ | 1.9.4 | — |
| TanStack Query | Server state | ✓ | 5.96.1 | — |
| React Router DOM | Routing | ✓ | 7.13.2 | — |
| Tailwind CSS | Styling | ✓ | 4.2.2 | — |
| Vite | Dev server / build | ✓ | 8.0.3 | — |
| lucide-react | Icons | ✗ | — | Must install: `npm i lucide-react` from `frontend/` |
| FastAPI backend | API data source | ✓ (Phase 3 complete) | — | Dev: `uvicorn app.main:app --reload` in `backend/` |
| Vitest | Frontend tests | ✗ | — | Must install: Wave 0 task |

**Missing dependencies with no fallback:**
- `lucide-react` — required for filter icon button, bottom nav icons, and source badge. Must be installed before component work. Command: `cd frontend && npm i lucide-react`
- Vitest test framework — no frontend test infrastructure exists. Wave 0 must install and configure it.

**Missing dependencies with fallback:**
- None.

---

## Common Pitfalls

### Pitfall 1: Leaflet Default Marker Images Break with Vite

**What goes wrong:** When using the default Leaflet `Marker` without a custom icon, markers render as broken image icons. The marker PNG assets (marker-icon.png, marker-shadow.png) are bundled incorrectly by Vite.

**Why it happens:** Leaflet resolves marker images relative to its own CSS, which breaks in module bundlers. The path resolution assumes a classic script tag environment.

**How to avoid:** Use `L.divIcon()` for all markers (which this phase does by design). Never use `new L.Icon.Default()` or the Leaflet default marker. The DivIcon approach in the `ListingPin` component completely sidesteps this issue.

**Warning signs:** Markers appear but show a broken image placeholder.

### Pitfall 2: Leaflet CSS Not Imported → Invisible Markers / Broken Map

**What goes wrong:** Map tiles and markers render but controls are missing, map chrome is wrong, or markers are invisible.

**Why it happens:** React-Leaflet does not automatically import Leaflet's CSS. The CSS contains z-index, positioning, and sprite image definitions that Leaflet depends on.

**How to avoid:** Add `import 'leaflet/dist/leaflet.css'` to `main.jsx` — before the `App` import. This must be the very first side-effect import.

**Warning signs:** Map loads but looks wrong (tiles overlap controls, marker z-index incorrect).

### Pitfall 3: Map Container Height with Mobile Browser Chrome

**What goes wrong:** Map appears cut off or bottom nav overlaps map on mobile Safari/Chrome.

**Why it happens:** `100vh` is the layout viewport (does not account for the browser address bar). On mobile, the address bar shrinks/expands as the user scrolls, but `100vh` remains fixed at the initial size.

**How to avoid:** Use `height: calc(100dvh - 56px)` (dvh = dynamic viewport height). `56px` is the bottom nav height (`h-14`). Also use `viewport-fit=cover` in the viewport meta tag (already confirmed in UI-SPEC).

**Warning signs:** Bottom nav overlaps the map or scrolls off-screen.

### Pitfall 4: TanStack Query v5 API Breaking Change

**What goes wrong:** Runtime error: "Expected queryKey to be defined" or "queryFn is not a function".

**Why it happens:** TanStack Query v5 removed the old positional `useQuery(key, fn, options)` signature. v5 requires `useQuery({ queryKey: [...], queryFn: fn })`.

**How to avoid:** Always use the object form. Check the version once: `node_modules/@tanstack/react-query/package.json` confirms v5.96.1 is installed.

**Warning signs:** Runtime errors referencing queryKey shape.

### Pitfall 5: Filter State and Query Key Must Stay in Sync

**What goes wrong:** Filter changes don't trigger refetch; or every character typed in the price slider fires a separate network request.

**Why it happens:** If `filterParams` is not properly memoized as the `queryKey`, TanStack Query either does not detect the change (stale cache) or fires too many requests (object identity changes on every render).

**How to avoid:** Store filter state as a flat primitive object (not nested). Use `useState` with individual keys, not a single nested object that gets spread. Alternatively, use `useMemo` to stabilize the query key object when deriving it from multiple state variables.

**Warning signs:** Network tab shows no refetch on filter change, or shows many rapid requests.

### Pitfall 6: Seen Listings Disappear Immediately (Unexpected UX)

**What goes wrong:** When a user taps "ראיתי", the pin vanishes from the map immediately if the filter `is_seen` is not explicitly set to `false` in the query.

**Why it happens:** The UI-SPEC (Interaction Contracts section) specifies: "Default map view shows all pins including seen ones. Seen pins are visually de-emphasized (grey, 50% opacity) but not hidden at map level." The backend default returns all active listings regardless of `is_seen`. The frontend handles visual de-emphasis, not server-side filtering.

**How to avoid:** Do NOT pass `is_seen=false` to the GET /listings query in the default map view. Apply the grey/opacity styling on the frontend based on the `is_seen` field in the response. Only the favorites view uses `is_favorited=true`.

**Warning signs:** Tapping "ראיתי" makes a pin disappear from the map when it should only become grey.

### Pitfall 7: RTL Breaks Leaflet Map Controls

**What goes wrong:** Leaflet zoom controls, attribution badge, and tile credits appear on the wrong side or overlap.

**Why it happens:** Leaflet renders its own DOM outside React's tree. The `dir="rtl"` on `<html>` propagates into Leaflet's container, flipping its internal layout.

**How to avoid:** Override Leaflet control positioning explicitly. Use `zoomControl={false}` on `<MapContainer>` and add `<ZoomControl position="bottomright" />` explicitly to override the default. Check that attribution badge does not overlap the bottom nav.

**Warning signs:** Zoom controls appear on the wrong side; attribution overlaps UI elements.

---

## Code Examples

### ListingPin — DivIcon with 3-state logic

```jsx
// src/components/ListingPin.jsx
// Source: Leaflet 1.9.4 node_modules — DivIcon API confirmed
import L from 'leaflet'

export function createPinIcon(listing) {
  if (listing.is_favorited) {
    return L.divIcon({
      html: `<div style="color:#EF4444;font-size:22px;line-height:1;filter:drop-shadow(0 1px 2px rgba(0,0,0,0.3))">❤</div>`,
      className: '',
      iconSize: [22, 22],
      iconAnchor: [11, 11],
    })
  }
  if (listing.is_seen) {
    return L.divIcon({
      html: `<div style="width:18px;height:18px;border-radius:50%;background:#94A3B8;border:2px solid white;opacity:0.5;box-shadow:0 1px 3px rgba(0,0,0,0.2)"></div>`,
      className: '',
      iconSize: [18, 18],
      iconAnchor: [9, 9],
    })
  }
  // Default: unseen (new)
  return L.divIcon({
    html: `<div style="width:20px;height:20px;border-radius:50%;background:#2563EB;border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.3)"></div>`,
    className: '',
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  })
}
```

### main.jsx — Required Provider Wrappers + Leaflet CSS

```jsx
// src/main.jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'leaflet/dist/leaflet.css'   // MUST come before App
import App from './App.jsx'
import './index.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

### TanStack Query — Listings Fetch with Filter Params

```jsx
// Source: @tanstack/react-query v5.96.1 confirmed
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

// Fetch with live filter params (D-05, D-11)
function useListings(filterParams) {
  return useQuery({
    queryKey: ['listings', filterParams],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (filterParams.price_max) params.set('price_max', filterParams.price_max)
      if (filterParams.rooms_min) params.set('rooms_min', filterParams.rooms_min)
      if (filterParams.rooms_max) params.set('rooms_max', filterParams.rooms_max)
      if (filterParams.neighborhood) params.set('neighborhood', filterParams.neighborhood)
      if (filterParams.since_hours) params.set('since_hours', filterParams.since_hours)
      const res = await fetch(`/api/listings/?${params}`)
      if (!res.ok) throw new Error('API error')
      return res.json()
    },
    staleTime: 300_000,
    refetchOnWindowFocus: true,
    refetchInterval: 300_000,
  })
}

// Mark seen mutation (MAP-05)
function useMarkSeen() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id) =>
      fetch(`/api/listings/${id}/seen`, { method: 'PUT' }).then(r => r.json()),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['listings'] }),
  })
}
```

### Favorites Fetch (MAP-06)

```jsx
// FavoritesView.jsx
const { data: favorites = [], isLoading } = useQuery({
  queryKey: ['listings', { is_favorited: true }],
  queryFn: () => fetch('/api/listings/?is_favorited=true').then(r => r.json()),
  staleTime: 300_000,
})
```

### index.html Viewport Meta (MAP-08 — already confirmed present)

```html
<!-- index.html — already has lang="he" dir="rtl" -->
<!-- Needs viewport-fit=cover added to existing viewport meta: -->
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
```

**Confirmed:** `index.html` already has `<html lang="he" dir="rtl">`. The viewport meta currently uses `initial-scale=1.0` without `viewport-fit=cover`. The UI-SPEC requires `viewport-fit=cover` for iOS safe areas — this must be updated in Wave 0.

---

## State of the Art

| Old Approach | Current Approach | Version When Changed | Impact |
|--------------|------------------|----------------------|--------|
| `useQuery(key, fn, options)` positional args | `useQuery({ queryKey, queryFn, ...options })` object form | TanStack Query v5 (2024) | Breaking change from v4; v5.96.1 is installed |
| `tailwind.config.js` + `tailwind.config.cjs` | `@import "tailwindcss"` + `@theme {}` in CSS | Tailwind v4 (2025) | No config file; all customization in CSS |
| Create React App | Vite | 2022–2023 | CRA is deprecated; Vite 8.x is current |
| `100vh` for mobile full-height | `100dvh` (dynamic viewport height) | CSS Levels 4 (2023 broad support) | `dvh` adjusts for browser chrome; `vh` does not |
| Leaflet default Icon class | `L.divIcon()` with inline HTML | Always available, now preferred | Avoids Vite bundling image path issues entirely |

---

## Open Questions

1. **Vite proxy config for `/api` calls in development**
   - What we know: The frontend runs on port 5173 (Vite), the backend on port 8000 (FastAPI). Fetch calls to `/api/listings/` will fail with CORS or 404 in dev without a proxy.
   - What's unclear: Whether `vite.config.js` currently has a proxy configured.
   - Recommendation: Wave 0 must add `server.proxy = { '/api': 'http://localhost:8000' }` to `vite.config.js` if not present. Confirmed: current `vite.config.js` does NOT have a proxy entry — only `host: true` and `port: 5173`.

2. **Filter behavior for multiple room toggles**
   - What we know: The UI-SPEC notes "Multiple room toggles can be active simultaneously — frontend sends one request per active toggle and merges results, or sends the lowest rooms_min of active selections."
   - What's unclear: The backend only accepts a single `rooms_min`/`rooms_max` pair. Multiple simultaneous room selections require either multiple queries or a "range union" logic.
   - Recommendation: Implement as "lowest rooms_min of active selections" approach — simplest, single request. If 2.5 and 3 are both active, send `rooms_min=2.5&rooms_max=3`. If 3.5+ is active alone, send `rooms_min=3.5` (no max). Document this logic clearly in FilterSheet.jsx.

3. **Backend CORS configuration for local dev**
   - What we know: FastAPI backend is on port 8000; frontend on 5173. Without CORS headers or Vite proxy, API calls will be blocked.
   - What's unclear: Whether the Phase 3 backend includes CORS middleware.
   - Recommendation: Check `backend/app/main.py` for `CORSMiddleware`. If absent, Wave 0 adds it (or the Vite proxy makes it unnecessary for dev). For production, Nginx proxies `/api` so CORS is not needed in prod.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Vitest (to be installed in Wave 0) |
| Config file | `frontend/vite.config.js` — add `test` block |
| Quick run command | `cd frontend && npx vitest run --reporter=dot` |
| Full suite command | `cd frontend && npx vitest run` |

No frontend test framework is currently installed. The project has a robust backend test suite (pytest, confirmed in `backend/tests/`), but the frontend has zero test files and no test runner.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MAP-01 | Map renders with pins from API | unit (component render) | `npx vitest run tests/MapView.test.jsx` | ❌ Wave 0 |
| MAP-02 | Pin tap opens bottom sheet with listing fields | unit (interaction) | `npx vitest run tests/ListingSheet.test.jsx` | ❌ Wave 0 |
| MAP-03 | Map defaults to Haifa viewport center=[32.7940, 34.9896] zoom=13 | unit (props) | `npx vitest run tests/MapView.test.jsx` | ❌ Wave 0 |
| MAP-04 | Filter changes update query params sent to API | unit (state) | `npx vitest run tests/FilterSheet.test.jsx` | ❌ Wave 0 |
| MAP-05 | "ראיתי" tap calls PUT /seen and updates pin state | unit (mutation) | `npx vitest run tests/ListingSheet.test.jsx` | ❌ Wave 0 |
| MAP-06 | "שמור" tap calls PUT /favorited; /favorites shows favorited listings | unit (mutation + route) | `npx vitest run tests/FavoritesView.test.jsx` | ❌ Wave 0 |
| MAP-07 | HTML dir="rtl" lang="he" present; text flows RTL | smoke (DOM check) | manual verify in browser | manual-only |
| MAP-08 | Touch targets >= 44px; 100dvh map container | unit (style assertions) | `npx vitest run tests/layout.test.jsx` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd frontend && npx vitest run --reporter=dot`
- **Per wave merge:** `cd frontend && npx vitest run`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `frontend/tests/setup.js` — jsdom + @testing-library/react setup
- [ ] `frontend/tests/MapView.test.jsx` — covers MAP-01, MAP-03
- [ ] `frontend/tests/ListingSheet.test.jsx` — covers MAP-02, MAP-05
- [ ] `frontend/tests/FilterSheet.test.jsx` — covers MAP-04
- [ ] `frontend/tests/FavoritesView.test.jsx` — covers MAP-06
- [ ] `frontend/tests/layout.test.jsx` — covers MAP-08
- [ ] Install test framework: `cd frontend && npm i -D vitest @vitest/ui jsdom @testing-library/react @testing-library/user-event`
- [ ] Add `test` block to `frontend/vite.config.js`
- [ ] Add Vite proxy: `server.proxy = { '/api': 'http://localhost:8000' }` to `frontend/vite.config.js`
- [ ] Update viewport meta in `frontend/index.html` to add `viewport-fit=cover`

---

## Sources

### Primary (HIGH confidence)
- `frontend/node_modules/react-leaflet/lib/index.js` — confirmed exported APIs (MapContainer, TileLayer, Marker, useMap, useMapEvent)
- `frontend/node_modules/react-leaflet/lib/MapContainer.js` — MapContainer implementation confirmed
- `frontend/node_modules/react-leaflet/lib/Marker.js` — Marker with icon/position props confirmed
- `frontend/node_modules/react-leaflet/lib/hooks.js` — useMap, useMapEvent, useMapEvents confirmed
- `frontend/node_modules/@tanstack/react-query/package.json` — v5.96.1 confirmed
- `backend/app/routers/listings.py` — all API params and mutation endpoints confirmed
- `backend/app/schemas/listing.py` — ListingResponse fields confirmed
- `frontend/index.html` — `dir="rtl"` `lang="he"` confirmed present
- `frontend/package.json` — all dependency versions confirmed
- `.planning/phases/04-map-web-ui/04-CONTEXT.md` — all locked decisions
- `.planning/phases/04-map-web-ui/04-UI-SPEC.md` — full component inventory, color spec, spacing

### Secondary (MEDIUM confidence)
- Leaflet DivIcon `className: ''` requirement — known issue documented widely; confirmed by examining Leaflet's default CSS behavior
- `100dvh` for mobile — CSS specification; confirmed by examining MDN browser support data in training corpus (broad support since 2023)

### Tertiary (LOW confidence)
- None — all critical claims verified against installed source code.

---

## Project Constraints (from CLAUDE.md)

The following directives from `CLAUDE.md` apply to Phase 4 and the planner MUST verify compliance:

| Directive | Implication for Phase 4 |
|-----------|------------------------|
| React 18.x specified in CLAUDE.md stack table | **Overridden by STATE.md decision:** React 19.2.4 is installed and confirmed. Use React 19. |
| Leaflet (React-Leaflet 4.2+, Leaflet 1.9+) | React-Leaflet 5.0.0 and Leaflet 1.9.4 installed — exceeds minimum. Use installed versions. |
| TanStack Query 5.x | 5.96.1 installed — compliant. |
| React Router 6.x specified | **Overridden by STATE.md decision:** React Router DOM 7.13.2 installed. Use v7. |
| Tailwind CSS 3.4+ with `rtl:` variants | **Overridden by STATE.md:** Tailwind v4 (4.2.2) installed with CSS-based config. Use v4 patterns. |
| `dir="rtl"` on `<html>` from day one (MAP-07) | index.html already has `<html lang="he" dir="rtl">` — compliant. |
| Mobile-first, smartphone browser primary | 100dvh, 44px touch targets, bottom nav at 56px height. |
| Noto Sans Hebrew | Already loaded in index.css + Google Fonts. No action needed. |
| No native app — responsive web only | Confirmed: this phase is a web app. |
| OpenStreetMap tiles (free, no API key) | TileLayer URL: `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png` — no key required. |
| Single-user, no auth required | No auth guards, no login flow in this phase. |

**Stack version note:** CLAUDE.md specifies floor versions. STATE.md records that Phase 1 already installed newer versions (React 19, Vite 8, Tailwind v4, React Router 7). All Phase 4 work must use the installed versions, not the CLAUDE.md floor versions.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified by node_modules scan with exact versions
- Architecture: HIGH — UI-SPEC Component Inventory is prescriptive; API contract confirmed in backend source
- Pitfalls: HIGH — Leaflet/Vite interaction issues are well-documented; TanStack v5 breaking changes verified against installed version
- Test architecture: MEDIUM — Vitest is the correct choice for Vite projects but is not yet installed; setup details are standard but unverified in this specific project

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (30 days — React-Leaflet and TanStack Query are stable)
