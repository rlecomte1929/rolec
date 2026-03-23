"""Contract tests: normalization error envelope (outcome, persistence_stage, etc.)."""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_normalization_errors import (  # noqa: E402
    PolicyNormalizationFieldIssue,
    PolicyNormalizationPayloadInvalid,
)


class PolicyNormalizationErrorsTests(unittest.TestCase):
    def test_invalid_schema_maps_to_validation_failed_outcome(self) -> None:
        inv = PolicyNormalizationPayloadInvalid(
            error_code="INVALID_POLICY_VERSION_SCHEMA",
            message="bad",
            details=[PolicyNormalizationFieldIssue(field="policy_versions[0].status", issue="invalid")],
        )
        body = inv.to_response_body()
        self.assertEqual(body["outcome"], "validation_failed")
        self.assertEqual(body["error_code"], "INVALID_POLICY_VERSION_SCHEMA")
        self.assertFalse(body["ok"])

    def test_persistence_failed_includes_stage(self) -> None:
        inv = PolicyNormalizationPayloadInvalid(
            error_code="PERSISTENCE_FAILED",
            message="db said no",
            persistence_stage="layer2",
        )
        body = inv.to_response_body()
        self.assertEqual(body["outcome"], "persistence_failed")
        self.assertEqual(body["persistence_stage"], "layer2")

    def test_normalization_not_ready_outcome(self) -> None:
        inv = PolicyNormalizationPayloadInvalid(
            error_code="NORMALIZATION_NOT_READY",
            message="input",
        )
        self.assertEqual(inv.to_response_body()["outcome"], "normalization_not_ready")


if __name__ == "__main__":
    unittest.main()
