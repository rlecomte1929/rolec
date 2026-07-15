"""
Intake submit must seed the default relocation plan so the employee's plan view
(GET /api/relocation-plans/{case_id}/view, which reads case_milestones) is not
empty immediately after submit. Before this fix, case_milestones were only ever
populated lazily by the timeline `?ensure_defaults=true` endpoints, so a
freshly-submitted case showed phases:0 until an HR user happened to open the
timeline.

These tests exercise the extracted helper `_ensure_default_milestones_for_case`
directly with the DB layer mocked, covering:
  - idempotency (no-op when the case already has milestones — never clobber an
    HR-curated timeline),
  - seeding when empty (one upsert per derived milestone),
  - corridor/context extraction from the wizard draft (the inputs that make the
    default milestones corridor-aware).
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("POLICY_ASSISTANT_LLM", "mock")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.main as M  # noqa: E402


class _FakeCase:
    def __init__(self, draft, target_move_date=None):
        self.draft_json = json.dumps(draft)
        self.target_move_date = target_move_date


_DRAFT = {
    "relocationBasics": {
        "originCountry": "IN",
        "destCountry": "DE",
        "nationality": "IN",
    },
    "assignmentContext": {"contractType": "Permanent"},
}


class EnsureDefaultMilestonesTests(unittest.TestCase):
    def test_idempotent_when_milestones_already_exist(self):
        with mock.patch.object(M, "db") as db, mock.patch.object(
            M, "compute_default_milestones"
        ) as cdm:
            db.list_case_milestones.return_value = [{"id": "m1"}]
            created = M._ensure_default_milestones_for_case("case1", "asg1")
        self.assertEqual(created, 0)
        cdm.assert_not_called()
        db.upsert_case_milestone.assert_not_called()

    def test_seeds_when_empty_and_extracts_corridor_context(self):
        captured = {}

        def fake_cdm(**kwargs):
            captured.update(kwargs)
            return [
                {"milestone_type": "visa", "title": "Apply for visa"},
                {"milestone_type": "housing", "title": "Find housing"},
            ]

        with mock.patch.object(M, "db") as db, mock.patch.object(
            M, "SessionLocal"
        ), mock.patch.object(M, "app_crud") as app_crud, mock.patch.object(
            M, "compute_default_milestones", side_effect=fake_cdm
        ):
            db.list_case_milestones.return_value = []
            db.list_case_services.return_value = [
                {"service_key": "housing", "selected": True},
                {"service_key": "banks", "selected": False},
            ]
            app_crud.get_case.return_value = _FakeCase(_DRAFT, "2026-10-01")
            created = M._ensure_default_milestones_for_case("case1", "asg1")

        self.assertEqual(created, 2)
        self.assertEqual(db.upsert_case_milestone.call_count, 2)
        # The wizard draft drives the corridor-aware milestone derivation.
        self.assertEqual(captured["destination_country"], "DE")
        self.assertEqual(captured["origin_country"], "IN")
        self.assertEqual(captured["nationality"], "IN")
        self.assertEqual(captured["contract_type"], "Permanent")
        self.assertEqual(captured["target_move_date"], "2026-10-01")
        # Only selected services flow through.
        self.assertEqual(captured["selected_services"], ["housing"])

    def test_upsert_failure_is_swallowed_and_counted_correctly(self):
        def fake_cdm(**_):
            return [
                {"milestone_type": "visa", "title": "A"},
                {"milestone_type": "housing", "title": "B"},
            ]

        with mock.patch.object(M, "db") as db, mock.patch.object(
            M, "SessionLocal"
        ), mock.patch.object(M, "app_crud") as app_crud, mock.patch.object(
            M, "compute_default_milestones", side_effect=fake_cdm
        ):
            db.list_case_milestones.return_value = []
            db.list_case_services.return_value = []
            app_crud.get_case.return_value = _FakeCase(_DRAFT)
            db.upsert_case_milestone.side_effect = [None, RuntimeError("boom")]
            created = M._ensure_default_milestones_for_case("case1", "asg1")
        # One succeeded, one failed — failure must not raise, count reflects success.
        self.assertEqual(created, 1)

    def test_generation_leaves_the_roadmap_released_no_hr_hold(self):
        # [AIQ-1377] A generated roadmap is RELEASED by default. Generation must NOT create a
        # roadmap_review_status row: doing so held every new case pending an HR approval that,
        # for wizard-id cases with no linked HR, never came — the roadmap page rendered
        # "in review" instead of the plan for every freshly provisioned case. HR still HOLDS a
        # plan on demand via request-changes; it is an opt-in action, not a default block.
        import backend.app.models as _models

        with mock.patch.object(M, "db") as db, mock.patch.object(
            M, "SessionLocal"
        ), mock.patch.object(M, "app_crud") as app_crud, mock.patch.object(
            M, "compute_default_milestones",
            side_effect=lambda **_: [{"milestone_type": "visa", "title": "A"}],
        ), mock.patch.object(_models, "RoadmapReviewStatus") as RRS:
            db.list_case_milestones.return_value = []
            db.list_case_services.return_value = []
            app_crud.get_case.return_value = _FakeCase(_DRAFT)
            created = M._ensure_default_milestones_for_case("case1", "asg1")

        self.assertEqual(created, 1)
        # The regression guard: no HR-review hold row is constructed on generation.
        RRS.assert_not_called()


if __name__ == "__main__":
    unittest.main()
