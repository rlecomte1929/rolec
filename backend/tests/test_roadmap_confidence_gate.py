"""P2-01b — confidence-based gating in the roadmap read path.

Gates AI-roadmap steps by confidence: HIGH (and not requires_expert_review)
shows directly; MEDIUM / LOW / UNKNOWN / expert-flagged are withheld until the
case is released_to_user via the specialist_review flow. The deterministic
derive_roadmap output (no `result` key) is never gated.
"""
import unittest
from types import SimpleNamespace
from unittest import mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import models
from backend.app.routers import cases_read
from backend.app.services import feature_flags, roadmap_confidence_gate as gate


def _step(order, confidence, *, expert=False, title=None):
    return {
        "order": order,
        "title": title or f"step-{order}",
        "confidence": confidence,
        "requires_expert_review": expert,
        "source_url": "https://example.test/rule",
    }


def _ai_roadmap(steps, result="OK"):
    return {"result": result, "corridor": "FR→NO", "summary": "s", "steps": steps}


class GateAiRoadmapTests(unittest.TestCase):
    def test_all_high_shown_directly(self):
        rm = _ai_roadmap([_step(1, "high"), _step(2, "high")])
        out = gate.gate_ai_roadmap(rm, released_to_user=False)
        self.assertEqual(len(out["steps"]), 2)
        self.assertEqual(out["withheld_steps"], [])
        self.assertFalse(out["requires_specialist_review"])

    def test_medium_step_withheld_until_released(self):
        rm = _ai_roadmap([_step(1, "high"), _step(2, "medium")])
        out = gate.gate_ai_roadmap(rm, released_to_user=False)
        self.assertEqual([s["order"] for s in out["steps"]], [1])
        self.assertEqual([s["order"] for s in out["withheld_steps"]], [2])
        self.assertTrue(out["requires_specialist_review"])

    def test_low_and_unknown_confidence_withheld(self):
        rm = _ai_roadmap([_step(1, "low"), _step(2, None), _step(3, "garbage")])
        out = gate.gate_ai_roadmap(rm, released_to_user=False)
        self.assertEqual(out["steps"], [])
        self.assertEqual(len(out["withheld_steps"]), 3)
        self.assertTrue(out["requires_specialist_review"])

    def test_high_but_expert_flagged_is_withheld(self):
        rm = _ai_roadmap([_step(1, "high", expert=True)])
        out = gate.gate_ai_roadmap(rm, released_to_user=False)
        self.assertEqual(out["steps"], [])
        self.assertTrue(out["requires_specialist_review"])

    def test_released_shows_everything(self):
        rm = _ai_roadmap([_step(1, "high"), _step(2, "medium"), _step(3, "low")])
        out = gate.gate_ai_roadmap(rm, released_to_user=True)
        self.assertEqual(len(out["steps"]), 3)
        self.assertEqual(out["withheld_steps"], [])
        self.assertFalse(out["requires_specialist_review"])
        self.assertTrue(out["released_to_user"])

    def test_rule_not_found_has_no_steps_and_no_review(self):
        rm = _ai_roadmap([], result="RULE_NOT_FOUND")
        out = gate.gate_ai_roadmap(rm, released_to_user=False)
        self.assertEqual(out["steps"], [])
        self.assertFalse(out["requires_specialist_review"])

    def test_preserves_roadmap_metadata(self):
        rm = _ai_roadmap([_step(1, "high")])
        out = gate.gate_ai_roadmap(rm, released_to_user=False)
        self.assertEqual(out["corridor"], "FR→NO")
        self.assertEqual(out["result"], "OK")


class IsAiRoadmapTests(unittest.TestCase):
    def test_ai_roadmap_detected_by_result_key(self):
        self.assertTrue(gate.is_ai_roadmap({"result": "OK", "steps": []}))
        self.assertTrue(gate.is_ai_roadmap({"result": "RULE_NOT_FOUND", "steps": []}))

    def test_deterministic_roadmap_is_not_ai(self):
        # derive_roadmap output: tracks/steps/lanes, no `result` key.
        self.assertFalse(gate.is_ai_roadmap({"steps": [], "lanes": []}))
        self.assertFalse(gate.is_ai_roadmap({"result": "something-else"}))
        self.assertFalse(gate.is_ai_roadmap(None))


class _DBTest(unittest.TestCase):
    TABLES = [models.RoadmapReviewStatus, models.FeatureFlag, models.FeatureFlagAccount]

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        models.Base.metadata.create_all(self.engine, tables=[t.__table__ for t in self.TABLES])
        self.Session = sessionmaker(bind=self.engine)

    def _set_released(self, case_id, released):
        with self.Session() as db:
            db.add(models.RoadmapReviewStatus(case_id=case_id, released_to_user=released))
            db.commit()


class ReleasedLookupTests(_DBTest):
    def test_absent_status_is_not_released(self):
        with self.Session() as db:
            self.assertFalse(gate.released_to_user_for("case-x", db=db))

    def test_released_flag_is_read(self):
        self._set_released("case-1", True)
        self._set_released("case-2", False)
        with self.Session() as db:
            self.assertTrue(gate.released_to_user_for("case-1", db=db))
            self.assertFalse(gate.released_to_user_for("case-2", db=db))

    def test_gate_for_case_combines_lookup_and_gate(self):
        self._set_released("case-1", False)
        rm = _ai_roadmap([_step(1, "high"), _step(2, "medium")])
        with self.Session() as db:
            out = gate.gate_roadmap_for_case("case-1", rm, db=db)
        self.assertEqual([s["order"] for s in out["steps"]], [1])
        self.assertTrue(out["requires_specialist_review"])


