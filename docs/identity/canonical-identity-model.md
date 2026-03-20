# Canonical identity model

Structural split between **auth**, **company-scoped contacts**, **assignments**, and **claim records**. HR can create contacts and assignments before any signup; signup only touches `users` / auth tables.

## Final entities

| Entity | Table(s) | Role |
|--------|----------|------|
| **Auth user** | `users` (+ sessions, profiles as today) | Real login account. **Email/username uniqueness applies here only.** |
| **Employee contact** | `employee_contacts` | Company-scoped operational person: `company_id`, `invite_key` (normalized identifier), optional `email_normalized`, name fields, optional `linked_auth_user_id`. **No row in `users` required.** Unique `(company_id, invite_key)`. |
| **Assignment (case link)** | `case_assignments` + `relocation_cases` | Relocation assignment: `company_id` via case, `employee_contact_id` (optional but set for new HR flows), `employee_user_id` when claimed, `employee_identifier` (normalized copy for legacy queries/messages). |
| **Assignment invitation / claim** | `assignment_invites` (legacy, case-scoped token), `assignment_claim_invites` (canonical) | Bridge for claiming: links `assignment_id` + `employee_contact_id`, optional `email_normalized`, `token`, `status` (`pending` / `claimed` / `revoked`), `claimed_by_user_id`, `claimed_at`. |

## Relationships

```
companies
   └── employee_contacts (company_id) ──optional──► users (linked_auth_user_id)
   └── relocation_cases (company_id)
            └── case_assignments (case_id, employee_contact_id?, employee_user_id?)
                     └── assignment_claim_invites (assignment_id, employee_contact_id)
```

- Many **assignments** can reference the same **employee contact** (same `employee_contact_id` on multiple `case_assignments` rows).
- Linking auth later: `attach_employee_to_assignment` sets `employee_user_id` and idempotently sets `employee_contacts.linked_auth_user_id` when null or already the same user.

## Normalization

- `identity_normalize.normalize_invite_key` — trimmed lowercase match key for email or username.
- `identity_normalize.email_normalized_from_identifier` — normalized email when identifier contains `@`.
- Assign flows store **normalized** `employee_identifier` on `case_assignments` for consistent matching; legacy rows still match via `LOWER(TRIM(employee_identifier))` or `employee_contacts.invite_key` in `get_unassigned_assignment_by_identifier`.

## What changed from the previous design

1. **No placeholder auth users** — HR assign no longer calls `create_user` with a temporary password. Pre-signup employees exist only as `employee_contacts` (+ assignment rows).
2. **Contacts do not reserve auth emails** — `employee_contacts` are scoped by `company_id`; the same normalized email can exist as a contact in company A without blocking signup of a real `users` row (global uniqueness remains on `users` only).
3. **Explicit claim table** — `assignment_claim_invites` records pending/claimed state and `claimed_by_user_id`; legacy `assignment_invites` remains for existing token flows and is updated in parallel where applicable.
4. **Backfill** — `Database._backfill_employee_contacts()` attaches `employee_contact_id` to old assignments when `relocation_cases.company_id` is present (idempotent).

## Migrations / code

- Postgres: `supabase/migrations/20260320120000_canonical_identity_employee_contacts.sql`, `20260321120000_employee_contacts_unique_email_per_company.sql`
- App layer: `backend/database.py` (CRUD, backfill, claim marking), `backend/main.py` (HR assign, admin create, employee claim/auto-attach), `backend/identity_normalize.py`.
- **HR + Admin assignment creation** share `backend/services/unified_assignment_creation.py` — see [unified-assignment-creation.md](./unified-assignment-creation.md).

Full end-to-end refactors (e.g. every read path keyed only on `employee_contact_id`) are intentionally **out of scope** for this pass; behavior remains backward-compatible with rows that only have `employee_identifier`.
