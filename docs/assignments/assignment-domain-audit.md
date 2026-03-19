# ReloPass Assignment Domain Audit

**Date:** 2025-03-19  
**Purpose:** Document the ReloPass assignment domain model, including canonical entities, company scoping, linkages, and current ambiguities.

---

## Canonical Entities

| Entity | Table | Key Columns | Purpose |
|--------|-------|-------------|---------|
| **companies** | `companies` | id, name, country, size_band, address, phone, hr_contact | Company profile record (created by Admin or on first HR save) |
| **hr_users** | `hr_users` | id, company_id, profile_id, permissions_json | Canonical HR→company mapping (one row per HR user) |
| **profiles** | `profiles` | id, role, email, full_name, company_id, status | User identity; company_id may be set by Admin assign |
| **employees** | `employees` | id, company_id, profile_id, band, assignment_type | Employee→company mapping |
| **case_assignments** | `case_assignments` | id, case_id, canonical_case_id, hr_user_id, employee_user_id, employee_identifier, status | Assignment linking case to employee |
| **relocation_cases** | `relocation_cases` | id, hr_user_id, company_id, employee_id, profile_json, status | Legacy case storage; carries company_id |
| **assignment_invites** | `assignment_invites` | id, case_id, hr_user_id, employee_identifier, token, status | Invite tokens for employees to claim assignments (no assignment_id) |

---

## Company Scoping Representation

- **Companies** are the top-level tenant; all HR and employee records are scoped by `company_id`.
- **Assignment visibility** is determined by company: an assignment belongs to a company either via:
  1. `relocation_cases.company_id` (case-level), or
  2. `hr_users.company_id` when `relocation_cases.company_id` is null (HR ownership fallback).

```sql
-- assignment_belongs_to_company (database.py)
WHERE a.id = :aid AND (rc.company_id = :cid OR (rc.company_id IS NULL AND hu.company_id = :cid))
```

- **list_assignments_for_company** uses the same predicate:
  `WHERE (rc.company_id = :cid OR (rc.company_id IS NULL AND hu.company_id = :cid))`

---

## HR→Company Linkage

| Source | Column | Usage |
|--------|--------|-------|
| **hr_users** | `hr_users.company_id` | Canonical; preferred for HR company resolution |
| **profiles** | `profiles.company_id` | Fallback when no hr_users row exists |

**Resolution order** (`db.get_hr_company_id(profile_id)`):

1. `SELECT company_id FROM hr_users WHERE profile_id = :pid LIMIT 1`
2. If missing: `get_profile_record(pid)` → `profile.company_id`

**Admin assign flow:** When Admin assigns HR to company (`POST /api/admin/people/{person_id}/assign-company`):

- `db.set_profile_company(person_id, company_id)` — updates `profiles.company_id`, `hr_users.company_id`, `employees.company_id`
- `db.ensure_hr_user_for_profile(person_id, company_id)` — creates `hr_users` row if missing

---

## Employee→Company Linkage

| Source | Column | Usage |
|--------|--------|-------|
| **employees** | `employees.company_id` | Canonical for employee records |
| **profiles** | `profiles.company_id` | Used when employee has profile; may be synced on Admin assign |

- `list_employees_with_profiles(company_id)` filters by `employees.company_id`
- `admin_reassign_employee_company` updates both `profiles.company_id` and `employees.company_id`

---

## Assignment→Company

An assignment is company-scoped via **one of**:

1. **relocation_cases.company_id** — when case has company set
2. **hr_users.company_id** — when `relocation_cases.company_id` is null (via `hr_user_id`)

`assignment_belongs_to_company` and `list_assignments_for_company` both use:

```
(rc.company_id = :cid OR (rc.company_id IS NULL AND hu.company_id = :cid))
```

On **assign_case**, when `profile.company_id` is set but `relocation_cases.company_id` is null, the backend upserts the case with `company_id` from the HR profile.

---

## Assignment→Employee

| Column | Purpose |
|--------|---------|
| **employee_user_id** | UUID of auth user (profiles.id) when employee has an account; may be null |
| **employee_identifier** | Required; typically email or username; used for invite matching and display |

- Assignment creation: `employee_user_id` is set if employee already has an account; otherwise null.
- Claim flow: `attach_employee_to_assignment` sets `employee_user_id` when employee proves identity via identifier match.

---

## Employee Without Account Representation

- **employee_user_id**: null when employee has no account yet
- **employee_identifier**: required; always populated (e.g. email like `jane@relopass.com`)

When HR assigns to an employee without an account:

