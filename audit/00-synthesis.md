# ReloPass Multi-Persona Audit — Synthesis

**Run date:** 2026-05-25
**Mode:** Report-only, comprehensive, all personas
**Method (this run):** 12 source files in `audit/` — 1 baseline + 4 persona-input + 7 expert-review (4 plan-mode intent + 3 live-reality + 3 specialist + 1 QA = 11 total expert lenses).
**Confidence (this synthesis):** Medium-high (75%). Specific gaps flagged inline. Real customer-interview throughput is the binding constraint on confidence (same constraint as the April 2026 synthesis).

---

## Composite scorecard

| Expert lens | Score | What would push to 10 |
|---|---|---|
| CEO / strategy (intent) | **8.5 / 10** | Close the customer-discovery gap; ship the two anchor surfaces |
| Eng manager (intent) | 6.0 / 10 | Publish 6:61 migration plan; route-auth CI check; clean service tree |
| Designer (intent) | 7.0 / 10 | In-product design spec; jargon-class forbidden in brand voice |
| DevEx (intent) | 5.5 / 10 | External API doc; vendor onboarding doc; fix CLAUDE.md |
| Full-stack (live) | 5.5 / 10 | Zero P0 security; one services tree; god-router decomposition |
| Designer (live) | 5.5 / 10 | W1 rewritten; no raw status codes; antigravity used everywhere |
| Accessibility | **4.5 / 10** | aria-labels; label associations; tab pattern; color+text |
| UX copy | **4.0 / 10** | statusLabel(); rewrite W1; error map; empty-state guidance |
| QA | 6.0 / 10 | Clean startup; no console.* in prod; E2E per persona in CI |
| Security | 6.5 / 10 | RLS CI check; cases.get_case hardened; structured LLM outputs |
| Performance | 6.0 / 10 | Bundle profile; query-count middleware; decompose monoliths |

**Composite:** ~6.0 / 10 — solid bones, weak finish. The strategic thinking (CEO 8.5) is genuinely good; the execution discipline (UX copy 4.0, a11y 4.5) is well below the strategic ambition. Closing that gap is the highest-leverage action.

---

## Persona × Expert cross-tab — where pain points map to expert findings

| Persona pain (from `01-persona-*`) | Validated by | Expert finding |
|---|---|---|
| Employees have no self-service case visibility (PP-18, Critical) | Designer live + UX copy + a11y | DES-LIVE-1, COPY-1 (W1 still live), Dashboard.tsx bare empty state |
| HR has no real-time cross-provider visibility (PP-1, Critical, Very High freq) | Designer live | HrCommandCenter scored 8/10 (good KPIs) BUT no per-provider grid yet — PP-20 still open |
| Manual policy compliance vs 40-page doc | Full-stack + intent | Policy Builder UI in AI Work Queue (P1-3); Estimate Review (W2) lightest surface = value-prop gap |
| 15 hours/week on manual provider coordination (PP-13) | Full-stack + designer | `provider_portal.py` exists; portal UI in queue (AIQ-4-D); Provider × Case grid in queue (AIQ-14-A/B) |
| Provider communication fragmented, no audit trail | Security | SEC-2 RLS gap; audit-log surfacing not confirmed in UI |
| Late document errors cause start-date delays | UX copy + full-stack | Error messages blame instead of guide (COPY-3); OCR has no retry (P1-6) |
| Employee anxiety from no status | UX copy | Status codes leak as text; empty states bare; no "next action" anchor |

**Blind spots — pain with no expert validation in this audit:**
- Vendor experience beyond Helena Harless (only one DSP-side interview)
- Mobile employee experience (no responsive testing done)
- Admin operator daily-use friction (zero customer signal, internal-inferred only)
- AI Assistant / Policy Assistant (modified `assistant_router.ts` in working tree; security review deferred)

**Low-priority signals — expert findings with no corresponding pain:**
- DevEx external API doc gap — no integrator interviews exist yet
- French-market voice / i18n — not yet a customer signal beyond Philippe Maury
- Provider portal UX — no transactional-vendor interview

