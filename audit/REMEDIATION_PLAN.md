# Remediation Plan — Staged, Traced, Re-Audited

**Status:** Approved-for-Stage-0 pending user green-light.
**Mode of operation:** One stage at a time. No stage starts until the previous is merged + canary-clean. Every stage produces a re-audit doc proving the score moved in the right direction.
**Author:** This file is the canonical staging plan. `audit/STAGES.md` is the rolling outcome log (created when Stage 1 begins).

---

## Why this structure

The synthesis (`audit/00-synthesis.md`) lists 29 findings across Tier A/B/C punch lists. Two failure modes to avoid:

1. **Big-chunk burnout** — trying to fix 9 Tier-A items in one branch produces a PR no one can review.
2. **Untraced drift** — fixing without re-auditing means you can't tell whether the audit score improved or regressed.

This plan groups findings into **10 stages**, each:
- Small enough to land in one working session.
- Independently shippable + revertable.
- Has its own re-audit step using the matching expert lens.
- Produces a traceable artifact set: branch + PR + Notion work-queue entry + re-audit doc.

---

## Universal stage protocol (applies to every stage 1–10)

Every stage runs this exact pipeline. Treat it as a checklist.

| Step | Tool / skill | Output |
|---|---|---|
| 1. Mark chapter | `mcp__ccd_session__mark_chapter` | Visible chapter in transcript |
| 2. Create branch | Bash `git checkout -b audit/stage-N-<slug>` | Branch off `main` |
| 3. Create or update Notion work-queue entries | `mcp__notion-create-pages` against AI Work Queue DB (`75d7ed78-...`) | One row per finding, with Priority + Complexity + Validation Criteria fields populated |

> **Superseded 2026-08-18.** _(that database is now titled “AI Work Queue (RETIRED)”; the live queue is `3bc887c6-4d48-8089-8188-fcf2dc3edc1b` / data source `4e2887c6-4d48-82c1-931e-87b09fb5c4ed`.)_ New entries go to the live queue; the id above records the plan as originally written.

| 4. Spawn task tree | `TaskCreate` per atomic action; `TaskUpdate` in_progress / completed as we go | Visible in harness UI |
| 5. Implement | `Read` / `Edit` / `Write` | Code changes |
| 6. Sanity check | `Bash` — `npm run build` (frontend) + `pytest` (backend) + `tsc --noEmit` | All green |
| 7. Independent second opinion | `/codex review` | Pass/fail gate |
| 8. Pre-landing diff review | `/review` | Issues flagged |
| 9. Mini re-audit (stage-specific) | Skill named in the stage row (e.g. `/cso` for Stage 1) | `audit/re-audit-stage-N.md` with score delta vs Phase-2 baseline |
| 10. Update STAGES.md | `Edit audit/STAGES.md` | Append row with: stage, finding IDs closed, score delta, PR URL, Notion URLs |
| 11. Ship | `/ship` | PR created |
| 12. User reviews + merges | (manual) | PR merged |
| 13. Deploy + canary | `/land-and-deploy` then `/canary` | Production health confirmed |
| 14. Retro learnings | `/learn` (optional) | Anything worth remembering |

**Gate after each stage:** user types "go stage N+1" or "pause". No stage auto-chains into the next.

**Safety nets:**
- `/freeze` to scope edits to the relevant directory during code-touching stages.
- `/careful` mode when touching production data / migrations.
- `/guard` = both, for the riskier stages (Stage 7 LLM hardening, Stage 8 architectural moves).

---

## Stage map (overview)

| # | Stage | Theme | Effort | Risk | Re-audit skill |
|---|---|---|---|---|---|
| **0** | **Governance + traceability scaffold** | Setup | 30 min | None | n/a — this is the scaffolding itself |
| **1** | Security & ops hygiene (A1, A2, A3, A7) | Quick wins | 1 day | Low | `/cso` daily mode |
| **2** | Employee-facing copy + W1 surface (A4, A5) | User-visible value | 1 day | Low | `/design-review` report-only + `design:ux-copy` + `relopass-brand-voice` |
| **3** | A11y baseline (A6 + ESLint rule) | Compliance / quality | 1 day | Low | `design:accessibility-review` |
| **4** | Code hygiene (A8, A9) | Maintainability | 1 day | Low-medium | `/health` + `/simplify` |
| **5** | Estimate Review redesign (B1) | The value-prop surface | 1 week | Medium | `/plan-design-review` → `/design-shotgun` → `/design-html` → `/design-review` |
| **6** | Design system enforcement (B2, B3, B4) | Visual consistency | 1 week | Low-medium | `/design-review` + `design:design-system` |
| **7** | LLM hardening (B5 + retrofits) | Reliability + security | 3 days | Medium | `/cso` + `/codex challenge` against the wrapper |
| **8** | Architectural moves (B6, B7, B8, B9, ENG-1 migration plan) | Tech debt | 2 weeks | High | `Plan` agent → `/codex consult` → `/benchmark` before/after |
| **9** | Customer discovery wave (B10) | Strategic — non-code | 30 days | n/a | `relopass-interview-intake` per call; refresh `01-persona-*.md` |
| **10** | Full re-audit + ship-readiness | Closure | 1 day | None | Re-run the entire audit; produce `00-synthesis-v2.md` and compare |

