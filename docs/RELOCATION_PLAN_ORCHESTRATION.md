# Relocation plan orchestration — architecture audit & implementation path

**Status:** design note (no implementation in this change).  
**Goal:** evolve the shared employee/HR checklist into a **phased, backend-driven** relocation plan with next-action surfacing, progressive disclosure, auto-derived statuses, and dependency/blocking logic—while **one canonical plan** feeds both roles.

---

## 1. Current state (what exists today)

### 1.1 Canonical operational tasks — `case_milestones` + `milestone_links`

- **Storage:** `case_milestones` (per case): `milestone_type`, `title`, `description`, `target_date`, `actual_date`, `status`, `sort_order`, `owner`, `criticality`, `notes`; optional links in `milestone_links` (`linked_entity_type`, `linked_entity_id`).
- **Defaults:** `backend/app/services/timeline_service.py` — `OPERATIONAL_TASK_DEFAULTS` + `compute_default_milestones()` (anchors due dates from move date; filters some tasks by selected services).
- **APIs:** `GET/PATCH` timeline under case and assignment (see `backend/main.py` — `get_assignment_timeline`, `get_case_timeline`, `update_case_milestone`, `add_milestone_link`).
- **Summary:** `compute_timeline_summary()` — counts total / completed / overdue / due this week / blocked / in_progress.
- **UI:** `frontend/src/features/timeline/RelocationTaskTracker.tsx` loads `timelineAPI.getByAssignment`, computes **“Next focus”** client-side from sorted tasks (`nextCritical`), shows flat list + counters.

**Implication:** The “flat checklist” is already backed by a **single table** shared by HR and employee; phase and orchestration are **not modeled**—only `sort_order` and implicit ordering in code.

### 1.2 HR intake / readiness (parallel, partially bridged)

- **`backend/hr_case_readiness_view.py`:** `build_intake_checklist_items()` — deterministic checklist from assignment **profile JSON**; each item can expose `linked_tracker_task_type` mapping to `milestone_type` (`INTAKE_KEY_TO_TRACKER_TYPE`).
- **Supabase readiness templates:** `readiness_template_*`, checklist items with `stable_key` (e.g. SG employment) — **route-specific** HR checklist, not the same row set as `case_milestones`.
- **API:** HR assignment payload includes readiness UI; separate patch for readiness milestone state (`patch_hr_readiness_milestone` in `main.py`).

**Implication:** Two “checklist” concepts—**operational plan** (`case_milestones`) vs **template-driven readiness**—already linked only by **convention** (`milestone_type` / stable keys).

### 1.3 Mobility graph — evaluations, documents, context

- **Tables:** `mobility_cases`, `case_people`, `case_documents`, `requirements_catalog`, `case_requirement_evaluations` (see `supabase/migrations/20260411100000_mobility_graph_context.sql` and follow-ups).
- **`CaseContextService`** (`backend/services/case_context_service.py`): assembles case + people + documents + rules + evaluations for inspect/context APIs.
- **`RequirementEvaluationService`:** upserts evaluations (admin/assignment-scoped flows); statuses drive what’s “open.”

### 1.4 Next actions (mobility UUID cases only)

- **`NextActionService`** (`backend/services/next_action_service.py`): reads **open** `case_requirement_evaluations` (`missing`, `needs_review`) + optional spouse reminder from `mobility_cases.metadata` / `case_people`.
- **API:** `GET /api/mobility/cases/{case_id}/next-actions` (`backend/app/routers/mobility_context.py`).
- **Used by:** `mobility_inspect_service`, admin evaluation trigger, `MobilityCasePanels` (frontend) — **not** merged into `GET …/timeline` today.

**Implication:** “Next step” for mobility is **evaluation-centric**; relocation plan “Next focus” is **milestone-centric**—risk of **duplicate or conflicting** UX until unified in one view-model.

### 1.5 Legacy / secondary timelines

