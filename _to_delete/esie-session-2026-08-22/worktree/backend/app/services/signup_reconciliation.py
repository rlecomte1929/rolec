"""
Compatibility shim: tests and older imports use `reconcile_employee_signup_after_register`.

Canonical implementation: `assignment_claim_link_service.reconcile_pending_assignment_claims`
(used directly from auth handlers when structured logging needs the `ClaimLinkResult`).
"""

from .assignment_claim_link_service import reconcile_employee_signup_after_register

__all__ = ["reconcile_employee_signup_after_register"]
