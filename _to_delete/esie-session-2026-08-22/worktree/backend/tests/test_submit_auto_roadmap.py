"""
Auto-trigger: after intake submit, AI roadmap generation runs in the background
(_async_generate_and_persist_roadmap) so corridor-specific content replaces the
deterministic seed without a manual admin call. These tests cover the worker's
branch logic (persist on OK, skip on refusal, never raise) with deps mocked —
the deferred imports are patched at their source module.
"""
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

_GEN = "backend.app.services.case_roadmap_profile.generate_ai_roadmap_for_case"
_PERSIST = "backend.app.services.case_roadmap_profile.persist_generated_milestones"


class _FakeCase:
    draft_json = '{"relocationBasics": {"originCountry": "IN", "destCountry": "DE"}}'
    status = "active"


class AsyncGenerateAndPersistTests(unittest.TestCase):
    def test_persists_when_generation_ok(self):
        with mock.patch.object(M, "app_crud") as crud, mock.patch.object(
            M, "SessionLocal"
        ), mock.patch(
            _GEN,
            return_value={"result": "OK", "steps": [{"title": "Blue Card"}], "corridor": "IN→DE", "approved": False},
        ) as gen, mock.patch(_PERSIST, return_value=8) as persist:
            crud.get_case.return_value = _FakeCase()
            M._async_generate_and_persist_roadmap("case-1", "rq")
        gen.assert_called_once()
        persist.assert_called_once()
        # The case_id + request_id thread through to the persist call.
        args, kwargs = persist.call_args
        self.assertEqual(args[1], "case-1")
        self.assertEqual(args[3], "IN→DE")

    def test_skips_persist_on_rule_not_found(self):
        with mock.patch.object(M, "app_crud") as crud, mock.patch.object(
            M, "SessionLocal"
        ), mock.patch(_GEN, return_value={"result": "RULE_NOT_FOUND", "steps": []}), mock.patch(
            _PERSIST
        ) as persist:
            crud.get_case.return_value = _FakeCase()
            M._async_generate_and_persist_roadmap("case-1", "rq")
        persist.assert_not_called()

    def test_skips_when_case_missing(self):
        with mock.patch.object(M, "app_crud") as crud, mock.patch.object(
            M, "SessionLocal"
        ), mock.patch(_GEN) as gen, mock.patch(_PERSIST) as persist:
            crud.get_case.return_value = None
            M._async_generate_and_persist_roadmap("case-1", "rq")
        gen.assert_not_called()
        persist.assert_not_called()

    def test_never_raises_on_generation_error(self):
        with mock.patch.object(M, "app_crud") as crud, mock.patch.object(
            M, "SessionLocal"
        ), mock.patch(_GEN, side_effect=RuntimeError("boom")), mock.patch(_PERSIST) as persist:
            crud.get_case.return_value = _FakeCase()
            # Must swallow the error — a background failure can't crash the worker.
            M._async_generate_and_persist_roadmap("case-1", "rq")
        persist.assert_not_called()


class SeedThenGenerateChainTests(unittest.TestCase):
    """The submit handler dispatches ONE chained background task that seeds the
    deterministic plan then generates the AI roadmap — chained (not two pool
    tasks) so seeding always lands before generation's delete+rewrite."""

    def test_seeds_then_generates_in_order(self):
        calls = []
        with mock.patch.object(
            M, "_ensure_default_milestones_for_case", side_effect=lambda *a, **k: calls.append("seed") or 3
        ) as seed, mock.patch.object(
            M, "_async_generate_and_persist_roadmap", side_effect=lambda *a, **k: calls.append("gen")
        ) as gen:
            M._async_seed_and_generate_roadmap("case-1", "asg-1", "rq")
        seed.assert_called_once_with("case-1", "asg-1", "rq")
        gen.assert_called_once_with("case-1", "rq")
        self.assertEqual(calls, ["seed", "gen"])  # ordering guaranteed

    def test_seeding_failure_does_not_block_generation(self):
        with mock.patch.object(
            M, "_ensure_default_milestones_for_case", side_effect=RuntimeError("boom")
        ), mock.patch.object(M, "_async_generate_and_persist_roadmap") as gen:
            # Must not raise; generation still runs after a seeding failure.
            M._async_seed_and_generate_roadmap("case-1", "asg-1", "rq")
        gen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
