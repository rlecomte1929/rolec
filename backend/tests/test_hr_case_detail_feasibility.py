"""AIQ-1749 — the feasibility block on GET /api/hr/cases/{id}/overview.

Mounts the PROD app (backend.main), so this also proves the route is served by the
instance Render actually boots — not just by the modular app/ sub-app.

Auth overrides are keyed on backend.app.auth_deps.get_current_user, NOT the
same-named function in backend.main. Overriding the wrong one leaves the real auth
path running and makes tenant-scoped tests pass for the wrong reasons (AIQ-567).
"""
from __future__ import annotations

import unittest
from typing import Any, Dict, Optional
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app, UserRole
from backend.app.auth_deps import get_current_user, get_org_id_for_hr_user

_HR: Dict[str, Any] = {
    "id": "user-hr-a",
    "role": UserRole.HR.value,
    "email": "hr-a@company-a.test",
    "is_admin": False,
}


def _case(**overrides: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "id": "case-a",
        "company_id": "company-a",
        "hr_user_id": "user-hr-a",
        "employee_id": "emp-a",
        "origin_country_code": "ES",
        "dest_country_code": "IE",
        "corridor": "ES_IE",
        "status": "in_progress",
        "stage": "documents",
        "target_start_date": None,
        "actual_start_date": None,
        "target_close_date": None,
        "nationality": None,
    }
    base.update(overrides)
    return base


def _make_dependency_override(fake_user: Dict[str, Any]):
    async def _override(request=None, authorization=None) -> Dict[str, Any]:  # type: ignore[override]
        return fake_user
    return _override


def _make_failing_engine() -> Any:
    class _FailingEngine:
        def connect(self):
            raise RuntimeError("simulated DB unavailable")
    return _FailingEngine()


class _Base(unittest.TestCase):
    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def _overview(self, case: Optional[Dict[str, Any]]) -> Any:
        app.dependency_overrides[get_current_user] = _make_dependency_override(_HR)
        # Override the org resolver directly rather than patching the db calls behind
        # it: get_org_id_for_hr_user resolves via db.get_hr_company_id FIRST (AIQ-862),
        # falling back to user["company"], so patching get_profile_record alone leaves
        # org_id="" and every request 404s on a tenant mismatch that isn't real.
        app.dependency_overrides[get_org_id_for_hr_user] = lambda: "company-a"
        client = TestClient(app, raise_server_exceptions=False)
        patches = [
            patch(
                "backend.app.routers.hr_case_detail.db.get_relocation_case",
                side_effect=lambda cid: case if (case and cid == case["id"]) else None,
            ),
            patch(
                "backend.app.routers.hr_case_detail.db.get_user_by_id",
                side_effect=lambda uid: {"id": uid, "name": "E", "email": "e@x.test"},
            ),
            patch(
                "backend.app.routers.hr_case_detail.db.engine",
                new=_make_failing_engine(),
            ),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return client.get(
            "/api/hr/cases/case-a/overview",
            headers={"Authorization": "Bearer hr-a-token"},
        )


class FeasibilityOnOverviewTests(_Base):
    def test_es_ie_short_notice_returns_critical(self) -> None:
        # ES_IE needs 104 days of pre-arrival runway; 30 days out cannot work.
        from datetime import date, timedelta
        start = (date.today() + timedelta(days=30)).isoformat()

        resp = self._overview(_case(target_start_date=start))
        self.assertEqual(resp.status_code, 200)
        feas = resp.json()["overview"]["feasibility"]
        self.assertIsNotNone(feas, "ES_IE at 30 days out should carry an assessment")
        self.assertEqual(feas["verdict"], "critical")
        self.assertEqual(feas["required_days"], 104)
        self.assertEqual(feas["available_days"], 30)
        self.assertIn("104", feas["derivation"])

    def test_es_ie_comfortable_horizon_is_ok(self) -> None:
        from datetime import date, timedelta
        start = (date.today() + timedelta(days=300)).isoformat()

        resp = self._overview(_case(target_start_date=start))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["overview"]["feasibility"]["verdict"], "ok")

    def test_free_movement_case_never_warns(self) -> None:
        from datetime import date, timedelta
        start = (date.today() + timedelta(days=7)).isoformat()

        resp = self._overview(
            _case(origin_country_code="FR", dest_country_code="NO",
                  corridor="FR_NO", target_start_date=start)
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["overview"]["feasibility"]["verdict"], "ok")

    def test_no_target_start_date_yields_null_not_500(self) -> None:
        resp = self._overview(_case(target_start_date=None))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()["overview"]["feasibility"])

    def test_unknown_corridor_yields_null_not_500(self) -> None:
        from datetime import date, timedelta
        start = (date.today() + timedelta(days=10)).isoformat()

        resp = self._overview(
            _case(origin_country_code="ZZ", dest_country_code="QQ",
                  corridor="ZZ_QQ", target_start_date=start)
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()["overview"]["feasibility"])

    def test_missing_geo_yields_null_not_500(self) -> None:
        from datetime import date, timedelta
        start = (date.today() + timedelta(days=10)).isoformat()

        resp = self._overview(
            _case(origin_country_code=None, dest_country_code=None,
                  corridor=None, target_start_date=start)
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()["overview"]["feasibility"])

    def test_unparseable_start_date_yields_null_not_500(self) -> None:
        resp = self._overview(_case(target_start_date="not-a-date"))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()["overview"]["feasibility"])

    def test_overview_is_backward_compatible(self) -> None:
        # Every pre-existing consumer keeps working: the fields they read are
        # untouched and feasibility is purely additive.
        resp = self._overview(_case())
        self.assertEqual(resp.status_code, 200)
        overview = resp.json()["overview"]
        for key in (
            "case_id", "employee", "origin_country_code", "dest_country_code",
            "corridor", "status", "stage", "target_start_date", "family_members",
        ):
            self.assertIn(key, overview)


class RouteIsServedByProdAppTests(unittest.TestCase):
    def test_overview_route_exists_on_the_prod_app_instance(self) -> None:
        # Render boots uvicorn backend.main:app. A route registered only on the
        # modular app/ instance 405s in production (AI-002 v2, AIQ-567, AIQ-568).
        paths = {getattr(r, "path", "") for r in app.routes}
        self.assertIn("/api/hr/cases/{case_id}/overview", paths)


if __name__ == "__main__":
    unittest.main()