class RoadmapEndpointGatingTests(_DBTest):
    """Endpoint wiring (P2-01e): when eligible, get_case_roadmap serves the AI
    roadmap from the pipeline (patched here via generate_ai_roadmap_for_case),
    gated by confidence; otherwise it serves the deterministic roadmap."""

    _DET = {"steps": [{"key": "a"}], "lanes": []}

    def _call(self, account_id, *, ai_roadmap=None, flag_enabled=True, allowlist=("acct",), released=False):
        with self.Session() as db:
            db.add(models.FeatureFlag(key=feature_flags.LIVE_EEA_ROADMAP_FLAG, enabled=flag_enabled))
            for a in allowlist:
                db.add(models.FeatureFlagAccount(flag_key=feature_flags.LIVE_EEA_ROADMAP_FLAG, account_id=a))
            db.add(models.RoadmapReviewStatus(case_id="case-1", released_to_user=released))
            db.commit()
        case = SimpleNamespace(status="created", draft_json="{}")
        with mock.patch.object(cases_read, "SessionLocal", self.Session), \
                mock.patch.object(cases_read.crud, "get_case", return_value=case), \
                mock.patch.object(cases_read, "_assert_case_access", lambda *a, **k: None), \
                mock.patch.object(cases_read, "generate_ai_roadmap_for_case",
                                  side_effect=lambda *a, **k: (dict(ai_roadmap) if ai_roadmap is not None else None)), \
                mock.patch.object(cases_read, "derive_roadmap", side_effect=lambda *a, **k: dict(self._DET)), \
                mock.patch.object(feature_flags, "SessionLocal", self.Session), \
                mock.patch.object(gate, "SessionLocal", self.Session):
            return cases_read.get_case_roadmap("case-1", user={"id": account_id})

    def test_falls_back_to_deterministic_when_no_ai_roadmap(self):
        # Flag on + allowlisted, but the pipeline yields nothing → deterministic, ungated.
        res = self._call("acct", ai_roadmap=None)
        self.assertNotIn("requires_specialist_review", res)
        self.assertNotIn("ai_roadmap_eligible", res)
        self.assertEqual(res["steps"], [{"key": "a"}])

    def test_ai_roadmap_gated_when_eligible_and_not_released(self):
        rm = _ai_roadmap([_step(1, "high"), _step(2, "medium")])
        res = self._call("acct", ai_roadmap=rm, released=False)
        self.assertEqual([s["order"] for s in res["steps"]], [1])
        self.assertTrue(res["requires_specialist_review"])
        self.assertTrue(res["ai_roadmap_eligible"])

    def test_flag_off_serves_deterministic(self):
        # Not eligible → pipeline never called → deterministic roadmap served.
        rm = _ai_roadmap([_step(1, "high"), _step(2, "medium")])
        res = self._call("acct", ai_roadmap=rm, flag_enabled=False)
        self.assertEqual(res["steps"], [{"key": "a"}])
        self.assertNotIn("requires_specialist_review", res)
        self.assertNotIn("ai_roadmap_eligible", res)

    # ── [AIQ-1614] test-drive auto-release ─────────────────────────────────────
    def _seed_profile(self, account_id, *, is_test):
        with self.engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS profiles (id TEXT PRIMARY KEY, is_test INTEGER)"
            )
            conn.exec_driver_sql(
                "INSERT INTO profiles (id, is_test) VALUES (?, ?)",
                (account_id, 1 if is_test else 0),
            )

    def test_test_drive_employee_gets_all_steps_auto_released(self):
        # An is_test (test-drive) employee: the AI roadmap is auto-released in-session —
        # even MEDIUM/LOW steps show, and there is no specialist hold. The review row is
        # still NOT released (released=False) — the is_test branch bypasses it entirely.
        self._seed_profile("acct", is_test=True)
        rm = _ai_roadmap([_step(1, "high"), _step(2, "medium"), _step(3, "low")])
        res = self._call("acct", ai_roadmap=rm, released=False)
        self.assertEqual(len(res["steps"]), 3)
        self.assertFalse(res.get("requires_specialist_review"))
        self.assertTrue(res["ai_roadmap_eligible"])

    def test_real_case_gate_still_fires_for_non_test_employee(self):
        # REGRESSION (the whole point of AIQ-1614): a NON-is_test employee keeps the
        # fail-closed confidence gate — a MEDIUM step stays withheld pending specialist
        # release — even with a profiles table present.
        self._seed_profile("acct", is_test=False)
        rm = _ai_roadmap([_step(1, "high"), _step(2, "medium")])
        res = self._call("acct", ai_roadmap=rm, released=False)
        self.assertEqual([s["order"] for s in res["steps"]], [1])
        self.assertTrue(res["requires_specialist_review"])
        self.assertTrue(res["ai_roadmap_eligible"])


if __name__ == "__main__":
    unittest.main()