---

## Plan-vs-Reality boomerang deltas (most actionable section)

The prior April 2026 synthesis was strategic intent. This run measures reality against it.

| The plan committed to… | Reality on 2026-05-25 | Delta |
|---|---|---|
| Phase-1 W1 fix (Employee Dashboard, P0) | `EmployeeJourney.tsx:217, 243` still renders "Assignment ID from HR (UUID)" | **NOT SHIPPED** — 1 month after the plan committed it |
| Phase-1 W2 fix (Estimate Review redesign) | `ServicesEstimate.tsx:48-77` is bare list + numbered steps | **NOT SHIPPED** — the value-prop screen is still 4/10 |
| Customer-discovery wave (5-10 mid-market HR/mobility interviews) | 1 real in-house buyer interview in past 12 months (Victoria NBIM 2025-10) | **NOT EXECUTED** — single highest-leverage CEO action still open |
| Spike 2 (Task.due_date verification) | Commit `4648944` references FOUNDATION work; verification status unclear | **STATUS UNCLEAR** — needs a status row, kept current |
| Brand site at the strategic narrative depth | Brand audit 27/50; "operating layer" / differentiation / compliance promise absent site-wide | **NOT SHIPPED** — brand site lags strategic ambition |
| 6:61 dual-layer modular migration progress | Still 6:61 | **NO PROGRESS** measurable |
| Topia complement data-export readiness | No export contract visible in schema | **UNVERIFIED** |
| AI-native at par with Topia Horizon | OCR has no retry/timeout/structured output — single-shot calls | **PARTIAL** — claims yes, implementation says no |

**Reading:** the strategic plan is correct; the *follow-through* is the constraint. None of the deltas above represent strategic mistakes — they all represent execution shortfalls.

---

## AI Work Queue cross-reference — known vs newly discovered

**Items already in AI Work Queue ("known" — the team plans to fix):**
- P1-2 Form Template Registry admin UI
- P1-3 Policy Builder UI (3-question wizard)
- P1-5 Dossier & Forms list view
- P2-3 Form Editor UI (side-by-side PDF + fields)
- P2-5 Save draft flow + completion %
- P2-6 HR document review queue UI
- P3-1 PDF Service, P3-3 Form PDF download
- P3-2 Employee Benefit Comparison dashboard (= W2 fix candidate)
- P3-4 Dossier Builder UI
- P5-3 Question tile system + Policy Assistant UI
- P5-5 Feedback collection (thumbs down → HR review queue)
- AIQ-4-D Provider task portal UI
- AIQ-14-A/B Provider × Case status grid (= PP-20 fix)
- AIQ-13-D HR reviewer DocumentReviewCard
- AIQ-33-B Personio OAuth + HR admin settings UI
- AIQ-38-A BambooHR OAuth + settings UI
- Design dedicated Pets section (May 2026 design review)

**Newly discovered in this audit (not in the queue):**
- W1 surface fix (`EmployeeJourney.tsx:217, 243`) — was P0 in April; still not in queue with a fix ticket
- `statusLabel()` utility — 10+ status-code render sites need it; no queue item
- A11y baseline pass (aria-labels, tab pattern, label associations) — no queue item
- `ensure_initialized` startup transaction abort root-cause — no queue item
- RLS coverage CI check — no queue item
- Route-auth CI check — no queue item
- LLM hardening template (retry + timeout + structured output) — no queue item
- `database.py` 17k LOC decomposition — no queue item
- 6:61 router migration plan — no queue item
- Brand voice doc "Product copy" appendix — no queue item

**Reading:** the AI Work Queue is rich for *new feature work* but thin on *quality / hygiene work*. The audit's primary value-add is surfacing the second class.

---

## Tiered punch list

