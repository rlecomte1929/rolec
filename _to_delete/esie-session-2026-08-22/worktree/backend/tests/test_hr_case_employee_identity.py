"""AIQ-1803 — HR case surfaces must name the employee, not the case id.

`relocation_cases.employee_id` is null for all but 4 of the 1,091 rows in production, so
both the HR case list and the case detail rendered an anonymous placeholder —
"Case 08b7280b" — where the person's name belongs. The identity IS reachable, through
`case_assignments`, which is what every endpoint that already shows a real name uses.

Two properties matter and they pull against each other:

  * a case whose identity CAN be determined must show it (706 of 1,091), and
  * a case whose identity CANNOT be determined must keep its placeholder rather than
    gain an invented one (385 of 1,091).

The second is the easy one to get wrong: a resolver that returns "Employee" for everyone
would make the first test pass and the product worse.
"""
from __future__ import annotations

import sys
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock, patch

_qc = MagicMock()
_qc.install_query_counter = lambda *a, **kw: None
sys.modules.setdefault("backend.app.services.query_counter", _qc)

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app, UserRole  # noqa: E402
from backend.app.auth_deps import get_current_user, get_org_id_for_hr_user  # noqa: E402
from backend.db.cases import _employee_display_name  # noqa: E402

CASE_ID = "08b7280b-491d-4d50-ae8b-325cb29aa3f1"
_HR = {"id": "user-hr-a", "role": UserRole.HR.value, "email": "hr@co.test", "is_admin": False}
_CASE: Dict[str, Any] = {
    "id": CASE_ID, "company_id": "company-a",
    "employee_id": None, "origin_country_code": None, "dest_country_code": None,
    "corridor": None, "status": "created", "stage": "intake",
    "target_start_date": None, "actual_start_date": None, "target_close_date": None,
}


class TestTheNameLadder(unittest.TestCase):
    """Lifted from list_hr_conversation_summaries so the HR inbox and the HR case
    surface can never disagree about what a person is called."""

    def test_precedence_order(self) -> None:
        self.assertEqual(
            _employee_display_name({"employee_full_name": "Anna Eriksson",
                                    "employee_first_name": "Ignored",
                                    "employee_identifier": "ignored@x.test"}),
            "Anna Eriksson")
        self.assertEqual(
            _employee_display_name({"employee_first_name": "Anna",
                                    "employee_last_name": "Eriksson",
                                    "employee_identifier": "ignored@x.test"}),
            "Anna Eriksson")
        self.assertEqual(
            _employee_display_name({"employee_identifier": "anna@x.test"}),
            "anna@x.test")

    def test_returns_none_rather_than_a_generic_stand_in(self) -> None:
        """The caller already has a placeholder. Two layers each substituting a
        different stand-in is how "Employee" and "Case 08b7280b" came to mean the same
        thing in two places."""
        self.assertIsNone(_employee_display_name({}))
        self.assertIsNone(_employee_display_name(
            {"employee_full_name": "  ", "employee_first_name": "", "employee_identifier": None}))

    def test_a_half_populated_name_still_resolves(self) -> None:
        self.assertEqual(_employee_display_name({"employee_first_name": "Anna"}), "Anna")


class _RouterBase(unittest.TestCase):
    def setUp(self) -> None:
        async def _user(request=None, authorization=None):
            return _HR

        async def _org():
            return "company-a"

        app.dependency_overrides[get_current_user] = _user
        app.dependency_overrides[get_org_id_for_hr_user] = _org
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def _overview(self, resolved: Dict[str, Any], case=None):
        class _FailingEngine:
            def connect(self):
                raise RuntimeError("rce.* not needed for this assertion")

        with (
            patch("backend.app.routers.hr_case_detail.db.get_relocation_case",
                  side_effect=lambda cid: (case if case is not None else _CASE)
                  if cid == CASE_ID else None),
            patch("backend.app.routers.hr_case_detail.db.resolve_case_identities",
                  return_value=resolved) as spy,
            patch("backend.app.routers.hr_case_detail.db.engine", new=_FailingEngine()),
        ):
            resp = self.client.get(f"/api/hr/cases/{CASE_ID}/overview",
                                   headers={"Authorization": "Bearer t"})
        return resp, spy


