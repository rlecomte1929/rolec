"""
[BUG-260804-1327] The manual claim form must accept the case code HR actually emails.

Three different values get called "case code":
  1. assignment_claim_invites.token — what assignment_invite_email.py mails the employee,
     verbatim, under "link it manually with this case code";
  2. the dashboard's 8-char Reference (formatCaseReference) — a display label;
  3. case_assignments.id — historically the ONLY thing the claim endpoint understood.

An employee pasting (1) got a bare 404 and could not link their own case.

These call the handler directly rather than over HTTP: the endpoint hangs off `app` in
backend/main.py behind a rate limiter and a role dependency, and the behaviour under test
is which identifier resolves to which assignment — not the transport. Before this change
there was no test of the claim endpoint at all.
"""
from __future__ import annotations

import unittest
from typing import Any, Dict, Optional
from unittest import mock

from fastapi import HTTPException

from backend import main as bmain
from backend.schemas import ClaimAssignmentRequest


ASSIGNMENT_ID = "11111111-2222-3333-4444-555555555555"
INVITE_TOKEN = "99999999-8888-7777-6666-555555555555"
EMPLOYEE = {"id": "user-1", "email": "jane@acme.com", "username": "jane"}


class _Req:
    """Minimal stand-in for the FastAPI Request the handler reads request_id off."""

    class _State:
        request_id = "req-test"

    state = _State()


class _FakeDb:
    """Only the handful of db calls this endpoint makes."""

    def __init__(self, *, invite: Optional[Dict[str, Any]] = None):
        self._invite = invite
        self.attached_to: Optional[str] = None

    def get_assignment_by_id(self, assignment_id: str, *a: Any, **k: Any):
        if assignment_id == ASSIGNMENT_ID:
            return {"id": ASSIGNMENT_ID, "employee_user_id": None, "employee_email": EMPLOYEE["email"]}
        return None

    def get_claim_invite_by_token(self, token: str):
        if self._invite and token == INVITE_TOKEN:
            return self._invite
        return None

    def assignment_identity_matches_user_identifiers(self, *a: Any, **k: Any) -> bool:
        return True

    def is_assignment_auto_claim_blocked_by_revoked_invites(self, *a: Any, **k: Any) -> bool:
        return False


def _call_with(db: _FakeDb, code: str):
    with mock.patch.object(bmain, "db", db), \
         mock.patch.object(bmain, "identity_event", lambda *a, **k: None), \
         mock.patch.object(bmain, "_deny_if_impersonating", lambda *a, **k: None), \
         mock.patch.object(bmain, "_effective_user", lambda *a, **k: dict(EMPLOYEE)), \
         mock.patch.object(bmain, "finalize_assignment_claim_attach") as finalize:
        result = bmain.claim_assignment(
            _Req(),  # type: ignore[arg-type]
            code,
            ClaimAssignmentRequest(email=EMPLOYEE["email"]),
            user=dict(EMPLOYEE),
        )
        return result, finalize


class ClaimAcceptsTheEmailedCodeTests(unittest.TestCase):
    def test_the_raw_assignment_id_still_works(self) -> None:
        """The pre-existing path must not regress."""
        db = _FakeDb()
        result, finalize = _call_with(db, ASSIGNMENT_ID)
        self.assertTrue(result["success"])
        self.assertEqual(result["assignmentId"], ASSIGNMENT_ID)
        self.assertEqual(finalize.call_args.kwargs["assignment_id"], ASSIGNMENT_ID)

    def test_the_emailed_invite_token_is_accepted(self) -> None:
        """The bug: this used to 404. It is the code HR's email tells them to use."""
        db = _FakeDb(invite={"assignment_id": ASSIGNMENT_ID, "status": "pending"})
        result, finalize = _call_with(db, INVITE_TOKEN)
        self.assertTrue(result["success"])
        # Resolved to the real assignment, not echoed back as the token.
        self.assertEqual(result["assignmentId"], ASSIGNMENT_ID)
        self.assertEqual(finalize.call_args.kwargs["assignment_id"], ASSIGNMENT_ID)

    def test_the_token_path_is_recorded_so_we_can_see_which_code_people_use(self) -> None:
        db = _FakeDb(invite={"assignment_id": ASSIGNMENT_ID, "status": "pending"})
        _, finalize = _call_with(db, INVITE_TOKEN)
        self.assertEqual(
            finalize.call_args.kwargs["case_event_payload"], {"code_form": "invite_token"}
        )

    def test_the_id_path_is_recorded_distinctly(self) -> None:
        db = _FakeDb()
        _, finalize = _call_with(db, ASSIGNMENT_ID)
        self.assertEqual(
            finalize.call_args.kwargs["case_event_payload"], {"code_form": "assignment_id"}
        )

    def test_an_unknown_code_still_404s(self) -> None:
        db = _FakeDb()
        with self.assertRaises(HTTPException) as ctx:
            _call_with(db, "not-a-real-code")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_the_404_explains_which_code_to_use(self) -> None:
        """A bare 'Assignment not found' is what left the reporter stuck."""
        db = _FakeDb()
        with self.assertRaises(HTTPException) as ctx:
            _call_with(db, "not-a-real-code")
        detail = str(ctx.exception.detail).lower()
        self.assertIn("invitation email", detail)
        self.assertIn("dashboard", detail)

    def test_an_invite_pointing_at_a_missing_assignment_404s_rather_than_crashing(self) -> None:
        db = _FakeDb(invite={"assignment_id": "gone", "status": "pending"})
        with self.assertRaises(HTTPException) as ctx:
            _call_with(db, INVITE_TOKEN)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_the_short_dashboard_reference_is_NOT_accepted(self) -> None:
        """Deliberate. case_assignments.id is TEXT with non-uuid rows in production, the
        Reference is derived from case_id (a different id space), and a trailing-wildcard
        match would be unindexable and collision-prone on a brute-forceable endpoint."""
        db = _FakeDb(invite={"assignment_id": ASSIGNMENT_ID, "status": "pending"})
        short_ref = ASSIGNMENT_ID[-8:].upper()
        with self.assertRaises(HTTPException) as ctx:
            _call_with(db, short_ref)
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
