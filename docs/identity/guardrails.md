# Identity & assignment linking guardrails

This document lists **invariants** enforced to prevent regression of duplicate contacts, cross-company leaks, duplicate claim invites, and auth/operational email confusion.

For **one-off cleanup** of historical bad rows, see [data-reconciliation-plan.md](./data-reconciliation-plan.md).

For **UX copy and order-of-operations** (HR first vs employee first), see [flexible-parallel-user-journeys.md](./flexible-parallel-user-journeys.md).

---

## Canonical code paths (service layer)

| Responsibility | Where | Notes |
|----------------|-------|--------|
| Find-or-create `employee_contacts` | `Database.resolve_or_create_employee_contact` | Only application writer of `employee_contacts` rows (except ops/reconciliation scripts). Normalizes via `identity_normalize`. **Idempotent** under unique indexes: concurrent `INSERT` races retry with `IntegrityError` + re-select. |
| HR/Admin assignment + invites | `unified_assignment_creation.create_assignment_with_contact_and_invites` | Always resolves contact first; never creates auth users. Imported via `services.identity_canonical` for discoverability. |
| Login / signup / employee-route auto-link | `assignment_claim_link_service.reconcile_pending_assignment_claims` | Single claim/link implementation; idempotent attaches + invite marking. |

**Do not** add parallel assignment-creation or ad-hoc `INSERT INTO employee_contacts` in feature code.

---

## Database (Postgres / Supabase)

| Invariant | Enforcement | Prevents |
|-----------|-------------|----------|
| Auth email unique in **auth domain only** | `public.users` unique on `email` (`users_email_key` in baseline schema) | Reusing another person’s login; **does not** block the same string in `employee_contacts` (company-scoped operational identity). |
| One operational contact per company + normalized email | Partial unique index `idx_employee_contacts_company_email_unique` on `(company_id, email_normalized)` where email non-empty | Duplicate HR invites for the same email in one company. |
| One operational contact per company + `invite_key` | `UNIQUE (company_id, invite_key)` on `employee_contacts` | Colliding username/invite keys within a company. |
| Assignment → contact integrity | `case_assignments.employee_contact_id` references `employee_contacts(id)` (nullable, `ON DELETE SET NULL`) | Orphan FKs at rest on Postgres when column is set. |
| **At most one pending** claim invite per assignment | Partial unique index `idx_assignment_claim_invites_one_pending_per_assignment` on `(assignment_id)` where `status = 'pending'` (migration `20260410120000_identity_link_guardrails.sql`) | Double pending tokens / duplicate auto-claim rows from races or bugs. |
| Claim invite token global uniqueness | `assignment_claim_invites.token` UNIQUE | Token reuse. |
| Lookup performance | Indexes on `employee_contacts(company_id)`, `(invite_key)`, `(linked_auth_user_id)`, partial on `email_normalized`; `assignment_claim_invites(assignment_id)`, `(assignment_id, status)` | Slow signup/login reconcile and HR assign. |

**Migration note:** applying the partial unique index runs a **deduplicating DELETE** on duplicate `pending` rows (keeps oldest `created_at`, tie-break `id`).

---

## Database (SQLite / local dev)

- Same logical indexes where supported: partial unique `assignment_id` for `status = 'pending'`, composite `(assignment_id, status)`, partial index on `email_normalized`.
- `PRAGMA foreign_keys=ON` on every SQLite connection so `REFERENCES` clauses are honored when present.
- `Database.create_assignment` **validates** that `employee_contact_id` (when provided) exists — catches app-layer mistakes before insert (SQLite may not declare FK on legacy `case_assignments` DDL).

---

## Service / API behavior

| Invariant | Enforcement | Prevents |
|-----------|-------------|----------|
| Normalized matching | `normalize_invite_key` / `email_normalized_from_identifier` on identifiers | Case/spacing drift breaking claim match. |
| Idempotent pending invites | `ensure_pending_assignment_invites` checks existing pending token; on `IntegrityError` re-reads token | Concurrent HR assigns creating two pendings. |
| Idempotent claim | `reconcile_pending_assignment_claims` + `attach_employee_to_assignment` + fresh read in `_try_attach_assignment` | Double attach; stealing assignments on stale reads. |
| Company isolation | Contacts scoped by `company_id`; employee assignment lists filtered by ownership / visibility — no cross-company merge in reconcile | One user seeing another company’s case via contact merge. |
| Structured errors | `identity_errors.IdentityErrorCode` + `err_detail()` on register, login, and `POST .../claim` | Opaque 4xx strings; clients can branch on `detail.code`. |

**Login vs signup vs claim (response shape):**

- **Register / login** success: `LoginResponse` with optional `reconciliation` (`PostSignupReconciliation`) when contacts linked or assignments attached (register: broader; login: only when **new** assignments attached).
- **Claim** success: `{ "success": true, "assignmentId": "..." }`.
- **Errors:** `detail` is `{ "code": "<IdentityErrorCode>", "message": "..." }` for structured endpoints (auth + claim).

---

## Tests

- `backend/tests/test_unified_assignment_creation.py` — unified path, contact reuse, idempotent invites.
- `backend/tests/test_assignment_claim_link_service.py` — claim/link idempotency and safety.
- `backend/tests/test_signup_reconciliation.py` — signup does not block on `employee_contacts`; auth uniqueness on `users` only.

Run:

```bash
python3 -m unittest \
  backend.tests.test_unified_assignment_creation \
  backend.tests.test_assignment_claim_link_service \
  backend.tests.test_signup_reconciliation \
  -v
```

---

## Related docs

- [assignment-claim-flow.md](./assignment-claim-flow.md)
- [signup-vs-employee-contact.md](./signup-vs-employee-contact.md)
- [data-reconciliation-plan.md](./data-reconciliation-plan.md)
