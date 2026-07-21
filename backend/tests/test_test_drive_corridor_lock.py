"""TD-FIX-7 (AIQ-1510) — the assigned corridor is enforced, not merely communicated.

Three layers:
  1. resolve_test_drive_route — the acting-user → corridor resolver. Must resolve for
     BOTH the HR and the employee account of a session, across ALL five locked
     corridors, and must return None for every real user.
  2. patch_case override — the real tamper surface. The employee intake submits
     origin/destination here, so a tampered payload must still land on the assigned
     corridor. Also covers the create-on-missing path (which skips the access check).
  3. assign_case stamp — a test-drive case is pinned to its corridor at assign time;
     a real HR user's case is never touched.

Deliberately parametrised across corridors (not just FR_NO): a FR_NO-only regression —
e.g. hardcoding the default corridor — must fail here.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import cases_write  # noqa: E402
from backend.app.services import test_drive_corridor as tdc  # noqa: E402

_HR_USER = {"id": "hr-1", "email": "hr-alex-1a2b@probe.test", "role": "HR"}
_EMP_USER = {"id": "emp-1", "email": "emp-alex-1a2b@probe.test", "role": "EMPLOYEE"}
_REAL_HR = {"id": "hr-9", "email": "hr@acme.com", "role": "HR"}


def _db_returning_corridor(corridor_id):
    """MagicMock db whose test_sessions SELECT yields `corridor_id` (None → no row)."""
    db = mock.MagicMock()
    conn = db.engine.connect.return_value.__enter__.return_value
    row = {"corridor_id": corridor_id} if corridor_id is not None else None
    conn.execute.return_value.mappings.return_value.first.return_value = row
    return db


class ResolveTestDriveRouteTests(unittest.TestCase):
    def test_resolves_every_locked_corridor(self):
        # All five corridors must resolve to their own route — no FR_NO fallback.
        expected = {
            "FR_NO": ("FR", "Paris", "NO", "Oslo"),
            "IN_DE": ("IN", "Mumbai", "DE", "Munich"),
            "GB_US": ("GB", "London", "US", "New York"),
            "NL_SG": ("NL", "Amsterdam", "SG", "Singapore"),
            "ES_AE": ("ES", "Madrid", "AE", "Dubai"),
        }
        self.assertEqual(set(expected), set(tdc.LOCKED_CORRIDORS))
        for corridor_id, (home_c, home_city, host_c, host_city) in expected.items():
            with self.subTest(corridor=corridor_id):
                with mock.patch.object(tdc, "db", _db_returning_corridor(corridor_id)):
                    route = tdc.resolve_test_drive_route(_HR_USER)
                self.assertEqual(route, {
                    "home_country": home_c, "home_city": home_city,
                    "host_country": host_c, "host_city": host_city,
                })

    def test_resolves_for_the_employee_account_too(self):
        # The EMPLOYEE account is the one that submits the intake carrying the route.
        with mock.patch.object(tdc, "db", _db_returning_corridor("NL_SG")):
            route = tdc.resolve_test_drive_route(_EMP_USER)
        self.assertEqual(route["host_city"], "Singapore")

    def test_real_user_is_unaffected(self):
        # A non-@probe.test user never even reaches the DB — no lock, route stays free.
        db = _db_returning_corridor("FR_NO")
        with mock.patch.object(tdc, "db", db):
            self.assertIsNone(tdc.resolve_test_drive_route(_REAL_HR))
        db.engine.connect.assert_not_called()

    def test_probe_email_with_no_session_is_none(self):
        with mock.patch.object(tdc, "db", _db_returning_corridor(None)):
            self.assertIsNone(tdc.resolve_test_drive_route(_HR_USER))

    def test_unknown_corridor_id_is_none(self):
        # A corridor outside the five locked ones never yields a route.
        with mock.patch.object(tdc, "db", _db_returning_corridor("BR_JP")):
            self.assertIsNone(tdc.resolve_test_drive_route(_HR_USER))

    def test_lookup_failure_degrades_to_none(self):
        db = mock.MagicMock()
        db.engine.connect.side_effect = RuntimeError("db down")
        with mock.patch.object(tdc, "db", db):
            self.assertIsNone(tdc.resolve_test_drive_route(_HR_USER))

    def test_missing_or_empty_user(self):
        self.assertIsNone(tdc.resolve_test_drive_route(None))
        self.assertIsNone(tdc.resolve_test_drive_route({}))


class _Stop(Exception):
    """Halt patch_case right after the override, before downstream side-effects."""


def _tampered_patch():
    """An intake submit pointing at a corridor the tester was NOT assigned."""
    return mock.Mock(**{"model_dump.return_value": {
        "relocationBasics": {
            "originCountry": "BR", "originCity": "Rio de Janeiro",
            "destCountry": "JP", "destCity": "Tokyo",
            "purpose": "work", "targetMoveDate": "2026-09-01",
        },
    }})


class PatchCaseCorridorOverrideTests(unittest.TestCase):
    """The server-side guard: whatever the client sends, the route is the assigned one."""

    def _run_patch_case(self, user, route, *, existing_case):
        get_case = mock.Mock(return_value=mock.Mock(draft_json="{}") if existing_case else None)
        sink = mock.Mock(side_effect=_Stop)
        with mock.patch.object(cases_write, "SessionLocal"), \
             mock.patch.object(cases_write, "resolve_test_drive_route", return_value=route), \
             mock.patch.object(cases_write, "_assert_case_access"), \
             mock.patch.object(cases_write.crud, "get_case", get_case), \
             mock.patch.object(cases_write.crud, "create_case", sink), \
             mock.patch.object(cases_write.crud, "update_case", sink):
            with self.assertRaises(_Stop):
                cases_write.patch_case(
                    case_id="c1",
                    patch=_tampered_patch(),
                    background_tasks=mock.Mock(),
                    user=user,
                )
        return sink

    def test_tampered_corridor_is_overridden_on_existing_case(self):
        route = tdc.TEST_DRIVE_CORRIDOR_ROUTES["IN_DE"]
        sink = self._run_patch_case(_EMP_USER, route, existing_case=True)
        basics = sink.call_args.args[2]["relocationBasics"]
        self.assertEqual(basics["originCountry"], "IN")
        self.assertEqual(basics["originCity"], "Mumbai")
        self.assertEqual(basics["destCountry"], "DE")
        self.assertEqual(basics["destCity"], "Munich")
        # Non-route fields the tester supplied are preserved.
        self.assertEqual(basics["purpose"], "work")

    def test_tampered_corridor_is_overridden_on_create_on_missing(self):
        # This path skips _assert_case_access, so it must not be a way around the lock.
        route = tdc.TEST_DRIVE_CORRIDOR_ROUTES["ES_AE"]
        sink = self._run_patch_case(_EMP_USER, route, existing_case=False)
        basics = sink.call_args.args[2]["relocationBasics"]
        self.assertEqual((basics["originCountry"], basics["destCountry"]), ("ES", "AE"))
        self.assertEqual(basics["destCity"], "Dubai")

    def test_real_user_route_is_untouched(self):
        # resolve returns None → the submitted route is persisted verbatim.
        sink = self._run_patch_case(_REAL_HR, None, existing_case=True)
        basics = sink.call_args.args[2]["relocationBasics"]
        self.assertEqual(basics["originCountry"], "BR")
        self.assertEqual(basics["destCountry"], "JP")
        self.assertEqual(basics["destCity"], "Tokyo")


class AssignCaseStampTests(unittest.TestCase):
    """assign_case pins a test-drive case to its corridor; a real case is never stamped."""

    def _assign(self, user, route):
        from backend import main

        db = mock.MagicMock()
        db.get_case_by_id.return_value = {"id": "c1", "company_id": "co-1", "employee_id": None}
        # [AIQ-1651] the stamp also writes the wizard_cases row via app_crud through a real
        # SessionLocal; mock both so we can assert the destination write without a live DB.
        crud = mock.MagicMock()
        crud.get_case.return_value = mock.Mock(
            draft_json="{}", purpose=None, target_move_date=None, flags_json="{}")
        with mock.patch.object(main, "db", db), \
             mock.patch.object(main, "_deny_if_impersonating"), \
             mock.patch.object(main, "_effective_user", return_value=user), \
             mock.patch.object(main, "_get_hr_company_id", return_value="co-1"), \
             mock.patch.object(main, "SessionLocal"), \
             mock.patch.object(main, "app_crud", crud), \
             mock.patch.object(main, "create_assignment_with_contact_and_invites",
                               side_effect=_Stop), \
             mock.patch(
                 "backend.app.services.test_drive_corridor.resolve_test_drive_route",
                 return_value=route,
             ):
            req = mock.Mock(employeeIdentifier="emp@x.com", employeeLevel=None,
                            employeeFirstName=None, employeeLastName=None)
            try:
                main.assign_case(case_id="c1", request=req,
                                 request_obj=mock.Mock(), user=user)
            except Exception:
                pass  # _Stop (or the HTTPException it is wrapped in) — we only assert the stamp
        return db, crud

    def test_test_drive_case_is_stamped_with_its_own_corridor(self):
        # Parametrised: a FR_NO-only implementation must fail here.
        for corridor_id in ("FR_NO", "IN_DE", "GB_US"):
            with self.subTest(corridor=corridor_id):
                route = tdc.TEST_DRIVE_CORRIDOR_ROUTES[corridor_id]
                db, _ = self._assign(_HR_USER, route)
                db.set_relocation_case_route.assert_called_once_with("c1", **route)

    def test_test_drive_case_stamps_wizard_cases_destination(self):
        # [AIQ-1651] The recs engine reads wizard_cases; the stamp must set dest there too, so
        # city-scoped housing/schools recs populate without the tester completing intake.
        for corridor_id, (host_c, host_city) in (
            ("FR_NO", ("NO", "Oslo")), ("ES_AE", ("AE", "Dubai"))
        ):
            with self.subTest(corridor=corridor_id):
                route = tdc.TEST_DRIVE_CORRIDOR_ROUTES[corridor_id]
                _db, crud = self._assign(_HR_USER, route)
                crud.update_case.assert_called_once()
                # signature: update_case(session, case, draft, derived, flags)
                derived = crud.update_case.call_args.args[3]
                self.assertEqual(derived["dest_country"], host_c)
                self.assertEqual(derived["dest_city"], host_city)
                draft = crud.update_case.call_args.args[2]
                self.assertEqual(draft["relocationBasics"]["destCity"], host_city)

    def test_real_hr_case_is_never_stamped(self):
        db, crud = self._assign(_REAL_HR, None)
        db.set_relocation_case_route.assert_not_called()
        crud.update_case.assert_not_called()  # no wizard_cases stamp for a real HR case


if __name__ == "__main__":
    unittest.main()
