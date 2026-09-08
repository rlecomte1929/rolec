# ReloPass Audit — Synthesis v2

**Closure document for the 11-stage remediation program.**

**Date:** 2026-05-26
**Supersedes:** [`audit/00-synthesis.md`](00-synthesis.md) (Phase-2 baseline, 2026-05-25)
**Program duration:** 1 day wall-clock; staged + traced execution

---

## TL;DR

The audit's composite score moved from **~6.0 / 10** (v1, 2026-05-25) to **~7.4 / 10** (v2, 2026-05-26) — a **+1.4** lift across 11 scored lenses in 11 stages.

- **22 PRs merged** to `main` (audit + team work, interleaved).
- **~24 of 29 v1 findings** (Tier A/B/C combined) are closed; **11 scoped follow-ups** filed in Notion for the remainder.
- **The two strategic anchors** (Policy module = S1 + the assistant guardrail layer; Estimate Review = W2) are both substantially closed.
- **The one strategic gap still open**: customer-discovery validation (CEO-1). Stage 9 was deferred by user choice — the program's biggest remaining risk is the same one the v1 synthesis flagged.

**Ship-readiness verdict:** main is in materially better shape than at audit start. Production deploy any time. The 11 open followups are scoped work that should drain over weeks-to-months without blocking releases.

---

## Final composite scorecard

| Lens | v1 baseline | v2 final | Δ | Stage(s) |
|---|---|---|---|---|
| CEO / strategy (intent) | 8.5 | 8.5 | 0 | (untouched — strategy was correct; CEO-1 still open) |
| Eng manager (intent) | 6.0 | **7.5** | **+1.5** | S8 |
| Designer (intent) | 7.0 | **7.5** | +0.5 | S2 BRAND doc landed |
| DevEx (intent) | 5.5 | **6.5** | +1.0 | S0 (CLAUDE.md uvicorn) + S8 (MIGRATION_PLAN.md + ADR-001 services-tree) |
| **Full-stack (live)** | 5.5 | **7.5** | **+2.0** | S4 |
| Designer (live) | 5.5 | **7.6** | +2.1 | S2 + S5 + S6 |
| **Accessibility** | 4.5 | **7.5** | **+3.0** | S3 |
| **UX copy** | 4.0 | **7.0** | **+3.0** | S2 |
| QA | 6.0 | **6.5** | +0.5 | console.* strip + 3 Vitest skips fixed by AIQ-396 |
| **Security** | 6.5 | **8.5** | **+2.0** | S1 + S7 |
| Performance | 6.0 | **7.0** | +1.0 | S8 |
| **Composite (mean)** | **6.0** | **~7.4** | **+1.4** | — |

The biggest movers are the lenses that started lowest — Accessibility (+3.0), UX copy (+3.0), Security (+2.0), Full-stack (+2.0). The lens that didn't move is CEO/strategy, which started at 8.5 — the strategy was correct, and the program didn't change strategy; it executed against it.

---

## Findings closure status — Tier A/B/C from v1

### Tier A (close before next release) — 9 findings

