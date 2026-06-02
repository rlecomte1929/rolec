# Daytime run — stuck/skipped PRs (append-only)

PRs surfaced as blocked during the 2026-06-01 daytime interactive run, skipped by Romain's direction after a blocker was raised. Each needs human follow-up.

---

## #189 (C1-12-be — resolve + escalate POST endpoints) — ✅✅ RESOLVED + MERGED 2026-06-02 (`d2b808fb`). Dual-layer fix landed (registered in backend/main.py); post-deploy smoke: POST .../resolve + .../escalate both 401 (not 405). Backed by rce.contradictions (#216). #183 is next in the stack.

- **Hard blocker:** both handlers run `SELECT … FROM rce.contradictions … FOR UPDATE`; the table **does not exist on prod in any schema** (verified via Supabase MCP — `rce` has 22 tables, none named contradictions; no `%contradiction%` table anywhere). The endpoints would **500 on every call** (broad `except Exception` → HTTP 500; no defensive degrade).
- **Soft blocker:** dual-layer 405 trap — router registered only in `backend/app/main.py`, not `backend/main.py`. Would need fix-in-PR like #181 received.
- **Otherwise solid:** atomicity correctly implemented — `db.engine.begin()` transaction + `SELECT … FOR UPDATE` row lock + 409 already-resolved guard. Backward-compat fine (separate router; doesn't touch #181's read DTOs).
- **Next action:** land **C1-08** (which creates `rce.contradictions`) FIRST, then rebase #189, fix the dual-layer registration, merge. Until then #189 stays open. 
  - **Status 2026-06-01 late:** C1-08 draft migration opened as **PR #216** (`rce.contradictions`). Pending Romain's schema review + prod apply tomorrow. Once landed, #189/#183 become unblockable (#189 also needs its dual-layer fix).

## #183 (C1-12 — Contradiction Resolution UI) — ✅ UNBLOCKED 2026-06-02 (C1-08 landed; needs bbox List[int]→{x0,y0,x1,y1} map per #182 spot-check, and #189 ahead of it)

- Binds to #189's POST resolve/escalate endpoints + #181's `GET /contradictions/{id}/history`.
- The frontend itself may build/merge independently, but the resolve/escalate buttons would **500** until C1-08 + #189 land. Recommend deferring to land as a stack: **C1-08 → #189 → #183**. 
  - **Status 2026-06-01 late:** C1-08 draft migration opened as **PR #216** (`rce.contradictions`). Pending Romain's schema review + prod apply tomorrow. Once landed, #189/#183 become unblockable (#189 also needs its dual-layer fix).
- **When #183 eventually merges:** it must map the contradictions endpoint's `bbox` (`List[int]`) → the overlay's `{x0,y0,x1,y1}` object (from the #182 spot-check finding).

### #183 — UPDATE (2026-06-01 afternoon autonomous burst): SUPERSEDED by main — should be closed, not merged

Re-attempted under autonomy rules now that morning unblocked it. Recon found this PR is comprehensively superseded — merging would REGRESS main:

- **0 unique files.** Of 49 files in the diff: 42 are byte-identical to main, 7 differ, 0 are new.
- **Diff direction is main-is-newer on all 7 divergent files** — #183 is 75 commits behind:
  - `ResolutionPage.tsx`: main has the full 159-line implementation (`ContradictionPanel` + `useCaseContradictionsQuery` + one-at-a-time stepping + loading/error/empty states). #183 has the old 16-line "lands in C1-12 … This scaffold reserves the route" stub.
  - `CaseDetailPage.tsx`: main has the full 125-line case-detail UI (`CaseDetailNav` + 5 sections + badges). #183 has the old 21-line "lands in C1-11c" stub.
  - `.github/workflows/ci.yml`: #183's version is pre-#178 AND pre-#215 — merging would **DELETE the now-active dual-layer guard step** (#215's work, activated this morning) AND **DELETE the tax_cert test registrations** (#178's work). This alone makes #183 skip-and-log per autonomy rule #4 (no workflow touch).
  - `CorrectionHistory.tsx`: main has an a11y `role="list"` #183 lacks.
  - `package.json`/`package-lock.json`/`index.css`: stale older versions.
