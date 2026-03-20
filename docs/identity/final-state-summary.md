# Identity & assignment — final architecture (stabilization)

This is the **post-implementation** summary after the canonical identity model, unified assignment creation, signup/login reconcile, claim flow, guardrails, and instrumentation. Use it as the source of truth for **what must not regress**.

---

## Final canonical flows

### 1. HR or Admin creates an assignment (no auth pre-creation)

1. API handlers call **`create_assignment_with_contact_and_invites`** (`backend/services/unified_assignment_creation.py`) with `company_id`, HR/admin actor id, case id, and **employee identifier** (email or username-shaped string).
2. **`Database.resolve_or_create_employee_contact`** creates or reuses a **company-scoped** `employee_contacts` row. This is **not** a login account.
3. **`Database.create_assignment`** stores `employee_contact_id` and optional `employee_user_id` if the employee already has a `users` row.
4. If there is **no** `employee_user_id`, **`ensure_pending_assignment_invites`** creates aligned rows in:
   - **`assignment_invites`** (legacy-compatible row, case-scoped token), and  
   - **`assignment_claim_invites`** (canonical pending claim, assignment-scoped, idempotent per assignment).

### 2. Employee signs up or signs in

1. **Signup** checks **only** `users` (and username rules) for collisions — **not** `employee_contacts` (see `register` in `backend/main.py`).
2. After a successful **register** or **login**, **`reconcile_pending_assignment_claims`** (`assignment_claim_link_service`) runs for employees:
   - Links matching contacts to `auth_user_id` when safe.
   - Attaches unclaimed assignments; respects **other owner**, **revoked invites**, **idempotent same user**.
3. **Best-effort** reconcile also runs on **`GET /api/dashboard`** and **`GET /api/employee/assignments/current`** via `_best_effort_reconcile_employee_assignments` so late HR provisioning still links without requiring a new login.

### 3. Manual claim

**`claim_assignment`** (and related errors) handles explicit claim with identifier checks; complements auto-reconcile.

### 4. Legacy / repair paths

- **`identity_data_reconciliation`**: audits and safe fixes for historical rows (duplicate contacts, stale invites).
- **SQLite `_seed_demo_cases`**: still inserts **legacy** assignments **without** the unified pipeline — **local demo only**; documented in code.

---

## Removed or retired assumptions

| Old assumption | Current truth |
|----------------|---------------|
| Employee contact row implies a `users` row | Contact is operational identity; auth is optional until signup/login. |
| Signup blocked if email exists on `employee_contacts` | Blocked only if email/username exists in **`users`**. |
| One code path for “invite” without claim rows | Product flows use **`ensure_pending_assignment_invites`** (both tables). |
| Dashboard / employee UI assumes assignment exists at first paint | Assignment may appear **after** HR acts; refetch + server reconcile handle ordering. |
| Duplicate “ensure user” snippets in seed scripts | Single helper **`ensure_dev_seed_auth_user`** (`backend/dev_seed_auth.py`) for **dev auth rows only**. |

---

## What future developers must preserve

1. **Single writer for HR/admin assignment creation**  
   Use **`create_assignment_with_contact_and_invites`** (or the documented admin/HR endpoints that call it). Do not add parallel `create_assignment` + ad-hoc invite inserts for product features.

2. **Single reconcile implementation**  
   Use **`reconcile_pending_assignment_claims`** for auto-linking. The **`signup_reconciliation`** module is a **thin re-export** for compatibility only.

3. **Company isolation**  
   Contacts and matching stay **per `company_id`**. Do not match assignments across companies by email alone without explicit guardrails.

4. **Uniqueness**  
   - Auth: `users` email/username uniqueness.  
   - Operations: `employee_contacts` uniqueness scoped by company + normalized identifier (see DB constraints / `resolve_or_create_employee_contact`).

5. **Privacy / observability**  
   Structured identity logs use **`identity_observability`**; do not log raw emails in new code.

6. **Dev seed vs product**  
   **`ensure_dev_seed_auth_user`** is for **demo/local users** only. It must **not** be used to implement “HR invited employee” — that remains **contact + assignment + invites**, not `create_user`.

---

## Execution order (reference)

The program was delivered in this order; stabilization (this doc) is step **10**:

1. Audit → 2. Canonical model → 3. Unify Admin/HR assignment creation → 4. Fix signup → 5. Claim/link → 6. Reconcile old data → 7. Guardrails → 8. UX → 9. Instrumentation / verification → **10. Stabilization cleanup**.

---

## Related documents

- `docs/identity/unified-assignment-creation.md`
- `docs/identity/end-to-end-verification.md`
- `docs/identity/guardrails.md`
- `backend/services/identity_canonical.py` (import surface + table)
