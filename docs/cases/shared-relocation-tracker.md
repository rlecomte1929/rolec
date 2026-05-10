# Shared relocation operational tracker

## Purpose

The former passive **Relocation timeline** (ordered milestones with minimal metadata) is now an **operational task tracker** shared by **HR** and **employees**: same `case_milestones` rows, same APIs, clearer ownership, due dates, status, notes, and urgency styling.

## Task model (persistence)

Each row is still a **`case_milestone`** (no second timeline system).

| Field | Use |
|--------|-----|
| `title` | Short task title |
| `description` | Practical “what to do” copy |
| `milestone_type` | Stable key (e.g. `task_passport_upload`) for future alignment with readiness/checklist |
| `status` | `pending` (UI: **Not started**), `in_progress`, `blocked`, `done`, `skipped`, `overdue` (legacy; UI derives overdue from dates) |
| `owner` | `hr` \| `employee` \| `provider` \| `joint` |
| `criticality` | `critical` \| `normal` (drives emphasis with dates) |
| `target_date` | Due date |
| `actual_date` | Completion date (auto-set when status → `done` if empty) |
| `notes` | Free-text operational comment |
| `sort_order` | Default ordering tie-breaker |

## Ownership model

- **HR** — internal review, routing, scheduling counsel/vendor steps.  
- **Employee** — uploads, confirmations, travel/housing actions they execute.  
- **Provider** — third-party/vendor-driven steps when applicable.  
- **Joint** — requires both sides (or counsel + company) within the same milestone.

Owners are **expectations**, not enforced permissions yet: both HR and employee can PATCH milestones if they already have case access (`require_hr_or_employee`).

## Status model

| Stored | Shown in UI |
|--------|-------------|
| `pending` | Not started |
| `in_progress` | In progress |
| `blocked` | Blocked |
| `done` | Done |
| `skipped` | Skipped |
| `overdue` | Still supported in DB; primary “overdue” signal is **date vs today** in the UI |

## Urgency / color rules (UI)

Consistent **list stripe** and **detail panel** accent:

| Signal | Color |
|--------|--------|
| Past due (`target_date` &lt; today, not done/skipped) | **Red** |
| Due within 7 days, **or** `blocked`, **or** `in_progress` | **Orange** |
| `done` / `skipped` | **Green** |
| Otherwise | **Neutral** |

## Default ordering (UI)

Tasks sort into buckets:

1. Overdue  
2. Due this week (≤ 7 days)  
3. Blocked  
4. In progress  
5. Upcoming  
6. Completed  

Within a bucket: by due date (earliest first for active work), then `sort_order`.

## API (single list + summary, no per-task fan-out)

- `GET /api/assignments/{assignment_id}/timeline?ensure_defaults=1&include_links=0`  
  - **`milestones`**: full task list (including `owner`, `criticality`, `notes`).  
  - **`summary`**: `{ total, completed, overdue, due_this_week, blocked, in_progress }` computed server-side in one pass.  
  - **`include_links=0`** omits link rows for a lighter payload (links still available via full load if needed).

- `PATCH /api/cases/{case_id}/timeline/milestones/{milestone_id}`  
  - Body may include `status`, `owner`, `criticality`, `notes`, `target_date`, `actual_date`, etc.

## Linkage to readiness / checklist

- **Same case** as readiness templates and assignment profile; no duplicate store.  
- `milestone_type` prefixes (`task_*`) are reserved for operational milestones and can later be **mapped** to readiness checklist stable keys without migrating storage.  
- **Readiness template milestones** (`readiness_template_milestones` + `case_readiness_milestone_state`) remain the **route-specific** layer; **case_milestones** are the **cross-route operational plan**. The UI surfaces operational tasks here; HR still expands **Case readiness** for template checklist detail.

## Reused vs refactored

| Piece | Change |
|--------|--------|
| `case_milestones` table | **Extended** (`owner`, `criticality`, `notes`; `blocked` in status check). |
| `compute_default_milestones` | **Replaced** vague phase milestones with **practical tasks** from `OPERATIONAL_TASK_DEFAULTS` in `timeline_service.py` (still one insert path when `ensure_defaults` and empty). |
| `CaseTimeline.tsx` | **Replaced** by `RelocationTaskTracker.tsx` (re-exported as `CaseTimeline` for imports). |
| Timeline endpoints | **Enriched** with `summary` and optional `include_links`. |

## Migrations

- **Supabase**: `supabase/migrations/20260317000000_case_milestones_tracker.sql`  
- **SQLite (local)**: `Database._ensure_case_milestones_tracker_sqlite` rebuilds legacy tables to add columns + `blocked`.

## Performance notes

- One GET returns **all tasks + summary**; no N+1 per milestone.  
- Notes are loaded with the list (typically small). If note payloads grow, add `?omit_notes=1` later without changing the core model.
