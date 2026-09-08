# AIQ-3-A — `case_milestones` Schema Audit + Component Data Contract

**Task:** Research task for AIQ-3 (Redesign employee timeline UX)  
**Status:** Complete  
**Date:** 2026-05-13  
**Author:** Claude (AI)

---

## 1. Current Schema (live Supabase — project `nsvefcvpvwwwhuqyuqmp`)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | uuid | NO | gen_random_uuid() | Primary key |
| `case_id` | text | NO | — | FK to relocation_cases (stored as text) |
| `canonical_case_id` | text | YES | — | Alternate case identifier for cross-reference |
| `milestone_type` | text | NO | — | Phase or task enum value (see §3) |
| `title` | text | NO | — | Display name for this milestone |
| `description` | text | YES | — | Extended description / instructions |
| `target_date` | date | YES | — | When this milestone should be completed |
| `actual_date` | date | YES | — | When it was actually completed |
| `status` | text | NO | 'pending' | See §2 for full value set |
| `sort_order` | integer | NO | 0 | Position within timeline for this case |
| `owner` | text | NO | 'joint' | Responsible party: `employee`, `hr`, `joint` |
| `criticality` | text | NO | 'normal' | `normal` or `critical` |
| `notes` | text | YES | — | Free-text note (also used for block reason) |
| `created_at` | timestamptz | NO | now() | — |
| `updated_at` | timestamptz | NO | now() | — |

**Indexes:**
- `case_milestones_pkey` — UNIQUE on `id`
- `idx_case_milestones_case_id` — btree on `case_id`
- `idx_case_milestones_canonical` — btree on `canonical_case_id`
- `idx_case_milestones_sort` — btree on `(case_id, sort_order)`

---

## 2. Status Value Set

The `status` column has no CHECK constraint in the database. The frontend uses the following values:

| DB / API value | UI label | Meaning |
|---|---|---|
| `pending` | Not started | Default; task hasn't been started |
| `in_progress` | In progress | Employee or HR is actively working on it |
| `blocked` | Blocked | Cannot proceed; `notes` should explain why |
| `done` | Done | Completed; `actual_date` should be set |
| `skipped` | Skipped | Not applicable for this case |

**Important:** `overdue` is **not a stored status** — it is derived at the component level:

```ts
const is_overdue =
  milestone.target_date &&
  new Date(milestone.target_date) < startOfDay(new Date()) &&
  !['done', 'skipped'].includes(milestone.status);
```

---

## 3. Milestone Type Values (live data)

Two distinct tiers of milestones exist:

### Phase-level (6 types — high-level relocation phases)
| `milestone_type` | Suggested display label |
|---|---|
| `case_created` | Case opened |
| `visa_preparation` | Visa preparation |
| `arrival` | Arrival |
| `housing_search` | Housing search |
| `school_search` | School search |
| `move_logistics` | Move logistics |
| `settling_in` | Settling in |

### Task-level (15 types — individual actionable items)
| `milestone_type` | Suggested display label |
|---|---|
| `task_profile_core` | Complete relocation profile |
| `task_passport_upload` | Upload passport |
| `task_visa_docs_prep` | Prepare visa documents |
| `task_visa_submit` | Submit visa application |
| `task_biometrics` | Biometrics appointment |
| `task_immigration_review` | Immigration review |
| `task_route_verify` | Verify travel route |
| `task_travel_plan` | Confirm travel plan |
| `task_temp_housing` | Arrange temporary housing |
| `task_employment_letter` | Obtain employment letter |
| `task_movers_shipment` | Book movers / shipment |
| `task_tax_local_registration` | Local tax registration |
| `task_arrival_registration` | Register on arrival |
| `task_family_dependents` | Family dependant documents |
| `task_hr_case_review` | HR case review |
| `task_settling_in` | Settling-in support |

The component will likely want to render phase milestones as **section headers / phase dividers** and task milestones as **individual checklist items** within each phase.

---

## 4. UX Requirement Coverage Analysis

| UX requirement | Column | Status |
|---|---|---|
| Milestone status | `status` | ✅ Covered (5 values, see §2) |
| Target date | `target_date` | ✅ Present |
| Actual (completion) date | `actual_date` | ✅ Present |
| Responsible party | `owner` | ✅ Present (`employee`, `hr`, `joint`) |
| Optional note | `notes` | ✅ Present |
| Overdue state | — | ✅ Derivable from `target_date` + `status` |
| Visual urgency / priority | `criticality` | ✅ `critical` / `normal` |
| Display order | `sort_order` | ✅ Present |

---

## 5. Gaps & Risks

### GAP-1 — No CHECK constraint on `status` (⚠️ Medium risk)
**Problem:** The database accepts any text value. All 126 live rows currently have `status = 'pending'` — no `in_progress`, `done`, or `blocked` values exist yet in production. This means the application has never exercised the full status lifecycle against the DB.

**Recommendation:** Add a CHECK constraint before the `<RelocationTimeline />` component ships:
```sql
ALTER TABLE case_milestones
  ADD CONSTRAINT case_milestones_status_check
  CHECK (status IN ('pending', 'in_progress', 'blocked', 'done', 'skipped'));
```
This migration is in AIQ-3-B's scope.

### GAP-2 — `owner` is a party type, not a named person (ℹ️ Low risk)
**Problem:** `owner` stores `employee`, `hr`, or `joint` — not a person's name. The timeline UX can label milestones "Employee action" / "HR action" / "Joint" but cannot display "Assigned to: Sarah Chen".

