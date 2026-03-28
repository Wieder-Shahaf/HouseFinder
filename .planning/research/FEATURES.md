# Feature Landscape

**Domain:** Personal apartment listing aggregator — Israeli market (Haifa), single user, scraping-based
**Researched:** 2026-03-28
**Confidence note:** WebSearch unavailable. Findings based on training knowledge of Yad2/Madlan UX, real estate aggregator patterns, Facebook scraping conventions, and WhatsApp notification tooling. Confidence levels reflect source quality.

---

## Table Stakes

Features without which the app fails its core value proposition: "open the app each morning and see all new listings without manually searching anywhere."

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Periodic background scraping (Yad2, Madlan) | Without it there are no listings — the app IS the scraper | High | Yad2 and Madlan have structured HTML/JSON; anti-scraping measures exist but are circumventable with proper rate limiting and headers. HIGH confidence this is feasible. |
| Facebook group/Marketplace scraping | Facebook groups are a primary Israeli rental channel, especially for landlord-direct listings | High | Facebook actively blocks scraping. Requires either unofficial API (e.g., Apify Facebook scrapers), Playwright with login session cookies, or public group RSS workarounds. This is the hardest scraping target. |
| Listing storage with deduplication | The same apartment gets posted on multiple platforms; without dedup the user sees 3-5 copies of every listing | Medium | Dedup logic: normalize address + price + room count into a canonical fingerprint. Fuzzy match on description text as secondary signal. |
| Interactive map view (all listings as pins) | Map is the primary navigation surface — it answers "where is this relative to where I want to live?" | Medium | Mapbox GL JS or Leaflet.js with OpenStreetMap tiles. Pins must be clustered at zoom-out. Geocoding required for listings that have only a neighborhood name (not a full address). |
| Default filter applied on load | Rent ≤ 4,500 ₪, 2.5–3.5+ rooms — without this, irrelevant listings dominate | Low | Filters must persist across sessions (localStorage or DB-backed user state). |
| Listing card with key data | Price, rooms, size (sqm), contact info, post date, source — without this the user has to click through to the source | Low | Card must show WhatsApp/phone CTA directly. Contact info extraction from scraped text requires regex parsing (Hebrew phone numbers: 05X-XXXXXXX format). |
| "Seen" marking | Declutters the map — prevents re-reviewing listings already dismissed | Low | Toggle on pin or card. Seen pins visually muted or hidden (filter toggle). |
| Favorites / bookmarking | Allows returning to shortlisted listings | Low | Simple boolean flag per listing. Favorites view separate from map or overlaid with distinct pin color. |
| WhatsApp notification on new listing | Core value: user is notified without opening the app | Medium | Twilio WhatsApp API (sandbox → production requires Meta approval) or CallMeBot (free, no approval needed for personal use). New listing = passes current active filters and was not seen before. |
| Mobile-responsive UI | Primary usage context is a smartphone browser in the morning | Medium | CSS RTL layout, touch-friendly pin tap targets (min 44px), bottom navigation bar pattern for mobile. |
| Hebrew UI with RTL layout | All content is in Hebrew; English UI on Hebrew content is jarring | Medium | `dir="rtl"` on root, RTL-aware CSS (logical properties: `margin-inline-start` instead of `margin-left`), RTL font stack (system-ui covers Hebrew on all major platforms). |
| Haifa neighborhood filter | Carmel, Downtown (Merkaz), Neve Shanan are distinct sub-markets | Low | Bounding box or polygon filter applied during scrape or at display. Requires geocoding scraped listings to neighborhoods. |

---

## Differentiators

Features that go beyond survival — they make the tool meaningfully better than manually searching Yad2 each morning.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Source badge on listing card | Tells the user whether the listing is agent-posted (Yad2/Madlan) or landlord-direct (Facebook) — landlord-direct means no agency fee | Low | Simple label: "יד2", "מדלן", "פייסבוק". Confidence: HIGH — trivially derivable from scrape source. |
| "New today" visual distinction | Listings added in the last N hours get a highlighted pin color or "חדש" badge | Low | Time-based flag. Reinforces the morning review habit. |
| Listing age indicator | "פורסם לפני 3 שעות" — freshness signal that helps prioritize | Low | Derivable from scraped post timestamp vs. current time. |
| Price-per-sqm display | Normalized metric for comparing listings of different sizes | Low | Only applicable when both price and size are available. Many Israeli listings omit size — handle gracefully. |
| Duplicate source links | "Also on Yad2 / Madlan" link on a deduplicated card | Medium | Requires storing all source URLs per dedup cluster, not just one. |
| Scrape status dashboard | When did each source last run? How many listings found? Any errors? | Low | Single admin page. Makes debugging scraper failures visible without checking logs. |
| Manual listing add | Paste a URL or fill in a form to add a listing found outside the scraper | Low | Useful when a friend shares a listing. No scraper dependency needed. |
| Filter by floor (קומה) | High-floor preference is common in Haifa due to views and noise | Low | Only applicable when floor data is available in scraped content. |
| Listing notes field | Free-text note on a favorite ("visited, noisy street") | Low | Stored per listing in DB. Useful during active apartment search. |
| Contact history log | Track which listings were contacted and when | Medium | Prevents re-contacting, tracks follow-up. Simple timestamp + status field. |
| Neighborhood heatmap | Visual density of available listings by neighborhood | Medium | Derived from geocoded listings. Useful for understanding supply distribution. |
| Smart dedup confidence score | Show "95% likely duplicate" vs. "confirmed same" on the dedup cluster | High | Nice to have for debugging, not needed for daily use. |

