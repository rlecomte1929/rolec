# Employee assignment overview endpoint

Lightweight summaries for the authenticated employee: **linked** work (account already owns the assignment) and **pending** work (HR provisioned, awaiting explicit claim). No case draft, wizard payload, or employee profile hydration.

---

## Endpoint

| Method | Path | Auth |
|--------|------|------|
| `GET` | `/api/employee/assignments/overview` | Employee session (`require_role(EMPLOYEE)`); uses `_effective_user` |

### Behavior

1. Unless **admin impersonation** is active, runs **`_best_effort_reconcile_employee_assignments`** (same as `/assignments/current`) so contact linkage stays current.
2. Builds the JSON via **`build_employee_assignment_overview`** in `backend/services/employee_assignment_overview.py`.

Impersonation does **not** run reconcile (read-only parity with `/assignments/current`).

---

## Response contract

Top-level object:

```json
{
  "linked": [ /* ... */ ],
  "pending": [ /* ... */ ]
}
```

### `linked[]` — assignments where `case_assignments.employee_user_id` = current user

| Field | Type | Description |
|-------|------|-------------|
| `assignment_id` | string | Assignment primary key |
| `case_id` | string | Canonical case id (`COALESCE(canonical_case_id, case_id)`) |
| `company.id` | string \| null | Resolved company id (`relocation_cases.company_id` or `hr_users.company_id` fallback) |
| `company.name` | string \| null | From `companies` join |
| `destination.label` | string \| null | e.g. `home_country → host_country` when both set, else first non-empty |
| `destination.host_country` | string \| null | From `relocation_cases.host_country` |
| `destination.home_country` | string \| null | From `relocation_cases.home_country` |
| `status` | string | Assignment status, passed through **`normalize_status`** (same rules as the rest of the API) |
| `created_at` | string \| null | Assignment `created_at` |
| `updated_at` | string \| null | Assignment `updated_at` |
| `current_stage` | string \| null | **`relocation_cases.stage`** (cheap operational stage, if populated) |
| `relocation_case_status` | string \| null | **`relocation_cases.status`** |

No `wizard_cases` / draft reads in this path (keeps the query cheap and SQLite-safe).

### `pending[]` — `pending_claim` rows for contacts already linked to this user

| Field | Type | Description |
|-------|------|-------------|
| `assignment_id` | string | Assignment id |
| `case_id` | string | As for linked |
| `company.id` / `company.name` | string \| null | `COALESCE(rc.company_id, employee_contacts.company_id)` + `companies` |
| `destination.*` | | Same derivation as linked (from `relocation_cases` when joined) |
| `created_at` | string \| null | Assignment `created_at` |
| `claim` | object | See below |

#### `claim` object

Derived from **`assignment_claim_invites`** statuses for that assignment (bulk-loaded, lowercase):

| Field | Type | Meaning |
|-------|------|---------|
| `state` | string | `no_invite` \| `invite_pending` \| `invite_claimed` \| `invite_revoked` \| `mixed` |
| `requires_explicit_claim` | boolean | Always `true` for pending items (product: must link account to assignment explicitly) |
| `extra_verification_required` | boolean | `true` when `state` is `invite_revoked` or `mixed` (HR / non–self-serve paths likely) |

Logic:

- No invite rows → `no_invite`
- Any `pending` → `invite_pending`
- Else any `claimed` → `invite_claimed`
- Else all `revoked` → `invite_revoked`
- Otherwise → `mixed`

---

## Selection logic & scoping

### Linked

- **WHERE** `case_assignments.employee_user_id = :authenticated_employee_id`
- **JOIN** `relocation_cases` on the standard relocation join (`_relocation_cases_join_on`)
- **JOIN** `hr_users` and `companies` only for company name/id resolution

No cross-employee access: rows are strictly those owned by the user id on the assignment.

### Pending

- **INNER JOIN** `employee_contacts` with `linked_auth_user_id = :authenticated_employee_id`
- **AND** `employee_user_id IS NULL`
- **AND** `employee_link_mode` (trimmed, lower) = `pending_claim`
- **AND** company consistency guard:

  `relocation_cases` missing **or** contact/case company ids missing **or** **`rc.company_id` = `ec.company_id`** (text-cast safe for Postgres/SQLite)

  This prevents showing a pending assignment whose case was tied to a **different** company than the employee contact’s company (data anomaly / leak scenario).

### Bulk invite lookup

- **`map_claim_invite_statuses_by_assignments`**: single `IN (...)` query over `assignment_claim_invites` for all pending assignment ids.

---

## Implementation map

| Piece | Location |
|-------|-----------|
| HTTP route | `backend/main.py` — `get_employee_assignments_overview` |
| Response shaping | `backend/services/employee_assignment_overview.py` — `build_employee_assignment_overview` |
| SQL | `backend/database.py` — `list_employee_linked_assignment_overview`, `list_employee_pending_assignment_overview`, `map_claim_invite_statuses_by_assignments` |
| Tests | `backend/tests/test_employee_assignment_overview.py` |

---

## Frontend integration

`frontend/src/api/client.ts` exposes **`employeeAPI.getAssignmentsOverview()`** → `GET /api/employee/assignments/overview` (uncached so lists stay fresh after claim/dismiss).

Use after login to render linked + pending cards without loading full case detail until the user opens a specific assignment.
