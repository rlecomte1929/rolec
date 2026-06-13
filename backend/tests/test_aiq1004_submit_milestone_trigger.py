"""AIQ-1004 — intake submit must materialize the relocation plan.

The submit handler used to end at set_assignment_submitted + a case_event, so
case_milestones stayed empty and relocation-plans/{id}/view returned phases:0
until someone hit the timeline endpoint with ?ensure_defaults. The fix wires the
shared _ensure_default_milestones_for_case helper into submit.

This drives that helper directly (DB layer patched) and asserts it loads the
case draft → computes default milestones → upserts them. The milestone-content
correctness is the verbatim-lifted compute_default_milestones, covered by
test_s5_plan_wiring / test_p2_immigration_regimes.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.main as m  # noqa: E402


class EnsureDefaultMilestonesTests(unittest.TestCase):
    def _fake_case(self):
        c = mock.MagicMock()
        c.draft_json = json.dumps({
            "relocationBasics": {"destCountry": "DE", "originCountry": "IN", "contractType": "LTA"},
            "primaryApplicant": {"nationality": "IN"},
        })
        c.target_move_date = "2026-09-01"
        return c

    def test_helper_materializes_milestones_from_draft(self):
        upserts = []
        with mock.patch.object(m, "app_crud") as mac, \
             mock.patch.object(m.db, "list_case_services", return_value=[]), \
             mock.patch.object(m.db, "upsert_case_milestone",
                               side_effect=lambda **kw: upserts.append(kw)), \
             mock.patch.object(m.db, "upsert_exception_request", return_value=None):
            mac.get_case.return_value = self._fake_case()
            m._ensure_default_milestones_for_case("assign-1", "case-1")
        # The deterministic LTA plan produced at least one milestone, persisted.
        self.assertGreater(len(upserts), 0)
        for kw in upserts:
            self.assertEqual(kw["case_id"], "case-1")
            self.assertTrue(kw.get("milestone_type"))
            self.assertTrue(kw.get("title"))

    def test_helper_never_raises_on_db_failure(self):
        # Best-effort contract: a DB hiccup must not propagate into the caller
        # (submit must still return success:true).
        with mock.patch.object(m, "app_crud") as mac, \
             mock.patch.object(m.db, "list_case_services", side_effect=RuntimeError("boom")), \
             mock.patch.object(m.db, "upsert_case_milestone", side_effect=RuntimeError("boom")):
            mac.get_case.side_effect = RuntimeError("boom")
            # Must not raise.
            m._ensure_default_milestones_for_case("assign-1", "case-1")

    def test_submit_handler_calls_the_materializer(self):
        # Lock the wiring: the submit endpoint invokes the materializer. We assert
        # the source wires it (guards against a future refactor dropping the call).
        import inspect
        src = inspect.getsource(m.submit_assignment)
        self.assertIn("_ensure_default_milestones_for_case", src)


if __name__ == "__main__":
    unittest.main()
