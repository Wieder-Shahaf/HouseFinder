---
status: partial
phase: 02-yad2-scraper-llm-pipeline
source: [02-VERIFICATION.md]
started: 2026-04-02T00:00:00
updated: 2026-04-02T00:00:00
---

## Current Test

[awaiting human testing]

## Tests

### 1. Live Yad2 API scrape
expected: With a valid ANTHROPIC_API_KEY set, running `cd backend && python3 -c "import asyncio; from app.scrapers.yad2 import run_yad2_scraper; print(asyncio.run(run_yad2_scraper()))"` returns a ScraperResult with listings_found > 0 and listings_inserted > 0, all from Haifa target neighborhoods (כרמל, מרכז העיר, נווה שאנן) with price <= 4500
result: [pending]

### 2. LLM classification on real Hebrew text
expected: Claude Haiku correctly classifies genuine rental posts (is_rental=True) and rejects "מחפש דירה" / "דרוש שותף" posts (is_rental=False) on actual Yad2 Hebrew content
result: [pending]

### 3. Playwright fallback HTML selectors
expected: The secondary fallback path (`_parse_html_listings`) selectors at lines 91 and 103 of backend/app/scrapers/yad2.py match the live Yad2 DOM (only needed if httpx API returns 403)
result: [pending — low priority, only needed if primary path fails]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
