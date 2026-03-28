# Domain Pitfalls

**Domain:** Apartment listing aggregator — web scraping, Israeli real estate platforms, Hebrew RTL UI
**Project:** ApartmentFinder (Haifa, Israel)
**Researched:** 2026-03-28
**Confidence note:** WebSearch unavailable. Findings drawn from training knowledge (cutoff August 2025) on scraping anti-patterns, Israeli platform specifics, RTL rendering, and WhatsApp API. Confidence levels reflect source quality.

---

## Critical Pitfalls

Mistakes that cause rewrites, legal exposure, or complete data loss.

---

### Pitfall 1: Facebook Login State Expiry Silently Kills Scraping

**What goes wrong:** You authenticate Playwright/Puppeteer with a real Facebook account and save the session cookie. Weeks later, Facebook silently invalidates the session (due to inactivity, suspicious geo, or cookie rotation). Your scraper stops returning listings — but it doesn't throw an error. It lands on a login redirect page and scrapes zero results. Your app shows no new listings, and you assume there are simply no listings.

**Why it happens:** Facebook uses short-lived session tokens combined with device fingerprinting. A headless browser running on a server has a different fingerprint from your phone. Any deviation (IP change, missing canvas fingerprint, timing anomaly) triggers soft-blocking or session termination.

**Consequences:**
- Silent data gaps. You don't know the scraper failed.
- Risk of account suspension if Facebook detects automated login.
- If your personal Facebook account is used, it may be banned permanently.

**Prevention:**
- Add a sentinel check after every scrape run: if the page title or URL contains "login", "checkpoint", or "מחדש" (Hebrew login prompts), emit an alert immediately.
- Never use your primary personal Facebook account for scraping. Use a dedicated secondary account with a consistent session profile.
- Persist cookies and rotate IP minimally — changing IP mid-session is a red flag.
- Store the last-successful-scrape timestamp. If it's more than 2× the scrape interval, trigger a notification.

