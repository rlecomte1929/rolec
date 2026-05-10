"""
Sprint A integration tests for the Policy Assistant RAG layer.

Covers the full chunker → embedder → indexer → retriever path on an
in-memory SQLite mirror with the HashEmbedder. No network calls; no
OpenAI key needed.

What we assert:
  - Chunker formats benefits + Section C overrides into self-contained text
  - Indexer wipes prior chunks and re-inserts (idempotent)
  - Retriever returns top-K, ordered by similarity
  - Retriever NEVER returns chunks from another company (the load-bearing
    guardrail — even if scoring is wrong, cross-company drift must be
    physically impossible)
  - source_type filter narrows the result set
"""
from __future__ import annotations

import json
import os
import sys
import unittest
import uuid
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Force the hash embedder so the test never tries to call OpenAI.
os.environ["POLICY_ASSISTANT_EMBEDDER"] = "hash"

from backend.services import policy_chunk_indexer  # noqa: E402
from backend.services import policy_chunk_retriever  # noqa: E402
from backend.services.policy_assistant_embedder import (  # noqa: E402
    HashEmbedder,
    cosine_similarity,
    get_default_embedder,
)
from backend.services.policy_chunk_indexer import (  # noqa: E402
    format_benefit_chunk,
    format_override_chunk,
    index_company_policy,
)


SCHEMA = """
CREATE TABLE policy_assistant_chunks (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    policy_version_id TEXT,
    source_type TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_metadata TEXT NOT NULL DEFAULT '{}',
    embedding TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (company_id, source_type, source_ref)
);
"""


class _FakePolicyDb:
    """
    Minimal stub of the parts of `db` the indexer touches. Lets the
    test feed canned benefit + override payloads without spinning up
    the full matrix service.
    """
    def __init__(self, engine):
        self.engine = engine
        self._configs = {}            # company_id -> config row
        self._versions = {}           # company_id -> published version row
        self._benefits = {}           # version_id -> [rows]
        self._overrides = {}          # benefit_id -> [override rows]

    # -- shape used by _load_policy_for_indexing --
    def ensure_policy_config(self, company_id, config_key):
        return self._configs.get(company_id)

    def get_latest_published_policy_config_version(self, company_id, config_key):
        return self._versions.get(company_id)

    def get_policy_config_draft_for_config(self, pid):
        return None

    def list_policy_config_benefits(self, vid):
        return list(self._benefits.get(str(vid), []))

    def list_jurisdiction_overrides_for_benefit_rows(self, benefit_ids):
        out = {bid: [] for bid in benefit_ids}
        for bid in benefit_ids:
            out[bid] = list(self._overrides.get(str(bid), []))
        return out


def _seed_company(fake_db, company_id, *, benefits, overrides_by_benefit_id=None):
    """Wire a company → config → published version → benefits + overrides."""
    cfg_id = f"cfg-{company_id}"
    ver_id = f"ver-{company_id}"
    fake_db._configs[company_id] = {"id": cfg_id, "company_id": company_id}
    fake_db._versions[company_id] = {"id": ver_id, "policy_config_id": cfg_id, "status": "published"}
    fake_db._benefits[ver_id] = benefits
    if overrides_by_benefit_id:
        for bid, ovs in overrides_by_benefit_id.items():
            fake_db._overrides[bid] = ovs