- **`_build_timeline`** in `backend/main.py` — older **dashboard** `TimelinePhase` / `TimelineTask` shapes; separate from `case_milestones`.
- **`docs/TIMELINE_WORKFLOW.md`** — documents an earlier 7-milestone “phase” set (`visa_preparation`, `housing_search`, …) that differs from **operational** `OPERATIONAL_TASK_DEFAULTS` (`task_passport_upload`, …).

**Implication:** Avoid a third parallel model; **extend** `case_milestones` + services rather than reviving the old dashboard timeline as source of truth.

### 1.6 Audit / events

- **`audit_logs`** (migration `20260411140000_audit_logs.sql`) — mobility/case activity; can support “why did status change?” if orchestration writes evaluations or milestone updates through instrumented paths.

---

## 2. Target capabilities mapped to gaps

| Capability | Today | Gap |
|------------|--------|-----|
| **Phased timeline** | Flat list ordered by `sort_order` | No `phase` / `phase_order` on milestones; no server-side grouping contract |
| **Next-action card** | Client picks first urgent milestone; mobility has separate next-actions API | No single **PlanProjection** merging milestones + evaluations + intake |
| **Progressive disclosure** | All tasks listed | No `visibility` / `unlocked_when` / phase collapse in API |
| **Auto-derived status** | Status manual unless HR/employee PATCH | No reconciler from documents, evaluations, or profile |
| **Blocking / dependencies** | `blocked` status + `notes` only | No `depends_on_milestone_id` or rule engine; links table unused for gating |

---

## 3. Recommended direction (cleanest path)

**Treat `case_milestones` as the canonical plan row** for both employee and HR. Add **orchestration** as:

1. **Read models** — computed DTOs (phases, next action, lock state) built from milestones + evaluations + profile + documents **without** duplicating long-lived state in a second task table.
2. **Reconciliation service** — periodic or on-write hooks that **propose** status updates (or flags) from system truth; optionally **auto-apply** with audit when confidence is high.
3. **Dependency metadata** — either new columns on `case_milestones` or a small **`milestone_dependencies`** table (from_milestone_id → to_milestone_id, rule_type).

**Prefer extending:** `timeline_service`, new `relocation_plan_service` (or `plan_orchestration_service`) that **calls** `NextActionService`, `CaseContextService` / document queries, and `build_intake_checklist_items` **internally** to build one response.

**Admin-only:** keep requirement evaluation triggers, template editing, and bulk replans behind existing admin routers; orchestration **reads** their outputs, does not reimplement evaluation SQL in the plan service.

---

## 4. Files / modules to touch (when implementing)

| Area | Files |
|------|--------|
| Plan assembly | New: `backend/app/services/relocation_plan_service.py` (or `plan_orchestration_service.py`) |
| Milestone defaults / phases | `backend/app/services/timeline_service.py` — extend defaults + grouping helpers |
| API surface | `backend/main.py` — e.g. `GET /api/assignments/{id}/relocation-plan` (canonical JSON for employee + HR) **or** extend existing timeline response with `v=2` / optional `include=phases,next_action` for backward compatibility |
| Mobility merge | `backend/services/next_action_service.py` — optional thin adapters if response shape must align with plan DTOs |
| Context/documents | `backend/services/case_context_service.py` — reuse fetch; avoid copy-paste of SQL into plan service (inject or call service methods) |
| HR intake bridge | `backend/hr_case_readiness_view.py` — keep mapping table `INTAKE_KEY_TO_TRACKER_TYPE`; may export a function plan service calls |
| DB access | `backend/database.py` — list/upsert milestones, new dependency rows, migrations for new columns |
| Migrations | `supabase/migrations/*` — align Postgres `case_milestones` with SQLite (e.g. `blocked`, `owner`, `criticality`, `notes` if any env still on older migration) |
| Admin inspect | `backend/services/mobility_inspect_service.py` — optional: include plan projection for debug |
| Frontend | `frontend/src/api/client.ts` (`timelineAPI`), `RelocationTaskTracker.tsx`, `EmployeeRelocationPlanPage.tsx`, HR case summary embeds — consume single plan payload |

---

## 5. Suggested new names