---

## Stage 0 — Governance & traceability scaffold (do this first)

**Goal:** stand up the bookkeeping so every later stage has a place to land. No code changes outside the audit/ directory + CLAUDE.md.

**Atomic actions:**
1. Fix CLAUDE.md uvicorn command (A7 — the trivial 5-minute item; included here because it's pure docs).
2. Create `audit/STAGES.md` rolling log skeleton.
3. Create one Notion AI Work Queue page per Tier-A finding (A1, A2, A3, A4, A5, A6, A8, A9) using `mcp__notion-create-pages`. Each page populates: Task Title, Priority, Estimated Complexity, Strategic Objective, Expected Output, Technical Constraints, Validation Criteria, Context Links (linking to `audit/02-expert-*.md` source files).
4. Create one Notion page per Tier-B item that is currently NOT in the queue (statusLabel utility, llm_client wrapper, route-auth CI check, etc. — list from synthesis "Newly discovered" section).
5. Establish branch naming convention in CLAUDE.md: `audit/stage-N-<slug>`.
6. Set up a `/loop` (optional) that runs `/health` weekly and writes the score to STAGES.md so we have a trend line.

**Skills used:** `mcp__notion-create-pages`, `Edit`, `Write`, `TaskCreate`.
**Exit criteria:** STAGES.md exists; Notion queue has ≥ Tier-A items; CLAUDE.md uvicorn command is fixed; weekly `/health` loop is configured (or explicitly skipped).
**Re-audit:** none (Stage 0 is itself the audit infrastructure).
**Gate:** user types "go stage 1" to proceed.

---

## Stage 1 — Security & ops hygiene

**Closes findings:** SEC-1 / QA-1 / PERF-8 (ensure_initialized), SEC-3 (cases.get_case latent), SEC-2 (RLS coverage CI guard), DX-3 (CLAUDE.md was already done in Stage 0).

**Atomic actions:**
1. **A1 — `/investigate` `ensure_initialized` failure.** Use the `/investigate` skill (Iron Law: no fixes without root cause). Output: investigation note → root cause → fix. Likely path: identify earlier failing DDL, surface as ERROR not WARNING, retry on a fresh transaction, or fail-fast on startup if DB integrity check fails.
2. **A2 — Add `Depends(get_current_user)` to `backend/app/routers/cases.py:101`.** 5-minute defensive fix. Add `_assert_case_access(user, case)` mirroring sibling handlers.
3. **A3 — RLS coverage CI guard.** Write SQL: `SELECT tablename FROM pg_tables LEFT JOIN pg_policies USING (tablename) WHERE schemaname='public' AND policyname IS NULL`. Capture the list. For each policy-less table, decide: server-only (allowlist) or needs policy (open Notion ticket). Add the query as a CI step that fails on any policy-less table not on the allowlist.

**Skills used:** `/investigate` (RCA), `Edit`, `Bash`, `/codex review`, `/review`, `/cso` daily-mode for re-audit.
**Exit criteria:** `uvicorn backend.main:app` startup log is clean — no `InFailedSqlTransaction` warning; `curl /api/cases/X` still returns 401; CI has a `rls-coverage-check` step that's green.
**Re-audit:** `audit/re-audit-stage-1-security.md` from `/cso`. Compare to `02-expert-security.md` (baseline score: 6.5/10). Target: ≥ 7.5/10.
**Gate:** user merges + canary clean → "go stage 2".

---

## Stage 2 — Employee-facing copy + W1 surface

**Closes findings:** A4 (W1 rewrite), A5 (statusLabel utility), COPY-1, COPY-2, COPY-3 (error message map), DES-LIVE-1, DES-LIVE-2.

**Atomic actions:**
1. **Create `frontend/src/lib/statusLabel.ts`** — single utility mapping every backend status enum to user-facing English. Include unit tests covering each known status.
2. **Replace all raw-code render sites.** Grep targets: `pages/EmployeeJourney.tsx:688,733`, `pages/Dashboard.tsx:107-109`, `pages/HrCommandCenterCaseDetail.tsx:339-347`. Likely 10–15 sites total.
3. **Rewrite W1 copy** in `EmployeeJourney.tsx:217, 243, 338, 688, 733` per the rewrites in `audit/02-expert-ux-copy.md` (COPY-1, COPY-2, COPY-3).
4. **Check Intake Wizard v2** (`features/platform-v2/intake/EmployeeIntakePage.tsx`) for inherited W1 copy. Fix if present.
5. **Add the error-message map** for top 10 user-visible failure modes (assignment link, document upload, OCR, login, etc.).
6. **Update `relopass-brand-voice` doc** with a new "Product copy" appendix (`audit/02-expert-ux-copy.md` cross-cutting patterns table).

**Skills used:** `Edit`, `design:ux-copy` (for rewrite review), `relopass-brand-voice` (for voice consistency), `/codex review`, `/design-review` report-only for re-audit.
**Exit criteria:** `grep -rn "UUID" frontend/src/pages frontend/src/features` returns zero user-visible matches; status codes never rendered raw in JSX; `statusLabel('invite_revoked')` returns a human string in unit test.
**Re-audit:** `audit/re-audit-stage-2-copy.md`. Compare to `02-expert-ux-copy.md` (baseline 4.0/10) and `02-expert-design-live.md` (baseline 5.5/10). Target: UX copy ≥ 7/10, design-live ≥ 6.5/10.
**Gate:** user merges → "go stage 3".

---

## Stage 3 — A11y baseline pass

**Closes findings:** A6 (Auth.tsx labels + icon-only aria-labels), A11Y-1 through A11Y-9.

**Atomic actions:**
1. Add `htmlFor`/`id` pairs to every form input/label in `Auth.tsx`.
2. Add `aria-label` to every icon-only button (sweep across pages — checklist from `02-expert-a11y.md`).
3. Replace `<tr onClick>` row-click pattern in `HrCommandCenter.tsx` with proper accessible row (button or proper keyboard handling).
4. Implement ARIA tab pattern on `Dashboard.tsx:167-183` (`role="tablist"`, `aria-selected`, `aria-controls`).
5. Add `<h1>` to top-level pages currently missing one.
6. **ESLint custom rule** prohibiting `<div onClick>` without `role="button"` + `tabIndex` + `onKeyDown`.
7. Pair color signals with text/icon per WCAG 1.4.1.

**Skills used:** `Edit`, `design:accessibility-review` (re-audit), `/codex review`.
**Exit criteria:** Custom ESLint rule passes; manual axe-core run against `pages/Auth.tsx` (still unauth) reports zero violations; all icon-only buttons have aria-label.
**Re-audit:** `audit/re-audit-stage-3-a11y.md`. Compare to `02-expert-a11y.md` (baseline 4.5/10). Target: ≥ 7/10.
**Gate:** user merges → "go stage 4".

---

## Stage 4 — Code hygiene cleanup

**Closes findings:** A8 (strip console.*), A9 (services tree decision), P0-2.

**Atomic actions:**
1. **A8** — Replace 19 `console.log/error/debug` sites with a small `lib/logger.ts` that no-ops in prod (or pipes to Sentry if available).
2. **A9** — Decide `backend/services/` vs `backend/app/services/`:
   - Read both trees, identify imports across the line.
   - Pick one (likely `app/services/` per CLAUDE.md).
   - Move modules from the deprecated tree.
   - Delete the deprecated tree.
   - Update CLAUDE.md.
3. Run `/simplify` over the diff to catch any dead code introduced or reuse opportunities.

**Skills used:** `/simplify`, `Read`, `Edit`, `Bash`, `/codex review`, `/health` for re-audit.
**Exit criteria:** `grep -rn "console\." frontend/src/pages frontend/src/features --include="*.tsx" | grep -v "// "` returns ≤ 0 matches; one services tree only.
**Re-audit:** `audit/re-audit-stage-4-hygiene.md`. Compare to `02-expert-fullstack.md` (baseline 5.5/10). Target: ≥ 7/10.
**Gate:** user merges → "go stage 5".

---

## Stage 5 — Estimate Review redesign (the value-prop surface)

**Closes findings:** B1 (W2), DES-LIVE-3 — the prior synthesis flagged this as one of two strategic anchors.

**Atomic actions:**
1. **`/plan-design-review`** against the Side-Output A spec in the prior synthesis Appendix A.
2. **`/plan-ceo-review`** — small pass to verify the redesign matches the strategic anchor framing (this is the value-prop screen).
3. **`/design-shotgun`** — generate 3-4 design variants for the redesigned page. Pick one.
4. **`/design-html`** — finalize the picked variant into production JSX.
5. Implement against `frontend/src/pages/services/ServicesEstimate.tsx`.
6. Add policy-vs-spend reconciliation logic; surface delta + personal-cost callout.
7. **`/design-review`** report-only against the live result.

**Skills used:** `/plan-design-review`, `/plan-ceo-review`, `/design-shotgun`, `/design-html`, `/design-review`, `Edit`, `/codex review`.
**Exit criteria:** ServicesEstimate page has: cap comparison per service, delta callout, personal-cost line, exception flow visible, FX color-coding per spec.
**Re-audit:** `audit/re-audit-stage-5-estimate-review.md`. Compare to baseline (`ServicesEstimate.tsx` scored 4/10 in `02-expert-design-live.md`). Target: ≥ 8/10.
**Gate:** user merges → "go stage 6".

---

## Stage 6 — Design system enforcement

**Closes findings:** B2 (37 raw HTML), B3 (empty states), DES-LIVE-4 through DES-LIVE-8.

**Atomic actions:**
1. Migrate 7 raw `<button>` in `Auth.tsx` to antigravity `Button`.
2. Migrate ~25 raw form elements across admin pages.
3. Migrate 5 in HR pages.
4. Empty-state pass on 6 pages (Dashboard, HrCommandCenter, EmployeeJourney, HrEmployees, AdminProspects, AdminMobilityCaseInspectPage).
5. **`design:design-system`** to refresh DESIGN.md if it exists, or create it.

**Skills used:** `Edit`, `design:design-system`, `/design-review`, `/codex review`.
**Exit criteria:** `grep -rn '<button' frontend/src/pages frontend/src/features --include="*.tsx"` matches drop by ≥80%; every empty state has guidance text + primary CTA.
**Re-audit:** `audit/re-audit-stage-6-design-system.md`. Compare to `02-expert-design-live.md` (baseline 5.5/10). Target: ≥ 7.5/10.
**Gate:** user merges → "go stage 7".

---

## Stage 7 — LLM hardening

**Closes findings:** B5 (llm_client.py wrapper), SEC-5 (passport OCR structured output), ENG-7, P1-6.

**Atomic actions:**
1. Create `backend/app/services/llm_client.py` (or `backend/lib/llm_client.py`) wrapping OpenAI/Anthropic with: timeout (30s default), exponential backoff (3 retries on 429/5xx), structured-output JSON schema enforcement, structured logging, error-mapping to user-friendly messages.
2. Refactor `ocr_passport_extractor.py` to use the wrapper + add structured output schema.
3. Audit and refactor `assistant_router.ts` (currently modified in working tree) for: input validation, output sanitization, prompt-injection defenses.
4. Identify other LLM call sites (`grep -rn "openai\|anthropic" backend/`) and migrate them.

**Skills used:** `Read`, `Write`, `Edit`, `claude-api` skill (if Anthropic SDK in scope), `/codex challenge` (adversarial review — try to break it), `/cso` for security re-audit.
**Exit criteria:** Every `openai.chat.completions.create(...)` call site goes through the wrapper; structured-output schema enforced on OCR; `/codex challenge` cannot find an exploit path; OCR fails gracefully on transient errors.
**Re-audit:** `audit/re-audit-stage-7-llm.md`. Compare to `02-expert-security.md` SEC-5 (P1) + `02-expert-fullstack.md` P1-6. Target: SEC-5 closed; SEC-6 (assistant_router) reviewed.
**Gate:** user merges → "go stage 8".

---

## Stage 8 — Architectural moves (multi-week)

**Closes findings:** B6 (route-auth CI), B7 (query-count log), B8 (bundle profile), B9 (decompose cases.py + immigration.py), ENG-1 (migration plan), PERF-1, PERF-2.

This is the largest stage by effort. Use **`/guard`** mode (freeze + careful).

**Atomic actions (each a sub-stage; can be its own PR):**
1. **8a** — Route-auth CI check (FastAPI route-enumeration script asserts auth presence; allowlist for genuinely public).
2. **8b** — Per-request query-count middleware (log + warn above threshold).
3. **8c** — Bundle profile (`npx source-map-explorer`); identify top 5 bloat sources; lazy-load admin pages.
4. **8d** — Publish ENG-1 migration plan (6:61 → 30:30 over 12 months) as a doc + project board.
5. **8e** — Extract `cases.py:get_case` family of handlers into `services/case_service.py`.
6. **8f** — Extract `immigration.py` similarly.
7. **8g** — Start `database.py` decomposition: split off the top 3 domain blocks.

**Skills used:** `Plan` agent (architectural planning), `/codex consult` (second opinion on each sub-stage), `Edit`, `Bash`, `/benchmark` before/after for 8c, `/guard` mode throughout.
**Exit criteria:** each sub-stage has its own merged PR; bundle size ≥30% smaller; `cases.py` ≤ 1,000 lines; `immigration.py` ≤ 600 lines; migration plan visible in repo.
**Re-audit:** `audit/re-audit-stage-8-arch.md`. Compare to `02-expert-fullstack.md` (5.5) + `02-expert-perf.md` (6.0). Target: both ≥ 7.5/10.
**Gate after each sub-stage:** user types "go stage 8b" / 8c / etc. Don't auto-chain.

---

## Stage 9 — Customer discovery wave (non-code)

**Closes findings:** B10, CEO-1 — the single highest-leverage non-engineering action per the synthesis.

**Atomic actions:**
1. Block calendar windows for 5–10 mid-market HR/mobility interviews over 30 days.
2. Use `mcp__notion-create-pages` to schedule each in the Customer Interviews DB.
3. After each call: run `relopass-interview-intake` skill to ingest the transcript and create linked Notion entries (Stakeholder, Pain Points, Product Opportunities, Feature Requests, Interview record).
4. After all calls: refresh `audit/01-persona-employee.md` and `audit/01-persona-hr.md` with the new evidence.
5. Optionally: re-run `/plan-ceo-review` against the updated personas to check if positioning needs adjusting.

**Skills used:** `relopass-interview-intake` per call; `mcp__notion-create-pages`; `/plan-ceo-review` for end-of-wave reflection.
**Exit criteria:** ≥5 interviews logged in Customer Interviews DB with Mom Test grade ≥ B; persona files refreshed; CEO-lens score (`02-expert-ceo-intent.md`) re-scored.
**Re-audit:** `audit/re-audit-stage-9-discovery.md`. Compare to `02-expert-ceo-intent.md` (baseline 8.5/10) — but the *confidence* changes, not necessarily the score. Target: customer-discovery confidence raised from "Medium-high 75%" to "High 85%+" in the next full audit run.
**Gate:** user types "go stage 10" once enough calls are done.

---

## Stage 10 — Full re-audit + ship-readiness

**Goal:** re-run the entire audit pipeline against the now-improved codebase and compare scores. Decide ship readiness.

**Atomic actions:**
1. Re-run Phase 0 baseline (`/health`, `/benchmark`, `tsc --noEmit`).
2. Re-run Phase 2 expert reviews (all 11 lenses).
3. Produce `audit/00-synthesis-v2.md` with side-by-side comparison: v1 score vs v2 score per lens, findings closed vs still-open, new findings introduced.
4. Run `/qa` full-mode (no longer report-only) against any new bugs.
5. `/cso` comprehensive mode (deep monthly scan, 2/10 bar) — bar drops from "daily 8/10 gate" to "comprehensive 2/10" to catch slow accretion.
6. `/devex-review` live to validate the docs/onboarding fixes from Stages 0+8d.
7. `/landing-report` to check queue state before shipping.
8. **`/ship`** the cumulative audit-driven changes (this is the bigger "audit cleanup release").
9. **`/land-and-deploy`** to production.
10. **`/canary`** to monitor post-deploy.
11. **`/document-release`** to update README, ARCHITECTURE, CHANGELOG with what shipped.
12. **`/retro`** to capture lessons learned across the 10-stage program.

**Skills used:** All of the above + `Plan` agent if v2 reveals a new strategic pivot.
**Exit criteria:** Composite score ≥ 8.0/10 (up from current ~6.0). Zero P0 findings. Tier-A punch list fully closed. Tier-B ≥ 70% closed.
**Re-audit:** Stage 10 *is* the re-audit. No further re-audit needed.

---

## Skills inventory — which stage uses what

This is the explicit "use all relevant skills" mapping you asked for.

| Skill | Used in stage(s) | Purpose |
|---|---|---|
| `/investigate` | 1 | Root-cause analysis for ensure_initialized |
| `/codex review` | 1, 2, 3, 4, 5, 6, 7, 8 | Independent second opinion on every PR |
| `/codex challenge` | 7 | Adversarial test of LLM hardening |
| `/codex consult` | 8 | Architectural second opinion |
| `/review` | every code stage | Pre-landing diff review |
| `/cso` daily | 1, 7 | Security re-audit (8/10 gate) |
| `/cso` comprehensive | 10 | Deep security scan (2/10 bar) |
| `/health` | 0, 4, 10 | Composite quality score over time |
| `/benchmark` | 8c, 10 | Perf before/after |
| `/qa` (report) | 10 only — report mode is for fresh audit phases | |
| `/qa` (fix) | 10 | Drive bug fixes during ship-readiness |
| `/plan-design-review` | 5 | Estimate Review design plan |
| `/plan-ceo-review` | 5, 9 | Strategic re-check |
| `/plan-eng-review` | 8 | Architectural plan review |
| `/plan-devex-review` | 8d | DX/onboarding plan |
| `/design-shotgun` | 5 | Design variants for Estimate Review |
| `/design-html` | 5 | Final HTML/CSS for Estimate Review |
| `/design-review` | 2, 5, 6, 10 | Live visual audit |
| `design:ux-copy` | 2 | UX copy review |
| `design:accessibility-review` | 3 | A11y re-audit |
| `design:design-system` | 6 | Design system refresh |
| `relopass-brand-voice` | 2 | Voice consistency check |
| `relopass-interview-intake` | 9 | Per-call ingest |
| `relopass-dev-queue` / `notion-task-executor` | 0 + ongoing | AI Work Queue management |
| `Plan` agent | 8 | Architectural plans |
| `Explore` agent | spot-use as needed | Targeted code recon |
| `claude-api` | 7 | Anthropic SDK usage in llm_client |
| `/simplify` | 4 | Catch dead code in hygiene PR |
| `/ship` | every code stage | PR creation |
| `/land-and-deploy` | every code stage | Merge + verify |
| `/canary` | every code stage | Post-deploy monitor |
| `/document-release` | 10 | Post-ship docs |
| `/retro` | 10 (and weekly via `/loop`) | Lessons learned |
| `/learn` | optional after each stage | Capture learnings |
| `/loop` | 0 | Weekly `/health` snapshot |
| `/schedule` | optional | Recurring audit tasks |
| `/freeze` / `/careful` / `/guard` | 7, 8 | Safety guardrails on risky stages |
| `/landing-report` | before each `/ship` | Slot-claim check |
| `/codex` | as needed | Tie-breaker on disagreements |

---

## Traceability artifacts per stage

Each stage produces:

```
audit/
├── REMEDIATION_PLAN.md          (this file — never edited after Stage 0)
├── STAGES.md                    (rolling log; one row per stage)
├── re-audit-stage-1-security.md
├── re-audit-stage-2-copy.md
├── re-audit-stage-3-a11y.md
├── re-audit-stage-4-hygiene.md
├── re-audit-stage-5-estimate-review.md
├── re-audit-stage-6-design-system.md
├── re-audit-stage-7-llm.md
├── re-audit-stage-8-arch.md
├── re-audit-stage-8a..8g-*.md   (one per sub-stage)
├── re-audit-stage-9-discovery.md
└── 00-synthesis-v2.md           (Stage 10 output; supersedes 00-synthesis.md as current state)
```

Plus per stage:
- 1 git branch
- 1 PR
- 1+ Notion work-queue rows (Status: Done at end)
- 1 chapter mark in transcript
- 1 row in STAGES.md

---

## What I will NOT do without explicit approval

- Start any code change in Stages 1–9.
- Create Notion entries (these write to your workspace).
- Run `/ship` or `/land-and-deploy` (these create PRs and deploys).
- Touch `main` directly.

---

## Decision point — pick your entry

| Option | What happens |
|---|---|
| **"go stage 0"** | I do the scaffolding only — STAGES.md skeleton, Notion entries for Tier-A, fix CLAUDE.md uvicorn command (5-min docs fix). No risky changes. ~30 min. |
| **"go stage 1 directly, skip 0"** | I skip the scaffolding and dive into security/ops hygiene. Risk: less traceability. |
| **"pause and review the plan"** | I make no changes. You can edit this plan file and tell me to proceed once it's right. |

Default recommendation: **"go stage 0"** — it's safe, fast, and earns its keep by making every later stage cheap to track.
