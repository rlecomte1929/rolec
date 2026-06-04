"""
SEC-CASES-1: auth on the two previously-unauthenticated cases.py mutation
endpoints — PATCH /api/cases/{id} (patch_case) and POST /api/cases/{id}/create
(create_case).

Two layers, deterministic (no DB, no app mount):
  * Dependency wiring: both handlers declare get_current_user as their auth
    dependency → FastAPI rejects a tokenless request with 401 before any handler
    logic runs.
  * Unit (handlers called directly, db layer mocked): an existing case enforces
    access via _assert_case_access (a 403 there short-circuits before any
    mutation); patch_case's create-on-missing path does NOT access-check (so an
    authenticated user can still create a case via the wizard).
"""
from __future__ import annotations

import inspect
import os
import sys
import unittest
from unittest import mock

from fastapi import HTTPException
from fastapi.params import Depends as DependsParam

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.auth_deps import get_current_user  # noqa: E402
from backend.app.routers import cases  # noqa: E402

_OWNER = {"id": "emp-1", "auth_uuid": None, "role": "EMPLOYEE"}


class AuthDependencyWiredTests(unittest.TestCase):
    """Both mutation handlers require get_current_user — so FastAPI returns 401
    for a tokenless request (get_current_user raises 401 on a missing header)."""

    def _assert_requires_auth(self, fn) -> None:
        param = inspect.signature(fn).parameters.get("user")
        self.assertIsNotNone(param, f"{fn.__name__} has no `user` auth param")
        self.assertIsInstance(param.default, DependsParam)
        self.assertIs(param.default.dependency, get_current_user)

    def test_patch_case_requires_auth(self):
        self._assert_requires_auth(cases.patch_case)

    def test_create_case_requires_auth(self):
        self._assert_requires_auth(cases.create_case)


class _Sentinel(Exception):
    pass


class PatchCaseAccessWiringTests(unittest.TestCase):
    def test_existing_case_enforces_access(self):
        # Existing case + non-owner → _assert_case_access raises 403, which must
        # short-circuit before any mutation.
        with mock.patch.object(cases, "SessionLocal"), \
             mock.patch.object(cases.crud, "get_case", return_value=mock.Mock()), \
             mock.patch.object(cases.crud, "update_case", side_effect=_Sentinel) as upd, \
             mock.patch.object(cases, "_assert_case_access",
                               side_effect=HTTPException(status_code=403)) as guard:
            with self.assertRaises(HTTPException) as ctx:
                cases.patch_case(case_id="c1", patch=mock.Mock(**{
                    "model_dump.return_value": {}}), user=_OWNER)
        self.assertEqual(ctx.exception.status_code, 403)
        guard.assert_called_once_with(_OWNER, "c1")
        upd.assert_not_called()  # no mutation past the access check

    def test_missing_case_skips_access_check_and_creates(self):
        # No existing case → create-on-missing path: NOT access-checked, so an
        # authenticated user can create the case (wizard flow). crud.create_case
        # is reached (we sentinel it to stop before the downstream side-effects).
        with mock.patch.object(cases, "SessionLocal"), \
             mock.patch.object(cases.crud, "get_case", return_value=None), \
             mock.patch.object(cases.crud, "create_case", side_effect=_Sentinel) as create, \
             mock.patch.object(cases, "_assert_case_access") as guard:
            with self.assertRaises(_Sentinel):
                cases.patch_case(case_id="new-case", patch=mock.Mock(**{
                    "model_dump.return_value": {}}), user=_OWNER)
        guard.assert_not_called()       # create path is auth-only
        create.assert_called_once()     # reached the create


class CreateCaseAccessWiringTests(unittest.TestCase):
    def test_enforces_access_on_existing_case(self):
        case = mock.Mock(draft_json="{}")
        with mock.patch.object(cases, "SessionLocal"), \
             mock.patch.object(cases.crud, "get_case", return_value=case), \
             mock.patch.object(cases, "_assert_case_access",
                               side_effect=HTTPException(status_code=403)) as guard:
            with self.assertRaises(HTTPException) as ctx:
                cases.create_case(case_id="c1", request=mock.Mock(), user=_OWNER)
        self.assertEqual(ctx.exception.status_code, 403)
        guard.assert_called_once_with(_OWNER, "c1")

    def test_missing_case_404_before_access(self):
        with mock.patch.object(cases, "SessionLocal"), \
             mock.patch.object(cases.crud, "get_case", return_value=None), \
             mock.patch.object(cases, "_assert_case_access") as guard:
            with self.assertRaises(HTTPException) as ctx:
                cases.create_case(case_id="missing", request=mock.Mock(), user=_OWNER)
        self.assertEqual(ctx.exception.status_code, 404)
        guard.assert_not_called()


if __name__ == "__main__":
    unittest.main()
