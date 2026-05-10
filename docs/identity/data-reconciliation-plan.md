# Identity & assignment data reconciliation plan

This document describes **historical inconsistencies** that can appear when evolving from legacy HR flows (pre-created auth users, duplicate contacts, missing `employee_contact_id`) to the **canonical model** ([assignment-claim-flow.md](./assignment-claim-flow.md), [unified-assignment-creation.md](./unified-assignment-creation.md)).

**Implementation**

- Service: `backend/services/identity_data_reconciliation.py` (`audit_identity_data`, `apply_safe_fixes`)
- CLI: `backend/scripts/reconcile_identity_data.py`

**Prevention (ongoing):** see [guardrails.md](./guardrails.md) for schema + API invariants that stop these issues from recurring.

**Operating principles**

1. **Audit first** — classify issues; never mutate without a prior report.
2. **Dry-run default** — CLI runs fixes inside a **rolled-back** transaction and prints counts.
3. **Conservative merges** — duplicate `employee_contacts` are merged **only** when there is **no conflicting `linked_auth_user_id`** between rows in the same duplicate group.
4. **No silent identity resolution** — ambiguous auth/contact conflicts are **manual review** only.
5. **Re-run** — after `--apply`, run audit again; some fixes (e.g. contact merge before link) may require a second pass.

---

## Categories of inconsistencies

| Code | Description |
|------|-------------|
| `duplicate_employee_contacts` | More than one `employee_contacts` row for the same `company_id` and same **normalized** `email_normalized` (trim + lowercase). Often pre-dates partial unique index `idx_employee_contacts_company_email_unique` or came from inconsistent normalization. |
| `assignment_missing_employee_contact_id` | `case_assignments.employee_contact_id` empty but `employee_identifier` present — legacy rows before backfill. |
| `assignment_orphan_employee_contact` | `employee_contact_id` points to a **missing** `employee_contacts` row (bad FK / manual delete). |
| `assignment_contact_company_mismatch` | `employee_contacts.company_id` ≠ `relocation_cases.company_id` for the assignment’s case — wrong contact attached. |
| `contact_linkable_to_auth_user` | `email_normalized` matches a `users.email` (case-insensitive), but `linked_auth_user_id` is null — signup/link never ran. |
| `contact_linked_auth_user_missing` | `linked_auth_user_id` set but no matching `users.id` — orphan pointer. |
| `claim_invite_pending_but_assignment_assigned` | `assignment_claim_invites.status = pending` while `case_assignments.employee_user_id` is set — state drift after manual assignment or partial claim. |
| `claim_invite_claimed_user_mismatch` | Claim row `claimed_by_user_id` ≠ assignment `employee_user_id` — serious ambiguity. |
| `claim_invite_multiple_pending` | More than one **pending** claim invite for the same `assignment_id` — token / resend bug. |
| `legacy_invite_active_but_assigned` | `assignment_invites` still `ACTIVE` for a case + identifier that already has an assignment with `employee_user_id` set. |
| `employee_user_id_orphan` | Assignment references a missing `users` row. |
| `suspicious_employee_user_no_password` | **Heuristic only**: `users.role` is employee-like and `password_hash` empty — may indicate abandoned placeholder accounts or SSO-only users; **never auto-deleted**. |

**Legacy tables** (`employees`, old profile links) are out of scope for automatic repair; treat them as **manual** if they contradict `case_assignments`.

---

## Remediation logic

### Auto-fix (safe)

| Action | When | What it does |
|--------|------|----------------|
| `merge_duplicate_employee_contacts` | Same `(company_id, normalized email)` group; **all** non-null `linked_auth_user_id` values are equal or **at most one** row is linked | Pick **canonical** row: prefer linked contact, else oldest `created_at`. Repoint `case_assignments.employee_contact_id` and `assignment_claim_invites.employee_contact_id` from losers → canonical; **delete** loser contacts. |
| `backfill_employee_contact_id` | Missing contact id, identifier + resolvable case `company_id` | Same resolution order as `Database._backfill_employee_contacts` / `resolve_or_create_employee_contact`: match by `email_normalized`, then `invite_key`, else **insert** contact. |
| `link_employee_contact_to_auth_user` | Email match to exactly one user row; contact link empty | `UPDATE employee_contacts SET linked_auth_user_id` (idempotent `WHERE` clause). |
| `sync_claim_invite_to_assigned_employee` | Pending claim invite + assignment already has `employee_user_id` | Set invite `claimed`, `claimed_by_user_id`, `claimed_at`. |
| `mark_legacy_invite_claimed` | Legacy `assignment_invites` ACTIVE + same case + normalized identifier has assigned employee | `UPDATE … status = 'CLAIMED'`. |

Fix execution order inside one run: **merge → backfill → link → sync claim → legacy invite**.

Counters increment only when an `UPDATE`/`DELETE` actually affects rows (avoids noise after merges removed a contact that also had a pending “link” suggestion).

### Manual review (no auto-fix)

| Situation | Reason |
|-----------|--------|
| Duplicate contacts with **different** non-null `linked_auth_user_id` | Would merge two real auth identities — **forbidden** without human decision. |
| `assignment_orphan_employee_contact` | Cannot infer correct contact without HR input. |
| `assignment_contact_company_mismatch` | Cross-company attach — likely data entry error; fix case or contact in admin tooling. |
| `claim_invite_claimed_user_mismatch` | Possible fraud or support mistake — reconcile with logs. |
| `claim_invite_multiple_pending` | Revoke/consolidate invites after deciding which token is valid. |
| `employee_user_id_orphan` | Re-point assignment to real user or clear + re-invite. |
| `suspicious_employee_user_no_password` | Confirm with product/security; may be valid (future SSO) or stale seed. |

---

## What is auto-fixed vs manual (summary)

| Auto | Manual |
|------|--------|
| Duplicate contacts **without** conflicting auth links | Duplicate contacts **with** conflicting auth links |
| Missing `employee_contact_id` when case company + identifier resolve | Orphan / wrong-company `employee_contact_id` |
| Link contact → user when emails match and link empty | Orphan `linked_auth_user_id` |
| Pending claim invite vs assigned employee (sync) | Claimed-by ≠ assignment employee |
| Legacy ACTIVE invite when employee already assigned | Multiple pending claim invites per assignment |
| | Orphan `employee_user_id` on assignment |
| | “Suspicious” employee users (report only) |

---

## CLI workflow

```bash
# Audit + simulated fixes (transaction rolled back)
PYTHONPATH=. python backend/scripts/reconcile_identity_data.py

# Write machine-readable report
PYTHONPATH=. python backend/scripts/reconcile_identity_data.py --json-out ./identity-audit.json

# After review — persist safe fixes only
PYTHONPATH=. python backend/scripts/reconcile_identity_data.py --apply
```

Then **re-run without `--apply`** to confirm counts dropped; repeat until only manual items remain.

**Production**: run against a **backup** or maintenance window; Postgres should use a migration user / service role consistent with your RLS setup.

---

## Related documentation

- [assignment-claim-flow.md](./assignment-claim-flow.md) — runtime claim/link behavior
- [signup-vs-employee-contact.md](./signup-vs-employee-contact.md) — why `users` vs `employee_contacts` must stay separate
