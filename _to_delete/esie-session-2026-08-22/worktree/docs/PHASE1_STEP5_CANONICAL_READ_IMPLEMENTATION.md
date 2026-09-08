# Phase 1 Step 5: Canonical Read Path Implementation

## Overview

Canonicalize read paths so backend reads prefer `canonical_case_id` while preserving backward compatibility with legacy `case_id`. No removal of legacy columns, no forced frontend route changes, no breaking changes to existing endpoints.

---

## Exact Files Changed

| File | Changes |
|------|---------|
| `backend/database.py` | Added `resolve_canonical_case_id`, `coalesce_case_lookup_id`; updated 12 read methods to use dual-column WHERE; added SQLite schema support for canonical_case_id on dossier/relocation tables |

---

## Exact Methods Added

| Method | Signature | Behavior |
|--------|-----------|----------|
| `resolve_canonical_case_id` | `(case_id: str) -> Optional[str]` | Returns `case_id` if it matches `wizard_cases.id`; else `None`. On error (e.g. wizard_cases missing), returns `None`. |
| `coalesce_case_lookup_id` | `(case_id: str) -> str` | Returns canonical when `resolve_canonical_case_id` succeeds; otherwise returns the original `case_id` unchanged. |

---

## Exact Read Paths Updated

| Method | Change |
|--------|--------|
| `list_case_events` | `cid = coalesce_case_lookup_id(case_id)`; WHERE `(canonical_case_id = :cid OR case_id = :cid)` |
| `list_case_participants` | Same pattern |
| `list_case_evidence` | Same pattern |
| `get_assignment_by_case_id` | Same pattern |
| `list_case_service_answers` | Same pattern |
| `list_dossier_answers` | Same pattern |
| `list_dossier_case_questions` | Same pattern |
| `list_dossier_case_answers` | Same pattern |
| `list_dossier_source_suggestions` | Same pattern |
| `get_latest_guidance_pack` | Same pattern |
| `list_trace_events` | Same pattern |

---

## SQLite Schema Extensions

Added `canonical_case_id` column to SQLite tables that did not have it:

- `relocation_guidance_packs`
- `dossier_answers`
- `dossier_case_questions`
- `dossier_case_answers`
- `dossier_source_suggestions`
- `relocation_trace_events`

---

## Live Read Endpoints (Automatic)

Endpoints that call the updated Database methods automatically benefit; no endpoint code changes required:

| Endpoint / Flow | Database Method(s) |
|-----------------|--------------------|
| Case details by assignment | `get_assignment_by_case_id` |
| Case events history | `list_case_events` |
| Case participants listing | `list_case_participants` |
| Case evidence listing | `list_case_evidence` |
| Case service answers | `list_case_service_answers` |
| Dossier questions/answers/suggestions | `list_dossier_*` |
| Latest guidance pack | `get_latest_guidance_pack` |
| Trace events | `list_trace_events` |

---

## Read Methods / Endpoints Still Using Raw Legacy case_id

| Method / Location | Reason |
|-------------------|--------|
| `list_rule_evaluation_logs` | `rule_evaluation_logs` has no `canonical_case_id` column; uses `WHERE case_id = :cid` only. Intentionally deferred. |
| `list_case_services` | Filters by `assignment_id`, not `case_id`; no change needed. |
| `list_assignment_evidence` | Filters by `assignment_id`, not `case_id`; no change needed. |
| `get_case_by_id` | Primary-key lookup on `relocation_cases`; `case_id` is the row id. No canonical mapping applies. |
| case_requirements_snapshots | No dedicated `list_*` method in Database taking `case_id`; reads occur via other paths. Deferred. |
| case_feedback | No dedicated `list_*` method in Database taking `case_id`; reads via `list_hr_feedback(assignment_id)`. Deferred. |
| case_resource_preferences | No dedicated case-scoped read method. Deferred. |
| rfqs | No dedicated `list_rfqs_by_case_id` in Database. Deferred. |

---

## Endpoints Intentionally Deferred

- None. All case-scoped read endpoints that go through the Database layer now use canonical lookup. Deferred items above are either assignment-scoped, primary-key lookups, or have no existing read method.

---

## Manual Verification Steps

1. **Wizard case (canonical)**  
   - Create a wizard case, get its `id`.  
   - Create assignment, events, participants, evidence, etc.  
   - Call read endpoints with that `id`.  
   - Confirm all case-scoped data is returned.

2. **Legacy relocation case**  
   - Use an existing `relocation_cases.id` that is not in `wizard_cases`.  
   - Call read endpoints with that `id`.  
   - Confirm backward compatibility: data is still returned when it exists.

3. **SQLite local dev**  
   - Run backend with SQLite.  
   - Exercise case events, participants, evidence, dossier flows.  
   - Confirm no "no such column: canonical_case_id" errors.

4. **Missing wizard_cases**  
   - In an environment where `wizard_cases` does not exist or is empty, `resolve_canonical_case_id` should return `None` and `coalesce_case_lookup_id` should return the input.  
   - Reads should still work via `case_id` branch of the dual-column WHERE.

---

## Rollback Notes

1. **Backend**  
   Revert `backend/database.py` changes for Phase 1 Step 5:
   - Remove `resolve_canonical_case_id` and `coalesce_case_lookup_id`.
   - Restore each updated read method to `WHERE case_id = :cid` (and remove `cid = coalesce_case_lookup_id(...)`).
   - Remove the SQLite schema block that adds `canonical_case_id` to dossier/relocation tables (optional; column presence does not break legacy reads).

2. **Database**  
   No migration rollback is required. Columns and data remain; reads simply stop using the dual-column pattern.

3. **Behavior after rollback**  
   Reads revert to using only `case_id`. Wizard cases that use `canonical_case_id` will not be found if the caller passes a different identifier; legacy cases continue to work as before.
