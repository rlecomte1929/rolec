# Morning run — summary (2026-06-02)

Resumed yesterday's queue work. Goal: land the 3 staged drafts (#214 → #215 → #216) in order.

## Landed (all 3 drafts merged)

| PR | Title | Merge SHA | Notes |
|----|-------|-----------|-------|
| #214 | dual-layer router registration mount-check guard + allowlist | `b7d7c4f1` | Script + 21-entry allowlist. Verified guard PASSES on current main. Script-only (no CI wiring yet). |
| #215 | wire #214's guard into Backend tests job | `bfc6610a` | Rebased onto new main (script present), CI green. **Guard now ACTIVE** — Backend tests log shows it ran + printed "PASS — … 21 allowlisted". Every future PR adding a modular-only router will red CI until registered in backend/main.py or allowlisted. |
| #216 | C1-08 — create rce.contradictions | `18000b0c` | **Applied to prod via MCP + verified.** Schema synthesized from #181 reads + #189 writes. **4 pre-merge catches:** real CHECK values, no correction_id, service-role-only RLS (not §12.2), and **resolved_by FK dropped** (FK to auth.users would 500 #189 — hr_user_id is public.users.id text, not auth.uid()). |
| #189 | C1-12-be — resolve + escalate POST endpoints | `d2b808fb` | **Dual-layer 405 fix** (registered hr_case_resolve in backend/main.py; same pattern as #181/#188/#213). The new CI guard (#215) self-verified the fix in-pipeline. Rebased clean (additive union of 3-router list). Post-deploy smoke: both POSTs 401 (not 405). Backed by rce.contradictions (#216). |

## C1-08 apply verification (all green)
table exists ✓ · RLS enabled ✓ · 1 policy `contradictions_service_role_only` (ALL/service_role/PERMISSIVE) ✓ · anon/authenticated grants stripped ✓ · 15 columns correct types ✓ · constraints = PK + FK(rce.cases) + FK(rce.canonical_entities) + CHECK, **NO FK on resolved_by** ✓ · anon smoke 404/406 (rce not PostgREST-exposed) ✓.

## The resolved_by trace (the morning's key catch)
#189 `resolved_by = :hr_user_id`; `hr_user.get("id")` ← `get_current_user` ← `db.get_user_by_token` = legacy ReloPass auth → **public.users.id (text)**, NOT auth.uid() (uuid). `rce.corrections.corrected_by` stores the same value as **uuid, no FK** → matched that. An FK to auth.users(id) would have 500'd #189's resolve on every call. Caught + fixed pre-apply.

## Queue: 7 → 4 open
Started the morning with 7 open (4 carry-over + 3 staged drafts #214/#215/#216). All 3 drafts merged → **4 open**: **#176** (schema-drift / #209 reconciliation), **#183** (UNBLOCKED — needs bbox List[int]→object map), **#189** (UNBLOCKED — needs its dual-layer 405 fix), **#209** (Parker reconciliation).
