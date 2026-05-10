# End-to-end identity & assignment verification

This document ties **structured observability** to **scenario-level proof** for the redesigned HR/Admin assignment → employee contact → invite → signup/login → reconcile → manual claim flow.

## How to read logs

- **Logger:** `backend.identity_observability`
- **Line prefix:** `identity_obs ` followed by a single JSON object (easy to grep in Loki/Datadog/CloudWatch).
- **Suggested queries:** `identity_obs`, `"event":"identity.assign.created"`, `"event":"identity.reconcile.complete"`.
- **Privacy:** Raw emails are **not** logged. Correlation uses `principal_fingerprint` (16-hex SHA-256 prefix of normalized email/username material). IDs (`company_id`, `employee_contact_id`, `assignment_id`, `auth_user_id`) are logged in full for traceability in **secured** log sinks.

### Common fields

| Field | When present |
|--------|----------------|
| `event` | Always |
| `request_id` | HTTP middleware / explicit pass-through where wired |
| `company_id` | Assignment creation, contact resolve |
| `employee_contact_id` | Contact resolve, pending invite ensure, reconcile (via DB paths) |
| `assignment_id` | Assignment create, invite ensure, reconcile attach, manual claim |
| `auth_user_id` | Signup/signin success, reconcile, claim |
| `principal_fingerprint` | Signup/signin/claim/reconcile user-correlation |
| `channel` | `hr` \| `admin` on `identity.assign.created` |
| `failure_code` / `reason` | Claim/signup/signin failures |

### Event catalog (implementation)

| Event | Meaning |
|--------|---------|
| `identity.contact.resolve` | `outcome`: `reused` \| `created` \| `reused_after_race` |
| `identity.invite.pending_ensure` | `outcome`: `created` \| `idempotent_reuse` \| `idempotent_reuse_concurrent` |
| `identity.assign.created` | Assignment row created; `variant=admin_placeholder` for sentinel `admin-created` |
| `identity.auth.signup.failed` | `reason`: e.g. `AUTH_EMAIL_TAKEN`, `AUTH_USERNAME_INVALID_FORMAT` |
| `identity.auth.signup.reconcile` | Post-signup reconcile summary or `outcome=error` |
| `identity.auth.signup.ok` | User row + session path succeeded |
| `identity.auth.signin.failed` | Bad identifier / password / missing user |
| `identity.auth.signin.reconcile` | Post-login reconcile summary or `outcome=error` |
| `identity.auth.signin.ok` | Login succeeded |
| `identity.reconcile.attach_skipped` | `reason`: `idempotent_same_user` \| `other_owner` \| `revoked_invites_only` |
| `identity.reconcile.complete` | Full counters + `attached_assignment_ids`; or `skipped_non_employee_role` / `skipped_no_principal_identifiers` |
| `identity.claim.manual` | Manual claim: `outcome`: `idempotent_already_linked` \| `attached` |
| `identity.claim.manual.failed` | `failure_code`: e.g. `CLAIM_ACCOUNT_IDENTIFIER_MISMATCH`, `CLAIM_ASSIGNMENT_ALREADY_CLAIMED` |

---

## Scenario matrix

| # | Scenario | Primary proof (logs) | Expected API / data outcome |
|---|----------|----------------------|-----------------------------|
| 1 | HR creates assignment → employee signs up later | `identity.assign.created` `channel=hr` → `identity.contact.resolve` → `identity.invite.pending_ensure` → `identity.auth.signup.ok` + `identity.auth.signup.reconcile` + `identity.reconcile.complete` | New user; assignment `employee_user_id` set; contact `linked_auth_user_id` set; invites consumed |
| 2 | Admin creates assignment → employee signs up later | Same as (1) with `channel=admin` | Same as (1) |
| 3 | Employee already has account → HR creates assignment later | `identity.assign.created` `pre_linked_auth_user=true`; no pending invite (`has_pending_invite=false`); optional `identity.contact.resolve` `reused` | Assignment immediately tied to user; no duplicate contact for same company+email |
| 4 | Employee already has account → Admin creates assignment later | Same as (3) with `channel=admin` | Same as (3) |
| 5 | Same employee gets second assignment | Second `identity.assign.created`; `identity.contact.resolve` `reused`; second `identity.invite.pending_ensure` `created` | One contact, two assignments, two pending claim rows |
| 6 | Repeated claim attempt | First: `identity.claim.manual` `outcome=attached` (or auto-reconcile `attach_skipped` `idempotent_same_user`); repeat: `outcome=idempotent_already_linked` or same skip | 200 success, idempotent; no duplicate attachment |
| 7 | Ambiguous / multi-company “unsafe” case | `identity.reconcile.complete` with `skipped_contacts_linked_to_other_user` > 0 or `skipped_assignments_other_user` > 0; signup may show reconciliation skips | No cross-user attachment; contact already owned by another auth user blocks link |

---

## Expected vs actual results

### Automated coverage (local / CI)

| # | Automated test module | What it proves |
|---|------------------------|----------------|
| 1–2 | `backend.tests.test_signup_reconciliation`, `test_assignment_claim_link_service` | HR-style unified creation + post-signup/login reconcile attaches assignment |
| 3–4 | `test_unified_assignment_creation.test_assignment_for_existing_linked_auth_user_skips_invites` | Pre-linked user: no pending invites, contact linked |
| 5 | `test_unified_assignment_creation.test_second_assignment_reuses_same_contact_same_company` | Reused contact, distinct assignments |
| 6 | `test_unified_assignment_creation.test_ensure_pending_invite_reuses_existing_row` | Idempotent `ensure_pending_assignment_invites` |
| 7 | `test_signup_reconciliation.test_reconcile_skips_contact_linked_to_another_auth_user` | Second user does not steal contact/assignment |

**Actual (most recent automated run):**

```text
# From repo root:
python3 -m unittest \
  backend.tests.test_identity_observability \
  backend.tests.test_unified_assignment_creation \
  backend.tests.test_assignment_claim_link_service \
  backend.tests.test_signup_reconciliation -v

# 2026-03-17 — exit 0, 23 tests OK (includes identity_obs log assertions + reconcile flow)
```

### Staging / production log validation (manual)

For each scenario row, capture one correlated trace (e.g. by `assignment_id` or `principal_fingerprint`):

| # | Expected log sequence seen? | Notes |
|---|-----------------------------|-------|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |
| 6 | | |
| 7 | | |

---

## Known limitations

1. **`request_id`** is not yet threaded through every path (e.g. `/api/auth/register` uses `request_id=None` today). Prefer correlating via `assignment_id` + `principal_fingerprint` + timestamps until middleware IDs are plumbed everywhere.
2. **Cross-company ambiguity** for the same email in multiple companies is handled by **per-company contacts** and **skip** semantics when a contact is already linked to another auth user; there is no single “global” merge in logs—look at `skipped_contact_other_user` / `skipped_assignments_other_user` on `identity.reconcile.complete`.
3. **Manual claim** events require the claim API to be exercised; auto-reconcile alone emits `identity.reconcile.*` but not `identity.claim.manual` unless the user uses the claim endpoint.
4. **SQLite tests** approximate Postgres behavior; race paths (`reused_after_race`, `idempotent_reuse_concurrent`) are harder to force in CI—validate under concurrent load in staging if needed.

---

## Related docs

- `docs/identity/final-state-summary.md` (architecture after stabilization)
- `docs/identity/unified-assignment-creation.md`
- `docs/identity/assignment-claim-flow.md`
- `backend/identity_observability.py`
