# Explicit link assignment flow (pending hub rows)

Employees see **pending** assignments on the hub when HR created work against their **employee contact** (same email/username) but the assignment is in **`pending_claim`** mode: the account is known, yet the employee must **confirm linkage** before `employee_user_id` is set.

This document covers the **strict** link path used from **Section B — Pending assignments**. The broader **manual UUID claim** path remains `POST /api/employee/assignments/{id}/claim` and does **not** require `pending_claim`.

---

## Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /api/employee/assignments/{assignment_id}/link-pending` | **Explicit pending link** — eligibility matches the employee overview “pending” rules + invite gates. |
| `POST /api/employee/assignments/{assignment_id}/claim` | **Manual claim** — identifier + assignment UUID; does not require pending_claim. |

Both accept the same JSON body: `{ "email": "<user's login email or username>" }` (must match the authenticated account — same check as manual claim).

---

## Validation steps (`link-pending`)

Order is enforced in `backend/services/explicit_pending_link_service.py` (`evaluate_pending_explicit_link_eligibility`).

1. **Assignment exists** — otherwise `404` / `not_found`.
2. **Idempotent already linked** — if `case_assignments.employee_user_id` equals the caller, return success with `alreadyLinked: true` (no duplicate DB writes).
3. **Not owned by another user** — if `employee_user_id` is set to a different id → `403` `CLAIM_ASSIGNMENT_ALREADY_CLAIMED`.
4. **Mode** — `LOWER(TRIM(employee_link_mode))` must be `pending_claim`. Otherwise → `409` `CLAIM_ASSIGNMENT_NOT_PENDING` (use manual claim if appropriate).
5. **Employee contact** — assignment must have `employee_contact_id`; contact must exist; `employee_contacts.linked_auth_user_id` must equal the caller → otherwise `403` `CLAIM_PENDING_CONTACT_MISMATCH`.
6. **Identity** — `assignment_identity_matches_user_identifiers` (assignment identifier / contact invite key / email vs account identifiers) must pass → otherwise `403` `CLAIM_ASSIGNMENT_IDENTIFIER_MISMATCH`.
7. **Company alignment** — same rule as overview pending list: if both relocation case `company_id` and contact `company_id` are non-empty, they must match → otherwise `403` `CLAIM_PENDING_COMPANY_MISMATCH`.
8. **Claim invites** — statuses from `assignment_claim_invites` (aligned with hub `claim.state` / `extra_verification_required`):
   - If only **revoked** rows (no `pending`, no `claimed`) → `403` `CLAIM_INVITE_REVOKED`.
   - If **neither** `pending` nor `claimed`, and **not** all revoked (e.g. unknown / mixed) → `403` `CLAIM_EXTRA_VERIFICATION_REQUIRED`.
   - Empty invite list → allowed (same as overview `no_invite`).

Impersonation is denied the same way as other employee mutations (`_deny_if_impersonating`).

---

## Status transitions (success)

| Artifact | Before | After successful link |
|----------|--------|------------------------|
| `case_assignments.employee_user_id` | `NULL` | Current auth user id |
| `case_assignments.employee_link_mode` | `pending_claim` | Cleared (`NULL` after attach) |
| `assignment_claim_invites` (pending rows) | `pending` | `claimed` (via `mark_invites_claimed`) |
| Case participant | May be missing | `ensure_case_participant` (relocatee) |
| `case_events` | — | `assignment.claimed` with `payload.path = explicit_pending_link` |

Telemetry: `identity.claim.pending_explicit` with `outcome` `attached` or `idempotent_already_linked`. Failures emit `identity.claim.pending_explicit.failed` with `failure_code` derived from the internal reason.

---

## Failure modes (summary)

| Condition | HTTP | `IdentityErrorCode` (in `detail`) |
|-----------|------|-----------------------------------|
| Unknown assignment id | 404 | plain message |
| Wrong account identifier in body | 400/403 | `CLAIM_MISSING_*`, `CLAIM_ACCOUNT_IDENTIFIER_MISMATCH` |
| Another user owns assignment | 403 | `CLAIM_ASSIGNMENT_ALREADY_CLAIMED` |
| Not `pending_claim` | 409 | `CLAIM_ASSIGNMENT_NOT_PENDING` |
| Contact not linked / missing | 403 | `CLAIM_PENDING_CONTACT_MISMATCH` |
| Identifier does not match assignment | 403 | `CLAIM_ASSIGNMENT_IDENTIFIER_MISMATCH` |
| Company mismatch | 403 | `CLAIM_PENDING_COMPANY_MISMATCH` |
| Revoked-only invites | 403 | `CLAIM_INVITE_REVOKED` |
| Mixed / non-standard invite state | 403 | `CLAIM_EXTRA_VERIFICATION_REQUIRED` |

---

## Success state

Response:

```json
{
  "success": true,
  "assignmentId": "<uuid>",
  "alreadyLinked": false
}
```

On idempotent replay for the same user:

```json
{
  "success": true,
  "assignmentId": "<uuid>",
  "alreadyLinked": true
}
```

The frontend should refetch **`GET /api/employee/assignments/overview`** (and invalidate `employee:current-assignment` cache). The assignment appears under **linked**; the employee can open the case (e.g. `/employee/case/{id}/summary`).

---

## Frontend

- `employeeAPI.linkPendingAssignment(assignmentId, email)` → `POST .../link-pending`.
- Hub **Link assignment** uses this API (not `claim`) so only **eligible pending** rows can be linked through this path.

---

## Security notes (v1)

- **No extra modal** for assignment id / company in v1: the user already authenticated; the body re-confirms **email/username** matches the session (same as manual claim).
- **Idempotency** prevents duplicate attachment rows; `attach_employee_to_assignment` is a single-row update.
- **Guessing UUIDs** is not enough: without pending_contact + `pending_claim` + identity + company + invite rules, `link-pending` returns 403/409.

---

## Tests

- `backend/tests/test_explicit_pending_link.py` — eligibility, idempotency, company mismatch, mode, contact link, revoked invites, non-standard invite status.

---

## Related docs

- [employee-assignment-hub.md](./employee-assignment-hub.md) — UI sections and fields.
- [employee-assignment-overview-endpoint.md](./employee-assignment-overview-endpoint.md) — pending vs linked definitions.
- [linked-vs-pending-model.md](./linked-vs-pending-model.md) — `employee_link_mode` semantics.
