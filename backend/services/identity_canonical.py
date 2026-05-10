"""
Canonical import surface for identity / assignment linking.

**Do not** add parallel assignment-creation or claim paths outside these modules:

| Concern | Module / API |
|--------|----------------|
| HR/Admin creates assignment + contact + invites | `unified_assignment_creation.create_assignment_with_contact_and_invites` |
| Post-login / post-signup / employee routes auto-link | `assignment_claim_link_service.reconcile_pending_assignment_claims` |
| Resolve company-scoped contact (normalized email / invite key) | `Database.resolve_or_create_employee_contact` (only writer of `employee_contacts` in app code) |
| Dev/demo **auth** rows only (not contacts) | `dev_seed_auth.ensure_dev_seed_auth_user` |

Operational email lives in `employee_contacts`; auth email in `users` only (`users_email_key` on Postgres).
Company isolation is enforced by scoping contacts and case/assignment visibility queries to `company_id`.
"""
from __future__ import annotations

from .assignment_claim_link_service import reconcile_pending_assignment_claims
from .unified_assignment_creation import create_assignment_with_contact_and_invites

__all__ = [
    "create_assignment_with_contact_and_invites",
    "reconcile_pending_assignment_claims",
]
