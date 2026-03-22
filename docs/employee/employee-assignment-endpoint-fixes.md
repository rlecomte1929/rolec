# Employee assignment endpoint fixes (Phase 2)

## Handlers

- `GET /api/employee/assignments/overview` — `backend/main.py` → `build_employee_assignment_overview`
- `GET /api/employee/assignments/current` — `backend/main.py` → `list_linked_assignments_for_employee` + `list_pending_claim_assignments_for_auth_user`

## Root causes addressed

1. **Serialization** — Row mappings from SQLAlchemy/Postgres could include `uuid.UUID`, `datetime`, or `Decimal`. These are now normalized to JSON-safe types in `backend/services/employee_assignment_overview.py` (`_json_scalar`) and via `_sanitize_assignment_row_dict` for `current`.
2. **Partial DB failure** — Linked and pending overview queries are each wrapped in `try/except` with logging; empty partial results instead of a single exception killing the whole overview.
3. **Invite map failures** — `map_claim_invite_statuses_by_assignments` failures degrade to empty invite state per assignment.
4. **Top-level safety net** — `overview` handler wraps `build_employee_assignment_overview` in `try/except` and returns `{ linked: [], pending: [], overview_degraded: true }` on unexpected errors. `current` wraps list queries similarly and returns empty lists + `overview_degraded: true`.
5. **identity_event** — Wrapped in `try/except` so logging cannot break the response.
6. **Join typing** — `backend/database.py` `_relocation_cases_join_on` now uses `CAST(rc.id AS TEXT) = CAST((<rhs>) AS TEXT)` on Postgres to avoid uuid/text operator issues.

## Safe response behavior

| Endpoint | Normal | Degraded / empty |
|----------|--------|------------------|
| `overview` | `{ linked: [...], pending: [...] }` | `{ linked: [], pending: [] }` optionally `overview_degraded: true` |
| `current` | `assignment`, `linked_assignments`, `pending_claim_assignments` | `assignment: null`, empty arrays, optional `overview_degraded: true` |

**Authorization** unchanged: still `require_role(EMPLOYEE)`; no broadening of data visible to the user.

## Verification

- `python -m unittest backend.tests.test_employee_assignment_overview`
