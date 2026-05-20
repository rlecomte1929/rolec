# AIQ-3-B — `<RelocationTimeline />` Component Spec

**Task:** Component spec for AIQ-3 (Redesign employee timeline UX)  
**Status:** Awaiting Romain approval before AIQ-3-C implementation begins  
**Date:** 2026-05-13  
**Author:** Claude (AI)  
**References:** AIQ-3-A data contract (`docs/timeline/AIQ-3-A-case-milestones-data-contract.md`)

---

## 0. Goals

Replace the existing accordion-list `<RelocationTaskTracker />` with a **visual timeline** that answers *"What do I need to do next?"* in under 3 seconds of scanning.

Inspiration: Stripe Radar timeline, Linear issue timeline — dense, scannable, information-rich without feeling cluttered.

Key differences from current component:
- Explicit vertical timeline connector (not a flat list)
- Phase-level sections visually group tasks into relocation stages
- Overdue items surface with maximum visual priority — never buried
- Desktop shows a persistent detail panel (no need to scroll to see the form)
- Mobile collapses to an accordion within a single column

---

## 1. Anatomy

```
┌──────────────────────────────────────────────────────────────┐
│  NEXT FOCUS CALLOUT (when overdue or critical items exist)   │
├──────────────────────────────────────────────────────────────┤
│  FILTER TABS:  Total · Overdue · Blocked · In Progress · Done│
├────────────────────────────┬─────────────────────────────────┤
│  TIMELINE LIST             │  DETAIL PANEL  (desktop only)   │
│  ┌─ Phase: Case opened     │                                  │
│  │  ✓ Complete profile     │  [Task title]                    │
│  │  ✓ Upload passport      │  Status selector                 │
│  ├─ Phase: Visa prep       │  Owner badge                     │
│  │  ⚠ Visa docs — OVERDUE  │  Due date + actual date          │
│  │  ○ Submit application   │  Notes textarea                  │
│  ├─ Phase: Arrival         │  [Save] button                   │
│  │  ○ Book temp housing    │                                  │
│  └─ ...                    │                                  │
└────────────────────────────┴─────────────────────────────────┘
```

On mobile (< 768px): detail panel is removed; clicking a task expands an inline panel beneath that row.

---

## 2. Milestone State System

### 2a. Status → Visual Token Mapping

| Status | Derived from | Timeline dot | Left accent | Text colour | Label |
|---|---|---|---|---|---|
| `done` | `status = 'done'` | `●` filled emerald-500, ✓ inside | emerald-500 | slate-400 (muted) | Done |
| `skipped` | `status = 'skipped'` | `○` outline slate-300, line-through text | slate-200 | slate-400 (muted) | Skipped |
| `in_progress` | `status = 'in_progress'` | `◑` half-filled sky-500 | sky-500 | slate-900 | In progress |
| `blocked` | `status = 'blocked'` | `⊘` amber-500 circle with horizontal line | amber-500 | slate-900 | Blocked |
| `overdue` | `target_date < today AND status not done/skipped` | `▲` red-500 triangle | red-500 | red-700 | Overdue |
| `pending` | `status = 'pending'` (not overdue) | `○` outline slate-300 | — (no accent) | slate-700 | Not started |

> **Overdue supersedes in_progress**: if `status = 'in_progress'` but `target_date < today`, render as **overdue** (red) not in_progress (sky). The status field is not changed — overdue is derived only.

### 2b. Criticality Layer

When `criticality = 'critical'`, add a **⬡ diamond-shape** icon at 10px to the right of the milestone title in red-700. This is additive — a critical overdue task gets both the overdue red treatment AND the criticality diamond.

### 2c. Owner Chip

Each task shows a small chip to the right of the title:

| Owner value | Chip label | Chip colour |
|---|---|---|
| `employee` | Employee | amber/warning |
| `hr` | HR | sky/info |
| `joint` | Joint | slate/neutral |

---

## 3. Layout Specification

