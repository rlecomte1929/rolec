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
        # TD-FIX-4: mid-journey stages present with counts (distinct sessions per stage)
        for k in ("hr_handoff", "intake_start", "intake_completed", "roadmap_reached", "vendor_selected"):
            self.assertEqual(data["funnel"][k], 3, k)
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

    def test_stage_timing_median_and_dropoff(self):
        """TD-M3 (AIQ-1558): median time-on-stage + per-stage drop-off from funnel_events."""
        self._as(True)

        def fake_scalar(sql, params):
            return 0

        def fake_rows(sql, params):
            if "GROUP BY session_id, event_type" in sql:
                return [
                    {"session_id": "s1", "event_type": "start", "ts": "2026-07-05T00:00:00+00:00"},
                    {"session_id": "s1", "event_type": "hr-handoff", "ts": "2026-07-05T00:00:10+00:00"},
                    {"session_id": "s1", "event_type": "intake-start", "ts": "2026-07-05T00:00:20+00:00"},
                    {"session_id": "s2", "event_type": "start", "ts": "2026-07-05T00:00:00+00:00"},
                    {"session_id": "s2", "event_type": "hr-handoff", "ts": "2026-07-05T00:00:30+00:00"},
                ]
            return []

        with patch("backend.app.routers.admin_test_drive._scalar", side_effect=fake_scalar), \
                patch("backend.app.routers.admin_test_drive._rows", side_effect=fake_rows):
            resp = self.client.get("/api/admin/test-drive/overview")
        self.assertEqual(resp.status_code, 200, resp.text)
        timing = {(t["from_stage"], t["to_stage"]): t for t in resp.json()["stage_timing"]}
        # start → hr-handoff: both sessions (durations 10s, 30s → median 20), no drop-off.
        t1 = timing[("start", "hr-handoff")]
        self.assertEqual(t1["median_seconds"], 20.0)
        self.assertEqual(t1["drop_off_pct"], 0.0)
        # hr-handoff → intake-start: only s1 has both (10s); s2 dropped → 50% drop-off.
        t2 = timing[("hr-handoff", "intake-start")]
        self.assertEqual(t2["median_seconds"], 10.0)
        self.assertEqual(t2["reached_from"], 2)
        self.assertEqual(t2["reached_to"], 1)
        self.assertEqual(t2["drop_off_pct"], 50.0)

    def test_follow_up_queue_unions_and_ranks(self):
        """TD-M5 (AIQ-1561): pilot + value-rejecter + early dropout, deduped, pilot-yes first."""
        self._as(True)

        def fake_scalar(sql, params):
            return 0

        def fake_rows(sql, params):
            if "pilot_interest IN ('yes', 'maybe') OR q3_problem_fit = 'no'" in sql:
                return [
                    {"tester_name": "Pilot Y", "tester_email": "y@x.test", "tester_company_role": "Head",
                     "corridor_id": "GB_US", "tester_segment": "prospect", "pilot_interest": "yes",
                     "pilot_note": "keen", "q3_problem_fit": "yes", "q3_why": "", "created_at": "2026-07-05"},
                    {"tester_name": "Rejecter", "tester_email": "n@x.test", "tester_company_role": "Mgr",
                     "corridor_id": "IN_DE", "tester_segment": "internal", "pilot_interest": "no",
                     "pilot_note": "", "q3_problem_fit": "no", "q3_why": "not for us", "created_at": "2026-07-04"},
                ]
            if "status <> 'completed'" in sql:
                return [
                    {"tester_name": "Dropout", "tester_email": "d@x.test", "corridor_id": "FR_NO",
                     "tester_segment": "prospect", "created_at": "2026-07-03"},
                ]
            return []

        with patch("backend.app.routers.admin_test_drive._scalar", side_effect=fake_scalar), \
                patch("backend.app.routers.admin_test_drive._rows", side_effect=fake_rows):
            resp = self.client.get("/api/admin/test-drive/overview")
        self.assertEqual(resp.status_code, 200, resp.text)
        q = resp.json()["follow_up"]
        self.assertEqual({e["tester_email"] for e in q}, {"y@x.test", "n@x.test", "d@x.test"})
        self.assertEqual(q[0]["tester_email"], "y@x.test")  # pilot-yes ranked first
        self.assertIn("pilot_yes", q[0]["reasons"])
        rejecter = next(e for e in q if e["tester_email"] == "n@x.test")
        self.assertIn("problem_fit_no", rejecter["reasons"])
        dropout = next(e for e in q if e["tester_email"] == "d@x.test")
        self.assertIn("dropout", dropout["reasons"])

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
            # AIQ-1566 — prod serves backend.main, so a route only in the modular app 405s.
            self.assertIn("/api/admin/test-drive/referrals", paths, f"referrals missing in {label}")

    # ── AIQ-1566 (BUG-260717-3D77) — referrals for the Outreach page ────────────────

    def test_referrals_non_admin_forbidden(self):
        self._as(False)
        resp = self.client.get("/api/admin/test-drive/referrals")
        self.assertEqual(resp.status_code, 403, resp.text)

    def test_referrals_returns_all_and_flags_unconsented(self):
        """Unlike contacts.csv, this must NOT filter on consent — it flags instead.

        Romain's call: show every referral and mark the ones the referrer didn't confirm,
        so he can see the full picture and decide. Consent gates OUTREACH, not visibility;
        nothing on this path contacts anyone.
        """
        self._as(True)
        sql_calls = []

        def fake_rows(sql, params):
            sql_calls.append(sql)
            return [
                {"referral_name": "Marie Dupont", "referral_contact": "marie@x.test",
                 "referral_company_role": "Head of Mobility", "referral_consent": True,
                 "corridor_id": "FR_NO", "tester_name": "Alex", "created_at": "2026-07-16"},
                {"referral_name": "Jan Novak", "referral_contact": "+420 555 111",
                 "referral_company_role": "HRBP", "referral_consent": None,  # never answered
                 "corridor_id": "FR_NO", "tester_name": "Priya", "created_at": "2026-07-15"},
            ]

        with patch("backend.app.routers.admin_test_drive._rows", side_effect=fake_rows):
            resp = self.client.get("/api/admin/test-drive/referrals?corridor=FR_NO")

        self.assertEqual(resp.status_code, 200, resp.text)
        rows = resp.json()["referrals"]
        self.assertEqual(len(rows), 2, "both referrals returned — consent must not filter")
        self.assertTrue(rows[0]["referral_consent"])
        # NULL consent is "not answered", which is not consent — must coerce to False, not None.
        self.assertIs(rows[1]["referral_consent"], False)
        self.assertEqual(rows[0]["referred_by"], "Alex")
        self.assertEqual(rows[1]["referral_contact"], "+420 555 111")

        sql = sql_calls[0]
        self.assertNotIn("referral_consent = :consent", sql,
                         "must not inherit contacts.csv's consent filter — flag, don't hide")
        self.assertIn("referral_name IS NOT NULL", sql, "must only return rows that have a referral")

    def test_referrals_soft_fail_returns_empty(self):
        """A referral outage must never break the Outreach page."""
        self._as(True)

        def boom(sql, params):
            raise RuntimeError("db down")

        with patch("backend.app.routers.admin_test_drive._rows", side_effect=boom):
            resp = self.client.get("/api/admin/test-drive/referrals")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["referrals"], [])

    # ── multi-referral read-out ────────────────────────────────────────────────
    # A survey row carries its full list in `survey_responses.referrals` (jsonb) and mirrors
    # referrals[0] into the legacy scalars, so reading only the scalars showed ONE intro per
    # survey however many the tester left.

    def _multi_row(self, referrals, **overrides):
        """One survey row whose legacy scalars mirror referrals[0], as the writer stores it."""
        first = referrals[0] if referrals else {}
        row = {
            "referral_name": first.get("name"),
            "referral_contact": first.get("contact"),
            "referral_company_role": first.get("company_role"),
            "referral_consent": first.get("consent", False),
            "referrals": referrals,
            "corridor_id": "FR_NO",
            "tester_name": "Alex",
            "created_at": "2026-07-16",
        }
        row.update(overrides)
        return row

    def test_referrals_expands_one_entry_per_person(self):
        """Three intros on one survey → three entries, each with its OWN consent flag."""
        self._as(True)
        referrals = [
            {"name": "Marie Dupont", "company_role": "Head of Mobility", "contact": "marie@x.test",
             "consent": True},
            {"name": "Jan Novak", "company_role": "HRBP", "contact": "+420 555 111", "consent": False},
            {"name": "Robin Three", "company_role": "People Ops", "contact": "robin@x.test",
             "consent": True},
        ]
        with patch("backend.app.routers.admin_test_drive._rows",
                   return_value=[self._multi_row(referrals)]):
            resp = self.client.get("/api/admin/test-drive/referrals?corridor=FR_NO")

        self.assertEqual(resp.status_code, 200, resp.text)
        rows = resp.json()["referrals"]
        self.assertEqual(len(rows), 3, "one entry per referred person, not per survey")
        self.assertEqual([r["referral_name"] for r in rows],
                         ["Marie Dupont", "Jan Novak", "Robin Three"])
        # Consent is per person — #2 declined while #1 and #3 agreed.
        self.assertEqual([r["referral_consent"] for r in rows], [True, False, True])
        # Survey-level context is carried onto every entry.
        self.assertTrue(all(r["referred_by"] == "Alex" for r in rows))
        self.assertTrue(all(r["corridor_id"] == "FR_NO" for r in rows))

    def test_referrals_json_string_column_is_parsed(self):
        """SQLite hands jsonb back as text where psycopg2 gives a list — both must expand."""
        self._as(True)
        referrals = [{"name": "Marie", "contact": "marie@x.test", "consent": True},
                     {"name": "Jan", "contact": "jan@x.test", "consent": True}]
        row = self._multi_row(referrals)
        row["referrals"] = json.dumps(referrals)
        with patch("backend.app.routers.admin_test_drive._rows", return_value=[row]):
            resp = self.client.get("/api/admin/test-drive/referrals")
        self.assertEqual([r["referral_name"] for r in resp.json()["referrals"]], ["Marie", "Jan"])

    def test_referrals_historical_row_uses_legacy_scalars_once(self):
        """A row written before multi-referral has `referrals` empty — fall back to the
        legacy scalars and emit exactly ONE entry (never a duplicate of referrals[0])."""
        self._as(True)
        row = self._multi_row([])
        row.update({"referral_name": "Old Referral", "referral_contact": "old@x.test",
                    "referral_company_role": "HRD", "referral_consent": True, "referrals": []})
        with patch("backend.app.routers.admin_test_drive._rows", return_value=[row]):
            resp = self.client.get("/api/admin/test-drive/referrals")
        rows = resp.json()["referrals"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["referral_name"], "Old Referral")
        self.assertTrue(rows[0]["referral_consent"])

    def test_referrals_falls_back_when_column_missing(self):
        """Before the migration is applied prod has no `referrals` column — the panel must
        degrade to the old one-per-survey view, NOT to empty."""
        self._as(True)
        seen = []

        def fake_rows(sql, params):
            seen.append(sql)
            if "referrals," in sql:
                raise RuntimeError('column "referrals" does not exist')
            return [{"referral_name": "Marie", "referral_contact": "marie@x.test",
                     "referral_company_role": "Head of Mobility", "referral_consent": True,
                     "corridor_id": "FR_NO", "tester_name": "Alex", "created_at": "2026-07-16"}]

        with patch("backend.app.routers.admin_test_drive._rows", side_effect=fake_rows):
            resp = self.client.get("/api/admin/test-drive/referrals")

        self.assertEqual(resp.status_code, 200, resp.text)
        rows = resp.json()["referrals"]
        self.assertEqual(len(rows), 1, "degrades to the legacy view rather than going empty")
        self.assertEqual(rows[0]["referral_name"], "Marie")
        self.assertEqual(len(seen), 2, "tries the referrals column, then falls back")

    def test_contacts_csv_lists_every_consented_person(self):
        """The outreach CSV must carry each consented person — including #2 on a survey whose
        first referral was NOT consented, which a row-level SQL consent filter would drop."""
        self._as(True)
        referrals = [
            {"name": "Unconsented First", "company_role": "HRBP", "contact": "no@x.test",
             "consent": False},
            {"name": "Consented Second", "company_role": "Head of Mobility",
             "contact": "yes@x.test", "consent": True},
        ]
        row = self._multi_row(referrals)

        # The CSV builds three sections off _rows; only feed the referral one.
        def fake_rows(sql, params):
            return [row] if "referral_name" in sql else []

        with patch("backend.app.routers.admin_test_drive._rows", side_effect=fake_rows):
            resp = self.client.get("/api/admin/test-drive/contacts.csv")

        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.text
        referral_lines = [ln for ln in body.splitlines() if ln.startswith("referral,")]
        self.assertEqual(len(referral_lines), 1, "only the consented person is exported")
        self.assertIn("Consented Second", referral_lines[0])
        self.assertNotIn("Unconsented First", body, "consent gates outreach, per person")


if __name__ == "__main__":
    unittest.main()
