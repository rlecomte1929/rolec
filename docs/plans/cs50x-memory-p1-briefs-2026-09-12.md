# CS50x Lec 4 Memory → ReloPass P1 briefs (grounded)

Generated 2026-09-12. Source: [CS50x 2024 Lecture 4 notes](https://cs50.harvard.edu/x/2024/notes/4/). These briefs are for **repo-attached Cursor** pickup. They do **not** implement the work; they are the Execution Prompts.

**Notion (Ready for AI, Assigned Cursor):**

- AIQ-2302 [RP-MEM-007 Source fetch NULL-check](https://app.notion.com/p/3d9887c64d48816197c0e562834f7f70)
- AIQ-2303 [RP-MEM-002 Requirement decay monitor](https://app.notion.com/p/3d9887c64d4881d88cfdc834cb08e05c)
- AIQ-2304 [RP-MEM-001 Compiled catalog cache](https://app.notion.com/p/3d9887c64d4881198d13e15033b9b7cb)
- AIQ-2305 [RP-MEM-003 Invalidate on write](https://app.notion.com/p/3d9887c64d48810ab374de6b5062d036) (Depends On → 001 / AIQ-2304)

**Do not invent tables.** Served catalog is `public.requirement_items` via `backend/app/services/requirements_builder.py`. `requirement_facts` is extract/admin, not Case Command.

**Pickup order:** RP-MEM-007 → RP-MEM-002 (independent of cache) · RP-MEM-001 then RP-MEM-003 (003 is blocked on 001). Prefer shipping 001 and 003 in the **same PR**.

**Related parked cards (do not re-open as Ready for AI):**

- [Cache compiled corridor requirements + invalidation](https://app.notion.com/3bf887c64d48811687a0d9a368c265cf) (Parked P2)
- [verified_at + staleness queue](https://app.notion.com/3bf887c64d488153a80feab7edd40df7) (Parked P2)
- [Resilient source fetching](https://app.notion.com/3bf887c64d4881fbb815db43d07f36f4) (Parked P2)
- [Invalidate attested items on source drift](https://app.notion.com/3c1887c64d488117a392c145b73fff79) (Parked P3)

**Already shipped (out of this P1 set):**

- RP-MEM-006 quote integrity: `backend/app/services/evidence_quote_validator.py` (AIQ-1956)
- RP-MEM-004 pack dependency graph: `scripts/check_corridor_facts.py` `check_graph()`

Work in a git worktree. Commit explicit paths. No `supabase db push`. No EU AI Act status claims.

---

## RP-MEM-007 — Source fetch NULL-check (official ingest)

| Field | Value |
|---|---|
| Assigned AI Agent | Cursor |
| Status | Ready for AI |
| Priority | P1 |
| Task Type | Backend Implementation |
| Product Area | Data Quality |
| Layer | API |
| Estimated Complexity | Low |
| Autonomy Tier | Yellow — self-validate + sample |
| Definition of Ready | Vetted — ready |

### Execution Prompt

```
You are implementing RP-MEM-007 on ReloPass (repo rlecomte1929/rolec).

CS50 analogy: malloc() returning NULL must be checked. A failed HTTP fetch is NULL. Do not persist it as evidence.

## Goal
Make every URL-fetch that can persist a knowledge/requirement row treat failure like `backend/imports/immigration/fetcher.py`: `ok=false` → no document body stored as evidence, no fact promotion, `fetch_status` is `fetch_failed` (or no row).

## Known gap (verify, then fix)
`backend/app/services/official_ingest_service.py` `ingest_url_to_knowledge_doc`:
- On exception it sets `fetch_status = "fetch_failed"` but still calls `db.upsert_knowledge_doc_by_url(..., text_content=excerpt or "")`.
- Contrast: `backend/imports/immigration/fetcher.py` `FetchedDoc.ok` and the module docstring: a failed fetch produces no row / no placeholder body.

Also audit (read, do not invent new wrappers unless a second writer has the same bug):
- `backend/scripts/backfill_fact_evidence.py` (`fetch_status_for`)
- any other caller of `_fetch_html` / live source fetch that upserts `knowledge_docs` or `requirement_items`

## Must
- 4xx, 5xx, empty extraction, login-page redirect, below MIN_TEXT: not stored as `fetch_status=fetched` and not stored as empty `text_content` that later reads as a source.
- Successful fetch path unchanged (allowlist, sha256 of real excerpt).
- Log `source_host` + `failure_reason` (logger is enough; PostHog optional).
- No UI. No migration unless you discover a NOT NULL that forces a placeholder — if so, stop and report.

## Must not
- Do not treat WorkspaceDB as the serving store.
- Do not change serving engines (`requirements_builder`, `rules_engine`, …) to import LLM modules.
- Do not claim compliance status in copy.

## Test
Add/extend pytest so a mocked 403 / empty body does not upsert empty evidence as fetched. Success path still upserts fetched + hash.

Worktree: `git worktree add -q -b feat/rp-mem-007-fetch-null-check /tmp/wt-rp-mem-007 origin/main`
Commit explicit paths. Register no new routers unless you add an API (prefer not to).
```

### Validation Criteria

1. pytest: mocked failed fetch does not leave `knowledge_docs.text_content` as `""` with `fetch_status=fetched`.
2. pytest: mocked successful official-domain fetch still stores excerpt + sha256 and `fetch_status=fetched`.
3. `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 pytest` on the touched test files passes.

### Expected Output

Patch to `official_ingest_service.py` (and any other writer with the same bug) + tests. No admin UI.

### Files to Touch

- `backend/app/services/official_ingest_service.py`
- existing official-ingest / knowledge-doc tests (add if missing)
- possibly `backend/scripts/backfill_fact_evidence.py` only if it writes empty fetched bodies

### Test Command

```bash
cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 pytest tests/ -k "official_ingest or knowledge_doc or backfill_fact_evidence" -q
```

### Technical Constraints

Immigration fetcher already does this correctly — match that contract. Hard gates: no `supabase db push`; dual router registration only if you add a router (do not).

### Risk & Rollback

Low. Failed fetches already exist as a status. Worst case: fewer placeholder docs, more explicit failures. Revert the upsert-guard commit.

---

## RP-MEM-002 — Requirement decay monitor (last_verified_at)

| Field | Value |
|---|---|
| Assigned AI Agent | Cursor |
| Status | Ready for AI |
| Priority | P1 |
| Task Type | Backend Implementation |
| Product Area | Corridor Knowledge |
| Layer | Feature |
| Estimated Complexity | Medium |
| Autonomy Tier | Yellow — self-validate + sample |
| Definition of Ready | Vetted — ready |

### Execution Prompt

```
You are implementing RP-MEM-002 on ReloPass.

CS50 analogy: Valgrind for leaks. Stale served rules accumulate silently unless decay is visible.

## Goal
Flag approved `requirement_items` whose `last_verified_at` is older than a declared review cycle. Surface as a report (CLI and/or admin GET). Do not silently un-approve (that would empty Case Command).

## Ground truth
- Table: `public.requirement_items` (`backend/app/models.py` `RequirementItem`).
- `last_verified_at` already exists and is NOT NULL.
- Serve gate is `review_status='approved'` in `requirements_builder.py`.
- Do NOT add columns to `requirement_facts` for this. Do NOT use WorkspaceDB `requirement_decay_queue`.

## Preferred v0 (no migration)
Code-side cycle map keyed by `pillar` (e.g. immigration/residence 90 days, housing/healthcare/structural 365). Function: given now + row → `is_stale: bool`. Script: `python -m backend.app.services.requirement_decay` or `scripts/report_requirement_decay.py` listing country_code, id, title, age_days, cycle_days.

Optional smallest admin JSON: GET that returns `{ count, by_country: [...] }` for admin/HR. If you add a router, register in BOTH `backend/main.py` AND `backend/app/main.py`.

## Must not
- New `public` column unless the report is blocked without it. If you add `review_cycle_days`, migration must be idempotent, timestamp above repo max AND ledger max, RLS already on, REVOKE anon already on — do not recreate the table.
- Do not drop approved rows from serving. Stale = labeled, still served.
- No 30-day edge cache. No EU AI Act claims.

## Test
Fixture: approved item `last_verified_at` 100 days ago with 90-day cycle → flagged. Fresh stamp → not flagged. `requirements_builder` still returns the stale approved item.

Worktree: `git worktree add -q -b feat/rp-mem-002-decay-monitor /tmp/wt-rp-mem-002 origin/main`
```

### Validation Criteria

1. Unit test: 100-day-old approved immigration-pillar item is stale; same-day item is not.
2. Served catalog still includes the stale approved item (no silent un-approve).
3. Report/CLI exits 0 and prints at least country + id for fixtures.

### Expected Output

Decay helper + tests. CLI or admin GET. Optional tiny admin widget only if it fits the same PR without design-system invention.

### Files to Touch

- new `backend/app/services/requirement_decay.py` (or similar)
- tests under `backend/tests/`
- optional script under `scripts/`
- optional admin router only if adding GET — then both `backend/main.py` and `backend/app/main.py`

### Test Command

```bash
cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 pytest tests/test_requirement_decay.py tests/test_requirement_review_gate.py -q
```

### Technical Constraints

Prefer no migration. If migration is required, stamp above both `git ls-tree origin/main --name-only supabase/migrations/` max and prod ledger max. Never `supabase db push`.

### Risk & Rollback

Medium if a migration is added; Low if code-only. Rollback = revert. Serving behavior must remain “approved still served.”

---

## RP-MEM-001 — Compiled catalog cache (in-process, short TTL)

| Field | Value |
|---|---|
| Assigned AI Agent | Cursor |
| Status | Ready for AI |
| Priority | P1 |
| Task Type | Performance Optimization |
| Product Area | Core Product |
| Layer | API |
| Estimated Complexity | Medium |
| Autonomy Tier | Red — full human gate |
| Definition of Ready | Vetted — ready |

### Execution Prompt

```
You are implementing RP-MEM-001 on ReloPass. You MUST land RP-MEM-003 in the same PR (or this card is not done). Cache without invalidation is worse than no cache.

CS50 analogy: malloc once, reuse. Not a 30-day CDN.

## Goal
In-process cache around `requirements_builder` compile for a destination catalog lookup. Key: country_code + purpose (and any other dimensions the builder already uses: assignment type / nationality filters if they change the result) + a catalog generation token. TTL: minutes to a few hours, NOT 30 days. Render is `--workers 1` — no “edge” layer.

## Ground truth
- Read path: `backend/app/services/requirements_builder.py` over `requirement_items` with `review_status='approved'`.
- Do not cache `requirement_facts`.
- Query-count test pattern: `backend/tests/test_employee_policy_caps_query_count.py`.

## Must
- Hit returns the same DTO as a cold compile for the same key.
- Miss compiles via existing builder, stores, returns.
- Log cache_hit vs cache_miss (logger; PostHog optional).
- Invalidation: see RP-MEM-003 in this same PR.

## Must not
- 30-day TTL. Redis/CDN unless already in prod (it is not the default).
- Cache pending/rejected rows.
- Serving engines must not import LLM SDKs.

Worktree: `git worktree add -q -b feat/rp-mem-001-003-catalog-cache /tmp/wt-rp-mem-001 origin/main`
```

### Validation Criteria

1. Second identical lookup does not re-query `requirement_items` (query-count or mock).
2. After TTL expiry, a compile runs again.
3. DTO equality: hit == miss payload for the same fixture catalog.
4. RP-MEM-003 tests also pass in this PR.

### Expected Output

Cache wrapper + tests, landed with RP-MEM-003 invalidation.

### Files to Touch

- `backend/app/services/requirements_builder.py` (or a thin cache module it calls)
- `backend/tests/` query-count / builder tests

### Test Command

```bash
cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 pytest tests/ -k "requirements_builder or requirement_item or catalog_cache" -q
```

### Technical Constraints

Same PR as RP-MEM-003. Dual-layer: no new router required. `npx tsc --noEmit` only if frontend is touched (prefer not).

### Dependencies

Ship with RP-MEM-003. Do not merge 001 alone.

### Risk & Rollback

Stale catalog if invalidation is missed — that is why 003 is mandatory. Rollback = revert PR.

---

## RP-MEM-003 — Invalidate catalog cache on requirement_items write

| Field | Value |
|---|---|
| Assigned AI Agent | Cursor |
| Status | Ready for AI (Blocked until RP-MEM-001 exists in the same branch) |
| Priority | P1 |
| Task Type | Backend Implementation |
| Product Area | Core Product |
| Layer | API |
| Estimated Complexity | Medium |
| Autonomy Tier | Red — full human gate |
| Definition of Ready | Vetted — ready |

### Execution Prompt

```
You are implementing RP-MEM-003. Depends on RP-MEM-001 (same PR).

CS50 analogy: free() after mutation. A cache entry must not outlive the requirement_item it was compiled from.

## Goal
On `requirement_items` INSERT/UPDATE including `review_status` / lawyer/attest promote, drop in-process cache keys for that `country_code` (or bump a per-country generation token that is part of the cache key). Next `requirements_builder` call is a miss and reflects the new row.

## Ground truth
- Writes go through `crud.create_requirement_item` / review and attestation promote paths. Hook the funnel, not a random SQL trigger unless that is the only complete write path.
- In-process cache: no background recompile queue.

## Must
- After approve/edit of an item, next compile for that country is a miss and includes/excludes the change.
- Log who/when/item id at info (no PII beyond ids).
- Other countries’ cache keys untouched.

## Must not
- Invalidate the entire process cache on every write if a per-country key exists.
- Persist invalidation events in a new public table unless you need audit — prefer existing audit_logs if a pattern already exists; do not add a table without RLS + policy + REVOKE anon.

Worktree: same as RP-MEM-001 (`feat/rp-mem-001-003-catalog-cache`).
```

### Validation Criteria

1. Edit or approve a fixture item → next builder call misses and returns the new description/status.
2. Unrelated country’s cached compile is unchanged.
3. Combined with RP-MEM-001 query-count test: miss after write, hit on second read.

### Expected Output

Invalidation hooks in crud/promote + tests, same PR as 001.

### Files to Touch

- `backend/app/crud.py` (or wherever `create_requirement_item` lives)
- lawyer/attest promote if they update `requirement_items` outside crud
- cache module from RP-MEM-001
- tests

### Test Command

```bash
cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 pytest tests/ -k "catalog_cache or requirement_item_review or attestation" -q
```

### Technical Constraints

Hook writes ReloPass already uses. No `supabase db push`. Serving/LLM isolation unchanged.

### Dependencies

RP-MEM-001 (same PR). Notion `Depends On` relation should point at the 001 card.

### Risk & Rollback

If hooks miss a write path, stale cache. Tests must cover crud + review_status change. Rollback with 001.