- **The bbox `List[int]→{x0,y0,x1,y1}` watch-item** (from #182's spot-check): genuinely-future work — neither #183 nor main delivers it. #183 shows bbox as a 4-tuple via `formatBbox` (display-only string) plus an explicit "Placeholder for the C1-11e bbox-overlay PDF preview" stub. So this PR doesn't move the bbox-mapping ball forward in any way.

**Verdict:** merging would regress main on 4 axes (revert ResolutionPage to stub + revert CaseDetailPage to stub + delete CI guard step + delete tax_cert tests). Closing loses nothing. Same shape as #193/#182.

**Next action for Romain (paste-ready):**

```
gh pr close 183 --comment "Superseded by main — the C1-12 Resolution UI shipped via prior merges. 0 unique files vs main, 42/49 byte-identical, the 7 divergent files all have #183's older versions (would regress: ResolutionPage→stub, CaseDetailPage→stub, ci.yml→pre-#178/pre-#215 deleting the dual-layer guard step + tax_cert tests). bbox array→object mapping (#182 watch-item) genuinely-future on both #183 and main, so no salvage value. Same shape as #193/#182."
```

No autonomy state-change beyond logging.

---

### Convention note for future PR authors (worth a CLAUDE.md / docs line if Romain agrees)

`rce.*` tables land incrementally. #181 defensively degrades (returns zeroes when `rce.contradictions` is absent — *"table lands with C1-08"*); #189 hard-errors (500) on the same missing table. The inconsistency was caught via a Supabase MCP existence check. **Future PRs touching `rce.*` should default to the #181 pattern: check table existence at query time and return a safe fallback**, so a not-yet-migrated table degrades gracefully instead of 500-ing in prod.

---

## #195 (AIQ-174 — PDF coordinate mapper) — ✅ MERGED 2026-06-01 late (`29d34437`; mock react-pdf in the test)

- **CI failure (accurate):** Unit Tests crashed on `Promise.withResolvers is not a function`. `PdfCoordinateMapper.test.tsx` imports `../PdfCoordinateMapper` (for its pure coord-math helpers), and that module's top-level code imports **`react-pdf`** → which transitively loads **`pdfjs-dist@4.8.69`**, whose `node_utils.js` calls `Promise.withResolvers()` (Node 22+) at import time → crash under jsdom/vitest.
- **~~Latent issue: pdfjs-dist undeclared / hoisted from apps/hr-dashboard~~ — WRONG, struck out.** Correct analysis: `react-pdf@^9.2.1` **is** declared in `frontend/package.json` and pins `pdfjs-dist@4.8.69` (its own dependency). `frontend/src` has **zero direct `pdfjs-dist` imports** — all via react-pdf. So pdfjs-dist is a *legitimate transitive dep*, not an accidental hoist (apps/hr-dashboard's `pdfjs-dist@4.10.38` is a separate copy for that separate app). **Declaring a direct `pdfjs-dist` would have been harmful** — a `4.10.38` vs react-pdf's `4.8.69` skew risks the "API version does not match Worker version" runtime break. No package.json change made.
- **Fix:** `vi.mock('react-pdf', …)` at the top of the test (Document/Page → `() => null`, `pdfjs` stub with `version: '4.8.69'`). Keeps real react-pdf/pdfjs-dist out of the test entirely. Verified locally: vitest 10/10 pass, `tsc --noEmit` exit 0. Pushed as `6b0cd1c3`.
- **Still open (Romain's call, unchanged):** should this admin coord-mapper live in `apps/hr-dashboard` instead of `frontend/`, given that's where the rest of the PDF-viewer stack lives (#184)? Not blocking; design preference for later.

---

## #191 (C2-04 rule scraper) — post-merge operational note

- Migration `20260604000000` registered `cron.schedule('rce-rule-scraper-daily', '0 3 * * *', ...)` calling Edge Function `/rce-rule-scraper`. **Verified registered on prod** (`cron.job` has the entry).
- If the Edge Function isn't deployed, the cron will fail daily at 03:00 UTC starting **2026-06-02** (silent failure — Supabase cron errors don't page).
- **RESOLVED TONIGHT (2026-06-01):** Checked via Supabase MCP `list_edge_functions` — `rce-rule-scraper` is **NOT deployed** (scanned all 24 functions; no such slug). Per plan, did NOT deploy untested code tonight. Instead **unscheduled the cron**: `SELECT cron.unschedule('rce-rule-scraper-daily');` → verified `cron.job` now has 0 rows for that jobname. The daily 03:00 UTC silent 404 is averted.
- **Remaining action for tomorrow:** when `/rce-rule-scraper` is ready, deploy it AND re-register the cron (schedule SQL is the `cron.schedule(...)` block in migration `20260604000000`). Until then it stays unscheduled. Log this pattern (migration registers cron → Edge Function dependency) in the deployment checklist so it's caught pre-merge in future RLS reviews.
- Table itself is correct: `rce.rule_change_proposals` exists, RLS enabled, 2 policies (admin_all + service_role_all), anon unreachable (rce schema not PostgREST-exposed).

---

## #176 (C2-06-FOLLOWUP — policy-gap adapter) — stale duplicate migrations (#209 pattern)

- **Backend code likely has independent value:** `policy_gaps` router (dual-layer registered correctly in BOTH backend/main.py + backend/app/main.py), `policy_evidence/` detectors (housing_benefit, immigration_support, language_training), adapter + events, tests.
- **Migrations are stale duplicates:** `20260529160000_rce_policy_gaps.sql` + `20260529161000_rce_case_artefacts.sql` use **bare `CREATE TABLE`** (no IF NOT EXISTS). Both `rce.policy_gaps` and `rce.case_artefacts` **already exist on prod** with **byte-identical schemas** (verified column-by-column via MCP), applied earlier via prod migration history `20260529125415`/`20260529125813`. Applying #176's migrations → `relation already exists` failure; merging as-is re-introduces a `supabase db reset`/replay landmine (same as #209).
- **Architectural question for Romain (tomorrow):**
  - Path A: open a new PR with just the backend code (no migrations) once #209 lineage is cleaned up.
  - Path B: rewrite #176's migrations with `IF NOT EXISTS` so they're idempotent (apply cleanly to both fresh DBs and prod).
  - **Recommendation:** defer to **#209 reconciliation day** — both face the same "stale-vs-deduped migration lineage" problem; resolve them together.
- Not merged. Left open.

### #176 — UPDATE (2026-06-01 late): deeper than "stale duplicate" — DO NOT delete or naive-idempotent-rewrite

Attempted Path B (idempotent rewrite). STEP-1 prod verification surfaced two blockers — **stopped before any branch/surgery**:

1. **Canonical source migrations are NOT in the repo on main.** No file on main creates `rce.policy_gaps` or `rce.case_artefacts`; #176's two migrations are the *only* file-based source. Prod has the tables via history-drift (`20260529125415`/`125813` in prod migration history, no repo files). So **deleting #176's migrations would leave the repo with zero source for these tables** (fresh `db reset` would fail; code references uncreated tables).

2. **Policy name + security-posture mismatch (the real blocker).** Prod has `policy_gaps_service_role_only` / `case_artefacts_service_role_only` (restrictive, cmd ALL). #176 declares `policy_gaps_permissive` / `case_artefacts_permissive` (`USING(true)` for authenticated). `DROP POLICY IF EXISTS <#176 name>` would NOT match the live names → applying #176 would **add a permissive policy alongside the restrictive one** → since RLS permissives OR together, this **loosens access** (authenticated users gain read/write). Security regression, not a no-op.

3. **Prod schema is more evolved than #176.** `rce.case_artefacts` on prod has extra unique indexes (`case_artefacts_one_per_source_cost`, `case_artefacts_one_per_source_doc`) absent from #176's migration. #176's migration is an *older design* superseded by what's live.

**Path forward (tomorrow, fresh head, with #209/drift cleanup):** decide the canonical schema — almost certainly prod's (service-role-only + the extra constraints) — then either (a) commit a NEW repo migration matching prod's actual state and drop #176's migrations + keep its backend code, or (b) rewrite #176's migrations to *exactly* mirror prod (same policy names `*_service_role_only`, same indexes). Either way, the backend code (policy_gaps router + detectors) likely needs review against the service-role-only policy (does it read via service-role/pooler? then fine). **The permissive `USING(true)` policy in #176 should NOT land on prod.** No prod changes were made tonight.

### #176 — UPDATE (2026-06-01 afternoon autonomous burst): re-confirmed skip, no new analysis

Re-checked under autonomy rules. Stuck classification unchanged from the analysis above:

- Carries Supabase migrations creating `rce.policy_gaps` + `rce.case_artefacts` → autonomy rule #1 trigger (no migrations in auto-merge).
- Yesterday's deeper finding (Path-B blockers) stands: prod policies are `*_service_role_only` (restrictive); #176 declares `*_permissive` (`USING(true)` for authenticated) under DIFFERENT names → `DROP POLICY IF EXISTS` wouldn't catch the live policies → applying would coexist OR-combined permissive+restrictive → security regression granting `authenticated` read/write the live policies deny.

No autonomy-eligible path; bundles with #209 reconciliation. No new investigation; no prod changes.

### #176 — RESOLVED 2026-06-02 (autonomous execution, pre-authorized)

Executed the resolution plan (`audit/176-resolution-plan-2026-06-02.md`) end-to-end. **Merge SHA `5a58bf0d78d795a3aeeefdd43d4516c5601c07a7`.**

- **Rebased** #176 on origin/main; **deleted** the two stale permissive migrations (`20260529160000_rce_policy_gaps.sql`, `20260529161000_rce_case_artefacts.sql`).
- **Authored** `supabase/migrations/20260604100000_rce_policy_gaps_and_case_artefacts_with_service_role_hardening.sql` — fully idempotent (CREATE TABLE IF NOT EXISTS, DROP POLICY IF EXISTS + recreate `*_service_role_only`, REVOKE from anon/authenticated/public, GRANT to service_role). Mirrors prod's evolved schema (extra unique constraints + service-role-only posture); no-ops on prod, replays clean on fresh DB. The permissive `USING(true)` policies are gone.
- **CI:** all real checks green. Supabase Preview failed as expected (#194 replay landmine, unrelated — see `audit/194-replay-landmine-2026-06-02.md`).
- **MCP apply** to prod (`nsvefcvpvwwwhuqyuqmp`, name `rce_policy_gaps_and_case_artefacts_with_service_role_hardening`) → `{"success":true}`.
- **Verification (all 4 PASS):**
  1. Tables → 2 rows (`policy_gaps`, `case_artefacts`) ✓
  2. Policies → exactly 2, both `*_service_role_only` / ALL / `{service_role}`; NO `*_permissive` ✓
  3. Grants → only `postgres` + `service_role`; NO anon/authenticated ✓
  4. Anon smoke → `406` (Invalid schema: rce — not PostgREST-exposed) ✓
- Backend code (policy_gaps router + detectors + adapter + tests) kept unchanged — reads via service-role pooler, bypassing RLS.

### #209 → #220 — RESOLVED 2026-06-02 (path (c), multi-session, MANDATED pause-points) — RUN COMPLETE

Parker pipeline steps A–J are **live on `main`**. #209 (`audit/parker-integration`) reconciled via **path (c)** from `audit/pr-209-triage.md`: clean cherry-pick of the 58 additive work commits onto a fresh branch off current main, skipping the 10 merge commits. Landed as successor **PR #220, merge SHA `63daf587`**. Queue effect: **#209 stream drains to 0 open** (full RESOLVED write-up appended to `audit/pr-209-triage.md`).

- **Cherry-pick:** 58/58 commits applied, 0 skipped, 11 mechanical conflict resolutions (additive router/dep unions + 1 Parker-internal D×G union), **0 semantic conflicts** — the recon hypothesis held.
- **Code sanity:** `from backend.main import app` → **629 routes**, all Parker prefixes registered in the **prod** entry-point (dual-layer rule PASS); frontend `tsc --noEmit` exit 0; `/health` 200×3 on the merge commit.
- **Migrations applied one-at-a-time via MCP** (`nsvefcvpvwwwhuqyuqmp`, explicit GO per file, NO batching — same discipline that caught real divergence on #194/#176): **8 of 9 applied + verified** (`ml_models`, `benefit_optimizer`, `supplier_cluster_cache`, `prompt_registry`, `ai_human_feedback`, `ocr_shadow_comparison`, `conjoint`, `translation_cache`). All 11 Parker tables verified `rowsecurity=true` with exact declared policy counts; anon smoke 401/403 (406 for rce.*), never 200.

**3 defects discovered (all one root class — Parker assumed migrations are the sole DDL authority, but a second runtime table-creation path interacts differently on Postgres):**
1. **Mig 7 `ai_unit_economics` — DEFERRED, NOT applied.** `ALTER TABLE public.policy_assistant_traces …` against a table that **does not exist on prod and has no creation path** (`database.py:1186` returns before the SQLite-only `CREATE TABLE` scaffolding at line 2428; no migration creates it). Held as one txn → would fail `relation … does not exist`. Documented as **drift entry 11**. Only tracked open item from this run.
2. **Mig 9 `translation_cache` — RESOLVED in-session (Option B).** Table was already present in a **degraded ORM shape** — `app/db.py:19 create_all()` won the boot race and created it from `models.py:400` before the migration ran; the migration's `IF NOT EXISTS` then no-op'd, leaving prod without RLS/CHECKs/correct types. Reconciled via atomic DROP+rebuild (0 rows, no inbound FKs verified first). Documented as **drift entry 12**.
3. **Close-out observation:** Parker's convention is to enforce row-level invariants in the **service layer, not DB CHECK constraints** — consistent across all 8 applied migrations **except migration 9** (the only one with `domain`/`provider` CHECKs). Worth a convention-alignment note for future Parker work, not a blocker.

**Queue status: 0 actionable.** The sole tracked carry-forward is the mig-7 prerequisite (author a real `policy_assistant_traces` table migration + re-apply mig 7 — ~30 min, next session). The autonomous/mandated-pause multi-session Parker run is **COMPLETE**.

### Drift entry 10 (DE dossier seed) → FIX AUTHORED in #221, BLOCKED behind entry 13 — 2026-06-02

Task: turn Supabase Preview GREEN by fixing the DE dossier seed (`20260507150000_de_dossier_questions.sql`), reverse-drift entry 10. Chose **Option D** (no-op broken file + replay-safe re-seed). Opened **PR #221** (`fix/de-dossier-replay`): no-op'd the broken file + new `20260604300000_de_dossier_questions_corrected.sql` (9 DE rows, real columns, `ON CONFLICT … DO NOTHING`).

- **Pre-authorship verification (both clean):** category→domain is a 1:1 against prod's 9 DE rows; natural key `(destination_country, question_key, version)` confirmed for ON CONFLICT.
- **Standard CI:** all green (Backend tests incl. dual-layer guard, FE/HR builds, TS/ESLint, route-auth audit, unit tests).
- **Supabase Preview: still RED — but with a DIFFERENT error.** No longer the DE `column "destination" …`; now `column "case_id" does not exist` at `CREATE UNIQUE INDEX … idx_employee_profiles_case_employee` (`20260518120000`, May 18). **This is proof the DE fix WORKS** — the replay now walks past May 7 and dies at the next landmine downstream.
- **Decision per run's tree:** "Preview RED for a DIFFERENT error → STOP, document as new drift entry, do NOT merge." → **#221 left OPEN, unmerged.** Logged the new landmine as **drift entry 13** (root cause: Feb 21 baseline `employee_profiles` has PK `assignment_id`/no `case_id`; mig A's `CREATE TABLE IF NOT EXISTS` no-ops against it then its `case_id` index fails; the fix migration B at `20260522170000` is 4 days too late in replay order). **Prod verified HEALTHY** (MCP read-only): current `employee_profiles` has `case_id` + index; `legacy_employee_profiles` exists → B's rename ran on prod. Only repo replay is broken. **NO MCP apply performed** (nothing to apply; #221 unmerged).
- **Reframe surfaced:** Supabase Preview red is a **chain** of replay landmines (10 → 13 → …), not one bug. Each fix reveals the next. Preview goes green only when the whole chain is drained. Entry 13 (and any successors it reveals) needs separate authorization before #221 can merge.
- **Methodology note (carried):** always verify prod schema BEFORE assuming what an out-of-band path did — and expect replay fixes to surface the *next* landmine rather than turning Preview green on the first try.

### Drift entry 13 (employee_profiles) → FIX AUTHORED in #221; entry 14 surfaced → PIVOT — 2026-06-02

Authorized to fix entry 13 then reassess. Pre-authorship verification revealed the (a/b/c) framing was incomplete: Feb-21 baseline `employee_profiles` has 3 cols (no `id`/`employee_id`/`case_id`), prod = B's 51-col shape + trigger, and **A's `data_access_log_employee_select` policy is a second hidden failure point** inside A (reads the new shape). Chose **Design 2** (no-op + new file, the #219/#221 discipline) after surfacing the finding and getting GO.

- **Fix (folded into #221 so Preview tests the whole chain):** block-comment-disable A's `employee_profiles` block AND its `data_access_log_employee_select` policy (A's 6 other tables untouched); no-op B (`20260522170000`); add `20260604400000_employee_profiles_replay_safe.sql` = idempotent rebuild of the exact prod shape + the orphaned `data_access_log` policy. Structural checks all green (balanced block comments, even `$$`, balanced `BEGIN/COMMIT`); temporal-gap check clean (`data_access_log` referenced only in A).
- **Standard CI:** green. **Supabase Preview: RED again — at 5m35s (longer ⇒ advanced further), and a NEW, DIFFERENT error:** `column "plan_tier" of relation "public.profiles" does not exist` at `COMMENT ON COLUMN public.profiles.plan_tier` (`20260520000000_platform_redesign_schema.sql`, statement 6). **Proof both fixes WORK** — replay now clears the DE seed AND `employee_profiles`.
- **This is drift entry 14** — same `IF NOT EXISTS`-vs-Feb-21-baseline class as entries 12/13: `platform_redesign`'s `CREATE TABLE IF NOT EXISTS public.profiles (… plan_tier …)` no-ops against the baseline `profiles` (no `plan_tier`), then the COMMENT fails. **Prod HEALTHY** (MCP read-only): `profiles.plan_tier` + `companies.plan_tier` present. Iceberg: `platform_redesign` re-creates **4 baseline-colliding tables** (`companies, messages, policy_exceptions, profiles`); only `profiles` has thrown so far.
- **DECISION — PIVOT (per pre-authorized tree at entry-14 / chain-depth ≥3):** STOP single-fix sprints. **#221 marked DRAFT (held)** — both its fixes (entries 10 + 13) are correct but blocked behind entry 14+. Next session = a deliberate **baseline-reconciliation / `_remote_stub` backfill project** (enumerate the full collision set deterministically, pick one reconciliation primitive, fix + verify in ONE green Preview, then land #221's held fixes). Full plan in `audit/migration-drift-definitive-2026-06-02.md` § PIVOT.
- **No MCP apply performed** (nothing to apply; #221 held). Prod untouched throughout.
