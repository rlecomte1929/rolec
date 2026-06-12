# Employee Roadmap — Empty-First + Journey Context Implementation Plan

> Off `main` (foundation components already merged). Design: approved `roadmap-empty-E.html`
> mockup + `docs/design/employee-journey-ui-brief.md`. Branch: `feat/employee-journey-roadmap`.

**Goal:** Make the employee Roadmap page (`EmployeeCaseRoadmapPage`, route
`/employee/case/:caseId/roadmap`) handle its **prod-default empty state** as a polished,
reassuring "being built" screen (the roadmap is empty in prod — nothing writes
`roadmap_steps` yet), and add the 3-phase context bar for journey consistency. Leave the
heavy platform-v2 `RoadmapScreen` (the populated view) untouched.

**Why:** Today the honest empty state only renders on a fetch *error*; a successful fetch
that returns **no tracks** (the common prod case) falls through to `RoadmapScreen([])`,
which renders blank. Empty-first is the principle: design the empty state as a first-class
screen.

---

## Task 1: `RoadmapBeingBuilt` component (TDD)

A pure presentational "being built" empty state, matching `roadmap-empty-E.html`.

**Files:**
- Create: `frontend/src/features/employee-journey/RoadmapBeingBuilt.tsx`
- Create: `frontend/src/features/employee-journey/RoadmapBeingBuilt.test.tsx`

**Props:**
```ts
interface RoadmapBeingBuiltProps {
  onMessageTeam?: () => void; // optional CTA; omit to hide
}
```

**Content (from the mockup):**
- A centerpiece card: an inline-SVG route/map illustration with a small teal pulse dot,
  headline **"We're building your roadmap"**, and body: "Now that your intake and services
  are confirmed, our team is putting together your personalised relocation plan. You'll get
  an email the moment it's ready — usually within 2 working days." Plus a small teal
  "Preparing your plan" status pill.
- A **"What will appear here" preview**: 5 muted skeleton track rows (no fabricated data),
  each with an inline-SVG icon + track name + a faint "Steps will appear here": Immigration
  & visa · Housing · Schooling · Moving & setup · Banking. Render as low-contrast skeleton
  bars (placeholder, clearly not real content).
- A reassurance row of 3 items with tiny icons: "We'll email you when it's ready",
  "You can message your relocation team any time", "Nothing you need to do right now".
- If `onMessageTeam` provided, a primary navy "Message my relocation team" button.
- Palette: navy `#0b2b43`/`navy-800`, teal `#1f8e8b`/`accent-500`, borders `#e2e8f0`, white
  cards. Reuse antigravity `Card`, `Button`. Inline SVG only (NO emoji). NO fabricated dates/steps.

**Steps (TDD):**
1. Write `RoadmapBeingBuilt.test.tsx` (failing): asserts the "We're building your roadmap"
   headline renders; the 5 preview track names render (Immigration & visa, Housing,
   Schooling, Moving & setup, Banking); when `onMessageTeam` is provided a button
   /Message my relocation team/ exists and clicking it calls the callback; when omitted,
   no such button.
2. `cd frontend && npx vitest run RoadmapBeingBuilt` → fails (module missing).
3. Implement `RoadmapBeingBuilt.tsx` (named export).
4. Test passes.
5. `cd frontend && npx tsc --noEmit` clean.
6. Commit: `feat(employee-journey): RoadmapBeingBuilt empty state`.

## Task 2: Wire into `EmployeeCaseRoadmapPage` + add phase context bar

**File:** `frontend/src/pages/employee/EmployeeCaseRoadmapPage.tsx`

- Add imports: `import { PhaseContextBar } from '../../components/antigravity';`
  `import { RoadmapBeingBuilt } from '../../features/employee-journey/RoadmapBeingBuilt';`
- Define the phase bar element once (it appears on the empty + populated states):
  ```tsx
  const phaseBar = (
    <div className="mx-auto max-w-5xl px-6 pt-6">
      <PhaseContextBar
        phases={[
          { key: 'intake', label: 'Intake', status: 'done' },
          { key: 'services', label: 'Services & policy', status: 'done' },
          { key: 'roadmap', label: 'Roadmap', status: 'current' },
        ]}
        onSelect={(key) => {
          if (key === 'intake') navigate(buildRoute('employeeIntake'));
          if (key === 'services') navigate(buildRoute('services'));
        }}
      />
    </div>
  );
  ```
- Compute `const isEmpty = tracks.length === 0;`
- Change the render branches so the polished empty state covers BOTH the error and the
  empty-tracks cases (replace the existing tiny `if (error) { ... "being set up" ... }`
  block and the empty-tracks fall-through):
  - `if (loading)` → keep the existing spinner.
  - `if (error || isEmpty)` → render `<AppShell>{phaseBar}<div className="mx-auto max-w-5xl px-6 py-6"><RoadmapBeingBuilt onMessageTeam={() => navigate(buildRoute('inbox'))} /></div></AppShell>`
    (use the employee inbox/messages route key — confirm the exact key in routes.ts;
    if no obvious messages route exists, omit `onMessageTeam`).
  - else (populated) → render `<AppShell>{phaseBar}<div ref={selectionRef}><RoadmapScreen ... /></div>{selection && <ExplainTermPopover ... />}</AppShell>` (add `{phaseBar}` above the existing RoadmapScreen; otherwise unchanged).
- Do NOT modify `RoadmapScreen`, the fetch logic, doc-chip logic, or the loading spinner
  beyond adding the phase bar.
- Remove the now-unused old "being set up" inline SVG/markup ONLY (it's replaced by
  RoadmapBeingBuilt). Keep all other imports/logic.

**Verify:**
- `cd frontend && npx tsc --noEmit` clean.
- `cd frontend && npx vitest run` full suite green.
- `cd frontend && npm run build` succeeds.
- Commit: `feat(employee-journey): empty-first roadmap + phase context bar`.

## Self-review
- Reuses `Card`/`Button`/`PhaseContextBar`; no new tokens. No fabricated roadmap data
  (skeleton preview only). The heavy `RoadmapScreen` is untouched. Fetch/doc-chip logic
  unchanged. Every changed line traces to the empty-first redesign.
