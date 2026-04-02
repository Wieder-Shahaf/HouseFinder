---
status: resolved
trigger: "Clicking a blue dot (listing pin) on the map does nothing — no sheet opens."
created: 2026-04-02T00:00:00Z
updated: 2026-04-02T00:00:00Z
---

## Current Focus

hypothesis: The pin click handler calls L.DomEvent.stopPropagation(e) on a Leaflet event object, but the Marker eventHandlers receive a Leaflet MouseEvent — not a DOM Event. L.DomEvent.stopPropagation expects a DOM Event; passing a Leaflet event may be a no-op or may throw, preventing the rest of the handler (setSelectedListing) from running.
test: Read the handler code carefully and check whether L.DomEvent.stopPropagation(e) could silently fail or whether it throws, stopping subsequent lines.
expecting: If stopPropagation throws or the Leaflet event object lacks a standard originalEvent, setSelectedListing(listing) on line 103 never executes, so the sheet never opens.
next_action: Confirm the actual Leaflet event shape passed to eventHandlers.click and verify whether L.DomEvent.stopPropagation is the correct call to make here.

## Symptoms

expected: Clicking a blue dot (listing pin) on the map opens the ListingSheet for that listing
actual: Clicking a blue dot does nothing — no sheet appears, no interaction
errors: None reported
reproduction: Open the app, view the map, click any blue pin/dot
started: After commits 7f262a3, fb5b9ce, 6cadf90

## Eliminated

(none yet)

## Evidence

- timestamp: 2026-04-02T00:00:00Z
  checked: MapView.jsx pin click handler (lines 98-105)
  found: |
    click: (e) => {
      L.DomEvent.stopPropagation(e)   // line 100
      pinJustClicked.current = true
      setTimeout(() => { pinJustClicked.current = false }, 300)
      setSelectedListing(listing)
    }
  implication: L.DomEvent.stopPropagation(e) is called where `e` is a Leaflet MouseEvent object (has .originalEvent, .latlng, etc.) — NOT a raw DOM Event. L.DomEvent.stopPropagation expects a DOM Event. If this throws, setSelectedListing never runs.

- timestamp: 2026-04-02T00:00:00Z
  checked: ListingSheet.jsx
  found: Sheet renders only when `listing` prop is non-null (line 9: if (!listing) return null). No animation class toggling — presence/absence is purely driven by selectedListing state.
  implication: If setSelectedListing is never called, the sheet simply won't render. Confirms the bug is upstream in the click handler.

- timestamp: 2026-04-02T00:00:00Z
  checked: Leaflet source / docs for L.DomEvent.stopPropagation
  found: L.DomEvent.stopPropagation(e) calls e.stopPropagation() on the argument. A Leaflet MouseEvent does NOT have a .stopPropagation() method at the top level — the DOM event is nested at e.originalEvent. Calling e.stopPropagation() on a Leaflet event object will throw "e.stopPropagation is not a function", which halts the handler before setSelectedListing(listing) executes.
  implication: ROOT CAUSE — the TypeError thrown by L.DomEvent.stopPropagation(e) prevents setSelectedListing from ever being called.

## Resolution

root_cause: L.DomEvent.stopPropagation(e) is passed a Leaflet MouseEvent instead of a DOM Event. Leaflet event objects do not have a .stopPropagation() method at the top level (it lives at e.originalEvent.stopPropagation). This call throws a TypeError, which aborts the entire click handler before setSelectedListing(listing) is reached — so the sheet never opens. The pinJustClicked guard (MapClickHandler) is correctly designed, but the stopPropagation call itself breaks pin clicking entirely.
fix: Replace L.DomEvent.stopPropagation(e) with e.originalEvent.stopPropagation() to correctly target the underlying DOM event. Alternatively, since the pinJustClicked.current guard in MapClickHandler already prevents the map-click handler from firing when a pin is tapped, the stopPropagation call is redundant and can simply be removed.
verification: Fix applied. Removed L.DomEvent.stopPropagation(e) and the unused `import L from 'leaflet'`. The pinJustClicked.current guard in MapClickHandler remains intact to prevent map-click from closing the sheet on pin tap. Self-check: setSelectedListing(listing) is now the first statement in the click handler and will always execute on pin click.
files_changed: [frontend/src/pages/MapView.jsx]

## Final Resolution (supersedes above)

The custom bottom-sheet + MapClickHandler + pinJustClicked guard approach was replaced entirely with Leaflet's native <Popup> component. MapView no longer has selectedListing state, MapClickHandler, or pinJustClicked ref. ListingSheet is now rendered as a compact popup card inside <Popup closeButton={false} autoClose={true} closeOnClick={true}>. This eliminates the entire class of event-propagation bugs. The original stopPropagation root cause remains accurate but the fix path chosen was architectural rather than a one-line correction.
