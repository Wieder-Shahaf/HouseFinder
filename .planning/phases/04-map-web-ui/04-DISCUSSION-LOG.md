# Phase 4: Map Web UI - Discussion Log

**Date:** 2026-04-02
**Phase:** 4 — Map Web UI

---

## Areas Selected

All four gray areas discussed: Pin → card interaction, Filter panel UX, Favorites view, New listing visual treatment.

---

## Area 1: Pin → Card Interaction

**Q: When a pin is tapped, how should the listing card appear?**
Options: Bottom sheet / Leaflet popup / Full-screen modal
**Selected:** Bottom sheet (card slides up from bottom, map stays visible behind)

**Q: Can the bottom sheet be expanded, or is it fixed height?**
Options: Fixed height / Two-height peek + expanded
**Selected:** Fixed height, all info visible

**Q: Tapping the map background — what happens?**
Options: Sheet dismisses / Sheet stays with X button
**Selected:** Sheet dismisses

---

## Area 2: Filter Panel UX

**Q: Where does the filter panel live on mobile?**
Options: Bottom sheet/drawer / Sticky top bar
**Selected:** Bottom sheet/drawer (filter button opens it)

**Q: How do filters apply?**
Options: Live / instant / Apply button
**Selected:** Live / instant

**Q: "New only" toggle — simple on/off (24h) or 24h/48h picker?**
Options: Simple on/off 24h hardcoded / Toggle with 24h/48h picker
**Selected:** Simple on/off toggle, 24h hardcoded

---

## Area 3: Favorites View

**Q: Where does the favorites list live?**
Options: Separate /favorites route / Filtered map view / Slide-out side panel
**Selected:** Separate /favorites route (dedicated page, vertical card list)

**Q: How do you get to /favorites? Navigation pattern?**
Options: Bottom navigation bar / Top-right heart icon
**Selected:** Bottom navigation bar (🗺 Map | ♥ Favorites)

---

## Area 4: New Listing Visual Treatment

**Q: How should new/unseen listings be visually distinguished?**
Options: Bold pin color + seen fade / "New" badge on pins / Just faded seen pin
**Selected:** Bold pin color + subtle seen fade
- Unseen: 🟦 Blue pin (default)
- Seen: ◦ Faded/grey pin
- Favorited: ❤️ Red/heart pin

**Q: App data refresh — when should listings reload?**
Options: On focus + 5min interval / Manual refresh only / Every 1 minute
**Selected:** On focus + 5min interval (TanStack Query)

---

*Log generated: 2026-04-02*