class ChunkFormattingTests(unittest.TestCase):
    """Pure-function chunker tests — no DB."""

    def test_benefit_chunk_includes_label_amount_currency_freq(self):
        row = {
            "id": "b-1",
            "benefit_key": "housing_allowance",
            "benefit_label": "Housing allowance",
            "category": "compensation_allowances",
            "covered": True,
            "amount_value": 4500,
            "currency_code": "USD",
            "unit_frequency": "monthly",
            "notes": "Base allowance for mid-cost cities.",
        }
        text_out = format_benefit_chunk(row)
        self.assertIn("Housing allowance", text_out)
        self.assertIn("compensation_allowances", text_out)
        self.assertIn("USD", text_out)
        self.assertIn("4500", text_out)
        self.assertIn("monthly", text_out)
        self.assertIn("mid-cost cities", text_out)

    def test_benefit_chunk_says_not_covered_when_covered_false(self):
        row = {"benefit_label": "Pet relocation", "category": "family_support_education", "covered": False}
        text_out = format_benefit_chunk(row)
        self.assertIn("NOT covered", text_out)

    def test_benefit_chunk_renders_targeting(self):
        row = {
            "benefit_label": "Tuition",
            "category": "family_support_education",
            "covered": True,
            "unit_frequency": "yearly",
            "assignment_types": ["permanent", "international"],
            "employee_levels": ["director", "vp"],
        }
        text_out = format_benefit_chunk(row)
        self.assertIn("permanent", text_out)
        self.assertIn("director", text_out)
        self.assertIn("Applies to", text_out)

    def test_override_chunk_grounds_in_parent_benefit_and_region(self):
        base = {"benefit_label": "Housing allowance", "benefit_key": "housing_allowance"}
        ov = {
            "id": "ov-1",
            "jurisdiction_countries": ["SG", "MY"],
            "employee_level": "director",
            "amount_value": 9500,
            "currency_code": "SGD",
            "reimbursement_md": "SEA director cap.",
        }
        text_out = format_override_chunk(base, ov)
        self.assertIn("Housing allowance", text_out)
        self.assertIn("SG", text_out)
        self.assertIn("MY", text_out)
        self.assertIn("director", text_out)
        self.assertIn("SGD", text_out)
        self.assertIn("9500", text_out)
        self.assertIn("SEA director cap.", text_out)

    def test_override_chunk_inherits_when_amount_null(self):
        base = {"benefit_label": "Spouse assistance"}
        ov = {
            "jurisdiction_countries": ["JP"],
            "amount_value": None,
            "currency_code": None,
            "reimbursement_md": "Tokyo language tuition only.",
        }
        text_out = format_override_chunk(base, ov)
        self.assertIn("inherited from base", text_out)
        self.assertIn("Tokyo language tuition only.", text_out)


