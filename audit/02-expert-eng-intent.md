# Plan-Mode Expert Review — Engineering Manager Lens

**Reviewer lens:** "Is the execution plan buildable, testable, and operable at the depth the strategy needs?"
**Docs reviewed:** `audit-docs/ReloPass_Audit_Final_Synthesis_INTERNAL.md` §8 (Architectural Verification Spikes), `audit-docs/ReloPass_Revised_Execution_Plan.md`, `CLAUDE.md`, `IMPLEMENTATION_EXECUTION_GUIDE.md`, plus codebase reality from `02-expert-fullstack.md`.

**Score: 6.0 / 10** — the spike plan is good, but the day-to-day execution plan does not match the actual repo state.

What would make it a 10: a published migration plan to invert the 6:61 router split, a working dev/test loop that catches the kinds of P0s found in the full-stack audit *before* they ship, and at least 50% of services on consistent DI pattern.

---

## Strengths

1. **Spike framing is excellent.** Five spikes, ~3 weeks total, each mapped to a verdict-sensitivity variable. This is exactly how an eng-manager should de-risk strategy.
2. **Verification-first culture.** "Build hygiene (pre-push hook + CI) → every commit on main must build cleanly." Real, enforced.
3. **Dual-layer pattern documented** in CLAUDE.md. The documentation acknowledges debt rather than hiding it.
4. **Strong test footprint relative to LOC** — 212 backend + 41 frontend tests is not nothing.

## Findings

### ENG-1 [P0] — Dual-layer pattern is at 6:61, with no visible migration plan
CLAUDE.md describes `backend/main.py` (legacy, large) and `backend/app/main.py` (modular) as a progressive migration. Reality: root mounts **61 routers**, modular mounts **6** (10%). No migration milestones, no per-quarter target. At this ratio, the modular layer is more of an experiment than a destination.
**Risk:** Any large refactor (e.g., extracting cases.py at 3,328 lines) creates merge nightmares because root main.py is the single source of churn.
**Recommend:** publish a 12-month "from 6:61 to 30:30" migration plan. Pick 1 domain per month. Start with auth + employee + HR (highest churn = highest payoff for splitting).

### ENG-2 [P0] — A P0 security regression slipped through (cases.get_case no-auth)
The CI pipeline + pre-push hook catch *build hygiene* (TypeScript, lint). They do not catch *security regressions* (a sibling handler having auth and this one not). Pattern-based linters or a route-level "every GET handler must declare auth" rule would catch this.
**Recommend:** add a CI step that enumerates FastAPI routes and asserts auth-dependency presence, with an explicit allowlist for genuinely public routes (healthcheck, public marketing endpoints).

### ENG-3 [P1] — `backend/services/` vs `backend/app/services/` split is undocumented
`requirements_sufficiency.py` cross-imports from a sibling services tree that CLAUDE.md does not mention. Either tree is live or dead — but the eng plan does not say which. New engineers will guess wrong.
**Recommend:** decide; document; delete the dead one.

### ENG-4 [P1] — God-routers go uncontested
`cases.py` 3,328 lines, `immigration.py` 1,544 lines, ~12 routers >500 lines. No file-size rule in CI. Eng-mgr should care because every change to these files takes longer + has higher review burden + higher merge-conflict rate.
**Recommend:** soft cap at 800 lines in CI (warn, not block). Hard cap at 1,500 (block).

### ENG-5 [P1] — Testing strategy for the services layer is uneven
212 backend tests but several services >500 LOC are untested (`roadmap_builder`, `timeline_service`, `supplier_registry`). The risk pattern: the well-tested services attract more tests; the untested ones drift further.
**Recommend:** publish a coverage target per `app/services/` module. Even 30% per module is enough to surface regressions.

### ENG-6 [P1] — Spike 2 (Task.due_date) was committed per recent git log but follow-on date triggers verification needs visible confirmation
Commit `4648944` mentions a FOUNDATION checkpoint. Spike 2 in the plan says "2 hrs verify; 2-3 wks fix." Eng-mgr question: is the verify done? Is the fix shipped? If not, F8 mitigation = 0% (per §8).
**Recommend:** spike status in a single Notion/spreadsheet row, kept current.

### ENG-7 [P1] — LLM-call hardening not part of standard service template
`ocr_passport_extractor.py` has no retry/timeout. This is a class issue, not a one-off — when other LLM calls land (policy assistant, document extraction), they will repeat the pattern.
**Recommend:** create a `llm_client.py` wrapper that enforces timeout + retry + structured-logging + error-mapping, and require all OpenAI/Anthropic calls go through it.

### ENG-8 [P2] — 280 Supabase migrations, drift documented
`MEMORY.md` flags `supabase db push` is blocked by ~95 orphan rows; team uses `apply_migration` MCP. This is a real eng-mgr concern: the drift makes onboarding new engineers slower and disaster recovery harder.
**Recommend:** reconcile drift in a dedicated 1-week sprint. Snapshot remote, apply pending locally, compare, fix.

---

## What the plan does NOT need

- More features. The strategy is clear; execution discipline is the constraint.
- Microservices. The monolith is fine; the split needs *internal* boundaries, not network ones.
- A bigger test count. A *targeted* test increase on the 5 god-modules is worth more than 100 trivial tests elsewhere.

## Recommended next eng-mgr actions

1. Publish the 6:61 → 30:30 migration plan with month-by-month milestones.
2. Add the route-auth-presence CI check (catches P0-1).
3. Decide+document `services/` vs `app/services/`; delete the other.
4. Introduce file-size soft caps in CI.
5. Build the `llm_client.py` wrapper before the next AI feature ships.
