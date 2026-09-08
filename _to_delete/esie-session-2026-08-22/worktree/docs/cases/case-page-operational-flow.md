# HR case page — operational flow

## Final block order (top → bottom)

1. **Header card** — Employee / route line, assignment status, actions (compliance run, reopen, approve/request changes, resources).
2. **Step 1 — Case essentials** — Who, email, family shape, origin, destination (`CaseEssentialsCard`).
3. **Step 2 — Readiness & actions** — Overall readiness state, explicit intake checkpoints, blocking/review rows, suggested next actions (`ReadinessAndActionsBlock` + `caseReadinessUi` / `intakeChecklist`).
4. **Step 3 — Shared relocation plan** — `case_milestones` task list with owner, due dates, status, urgency, notes (`RelocationTaskTracker` / `CaseTimeline`).
5. **Route & template reference** — Short dashed callout + **Case readiness** (expandable template checklist, references, trust tiering). Placed *after* the operational flow so it reads as **reference**, not the primary control surface.
6. **Collapsible / secondary** — Reopen, decision, compliance step-by-step log (auditors), bottom navigation buttons.

## Logical relationships between blocks

| Relationship | Implementation |
|--------------|----------------|
| Intake gap → plan task | `INTAKE_KEY_TO_TRACKER_TYPE` in `hr_case_readiness_view.py` maps each intake `key` to `case_milestones.milestone_type` (aligned with `OPERATIONAL_TASK_DEFAULTS` in `timeline_service.py`). |
| Checklist item → UI link | Each `intakeChecklist` row and intake-derived `blocking_items` / `next_actions` can carry `linked_tracker_task_type`. |
| Scroll to plan row | HR UI uses anchor ids `hr-op-task-{milestone_type}` on plan buttons + `scrollToPlanTask()` from `CaseOperationalSection.tsx`. |
| Non-contradictory suggestions | Intake-derived **per-line** “Have employee complete: …” strings were **replaced** by **one grouped** `next_actions` row per plan task type (`category: plan`), explicitly telling HR to use step 3 for owner & due date. |
| Readiness vs plan completion | Copy clarifies: intake/compliance **checkpoints** ≠ automatically marking plan tasks done (wizard save vs explicit task status). |
| Human review / provenance | Unchanged: `human_review_required` and `provenance_note` on blocking items; trust banner preserved. Case readiness remains the place for **official-source** framing when the template supplies it. |

## Questions each block answers (HR in seconds)

| Question | Where |
|----------|--------|
| Who is this case for? | Step 1 + header name. |
| What is missing? | Step 2 — blocking items + intake detail; links jump to the matching plan row when mapped. |
| What do I (HR) need to do next? | Step 2 state + plan rows owned by **HR** / **Joint** in step 3; “Next focus” in the plan highlights urgent work. |
| What does the employee need to do next? | Plan rows owned by **Employee**; step 2 groups gaps under the same plan task titles. |
| What is late or at risk? | Plan summary badges (overdue, due ≤7d, blocked) + red/orange row styling. |

## Visual / composition adjustments

- **`CaseOperationalSection`** — Numbered 1–2–3 column with shared subtitle pattern so the page reads as one spine.
- **Duplicate titles suppressed** inside cards when embedded (`embedInOperationalFlow` on essentials/readiness; `hideMainTitle` on the tracker).
- **`Card` component** — Accepts optional `id` (used for `hr-rel-tracker-root` scroll target).
- **Case readiness moved below the plan** — Avoids competing “two checklists” above the fold; dashed **Route & template reference** callout sets expectations.

## Data / API adjustments

- **`IntakeChecklistItem`**, **`ReadinessBlockingItemView`**, **`ReadinessNextActionView`** — Optional `linked_tracker_task_type`.
- **`TRACKER_TASK_TITLES`** — Derived from `OPERATIONAL_TASK_DEFAULTS` for consistent plan task titles in grouped next actions.

## Related docs

- [`readiness-actions-block.md`](./readiness-actions-block.md) — Readiness merge & intake checkpoints.
- [`shared-relocation-tracker.md`](./shared-relocation-tracker.md) — Plan task model & API.
