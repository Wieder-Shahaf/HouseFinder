# ApartmentFinder

## What This Is

A personal mobile-first web app that automatically scrapes Facebook groups, Facebook Marketplace, Yad2, and Madlan for apartment rental listings in Haifa, Israel. All listings are aggregated into an interactive live map, deduplicated, and filterable — so the user can open the app each morning and see all new listings without manually searching anywhere. The app is in Hebrew with full RTL support.

## Core Value

New Haifa rental listings from all sources appear on a single live map every morning — no manual searching required.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Periodic background scraping of Facebook groups (user-defined list), Facebook Marketplace, Yad2, and Madlan
- [ ] Listings stored in a database and deduplicated across sources
- [ ] Interactive map showing all listings as pins, filtered to Haifa (Carmel, Downtown, Neve Shanan)
- [ ] Default filters: rent up to 4,500 ₪/month, 2.5–3.5+ rooms
- [ ] Listing card shows: price, rooms & size, contact info, post date, source
- [ ] Mark listings as "seen" (declutter map) and save favorites (bookmark to revisit)
- [ ] WhatsApp or push notification when a new listing is found
- [ ] Mobile-responsive web app accessible via public URL (no native app required)
- [ ] Full Hebrew UI with RTL layout

### Out of Scope

- Multi-user support — single user only, no auth system needed initially
- Native mobile app — responsive web is sufficient
- Listings outside Haifa area — not relevant to search
- Price negotiation or contact management — out of scope for v1

## Context

- All listing sources are in Hebrew; scraped content will be in Hebrew
- Facebook scraping requires handling login state or public group access
- Yad2 and Madlan are the dominant Israeli real estate classifieds platforms
- User will provide the specific Facebook group list during setup
- The app will be self-hosted or deployed to a cloud platform (needs a public URL)
- Periodic scraping interval: likely every 1–3 hours to catch fresh listings
- WhatsApp notifications: likely via Twilio WhatsApp API or similar

## Constraints

- **Language**: Full Hebrew/RTL support required throughout the UI
- **Accessibility**: Must be usable on a smartphone browser (no native app)
- **Data freshness**: Listings must reflect posts within a few hours
- **Legal**: Scraping must respect rate limits and ToS boundaries where possible
- **Scale**: Single-user — no need to optimize for high concurrency

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Web app not native app | Faster to build, cross-platform, user's requirement | — Pending |
| WhatsApp notifications | User's preferred channel | — Pending |
| Haifa only (specific neighborhoods) | Carmel, Downtown, Neve Shanan — user's target | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-28 after initialization*
