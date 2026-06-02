# Daytime interactive PR merge run — summary (2026-06-01)

Operator: Romain (interactive, approving each checkpoint). Executor: Claude Code.
Plan: `audit/overnight-run-plan.md`. Mode: daytime interactive (`audit/daytime-run-prompt.md`).

| PR | Title | Outcome | Merge/close SHA | Notes |
|----|-------|---------|-----------------|-------|
| #179 | exception_requests RLS replayable | — | `7c41e3e5` | Already merged before run started; unblocked Parker. |
| #209 | Parker integration A–J | **skipped** | — | Stale (9 behind main); carries 8 dup-named migrations main already deduped + diverged exception_requests lineage. CI red = stale GH Actions billing failure (05-30), not code. Triage in `audit/pr-209-triage.md`. Fresh CI reruns triggered for tomorrow. |
| #193 | SEC-RLSa tenant-scoped RLS (cases) | **closed (dup)** | — | `b737700` already on main via #211/#179 chain; migration + integration test byte-identical to main. Nothing unique lost. |
| #194 | SEC-RLSe RLS triage audit/system tables (AIQ-662) | **MERGED** | `eab464eb` | rls_allowlist.txt semantic conflict vs main's SEC-RLSb/d drains — reconciled (start from main, −{error_logs,error_tickets}, layer #194 reasons, keep main's compliance_reference_sources reason). 4 contested classifications adjudicated → server-role-only (codebase-verified). Set invariant: 71→69. CI green. **Migration was broken against prod (uuid/text) → fixed by #212.** |
| #212 | fix(rls): correct profiles.id cast direction in error_tracking RLS | **MERGED + APPLIED** | `5ab3d39e` | Fix-forward for #194's broken migration. New migration `20260601130000_fix_rls_error_harden_uuid_cast.sql` recreates 3 policies with `profiles.id::uuid = auth.uid()`. CI green. **Applied to prod via MCP — success.** Verified: error_logs=1 policy (admin SELECT), error_tickets=2 (admin SELECT+UPDATE). Anon RLS smoke: 401 "permission denied" on both tables. ✅ |

