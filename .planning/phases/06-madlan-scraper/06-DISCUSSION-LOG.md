# Phase 6: Madlan Scraper — Discussion Log

**Date:** 2026-04-03
**Areas discussed:** Scraping approach, Scheduler coupling

---

## Area: Scraping Approach

**Q: How should the Madlan scraper approach the data source?**
Options: httpx-first → Playwright fallback / Playwright-first skip httpx / Researcher discretion
**Selected:** Playwright-first, skip httpx
*Rationale: ROADMAP's low-confidence flag on Madlan's API shape justifies bypassing httpx discovery entirely.*

**Q: Any constraints on how Playwright should scrape Madlan?**
Options: Same as Yad2 (stealth + proxy if enabled) / Stealth only no proxy / You decide
**Selected:** Same as Yad2 — stealth + proxy if enabled
*Rationale: Reuse existing proxy.py infrastructure, keep approach consistent.*

---

## Area: Scheduler Coupling

**Q: How should Madlan integrate into the APScheduler setup?**
Options: Separate independent job / Chained in one job
**Selected:** Separate independent job
*Preview selected: run_yad2_scrape_job() → yad2 scrape → geocode → dedup / run_madlan_scrape_job() → madlan scrape → geocode → dedup*
*Rationale: A Madlan hang or crash must not delay Yad2's geocode/dedup chain. Cleaner failure isolation.*

**Q: Should Madlan run on the same interval as Yad2, or a different interval?**
Options: Same interval as Yad2 / Separate configurable interval / You decide
**Selected:** Same interval as Yad2 (scrape_interval_hours)
*Rationale: One config knob, no added complexity.*

---

*Log generated: 2026-04-03*