### Tier A — Fix before next release (~1–2 weeks effort total)
| # | Item | Source | Effort |
|---|---|---|---|
| A1 | Root-cause + fix `ensure_initialized` startup transaction abort | SEC-1 / QA-1 / PERF-8 | 1–2 days |
| A2 | Add `Depends(get_current_user)` to `cases.py:101 get_case` defensively | SEC-3 | 5 min |
| A3 | Run RLS coverage query against prod; list policy-less tables; add CI guard | SEC-2 | 1 day |
| A4 | Rewrite W1 surface copy (`EmployeeJourney.tsx:217, 243, 338, 688, 733`) | COPY-1, COPY-3, DES-LIVE-1 | 1 day |
| A5 | Add `statusLabel()` utility + replace 10+ raw-code render sites | COPY-2 / DES-LIVE-2 | 1 day |
| A6 | Auth.tsx label associations + missing aria-labels on icon-only buttons | A11Y-1, A11Y-4 | 1 day |
| A7 | Fix CLAUDE.md local-dev uvicorn command (`backend.main:app` from repo root) | DX-3 | 5 min |
| A8 | Strip 19 console.* statements from production paths; route through real logger | QA-4 | 1 day |
| A9 | Decide + document `backend/services/` vs `app/services/`; delete the dead one | ENG-3 / P0-2 | 2 days investigation, 1 PR |

### Tier B — Next sprint (~3–4 weeks)
| # | Item | Source |
|---|---|---|
| B1 | Estimate Review redesign per Side-Output A spec (W2, the value-prop surface) | DES-LIVE-3 / prior synthesis W2 |
| B2 | Migrate 37 raw `<button>`/`<input>` to antigravity primitives | DES-LIVE-4 / P1-8 |
| B3 | Empty-state pass across 6 highest-traffic pages | COPY-4 |
| B4 | Error-message map for top 10 user-visible failure modes | COPY-3 |
| B5 | `llm_client.py` wrapper (timeout + retry + structured output + logging) | ENG-7 / SEC-5 / P1-6 |
| B6 | Route-auth CI check (every GET asserts auth presence or is on allowlist) | ENG-2 |
| B7 | Per-request query-count log + threshold alerting | PERF-5 |
| B8 | Bundle profile + decompose chunks; target <500KB initial JS | PERF-3 |
| B9 | Decompose `cases.py` (3,328 LOC) + `immigration.py` (1,544 LOC) into services | P1-3 |
| B10 | Customer-discovery wave: 5-10 mid-market HR/mobility interviews | CEO-1 (highest-leverage non-eng action) |

### Tier C — Backlog (within next 3 months)
| # | Item |
|---|---|
| C1 | `backend/main.py` + `database.py` decomposition (~30k LOC combined → modular) |
| C2 | 6:61 dual-layer migration plan published with monthly milestones (ENG-1) |
| C3 | Full a11y axe-core scan against authenticated surfaces (Phase 3 of a11y) |
| C4 | Lighthouse/Web Vitals baseline against production frontend |
| C5 | Webhook signature verification audit (SEC-8) |
| C6 | Open API spec published + curated "Integrate with ReloPass" doc (DX-1) |
| C7 | Provider portal UX completion (AIQ-4-D family) |
| C8 | Brand-site rewrite to address 27/50 (per `relopass-brand-audit-2026-04-23.md`) |
| C9 | `assistant_router.ts` security deep-dive (prompt injection, function calling) |
| C10 | Squash old migrations once schema stable |

---

## Top 10 findings ranked by (severity × persona-coverage)