**Recommendation:** No migration needed for MVP. The component should map owner to a role label + icon. If named assignment is required in future, add an `assigned_to_user_id` column.

### GAP-3 — No `blocked_reason` column (ℹ️ Low risk)
**Problem:** When `status = 'blocked'`, there is no dedicated field to record why. The `notes` column serves this purpose but is semantically overloaded.

**Recommendation:** No migration needed. The component should show `notes` prominently when `status = 'blocked'`, with placeholder text "Add a note about what's blocking this milestone."

### GAP-4 — Phase vs task milestone_types not semantically tagged (ℹ️ Low risk)
**Problem:** The component needs to know whether a milestone is a phase header (`arrival`) or a task item (`task_biometrics`). There is no `milestone_tier` column — the distinction is purely by naming convention (`task_*` prefix = task-level).

**Recommendation:** The component should use a `isTaskMilestone(type: string) => boolean` helper:
```ts
const isTaskMilestone = (t: string) => t.startsWith('task_');
```
No migration needed.

### GAP-5 — `canonical_case_id` vs `case_id` dual identity (ℹ️ Low risk)
**Problem:** Two case ID columns exist. The component must use `case_id` for API calls.

**Recommendation:** Component always uses `case_id`. `canonical_case_id` is internal only.

---

## 6. Proposed `CaseMilestone` TypeScript Interface

```typescript
// frontend/src/features/timeline/types.ts

export type MilestoneStatus = 'pending' | 'in_progress' | 'blocked' | 'done' | 'skipped';
export type MilestoneOwner = 'employee' | 'hr' | 'joint';
export type MilestoneCriticality = 'normal' | 'critical';

export interface CaseMilestone {
  /** UUID primary key */
  id: string;
  /** FK to relocation_cases (text) */
  case_id: string;
  /** Alternate case identifier — do not use for API calls */
  canonical_case_id?: string | null;
  /** Phase or task identifier — see milestone type registry */
  milestone_type: string;
  /** Human-readable title */
  title: string;
  /** Extended description or instructions */
  description?: string | null;
  /** ISO date string 'YYYY-MM-DD' — when this should be done */
  target_date?: string | null;
  /** ISO date string 'YYYY-MM-DD' — when it was actually done */
  actual_date?: string | null;
  /** Lifecycle status */
  status: MilestoneStatus;
  /** Display position within the case timeline */
  sort_order: number;
  /** Who is responsible for completing this milestone */
  owner: MilestoneOwner;
  /** Visual priority level */
  criticality: MilestoneCriticality;
  /** Free-text note; used as block reason when status = 'blocked' */
  notes?: string | null;
  /** ISO datetime */
  created_at: string;
  /** ISO datetime */
  updated_at: string;

  // ─── Derived client-side (not persisted) ───────────────────────────────────
  /**
   * True if target_date is in the past and status is not 'done' or 'skipped'.
   * Computed by the component; never sent to the API.
   */
  is_overdue?: boolean;
}

/**
 * True when this milestone is a task-level item (individual action),
 * false when it is a phase-level header (relocation phase divider).
 */
export const isTaskMilestone = (milestoneType: string): boolean =>
  milestoneType.startsWith('task_');

/**
 * Derive overdue flag from milestone data and current date.
 */
export const deriveIsOverdue = (m: CaseMilestone, today = new Date()): boolean => {
  if (!m.target_date) return false;
  if (['done', 'skipped'].includes(m.status)) return false;
  return new Date(m.target_date) < new Date(today.toDateString());
};
```

---

## 7. Schema Migration Needed?

**Yes, one lightweight migration** is recommended before AIQ-3-C ships:

```sql
-- Add CHECK constraint for status values
-- Safe to run on live DB — all 126 existing rows have status='pending' which is in the allowed set
ALTER TABLE case_milestones
  ADD CONSTRAINT case_milestones_status_check
  CHECK (status IN ('pending', 'in_progress', 'blocked', 'done', 'skipped'));
```

This migration is **non-breaking** (all existing rows pass the constraint) and prevents future inconsistency.

No other columns need to be added. The `overdue` state, `isTaskMilestone` classification, and named-person assignment can all be handled at the component layer without schema changes.

---

## 8. API Contract for `GET /api/cases/{caseId}/timeline`

The existing endpoint already returns `TimelineMilestone[]` matching the `CaseMilestone` interface above. The `TimelineMilestone` interface in `client.ts` is compatible but uses `string` for `status`, `owner`, and `criticality` instead of the narrower union types. AIQ-3-C should use the stricter `CaseMilestone` type internally while accepting the looser `TimelineMilestone` from the API and casting/validating.

---

## Handoff Notes for AIQ-3-B (Component Spec)

1. Use `isTaskMilestone()` to decide render mode: phase-header vs task-item
2. Compute `is_overdue` at render time via `deriveIsOverdue()`
3. `criticality = 'critical'` milestones should have a distinct visual treatment (bold border, warning colour)
4. `owner` maps to an icon + label: employee → person icon, hr → building icon, joint → two-person icon
5. The status CHECK constraint migration should be included in AIQ-3-B's scope (or extracted as a separate micro-task)
6. `links` array (present on `TimelineMilestone` in client.ts) is not in the DB schema — it is likely populated server-side by joining `case_milestone_links` table. AIQ-3-C should render linked entities if present.
