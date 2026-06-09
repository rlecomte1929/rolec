"""
[AIQ-931] Regression: a successful policy-document normalize must advance the
document's processing_status out of 'classified'.

Before this fix, normalize_policy_document created the company_policy /
policy_version / benefit_rules and (when publishable) auto-published, but never
wrote policy_documents.processing_status — so the document read 'classified'
forever even after a successful normalize+publish. Verified live against prod:
POST /api/hr/policy-documents/{id}/normalize returned normalized+published while
the row stayed 'classified' (the "21 docs stuck at classified" symptom).

The pipeline itself is heavy (run_normalization), so we mock the normalization
seam and assert only the new behaviour: on success the handler calls
db.update_policy_document(doc_id, processing_status=STATUS_NORMALIZED).
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

# Importing backend.main installs the SQLAlchemy query-counter on db.engine,
# which is a MagicMock under conftest's backend.database mock — registering the
# event listener on a mock raises. Disable the counter before import (the
# documented app-mounted-harness requirement).
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend import main as m  # noqa: E402
from backend.app.services.policy_document_intake import STATUS_NORMALIZED  # noqa: E402


def _result(publishable: bool):
    return {
        "policy_id": "pol-1",
        "policy_version_id": "ver-1",
        "publishable": publishable,
        "summary": {
            "benefit_rules": 2,
            "exclusions": 0,
            "evidence_requirements": 0,
            "conditions": 0,
        },
        "readiness_status": "ok",
        "readiness_issues": [],
        "policy_readiness": None,
        "normalization_draft": {"rule_candidates": {}, "draft_rule_candidates": []},
    }


class NormalizeAdvancesStatusTests(unittest.TestCase):
    def _run_normalize(self, result):
        doc = {"id": "d1", "company_id": "c1"}
        clauses = [{"id": "cl1"}]
        req = mock.MagicMock()
        req.state.request_id = "req-1"
        with mock.patch.object(m.db, "get_policy_document", return_value=doc), \
             mock.patch.object(m.db, "list_policy_document_clauses", return_value=clauses), \
             mock.patch.object(m, "_require_document_access", return_value=None), \
             mock.patch.object(m.db, "update_policy_document") as upd, \
             mock.patch.object(m, "_hr_publish_policy_version", return_value={"id": "ver-1"}), \
             mock.patch(
                 "backend.app.services.normalization_input."
                 "validate_and_prepare_normalization_input",
                 return_value=(doc, clauses, []),
             ), \
             mock.patch(
                 "backend.app.services.policy_normalization.run_normalization",
                 return_value=result,
             ):
            out = m.normalize_policy_document(
                doc_id="d1", req=req, user={"id": "u1", "role": "HR"}
            )
        return out, upd

    def test_not_publishable_still_advances_status(self):
        out, upd = self._run_normalize(_result(publishable=False))
        self.assertTrue(out["ok"])
        self.assertTrue(out["normalized"])
        upd.assert_called_once()
        self.assertEqual(upd.call_args.args[0], "d1")
        self.assertEqual(upd.call_args.kwargs.get("processing_status"), STATUS_NORMALIZED)

    def test_publishable_path_also_advances_status(self):
        out, upd = self._run_normalize(_result(publishable=True))
        self.assertTrue(out["ok"])
        self.assertTrue(out["published"])
        upd.assert_called_once()
        self.assertEqual(upd.call_args.kwargs.get("processing_status"), STATUS_NORMALIZED)


if __name__ == "__main__":
    unittest.main()
