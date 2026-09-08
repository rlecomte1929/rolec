"""
W2-5 answer-provenance instrumentation tests.

Covers:
  - Policy-assistant pipeline runs grounding on real answers (not refusals) and
    surfaces the verdict in the return dict.
  - flush() hoists answer_kind / grounding_verdict / verification_skipped /
    grounding_score out of step payloads into top-level trace columns (covers
    both the policy step names and the immigration `grounding_verification` step).
  - db.get_answer_provenance_rollup aggregates per company.
  - GET /api/hr/answer-provenance returns the rollup, scopes to the caller's
    company (no cross-tenant leak), and 403s without company context.

All LLM calls go through MockClient + a stubbed verifier — no API key needed.
"""
from __future__ import annotations

import os
import sys
import unittest
from typing import Any, Dict
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ["POLICY_ASSISTANT_LLM"] = "mock"
os.environ["POLICY_ASSISTANT_EMBEDDER"] = "hash"
os.environ["RELOPASS_DISABLE_RATE_LIMITS"] = "1"
os.environ["RELOPASS_QUERY_COUNTER_OFF"] = "1"

from backend.app.services import (  # noqa: E402
    policy_assistant_rag_engine as rag,
    policy_assistant_session_memory as session_memory,
    policy_chunk_retriever,
)
from backend.app.services.ai_trace_logger import TraceSession  # noqa: E402
from backend.app.services.policy_assistant_llm_client import MockClient  # noqa: E402


_GROUNDED = {
    "verdict": "grounded",
    "grounding_score": 0.95,
    "unsupported_claims": [],
    "verification_skipped": False,
    "latency_ms": 7,
}


class _StubAuditDb:
    def policy_hardening_tables_available(self):
        return False


# --------------------------------------------------------------------------- #
# 1. Engine wires grounding into the answer path                              #
# --------------------------------------------------------------------------- #
class EngineGroundingWiringTests(unittest.TestCase):
    def setUp(self):
        session_memory._reset_all_for_tests()
        self._retrieve_patcher = mock.patch.object(
            policy_chunk_retriever, "retrieve",
            return_value=[
                {"id": "ch-1", "source_type": "matrix_benefit",
                 "source_ref": "policy_config_benefits.b1",
                 "chunk_text": "Housing allowance: USD 4,500 per month."},
            ],
        )
        self._retrieve_patcher.start()
        self.addCleanup(self._retrieve_patcher.stop)
        self._db_patcher = mock.patch.object(rag, "db", _StubAuditDb())
        self._db_patcher.start()
        self.addCleanup(self._db_patcher.stop)

        # Capture the payload that reaches the DB writer (post-hoist).
        self.captured: Dict[str, Any] = {}

        def _cap(payload, company_id):
            self.captured = dict(payload)

        self._write_patcher = mock.patch(
            "backend.app.services.ai_trace_logger._write_to_db", side_effect=_cap
        )
        self._write_patcher.start()
        self.addCleanup(self._write_patcher.stop)

    def test_grounding_runs_on_answer_and_is_hoisted(self):
        with mock.patch.object(rag, "verify_grounding", return_value=_GROUNDED) as vg:
            client = MockClient(responses_by_pattern={
                "housing": "Housing allowance is USD 4,500/month [chunk:ch-1].",
            })
            result = rag.answer_policy_question(
                company_id="co-a", user_id="u-1",
                question="What's the housing allowance?",
                client=client,
            )
        vg.assert_called_once()
        # Return dict carries provenance.
        self.assertEqual(result["answer_kind"], "answer")
        self.assertEqual(result["grounding_verdict"], "grounded")
        self.assertEqual(result["grounding_score"], 0.95)
        self.assertFalse(result["verification_skipped"])
        # Hoisted onto the trace row.
        self.assertEqual(self.captured.get("answer_kind"), "answer")
        self.assertEqual(self.captured.get("grounding_verdict"), "grounded")
        self.assertEqual(self.captured.get("grounding_score"), 0.95)
        self.assertEqual(self.captured.get("verification_skipped"), False)

    def test_grounding_skipped_on_refusal(self):
        with mock.patch.object(rag, "verify_grounding") as vg:
            client = MockClient(responses_by_pattern={})  # → canonical refusal
            result = rag.answer_policy_question(
                company_id="co-a", user_id="u-1",
                question="What's the weather in Tokyo?",
                client=client,
            )
        vg.assert_not_called()
        self.assertEqual(result["answer_kind"], "refusal_out_of_policy")
        self.assertIsNone(result["grounding_verdict"])
        # answer_kind still hoisted; grounding columns stay absent (→ NULL).
        self.assertEqual(self.captured.get("answer_kind"), "refusal_out_of_policy")
        self.assertNotIn("grounding_verdict", self.captured)