class TestOverviewNamesTheEmployee(_RouterBase):
    def test_a_resolvable_case_shows_the_person(self) -> None:
        resp, _ = self._overview({CASE_ID: {
            "employee_user_id": "emp-1",
            "employee_display_name": "Anna Eriksson",
            "employee_email": "anna@x.test",
            "origin_country_code": "FR", "dest_country_code": "NO",
        }})
        self.assertEqual(resp.status_code, 200)
        emp = resp.json()["overview"]["employee"]
        self.assertEqual(emp["display_name"], "Anna Eriksson")
        self.assertEqual(emp["primary_email"], "anna@x.test")
        self.assertNotIn("Case 08b7280b", resp.text)

    def test_the_corridor_is_derived_from_the_resolved_countries(self) -> None:
        resp, _ = self._overview({CASE_ID: {
            "employee_display_name": "Anna Eriksson",
            "origin_country_code": "FR", "dest_country_code": "NO",
        }})
        body = resp.json()["overview"]
        self.assertEqual(body["origin_country_code"], "FR")
        self.assertEqual(body["dest_country_code"], "NO")
        self.assertEqual(body["corridor"], "FR-NO")

    def test_an_unresolvable_case_keeps_its_placeholder(self) -> None:
        """385 of 1,091 cases are reachable by neither table. A fabricated name would be
        worse than the honest placeholder they have now."""
        resp, _ = self._overview({})
        emp = resp.json()["overview"]["employee"]
        self.assertEqual(emp["display_name"], "Case 08b7280b")
        self.assertIsNone(emp["primary_email"])
        self.assertIsNone(resp.json()["overview"]["corridor"])

    def test_a_legacy_row_that_already_has_data_is_not_overwritten(self) -> None:
        """Fill only what is MISSING — this must not be able to change a case that was
        already correct."""
        good = {**_CASE, "origin_country_code": "DE", "dest_country_code": "FR",
                "corridor": "DE-FR"}
        resp, _ = self._overview(
            {CASE_ID: {"origin_country_code": "XX", "dest_country_code": "YY"}}, case=good)
        body = resp.json()["overview"]
        self.assertEqual(body["origin_country_code"], "DE")
        self.assertEqual(body["dest_country_code"], "FR")
        self.assertEqual(body["corridor"], "DE-FR")

    def test_a_resolver_failure_degrades_to_the_placeholder(self) -> None:
        class _FailingEngine:
            def connect(self):
                raise RuntimeError("no rce")

        with (
            patch("backend.app.routers.hr_case_detail.db.get_relocation_case",
                  side_effect=lambda cid: _CASE if cid == CASE_ID else None),
            patch("backend.app.routers.hr_case_detail.db.resolve_case_identities",
                  side_effect=RuntimeError("boom")),
            patch("backend.app.routers.hr_case_detail.db.engine", new=_FailingEngine()),
        ):
            resp = self.client.get(f"/api/hr/cases/{CASE_ID}/overview",
                                   headers={"Authorization": "Bearer t"})
        self.assertEqual(resp.status_code, 200, "identity resolution must never 500 the page")
        self.assertEqual(resp.json()["overview"]["employee"]["display_name"], "Case 08b7280b")

    def test_the_resolver_is_skipped_when_the_legacy_row_is_already_complete(self) -> None:
        """No point querying for what we already have."""
        complete = {**_CASE, "employee_id": "emp-legacy",
                    "origin_country_code": "DE", "dest_country_code": "FR"}
        with (
            patch("backend.app.routers.hr_case_detail.db.get_relocation_case",
                  side_effect=lambda cid: complete if cid == CASE_ID else None),
            patch("backend.app.routers.hr_case_detail.db.get_user_by_id",
                  return_value={"name": "Legacy Person", "email": "legacy@x.test"}),
            patch("backend.app.routers.hr_case_detail.db.resolve_case_identities") as spy,
            patch("backend.app.routers.hr_case_detail.db.engine",
                  new=type("E", (), {"connect": lambda s: (_ for _ in ()).throw(RuntimeError())})()),
        ):
            resp = self.client.get(f"/api/hr/cases/{CASE_ID}/overview",
                                   headers={"Authorization": "Bearer t"})
        self.assertEqual(resp.json()["overview"]["employee"]["display_name"], "Legacy Person")
        spy.assert_not_called()


