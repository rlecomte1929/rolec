"""
AIQ-622 / AI-I.4b — hermetic tests for the embedding-migration dry-run.

The runner's live path needs a DB; these tests exercise the pure cost/rebuild
math and the offline CLI contract (no DB), so the gate is deterministic in CI.
The roll-up key contract is the task's Validation Criteria:
``{rows, estimated_tokens, estimated_cost_usd, index_rebuild_seconds_est}``.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SCRIPT = os.path.join(_REPO_ROOT, "scripts", "embedding_migration_dryrun.py")

_spec = importlib.util.spec_from_file_location("embedding_migration_dryrun", _SCRIPT)
dryrun = importlib.util.module_from_spec(_spec)
# Register before exec so dataclasses defined in the module resolve their
# __module__ (pytest introspects cls.__module__ during collection).
sys.modules[_spec.name] = dryrun
_spec.loader.exec_module(dryrun)


class CostMathTests(unittest.TestCase):
    def test_tokens_and_cost_from_chars(self) -> None:
        im = dryrun.TableImpact(
            schema="public", table="policy_assistant_chunks",
            embedding_col="embedding", dim=1536, text_col="chunk_text",
            rows=271, chars=44766, indexes=["public.idx (hnsw)"],
        )
        report = dryrun.build_report(
            [im], price_per_1m=0.02, chars_per_token=4.0, rows_per_sec=2000.0
        )
        # 44766 / 4 = 11191.5 -> 11192 tokens; cost = 11192/1e6 * 0.02
        self.assertEqual(report["estimated_tokens"], 11192)
        self.assertAlmostEqual(report["estimated_cost_usd"], round(11192 / 1e6 * 0.02, 6))
        self.assertEqual(report["rows"], 271)

    def test_rollup_has_exact_validation_keys(self) -> None:
        report = dryrun.build_report([], price_per_1m=0.02, chars_per_token=4.0, rows_per_sec=2000.0)
        for key in ("rows", "estimated_tokens", "estimated_cost_usd", "index_rebuild_seconds_est"):
            self.assertIn(key, report)

    def test_index_rebuild_zero_when_no_rows(self) -> None:
        # An empty table with an index costs no rebuild time (mirrors prod rce.canonical_entities).
        im = dryrun.TableImpact(
            schema="rce", table="canonical_entities", embedding_col="embedding",
            dim=768, text_col="canonical_form", rows=0, chars=0,
            indexes=["rce.canonical_entities_embedding_hnsw (hnsw)"],
        )
        report = dryrun.build_report([im], price_per_1m=0.02, chars_per_token=4.0, rows_per_sec=2000.0)
        self.assertEqual(report["index_rebuild_seconds_est"], 0.0)


class OfflineCliTests(unittest.TestCase):
    def test_offline_json_prints_rollup(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = dryrun.main(["--offline", "--rows", "355", "--chars", "113554", "--json"])
        self.assertEqual(rc, 0)
        report = json.loads(buf.getvalue())
        self.assertEqual(report["rows"], 355)
        self.assertEqual(report["estimated_tokens"], 28388)
        self.assertAlmostEqual(report["estimated_cost_usd"], round(28388 / 1e6 * 0.02, 6))


if __name__ == "__main__":
    unittest.main()
