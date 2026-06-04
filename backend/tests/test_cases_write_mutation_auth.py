"""
SEC-CASES-2: auth on the LIVE cases_write.py mutation endpoints.

SEC-CASES-1 (#307) hardened backend/app/routers/cases.py — but that router is
unwired dead code (AUDIT-B9-cases-6). The live /api/cases mutations are served
by cases_write.py, whose patch_case / create_case / start_research were still
unauthenticated. This pins the real fix.

Deterministic (no DB, no app mount): dependency-wiring (→ 401 tokenless) +
handler-level access wiring (existing case → _assert_case_access short-circuits
before any mutation; patch_case create-on-missing stays open to authed users;
create_case/start_research 404 before the access check when missing).
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
from backend.app.routers import cases_write  # noqa: E402

_OWNER = {"id": "emp-1", "auth_uuid": None, "role": "EMPLOYEE"}


class _Sentinel(Exception):
    pass


class AuthDependencyWiredTests(unittest.TestCase):
    def _assert_requires_auth(self, fn) -> None:
        param = inspect.signature(fn).parameters.get("user")
        self.assertIsNotNone(param, f"{fn.__name__} has no `user` auth param")
        self.assertIsInstance(param.default, DependsParam)
        self.assertIs(param.default.dependency, get_current_user)

    def test_patch_case_requires_auth(self):
        self._assert_requires_auth(cases_write.patch_case)

    def test_create_case_requires_auth(self):
        self._assert_requires_auth(cases_write.create_case)

    def test_start_research_requires_auth(self):
        self._assert_requires_auth(cases_write.start_research)


class PatchCaseAccessWiringTests(unittest.TestCase):
    def test_existing_case_enforces_access(self):
        with mock.patch.object(cases_write, "SessionLocal"), \
             mock.patch.object(cases_write.crud, "get_case", return_value=mock.Mock()), \
             mock.patch.object(cases_write.crud, "update_case", side_effect=_Sentinel) as upd, \
             mock.patch.object(cases_write, "_assert_case_access",
                               side_effect=HTTPException(status_code=403)) as guard:
            with self.assertRaises(HTTPException) as ctx:
                cases_write.patch_case(case_id="c1", patch=mock.Mock(**{
                    "model_dump.return_value": {}}), user=_OWNER)
        self.assertEqual(ctx.exception.status_code, 403)
        guard.assert_called_once_with(_OWNER, "c1")
        upd.assert_not_called()

    def test_missing_case_skips_access_check_and_creates(self):
        with mock.patch.object(cases_write, "SessionLocal"), \
             mock.patch.object(cases_write.crud, "get_case", return_value=None), \
             mock.patch.object(cases_write.crud, "create_case", side_effect=_Sentinel) as create, \
             mock.patch.object(cases_write, "_assert_case_access") as guard:
            with self.assertRaises(_Sentinel):
                cases_write.patch_case(case_id="new", patch=mock.Mock(**{
                    "model_dump.return_value": {}}), user=_OWNER)
        guard.assert_not_called()
        create.assert_called_once()


class CreateAndResearchAccessWiringTests(unittest.TestCase):
    def test_create_case_enforces_access_on_existing(self):
        with mock.patch.object(cases_write, "SessionLocal"), \
             mock.patch.object(cases_write.crud, "get_case", return_value=mock.Mock(draft_json="{}")), \
             mock.patch.object(cases_write, "_assert_case_access",
                               side_effect=HTTPException(status_code=403)) as guard:
            with self.assertRaises(HTTPException) as ctx:
                cases_write.create_case(case_id="c1", request=mock.Mock(), user=_OWNER)
        self.assertEqual(ctx.exception.status_code, 403)
        guard.assert_called_once_with(_OWNER, "c1")

    def test_create_case_404_before_access_when_missing(self):
        with mock.patch.object(cases_write, "SessionLocal"), \
             mock.patch.object(cases_write.crud, "get_case", return_value=None), \
             mock.patch.object(cases_write, "_assert_case_access") as guard:
            with self.assertRaises(HTTPException) as ctx:
                cases_write.create_case(case_id="missing", request=mock.Mock(), user=_OWNER)
        self.assertEqual(ctx.exception.status_code, 404)
        guard.assert_not_called()

    def test_start_research_enforces_access_on_existing(self):
        with mock.patch.object(cases_write, "SessionLocal"), \
             mock.patch.object(cases_write.crud, "get_case", return_value=mock.Mock(draft_json="{}")), \
             mock.patch.object(cases_write, "_assert_case_access",
                               side_effect=HTTPException(status_code=403)) as guard:
            with self.assertRaises(HTTPException) as ctx:
                cases_write.start_research(case_id="c1", user=_OWNER)
        self.assertEqual(ctx.exception.status_code, 403)
        guard.assert_called_once_with(_OWNER, "c1")

    def test_start_research_404_before_access_when_missing(self):
        with mock.patch.object(cases_write, "SessionLocal"), \
             mock.patch.object(cases_write.crud, "get_case", return_value=None), \
             mock.patch.object(cases_write, "_assert_case_access") as guard:
            with self.assertRaises(HTTPException) as ctx:
                cases_write.start_research(case_id="missing", user=_OWNER)
        self.assertEqual(ctx.exception.status_code, 404)
        guard.assert_not_called()


if __name__ == "__main__":
    unittest.main()
