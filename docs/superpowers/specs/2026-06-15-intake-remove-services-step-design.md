# Remove the intake "My Needs" services step — design

**Date:** 2026-06-15
**Task:** [INTAKE-SERVICES] (Notion AI Work Queue)
**Branch:** `feat/intake-remove-services-step`

## Why

The employee intake wizard's "My Needs" step lets the employee pick service
categories (housing, immigration, schools, …) and collects housing/school
preferences. This duplicates the dedicated **Service providers tab** (`/services`,
`ServicesFlowContext` → `services_state` + `case_services`), which is the real,
durable services system that drives recommendations, quotes and budget.

Product direction (Romain, 2026-06-15): intake's job is to produce the
**preliminary roadmap** (the employee's first picture). Service *selection*
belongs to the later "Services & recommendations" phase, in the Services tab —
which then enriches the roadmap. So the intake should stop collecting services.

## Key facts established during recon (against `origin/main`)

- **`CaseDraftDTO.services` has no consumer.** The roadmap generator keys off
  `relocationBasics`, not services; nothing in HR or the frontend reads
  `draft.services`. Submit-time `_draft_to_relocation_profile` reads only
  `relocationBasics` / `employeeProfile` / `familyMembers` / `assignmentContext`.
- **`housing_prefs` is never persisted.** It is collected in the step but is not
  mapped into `intakeToCaseDraft`, so it is discarded on submit today. Removing
  it loses nothing currently stored.
- **Submit already generates the preliminary roadmap.**
  `POST /api/employee/assignments/{id}/submit` enqueues
  `_async_seed_and_generate_roadmap(case_id, …)` (deterministic milestones +
  AI roadmap). Independent of `data.services`.
- **Step count is the single source of truth in `intakeSteps.ts`.** The dashboard
  (`EmployeeJourney` / `JourneySpine`) derives its total from `INTAKE_TOTAL_STEPS`,
  so a 6→5 change propagates automatically — no dashboard edit needed.

## Scope

Wizard goes **6 steps → 5 steps**: `Journey · About You · My People · Work & Place · Review`.

Out of scope (sequenced follow-ups, separate tasks):
- Services-tab actions (quotes, embassy, schools) writing into the roadmap.
- A "validate roadmap before execution" gate before forms/uploads unlock.

## Change set

### `intakeSteps.ts`
- Remove `'My Needs'` from `INTAKE_STEP_LABELS` (→ 5 labels). `INTAKE_TOTAL_STEPS`
  auto-derives to 5. Update doc comment ("6 steps" → "5 steps").

### `EmployeeIntakePage.tsx`
- Delete the **Step 5 "My Needs"** render block (picker grid, housing/schools
  preference sub-forms, the "select a service" warning, `QuoteRequestPanel`).
- Renumber the **Review** render block `step === 6` → `step === 5`.
- Delete the **auto-select-services `useEffect`** (only writer of `data.services`).
- `stepValid`: remove `if (s === 5) return data.services.length >= 1;`. Review (5)
  falls through to `return true`. Removes the "≥1 service required" submit gate.
- Delete `SERVICES` const, `HousingPrefs` interface, and the `services` +
  `housing_prefs` fields from `IntakeData` + `INITIAL_DATA`.
- Delete the now-orphaned `QuoteRequestPanel` + `BudgetSummaryPanel` component
  defs and the Review block's `BudgetSummaryPanel` render. Drop imports they
  alone used.
- `partner` / `children` component-level locals stay (used by the My People step).
- Submit handler behavior unchanged.

### `intakeToCaseDraft.ts`
- Remove the `services: data.services` line. All other mappings unchanged.

### `intakeToCaseDraft.test.ts`
- Drop the `expect(d.services)` assertion; keep the rest.

## Migration / UX continuity

- Saved `intake_step`: existing clamp `Math.min(saved, TOTAL_STEPS)` maps old
  step 5 (My Needs) and old step 6 (Review) → new step 5 (Review).
- Already-submitted cases: dashboard `intakeSubmitted = currentStep >= totalSteps`
  → old `6 >= 5` stays "Submitted". No regression.
- Stale `intake_total_steps = 7` rows already ignored (derived from the constant).

## Verification

- `cd frontend && npx tsc --noEmit` (catches stranded refs/imports).
- `npx vitest run` over the intake `__tests__` + `intakeToCaseDraft` test.
- Grep proof: no remaining `data.services` / `housing_prefs` / `SERVICES` /
  `My Needs` references in `EmployeeIntakePage.tsx`.
- `npm run build` (pre-push hook gate).

## Delivery

Fresh worktree off `origin/main`; commit per logical unit; **branch + PR, no merge**.
