# Preview-red tail drainage — milestone summary (2026-06-02)

**Goal:** take Supabase Preview from red toward green by draining the post-redesign migration tail, **repo-only** (no prod mutation), prod-as-oracle.

**Outcome:** the entire *targeted* tail was drained. Supabase Preview advanced from the original DE-seed failure all the way to **`20260522160000`** (May 22), clearing every discrete landmine in scope. It is now blocked by a **different, larger class** — the `_remote_stub` structural backlog (out-of-band tables with no repo CREATE) — which was always scoped as a separate multi-day project. **Preview is not green; that requires the `_remote_stub` backfill (now a tracked Notion task).**

## PRs
- **#226** (`fix/preview-tail-drainage`) — entries 15/16/17 + orphan handling.
- **#227** (`fix/preview-tail-may22-replay-safe-and-entry11-drop`, stacked on #226) — May-22 replay-safety + entry-11 drop.

Both are correct, prod-verified, **repo-only** (no prod data/schema changed). Recommended to land as banked progress even though Preview stays red at the `_remote_stub` wall (same discipline as #224 — green requires draining the whole chain).

## What was drained (prod-as-oracle throughout)

| Entry | File | Class | Action |
|---|---|---|---|
| **15** | `20260521060000_case_form_comments_events` | `uuid = text` RLS cast (`cases.employee_id` uuid vs `auth.uid()::text`) | Dropped `::text` (×2) + `::uuid` on `p.id` (×2) to match prod's live policy |
| **16** | `policy_conflicts` + `policy_chunks_vector_index` | reverse-drift orphans (absent on prod) | **Dropped** both. (`policy_conflicts` was briefly reverted+fixed, then **re-dropped** — see below.) |
| **17** | `20260524000005_support_tickets` | invalid `CREATE POLICY IF NOT EXISTS` syntax | Rewrote to `DROP POLICY IF EXISTS … ; CREATE POLICY …` (bodies already matched prod) |
| (new) | `20260522140000_ai_refusal_logs` | orphan + nested dollar-quote bug | **Dropped** (absent on prod, never recorded, no consumers) |
| (new) | `20260522140001_policy_feedback_and_review_queue` | `GENERATED ALWAYS AS (array_to_string(...)) STORED` — not IMMUTABLE (42P17) | Replaced the generated column with a **BEFORE INSERT/UPDATE trigger** (repo-only replay-safety; does NOT deploy the feature) |
| (new) | `20260522120000_employee_tiers`, `20260522130000_policy_cap_exceptions` | replay-clean, **live backend consumers** | **Kept** (not orphans — Phase 2 deploys their tables) |
| **11** | `20260601080000_ai_unit_economics` | deferred Parker mig-7 (missing `policy_assistant_traces` prereq) | **Dropped** + Notion re-author task |

## Two course-corrections worth recording
1. **The "abandoned May-22 batch" premise was wrong.** A no-consumer grep found **live, prod-wired application code** (`app/routers/policy_feedback.py` registered dual-layer, `app/routers/employee_tiers.py`, `policy_query_answering.py`, frontend) for `policy_feedback`/`policy_review_queue`/`employee_tiers`. These aren't abandoned — they're **shipped features whose schema migrations were never applied to prod** (they degrade gracefully via `try/except`). So instead of dropping them, the migrations were made **replay-safe** (repo-only) and a **Phase 2 "MCP-apply to prod"** task was filed to actually enable them.
2. **`policy_conflicts` is structurally broken, not simply fixable.** Its first replay error was the entry-15 `auth.uid()::text` cast (fixable) — but Preview then exposed a **second, cross-era `uuid = text`**: its RLS policy joins redesign `profiles` (`company_id` uuid) to legacy `policy_knowledge_snapshots` (`company_id` **text**). No prod oracle (absent on prod) and a cast would be semantically wrong. So it was **re-dropped** + added to the re-author backlog.

## Preview progression (chain-advancement)
stmt 6 (DE seed, pre-session) → … → `20260521060000` (entry 15) → `20260522140000` (ai_refusal_logs) → `20260522140001` (policy_feedback) → `20260522100000` (policy_conflicts, after revert) → **`20260522160000` (`canonical_policy_facts` — `_remote_stub` wall)**. Final run 6m55s — the deepest replay yet.

## What remains: the `_remote_stub` wall
`20260522160000_canonical_policy_facts_tier.sql` ALTERs `public.canonical_policy_facts`, which **exists on prod but has no CREATE in the repo** — created out-of-band. There are **98 `*_remote_stub.sql`** placeholder files of this kind. A fresh replay therefore can't reproduce prod, and Preview can't go green until they're backfilled. This is the documented multi-day structural project, now tracked.

## Notion tasks filed
- **Re-author `ai_unit_economics` + `policy_assistant_traces`** (Parker mig-7 deferral) — P2, Backend.
- **MCP-apply May-22 feature batch to prod** (`employee_tiers` + `policy_cap_exceptions` + `policy_feedback` + `policy_review_queue`) — P1, Database Migration. *This is the deploy step that un-breaks the degraded prod features.*
- **`_remote_stub` backfill project** (~98 out-of-band tables; first blocker `canonical_policy_facts`) — P2, Infrastructure.
- Re-author backlog (within the Phase 2 task): `policy_chunks_vector_index` (pgvector/BM25, structural) + `policy_conflicts` (cross-era uuid/text `company_id`).

## Recommendation
Land #226 + #227 (banked, repo-only, prod-verified). Preview-green is gated on the `_remote_stub` backfill project — a separate, larger effort, now scoped and tracked.