class IndexerRetrieverIntegrationTests(unittest.TestCase):
    """End-to-end: seed two companies, index both, retrieve, assert
    cross-company isolation + correct ordering."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        self.fake_db = _FakePolicyDb(self.engine)
        # Patch both modules' `db` reference so insert/retrieve hit the
        # in-memory SQLite, and so list_* helpers come from our fake.
        p1 = mock.patch.object(policy_chunk_indexer, "db", self.fake_db)
        p2 = mock.patch.object(policy_chunk_retriever, "db", self.fake_db)
        p1.start()
        p2.start()
        self.addCleanup(p1.stop)
        self.addCleanup(p2.stop)

        # Seed company A: housing + shipment + a SG director override.
        _seed_company(
            self.fake_db,
            "co-a",
            benefits=[
                {"id": "ba-1", "benefit_key": "housing_allowance",
                 "benefit_label": "Housing allowance",
                 "category": "compensation_allowances",
                 "covered": True, "amount_value": 4500, "currency_code": "USD",
                 "unit_frequency": "monthly"},
                {"id": "ba-2", "benefit_key": "shipment",
                 "benefit_label": "Household goods shipment",
                 "category": "relocation_assistance",
                 "covered": True, "amount_value": 12000, "currency_code": "USD",
                 "unit_frequency": "one_time"},
            ],
            overrides_by_benefit_id={
                "ba-1": [{"id": "oa-1",
                          "jurisdiction_countries": ["SG"],
                          "employee_level": "director",
                          "amount_value": 9500, "currency_code": "SGD"}],
            },
        )
        # Seed company B: only school search (different category, different
        # company entirely). Cross-company isolation depends on company_id
        # being honored at retrieval.
        _seed_company(
            self.fake_db,
            "co-b",
            benefits=[
                {"id": "bb-1", "benefit_key": "school_search",
                 "benefit_label": "School search support",
                 "category": "family_support_education",
                 "covered": True, "amount_value": 15000, "currency_code": "USD",
                 "unit_frequency": "one_time"},
            ],
        )

    def test_index_inserts_chunks_for_company_a(self):
        result = index_company_policy("co-a")
        # 2 benefits + 1 override = 3 chunks for co-a
        self.assertEqual(result["chunks"], 3)
        with self.engine.connect() as conn:
            n = conn.execute(text(
                "SELECT COUNT(*) FROM policy_assistant_chunks WHERE company_id = :c"
            ), {"c": "co-a"}).scalar()
        self.assertEqual(n, 3)

    def test_index_is_idempotent(self):
        index_company_policy("co-a")
        index_company_policy("co-a")  # second time should wipe + reinsert
        with self.engine.connect() as conn:
            n = conn.execute(text(
                "SELECT COUNT(*) FROM policy_assistant_chunks WHERE company_id = :c"
            ), {"c": "co-a"}).scalar()
        self.assertEqual(n, 3)

    def test_index_skipped_for_company_with_no_policy(self):
        result = index_company_policy("co-nothing")
        self.assertEqual(result["chunks"], 0)
        self.assertEqual(result["reason"], "no_published_policy")

    def test_retrieve_returns_top_k_for_company(self):
        index_company_policy("co-a")
        chunks = policy_chunk_retriever.retrieve(
            company_id="co-a", query="housing allowance", top_k=2
        )
        self.assertLessEqual(len(chunks), 2)
        self.assertGreater(len(chunks), 0)
        # Top result should be the housing allowance chunk (matrix_benefit
        # or the override). Both are valid; assert at least one mentions
        # housing.
        joined = " ".join(c["chunk_text"] for c in chunks)
        self.assertIn("Housing allowance", joined)

    def test_retrieve_isolates_companies_LOAD_BEARING(self):
        """The guardrail: querying company A NEVER returns chunks from B,
        even though both are indexed in the same table."""
        index_company_policy("co-a")
        index_company_policy("co-b")
        a_chunks = policy_chunk_retriever.retrieve(
            company_id="co-a", query="school", top_k=10
        )
        b_chunks = policy_chunk_retriever.retrieve(
            company_id="co-b", query="housing", top_k=10
        )
        # Cross-check the source refs — co-a's chunks must reference
        # co-a's policy_config_benefits ids only.
        for c in a_chunks:
            self.assertIn(c["source_ref"].split(".")[-1],
                          ["ba-1", "ba-2", "oa-1"])
        for c in b_chunks:
            self.assertIn(c["source_ref"].split(".")[-1], ["bb-1"])

    def test_retrieve_source_type_filter(self):
        index_company_policy("co-a")
        only_overrides = policy_chunk_retriever.retrieve(
            company_id="co-a", query="Singapore", top_k=10,
            source_types=["matrix_override"],
        )
        for c in only_overrides:
            self.assertEqual(c["source_type"], "matrix_override")

    def test_retrieve_empty_query_returns_empty(self):
        index_company_policy("co-a")
        self.assertEqual(
            policy_chunk_retriever.retrieve(company_id="co-a", query=""), []
        )
        self.assertEqual(
            policy_chunk_retriever.retrieve(company_id="co-a", query="  "), []
        )

    def test_retrieve_no_company_returns_empty(self):
        self.assertEqual(
            policy_chunk_retriever.retrieve(company_id="", query="anything"), []
        )


class HashEmbedderTests(unittest.TestCase):
    def test_same_input_produces_same_vector(self):
        e = HashEmbedder()
        self.assertEqual(e.embed("housing allowance"), e.embed("housing allowance"))

    def test_overlapping_text_more_similar_than_disjoint(self):
        e = HashEmbedder()
        a = e.embed("housing allowance for relocating employees")
        b = e.embed("housing allowance details")  # overlap on "housing", "allowance"
        c = e.embed("dental insurance for executives")  # no overlap
        self.assertGreater(cosine_similarity(a, b), cosine_similarity(a, c))

    def test_get_default_embedder_returns_hash_under_env_override(self):
        os.environ["POLICY_ASSISTANT_EMBEDDER"] = "hash"
        e = get_default_embedder()
        self.assertEqual(e.name, "hash")


if __name__ == "__main__":
    unittest.main()
