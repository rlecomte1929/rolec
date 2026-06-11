# Employee Dashboard — Journey Home Implementation Plan

> Stacked on `feat/employee-journey-ui-foundation` (PR #644). Reuses the foundation
> antigravity components (Card, Button, StatusPill). Design source: the approved
> `dashboard-E.html` mockup + `docs/design/employee-journey-ui-brief.md`.

**Goal:** Replace the confusing 5-pill "Typical flow" on the employee dashboard
(`EmployeeJourney.tsx`) with the approved **3-phase journey** (Intake → Services &
Policy → Roadmap), so there is one coherent "where am I". Leave all claim/pending/
magic-link logic untouched.

**Branch:** `feat/employee-journey-dashboard` (off the foundation branch).

---

## Task 1: `JourneyPhases` component (TDD)

A pure presentational component: three phase cards reflecting the employee's intake
progress, with CTAs. Router-agnostic (callbacks, not hrefs) so it's testable without
a router. Reuses antigravity `Card`, `Button`, `StatusPill`.

**Files:**
- Create: `frontend/src/features/employee-journey/JourneyPhases.tsx`
- Create: `frontend/src/features/employee-journey/JourneyPhases.test.tsx`

**Props:**
```ts
interface JourneyPhasesProps {
  intakeStep: number;        // current intake step (0 = not started)
  intakeTotalSteps: number;  // total steps (e.g. 5)
  onContinueIntake: () => void;
  onPreviewBenefits: () => void;
  onViewRoadmap?: () => void; // undefined => Roadmap locked until intake done
}
```

**Behaviour:**
- Intake phase status: `done` if `intakeStep >= intakeTotalSteps && intakeTotalSteps>0`;
  `in-progress` if `intakeStep > 0`; else `not-started`. Show a slim progress bar
  (`intakeStep/intakeTotalSteps`) when started. The Intake card is visually elevated
  (navy/teal ring) when it is the current/active phase. CTA label: `Review intake`
  (done) / `Continue intake` (in-progress) / `Start intake` (not-started) → primary
  `Button` calling `onContinueIntake`.
- Services & Policy phase: `StatusPill status="upcoming"` "Up next"; ghost `Button`
  "Preview benefits" → `onPreviewBenefits`.
- Roadmap phase: if `onViewRoadmap` provided → primary-ish "View roadmap"; else a
  disabled `Button` "Locked until intake" + muted "Unlocks after intake".
- Layout: a responsive row/grid of 3 `Card`s (stack on mobile). Navy `#0b2b43`
  headings, teal `#1f8e8b` accent, inline-SVG icons (home / briefcase / route). No
  emoji. Match the `dashboard-E.html` mockup.

**Steps (TDD):**
1. Write `JourneyPhases.test.tsx` (failing) asserting:
   - renders all three phase titles ("Intake", "Services & policy", "Roadmap").
   - `intakeStep=2,total=5` → shows "Step 2 of 5" and a "Continue intake" button;
     clicking it calls `onContinueIntake`.
   - `intakeStep=5,total=5` → CTA reads "Review intake".
   - `intakeStep=0` → CTA reads "Start intake".
   - "Preview benefits" calls `onPreviewBenefits`.
   - no `onViewRoadmap` → a disabled button labelled /Locked until intake/ exists and
     there's no enabled "View roadmap"; with `onViewRoadmap`, clicking "View roadmap"
     calls it.
2. Run `cd frontend && npx vitest run JourneyPhases` → fails (module missing).
3. Implement `JourneyPhases.tsx` per the spec (named export).
4. Run the test → passes.
5. `cd frontend && npx tsc --noEmit` clean.
6. Commit: `feat(employee-journey): JourneyPhases (3-phase dashboard component)`.

## Task 2: Swap into `EmployeeJourney.tsx`

**File:** `frontend/src/pages/EmployeeJourney.tsx`

- Replace the "Typical flow" block — the heading `<div ...>Typical flow</div>` and
  `{flowchart}` (around lines 644-645) — with `<JourneyPhases .../>` driven by the
  primary linked assignment (use the first `linkedSummaries` row when present; if
  there are no linked summaries, render nothing there — the claim/pending UI already
  covers that state). Compute props:
  - `intakeStep = row.intake_step ?? 0`, `intakeTotalSteps = row.intake_total_steps ?? 5`
  - `onContinueIntake = () => navigate(buildRoute('employeeIntake'))`
  - `onPreviewBenefits = () => navigate(buildRoute('employeeBenefitsComparison'))`
  - `onViewRoadmap`: only when intake is submitted AND a case id is resolvable;
    otherwise omit (Roadmap stays locked). If the row exposes no caseId for the
    roadmap route, leave `onViewRoadmap` undefined (faithful to the mockup default).
- Add `import { JourneyPhases } from '../features/employee-journey/JourneyPhases';`
- Remove now-orphaned code **only if YOUR change made it unused**: `flowSteps`,
  `flowchart`, `FlowStep` type, `PILL_BASE/PILL_INTERACTIVE/PILL_MUTED` — verify each
  is unreferenced elsewhere before deleting (tsc `noUnusedLocals` will flag leftovers).
- Do NOT touch the claim, pending, magic-link, or "Your active cases" list logic.

**Verify:**
- `cd frontend && npx tsc --noEmit` clean (resolve any unused-symbol errors from the removal).
- `cd frontend && npx vitest run` full suite green.
- `cd frontend && npm run build` succeeds.
- Commit: `feat(employee-journey): 3-phase journey on the employee dashboard`.

## Self-review
- Reuses `Card`, `Button`, `StatusPill` from the foundation branch; no new design tokens.
- Claim/pending/magic-link untouched — every changed line traces to the 5-pill→3-phase swap.
- Roadmap/Services data realities respected (Roadmap locked until intake; benefits route is the live `/employee/benefits`).