---

## Anti-Features

Features to deliberately NOT build for a personal single-user app. Building these wastes time and adds maintenance burden.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| User authentication / login | Single user — auth adds complexity (password reset, session management, JWT) with zero benefit | Protect the URL with a long random path segment or HTTP Basic Auth via nginx/Caddy. Or simply keep it on localhost with Tailscale for remote access. |
| Multi-user support | Out of scope per PROJECT.md; requires RBAC, tenant isolation, shared-state complexity | Single user state in DB with no user FK. Adding users later is a migration, not a bloat. |
| Listing agent CRM | Contact management, lead tracking, deal stages — this is a $500/month SaaS product, not a morning briefing tool | A simple "contacted" boolean flag is sufficient. |
| Search ranking / relevance scoring | ML-based relevance or collaborative filtering requires training data and ongoing maintenance | Simple chronological sort + user-defined filters is better for personal use. |
| Saved search alerts for multiple saved searches | One user, one target market — over-engineering for a single search profile | One set of filters, one notification threshold. |
| Native mobile app (iOS/Android) | Responsive web is sufficient, adds App Store/Play Store maintenance | PWA with `manifest.json` gives "add to home screen" on iOS/Android for near-native feel. |
| Price history charts | Requires longitudinal data across months; Israeli rental prices don't change frequently enough to matter for a short search window | Show current price only. |
| Automated contact / messaging | Sending automated WhatsApp/SMS to landlords is spam, legally risky, and ruins rapport | Show contact info; user reaches out manually. |
| In-app scheduling / calendar | Out of scope for this product entirely | External calendar (Google Calendar) is the right tool. |
| Social / sharing features | No other users to share with | Not applicable. |
| Server-side rendering optimization for SEO | Not a public product; SEO is irrelevant | Client-side rendering or simple SSR for functionality, not discoverability. |

---

## Feature Dependencies

```
Scraping pipeline (Yad2 + Madlan)
  → Listing storage
    → Deduplication logic
      → Map display (requires geocoded coordinates per listing)
        → Seen/favorites tracking (requires listing identity)
          → WhatsApp notification (requires "new, unseen, passes filters" logic)

Facebook scraping
  → Same pipeline as above (store → dedup → map)
  NOTE: Facebook scraping is independent; app works without it
  but loses landlord-direct listings

Geocoding
  → Map pin placement (blocking: pins cannot render without lat/lng)
  → Neighborhood filter (blocking: filter cannot apply without geocoded neighborhood)
  → Price-per-sqm and floor display are NOT blocked by geocoding

Default filters (price ≤ 4,500 ₪, rooms 2.5–3.5+)
  → WhatsApp notification (notification must respect active filters)
  → Map display (filter applied before rendering pins)

RTL layout
  → All UI components (pervasive, not a feature toggle — must be baked in from day one)
```

---

## MVP Recommendation

Prioritize this core loop: scrape → store → deduplicate → display on map → notify.

**Build first (Phase 1–2):**
1. Yad2 + Madlan scrapers (structured sources, lower anti-scraping risk than Facebook)
2. Listing storage with deduplication fingerprinting
3. Geocoding pipeline (address → lat/lng → neighborhood)
4. Map view with pins, listing card on tap, default filters applied
5. Seen marking (the single most important daily-use feature)

**Build second (Phase 3):**
6. Favorites / bookmarking
7. WhatsApp notification (Twilio or CallMeBot)
8. Hebrew RTL UI polish
9. Scraper status dashboard (makes debugging possible)

**Build third (Phase 4, if needed):**
10. Facebook group scraping (highest complexity, highest risk of breakage)
11. Facebook Marketplace scraping

**Defer indefinitely:**
- Source deduplication confidence score (debugging only, not user-facing)
- Neighborhood heatmap
- Contact history log
- Manual listing add

**Never build (anti-features above):** Auth, multi-user, CRM, native app, automated messaging.

