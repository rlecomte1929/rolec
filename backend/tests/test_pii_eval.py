"""
AIQ-602 / AI-W7.4 — pytest wrapper around the offline PII-leak / cross-tier-fence eval.

Keeps the compliance gate (zero leaks, every block carries a FallbackReason code)
green in CI's ``backend-tests`` job. The substantive logic lives in
``backend/eval/run_pii_eval.py``; this file just asserts its report.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.eval.run_pii_eval import DEFAULT_FIXTURES, run_eval


class PiiLeakEvalGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = run_eval(DEFAULT_FIXTURES)

    def test_corpus_has_ten_prompts(self) -> None:
        self.assertEqual(self.report["n_cases"], 10)

    def test_zero_leaks(self) -> None:
        self.assertEqual(
            self.report["leak_count"],
            0,
            msg=f"PII leaks (answered instead of blocked): {self.report['leaks']}",
        )

    def test_every_block_has_a_fallback_reason_code(self) -> None:
        # An un-coded block is invisible to the audit log — the validation
        # criterion requires the block AND the FallbackReason code.
        self.assertEqual(self.report["uncoded_blocks"], [])

    def test_gate_passes_overall(self) -> None:
        self.assertTrue(self.report["gate_pass"])


if __name__ == "__main__":
    unittest.main()
