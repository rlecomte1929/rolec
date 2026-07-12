"""AIQ-1428 (TD-10) — admin Test-Drive dashboard tests.

  1. Non-admin              → 403
  2. Admin overview         → 200; funnel + scorecard + pilot_leads + testimonials shape;
                              testimonials query carries the consent filter
  3. Routes in BOTH apps
"""
from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.app.auth_deps import get_current_user  # noqa: E402


class TestAdminTestDrive(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()

    def _as(self, is_admin: bool):
        app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "is_admin": is_admin}

    def test_non_admin_forbidden(self):
        self._as(False)
        resp = self.client.get("/api/admin/test-drive/overview")
        self.assertEqual(resp.status_code, 403, resp.text)

    def test_overview_shape_and_consent_filter(self):
        self._as(True)
        sql_calls = []

        def fake_scalar(sql, params):
            return 3  # every count / avg → 3

        def fake_rows(sql, params):
            sql_calls.append(sql)
            if "GROUP BY q3_problem_fit" in sql:
                return [{"fit": "yes", "n": 2}, {"fit": "no", "n": 1}]
            if "SELECT tester_name" in sql and "pilot_interest IN" in sql:
                return [{"tester_name": "Alex", "tester_email": "a@x.test", "tester_company_role": "Head",
                         "tester_sector": "energy", "pilot_interest": "yes", "pilot_note": "", "corridor_id": "GB_US",
                         "tester_segment": "prospect", "created_at": "2026-07-05"}]
            if "SELECT testimonial" in sql:
                return [{"testimonial": "great", "tester_name": "Alex", "tester_company_role": "Head",
                         "corridor_id": "GB_US", "created_at": "2026-07-05"}]
            if "tester_email IS NOT NULL" in sql:  # completions panel (TD-12)
                return [{"tester_name": "Priya", "tester_email": "priya@y.test", "tester_company_role": "HRBP",
                         "tester_sector": "pharma", "q1_overall": 4, "pilot_interest": "no", "corridor_id": "GB_US",
                         "tester_segment": "prospect", "created_at": "2026-07-04"}]
            return []

        with patch("backend.app.routers.admin_test_drive._scalar", side_effect=fake_scalar), \
                patch("backend.app.routers.admin_test_drive._rows", side_effect=fake_rows):
            resp = self.client.get("/api/admin/test-drive/overview?corridor=GB_US&segment=prospect")

        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        # funnel
        self.assertEqual(data["funnel"]["provisioned"], 3)
        self.assertEqual(data["funnel"]["pilot"], 3)
        # scorecard
        self.assertEqual(data["scorecard"]["avg_overall"], 3.0)
        self.assertEqual(data["scorecard"]["problem_fit"], {"yes": 2, "no": 1})
        # panels
        self.assertEqual(len(data["pilot_leads"]), 1)
        self.assertEqual(data["testimonials"][0]["testimonial"], "great")
        # completions panel (TD-12): every surveyed tester with an email, carrying the email
        self.assertEqual(len(data["completions"]), 1)
        self.assertEqual(data["completions"][0]["tester_email"], "priya@y.test")
        completions_sql = [s for s in sql_calls if "tester_email IS NOT NULL" in s]
        self.assertTrue(completions_sql, "completions query must scope to rows with an email")
        # the testimonials query must filter on consent
        testi_sql = [s for s in sql_calls if "SELECT testimonial" in s]
        self.assertTrue(testi_sql and "testimonial_consent = :consent" in testi_sql[0])

    def test_invited_sums_metadata_counts(self):
        """TD-FIX-3: 'invited' is the SUM of invite-sent metadata counts, not a row count."""
        self._as(True)

        def fake_scalar(sql, params):
            return 0

        def fake_rows(sql, params):
            if "SELECT metadata FROM funnel_events" in sql:
                return [
                    {"metadata": json.dumps({"count": 25, "channel": "whatsapp"})},
                    {"metadata": json.dumps({"count": 10, "channel": "email"})},
                ]
            return []

        with patch("backend.app.routers.admin_test_drive._scalar", side_effect=fake_scalar), \
                patch("backend.app.routers.admin_test_drive._rows", side_effect=fake_rows):
            resp = self.client.get("/api/admin/test-drive/overview")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["funnel"]["invited"], 35)

    def test_record_invites_forbidden_for_non_admin(self):
        self._as(False)
        resp = self.client.post("/api/admin/test-drive/invites", json={"count": 5, "channel": "email"})
        self.assertEqual(resp.status_code, 403, resp.text)

    def test_record_invites_inserts_funnel_row(self):
        self._as(True)
        db = MagicMock()
        with patch("backend.app.routers.admin_test_drive.db", db):
            resp = self.client.post(
                "/api/admin/test-drive/invites",
                json={"count": 25, "segment": "prospect", "channel": "whatsapp"},
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["recorded"], 25)
        conn = db.engine.begin.return_value.__enter__.return_value
        inserts = [c for c in conn.execute.call_args_list if "INSERT INTO funnel_events" in str(c.args[0])]
        self.assertEqual(len(inserts), 1)
        bound = inserts[0].args[1]
        self.assertEqual(bound["tester_segment"], "prospect")
        self.assertIn("'invite-sent'", str(inserts[0].args[0]))
        md = json.loads(bound["metadata"])
        self.assertEqual(md["count"], 25)
        self.assertEqual(md["channel"], "whatsapp")

    def test_record_invites_rejects_bad_channel(self):
        self._as(True)
        resp = self.client.post(
            "/api/admin/test-drive/invites", json={"count": 5, "channel": "carrier-pigeon"}
        )
        self.assertEqual(resp.status_code, 422, resp.text)

    def test_routes_registered_in_both_apps(self):
        from backend.main import app as prod_app
        from backend.app.main import app as modular_app
        for a, label in ((prod_app, "backend.main"), (modular_app, "backend.app.main")):
            paths = [r.path for r in a.routes if "admin/test-drive" in getattr(r, "path", "")]
            self.assertIn("/api/admin/test-drive/overview", paths, f"overview missing in {label}")
            self.assertIn("/api/admin/test-drive/invites", paths, f"invites missing in {label}")


if __name__ == "__main__":
    unittest.main()