### 3a. Desktop (≥ 1024px) — Two-column layout

```
┌──────────────────────────────────────────────────────────────────┐
│  Relocation plan                                                  │
│  Shared operational checklist — HR and employee view the same    │
│  tasks; ownership shows who drives each step.                    │
├──────────────────────────────────────────────────────────────────┤
│  [Next focus callout — if any overdue/critical tasks exist]      │
├──────────────────────────────────────────────────────────────────┤
│  Filter tabs (Total N · Done N · Overdue N · Blocked N · …)      │
├───────────────────────────┬──────────────────────────────────────┤
│  LEFT: Timeline list      │  RIGHT: Detail panel                 │
│  w: 40%                   │  w: 60%                              │
│  overflow-y: auto         │  sticky top-4                        │
│  max-h: 70vh              │                                      │
│                           │  [Empty: "Select a task to view      │
│  Vertical connector line  │  and edit details"]                  │
│  (2px slate-200)          │                                      │
│  runs the full height     │                                      │
│  left-offset: 20px        │                                      │
└───────────────────────────┴──────────────────────────────────────┘
```

**Timeline list item structure:**

```
┌─────────────────────────────────────────────────────────────┐
│  [DOT]───────[TITLE]  [owner chip]  [criticality diamond?]  │
│               Due 2026-04-10 · OVERDUE    ← date line       │
│               [Blocked banner if notes present]             │
└─────────────────────────────────────────────────────────────┘
```

**Phase header structure:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [PHASE ICON]  Visa preparation  ──────
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Phase headers span the full timeline column width. They have a slightly larger dot (12px vs 8px), bold text, and a horizontal rule extending to the right edge. The vertical connector line passes through the phase dot like all others.

### 3b. Mobile (< 768px) — Single-column accordion

- No right-side detail panel
- Clicking a task row expands an inline panel directly below it (slides open, ~200ms ease-out)
- Filter tabs scroll horizontally if they overflow (no wrapping)
- Phase headers remain as full-width section breaks
- Minimum touch target: 44×44px per WCAG 2.5.5

---

## 4. Component Props Interface

```typescript
// frontend/src/features/timeline/RelocationTimeline.tsx

import type { CaseMilestone, MilestoneStatus } from './types';

export interface RelocationTimelineProps {
  /** Required: used to fetch timeline data */
  assignmentId: string;

  /**
   * Controls which fields appear editable.
   * HR sees all controls; employee sees status + notes only.
   * Default: 'employee'
   */
  role?: 'hr' | 'employee';

  /**
   * 'phased' (default): fetch from GET /api/relocation-plans/{id}/view
   * 'timeline': legacy flat milestones via GET /api/cases/{id}/timeline
   */
  planDataSource?: 'phased' | 'timeline';

  /**
   * Role to pass as query param to the phased plan API.
   * Only relevant when planDataSource = 'phased'.
   */
  planViewRole?: 'employee' | 'hr';

  /** If true, ensures default milestones are created on first load */
  ensureDefaults?: boolean;

  /** Override card title. Default: 'Relocation plan' */
  title?: string;

  /** When embedded under a parent section header, hide the card's own h3 */
  hideMainTitle?: boolean;

  /**
   * Called when user selects a milestone (click on row).
   * Useful for external routing — e.g. deep-linking to a milestone.
   */
  onMilestoneSelect?: (milestoneId: string) => void;
}
```

### 4a. Edit Permissions by Role

| Field | Employee can edit | HR can edit |
|---|---|---|
| `status` | ✅ Yes | ✅ Yes |
| `notes` | ✅ Yes | ✅ Yes |
| `target_date` | ❌ No | ✅ Yes |
| `owner` | ❌ No | ✅ Yes |
| `criticality` | ❌ No | ✅ Yes |
| `title` | ❌ No | ❌ No (read-only for now) |

---

## 5. Detail Panel Content

