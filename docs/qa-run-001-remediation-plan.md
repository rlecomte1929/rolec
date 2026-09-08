# QA RUN 001 — Remediation Prioritization Plan

**Owner:** Romain · **Status:** For approval · 2026-07-18
**Source:** Audos E2E QA RUN 001 (India→Munich, dual-persona). All 16 findings triaged into the AI Work Queue.
**Lenses applied:** full-stack engineer (root cause, dependency, effort, risk) + business angel (does this fix move the beta wave toward usable feedback + pipeline + a fundable signal?).

---

## 1. Goals

**G1 — A first-time tester can complete BOTH personas end to end without a dead-end or a trust-breaking moment.** Today the employee side dead-ends after intake; that must be removed.

**G2 — The tester actually experiences the payoff.** The employee must reach a rendered roadmap and complete a service selection in-session — the "aha" that drives problem-fit and pilot-interest signal.

**G3 — The most important HR action (publish a policy) never looks broken.** No stuck spinners, no contradictory state on the action HR testers depend on.

**G4 — Spend effort where it converts to the wave's outcome; defer what doesn't.** Sequence by ROI-to-the-goal, not by raw severity.

**Overarching:** reach a state where RUN 002 passes the full dual-persona journey (or the descoped version we choose), so the cohort link can go out with confidence.

---

## 2. Coverage — every finding is in Notion (verified)

| Finding | Notion | Wave tier (recommended) | Notes |
|---------|--------|-------------------------|-------|
| F10 roadmap async (2-day SLA) | AIQ-1614 (🔴/Human) | **T0 — decision gate** | Decide sync vs reframe first |
| F16 Services binds to wrong case | AIQ-1612 (🟡) | **T1 — wave blocker** | Root cause of F15 |
| F15 "destination missing" dead-end | AIQ-1613 (🟡) | **T1 — wave blocker** | Clears with F16 + guard |
| F7 double publish → 409, stuck spinner | AIQ-1615 (🟡) | **T1 — wave blocker** | Key HR action |
| F6 "published" vs "no policy" contradiction | AIQ-1616 (🟡) | **T1 — wave blocker** | Pairs with F7 |
| F4 fresh HR has no policy | AIQ-1621 (🟡) | **T1 — wave blocker** | Seed default policy for test-drive |
| F2 silent case assignment | AIQ-1617 (🟡) | **T2 — fast-follow** | Cheap credibility win |
| F3 false notification badge | AIQ-1618 (🟡) | **T2 — fast-follow** | Trust in the notification system |
| F8 CSP blocks own geocoding | AIQ-1619 (🟡) | **T2 — fast-follow** | Intake polish |
| F12 currency defaults USD on EUR | AIQ-1620 (🟡) | **T2 — fast-follow** | Correctness for cost display |
| F14 policy/services taxonomy mismatch | AIQ-1611 (🔴/Red) | **T3 — post-wave** | Critical severity, low wave-ROI |
| F1/F9 email truncation + wheel scroll | AIQ-1622 (🟢) | **T3 — post-wave** | Papercuts |
| F5/F11 network aborts + 404s | AIQ-1623 (🟡) | **T3 — post-wave** | Investigate |
| F13 policy wiring works | — | ✅ Positive | No task |
| ENV: republish window disrupts QA | — | Ops note | Isolate QA runs from republish |

Prerequisite already Done: TD-BUG-1..7 (incl. AIQ-1590 HR dead-end fix), TD-M0..6, TD-FIX-1..6, TD-QA campaign-forwarding.

---

## 3. The classification principle (the business-angel move)

**Severity ≠ wave-priority.** Audos ranked by how badly each bug breaks the product. An angel re-ranks by *how much each fix moves the wave toward its goal* (usable feedback + pipeline). The two diverge in exactly two places, and getting these right is the whole point of this plan:

- **F14 (Critical severity → deferred for the wave).** The over-cap → Policy Exception feature is genuinely broken, but the friendly wave does **not** need it to produce usability + pipeline signal. It's high effort (architectural taxonomy unification, needs decomposition) with near-zero wave-ROI. Fix it *after* the wave, before you ever sell the over-cap feature. Descope the over-cap assertion from RUN 002.
- **F2/F3/F12/F8 (Medium severity → pulled forward).** Individually minor, but each is a cheap fix that removes a "this looks broken/wrong" moment. Collectively they protect the credibility that converts a friendly test into a warm intro. High ROI-per-hour → do them in the wave sprint.

Everything else sequences by dependency and by "does the tester dead-end or lose trust."

---

## 4. Spec — the four tiers

### T0 · Decision gate — F10 (roadmap SLA)
The employee payoff (roadmap) is 2 working days away by email, so no 20-minute tester sees it. **Decide before planning T1:**
- **Option A (recommended): synchronous test-drive roadmap.** Generate the roadmap in-session for test-drive sessions, OR ship a fast pre-generated sample roadmap for the two Tier-A corridors (FR_NO, IN_DE). The tester experiences the payoff; the wave can measure "does it solve the problem."
- **Option B (fallback): reframe.** Change the test-drive copy + completion condition so the employee journey honestly ends at intake and does not promise a roadmap. Cheap, but the wave then can't test your core value.
- *Angel view:* the roadmap is the value demonstration; a beta that can't show it can't produce a "yes, I'd use this." Choose A unless it's genuinely infeasible in the timeframe.
- *Engineer view:* A is bounded if scoped to test-drive + the 2 Tier-A corridors (sample or a synchronous fast-path); don't try to make the whole paid funnel synchronous now.