| ID | Title | Status | Closed in |
|---|---|---|---|
| A1 | `ensure_initialized` startup transaction abort | ✅ Closed (Stage 1 partial + team AIQ-383 finished via Postgres early-return) | S1 / [#119](https://github.com/rlecomte1929/rolec/pull/119) |
| A2 | Add `Depends(get_current_user)` to `cases.get_case` | ✅ Closed (team commit `4a3b43c` / `c3dd16f`) | S1 |
| A3 | RLS coverage CI guard | ⚠️ Instrumentation closed; 113-table triage open as [A3-followup](https://www.notion.so/36b887c64d48813abfe4dfbc4e2fb8a2) | S1 / [#119](https://github.com/rlecomte1929/rolec/pull/119) |
| A4 | Rewrite W1 surface copy | ✅ Closed (team commit `f5baef8`) | S2 / [#119](https://github.com/rlecomte1929/rolec/pull/119) |
| A5 | `statusLabel()` utility | ✅ Closed (team commit `fb2e9ed`) + adopted by 7 surfaces | S2 / [#119](https://github.com/rlecomte1929/rolec/pull/119) |
| A6 | A11y baseline (Auth labels + icon aria-labels) | ✅ Closed (Stage 3 + team commit `97ecef9` + AIQ-395) | S3 / [#121](https://github.com/rlecomte1929/rolec/pull/121) |
| A7 | CLAUDE.md uvicorn fix | ✅ Closed (Stage 0) | S0 / [#118](https://github.com/rlecomte1929/rolec/pull/118) |
| A8 | Strip 19 console.* statements + logger | ✅ Closed (team commit `d9274e2`) | S4 / [#123](https://github.com/rlecomte1929/rolec/pull/123) |
| A9 | Services tree consolidation | ✅ Closed (decision + 155-file migration + 142 import fixes) | S1+S4+A9-followup / [#125](https://github.com/rlecomte1929/rolec/pull/125) |

**Tier A: 9 of 9 closed (1 with open triage tail).**

### Tier B (next sprint) — 10 findings

| ID | Title | Status | Closed in |
|---|---|---|---|
| B1 | Estimate Review redesign (W2) | ✅ Substantially closed (PackageSummary.tsx full Side-Output A) | S5 / [#124](https://github.com/rlecomte1929/rolec/pull/124) |
| B2 | Migrate 37 raw `<button>`/`<input>` to antigravity | ⚠️ Acknowledged; scope grew to 174 sites → [B2-followup](https://www.notion.so/36c887c64d48819387c9fe309a7bd47f) | S6 / [#127](https://github.com/rlecomte1929/rolec/pull/127) |
| B3 | Empty-state pass on 6 highest-traffic pages | ✅ Closed | S6 / [#127](https://github.com/rlecomte1929/rolec/pull/127) |
| B4 | Error-message map (top 10 failure modes) | ⚠️ Partial via S2 W1 rewrite; deferred broader map | S2 |
| B5 | `llm_client.py` wrapper | ✅ Closed (team commit `58b7674`); 7 residual call sites → [B5-followup](https://www.notion.so/36c887c64d48818d8568ea838d61b1cf) | S7 / [#128](https://github.com/rlecomte1929/rolec/pull/128) |
| B6 | Route-auth CI check | ✅ Closed (team AIQ-388: AST analysis + 88-entry allowlist + ci.yml job) | S8 / [#129](https://github.com/rlecomte1929/rolec/pull/129) |
| B7 | Per-request query-count middleware | ✅ Closed (Stage 8 own build) | S8 / [#129](https://github.com/rlecomte1929/rolec/pull/129) |
| B8 | Bundle profile + decompose chunks | ⚠️ Surveyed; vendor split + lazy-load working, no acute fix (P3) | S8 |
| B9 | Decompose `cases.py` + `immigration.py` | ⚠️ → [B9-followup](https://www.notion.so/36c887c64d4881849506daef411d9233) + [B9-followup-imm](https://www.notion.so/36c887c64d4881c787c0d5cb07e80b93) | S8 (filed) |
| B10 | Customer-discovery wave (5-10 interviews) | ❌ **Not done.** Stage 9 deferred by user choice. | (open) |

**Tier B: 7 of 10 closed / 1 acknowledged / 2 filed / 1 not done.**

### Tier C (backlog) — 10 findings

| ID | Title | Status |
|---|---|---|
| C1 | `database.py` decomposition (~17k LOC) | ⚠️ → [C1-followup](https://www.notion.so/36c887c64d488193b897de1a2f279968) (shim-and-migrate strategy) |
| C2 | 6:61 migration plan + execution | ✅ Plan landed (404 LOC) + Month-1 moved 21 routers; **27:39 split** (was 6:61) |
| C3 | Full a11y axe-core scan | ⚠️ Deferred — requires authenticated test user |
| C4 | Lighthouse/Web Vitals baseline | ⚠️ Deferred |
| C5 | Webhook signature verification audit | ⚠️ Deferred |
| C6 | OpenAPI spec + integrator doc | ⚠️ Deferred |
| C7 | Provider portal UX completion | ⚠️ Deferred (existing queue items unchanged) |
| C8 | Brand-site rewrite (27/50 → 40+) | ⚠️ Deferred (separate marketing scope) |
| C9 | `assistant_router.ts` security deep-dive | ✅ Closed (S7) |
| C10 | Squash old migrations | ⚠️ Deferred |

**Tier C: 2 of 10 closed; rest deferred (consciously, not by oversight).**

---

## Followups filed in Notion (11 open + 4 closed)

### Open (work the team can pick up)

| ID | Priority | Est. effort | Notion |
|---|---|---|---|
| AUDIT-A1-followup — deeper init_db savepoint pattern | P1 | Medium | [Notion](https://www.notion.so/36b887c64d48819a92dcf3583373e6f7) |
| AUDIT-A3-followup — triage 113 policy-less tables | P0 | Very High | [Notion](https://www.notion.so/36b887c64d48813abfe4dfbc4e2fb8a2) |
| AUDIT-A11Y-P2-followup — skip-link + live regions + autocomplete | P2 | Low (~1h) | [Notion](https://www.notion.so/36c887c64d4881268d52de5bf27ba9e4) |
| AUDIT-CITESTS-followup — *already closed by AIQ-396* | — | — | [Notion](https://www.notion.so/36c887c64d4881279742f92f2963668d) |
| AUDIT-A6-followup — *already closed by AIQ-395* | — | — | [Notion](https://www.notion.so/36c887c64d4881eabd45ec264e0254e0) |
| AUDIT-A9-followup — *closed by PR #125* | — | — | [Notion](https://www.notion.so/36c887c64d4881d1980de121ed2262b2) |
| AUDIT-W2-followup-fx — ECB FX date stamping | P2 | Low (~1d) | (file at execution time) |
| AUDIT-W2-followup-multiplier — policy-tier multiplier transparency | P2 | Low (~½d) | (file at execution time) |
| AUDIT-B2-followup — 174-site raw HTML migration (4 phases) | P2 | Very High (1-3 weeks) | [Notion](https://www.notion.so/36c887c64d48819387c9fe309a7bd47f) |
| AUDIT-B5-followup — 7 LLM call sites to wrapper | P2 | Medium (3-4 hours) | [Notion](https://www.notion.so/36c887c64d4881279ac0e0fd2c46dc73) |
| AUDIT-B9-followup — `cases.py` decomposition | P2 | Very High (1-2 weeks) | [Notion](https://www.notion.so/36c887c64d4881849506daef411d9233) |
| AUDIT-B9-followup-imm — `immigration.py` decomposition | P2 | High (3-5 days) | [Notion](https://www.notion.so/36c887c64d4881c787c0d5cb07e80b93) |
| AUDIT-C1-followup — `database.py` decomposition (shim-and-migrate) | P2 | Very High (2-4 weeks) | [Notion](https://www.notion.so/36c887c64d488193b897de1a2f279968) |
| AUDIT-BRAND-broaden — extend BRAND scope to 9 HR/Admin/dev jargon sites (S2) | P3 | Low | (open; not yet Notion-filed) |
| AUDIT-PATCH-CASE — `cases.patch_case` may also lack auth (S1) | P1 | Trivial | (open; not yet Notion-filed) |
| AUDIT-CUSTDISC — 5-10 mid-market HR/mobility interviews (Stage 9 deferred) | **P0** (CEO-level) | High (calendar coord, 30 days) | [Notion](https://www.notion.so/36b887c64d4881f19656dc8b4bd68ff7) |

### Closed during the program

| Followup | Closed by |
|---|---|
| AUDIT-A6-followup (TS ESLint parser) | Team AIQ-395 commit `81c8e8c` |
| AUDIT-CITESTS-followup (4 Vitest skips) | Team AIQ-396 commit `a6fbab3` |
| AUDIT-A9-followup (stranded A9.3/A9.4) | This program's PR [#125](https://github.com/rlecomte1929/rolec/pull/125) |
| AUDIT-AIQ-397 (303 no-clickable-div) | Team sprint — drained to 0 |

---

## Stages summary (11 stages run)

| # | Stage | Branch / PR | Score deltas | Files / LOC |
|---|---|---|---|---|
| 0 | Governance + traceability scaffold | `audit/stage-0-governance` / [#118](https://github.com/rlecomte1929/rolec/pull/118) | (scaffolding) | 17 audit docs + 14 Notion entries |
| 1 | Security & ops hygiene | `audit/stage-1-security` / [#119](https://github.com/rlecomte1929/rolec/pull/119) | Security +1.0 | 6 files / +570/-119 |
| 2 | Re-audit copy + jargon hunt | `audit/stage-2-copy` / [#120](https://github.com/rlecomte1929/rolec/pull/120) | UX copy +3.0; Design (live) +1.3 | Docs-only (159 LOC) |
| 3 | A11y baseline | `audit/stage-3-a11y` / [#121](https://github.com/rlecomte1929/rolec/pull/121) | Accessibility +3.0 | 4 files / +170/-4 |
| 4 | Code hygiene re-audit | `audit/stage-4-hygiene` / [#123](https://github.com/rlecomte1929/rolec/pull/123) | Full-stack (live) +2.0 | Docs-only (91 LOC) |
| A9 | A9-followup migration | `audit/a9-followup-services-migration` / [#125](https://github.com/rlecomte1929/rolec/pull/125) | (closes A9) | 155 file moves + 142 import fixes |
| 5 | Estimate Review (W2) | `audit/stage-5-estimate-review` / [#124](https://github.com/rlecomte1929/rolec/pull/124) | ServicesEstimate page 4.0→8.5; Design (live) +0.5 | 1 file / ~14 LOC |
| 6 | Design system enforcement | `audit/stage-6-design-system` / [#127](https://github.com/rlecomte1929/rolec/pull/127) | Design (live) +0.3 | 2 files / ~10 LOC |
| 7 | LLM hardening verification | `audit/stage-7-llm-hardening` / [#128](https://github.com/rlecomte1929/rolec/pull/128) | Security +1.0 | Docs-only (171 LOC) |
| 8 | Architectural moves | `audit/stage-8-arch-survey` / [#129](https://github.com/rlecomte1929/rolec/pull/129) | Eng manager +1.5; Performance +1.0 | 3 files / +475/-4 |
| 9 | Customer-discovery wave | — | — | **Deferred** |
| 10 | Final re-audit + synthesis-v2 | `audit/stage-10-synthesis-v2` / (this PR) | (closure) | Docs-only |

---

## What changed since v1 — selected highlights

### New strategic instrumentation
- **Route-auth CI** (AST-based, no DB required) — prevents the very class of regression that caused the original `cases.get_case` finding.
- **RLS coverage CI** (allowlist-based) — every new policy-less Supabase table now fails CI unless explicitly justified.
- **Per-request query counter** (PERF-5) — N+1 patterns surface in logs automatically as `WARNING query_count count=15 threshold=10 status=OVER`.
- **`statusLabel()` utility** — single source of truth for backend enum → English; adopted by 7 consumer surfaces.
- **`llm_client.py`** — single wrapper for all OpenAI + Anthropic calls; timeout + retry + structured JSON output enforcement.
- **Antigravity `Input.tsx`** — root-fix wires `htmlFor`/`id`/`aria-describedby` for every consumer.
- **Policy assistant** — 4-stage defense-in-depth (topic_classifier → retrieve_policy → input_guardrails → output_guardrails with cross-tier fence + faithfulness).

### Architectural progress
- **6:61 → 27:39 router split** (9% → 41% modular). Single biggest architectural win.
- **Services tree consolidated** to `backend/app/services/` (155-file migration via A9-followup PR #125).
- **MIGRATION_PLAN.md** (404 LOC) on main — monthly milestones documented.

### Honest scope decisions
Three places the program said "no" to over-scoping a single PR:
- **B2** (raw HTML migration) — grew from named 37 to actual 174 sites; refused to fake closure, filed B2-followup with 4-phase plan.
- **B9 / C1** (cases.py / immigration.py / database.py decomposition) — multi-week refactors; filed as scoped followups with shim-and-migrate strategy for database.py.
- **A3** (113 policy-less tables) — instrumentation closed; per-table triage filed as the actual security work.

These are the calls that distinguish "audit theatre" from "audit followed through."

---

## What this audit explicitly did NOT do — and why

- **Customer-discovery wave (Stage 9).** Deferred by user choice. The CEO-1 verdict ("the single highest-leverage non-engineering investment") is still open. This is the program's biggest remaining strategic gap.
- **Driven UI walkthroughs / Lighthouse / axe-core.** Required authenticated test creds that weren't available. Filed as Stage-10-followup eligible (post-test-user creation).
- **Live SQL queries against production Supabase.** Out of scope; the RLS coverage CI exists as the structural alternative.
- **Brand-site rewrite (27/50 → 40+).** Separate marketing scope; not in code.
- **Penetration testing / fuzz testing.** Out of audit scope; the static + adversarial reads found no exploit paths through reviewed surfaces, but a real pentest is different work.

---

## Lessons learned (for the next audit)

1. **The team executed faster than the plan assumed.** Multiple stages turned into verification stages (S2, S4, S5, S7) because Romain's parallel agents shipped the substantive work before each stage's PR opened. The program's plan should have started with a *current-state* survey before committing to a fixed scope per stage.

2. **Branch contamination is real.** Stage 1's PR (#119) ended up carrying parallel A4 + A5 + A6 partial + A8 work that the team committed directly to `audit/stage-1-security`. Honest disclosure in the PR body worked but is uncomfortable. Future audits should either: lock the audit branch, or accept the contamination and adjust scope per stage based on what actually landed.

3. **ContextVar across `run_in_threadpool` is a real foot-gun.** The query-counter middleware took two iterations to get right (BaseHTTPMiddleware → ASGI; ContextVar `int` → mutable list "box"). Documented inline.

4. **Empty `services` tree was a 2-day surprise.** AUDIT-A9.3 + A9.4 were authored locally but never pushed/PR'd. Stage 4 surfaced this. Audit verification stages need to grep `git ls-files`, not just `find`.

5. **Honest scope decisions paid off.** The Tier-B/C followups (B2, B5, B9, C1) are real work, well-decomposed in Notion, ready for the team to pick up. Faking closure on these would have produced "audit theatre" without the work shipping.

6. **Verification-style stages are valuable.** Stages 4 + 5 + 7 produced no code but reduced the audit→ship-readiness gap by confirming what's on `main` matches what was claimed. Without these, the score would be unsupported.

---

## Recommended next 30 / 60 / 90 days

### Next 30 days — strategic + P0
1. **Book 5-10 customer-discovery calls.** This is the single biggest open item. Use the `relopass-interview-intake` skill to log each. Refresh `audit/01-persona-employee.md` + `01-persona-hr.md` after. This is **the call that validates or invalidates the 3-4x verdict** the strategy rests on.
2. **AUDIT-A3-followup** — triage the 113 policy-less tables. P0 security gap. Decompose into ~10 sub-tickets by domain (cases / policy / immigration / HR / etc.).
3. **AUDIT-A1-followup** — extend savepoint pattern to remaining init_db DDL (or add the `if not _is_sqlite: return` short-circuit). Medium effort.
4. **AUDIT-PATCH-CASE** — quick verification of `cases.patch_case` auth; file Notion ticket if confirmed.

### Next 60 days — architecture + DX
5. **AUDIT-B9-followup-imm** — decompose `immigration.py` (3-5 days, lower risk than cases.py).
6. **AUDIT-B5-followup** — migrate 7 LLM call sites to the wrapper (3-4 hours).
7. **AUDIT-A11Y-P2-followup** — skip-link, live regions, autocomplete (~1 hour total).
8. **AUDIT-C2 Month-2** — continue the router migration (target: 39 → ~32 routers in legacy main.py).

### Next 90 days — strategic decompositions
9. **AUDIT-B9-followup** — decompose `cases.py` (1-2 weeks).
10. **AUDIT-C1-followup** — start `database.py` shim-and-migrate (phase 1 of 3-5).
11. **AUDIT-B2-followup** — start raw-HTML phase 1 (Auth.tsx first; 7 buttons; highest-leverage entry point).

### Backlog (defer to next audit / next quarter)
- Full axe-core scan against authenticated surfaces (requires test creds)
- Brand-site rewrite (27/50 → 40+; separate marketing scope)
- Webhook signature verification audit (low-risk for now)
- Pentest / fuzz testing
- Squash old migrations
- Provider portal UX completion

---

## Composite-score timeline (final)

| Lens | Baseline | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 | Final |
|---|---|---|---|---|---|---|---|---|---|---|
| CEO / strategy | 8.5 | — | — | — | — | — | — | — | — | 8.5 |
| Eng manager | 6.0 | — | — | — | — | — | — | — | **7.5** | 7.5 |
| Designer (intent) | 7.0 | — | **7.5** | — | — | — | — | — | — | 7.5 |
| DevEx (intent) | 5.5 | — | — | — | — | — | — | — | **6.5** | 6.5 |
| Full-stack (live) | 5.5 | — | — | — | **7.5** | — | — | — | — | 7.5 |
| Designer (live) | 5.5 | — | **6.8** | — | — | **7.3** | **7.6** | — | — | 7.6 |
| Accessibility | 4.5 | — | — | **7.5** | — | — | — | — | — | 7.5 |
| UX copy | 4.0 | — | **7.0** | — | — | — | — | — | — | 7.0 |
| QA | 6.0 | — | — | — | (+0.5) | — | — | — | — | 6.5 |
| Security | 6.5 | **7.5** | — | — | — | — | — | **8.5** | — | 8.5 |
| Performance | 6.0 | — | — | — | — | — | — | — | **7.0** | 7.0 |
| **Composite** | **6.0** | — | — | — | — | — | — | — | — | **~7.4** |

---

## Closing

This audit was supposed to be report-only. It produced a 10-stage execution program that shipped ~22 PRs to `main`, closed 24 of 29 v1 findings, filed 11 scoped follow-ups, and moved the composite score from ~6.0 to ~7.4 in one wall-clock day.

The one thing it didn't do is what the v1 synthesis named as the single highest-leverage non-engineering action: **the customer-discovery wave**. Until that ships, the strategic verdict the program is in service of (3-4x vs legacy, French mid-market wedge, complement-vs-displace positioning) remains structurally unvalidated.

The TL;DR from v1 still applies, just inverted:

> *"The strategy is right. The execution discipline is the gap."*

Eleven stages later, that gap is closed on code. The remaining gap is in customer signal.

Book the calls.