class TestTheListResolvesInOneQuery(unittest.TestCase):
    """The HR list renders 34+ cases. A per-row lookup would be an N+1 on the page HR
    opens first."""

    def _enrich(self, items, resolved):
        from backend import main as backend_main
        with patch.object(backend_main.db, "resolve_case_identities",
                          return_value=resolved) as spy:
            out = backend_main._enrich_case_identities(items)
        return out, spy

    def test_one_call_for_many_cases(self) -> None:
        items = [{"id": f"case-{i}", "employee_id": None} for i in range(25)]
        resolved = {f"case-{i}": {"employee_user_id": f"emp-{i}",
                                  "employee_display_name": f"Person {i}"} for i in range(25)}
        out, spy = self._enrich(items, resolved)
        self.assertEqual(spy.call_count, 1, "expected ONE batched query, not one per case")
        self.assertEqual(len(spy.call_args[0][0]), 25, "all ids must go in a single batch")
        self.assertEqual(out[3]["employee_name"], "Person 3")
        self.assertEqual(out[3]["employee_id"], "emp-3")

    def test_unresolved_rows_are_left_exactly_as_they_were(self) -> None:
        items = [{"id": "case-known", "employee_id": None},
                 {"id": "case-unknown", "employee_id": None}]
        out, _ = self._enrich(items, {"case-known": {"employee_display_name": "Anna"}})
        self.assertEqual(out[0]["employee_name"], "Anna")
        self.assertNotIn("employee_name", out[1],
                         "an unresolvable case must not gain an invented name")

    def test_an_existing_value_is_not_overwritten(self) -> None:
        items = [{"id": "c1", "employee_id": "already-set", "origin_country_code": "DE"}]
        out, _ = self._enrich(items, {"c1": {"employee_user_id": "other",
                                             "origin_country_code": "XX"}})
        self.assertEqual(out[0]["employee_id"], "already-set")
        self.assertEqual(out[0]["origin_country_code"], "DE")

    def test_a_resolver_failure_returns_the_rows_unenriched(self) -> None:
        from backend import main as backend_main
        items = [{"id": "c1", "employee_id": None}]
        with patch.object(backend_main.db, "resolve_case_identities",
                          side_effect=RuntimeError("boom")):
            out = backend_main._enrich_case_identities(items)
        self.assertEqual(out, items, "the list must still render")

    def test_an_empty_page_does_not_query_at_all(self) -> None:
        out, spy = self._enrich([], {})
        self.assertEqual(out, [])
        spy.assert_not_called()


class CreateCaseMustNotClaimAnEmployeeTests(unittest.TestCase):
    """[AIQ-1818] The obvious "fix" for the null column is a data-protection defect.

    `POST /api/hr/cases` builds `RelocationProfile(userId=<the HR user>)`, so
    `profile_json->>'userId'` is the *creator*, not the subject — measured equal to
    `hr_user_id` in 466 of 466 unclaimed prod rows. `app/routers/gdpr.py` resolves a
    subject-access request with `relocation_cases.employee_id::text = :uid`, so writing
    the creator's id into that column would return every case they ever opened, about
    other people, to whoever asked for *their own* data.

    This test fails if someone adds employee_id to the INSERT.
    """

    def _captured_insert(self, profile: Dict[str, Any], company_id: Any):
        from backend.db.cases import CasesMixin

        conn = MagicMock()
        engine = MagicMock()
        engine.begin.return_value.__enter__.return_value = conn

        holder = type("_H", (CasesMixin,), {})()
        holder.engine = engine
        holder.create_case("case-1", "hr-user-1", profile, company_id=company_id)

        conn.execute.assert_called_once()
        stmt, params = conn.execute.call_args[0]
        return str(stmt), params

    def test_the_insert_does_not_write_employee_id(self) -> None:
        profile = {"userId": "hr-user-1", "primaryApplicant": {}}
        for company_id in ("company-a", None):
            with self.subTest(company_id=company_id):
                sql, params = self._captured_insert(profile, company_id)
                self.assertNotIn("employee_id", sql,
                                 "an unclaimed shell must not name a subject it does not have")
                self.assertNotIn("hr-user-1", [v for k, v in params.items() if k != "hr"],
                                 "the HR creator's id must not leak into any other column")

    def test_the_creator_is_still_recorded_as_hr_user(self) -> None:
        """The guard above must not be satisfiable by writing nothing at all."""
        sql, params = self._captured_insert({"userId": "hr-user-1"}, "company-a")
        self.assertIn("hr_user_id", sql)
        self.assertEqual(params["hr"], "hr-user-1")
        self.assertEqual(params["cid"], "company-a")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