# --------------------------------------------------------------------------- #
# 2. flush() hoist logic                                                      #
# --------------------------------------------------------------------------- #
class HoistProvenanceTests(unittest.TestCase):
    def _flush_capture(self, record):
        captured: Dict[str, Any] = {}

        def _cap(payload, company_id):
            captured.update(payload)

        tracer = TraceSession(
            session_id="s", query="q", company_id="co-a", feature_key="policy_assistant"
        )
        record(tracer)
        with mock.patch(
            "backend.app.services.ai_trace_logger._write_to_db", side_effect=_cap
        ), mock.patch(
            "backend.app.services.ai_trace_logger._forward_to_langsmith"
        ):
            tracer.flush()
        return captured

    def test_policy_steps_hoisted(self):
        def rec(t):
            t.record_step("answer_provenance", latency_ms=0, answer_kind="answer")
            t.record_step(
                "grounding_verification", latency_ms=3,
                grounding_verdict="partially_grounded",
                grounding_score=0.6, verification_skipped=False,
            )
        cap = self._flush_capture(rec)
        self.assertEqual(cap["answer_kind"], "answer")
        self.assertEqual(cap["grounding_verdict"], "partially_grounded")
        self.assertEqual(cap["grounding_score"], 0.6)
        self.assertEqual(cap["verification_skipped"], False)

    def test_immigration_grounding_step_hoisted(self):
        # Immigration records only the grounding_verification step (no
        # answer_provenance step) — the same hoist must still capture it.
        def rec(t):
            t.record_step(
                "grounding_verification", latency_ms=4,
                grounding_verdict="grounded", grounding_score=1.0,
                verification_skipped=False,
            )
        cap = self._flush_capture(rec)
        self.assertEqual(cap["grounding_verdict"], "grounded")
        self.assertNotIn("answer_kind", cap)

    def test_no_provenance_steps_leaves_columns_absent(self):
        cap = self._flush_capture(lambda t: t.record_step("retrieval", latency_ms=1, chunk_count=3))
        for k in ("answer_kind", "grounding_verdict", "verification_skipped", "grounding_score"):
            self.assertNotIn(k, cap)


# --------------------------------------------------------------------------- #
# 3. Rollup SQL against a REAL sqlite engine                                   #
# --------------------------------------------------------------------------- #
# The root conftest replaces backend.database with a MagicMock so unit tests
# never open a live DB. To exercise the real aggregation SQL we temporarily
# swap the real module back in (restored in tearDownClass), which gives us the
# default sqlite engine + the real insert/rollup methods + the new columns.
class RollupSqlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib

        cls._mock_module = sys.modules.pop("backend.database", None)
        cls._real = importlib.import_module("backend.database")
        cls.db = cls._real.db
        cls.db.init_db()

        def seed(cid, n, **cols):
            for i in range(n):
                cls.db.insert_policy_assistant_trace(
                    trace_id=f"{cid}-{cols.get('answer_kind')}-{cols.get('grounding_verdict')}-{i}",
                    session_id=None, query_hash="qh", company_id=cid,
                    steps_json="[]", total_latency_ms=10, fallback_triggered=False,
                    feature_key="policy_assistant", **cols,
                )

        # company-a: 2 grounded answers, 1 unverified answer, 1 refusal.
        seed("w25-co-a", 2, answer_kind="answer", grounding_verdict="grounded",
             verification_skipped=False, grounding_score=0.9)
        seed("w25-co-a", 1, answer_kind="answer", grounding_verdict=None,
             verification_skipped=True, grounding_score=None)
        seed("w25-co-a", 1, answer_kind="refusal_out_of_policy")
        # company-b: 1 answer that must NOT leak into company-a's rollup.
        seed("w25-co-b", 1, answer_kind="answer", grounding_verdict="grounded",
             verification_skipped=False, grounding_score=1.0)

    @classmethod
    def tearDownClass(cls):
        # Restore the conftest mock so later unit-test modules don't hit a live DB.
        if cls._mock_module is not None:
            sys.modules["backend.database"] = cls._mock_module

    def test_rollup_counts_and_rates_scoped_to_company(self):
        r = self.db.get_answer_provenance_rollup(company_id="w25-co-a")
        self.assertEqual(r["total"], 4)        # company-b excluded
        self.assertEqual(r["answers"], 3)
        self.assertEqual(r["refusals"], 1)
        self.assertEqual(r["grounded"], 2)
        self.assertEqual(r["unverified_count"], 1)
        self.assertEqual(r["refusal_rate"], round(1 / 4, 4))
        self.assertEqual(r["grounded_rate"], round(2 / 3, 4))  # grounded / answered

    def test_rollup_empty_company_is_zeroed(self):
        r = self.db.get_answer_provenance_rollup(company_id="w25-nobody")
        self.assertEqual(r["total"], 0)
        self.assertEqual(r["grounded_rate"], 0.0)


# --------------------------------------------------------------------------- #
# 4. HR endpoint glue (app-mounted; db layer mocked per suite convention)     #
# --------------------------------------------------------------------------- #
class ProvenanceEndpointTests(unittest.TestCase):
    _CANNED = {
        "total": 4, "answers": 3, "refusals": 1, "grounded": 2,
        "partially_grounded": 0, "ungrounded": 1, "unverified": 1,
        "refusal_rate": 0.25, "grounded_rate": 0.6667, "unverified_count": 1,
    }

    def _client(self, org_id):
        from fastapi.testclient import TestClient
        from backend.main import app
        import backend.app.auth_deps as auth_deps

        app.dependency_overrides[auth_deps.get_org_id_for_hr_user] = lambda: org_id
        self.addCleanup(app.dependency_overrides.clear)
        return TestClient(app, raise_server_exceptions=False)

    def test_endpoint_maps_rollup_and_scopes_to_caller(self):
        from backend.app.routers import hr_analytics
        with mock.patch.object(
            hr_analytics.main_db, "get_answer_provenance_rollup",
            return_value=dict(self._CANNED),
        ) as rollup:
            c = self._client("w25-co-a")
            resp = c.get("/api/hr/answer-provenance?window_days=365")
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["total"], 4)
        self.assertEqual(body["grounded"], 2)
        self.assertEqual(body["unverified_count"], 1)
        self.assertEqual(body["window_days"], 365)
        # Rollup queried for the caller's company only.
        self.assertEqual(rollup.call_args.kwargs["company_id"], "w25-co-a")

    def test_endpoint_403_without_company(self):
        c = self._client("")  # no resolvable company context
        resp = c.get("/api/hr/answer-provenance")
        self.assertEqual(resp.status_code, 403, resp.text)


if __name__ == "__main__":
    unittest.main()