- **`RelocationPlanService`** or **`PlanOrchestrationService`** — builds phased view + next action + locked/unlocked flags.
- **`MilestoneReconciliationService`** — maps documents/evaluations/profile → suggested `status` / `blocked` / `actual_date`.
- **`milestone_dependencies`** (table) **or** columns `phase_key`, `depends_on_types` (JSON) — start minimal: `phase_key` + `display_group` on `case_milestones` before full graph.

---

## 6. Schema: extend vs new tables

### Extend `case_milestones` (low risk, backward compatible)

- `phase_key` (text) — e.g. `pre_move_admin`, `immigration`, `logistics`, `arrival`
- `phase_order` (int) — order within phase
- `unlocked` (boolean, default true) or derive-only in API first
- `auto_status_source` (text, nullable) — e.g. `evaluation:passport_copy_uploaded` for traceability
- `last_reconciled_at` (timestamptz, optional)

Existing: `status`, `owner`, `criticality`, `milestone_type`, `milestone_links` stay the contract.

### New table (when dependencies need integrity)

- **`milestone_dependencies`:** `id`, `case_id`, `milestone_id`, `depends_on_milestone_id`, `dependency_kind` (`hard_block` | `soft`), optional `requirement_code` FK for mobility rules.

### Do **not** duplicate

- Avoid a second “tasks” table mirroring milestones; use evaluations for **requirement** state and milestones for **plan** state, linked by `milestone_type` / metadata keys.

### Postgres note

- Early migration `20260325000000_case_milestones.sql` uses **uuid** `id` and status check **without** `blocked`; app/runtime DDL in `database.py` uses **text** `id` and **blocked** + owner/criticality. Operations should **converge** migrations with `_ensure_postgres_case_milestones_schema` reality before orchestration relies on new columns.

---

## 7. Implementation order (lowest risk first)

1. **Contract-only API extension** — Add optional fields to existing timeline JSON: `phases[]` (grouped server-side from `phase_key` or from a static map `milestone_type → phase`), no DB migration. Frontend can render accordion without behavior change.
2. **Server-side “next action” for assignment timeline** — Single function: top milestone by existing sort + urgency **plus** optional mobility next-actions when `case_id` is UUID and evaluations exist (feature-flag or non-breaking extra field `mobility_next_actions`).
3. **Reconciliation v0 (read-only)** — `MilestoneReconciliationService` computes `suggested_status` / `blockers[]` **without** writing DB; UI shows “System suggests: Done” with accept button → existing PATCH.
4. **Auto-apply safe transitions** — e.g. when evaluation flips to `satisfied` and `milestone_type` maps 1:1 to requirement_code, PATCH milestone to `done` + write `audit_logs` / evaluation note.
5. **Dependencies** — Add `milestone_dependencies` or `depends_on_milestone_id`; set `blocked` when upstream not `done`; expose in plan DTO.
6. **Progressive disclosure** — `visibility` rules in orchestration (e.g. hide phase until previous phase has no critical open items).
7. **Unify HR readiness rows** — Gradually align template `stable_key` → `milestone_type` where 1:1; avoid double maintenance.

---

## 8. Backward compatibility

- Keep **`GET /api/assignments/{id}/timeline`** response shape working for existing clients; add **additive** keys (`phases`, `plan_meta`, `next_action`, `reconciliation`) or version query param.
- Employee and HR both use **assignment-scoped** timeline today—continue that; mobility-only UUID cases can still use `/api/mobility/.../next-actions` until merged.
- Admin evaluation and compliance endpoints remain **source of truth writers**; orchestration is **consumer** first, then selective writer.

---

## 9. Summary

The product already has the right **spine** (`case_milestones` + `timeline_service` + shared GET by assignment). The cleanest path is **not** a parallel task system but an **orchestration layer** that groups milestones into phases, merges **NextActionService** + document/evaluation signals into one **next-action** object, adds **reconciliation** (suggested status), then **dependencies**. Schema-wise, **extend `case_milestones`** with phase metadata first; add a **dependencies** table when blocking logic needs relational integrity.