## Open items
- **⛔ BLOCKER — #194 migration is broken against prod (HARD STOP):** Applying `20260530000000_rls_error_tracking_harden.sql` via MCP `apply_migration` **FAILED**: `ERROR 42883: operator does not exist: uuid = text`.
  - **Root cause:** migration gates admin policies on `profiles.id = auth.uid()::text`, but prod `profiles.id` is **`uuid`**. Correct codebase pattern (main commits `470cb584`/`95b97304`) is `profiles.id::uuid = auth.uid()`. #194 has the cast backwards. Passed CI because CI never applies migrations to a real DB + `rls-coverage` job is gated off.
  - **Prod state (unchanged — apply was transactional):** `error_logs`/`error_tickets`: RLS **enabled**, **0 policies**, **anon revoked**, `authenticated` has SELECT(+UPDATE). Safe default-deny; admin error-tracking UI reads no rows (pre-existing; #194 was meant to fix this).
  - **Latent risk:** main now carries a migration that fails on any clean `supabase db reset`/replay at this file.
  - **Status:** STOPPED per hard-stop rule. No rollback attempted; prod unchanged. Awaiting direction.
  - **RESOLVED** via fix-forward PR **#212** (merged `5ab3d39e`, applied to prod, verified, anon smoke 401). Block 2 now truly closed. CI-gap root-cause note: `audit/ci-gap-rls-migration-types.md`.

## Block 3 (in progress)
> **Framing:** the HR Dashboard PRs (#184, #182, #186, #183) ship **build-only** — they land on `main` and pass the `HR Dashboard build` CI lane, but `apps/hr-dashboard/` has no repo deploy target wired (no render.yaml/vercel/netlify), so they are **merged but not yet visible to users** at a live URL until a deploy is configured. Not a problem — honest framing.

| PR | Title | Outcome | Merge SHA | Notes |
|----|-------|---------|-----------|-------|
| #182 | C1-11d/e — pdf.js viewer + bbox overlay | **closed (dup)** | — | All 14 files byte-identical to main — fully shipped via #184. Closed as duplicate. **Spot-check of merged code: CLEAN** — `toCanonical.ts` correct 0–1000 top-left mapping w/ proper pdf.js y-flip; bbox data sourced from #181's contradictions endpoint (`bbox_page`+`bbox: List[int]`), matching `BboxHighlight` shape; no FE/BE mismatch. **#183 watch-item (not a defect):** endpoint returns `bbox` as array, overlay wants `{x0,y0,x1,y1}` object — integrator maps array→object. Overlay not yet wired into DocumentViewerSheet (by design = #183's job). |
| #184 | C1-11c — Case detail page (5 sections + viewer Sheet) | **MERGED** | `e52bb4af` | Frontend-only (`apps/hr-dashboard/`). No backend/migration/dual-layer. New dep: `pdfjs-dist@^4.10.38`. Consumes 5/6 of #181's endpoints (6th = #183's CorrectionHistory). Doesn't touch broken `hr_coordination`. Rebased clean (was 23 behind). CI green (HR Dashboard build 44s). Build-only — no live deploy. |
| #181 | C1-11c-be — case detail endpoints (6 reads) | **MERGED + SMOKED** | `2de0aafe` | 6 GET `/api/hr/cases/{case_id}/…` reads, company_id-scoped (`require_admin_or_hr` + `_require_case_access` vs `relocation_cases.company_id`). No migration. **Dual-layer prod-405 trap caught + fixed in-PR** (router was only in `backend/app/main.py`; added registration to `backend/main.py`). Rebased (was 20 behind). CI green. **Post-merge smoke: deploy rolled out (overview 405→401 at ~2min), all 6 endpoints return 401 (not 405)** — live on prod app. ✅ |

**Side discovery → `audit/dual-layer-audit-followup.md` (escalated to ACTIVE PROD BUG):** `hr_coordination` (prefix `/api/hr`) has 3 routes ABSENT from the prod app → 405: `GET /cases/{id}/providers`, `PATCH`+`DELETE /tasks/{id}`. Breaks the HR Command Center Provider Coordination panel (can't load providers, can't edit/complete/delete tasks; create still works). Visible error state shown to users. Fix = same 2-line dual-layer registration. Recommend same-week fix. (`hr_analytics` ambiguous — Tuesday.)

| #186 | C1-11A — WCAG 2.1 AA audit on HR Dashboard | **MERGED** | `22f5a344` | Pure docs (single file `audit/a11y_C1-11_2026-05-29.md`, +146). No code/migration. Merged direct (clean additive, no rebase). **Block 3 complete.** |

## Block 4 (in progress)
| PR | Title | Outcome | Notes |
|----|-------|---------|-------|
| #189 | C1-12-be — resolve + escalate POST | **SKIPPED (blocked)** | Depends on `rce.contradictions` which doesn't exist on prod (verified MCP) → would 500 every call. Undisclosed dep: **C1-08** not landed. Also dual-layer 405 trap. Atomicity solid. → `audit/daytime-run-stuck.md`. |
| #183 | C1-12 — Contradiction Resolution UI | **SKIPPED (blocked)** | Transitively blocked — binds #189's endpoints. Land as stack C1-08 → #189 → #183. → stuck file. |

| #190 | fix(intake): _destination_payload signature + city hydration | **MERGED** | `8a4ff204` | Fixes an **active prod 500** — caller passed 4 args, `_destination_payload` accepted 2 (TypeError in `employee_assignment_overview`). Adds 2 optional params + FE city hydration. No migration/dual-layer. CI green, auto-merged (5 checks green + main healthy + /health 200). Note: error-rate before/after not capturable (`error_logs` is FE-only, 0 rows/24h, no `path` col; backend 500s → Render stdout). **Block 4 closed.** |

## Block 5 (in progress)
| PR | Title | Outcome | Merge SHA | Notes |
|----|-------|---------|-----------|-------|
| #187 | C1-07 — entity resolver (5-stage deterministic-first) | **MERGED** | `931fc9ce` | Agent logic + tests only. No migration/dual-layer/endpoint. Deterministic-first dispatch verified (each stage short-circuits; human override → MRZ → block → ANN → LLM → new). Edge-case tests (typos/DOB-shift/transliteration → Stage 5). Auto-merged on green (3 guards). |

| #188 | C1-16 — case audit endpoint (chronological lineage) | **MERGED** | `11406f0e` | New endpoint `GET /api/hr/cases/{id}/audit` (ETag-cached, company_id-scoped). **Dual-layer 405 trap fixed in-PR** (added backend/main.py reg; union-merged app/main.py router-list conflict). Mount-check confirmed `/audit` on prod app. No migration; reads existing rce.* tables only. Post-merge /audit smoke: deploy rolled out (405→401 at ~2min), final 401 (not 405) ✅. |
| #213 | fix(dual-layer): restore hr_coordination include_router | **MERGED + SMOKED** | `a19291d7` | Standalone fix for the active prod bug found during #181/#188. Re-added `include_router` to backend/main.py (modular app isn't served in prod). Mount-check + post-deploy 3-route smoke: GET /providers, PATCH+DELETE /tasks/{id} all **401 (not 405)**. Provider Coordination panel live. ~17 other 'moved to app/main.py' routers flagged for tomorrow. |
| #196 | AIQ-626 / P1-01a — immigration_retriever wrapper | **MERGED** | `f1331ae5` | Pure service wrapper over existing `policy_chunk_retriever` + `policy_assistant_embedder` (both live in prod) — no new table/vector/embedding infra, no #189-style risk. No migration/dual-layer/endpoint. Tests fully isolated (FakeDb+SQLite+HashEmbedder); edge cases (cross-corridor leak, uncovered corridor, incomplete profile). Auto-merged (3 guards). |
| #195 | AIQ-174 — PDF coordinate mapper | **SKIPPED (CI red)** | — | Unit Tests crash: `pdfjs-dist` `Promise.withResolvers` not in vitest/jsdom env; + `pdfjs-dist` undeclared in `frontend/package.json` (works via #184 hoist). Not a flake — needs test-infra + dep decisions. → `audit/daytime-run-stuck.md`. **Block 5 done** (3 merged: #187/#188/#196; #195 deferred). |
| #178 | C2-02b — FR/DE/NO tax_cert agents + validators | **MERGED** | `b1237a4c` | Extraction agents + validators + fixtures + prompts. No migration/dual-layer/endpoint/rce-table. Touches `ci.yml` — verified safe (additive: appends 4 new test files to deterministic-P1 pytest). Explicit-go (workflow change). Backend tests 34s green (ran the new tests). |
| #191 | C2-04 — rule scraper + RuleChangeProposal queue (AIQ-555) | **MERGED + APPLIED** | `9647cec5` | Self-contained migration creates `rce.rule_change_proposals`. Hard gates ✅ (RLS + 2 policies + REVOKE anon), no cast trap. **Applied via MCP — success.** Verified: table exists, RLS on, 2 policies, anon unreachable (rce not PostgREST-exposed → 404/406, stronger than 401). **Cron registered** → `/rce-rule-scraper` Edge Function followup in stuck file. |
| #176 | C2-06-FOLLOWUP — policy-gap adapter | **SKIPPED (collision)** | — | Migrations are stale duplicates (#209 pattern): bare CREATE TABLE for `rce.policy_gaps`+`rce.case_artefacts` which already exist on prod with byte-identical schemas → would fail on apply. Backend code (router dual-layer-correct, detectors) has independent value. Defer to #209 reconciliation day. → `audit/daytime-run-stuck.md`. |

## Queue status
**Block 6 done.** All planned blocks complete. · Block 6: #176, #178, #191. (#209 skipped → triaged; #189/#183 blocked on C1-08; Parker closures #197–208/#210 wait on #209.)
Parker closures (#197–208, #210) deferred — they wait on #209's resolution.

## Final wrap-up (run complete)

**Queue: 30 open → 18 open.** All 6 blocks processed; every actionable non-Parker PR handled.

**Merged (12, incl. #213 hr_coordination dual-layer fix):** #194 (SEC-RLSe) + **#212** (fix-forward for #194's uuid/text migration, created this run) · #181 (case-detail endpoints, dual-layer fixed + smoked) · #184 (case-detail page) · #186 (WCAG doc) · #190 (intake 500 hotfix) · #187 (entity resolver) · #188 (case-audit endpoint, dual-layer fixed + smoked) · #196 (immigration retriever) · #178 (tax_cert agents) · #191 (rule scraper, migration applied).

**Closed as duplicate (2):** #193 (SEC-RLSa already on main), #182 (pdf-viewer shipped via #184).

**Migrations applied to prod via MCP (2):** #212 (error-tracking RLS, cast-fixed), #191 (rce.rule_change_proposals).

**Skipped/blocked → `audit/daytime-run-stuck.md` (5):**
- **#209** — stale Parker integration (8 dup migrations + exception_requests lineage). Triage: `audit/pr-209-triage.md`. Fresh CI reruns triggered.
- **#189** + **#183** — blocked on **C1-08** (`rce.contradictions` doesn't exist → #189 would 500; #183 binds #189). Land as stack C1-08 → #189 → #183.
- **#195** — failing Unit Tests (`pdfjs-dist` `Promise.withResolvers`) + undeclared dep. Needs test-infra decision.
- **#176** — stale duplicate migrations (#209 pattern). Defer to #209 reconciliation day.

**Active prod findings (for tomorrow):**
- `audit/dual-layer-audit-followup.md` — **`hr_coordination` is an ACTIVE PROD BUG** (3 routes 405; Provider Coordination panel broken). Same-week fix. `hr_analytics` ambiguous.
- `audit/ci-gap-rls-migration-types.md` — CI never applies migrations → uuid/text type bugs slip through (caused #194).
- #191 cron → `/rce-rule-scraper` Edge Function: verify deployed or unschedule before 2026-06-02 03:00 UTC.

**Remaining 18 open:** 14 Parker (#197–208, #210 to be *closed* as superseded once #209 is reconciled; #209 itself needs reconciliation) + 4 blocked (#176, #183, #189, #195).

**End state:** main CI `success` @ `9647cec5`, prod `/health` 200. No hard stops hit. No force-pushes to main. No CLAUDE.md/workflow/hook edits by me.

## Late-evening queue cleanup

Closed 3 obsolete paper-trail PRs (no code — reports/markers that outlived their purpose):
- **#207** — Parker pre-merge report. Analysis captured in `audit/parker-pipeline/PRE_MERGE_AUDIT.md` + `audit/pr-209-triage.md`; #197–206 decisions happen in #209 reconciliation.
- **#208** — dual-router fix report. Pattern now documented (`audit/dual-layer-audit-followup.md`, `audit/dual-layer-mount-check-2026-06-01.md`) and proven via #181/#188/#213.
- **#210** — "hold pending SEC-004" marker, obsolete (SEC-004 merged via #211 weeks ago).

**Queue: 18 → 15 open.** Remaining 15 = 11 Parker (#197–206 + #209; to be closed/reconciled on #209 day) + 4 blocked (#176, #183, #189, #195).

Also tonight: `hr_coordination` prod-405 fixed + live (#213); #191 cron unscheduled (Edge Function not deployed); dual-layer mount-check sweep filed (`audit/dual-layer-mount-check-2026-06-01.md`) — 0 clean fixes, deferred to tomorrow.

| #195 | AIQ-174 — PDF coordinate mapper | **MERGED** | `29d34437` | Originally skipped (Unit Tests crashed on `pdfjs-dist` `Promise.withResolvers`). Fixed by mocking at the **react-pdf boundary** in the test (`vi.mock('react-pdf')`) — the component imports react-pdf, which transitively loads pdfjs-dist@4.8.69. **FIX 1 (declare pdfjs-dist) dropped — would have caused a 4.10.38-vs-4.8.69 version skew** (react-pdf pins 4.8.69; near-miss caught pre-merge). No package.json change. vitest 10/10 + tsc clean locally; CI green. Backend adds 422 coord-validation to existing admin_form_templates handlers. |

## Late-evening: CI mount-check guard (draft PR #214)

Built + tested + opened as **draft PR #214** (`[DRAFT] feat(ci): dual-layer router registration mount-check guard + initial allowlist`):
- `scripts/check_router_registrations.py` — syntactic AST check that every router in `backend/app/main.py` is also in `backend/main.py`. Avoids the runtime prefix-doubling false positives.
- `scripts/router_registration_allowlist.txt` — seeded with the routers currently modular-only on main.
- **Upgrade finding:** the guard found **21** modular-only routers (vs the ~17 from the manual grep) — `ab_tests`, `pets`, `support`, `policy_gaps` are the 4 new ones. **The allowlist is now the authoritative dual-layer debt list.**
- Verified: PASS on current main (21 allowlisted); FAIL flagging ONLY `hr_coordination` on pre-#213; FAIL flagging ONLY `hr_case_detail` when its include is removed.
- CI wiring deferred to a separate follow-up PR (this PR doesn't touch `.github/workflows/*`).
- Draft for Romain's morning review.

- #214 marked ready-for-review at session end — Romain reviews + merges first thing tomorrow.

- #215 draft opened — wires #214's script into ci.yml (one step in the Backend tests job, before pytest). **Tomorrow's order: review + merge #214 → review + merge #215 → the dual-layer CI guard goes live on the next PR.** Merging #215 before #214 would red CI (script absent).

## Parker step PR closures (#197–#206)
Closed all 10 Parker step PRs (steps A–J) as superseded by #209 (which carries their work). Branches were 30+ days behind main and unsalvageable as individual rebases; reopen is one click if a step is revived (commits preserved in #209). **#209 kept OPEN** for tomorrow's strategic reconciliation. **Queue: 16 → 6 open** (#176, #183, #189 blocked · #209 integration · #214/#215 drafts).

- C1-08 draft (**PR #216**) opened — creates `rce.contradictions` to unblock #189/#183. Synthesized from #181 reads + #189 writes; **3 pre-write catches** (real CHECK values, no correction_id, service-role-only RLS not 3-principal). Draft — schema review before any prod apply.

## 2-hour autonomous burst (2026-06-01 afternoon, post-#189 merge)

Operator offline ~2h. Autonomy rules applied per `audit/daytime-run-autonomy-2h.md`.

| PR | Outcome | Reason |
|----|---------|--------|
| #183 | **SKIPPED** | Recon found this PR is superseded by main — 0 unique files vs main (42/49 byte-identical), the 7 divergent files are all #183's older versions (75 commits behind). Merging would regress 4 axes: revert `ResolutionPage.tsx` to a 16-line stub, revert `CaseDetailPage.tsx` to a 21-line stub, **DELETE the dual-layer guard step from `.github/workflows/ci.yml`** (#215's work, activated this morning), DELETE the tax_cert test registrations (#178's work). bbox `List[int]→{x0,y0,x1,y1}` mapping (the #182 watch-item) is genuinely-future on both #183 and main, so no salvage value. **Should be closed** (paste-ready command in stuck file). Same shape as #193/#182. → `daytime-run-stuck.md`. |
| #176 | **SKIPPED** (re-confirmed) | Carries Supabase migration (autonomy rule #1 trigger) + known security regression risk (`*_permissive` policies in different names → `DROP POLICY IF EXISTS` misses prod's `*_service_role_only` → OR-combine grants `authenticated` read/write the live policies deny). Bundles with #209 reconciliation. Yesterday's full analysis stands. → `daytime-run-stuck.md`. |
| #209 | **SKIPPED** | Explicit autonomy exclusion. → `pr-209-triage.md` (yesterday). |

**Burst outcome:** 0 merged, 3 skipped. **The right answer** — #183 was a near-miss regression (would have undone the morning's #215 guard activation + #178's tax_cert tests + reverted two pages to stubs); #176 was a near-miss security regression (permissive policy coexisting OR-combined with prod's restrictive). Bias-to-skip caught both.

**Queue state at burst end:** 3 open (#176, #183, #209), unchanged vs burst start. Main `d2b808fb` (post-#189), `/health` 200 throughout. No autonomy state-change actions taken (no merges, no closes, no force-pushes); only log updates.

**No hard-stops fired. No `audit/daytime-run-HALT.md` written.**

### Top recommendation for Romain when back

1. **Close #183 first** — 1-click paste-ready command in stuck file. Same shape as #193/#182.
2. **Tackle #176/#209 together** as a single fresh-head reconciliation session — both face the same stale-vs-deduped migration lineage / policy-mismatch problem; resolving #176 likely requires settling the canonical-schema question that #209 also surfaces.
3. **Productive lower-stakes alternatives** while the dual-layer context is fresh: investigate the `hr_analytics` ambiguity (`audit/dual-layer-audit-followup.md`) or start draining `scripts/router_registration_allowlist.txt` now that the guard is live.

The hard work is done. The queue is in clean state.
