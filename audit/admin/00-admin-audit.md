# ReloPass — Admin Profile Audit

**Date:** 2026-06-30 · **Ref:** `origin/main @ 0f14c760` · **Method:** static code audit + 3 read-only surface inventories (UI, backend controls/governance, feedback/bug-routine/HITL). Live click-through walkthrough deferred until prod/CI budgets return (≥ July 1). Spec: `.claude/plans` / this folder.

## Executive summary

Viewed as a platform **operator**, the admin is **rich in CMS reach but poor in governance**. There are ~30+ live admin pages and ~60+ admin endpoints — an admin can manage companies, people, assignments, policies, suppliers, catalog, resources, crawl/freshness, prompts, and review queues. But the things an operator most needs to *run and trust* an AI platform are weak:

- **You can't see the platform's real state in one place.** AI-quality is a mock dashboard, gate-impact is company-scoped (not fleet), the home "System SLA" card is a hard null, and the useful signals (errors, feedback, RAG quality, costs) are scattered and mostly buried (only 10 of ~30 pages are in the sidebar).
- **You can't control AI behavior without a developer.** Every behavior-shaping lever — groundedness gate, reranker, learned-weights, ranking weights, eval thresholds, model — is **env/code only**. An admin can edit prompts and publish policies, but cannot read the weights or flip a single AI flag.
- **You half-hear users.** The product-feedback widget closes a real loop to `AdminFeedback`; but the two AI-feedback streams are write-only to ML with no admin view, and the end-user policy-answer thumbs we built **have no UI to submit them**.
- **You can't respond systematically.** A reported bug just writes a row — there is **no in-app path to triage or dispatch an agent**; all automation lives in external Notion skills + GH Actions cron, invisible from the console.
- **Most critical AI levers lack a human gate.** The user-facing AI *roadmap* is well governed (confidence gate → specialist release → review queue), and policy/source/exception/publish flows have explicit approvals. But **source trust is auto-mutated daily off rejected AI feedback with no approval**, and the AI-quality flags are ungated env switches.
- **Access & audit have holes.** No in-app way to add/remove an admin (SQL only; no remove function), a `CRON_SECRET` root bypass, an unguarded `/admin/countries` route, and audit logging split across 3 mechanisms / 2 tables with many silent mutations and no platform-wide viewer.

**Bottom line:** the admin is a strong **content-management** tool and a weak **operations & AI-governance** tool. The highest-leverage work is not more CMS — it's the three operator systems below (feedback console, bug→agent routine, AI-governance/HITL panel) plus closing the access/audit/observability gaps.

## Scorecard (0–5; baseline from this audit, 90-day target ≥ 3)

| # | Dimension | Baseline | Target | Why the baseline |
|---|---|---|---|---|
| 1 | Observability & Visibility | **2** | 4 | funnel/ops real, but AI-quality mock, gate-impact company-scoped, SLA null, signals buried |
| 2 | Control & Configurability | **1** | 3 | only prompts + policy publish; all AI/ranking/threshold/model knobs env/code |
| 3 | User Feedback Loops | **2** | 4 | 1 of ~5 streams (product widget) closes to admin; AI thumbs write-only; helpfulness UI missing |
| 4 | Agent-Driven Bug Routines | **1** | 3 | no in-app dispatch; report = insert row; all automation external |
| 5 | Human-in-the-Loop & Governance | **3** | 4 | roadmap/policy/source-change strong; AI flags + daily reliability recompute ungated |
| 6 | Access Control & Auditability | **2** | 4 | SQL-only admin mgmt, no remove fn, CRON root bypass, fragmented/silent audit, no viewer |
| 7 | Usefulness & IA Hygiene | **2** | 4 | 10/30 discoverable; dead/decoy/duplicate/unguarded surfaces |
| 8 | Trust, Safety & Blast-Radius | **3** | 4 | destructive ops exist + partly audited; fleet vs tenant scope unlabeled |

**Operator-readiness aggregate: 2.0 / 5** ("a developer + SQL is required for routine operations and all AI governance"). Target after the priority work: **≥ 3.5** ("an operator can observe, control routine behavior, hear users, respond to bugs, and trust the critical gates from inside the app").

## Findings

34 findings in `gap-register.{md,json}` — **P1 = 14, P2 = 16, P3 = 4**. Full route/endpoint classification in `route-inventory.md`.

## The three operator systems (designs)

Romain's three explicit asks each get a design note that converts directly into an implementation plan:
- **D-Feedback** (`10-design-feedback-console.md`) — one admin Feedback console unifying all streams + wiring the missing policy-answer thumbs. Closes F-01/F-02/F-03/F-04.
- **D-BugRoutine** (`11-design-bug-routine.md`) — in-app report → triage → (agent) routine → status-back, reusing the existing skills/cron as the execution layer. Closes B-01/B-02/B-03.
- **D-HITL/Governance** (`12-design-hitl-governance.md`) — admin AI-governance control panel: surface + gate the env flags, thresholds, weights, and the auto reliability recompute, with audit + kill-switch. Closes C-01/C-02/C-03/H-01/H-02/H-03.

## Recommended "build-first" shortlist (for a separate follow-up plan)

Ordered by leverage ÷ effort; all are code-only and land ready for the July-1 deploy:

1. **F-01 — wire the policy-answer thumbs UI (S).** A built endpoint is inert; one component change activates an end-user AI-feedback stream. Highest leverage per effort.
2. **A-01 — guard `/admin/countries` (S)** + **A-07 consolidate admin checks (S).** Quick security/correctness wins.
3. **D-HITL panel, phase 1 (M): surface + gate the 3 AI flags** (C-01/H-02) with audit + kill-switch. Turns invisible env switches into governed admin controls — directly enables the July-1 groundedness-gate flip *from the app* instead of env+redeploy.
4. **D-Feedback console (M)** (F-02/F-04) — give the AI-feedback streams an admin view; promote Feedback/Errors into the sidebar.
5. **A-03/A-05 — admin lifecycle + audit viewer (M).** Self-serve admin management + one browsable audit trail.
6. **H-01 — gate the daily source-reliability recompute (M).** Stop silent auto-mutation of source trust.

D-BugRoutine (B-01, L) is the larger build; recommend it as the subsequent milestone once the feedback console + ticket lifecycle exist (it depends on them).

## Caveats

Static audit only — a live admin walkthrough (post-July-1) should confirm each "LIVE" page actually renders + that buried pages aren't intentionally hidden. Baselines are evidence-backed estimates, not measured telemetry; the quantitative trackers in the spec become real numbers once the observability gaps (O-01/O-02) are closed.