---

## Hebrew / RTL Specific Considerations

**HIGH confidence** — these are known requirements for Israeli web products:

- **Font stack:** System fonts cover Hebrew on all platforms. `font-family: system-ui, -apple-system, Arial, sans-serif` works. No custom Hebrew font needed for v1.
- **RTL direction:** Set `dir="rtl"` on `<html>` element, not per-component. All CSS layout must be tested RTL — Flexbox and Grid handle RTL correctly when `dir` is set; floats and absolute positioning do not.
- **Number formatting:** Israeli phone numbers (05X-XXXXXXX), prices in ₪ (ILS), and dates in DD/MM/YYYY format. Use `Intl.NumberFormat('he-IL', { style: 'currency', currency: 'ILS' })` for prices.
- **Map labels:** Mapbox and Leaflet both support Hebrew labels in OpenStreetMap tiles — no special configuration needed.
- **Scraped content:** All listing descriptions are in Hebrew. Text truncation on listing cards must handle Hebrew correctly — CSS `text-overflow: ellipsis` works regardless of script direction when `dir="rtl"` is set.
- **Rooms notation:** Israeli listings use "חדרים" with values like 2.5, 3, 3.5, 4. The 0.5 increments are standard and must be supported in filter UI (range slider or stepper).
- **WhatsApp:** WhatsApp is the dominant messaging platform in Israel. Twilio's WhatsApp API sends Hebrew text correctly (UTF-8). Message templates submitted to Meta for approval must be in Hebrew if user-facing text is Hebrew.

---

## Scraping Pipeline Feature Details

| Feature | Complexity | Key Challenge |
|---------|------------|---------------|
| Yad2 scraper | Medium | Yad2 has structured listing pages with JSON-LD or meta tags. Rate limit: 1 req/2–3 sec recommended. Occasional Cloudflare protection. |
| Madlan scraper | Medium | Madlan's frontend is React SPA — listing data comes from a GraphQL or REST API that can be reverse-engineered from network tab. More stable than Yad2's HTML structure. |
| Facebook group scraper | High | Requires authenticated session (login cookies via Playwright). Groups may be private. Post structure is not stable. High breakage risk. Consider Apify's Facebook scraper actor as an alternative to custom code. |
| Facebook Marketplace scraper | High | Similar to groups. Marketplace listings are location-based; Haifa filter must be applied. Playwright + login is the standard approach. |
| Geocoding | Medium | Yad2/Madlan listings often have an address string but not coordinates. Use Google Maps Geocoding API (paid, ~0.005 USD/request) or Nominatim (free, rate-limited to 1 req/sec). For a personal app at low volume, Nominatim is sufficient. |
| Deduplication | Medium | Canonical key: normalize(address) + price + room_count. Secondary: fuzzy match on description text (Levenshtein distance or Jaccard similarity). Flag as probable duplicate if primary key matches; confirmed duplicate if secondary also matches. |
| Scrape scheduling | Low | Cron job or node-cron inside the app process. Every 1–3 hours is sufficient. No distributed job queue needed for single-user scale. |

---

## Notification Feature Details

| Option | Complexity | Pros | Cons |
|--------|------------|------|------|
| CallMeBot WhatsApp | Low | Free, no Meta approval needed, personal use only, simple HTTP GET | Requires one-time setup via chat, limited reliability, rate-limited |
| Twilio WhatsApp API | Medium | Reliable, delivery receipts, programmatic | Sandbox only until Meta approves; approval requires template submission; cost ~$0.005/message |
| Web Push (browser notification) | Low | No third-party dependency, works on Android Chrome | Does not work reliably on iOS Safari (added in iOS 16.4, still requires user opt-in); requires PWA service worker |
| Telegram Bot | Low | Free, reliable, no approval process, supports Hebrew | User must use Telegram — project spec says WhatsApp |

**Recommendation:** Start with CallMeBot for MVP (zero setup friction). Migrate to Twilio if reliability becomes an issue. Web Push as optional second channel.

---

## Sources

- PROJECT.md: product requirements and constraints
- Training knowledge: Yad2/Madlan platform structure (HIGH confidence for major features, MEDIUM for anti-scraping specifics)
- Training knowledge: Facebook scraping approaches (MEDIUM confidence — Facebook changes frequently)
- Training knowledge: Israeli real estate UX conventions (HIGH confidence)
- Training knowledge: WhatsApp API options (HIGH confidence for Twilio; MEDIUM for CallMeBot current status)
- Training knowledge: RTL web development patterns (HIGH confidence)
- NOTE: WebSearch was unavailable during this research pass. Scraper-specific details (rate limits, API endpoints, anti-bot measures) should be validated with current documentation before implementation.