| Rank | Finding | Severity | Persona impact | Sources |
|---|---|---|---|---|
| 1 | W1 Employee Dashboard surface still ships implementation jargon (UUID, raw status codes) — was P0 in April | High | All employees, every login | COPY-1, DES-LIVE-1, A4 |
| 2 | `ensure_initialized` startup transaction abort — silent DB drift signal | High | Operational; every persona at risk if drift hits a critical table | SEC-1, QA-1, PERF-8 |
| 3 | RLS coverage gap (122 tables vs 82 policy-bearing files) — actual exposure unverified | High | All — data confidentiality crosscut | SEC-2 |
| 4 | Customer-discovery throughput is the binding constraint on confidence | High | CEO / strategy | CEO-1; same as April 2026 §11 |
| 5 | `cases.get_case` is unguarded in source (currently shadowed by compat; latent) | Medium-high | All employees + HR data | SEC-3, P0-1 (corrected) |
| 6 | Status-code text leaks (`GREEN`/`AMBER`/`fulfilled`/`invite_revoked`) across personas | Medium | Employee + HR | COPY-2, DES-LIVE-2 |
| 7 | Estimate Review (W2 value-prop screen) still bare — was P0 in April | Medium | Employee + HR finance reconciliation | DES-LIVE-3, B1 |
| 8 | 37 raw HTML form elements bypass antigravity design system | Medium | Auth (all personas) + admin | P1-8, DES-LIVE-4 |
| 9 | A11y baseline gaps (label associations, icon-only buttons, tab pattern) | Medium | All personas using assistive tech; legal exposure for B2B in EU | A11Y-1/3/4 |
| 10 | OCR (and likely other LLM calls) lack retry/timeout/structured-output | Medium | Employee intake (passport step); future surface area | SEC-5, P1-6, ENG-7 |

---

## Open questions the audit cannot answer alone

1. **Why is the April 2026 W1/W2 plan not yet shipped?** Is it deprioritized intentionally, or stuck behind something? (CEO-level visibility issue.)
2. **Is `backend/services/` live or dead?** Single decision unlocks ENG-3 / P0-2 cleanup.
3. **What's the compat-layer (`backend/routes/compat.py`) deprecation roadmap?** Without this, SEC-3 P1 stays P1; with a clear timeline, it becomes P0 or P2.
4. **Are there any logged-in QA users / test creds available** so a Phase-3 driven walkthrough can capture real screenshots + a11y scans?
5. **What's the Supabase pooler limit on the live project?** Determines whether `--workers 4` is safe (PERF-6).
6. **Does the assistant feature (modified `assistant_router.ts`) ship to users now or is it gated?** Determines security urgency for SEC-6.
7. **Has the Intake Wizard v2 (`features/platform-v2/intake/EmployeeIntakePage.tsx`, 1,439 LOC) inherited W1 copy?** Quick read pass needed.
8. **Is there a customer-discovery cadence locked in for the next 90 days?** Without this, the next audit (whenever it runs) will hit the same §11 limitation.

---

## What this audit explicitly did NOT do

- No code edits, no PRs, no fixes (per "report-only" mode).
- No authenticated walkthroughs (no test creds available).
- No automated axe-core scan, no Lighthouse, no k6 load test.
- No live SQL queries against the prod Supabase DB.
- No driven UI screenshots — source-of-truth was JSX text content.
- No interviews conducted in-flight — Phase 1 used existing Notion data only.

These are valid Phase-3 follow-ups; each is named in the "Recommended next actions" section of the relevant expert file.

---

## Files in `audit/` (deliverables)

```
00-baseline.md              — Phase 0 baseline + environment
00-synthesis.md             — this file
01-persona-employee.md      — Phase 1 persona input
01-persona-hr.md            — Phase 1 persona input
01-persona-admin.md         — Phase 1 persona input
01-persona-provider.md      — Phase 1 persona input
02-expert-ceo-intent.md     — Plan-mode CEO review
02-expert-eng-intent.md     — Plan-mode eng-manager review
02-expert-design-intent.md  — Plan-mode designer review
02-expert-devex-intent.md   — Plan-mode DevEx review
02-expert-fullstack.md      — Live full-stack code review
02-expert-design-live.md    — Live UI/UX review
02-expert-a11y.md           — Accessibility review
02-expert-ux-copy.md        — UX copy review
02-expert-qa.md             — QA (report-only)
02-expert-security.md       — Security (CSO lens)
02-expert-perf.md           — Performance review
```

---

## TL;DR

The strategy is right. The execution discipline is the gap.
The single highest-leverage action this quarter: **ship the W1 + W2 fixes that were committed in April but didn't land, and book the 5–10 customer-discovery calls that close the §11 confidence limitation.** Everything else in this audit is in service of those two moves.
