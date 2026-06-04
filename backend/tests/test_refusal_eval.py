"""
AIQ-601 / AI-W7.3 — pytest wrapper around the offline refusal-correctness eval.

Keeps the gate (refusal recall >= 0.95, no over-refusals, no pinned-code drift)
green in CI's ``backend-tests`` job. The substantive logic lives in
``backend/eval/run_refusal_eval.py``; this file just asserts its report.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.eval.run_refusal_eval import DEFAULT_FIXTURES, run_eval


class RefusalEvalGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = run_eval(DEFAULT_FIXTURES)

    def test_corpus_has_twenty_should_refuse_prompts(self) -> None:
        self.assertEqual(self.report["n_should_refuse"], 20)

    def test_has_should_answer_controls(self) -> None:
        # Controls guard against the trivial "refuse everything" recall=1.0 cheat.
        self.assertGreaterEqual(self.report["n_controls"], 1)

    def test_refusal_recall_meets_gate(self) -> None:
        self.assertGreaterEqual(
            self.report["refusal_recall"],
            self.report["threshold"],
            msg=f"missed refusals: {self.report['missed_refusals']}",
        )

    def test_no_over_refusals_on_controls(self) -> None:
        self.assertEqual(self.report["over_refusals"], [])

    def test_no_pinned_refusal_code_drift(self) -> None:
        self.assertEqual(self.report["code_mismatches"], [])

    def test_gate_passes_overall(self) -> None:
        self.assertTrue(self.report["gate_pass"])


if __name__ == "__main__":
    unittest.main()
