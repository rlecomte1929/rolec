# Audit Remediation — Stages Rolling Log

**Purpose:** One row per completed stage. Append-only. Visible trend of progress.

**Reading order:**
1. `audit/00-synthesis.md` — what the audit found (state on 2026-05-25).
2. `audit/REMEDIATION_PLAN.md` — how we're fixing it, stage by stage.
3. `audit/STAGES.md` — what we've actually done (this file).
4. `audit/re-audit-stage-N-*.md` — per-stage proof of improvement.
5. `audit/00-synthesis-v2.md` — Stage 10 output; supersedes v1 once cut.

---

## Stages log

| Stage | Date | Branch | PR | Findings closed | Re-audit doc | Score deltas | Notes |
|---|---|---|---|---|---|---|---|
| 0 | 2026-05-25 | `audit/stage-0-governance` | [#118](https://github.com/rlecomte1929/rolec/pull/118) | A7 (CLAUDE.md uvicorn fix) + governance scaffold + audit/* committed | n/a (Stage 0 = scaffolding) | n/a | 14 Notion AI Work Queue entries created; branch convention documented; rolling log + composite-score timeline + Tier A/B/C findings tracker scaffolded. **Merged 2026-05-25.** |
| 1 | 2026-05-25 | `audit/stage-1-security` | [#119](https://github.com/rlecomte1929/rolec/pull/119) (merged) | **A2** (already done by team commit 4a3b43c — verified) + **A3** (script + CI guard shipped; 113-entry seed allowlist; triage queued as A3-followup) + **A1 partial** (5 PRAGMA blocks guarded, 3 helpers guarded, 4 savepoint protections — original failing statement no longer fails; deeper init_db DDL has same class issue, queued as A1-followup). PR also carries parallel team work: **A4** (W1 copy), **A5** (statusLabel utility), **A6** partial (icon aria-labels), **A8** (logger + strip console.*) | [`audit/re-audit-stage-1-security.md`](re-audit-stage-1-security.md) | Security: **6.5 → 7.5** (+1.0) | Discovered `patch_case` likely also unguarded (new P1 finding). Two follow-ups: [A1-followup](https://www.notion.so/36b887c64d48819a92dcf3583373e6f7), [A3-followup](https://www.notion.so/36b887c64d48813abfe4dfbc4e2fb8a2). |
| 2 | 2026-05-26 | `audit/stage-2-copy` | [#120](https://github.com/rlecomte1929/rolec/pull/120) | A4 + A5 + BRAND verified landed via PR #119. Jargon hunt across HR/Admin/dev surfaces identified 9 remaining sites (HrDashboard, AdminMobilityCaseInspectPage, AdminAssignments, CaseEssentialsCard, AssignmentDebugPanel) — decision: retain on operator surfaces. COPY-8 acknowledged-not-closed. | [`audit/re-audit-stage-2-copy.md`](re-audit-stage-2-copy.md) | UX copy: **4.0 → 7.0** (+3.0); Design (live): **5.5 → 6.8** (+1.3) | No source-code edits. Stage 2 contribution is verification + jargon hunt + scoring doc. |
| 3 | 2026-05-26 | `audit/stage-3-a11y` | [#121](https://github.com/rlecomte1929/rolec/pull/121) | **A11Y-1 + A11Y-7** closed via root-fix at antigravity `Input.tsx` primitive (useId + htmlFor + aria-describedby + role=alert) — app-wide effect. **A11Y-8** closed via composed aria-label on Acknowledge / Mark-fulfilled quote buttons. **A11Y-2, A11Y-3, A11Y-4, A11Y-5, A11Y-6** already closed pre-Stage-3 (tab pattern + tr keyboard + icon aria-label + color+text + AppShell h1). **A11Y-9** acknowledged: 303 `no-clickable-div` violations surfaced via AIQ-395, drained by AIQ-397 sprint. | [`audit/re-audit-stage-3-a11y.md`](re-audit-stage-3-a11y.md) | Accessibility: **4.5 → 7.5** (+3.0) | 2 files, ~20 LOC net source-code change. P2 items (skip-link, live regions, autocomplete) recommended as `AUDIT-A11Y-P2-followup`. |
| 4 | 2026-05-26 | `audit/stage-4-hygiene` | [#123](https://github.com/rlecomte1929/rolec/pull/123) | **A8** verified closed on main (logger.ts + 0 non-exempt console.* in production frontend). **A9** acknowledged-not-closed: A9.1 + A9.2 docs landed but A9.3 (155-file migration) + A9.4 (97 router import corrections) are stranded on local audit/stage-1-security branch — never pushed to main. Dual services tree persists on main. AIQ-397 sprint drained 303 → 0 no-clickable-div errors. AIQ-398 has 9 `no-console` residuals in src/api/*. | [`audit/re-audit-stage-4-hygiene.md`](re-audit-stage-4-hygiene.md) | Full-stack (live): **5.5 → 7.5** (+2.0) | Filed AUDIT-A9-followup to land the stranded A9.3/A9.4 commits. Docs-only PR. |
| 6 | 2026-05-26 | `audit/stage-6-design-system` | (pending) | **B3 (empty-state pass)** closed for top-traffic pages: Dashboard + HrCommandCenter patched per docs/product-copy-rules.md; AdminProspects already compliant; EmployeeJourney verified in-context (sibling pending-invitations list handles actionable path). **B2 (raw HTML migration)** acknowledged-not-closed: Phase 2 named 37 sites; current count is **174** (121 buttons + 53 inputs) — mostly platform-v2/ growth since Phase 2. Filed as AUDIT-B2-followup (P2, 4-phase decomposition). | [`audit/re-audit-stage-6-design-system.md`](re-audit-stage-6-design-system.md) | Design (live): **7.3 → 7.6** (+0.3) | 2 source-code edits, ~10 LOC. Honest scope decision: 174-site refactor is multi-week, not one-stage. |
| 5 | 2026-05-26 | `audit/stage-5-estimate-review` | [#124](https://github.com/rlecomte1929/rolec/pull/124) | **W2 (Estimate Review redesign)** substantially closed: PackageSummary.tsx is a comprehensive Side-Output A implementation (cap comparison + visual bars + personal-cost callout + exception flow + currency conversion + multi-role view). Stage 5 own contribution: page-wrapper copy patch — "Next steps" generic list rewritten to outcome-described prose; empty-state polish per docs/product-copy-rules.md. ECB FX date stamping + multiplier transparency flagged as P2 followups. | [`audit/re-audit-stage-5-estimate-review.md`](re-audit-stage-5-estimate-review.md) | ServicesEstimate page: **4.0 → 8.5** (+4.5); Design (live): **6.8 → 7.3** (+0.5) | 1 file, ~14 LOC net change. The bulk of the W2 redesign was already on main via parallel team work; Stage 5 is verification + small polish. |

---

## Composite-score timeline

This table is updated at the end of each stage that re-audits a lens. Compare against the Phase-2 baseline.

| Lens | Baseline (2026-05-25) | After S1 | After S2 | After S3 | After S4 | After S5 | After S6 | After S7 | After S8 | After S9 | After S10 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CEO / strategy | 8.5 | — | — | — | — | — | — | — | — | — | — |
| Eng manager | 6.0 | — | — | — | — | — | — | — | — | — | — |
| Designer (intent) | 7.0 | — | — | — | — | — | — | — | — | — | — |
| DevEx (intent) | 5.5 | — | — | — | — | — | — | — | — | — | — |
| Full-stack (live) | 5.5 | — | — | — | **7.5** | — | — | — | — | — | — |
| Designer (live) | 5.5 | — | **6.8** | — | — | **7.3** | **7.6** | — | — | — | — |
| Accessibility | 4.5 | — | — | **7.5** | — | — | — | — | — | — | — |
| UX copy | 4.0 | — | **7.0** | — | — | — | — | — | — | — | — |
| QA | 6.0 | — | — | — | — | — | — | — | — | — | — |
| Security | 6.5 | **7.5** | — | — | — | — | — | — | — | — | — |
| Performance | 6.0 | — | — | — | — | — | — | — | — | — | — |
| **Composite** | **6.0** | — | — | — | — | — | — | — | — | — | — |

---

## Findings tracker

This table mirrors the `audit/00-synthesis.md` "Tiered punch list" (A/B/C). Mark each cell as the stage that closes the finding.

### Tier A (close before next release)

| ID | Title | Source | Notion URL | Closed in | PR |
|---|---|---|---|---|---|
| A1 | Root-cause + fix `ensure_initialized` startup transaction abort | SEC-1 / QA-1 / PERF-8 | [AUDIT-A1](https://www.notion.so/36b887c64d4881e6a865d0bda0fb78db) | Stage 1 (partial) + [A1-followup](https://www.notion.so/36b887c64d48819a92dcf3583373e6f7) | (stage-1) |
| A2 | Add `Depends(get_current_user)` to `cases.py:101 get_case` defensively | SEC-3 | [AUDIT-A2](https://www.notion.so/36b887c64d48811dbe6ff3e8bc6ca05b) | Stage 1 (was already team-fixed in commit 4a3b43c) | (stage-1) |
| A3 | RLS coverage CI guard | SEC-2 | [AUDIT-A3](https://www.notion.so/36b887c64d4881b1b9a2efda2dc6d0a7) | Stage 1 (instrumentation) + [A3-followup](https://www.notion.so/36b887c64d48813abfe4dfbc4e2fb8a2) | (stage-1) |
| A4 | Rewrite W1 surface copy | COPY-1, COPY-3, DES-LIVE-1 | [AUDIT-A4](https://www.notion.so/36b887c64d4881fa8b88f3fe2b464cf2) | Stage 2 | — |
| A5 | `statusLabel()` utility + replace render sites | COPY-2 / DES-LIVE-2 | [AUDIT-A5](https://www.notion.so/36b887c64d4881dba8a2ce2305d52089) | Stage 2 | — |
| A6 | Auth.tsx label associations + icon-only aria-labels | A11Y-1, A11Y-4 | [AUDIT-A6](https://www.notion.so/36b887c64d488191a70bcc576e43a394) | Stage 3 | — |
| A7 | Fix CLAUDE.md local-dev uvicorn command | DX-3 | n/a (doc only) | **Stage 0** | [#118](https://github.com/rlecomte1929/rolec/pull/118) |
| A8 | Strip 19 console.* statements; route through real logger | QA-4 | [AUDIT-A8](https://www.notion.so/36b887c64d48815391e4c3d24cf9d600) | Stage 4 (verified closed) | — |
| A9 | Decide + document `backend/services/` vs `app/services/` | ENG-3 / P0-2 | [AUDIT-A9](https://www.notion.so/36b887c64d48810bac10ee37c94977d8) | Stage 4 (A9.1/A9.2 closed; A9.3/A9.4 stranded → [A9-followup](https://www.notion.so/36c887c64d488148918dd44c45fcd9c4)) | — |

### Tier B (next sprint)

| ID | Title | Source | Notion URL | Closed in | PR |
|---|---|---|---|---|---|
| B1 | Estimate Review redesign per Side-Output A | DES-LIVE-3 / W2 | (existing queue entry — to confirm) | Stage 5 (substantially closed; ECB FX + multiplier transparency = P2 followups) | — |
| B2 | Migrate 37 raw `<button>`/`<input>` to antigravity | DES-LIVE-4 / P1-8 | (no entry yet — defer to Stage 6 prep) | Stage 6 (acknowledged; scope grew to 174; → [B2-followup](https://www.notion.so/36c887c64d48819387c9fe309a7bd47f)) | — |
| B3 | Empty-state pass across 6 highest-traffic pages | COPY-4 | (defer) | Stage 6 (closed for top pages) | — |
| B4 | Error-message map for top 10 failure modes | COPY-3 | (defer to Stage 2 / 6 prep) | Stage 2 / 6 | — |
| B5 | `llm_client.py` wrapper | ENG-7 / SEC-5 / P1-6 | [AUDIT-B5](https://www.notion.so/36b887c64d4881cbbe0ffb7a89863224) | Stage 7 | — |
| B6 | Route-auth CI check | ENG-2 | [AUDIT-B6](https://www.notion.so/36b887c64d488193b15dca3faca08067) | Stage 8a | — |
| B7 | Per-request query-count middleware | PERF-5 | [AUDIT-B7](https://www.notion.so/36b887c64d488125b03bd286e279ef0e) | Stage 8b | — |
| B8 | Bundle profile + decompose chunks | PERF-3 | (defer to Stage 8c prep) | Stage 8c | — |
| B9 | Decompose `cases.py` + `immigration.py` | P1-3 | (defer to Stage 8e/f prep) | Stage 8e/f | — |
| B10 | Customer-discovery wave (5-10 interviews) | CEO-1 | [AUDIT-B10](https://www.notion.so/36b887c64d4881f19656dc8b4bd68ff7) | Stage 9 | — |

### Tier C (backlog)

| ID | Title | Source | Notion URL | Closed in | PR |
|---|---|---|---|---|---|
| C1 | `backend/main.py` + `database.py` decomposition (~30k LOC combined) | PERF-1, PERF-2 | — | Stage 8g | — |
| C2 | 6:61 dual-layer migration plan with monthly milestones | ENG-1 | [AUDIT-C2](https://www.notion.so/36b887c64d4881a89f72decb4f6eb2b9) | Stage 8d | — |
| C3 | Full a11y axe-core scan against authenticated surfaces | A11Y deferred items | — | Stage 10 follow-up | — |
| C4 | Lighthouse/Web Vitals baseline against production frontend | PERF deferred items | — | Stage 10 follow-up | — |
| C5 | Webhook signature verification audit | SEC-8 | — | post-Stage 10 | — |
| C6 | OpenAPI spec published + "Integrate with ReloPass" doc | DX-1 | — | post-Stage 10 | — |
| C7 | Provider portal UX completion | AIQ-4-D family | (existing queue entries) | post-Stage 10 | — |
| C8 | Brand-site rewrite to address 27/50 | `relopass-brand-audit-2026-04-23.md` | — | post-Stage 10 | — |
| C9 | `assistant_router.ts` security deep-dive | SEC-6 | — | Stage 7 follow-up | — |
| C10 | Squash old migrations once schema stable | PERF-10 | — | post-Stage 10 | — |

### Cross-cutting hygiene (not in Tier A/B/C but tracked)

| Item | Source | Notion URL | Closed in |
|---|---|---|---|
| `relopass-brand-voice` doc — add "Product copy" appendix | UX copy review cross-cutting patterns | [AUDIT-BRAND](https://www.notion.so/36b887c64d4881e58b4cf5b32d86562e) | Stage 2 |

---

## Per-stage notes

### Stage 0 — 2026-05-25

- Branch `audit/stage-0-governance` created off `main`.
- CLAUDE.md fix: `cd backend && uvicorn main:app` → `uvicorn backend.main:app` (run from repo root).
- CLAUDE.md addition: new "Audit remediation workflow" section documenting branch convention + Notion system-of-record + gate discipline.
- Notion AI Work Queue entries created for: A1, A2, A3, A4, A5, A6, A8, A9, B5, B6, B7, B10, C2, brand-voice product-copy appendix (~14 entries).
- This rolling log + composite scorecard + findings tracker scaffolded.
- No re-audit (Stage 0 is the audit infrastructure itself).
- Optional: weekly `/health` snapshot via `/loop` — **NOT** configured in this stage; defer to user decision.