1. `create_assignment` is called with `employee_user_id=None`, `employee_identifier=<email>`
2. Optionally, a new user is auto-created if identifier looks like email (`@` present) — `create_user` + `ensure_profile_record`
3. If no user exists: `create_assignment_invite` stores token; message body includes assignment_id and invite token
4. Employee receives message; must sign up, then claim using assignment_id + email

**Display:** `employee_name` is derived from:

- `profiles.full_name` (when employee_user_id present)
- `employee_first_name` + `employee_last_name` (HR-entered)
- `employee_identifier` as fallback

---

## Assignment ID Storage and Claim Flow

### Assignment ID

- **Storage:** `case_assignments.id` (UUID, generated at creation)
- **Generation:** `assignment_id = str(uuid.uuid4())` in `assign_case` (main.py)
- **Propagation:** Included in message body: `"Assignment ID: {assignment_id}"` — employee learns it from the notification/message

### assignment_invites

- **Schema:** `id`, `case_id`, `hr_user_id`, `employee_identifier`, `token`, `status`
- **No assignment_id:** Invites are keyed by `case_id` + `employee_identifier`; not by assignment_id
- **Status:** `ACTIVE` → `CLAIMED` when employee claims

### Claim Flow

1. **Employee** must be logged in and know `assignment_id` (from message or shared link).
2. **POST** `/api/employee/assignments/{assignment_id}/claim` with `{ email }`
3. **Validation:**
   - Request email/username must match logged-in user
   - `assignment.employee_identifier` must match user’s email/username
4. **On success:**
   - `db.attach_employee_to_assignment(assignment_id, effective["id"])` — sets `employee_user_id`
   - `db.mark_invites_claimed(assignment["employee_identifier"])` — marks invites by identifier
   - `ensure_case_participant` (role `relocatee`)
   - `insert_case_event` (event_type `assignment.claimed`)

### Frontend

- `EmployeeJourney.tsx`: User enters `claimId` (assignment_id) and `claimEmail`; calls `employeeAPI.claimAssignment(claimId, claimEmail)`.

---

## Current Ambiguities

### 1. assign_case vs list: Different company resolution

| Endpoint / Flow | Company resolution | Location |
|-----------------|--------------------|----------|
| **assign_case** | `profile.get("company_id")` | main.py:2967–2968 |
| **list assignments** (HR) | `_get_hr_company_id(effective)` | main.py:3532 |

**Impact:** `assign_case` uses `profiles.company_id` directly; list uses `hr_users.company_id` first, then `profiles.company_id`. If `hr_users.company_id` and `profiles.company_id` diverge, assign may use a different company than list.

### 2. _get_hr_company_id vs get_company_for_user

- `_get_hr_company_id`: hr_users first, then profile
- `get_company_for_user`: profile only

`/api/company` uses `get_company_for_user`; `/api/hr/company-profile` uses `_get_hr_company_id`. For HR users, `/api/company` may return nothing while `/api/hr/company-profile` works if profile.company_id is stale.

### 3. assign_case company fallback

When `hr_profile.get("company_id")` is null, assign_case raises 400 "No company linked to your profile". It does **not** fall back to `_get_hr_company_id`, so an HR user with `hr_users.company_id` set but `profiles.company_id` null cannot assign.

### 4. assignment_invites has no assignment_id

Invites are linked by `case_id` + `employee_identifier`. There is no direct FK to `case_assignments.id`. Resolving assignment from invite requires joining via case_id and employee_identifier. A token-based claim flow (e.g. magic link with token) would need this join.

### 5. Multiple case representations

- `wizard_cases` (primary)
- `relocation_cases` (legacy)
- `case_assignments` has both `case_id` and `canonical_case_id`; joins use `COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)` for compatibility.

---

## Recommendations

1. **Unify assign_case company resolution:** Use `_get_hr_company_id(effective)` instead of `profile.get("company_id")` in assign_case.
2. **Align list/assign:** Ensure both assign and list use the same HR company resolution path.
3. **Consider assignment_id on assignment_invites:** Add `assignment_id` for direct linkage and token-based claim flows.
4. **Document token vs assignment_id claim:** Clarify whether token-based claim should return assignment_id or if assignment_id-in-URL is the only supported path.

---

## References

- `backend/database.py`: create_assignment, list_assignments_for_company, assignment_belongs_to_company, get_hr_company_id, create_assignment_invite, mark_invites_claimed, attach_employee_to_assignment
- `backend/main.py`: assign_case, claim_assignment, _get_hr_company_id, _require_assignment_visibility
- `docs/performance/hr-company-profile-data-model-audit.md`
- `supabase/migrations/20260221105601_remote_schema.sql`, `20260324000000_canonical_case_id_phase1.sql`, `20260308000000_case_assignments_employee_names.sql`