When a task is selected, the detail panel (desktop) or inline expansion (mobile) shows:

```
┌────────────────────────────────────────────┐
│  [Status badge]                [Owner chip] │
│                                             │
│  [Task description if present]              │
│                                             │
│  Status          Owner                      │
│  [dropdown]      [dropdown — HR only]       │
│                                             │
│  Due date        Criticality                │
│  [date input]    [dropdown — HR only]       │
│  (HR only)                                  │
│                                             │
│  Completed: 2026-04-12  ← if actual_date   │
│                                             │
│  Notes / block reason                       │
│  [textarea — placeholder shown when        │
│   status = 'blocked': "What's blocking     │
│   this? Add context for your HR team"]     │
│                                             │
│  [Save notes]  [Mark done ✓] ← quick       │
│                               actions       │
└────────────────────────────────────────────┘
```

**Quick action buttons:**
- "Mark done ✓" — visible when status ≠ 'done' and ≠ 'skipped'. One-click sets `status = 'done'` + `actual_date = today`.
- "Skip" — visible when role = 'hr' and status ≠ 'done'. Sets `status = 'skipped'`.

---

## 6. Next Focus Callout

Shown above filter tabs whenever at least one milestone is overdue OR has criticality = 'critical' and is not done.

```
┌────────────────────────────────────────────────────────────────┐
│ ⚠ Next focus:  Visa docs preparation                          │
│   Overdue by 3 days · Employee action                         │
└────────────────────────────────────────────────────────────────┘
```

- Background: `bg-red-50 border border-red-200` when overdue
- Background: `bg-amber-50 border border-amber-200` when critical but not overdue
- Clicking the callout selects that milestone in the timeline

---

## 7. Empty States

### No milestones at all

```
┌────────────────────────────────────────────────────────────────┐
│  📋  No relocation plan yet.                                   │
│                                                                │
│  Your HR team will set up your task list shortly.              │
│  [Create default plan]  ← visible to HR only                  │
└────────────────────────────────────────────────────────────────┘
```

### Filter returns zero results

```
  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
  No tasks match this filter.
  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
```

Dashed border box, text-sm text-slate-500, no action button.

### All tasks complete 🎉

```
┌────────────────────────────────────────────────────────────────┐
│  ✅  All tasks complete — great work!                          │
│                                                                │
│  Your relocation plan is fully checked off.                    │
│  Show completed tasks ↓                                        │
└────────────────────────────────────────────────────────────────┘
```

Shown when `summary.completed === summary.total && summary.total > 0`. Green success styling.

---

## 8. Loading & Error States

**Loading:**
```
[grey timeline skeleton]
  ○  ────────────────────
  ○  ────────────────────
  ○  ──────────
```
Use Tailwind `animate-pulse` on placeholder divs. No spinner. Skeleton matches the actual timeline shape.

**Error:**
```
⚠ Failed to load your relocation plan.
  [Retry]
```
`text-red-600`, retry button calls `load()`.

---

## 9. WCAG 2.1 AA Compliance Notes