### T1 · Wave blockers — fix before the cohort link
Rationale: without these the employee dead-ends or HR loses trust.
- **F16 (+F15):** Services must reuse the intake case (one case context per session); add the destination guard. *Root-cause fix; unblocks the entire employee back half.*
- **F7 (+F6):** collapse policy publish to one path + one state source; surface the 409; disable the second control while in flight. *The key HR action must not look broken.*
- **F4:** pre-seed a default published policy for test-drive HR so testers reach the benefit flow without building a policy. *Removes a chore before the payoff; lifts completion.*
- **F10 (once decided):** implement Option A or B.

### T2 · Fast-follow — same sprint, high ROI-per-hour
- **F2** assign success toast + redirect; **F3** reconcile badge vs list; **F8** allow/proxy the geocode host; **F12** default currency from destination. *Credibility polish across the flow.*

### T3 · Post-wave / architectural backlog
- **F14** ✅ DONE — unify policy/services taxonomy. Fixed by AIQ-1611 (budget-summary read source + service→benefit bridge), merged + deployed 2026-07-19; e2e-verified against real policy data (Housing over a published `host_housing_cap` → `over_budget` → exception).
- **F5/F11** ✅ DONE — aborts confirmed benign (React Query AbortController); 404s not reproducible on the current build (AIQ-1623).
- **F1/F9** ✅ F1 DONE (full credential email, AIQ-1622); F9 not a code defect (scroll container correct).
- **TD-BUG-3** ✅ over-cap assertion RE-ENABLED in **RUN 003** (`docs/audos-test-drive-e2e-scenario-run003.md`) now that F14 (AIQ-1611) has landed.
- **ENV** schedule QA runs outside republish windows.

---

## 5. Plan — sequence

1. **Decide F10** (T0). One call from you; everything downstream depends on the definition of "done" for the employee side.
2. **Sprint 1 (wave-blockers, T1):** F16 → F15 (same PR/root cause) · F7 → F6 (same PR) · F4 · then F10 implementation. These are mostly independent files → candidate for parallel execution (run `relopass-conductor-check`).
3. **Sprint 2 (fast-follow, T2):** F2, F3, F8, F12 — batchable, low risk.
4. **Gate:** re-run the Audos scenario as **RUN 002** (updated to reflect the F10 decision and to descope over-cap). Confirm the previously-blocked employee journey now passes.
5. **Launch** the cohort wave once RUN 002 is clean on T0+T1.
6. **Post-wave backlog (T3):** ✅ landed — F14 (AIQ-1611) → over-cap **re-enabled in RUN 003** → F5/F11 (AIQ-1623) → F1/F9 (AIQ-1622). Next: execute RUN 003 to verify the over-cap → Policy Exception chain end to end.

Dependency notes: F15 is fixed by F16; F6 pairs with F7; F12 feeds F14's correctness later; F4 is a precondition for the benefit flow (but F14 still blocks over-cap even with a policy).

---

## 6. Metrics — how we know the fixes achieved the goal

| Metric | Now (RUN 001) | Target after T0+T1 |
|--------|---------------|--------------------|
| Employee reaches a rendered roadmap in-session | 0% (async, unreachable) | ≥ 90% (Option A) — or N/A if Option B |
| Employee completes a service selection | 0% (dead-ends at Services) | ≥ 90% |
| Employee-side dead-end rate (F15/F16) | 100% | ~0% |
| HR publishes a policy without a stuck spinner / 409 | fails | 100% clean |
| Contradictory-state incidents (F3, F6) | present | 0 |
| Dual-persona end-to-end completion (RUN 002) | PARTIAL/BLOCKED | PASS |
| Downstream (wave): problem-fit % + pilot-interest | not measurable (no payoff) | measurable, segment-split |

The last row is the point: none of your headline campaign KPIs are trustworthy until the tester can actually reach the payoff.

---

## 7. Validation

- **Per task:** each Notion card carries its own Validation Criteria + Test Command (pytest / tsc). Standard dev-queue gate.
- **T0/T1 gate — RUN 002:** re-run the Audos E2E scenario (`docs/audos-test-drive-e2e-scenario.md`), updated to (a) reflect the F10 decision — assert an in-session roadmap if Option A, or the "preparing your plan" holding state if Option B — and (b) descope the over-cap assertion (F14 deferred). RUN 002 must PASS the full dual-persona journey through completion + survey.
- **Regression:** confirm the T1 fixes didn't disturb the already-solid parts (provisioning, HR→employee notification, intake auto-save).
- **Data hygiene:** RUN 002 under a `qa-*` campaign; purge after; `insead-2026` stays empty.

---

## 8. What I recommend you decide / approve
1. **F10 — Option A (synchronous/sample roadmap for test-drive) vs Option B (reframe).** This is the one decision that gates everything.
2. **Approve the wave-tier re-classification** — notably **F14 → post-wave** (defer over-cap), even though it's Critical severity, because the friendly wave doesn't need it. If you approve, I'll sync the Notion priorities to match these tiers (F14 wave-priority down, T1 items up).
3. **Descope the over-cap assertion from RUN 002** until F14 lands.

Net: the queue is complete and correct; what's left is one product decision (F10) and agreeing the sequence — fix the employee dead-end + the payoff + the HR-publish trust bug, ship the wave, and push the over-cap architecture to a post-wave sprint.
