# Unified assignment creation (HR + Admin)

## Old behavior

- **HR** (`POST /api/hr/cases/{case_id}/assign`) and **Admin** (`POST /api/admin/assignments`) each implemented their own sequence: resolve or create `employee_contacts`, insert `case_assignments`, then optionally create `assignment_invites` + `assignment_claim_invites`.
- Contact resolution was effectively “company + `invite_key`” only; the same normalized email could theoretically diverge if identifiers differed only by casing/spacing unless callers normalized consistently.
- Risk of **logic drift** between the two handlers (different ordering, error handling, or invite rules).

## New behavior

Both entry points call **`create_assignment_with_contact_and_invites`** in `backend/services/unified_assignment_creation.py`, which performs one ordered pipeline (see below). HR keeps **separate** responsibilities that are not part of this service: case validation, `ensure_profile_record` / `ensure_employee_for_profile` for **existing** auth users, `ensure_case_participant`, `insert_case_event`, and draft `create_message`.

## Shared service responsibilities

**Function:** `create_assignment_with_contact_and_invites(db, *, company_id, hr_user_id, case_id, employee_identifier_raw, employee_first_name, employee_last_name, employee_user_id, assignment_status, request_id, assignment_id=None)`

| Step | Responsibility |
|------|----------------|
| 1 | **Normalize** identifier (`normalize_invite_key`) and derive **normalized email** when the string is email-shaped (`email_normalized_from_identifier`). |
| 2 | **Resolve** `employee_contacts` row: if normalized email is present, match `company_id + email_normalized`; else match `company_id + invite_key` (canonical key = email when email-like, else normalized identifier). |
| 3 | **Insert** contact only if no row matched (never creates `users`). |
| 4 | If `employee_user_id` is set, **idempotently** set `employee_contacts.linked_auth_user_id` (`link_employee_contact_to_auth_user`). |
| 5 | **Insert** `case_assignments` with `employee_contact_id` and normalized `employee_identifier`. |
| 6 | If there is **no** `employee_user_id`, **ensure** a **pending** legacy + claim invite via `Database.ensure_pending_assignment_invites` (reuses existing pending row for the same `assignment_id` if present). |
| 7 | Return **`UnifiedAssignmentCreationResult`** (`assignment_id`, `case_id`, `employee_contact_id`, `stored_identifier`, `invite_token`, `employee_user_id`). |

**Explicit non-responsibilities**

- Does **not** create auth users or call signup.
- Does **not** create the relocation case (`create_case` remains the caller’s job so HR can assign to an existing case).
- Does **not** send email or write HR message drafts.

**Placeholder admin assignments**

- Identifier sentinel **`admin-created`** skips contact resolution and invites; creates an assignment row only (unchanged product behavior for minimal admin-created rows).

## Database constraints

- Partial unique index **`(company_id, email_normalized)`** where `email_normalized` is non-null (migration `20260321120000_employee_contacts_unique_email_per_company.sql` + SQLite init) enforces **at most one contact per company per normalized email**.

See also [signup-vs-employee-contact.md](./signup-vs-employee-contact.md) for how registration interacts with pre-provisioned contacts.

## Tests

See `backend/tests/test_unified_assignment_creation.py` (stdlib `unittest`). From the **repo root**:

```bash
python3 -m unittest backend.tests.test_unified_assignment_creation -v
```

Coverage:

- First assignment for a new email → one contact + pending invite.
- Second assignment, same company, same email (different casing/spacing) → **same** `employee_contact_id`, two assignments, two invite tokens.
- Assignment with **existing** `employee_user_id` → **no** invites; contact linked to auth user.
- `ensure_pending_assignment_invites` returns the same token when called again for the same assignment (idempotent).