| Requirement | Implementation |
|---|---|
| **Colour contrast 4.5:1** | Red-700 (#b91c1c) on white = 7.4:1 ✅. Sky-700 (#0369a1) on white = 5.9:1 ✅. All status text colours must be verified against bg-white and bg-slate-50. |
| **Focus indicators** | All interactive elements get `focus-visible:ring-2 focus-visible:ring-[#0b2b43] focus-visible:ring-offset-2`. Native select/textarea/date inputs inherit browser focus ring which must not be hidden. |
| **Keyboard navigation** | Timeline rows: Enter/Space to expand. Arrow keys navigate between rows when focused. Escape closes the expanded detail. Tab order: callout → filter tabs → timeline rows (top to bottom) → detail panel fields. |
| **Minimum touch targets** | All tappable rows: min 44px height via `py-3 min-h-[44px]`. Filter tabs: `px-3 py-2 min-h-[36px]` — exception allowed per WCAG 2.5.5 for inline elements in a group. |
| **Screen reader labels** | Timeline list: `<ul role="list" aria-label="Relocation milestones">`. Each row: `<li>` with `aria-expanded`. Status dot: `aria-hidden`. Status chip uses visually hidden text for SR: `<span class="sr-only">Status: Overdue</span>`. |
| **Colour-independent state** | Overdue = red colour + triangle icon ▲ + "Overdue" text label. Blocked = amber + ⊘ icon + "Blocked" label. Never communicate state via colour alone. |
| **Form labels** | All selects/inputs in detail panel use `<label>` wrapping or explicit `htmlFor` + `id` pairing. |
| **Alerts** | Overdue callout: `role="alert"` so screen readers announce it immediately on load. Error state: `role="alert"`. Filter tab bar: `role="tablist"` + `aria-selected`. |

---

## 10. Animation & Transitions

- Row expand/collapse: `max-h` transition, `ease-out 200ms` — no JS animation library needed
- Status change: brief `bg-sky-50` flash (200ms) on the row that was just updated
- "Mark done" quick action: checkmark icon spins 360° once on success (CSS keyframe, `duration-300`)
- No other animations — keep it calm for HR / employee stress context

---

## 11. Relationship to Existing `<RelocationTaskTracker />`

`<RelocationTimeline />` is a **new component** that will eventually replace `<RelocationTaskTracker />`. During the transition:

- `<RelocationTaskTracker />` remains unchanged — it is used on the HR command center
- `<RelocationTimeline />` is placed on the **employee dashboard** (`/employee/dashboard`) in Step 3 ("Track your case")
- After Romain validates the new component end-to-end, `<RelocationTaskTracker />` can be swapped out

Both components share:
- The same API calls (`timelineAPI`, `fetchRelocationPlanView`)
- The same `CaseMilestone` type (from `types.ts` created in AIQ-3-A)
- The same `planViewToMilestones` utility

---

## 12. File Locations

| File | Purpose |
|---|---|
| `frontend/src/features/timeline/RelocationTimeline.tsx` | Main component (AIQ-3-C) |
| `frontend/src/features/timeline/types.ts` | `CaseMilestone`, `MilestoneStatus`, helpers (from AIQ-3-A) |
| `frontend/src/features/timeline/RelocationTimeline.stories.tsx` | Storybook stories (AIQ-3-C) |
| `frontend/src/features/timeline/RelocationTimeline.test.tsx` | Unit tests (AIQ-3-C, optional) |

---

## 13. Storybook Stories Required (for AIQ-3-C)

| Story | Description |
|---|---|
| `Default` | 3 phases, mix of all 5 statuses |
| `AllOverdue` | All tasks overdue — worst case visual test |
| `AllDone` | All tasks complete — success state |
| `Empty` | No milestones — empty state |
| `Loading` | Skeleton loading state |
| `Error` | API error state |
| `SinglePhase` | One phase, 2 tasks |
| `EmployeeRole` | `role="employee"` — edit controls hidden |
| `HrRole` | `role="hr"` — all controls visible |
| `MobileViewport` | Viewport set to 375px |

---

## 14. Open Questions for Romain

1. **Phase grouping**: The spec groups tasks under their phase based on `milestone_type` prefix (e.g. all `task_visa_*` under "Visa preparation"). Is this the right grouping, or should phase assignment come from the API (phased plan endpoint already returns phase data)?

2. **Employee vs HR view**: Should employees be able to see the HR-owned tasks (view-only), or should they be hidden entirely from the employee-role view?

3. **"Mark done" quick action**: This sets `actual_date = today` automatically. Is that the right UX, or should employees be asked to confirm the date?

4. **Mobile detail expansion**: On mobile, does the inline expand below each row feel right, or would a bottom sheet (slide-up overlay) be preferable?

---

*Spec complete. Awaiting Romain's sign-off before AIQ-3-C implementation begins.*
