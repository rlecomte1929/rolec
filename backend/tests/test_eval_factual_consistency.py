"""
Tests for the P3-01c factual-consistency evaluator (AIQ-709 / FU1).

Three layers, all deterministic (no network, no API key):
  * FactualVerifierAdapter mapping — the real P1-01c `verify_step` driven by a
    MockClient, asserting StepVerdict → VerificationVerdict translation.
  * evaluate() control flow — stub retriever + stub verifier proving the
    skip-when-no-generated-step logic, the 1.0/0.0 metric, and flagged steps.
  * End-to-end smoke — seed in-memory chunks, run the real retriever adapter +
    the verifier adapter (MockClient) through evaluate(), and aggregate_report.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ["POLICY_ASSISTANT_EMBEDDER"] = "hash"
os.environ["POLICY_ASSISTANT_LLM"] = "mock"

_SCRIPTS = os.path.join(_REPO_ROOT, "backend", "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from backend.app.services import immigration_retriever  # noqa: E402
from backend.app.services.policy_assistant_embedder import HashEmbedder  # noqa: E402
from backend.app.services.policy_assistant_llm_client import MockClient  # noqa: E402

import eval_factual_consistency as efc  # noqa: E402
from rag_eval_harness import GoldenQuery, QueryResult, RetrievedChunk, VerificationVerdict  # noqa: E402


def _gq(query_id, corridor="IN->DE", intent="document_requirements", expected=None):
    return GoldenQuery(
        query_id=query_id,
        corridor=corridor,
        intent_category=intent,
        query_text="q?",
        expected_chunk_ids=expected or ["c1"],
        difficulty="easy",
        extra={"profile": {
            "nationality": "IN", "destination": "DE",
            "intent": "salaried_employment", "qualification_level": "master_or_higher",
            "salary_eur_annual": 60000, "occupation_category": "general",
        }},
    )


# ---------------------------------------------------------------------------
# FactualVerifierAdapter — StepVerdict → VerificationVerdict
# ---------------------------------------------------------------------------


class FactualVerifierAdapterTests(unittest.TestCase):
    def test_supported_step_maps_to_supported_verdict(self):
        # MockClient (keyed on the step text) returns a supported verdict that
        # cites a real retrieved chunk id.
        client = MockClient(responses_by_pattern={
            "step about passports": json.dumps(
                {"supported": True, "evidence_chunk_ids": ["c1"], "reason": "ok"}
            ),
        })
        adapter = efc.FactualVerifierAdapter(client=client)
        verdict = adapter.verify(
            "step about passports",
            [RetrievedChunk(chunk_id="c1", score=0.9, text="passport rule")],
        )
        self.assertIsInstance(verdict, VerificationVerdict)
        self.assertTrue(verdict.supported)
        self.assertEqual(verdict.confidence, 1.0)
        self.assertEqual(verdict.unsupported_claims, [])

    def test_unsupported_step_records_the_claim(self):
        # No retrieved sources → verify_step short-circuits to unsupported with
        # no LLM call; the adapter flags the generated step as unsupported.
        client = MockClient()
        adapter = efc.FactualVerifierAdapter(client=client)
        verdict = adapter.verify("hallucinated step", [])
        self.assertFalse(verdict.supported)
        self.assertEqual(verdict.confidence, 0.0)
        self.assertEqual(verdict.unsupported_claims, ["hallucinated step"])
        self.assertEqual(client.calls, [])  # short-circuit, no tokens spent


# ---------------------------------------------------------------------------
# evaluate() — skip logic, metric, flagged steps
# ---------------------------------------------------------------------------


class _StubRetriever:
    def set_current_query(self, q):
        self._q = q

    def retrieve(self, query, k=5):
        return [RetrievedChunk(chunk_id="c1", score=1.0, text="src")]


class _StubVerifier:
    """Supported iff the generated step contains 'good'."""

    def verify(self, generated_step, retrieved_sources):
        ok = "good" in generated_step
        return VerificationVerdict(
            supported=ok,
            confidence=1.0 if ok else 0.0,
            rationale="stub-ok" if ok else "stub-unsupported",
            unsupported_claims=[] if ok else [generated_step],
        )


class EvaluateTests(unittest.TestCase):
    def test_skips_queries_without_a_generated_step(self):
        queries = [_gq("Q1"), _gq("Q2"), _gq("Q3")]
        generated = {"Q1": "a good step", "Q3": "a bad step"}  # Q2 has none
        results, skipped = efc.evaluate(
            queries, _StubRetriever(), _StubVerifier(), generated, k=5
        )
        self.assertEqual(skipped, 1)  # Q2
        self.assertEqual({r.query.query_id for r in results}, {"Q1", "Q3"})

    def test_supported_scores_one_unsupported_scores_zero(self):
        queries = [_gq("Q1"), _gq("Q3")]
        generated = {"Q1": "a good step", "Q3": "a bad step"}
        results, _ = efc.evaluate(queries, _StubRetriever(), _StubVerifier(), generated, k=5)
        by_id = {r.query.query_id: r for r in results}
        self.assertEqual(by_id["Q1"].metrics["factual_consistency"], 1.0)
        self.assertEqual(by_id["Q3"].metrics["factual_consistency"], 0.0)

    def test_flagged_steps_capture_unsupported_only(self):
        queries = [_gq("Q1"), _gq("Q3")]
        generated = {"Q1": "a good step", "Q3": "a bad step"}
        results, _ = efc.evaluate(queries, _StubRetriever(), _StubVerifier(), generated, k=5)
        flagged = efc.build_flagged_steps(results, generated)
        self.assertEqual(len(flagged), 1)
        self.assertEqual(flagged[0]["query_id"], "Q3")
        self.assertEqual(flagged[0]["generated_step"], "a bad step")
        self.assertEqual(flagged[0]["rationale"], "stub-unsupported")


# ---------------------------------------------------------------------------
# End-to-end smoke — real retriever adapter + verifier adapter (MockClient)
# ---------------------------------------------------------------------------


# N2/AIQ-841 (#420): immigration rules moved to a dedicated immigration_corpus_chunks
# table (corridor-scoped, underscore corridor form), read via immigration_retriever.db.
# This fixture mirrors the one in test_eval_rag_context_precision.py, which drives the
# same retriever adapter. (Before this, the test seeded the old policy_assistant_chunks
# and patched policy_chunk_retriever.db, so the retriever read an empty table and the
# step came back ungrounded → factual_consistency 0.0 — UIAUDIT-G16.)
_SCHEMA = """
CREATE TABLE immigration_corpus_chunks (
    id TEXT PRIMARY KEY,
    corridor TEXT NOT NULL,
    source_doc_id TEXT,
    source_url TEXT NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    chunk_metadata TEXT DEFAULT '{}',
    trust_tier INTEGER NOT NULL DEFAULT 2,
    fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    embedding TEXT,
    content_hash TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TEXT
);
"""


class _FakeDb:
    def __init__(self, engine):
        self.engine = engine


class FactualConsistencyIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in _SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))
        emb = HashEmbedder()
        with self.engine.begin() as conn:
            # Corridor stored in underscore form; the retriever normalizes arrow -> underscore.
            meta = json.dumps({"corridor": "IN_DE", "pathway_type": "blue_card"})
            # The retrieval query is synthesized from the profile (immigration_retriever
            # ._build_query), NOT query_text — so the chunk BODIES must overlap it enough
            # to clear the N3 similarity floor (IMMIGRATION_MIN_SIMILARITY=0.25) under
            # HashEmbedder. Short bodies score below the floor and the retriever returns
            # nothing (the original UIAUDIT-G16 failure). Mirror the floor-clearing body
            # style from test_eval_rag_context_precision.py.
            for cid in ("in_de_bc_passport", "in_de_bc_degree"):
                body = f"India Germany Blue Card chunk {cid} passport degree contract"
                conn.execute(
                    text(
                        "INSERT INTO immigration_corpus_chunks "
                        "(id, corridor, source_url, chunk_text, chunk_index, chunk_metadata, "
                        " trust_tier, fetched_at, embedding, content_hash, is_active) "
                        "VALUES (:id, :cor, :ref, :body, 0, :meta, 1, :f, :emb, :h, 1)"
                    ),
                    {
                        "id": cid,
                        "cor": "IN_DE",
                        "ref": f"https://gov.example/immigration_rule/{cid}",
                        "body": body,
                        "meta": meta,
                        "f": "2026-06-06T00:00:00+00:00",
                        "emb": json.dumps(emb.embed(body)),
                        "h": cid,
                    },
                )
        self._patch = mock.patch.object(immigration_retriever, "db", _FakeDb(self.engine))
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def test_end_to_end_evaluate_and_report(self):
        q = _gq("Q-INDE-001", expected=["in_de_bc_passport", "in_de_bc_degree"])
        generated = {"Q-INDE-001": "Provide your passport for the Blue Card application."}
        # MockClient returns a supported verdict citing a seeded chunk id.
        client = MockClient(responses_by_pattern={
            "passport": json.dumps(
                {"supported": True, "evidence_chunk_ids": ["in_de_bc_passport"], "reason": "grounded"}
            ),
        })
        retriever = efc.ImmigrationRetrieverAdapter()
        verifier = efc.FactualVerifierAdapter(client=client)
        results, skipped = efc.evaluate([q], retriever, verifier, generated, k=5)

        self.assertEqual(skipped, 0)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].metrics["factual_consistency"], 1.0)

        from rag_eval_harness import aggregate_report
        report = aggregate_report(results, metric_name="factual_consistency", threshold=0.95)
        self.assertEqual(report["aggregate"], 1.0)
        self.assertTrue(report["passes_threshold"])
        self.assertIn("IN->DE", report["by_corridor"])

    def test_cli_main_writes_report_and_ci_gate_passes_at_zero_threshold(self):
        """Drive the full CLI against the real fixtures + a sidecar, under the
        seeded DB (criteria 2 + 4). The chosen query has no matching seeded
        corpus → unsupported → aggregate 0.0, so --threshold 0.0 exits 0."""
        import tempfile

        qpath = os.path.join(_REPO_ROOT, "backend", "tests", "fixtures", "rag_eval", "queries.jsonl")
        with open(qpath, encoding="utf-8") as f:
            first_qid = next(
                json.loads(line)["query_id"]
                for line in f
                if line.strip() and '"query_id"' in line
            )
        with tempfile.TemporaryDirectory() as d:
            side = os.path.join(d, "gen.json")
            with open(side, "w", encoding="utf-8") as f:
                json.dump({first_qid: "A generated immigration step."}, f)
            out = os.path.join(d, "report.json")

            efc.main(["--queries", qpath, "--generated-steps", side, "--out", out, "--k", "5"])
            self.assertTrue(os.path.exists(out))
            report = json.load(open(out, encoding="utf-8"))
            self.assertEqual(report["metric"], "factual_consistency")
            self.assertIn("flagged_steps_sample", report["extra"])

            with self.assertRaises(SystemExit) as ctx:
                efc.main([
                    "--queries", qpath, "--generated-steps", side,
                    "--out", out, "--ci", "--threshold", "0.0",
                ])
            self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
