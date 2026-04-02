# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## yad2-scraper-404-and-stealth-import — Yad2 scraper: 404 on httpx, stealth import crash, CAPTCHA, wrong URL params, wrong HTML parser, missing .env, LLM errors counted as rejections
- **Date:** 2026-04-02
- **Error patterns:** 404, stealth_async, cannot import name, networkidle, timeout, captcha, ShieldSquare, __NEXT_DATA__, LLM_API_KEY, Could not resolve authentication, listings_rejected, listings_found=0
- **Root cause:** Eight independent bugs: (1) config.py had unverified hypothesis URL path `/feed-search/realestate/rent` returning 404; (2) yad2.py imported `stealth_async` which does not exist in playwright_stealth 2.x API; (3) Playwright used `wait_until=networkidle` which never fires on Yad2 SPA; (4) Playwright fallback URL used wrong query params; (5) headless=True triggers Yad2 Radware ShieldSquare bot detection returning CAPTCHA page; (6) HTML parser used CSS card selectors but Yad2 embeds all data in `__NEXT_DATA__` JSON blob; (7) backend/.env missing so LLM_API_KEY defaulted to empty string causing Anthropic auth error; (8) LLM call failures were counted as content rejections, preventing any insertions.
- **Fix:** (1) URL → `/feed/realestate/rent`; (2) stealth → `Stealth().apply_stealth_async(page)`; (3) `wait_until="load"` timeout=60000; (4) fallback URL updated to match real browser URL with area/maxPrice/minRooms params; (5) headless=False + persistent browser profile + 90s wait for manual CAPTCHA solve; (6) `_flatten_nextdata_item()` reads `props.pageProps.feed.*` arrays from `__NEXT_DATA__`; (7) created `backend/.env` with `LLM_API_KEY` placeholder; (8) `rejection_reason` prefix `"LLM error:"` routes to flagged+insert(confidence=0.0) instead of rejected+skip.
- **Files changed:** backend/app/config.py, backend/app/scrapers/yad2.py, backend/.env
---
