"""
I-3 Stage 1 — corridor registry + retrieval-scope wiring tests.

Covers the registry loader (normalization, real FR_NO profile, fallback-safety,
list_corridors) and the immigration_retriever seam (scope fills unset params;
caller-supplied params win; no profile → unchanged behaviour). sqlite + hash
embedder, no network.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ["POLICY_ASSISTANT_EMBEDDER"] = "hash"

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.app.services import corridor_registry as reg  # noqa: E402
from backend.app.services import immigration_retriever as ir  # noqa: E402
from backend.app.services.immigration_retriever import (  # noqa: E402
    PathClassification,
    UserProfile,
)
from backend.app.services.policy_assistant_embedder import HashEmbedder  # noqa: E402


# --------------------------------------------------------------------------- #
# Registry loader                                                             #
# --------------------------------------------------------------------------- #
class NormalizeTests(unittest.TestCase):
    def test_forms_canonicalize_to_underscore(self):
        for raw in ("FR→NO", "FR-NO", "fr_no", "fr no", "  FR→NO  ", "FR->NO"):
            self.assertEqual(reg.normalize_corridor_id(raw), "FR_NO")

    def test_empty(self):
        self.assertEqual(reg.normalize_corridor_id(""), "")


class RealFrNoProfileTests(unittest.TestCase):
    """Loads the committed corridors/FR_NO/corridor.yaml from the repo."""

    def setUp(self):
        reg._reset_cache_for_tests()

    def test_fr_no_profile_fields(self):
        p = reg.load_corridor_profile("FR→NO")   # arrow form normalizes to FR_NO
        self.assertIsNotNone(p)
        self.assertEqual(p.corridor_id, "FR_NO")
        self.assertEqual(p.origin_iso, "FR")
        self.assertEqual(p.destination_iso, "NO")
        self.assertIn("FR→NO", p.aliases)
        self.assertIsNotNone(p.retrieval)
        self.assertEqual(p.retrieval.trust_tiers, (1, 2, 3))
        self.assertEqual(p.retrieval.min_similarity, 0.25)

    def test_list_corridors_includes_fr_no(self):
        self.assertIn("FR_NO", reg.list_corridors())

    def test_unknown_corridor_is_none(self):
        self.assertIsNone(reg.load_corridor_profile("ZZ_YY"))
        self.assertIsNone(reg.get_retrieval_scope("ZZ_YY"))


class FallbackSafetyTests(unittest.TestCase):
    def setUp(self):
        reg._reset_cache_for_tests()
        self._prev = os.environ.get("CORRIDOR_REGISTRY_DIR")
        self.tmp = tempfile.mkdtemp()
        os.environ["CORRIDOR_REGISTRY_DIR"] = self.tmp

        def restore():
            reg._reset_cache_for_tests()
            if self._prev is None:
                os.environ.pop("CORRIDOR_REGISTRY_DIR", None)
            else:
                os.environ["CORRIDOR_REGISTRY_DIR"] = self._prev
        self.addCleanup(restore)

    def _write(self, cid, body):
        d = os.path.join(self.tmp, cid)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "corridor.yaml"), "w", encoding="utf-8") as f:
            f.write(body)

    def test_malformed_yaml_returns_none_not_raises(self):
        self._write("XX_YY", "corridor: [this: is: not valid")
        self.assertIsNone(reg.load_corridor_profile("XX_YY"))   # no raise

    def test_missing_retrieval_section_yields_none_scope(self):
        self._write("XX_YY", "corridor:\n  id: XX_YY\n  origin_iso: XX\n")
        p = reg.load_corridor_profile("XX_YY")
        self.assertIsNotNone(p)
        self.assertIsNone(p.retrieval)


# --------------------------------------------------------------------------- #
# Retriever seam                                                              #
# --------------------------------------------------------------------------- #
_SCHEMA = (
    "CREATE TABLE immigration_corpus_chunks ("
    "id TEXT PRIMARY KEY, corridor TEXT NOT NULL, source_doc_id TEXT, source_url TEXT NOT NULL, "
    "chunk_text TEXT NOT NULL, chunk_index INTEGER NOT NULL, chunk_metadata TEXT DEFAULT '{}', "
    "trust_tier INTEGER NOT NULL DEFAULT 2, fetched_at TEXT NOT NULL, embedding TEXT, "
    "content_hash TEXT NOT NULL, is_active INTEGER DEFAULT 1, created_at TEXT)"
)


def _seed_mixed_tiers():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    emb = HashEmbedder()
    with eng.begin() as c:
        c.execute(text(_SCHEMA))
        for tier in (1, 2, 3):
            cid = f"xy-tier{tier}"
            body = f"XX to YY immigration requirements rule tier {tier}"
            c.execute(text(
                "INSERT INTO immigration_corpus_chunks "
                "(id, corridor, source_url, chunk_text, chunk_index, chunk_metadata, trust_tier, "
                " fetched_at, embedding, content_hash, is_active) VALUES "
                "(:id,:cor,:u,:t,:i,:m,:tt,:f,:e,:h,1)"),
                {"id": cid, "cor": "XX_YY", "u": f"https://gov.example/{cid}", "t": body,
                 "i": 0, "m": json.dumps({"corridor": "XX_YY"}), "tt": tier,
                 "f": "2026-06-06T00:00:00+00:00", "e": json.dumps(emb.embed(body)), "h": cid})
    return eng


class RetrieverScopeWiringTests(unittest.TestCase):
    def setUp(self):
        reg._reset_cache_for_tests()
        self.engine = _seed_mixed_tiers()
        self._prev = os.environ.get("CORRIDOR_REGISTRY_DIR")
        self.tmp = tempfile.mkdtemp()
        os.environ["CORRIDOR_REGISTRY_DIR"] = self.tmp
        # A profile that restricts retrieval to official (tier 1) only.
        d = os.path.join(self.tmp, "XX_YY")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "corridor.yaml"), "w", encoding="utf-8") as f:
            f.write("corridor:\n  id: XX_YY\n  retrieval:\n    trust_tiers: [1]\n")

        def restore():
            reg._reset_cache_for_tests()
            if self._prev is None:
                os.environ.pop("CORRIDOR_REGISTRY_DIR", None)
            else:
                os.environ["CORRIDOR_REGISTRY_DIR"] = self._prev
        self.addCleanup(restore)

        self.profile = UserProfile(nationality="XX", origin_country="XX", destination_country="YY", is_eea=False)
        self.path = PathClassification(pathway_type="work_permit")

    def _tiers(self, **kw):
        chunks = ir.retrieve_for_profile(
            profile=self.profile, classification=self.path, engine=self.engine,
            min_similarity_score=0.0, top_k=10, **kw,
        )
        return sorted({c["trust_tier"] for c in chunks})

    def test_scope_restricts_tiers_when_caller_unset(self):
        # Caller passes no trust_tiers → registry scope [1] applies.
        self.assertEqual(self._tiers(), [1])

    def test_caller_supplied_tiers_win_over_scope(self):
        # Explicit trust_tiers beat the registry (caller precedence).
        self.assertEqual(self._tiers(trust_tiers=[1, 2, 3]), [1, 2, 3])

    def test_no_profile_means_unchanged_all_tiers(self):
        # A corridor with no profile → all tiers (current default behaviour).
        os.environ["CORRIDOR_REGISTRY_DIR"] = tempfile.mkdtemp()  # empty registry
        reg._reset_cache_for_tests()
        self.assertEqual(self._tiers(), [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
