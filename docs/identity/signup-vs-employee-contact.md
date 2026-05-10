# Signup vs employee contact

## What was causing the conflict (historical / risk)

- Product expectation: **HR can pre-create** `employee_contacts` and **assignments** using an employee’s **email** before that person registers.
- If signup (or any layer) treated **“email already known”** as **“auth email taken”**—for example by enforcing uniqueness on `profiles.email`, syncing from non-auth tables, or blocking on invite rows—registration would **incorrectly fail** even though **no row existed in `public.users`** (the real auth account table for this API).
- The backend register handler must only consult **`users`** (via `get_user_by_email` / `create_user` uniqueness) for “email already in use”.

## What signup now checks

`POST /api/auth/register` (`backend/main.py`):

1. **Username** — must not already exist on **`users`** (`get_user_by_username`). Failure returns structured detail:
   - `code`: `AUTH_USERNAME_TAKEN`
   - `message`: human-readable string
2. **Email** — must not already exist on **`users`** (`get_user_by_email`). Failure returns:
   - `code`: `AUTH_EMAIL_TAKEN`
   - `message`: e.g. *An account with this email already exists. Try logging in instead.*
3. **`create_user`** — still subject to DB **unique constraint on `users.email`**; on failure returns `AUTH_USER_CREATE_FAILED`.

**Explicitly not used to block signup:**

- `employee_contacts` (company-scoped operational identity)
- `case_assignments` / `relocation_cases`
- `assignment_invites` / `assignment_claim_invites`
- Any other company workflow tables

`profiles` is written **after** user creation with the new `user_id` as primary key; it does not reserve email for someone else in this flow.

## What happens after signup (and login)

**Canonical implementation:** `reconcile_pending_assignment_claims` in **`backend/services/assignment_claim_link_service.py`**. Full lifecycle, rules, ambiguity handling, and UX copy are documented in **[assignment-claim-flow.md](./assignment-claim-flow.md)**.

For **`EMPLOYEE`** registrations (and post-login employee bootstrap) with **email and/or username**, the server runs that reconcile path. The thin alias **`reconcile_employee_signup_after_register`** remains in `backend/services/signup_reconciliation.py` (re-export only).

At a high level:

1. **Normalize** principals (email / username → invite-key style identifiers).
2. **Discover contacts** (email match + `invite_key` paths).
3. **Per contact** — link auth user when safe; **skip** if contact is bound to another user.
4. **Unassigned assignments** for those contacts (plus legacy rows without `employee_contact_id`) — attach, mark invites claimed, optional case side effects; **revoked-only** claim invites can block auto-attach.

**Multi-company:** the same person may have contacts in more than one company (same email); each contact is handled independently—**no cross-company merge** of rows, only per-contact linking.

**Multiple assignments** under one company / one contact are all attached in a loop.

**Response:** `LoginResponse` may include **`reconciliation`** (`PostSignupReconciliation`): `linkedContactIds`, `attachedAssignmentIds`, skip counters, `headline` / `message`.

**Frontend:** after register or login, reconciliation may be stored (e.g. **`post_auth_claim_reconciliation`** / legacy **`post_signup_reconciliation`**); **`EmployeeJourney`** shows alerts and refetches the current assignment when appropriate.

Structured auth error codes are defined in `backend/identity_errors.py` and documented with DB invariants in **[guardrails.md](./guardrails.md)**.

## Tests

```bash
python3 -m unittest backend.tests.test_assignment_claim_link_service backend.tests.test_signup_reconciliation -v
```

`test_assignment_claim_link_service.py` covers the canonical claim/link service (pending assignment, idempotency, stale-row safety, revoked invites, username principal).

`test_signup_reconciliation.py` covers HR/admin-style pre-provisioned assignment, no pending data, contact already linked to another user, and **`create_user`** failing on duplicate email (auth table only).
