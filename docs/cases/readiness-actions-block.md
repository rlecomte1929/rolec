# Readiness & Actions block (HR case summary)

## Purpose

Replace the disconnected **Profile completeness %** and **Compliance status** tiles with one **Readiness & actions** card that ties together:

- Explicit intake/document checkpoints  
- Route template checklist counts (when readiness resolves)  
- Latest **assignment-level compliance** run (`ComplianceEngine` + provenance enrich)  
- Trust / human-review messaging  

**Placement:** Immediately after **Case essentials**, before expandable **Case readiness** (template detail) and **Timeline**.

## API (single request)

`GET /api/hr/assignments/{id}` now returns:

| Field | Description |
|--------|-------------|
| `intakeChecklist` | List of `{ key, label, satisfied, category }` — deterministic from employee profile JSON. |
| `readinessSnapshot` | Full JSON from `db.get_hr_readiness_summary` (template, checklist counts, disclaimers, references). |
| `caseReadinessUi` | Pre-merged view model for the card (status, basis string, blocking rows, actions, trust banner, deadline). |

No extra HTTP round-trips.

## Backend modules

- `backend/hr_case_readiness_view.py`  
  - `build_intake_checklist_items(profile)`  
  - `build_hr_case_readiness_ui(...)`  
- `backend/main.py` — `get_hr_assignment` calls readiness summary + builders, validates `CaseReadinessUi`.

## Intake checkpoints counted (explicit)

Each item is **boolean** from current profile dict (same source as wizard / `RelocationProfile`):

1. `employee_name` — `primaryApplicant.fullName`  
2. `route_origin` — `movePlan.origin`  
3. `route_destination` — `movePlan.destination`  
4. `family_status` — `maritalStatus` **or** `spouse.fullName` **or** any `dependents[].firstName`  
5. `passport_details` — passport number, issuing country, or expiry  
6. `job_level` — `primaryApplicant.employer.jobLevel`  
7. `role_title` — `primaryApplicant.employer.roleTitle`  
8. `timeline` — `assignment.startDate` **or** `movePlan.targetArrivalDate`  
9. `doc_passport` — `complianceDocs.hasPassportScans === true`  
10. `doc_employment_letter` — `complianceDocs.hasEmploymentLetter === true`  

If `profile` is missing, **all** are `satisfied: false` (same keys).

These align with fields the internal **compliance engine** cares about (docs, job level, dates) without running a second scoring engine.

## Route checklist (template)

When `readinessSnapshot.resolved` and `checklist.total > 0`:

- `completion_basis` includes `completed_or_waived` / `total` from `case_readiness_checklist_state` + template items.  
- Open checklist rows contribute **blocking** and **human review** flags per provenance rules on the readiness side.

## Compliance checks

Non-`COMPLIANT` rows from the latest stored compliance report become **blocking_items** with:

- `rationale`, `rationale_legal_safety` → `provenance_note`  
- `human_review_required` preserved  

Actions from the report are merged into **next_actions** (deduped by title).

## Overall status (`overall_label` / `overall_status`)

Resolved in `build_hr_case_readiness_ui` with this **priority**:

1. **Missing information** — no profile **or** any intake checkpoint unsatisfied **or** readiness `reason === no_destination`.  
2. **Human review required** — readiness not resolved (store/template/error), or resolved compliance with `human_review_required` on template trust.  
3. **Needs review** — compliance `NON_COMPLIANT` / `NEEDS_REVIEW`, or no compliance run yet (`overallStatus` null), or route checklist pending &gt; 0.  
4. **Ready** — compliance `COMPLIANT`, all intake satisfied, readiness resolved, no checklist pending, and template does not force `human_review_required`.  

Immigration **eligibility is never** implied as legally verified; trust copy comes from compliance + readiness disclaimers.

## Completion basis string

Human-readable, e.g.:

- `7 of 10 intake & document checkpoints satisfied; 3 of 12 route checklist items completed (template)`

## Frontend

- `frontend/src/features/cases/ReadinessAndActionsBlock.tsx`  
- `frontend/src/pages/HrCaseSummary.tsx` — removed the 3-column completeness/compliance/deadline grid and the duplicate large compliance card; optional collapsible **step-by-step log** remains for auditors.

## Orchestrator `completeness` field

`AssignmentDetail.completeness` (legacy heuristic %) is **unchanged** for other consumers but **no longer shown** on this page.
