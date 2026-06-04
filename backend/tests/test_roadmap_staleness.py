"""P2-01c — >30-day source-staleness warning on roadmap steps.

A shown step whose cited source was last updated more than 30 days ago gets a
`staleness_warning`; the roadmap gets a top-level `has_stale_sources`. Absent or
unparseable timestamps never warn. `now` is injected (no wall-clock in the core).
"""
import datetime as dt
import unittest
from types import SimpleNamespace
from unittest import mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import models
from backend.app.routers import cases_read
from backend.app.services import feature_flags
from backend.app.services import roadmap_staleness as stale

NOW = dt.datetime(2026, 6, 4, tzinfo=dt.timezone.utc)


def _days_ago(n):
    return (NOW - dt.timedelta(days=n)).date().isoformat()


def _step(order, source_updated_at=None, citations=None):
    s = {"order": order, "title": f"step-{order}", "confidence": "high"}
    if source_updated_at is not None:
        s["source_updated_at"] = source_updated_at
    if citations is not None:
        s["citations"] = citations
    return s


def _ai_roadmap(steps):
    return {"result": "OK", "corridor": "FR→NO", "steps": steps}


class IsSourceStaleTests(unittest.TestCase):
    def test_fresh_source_not_stale(self):
        self.assertFalse(stale.is_source_stale(_days_ago(29), now=NOW))

    def test_old_source_is_stale(self):
        self.assertTrue(stale.is_source_stale(_days_ago(31), now=NOW))

    def test_exactly_threshold_not_stale(self):
        self.assertFalse(stale.is_source_stale(_days_ago(30), now=NOW))

    def test_absent_timestamp_not_stale(self):
        self.assertFalse(stale.is_source_stale(None, now=NOW))
        self.assertFalse(stale.is_source_stale("", now=NOW))

    def test_unparseable_timestamp_not_stale(self):
        self.assertFalse(stale.is_source_stale("not-a-date", now=NOW))

    def test_naive_now_treated_as_utc(self):
        self.assertTrue(stale.is_source_stale(_days_ago(40), now=dt.datetime(2026, 6, 4)))


class AnnotateStalenessTests(unittest.TestCase):
    def test_old_source_gets_warning(self):
        rm = _ai_roadmap([_step(1, _days_ago(45))])
        out = stale.annotate_staleness(rm, now=NOW)
        self.assertTrue(out["has_stale_sources"])
        w = out["steps"][0]["staleness_warning"]
        self.assertTrue(w["stale"])
        self.assertEqual(w["age_days"], 45)
        self.assertEqual(w["threshold_days"], 30)

    def test_fresh_source_no_warning(self):
        rm = _ai_roadmap([_step(1, _days_ago(10))])
        out = stale.annotate_staleness(rm, now=NOW)
        self.assertFalse(out["has_stale_sources"])
        self.assertNotIn("staleness_warning", out["steps"][0])

    def test_no_timestamp_no_warning(self):
        rm = _ai_roadmap([_step(1)])
        out = stale.annotate_staleness(rm, now=NOW)
        self.assertFalse(out["has_stale_sources"])
        self.assertNotIn("staleness_warning", out["steps"][0])

    def test_oldest_citation_drives_warning(self):
        rm = _ai_roadmap([_step(1, citations=[
            {"source_url": "a", "updated_at": _days_ago(5)},
            {"source_url": "b", "updated_at": _days_ago(99)},
        ])])
        out = stale.annotate_staleness(rm, now=NOW)
        self.assertTrue(out["has_stale_sources"])
        self.assertEqual(out["steps"][0]["staleness_warning"]["age_days"], 99)

    def test_mixed_steps(self):
        rm = _ai_roadmap([_step(1, _days_ago(2)), _step(2, _days_ago(60))])
        out = stale.annotate_staleness(rm, now=NOW)
        self.assertTrue(out["has_stale_sources"])
        self.assertNotIn("staleness_warning", out["steps"][0])
        self.assertIn("staleness_warning", out["steps"][1])

    def test_does_not_mutate_input(self):
        rm = _ai_roadmap([_step(1, _days_ago(40))])
        stale.annotate_staleness(rm, now=NOW)
        self.assertNotIn("staleness_warning", rm["steps"][0])
        self.assertNotIn("has_stale_sources", rm)


class RoadmapEndpointStalenessTests(unittest.TestCase):
    TABLES = [models.RoadmapReviewStatus, models.FeatureFlag, models.FeatureFlagAccount]

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        models.Base.metadata.create_all(self.engine, tables=[t.__table__ for t in self.TABLES])
        self.Session = sessionmaker(bind=self.engine)
        with self.Session() as db:
            db.add(models.FeatureFlag(key=feature_flags.LIVE_EEA_ROADMAP_FLAG, enabled=True))
            db.add(models.FeatureFlagAccount(flag_key=feature_flags.LIVE_EEA_ROADMAP_FLAG, account_id="acct"))
            db.add(models.RoadmapReviewStatus(case_id="case-1", released_to_user=True))
            db.commit()

    def _call(self, roadmap):
        from backend.app.services import roadmap_confidence_gate as gate
        case = SimpleNamespace(status="created", draft_json="{}")
        with mock.patch.object(cases_read, "SessionLocal", self.Session), \
                mock.patch.object(cases_read.crud, "get_case", return_value=case), \
                mock.patch.object(cases_read, "_assert_case_access", lambda *a, **k: None), \
                mock.patch.object(cases_read, "derive_roadmap", side_effect=lambda *a, **k: dict(roadmap)), \
                mock.patch.object(feature_flags, "SessionLocal", self.Session), \
                mock.patch.object(gate, "SessionLocal", self.Session):
            return cases_read.get_case_roadmap("case-1", user={"id": "acct"})

    def test_stale_source_surfaces_warning_on_served_roadmap(self):
        # released_to_user → step visible; source dated 2000 → always >30 days old.
        rm = _ai_roadmap([_step(1, "2000-01-01")])
        res = self._call(rm)
        self.assertTrue(res["has_stale_sources"])
        self.assertTrue(res["steps"][0]["staleness_warning"]["stale"])


if __name__ == "__main__":
    unittest.main()