**Detection (warning signs):**
- Zero new listings for >4 hours during daytime
- Scrape job completes suspiciously fast (sub-2 seconds — it's hitting a login wall, not loading content)
- HTTP 302 redirects to `/login` in Playwright network logs

**Phase:** Scraping foundation phase. Must be built into the scraper health-check layer from day one.

---

### Pitfall 2: Facebook Groups Require Login — Public Group Assumption is Wrong

**What goes wrong:** You assume Facebook apartment groups in Israel are public and accessible without authentication, so you build a session-free scraper. In practice, nearly all Israeli apartment rental groups on Facebook are closed groups requiring membership. Even "public" groups in Israel often load a feed-blocker after a few scrolls without login.

**Why it happens:** Facebook has progressively locked down group access since 2019. The GraphQL API that powered unauthenticated group access is fully deprecated. What appears as a "public" group in browser often loads initial posts but blocks continued scrolling without login.

**Consequences:**
- You build and test a scraper locally while logged in via browser cookies, not realizing the session is what's making it work. Deployment to a server (no browser session) silently fails.
- Entire Facebook Groups scraping layer fails on first server deployment.

**Prevention:**
- Test scraping explicitly in a fresh incognito profile with no cookies before shipping.
- Design the authentication layer (session cookie injection) as a first-class concern, not an afterthought.
- Budget time for Facebook Marketplace separately — it has a different auth flow from Groups.

**Detection:**
- Scraper returns HTML that contains "התחבר לפייסבוק" or "Log in to Facebook" in the page source.

**Phase:** Architecture/scraping design phase. Decision to use session-based scraping must be made before writing any Facebook scraper code.

---

### Pitfall 3: Yad2 and Madlan Bot Detection via TLS Fingerprinting

**What goes wrong:** You use `requests` (Python) or `fetch` (Node.js) with a spoofed User-Agent header, assuming that's enough to bypass bot detection. Yad2 and Madlan both use Cloudflare or similar TLS fingerprinting (JA3 fingerprint checking). A standard `requests` TLS handshake has a different JA3 fingerprint than a real browser, causing immediate 403 or a Cloudflare challenge page — even before any rate limiting kicks in.

**Why it happens:** Modern Israeli real estate sites have invested heavily in anti-scraping. Yad2 in particular is well-known in the Israeli developer community for aggressive bot detection. Simply spoofing User-Agent is a 2015-era technique that has been ineffective for years.

**Consequences:**
- Your scraper gets 403s from the first request, with no path forward without a full browser engine.
- Switching from `requests` to Playwright mid-project is a significant rewrite.

**Prevention:**
- Use a full headless browser (Playwright with Chromium) for both Yad2 and Madlan from the start. Never attempt simple HTTP scraping for these sites.
- Use `playwright-stealth` or equivalent to patch headless browser detection signals (navigator.webdriver, chrome runtime, etc.).
- Add random delays between 2–8 seconds between requests. Robotic sub-second request cadence is a primary detection signal.

**Detection:**
- Cloudflare challenge pages in response body (look for "Just a moment..." or "Checking your browser" in scraped HTML).
- HTTP 403 or 503 responses.
- Response body is a JavaScript challenge page (no actual listing content).

**Phase:** Scraping foundation. Architecture decision to use Playwright must precede Yad2/Madlan scrapers.

---

### Pitfall 4: Facebook Marketplace Geo-Restriction and Login Wall

**What goes wrong:** Facebook Marketplace listings in Haifa are served only to users whose account location matches or is near Haifa. A scraper account registered with a Tel Aviv or foreign location won't see Haifa Marketplace listings. Additionally, Marketplace requires login and often requires the account to have some activity history (age, friends, prior Marketplace use).

**Why it happens:** Marketplace is geo-personalized by design. Facebook serves listings based on the account's declared location and IP address.

**Consequences:**
- A fresh scraper account returns zero Marketplace listings even when listings exist.
- You waste time debugging the scraper when the problem is account configuration.

**Prevention:**
- Configure the dedicated scraper Facebook account with Haifa as home city.
- Ensure the server IP is in Israel (use an Israeli VPS or VPN endpoint for scraping). A server in Frankfurt or Dublin will suppress Israeli Marketplace results.
- Age the account slightly (create it a few weeks before the project, add a profile photo, set location) before using it for scraping.

**Detection:**
- Marketplace returns results but they're all from wrong cities.
- Marketplace returns 0 results while Haifa listings are visibly available in a real browser session.

**Phase:** Infrastructure planning phase. Server location and scraper account setup must be decided before deployment.

---

### Pitfall 5: Deduplication Fails on Address Variation

**What goes wrong:** The same apartment listing is posted on Yad2, in two Facebook groups, and on Madlan — three separate records in your database. Your deduplication logic does exact-string matching on address, so "רחוב הנביאים 14, חיפה" and "הנביאים 14 חיפה" and "נביאים 14" are treated as three different apartments. The map fills with triplicate pins.

**Why it happens:** Hebrew address strings are highly variable. Street name prefixes ("רחוב", "שדרות", "דרך") are sometimes included, sometimes not. Apartment numbers appear after a slash, a comma, or not at all. The same neighborhood is spelled multiple ways.

**Consequences:**
- Map becomes cluttered with duplicates, defeating the core value proposition.
- User marks one pin as "seen" but the duplicate remains.
- Price comparison across sources becomes impossible.

**Prevention:**
- Build a normalization pipeline: strip common prefixes (רחוב, שדרות, ד"ר), normalize spacing, extract numeric components (street number, apartment number) separately.
- Use fuzzy matching (Levenshtein distance or similar) on the normalized address + price combination. An identical price AND near-identical address (normalized) is a very strong duplicate signal.
- Consider geolocation as the primary dedup key: geocode the address to lat/lng (within ~50m radius), then group by proximity + price + room count.
- Do NOT deduplicate on listing text alone — different agents post the same apartment with completely different descriptions.

**Detection:**
- QA the map after first full scrape run and manually check if known popular apartments appear multiple times.

**Phase:** Data modeling phase. The deduplication schema must be designed before scraping begins, not patched in afterward.

---

### Pitfall 6: WhatsApp Business API Requires Pre-Approval and Has 24-Hour Window Restrictions

**What goes wrong:** You plan to use Twilio WhatsApp API for notifications. You assume you can send free-form messages to yourself at any time. In practice, WhatsApp Business API (including Twilio's implementation) enforces: (a) a 24-hour session window — you can only send arbitrary messages within 24 hours of the user sending you a message, and (b) outside that window, you can only send pre-approved "template messages." Template approval takes days to weeks.

**Why it happens:** This is a core WhatsApp Business Platform policy, not a Twilio limitation. It applies to all BSPs (Business Solution Providers).

**Consequences:**
- Your notification system breaks for any run more than 24 hours after you last messaged the bot.
- You either wait for template approval (blocking development) or you find the notification feature doesn't work in production.

**Prevention:**
- Use a pre-approved notification template for the primary alert (e.g., "{{count}} new listings found in Haifa. Open app: {{url}}"). Submit this template for approval during early infrastructure setup, not at the end.
- Alternatively, use Twilio's WhatsApp Sandbox for development (no template requirement) with a clear understanding it's dev-only.
- Consider a fallback: push notifications via the web app (Web Push API / PWA) are simpler, require no approval, and work immediately. Build push notifications as primary; WhatsApp as secondary.

**Detection:**
- "Outside of the 24-hour customer service window" error from Twilio API.
- Template messages rejected during approval review.

**Phase:** Notifications phase. Template submission must happen at project start as a long-lead item.

---

## Moderate Pitfalls

---

### Pitfall 7: Hebrew Text Encoding Corruption in Database and Logs

**What goes wrong:** Hebrew characters appear as "×©×›×™×¨×•×ª" or similar mojibake in the database or application logs. This typically happens when the database connection is not explicitly set to UTF-8, or when log files are written without encoding specification.

**Prevention:**
- Set `charset=utf8mb4` on all MySQL/MariaDB connections explicitly (utf8 in MySQL is actually a 3-byte subset; only utf8mb4 handles all Unicode).
- If using PostgreSQL, UTF-8 is the default but confirm with `SHOW SERVER_ENCODING`.
- Use `Content-Type: text/html; charset=UTF-8` headers on all API responses.
- Test Hebrew text round-trip (store→retrieve→display) before building any scraper.

**Phase:** Database setup phase.

---

### Pitfall 8: RTL Layout Breaks with Mixed Hebrew/Latin Content

**What goes wrong:** A listing contains "3 rooms, ₪4,200/month" — a mix of Hebrew and Latin characters plus numbers. The browser's Unicode Bidi algorithm applies automatic direction, which often produces garbled ordering: numbers appear on the wrong side, price and room count get reversed, phone numbers display backwards.

**Why it happens:** CSS `direction: rtl` sets the default paragraph direction but doesn't fully control inline bidi rendering of mixed-direction runs. Numbers in RTL context are treated as weak directionality and can flip unexpectedly.

**Prevention:**
- Wrap all listing card fields individually with `dir="rtl"` rather than relying on a single parent container.
- Use CSS `unicode-bidi: isolate` on inline numeric elements (price, phone number) to prevent bidi contamination.
- Phone numbers should be wrapped in `<bdi>` tags or `direction: ltr` spans — Israeli phone numbers (05X-XXX-XXXX) must display left-to-right.
- Test every listing card component with real Hebrew data containing numbers and Latin strings from day one.

**Detection:**
- Phone number appears as "XXXX-XXX-X50" instead of "050-XXX-XXXX".
- Price displays as "₪ 200,4" instead of "4,200 ₪".
- Any listing card with mixed content looks correct in English browser mode but breaks in RTL mode.

**Phase:** UI components phase.

---

### Pitfall 9: Map Pin Performance Degrades with >200 Listings

**What goes wrong:** Leaflet.js or Google Maps renders each listing as a DOM element. With 300+ pins (realistic after a week of scraping), the map becomes sluggish on mobile, especially on mid-range Android phones. Panning triggers noticeable lag; opening the app on mobile feels broken.

**Why it happens:** Each Leaflet marker is a separate DOM node. 300 DOM nodes with event listeners is manageable on desktop but kills mobile rendering performance.

**Prevention:**
- Use marker clustering from day one (`leaflet.markercluster` plugin). Clusters collapse nearby pins into count badges, reducing DOM nodes to <30 at typical zoom levels.
- Implement viewport-based rendering: only render pins currently in the visible map bounds. Remove pins that pan out of view.
- Apply "seen" filter by default: only show unseen listings on initial load. This keeps the pin count naturally low.

**Detection:**
- Load the map with 200+ synthetic pins on an actual mobile device (not Chrome DevTools emulation) before shipping.

**Phase:** Map implementation phase. Clustering must be built in, not added as a performance fix later.

---

### Pitfall 10: Scraper Runs Overlap and Corrupt State

**What goes wrong:** You set a cron job to run every hour. One scrape run takes 90 minutes (due to slow page loads, bot-delay waits, network retries). The next cron job fires while the first is still running. Two concurrent scrape processes write to the database simultaneously, creating duplicate records and corrupting the "last scraped" timestamp.

**Prevention:**
- Use a job lock: write a "scrape_in_progress" flag to the database (or a lockfile) at the start of each run; check it before starting a new run.
- Log scrape run duration. If any run exceeds 80% of the interval (e.g., 48 minutes on a 60-minute interval), trigger an alert to widen the interval.
- Set a hard timeout on each individual source scraper (e.g., 15 minutes max per source), so one stuck source doesn't block the entire run.

**Phase:** Scheduler/infrastructure phase.

---

### Pitfall 11: Geocoding Quota Exhaustion on Re-Scrape

**What goes wrong:** Every scrape run geocodes every listing address to get lat/lng for the map. You hit the Google Maps Geocoding API free tier (or Nominatim rate limit) after a few runs. Either your geocoding stops working silently (returns null coordinates) or you incur unexpected API costs.

**Prevention:**
- Geocode once per unique address and cache the result in the database. Never re-geocode an address you've already resolved.
- Use a fuzzy address match before geocoding: if the normalized address is within 80% string similarity of an already-geocoded address, reuse that coordinate.
- Consider using Nominatim (OpenStreetMap) with a 1-second rate limit between requests. It's free but slower. Good for Haifa-scale (hundreds of addresses, not millions).

**Phase:** Data pipeline phase.

---

### Pitfall 12: Madlan Requires JavaScript Rendering and Uses API Key in Frontend

**What goes wrong:** Madlan's listing data is loaded via internal API calls made by the browser's JavaScript, not in the initial HTML. A simple HTML scraper (even with Playwright but without waiting for network idle) returns a shell page with no listings. Additionally, Madlan's frontend makes authenticated API calls using a client-side API key embedded in JavaScript. Scraping these API calls directly may work initially but breaks whenever Madlan rotates the key.

**Prevention:**
- Always wait for `networkidle` in Playwright when scraping Madlan (wait until no network requests for 500ms). Never parse the initial DOM immediately after navigation.
- Do not reverse-engineer and directly call Madlan's internal API — scrape the rendered page content instead. Internal API changes will break your scraper; rendered HTML changes are more gradual.
- Build Madlan-specific CSS selectors as a separate, isolated module so they can be updated independently when the site changes.

**Phase:** Madlan scraper phase.

---

## Minor Pitfalls

---

### Pitfall 13: Listing Price Contains Non-Numeric Characters

**What goes wrong:** Scraped price strings come in as "4,500 ₪ לחודש", "~4500", "₪4.500", "4500-5000". Naive `parseInt()` or `parseFloat()` returns NaN for several of these formats. Filtering by max price (4,500 ₪) then silently includes or excludes listings incorrectly.

**Prevention:**
- Write a dedicated `parsePrice(str)` utility that: strips non-numeric non-separator characters, handles both `.` and `,` as thousands separators (Israeli convention uses comma), and extracts the lower bound for price ranges.
- Store raw price string alongside parsed integer in the database for debugging.

**Phase:** Data normalization phase.

---

### Pitfall 14: Room Count Uses Israeli Convention (2.5 Rooms != 2 Bedrooms)

**What goes wrong:** Israeli listings use "rooms" (חדרים), not "bedrooms." 2.5 rooms in Israeli convention means roughly 1 bedroom. A filter for "2.5–3.5 rooms" has a very different meaning than "2–3 bedrooms." If you build filters assuming bedroom counts, the entire filter system will be calibrated wrong for the user.

**Prevention:**
- Store and display values in Israeli room counts (חדרים) throughout. Never convert to bedroom counts.
- The filter UI should say "חדרים" not "bedrooms."
- Half-room values (2.5, 3.5) are common and expected — do not round them.

**Phase:** Data modeling and UI filter phase.

---

### Pitfall 15: Facebook Group Post Detection Misses Pinned/Admin Posts

**What goes wrong:** Facebook group pages often have pinned posts at the top (apartment agency listings, group rules). Your scraper processes these as new listings on every run, creating duplicate "new" notifications and database noise.

**Prevention:**
- Check for the pinned post indicator in the DOM before processing.
- Alternatively, always check if the listing's unique ID (Facebook post ID) already exists in the database before inserting — this is a required dedup check regardless.

**Phase:** Facebook scraper phase.

---

### Pitfall 16: Mobile Safari RTL Input Fields

**What goes wrong:** Filter input fields (price, room count) on iOS Safari in an RTL layout can render text cursor and placeholder text misaligned. The number input field shows the placeholder on the right but the typed text starts from the left — visually jarring and confusing.

**Prevention:**
- Explicitly set `direction: ltr` and `text-align: left` (or `right` with `ltr`) on number input fields. Numeric values should always be LTR even in an RTL UI.
- Test filter inputs on actual iPhone Safari, not just Chrome's mobile emulation.

**Phase:** UI/filter phase.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Project setup / infrastructure | Server location outside Israel → Marketplace geo-block (Pitfall 4) | Choose Israeli VPS from day one |
| Database schema design | Missing UTF-8mb4 → Hebrew mojibake (Pitfall 7); missing dedup fields → schema rewrite (Pitfall 5) | Design dedup + encoding before first migration |
| Facebook scraper | Session expiry silent failure (Pitfall 1); closed groups (Pitfall 2); pinned posts (Pitfall 15) | Build health-check sentinel in same phase |
| Yad2/Madlan scrapers | TLS fingerprint block (Pitfall 3); JS-rendering wait (Pitfall 12) | Playwright + stealth + networkidle from the start |
| Data normalization | Price parsing NaN (Pitfall 13); room count convention (Pitfall 14); address dedup failure (Pitfall 5) | Build normalization module with unit tests |
| Map implementation | Pin performance on mobile (Pitfall 9); geocoding quota (Pitfall 11) | Clustering + geocode cache mandatory |
| Notifications | WhatsApp 24hr window + template approval (Pitfall 6) | Submit template early; build Web Push as fallback |
| UI / RTL layout | Mixed bidi rendering (Pitfall 8); iOS Safari inputs (Pitfall 16) | Test with real Hebrew data + real iPhone from first component |
| Scheduler / cron | Overlapping scrape runs (Pitfall 10) | Add job lock before deploying first cron |

---

## Legal Considerations (Israel-Specific)

**Confidence: MEDIUM** — Based on known Israeli data protection law and ToS norms; not legal advice.

### Terms of Service Violations

Yad2 and Madlan explicitly prohibit automated scraping in their ToS. Facebook's ToS prohibits automated data collection. For a personal single-user tool, enforcement risk is low, but:
- Do not resell or republish scraped data.
- Do not scrape at aggressive intervals (sub-minute). 1–3 hour intervals are reasonable.
- Rate-limit between requests (2–8 second delays) to avoid denial-of-service impact.

### Israeli Privacy Law (PDPL — חוק הגנת הפרטיות)

Listings include personal contact details (phone numbers, sometimes names). Under Israeli PDPL:
- Storing personal data (phone numbers of private individuals) in a database is permissible for personal use but must not be shared or sold.
- The app is single-user and self-hosted, which minimizes exposure. Keep it that way.

### Recommendation

Build with respectful rate limits from day one. This is the correct engineering posture regardless of legal risk, because overly aggressive scraping will get the scraper blocked, which is worse than being polite.

---

## Sources

- Facebook Platform Policy and Graph API deprecation history (HIGH confidence — well-documented)
- WhatsApp Business Platform 24-hour session window policy (HIGH confidence — Twilio and Meta official documentation)
- Playwright stealth / headless browser detection (HIGH confidence — well-documented in Playwright community)
- Israeli real estate platform bot detection — Yad2/Madlan (MEDIUM confidence — known in Israeli developer community, no official source available)
- Leaflet.js marker clustering performance (HIGH confidence — leaflet.markercluster is the canonical solution)
- Israeli room count convention (HIGH confidence — standard Israeli real estate practice)
- Unicode Bidi algorithm and RTL rendering (HIGH confidence — W3C and MDN documentation)
- Israeli PDPL (MEDIUM confidence — law is public record; application to this specific case is assessment, not legal advice)
