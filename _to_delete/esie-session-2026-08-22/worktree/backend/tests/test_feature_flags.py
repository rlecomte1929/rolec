"""P2-01a — backend feature-flag gate for the live EEA roadmap.

Covers the `is_flag_enabled_for` helper truth-table and the single wiring
seam in `get_case_roadmap`: OFF path is byte-identical; ON + allowlisted
gains the additive `ai_roadmap_eligible` field.
"""
import os
import unittest
from types import SimpleNamespace
from unittest import mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import models
from backend.app.routers import cases_read
from backend.app.services import feature_flags
from backend.app.services import roadmap_confidence_gate as gate


SCHEMA_TABLES = [models.FeatureFlag, models.FeatureFlagAccount, models.RoadmapReviewStatus]
FLAG = feature_flags.LIVE_EEA_ROADMAP_FLAG


class _DBTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        models.Base.metadata.create_all(
            self.engine, tables=[t.__table__ for t in SCHEMA_TABLES]
        )
        self.Session = sessionmaker(bind=self.engine)

    def _seed(self, *, enabled: bool, allowlist=()):
        with self.Session() as db:
            db.add(models.FeatureFlag(key=FLAG, enabled=enabled))
            for account_id in allowlist:
                db.add(models.FeatureFlagAccount(flag_key=FLAG, account_id=account_id))
            db.commit()


class IsFlagEnabledForTests(_DBTest):
    def _check(self, account_id: str) -> bool:
        with self.Session() as db:
            return feature_flags.is_flag_enabled_for(account_id, db=db)

    def test_missing_flag_is_false(self):
        self.assertFalse(self._check("acct-1"))

    def test_disabled_flag_is_false_even_if_allowlisted(self):
        self._seed(enabled=False, allowlist=["acct-1"])
        self.assertFalse(self._check("acct-1"))

    def test_enabled_but_not_allowlisted_is_false(self):
        self._seed(enabled=True, allowlist=["acct-1"])
        self.assertFalse(self._check("acct-2"))

    def test_enabled_and_allowlisted_is_true(self):
        self._seed(enabled=True, allowlist=["acct-1"])
        self.assertTrue(self._check("acct-1"))

    def test_empty_account_id_is_false(self):
        self._seed(enabled=True, allowlist=[""])
        self.assertFalse(self._check(""))

    def test_opens_own_session_when_db_omitted(self):
        self._seed(enabled=True, allowlist=["acct-1"])
        with mock.patch.object(feature_flags, "SessionLocal", self.Session):
            self.assertTrue(feature_flags.is_flag_enabled_for("acct-1"))
            self.assertFalse(feature_flags.is_flag_enabled_for("nope"))


class RoadmapEndpointGateTests(_DBTest):
    """The flag gates whether get_case_roadmap serves the AI roadmap. When
    eligible, the pipeline (patched via generate_ai_roadmap_for_case) is served
    and marked ai_roadmap_eligible; otherwise the deterministic roadmap is."""

    _AI = {"result": "OK", "steps": [{"order": 1, "confidence": "high", "source_url": "u"}]}

    def _call(self, account_id: str):
        case = SimpleNamespace(status="created", draft_json="{}")
        with mock.patch.object(cases_read, "SessionLocal", self.Session), \
                mock.patch.object(cases_read.crud, "get_case", return_value=case), \
                mock.patch.object(cases_read, "_assert_case_access", lambda *a, **k: None), \
                mock.patch.object(cases_read, "generate_ai_roadmap_for_case",
                                  side_effect=lambda *a, **k: dict(self._AI)), \
                mock.patch.object(cases_read, "derive_roadmap", side_effect=lambda *a, **k: {"steps": []}), \
                mock.patch.object(feature_flags, "SessionLocal", self.Session), \
                mock.patch.object(gate, "SessionLocal", self.Session):
            return cases_read.get_case_roadmap("case-1", user={"id": account_id})

    def test_off_path_serves_deterministic(self):
        # Flag disabled → deterministic roadmap, AI pipeline never served.
        self._seed(enabled=False, allowlist=["test-acct"])
        res = self._call("test-acct")
        self.assertNotIn("ai_roadmap_eligible", res)
        self.assertEqual(res, {"steps": []})

    def test_enabled_but_not_allowlisted_serves_deterministic(self):
        self._seed(enabled=True, allowlist=["test-acct"])
        res = self._call("someone-else")
        self.assertNotIn("ai_roadmap_eligible", res)
        self.assertEqual(res, {"steps": []})

    def test_enabled_and_allowlisted_serves_ai_roadmap(self):
        self._seed(enabled=True, allowlist=["test-acct"])
        res = self._call("test-acct")
        self.assertIs(res["ai_roadmap_eligible"], True)
        self.assertEqual(res["result"], "OK")


class ResolveFlagSafeTest(unittest.TestCase):
    """`resolve_flag_safe`: DB row wins, else env var, else default; never raises."""

    KEY = "SOME_MIGRATED_TEST_FLAG"

    def tearDown(self) -> None:
        os.environ.pop(self.KEY, None)

    def _memory_sessionmaker(self):
        engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        models.Base.metadata.create_all(
            engine,
            tables=[models.FeatureFlag.__table__, models.FeatureFlagAccount.__table__],
        )
        return sessionmaker(bind=engine)

    def test_env_fallback_when_no_db_row(self):
        Session = self._memory_sessionmaker()
        with mock.patch.object(feature_flags, "SessionLocal", Session):
            os.environ[self.KEY] = "true"
            self.assertTrue(feature_flags.resolve_flag_safe(self.KEY))
            os.environ[self.KEY] = "false"
            self.assertFalse(feature_flags.resolve_flag_safe(self.KEY))
            os.environ.pop(self.KEY, None)
            self.assertFalse(feature_flags.resolve_flag_safe(self.KEY, env_default=False))
            self.assertTrue(feature_flags.resolve_flag_safe(self.KEY, env_default=True))

    def test_db_row_wins_over_env(self):
        Session = self._memory_sessionmaker()
        with Session() as db:
            db.add(models.FeatureFlag(key=self.KEY, enabled=True))
            db.commit()
        with mock.patch.object(feature_flags, "SessionLocal", Session):
            os.environ[self.KEY] = "false"  # env OFF, DB ON → DB wins
            self.assertTrue(feature_flags.resolve_flag_safe(self.KEY))

    def test_exception_falls_back_to_env(self):
        def _boom():
            raise RuntimeError("db unavailable")

        with mock.patch.object(feature_flags, "SessionLocal", _boom):
            os.environ[self.KEY] = "true"
            self.assertTrue(feature_flags.resolve_flag_safe(self.KEY))
            os.environ[self.KEY] = "false"
            self.assertFalse(feature_flags.resolve_flag_safe(self.KEY))


if __name__ == "__main__":
    unittest.main()
