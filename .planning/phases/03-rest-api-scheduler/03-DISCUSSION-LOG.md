# Phase 3: REST API + Scheduler - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-02
**Phase:** 03-rest-api-scheduler
**Areas discussed:** Scheduler first run, Health data storage, API default visibility, Neighborhood filter

---

## Scheduler First Run

| Option | Description | Selected |
|--------|-------------|----------|
| Run immediately on startup | Scrape fires as soon as the backend process starts — fresh data always available after a restart | ✓ |
| Wait for the first interval | First run happens 2 hours after startup — simpler config but empty map on cold start | |

**User's choice:** Run immediately on startup
**Notes:** User confirmed the recommended default — avoid the 2-hour cold-start wait.

---

## Health Data Storage

| Option | Description | Selected |
|--------|-------------|----------|
| In-memory dict | Module-level dict updated after each run — fast, zero extra code, lost on restart | ✓ |
| Dedicated DB table | scraper_runs table survives restarts, gives run history — more schema work | |
| Query listings table | Derive health from MAX(created_at) per source — no extra storage, doesn't track failures | |

**User's choice:** In-memory dict
**Notes:** Simplicity wins here; health data loss on restart is acceptable for a personal app.

---

## API Default Visibility

| Option | Description | Selected |
|--------|-------------|----------|
| All active listings | is_active=True, no exclusion of seen — frontend handles visibility | ✓ |
| Active + not seen | Excludes seen=true by default — matches morning-view use case | |

**User's choice:** All active listings

| Option | Description | Selected |
|--------|-------------|----------|
| Exclude low-confidence by default | llm_confidence < threshold listings hidden from frontend | ✓ |
| Include with field | All listings returned, llm_confidence visible — frontend decides | |

**User's choice:** Exclude by default
**Notes:** Verified listings only in the default view; flagged listings remain in DB for potential admin use later.

---

## Neighborhood Filter

| Option | Description | Selected |
|--------|-------------|----------|
| Text match now | Filter address column containing כרמל / מרכז העיר / נווה שאנן — works with Yad2 data today | ✓ |
| Skip until Phase 5 | Accept the param but ignore it until geocoding is available | |

**User's choice:** Text match now
**Notes:** Phase 5 will replace this with coordinate-based matching once Nominatim geocoding is added.

---

## Claude's Discretion

- Query param naming conventions
- Pagination design
- Whether to add a `neighborhood` column or derive at query time
- APScheduler job config details (coalesce, misfire grace)
- In-memory health dict structure

## Deferred Ideas

None.
