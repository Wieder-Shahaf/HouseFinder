---
phase: 1
slug: foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-01
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (backend) |
| **Config file** | `backend/pyproject.toml` or "none — Wave 0 installs" |
| **Quick run command** | `docker compose exec backend pytest tests/ -x -q` |
| **Full suite command** | `docker compose exec backend pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `docker compose exec backend pytest tests/ -x -q`
- **After every plan wave:** Run `docker compose exec backend pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | INFRA-01 | smoke | `docker compose config --quiet` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | INFRA-02 | smoke | `docker compose up --dry-run` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 1 | DATA-01 | unit | `docker compose exec backend pytest tests/test_schema.py -x -q` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 1 | DATA-02 | unit | `docker compose exec backend pytest tests/test_dedup.py -x -q` | ❌ W0 | ⬜ pending |
| 1-01-05 | 01 | 2 | INFRA-03 | integration | `docker compose exec backend alembic upgrade head && echo OK` | ❌ W0 | ⬜ pending |
| 1-01-06 | 01 | 2 | INFRA-04 | manual | see manual verifications | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_schema.py` — stubs for DATA-01 (listings table columns)
- [ ] `backend/tests/test_dedup.py` — stubs for DATA-02 (UNIQUE constraint enforcement)
- [ ] `backend/tests/conftest.py` — shared fixtures (in-memory SQLite, async session)
- [ ] `pytest` + `pytest-asyncio` + `aiosqlite` in `backend/requirements.txt`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| App accessible at public URL | INFRA-04 | Requires live VPS + DNS — not automatable in CI | 1. SSH to VPS; 2. `curl -I https://your-domain.me`; 3. Expect HTTP 200 |
| VPS provider selection (Kamatera vs DigitalOcean) | INFRA-04 | User decision required — DigitalOcean has no Israeli datacenter | Confirm with user before provisioning |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
