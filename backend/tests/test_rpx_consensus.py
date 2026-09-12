"""Tests for the RPX-05 consensus merge + eval harness.

Technique provenance:
- Multi-pass / self-consistency + offline evaluation suites — Berryman & Ziegler,
  *Prompt Engineering for LLMs* (O'Reilly, 2025), ch. 9 (LLM Workflows) and ch. 10
  (Evaluating LLM Applications).
- Evaluation-driven development + guardrails — Chip Huyen, *AI Engineering* (O'Reilly, 2024).

The merge is deterministic and LLM-free: N independent research passes go in, a voted,
citation-gated set of candidate facts comes out. This is the authoring layer — it never
serves and never calls a model (it consumes pass files a worker produced).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.imports.otto.consensus import (  # noqa: E402
    ConsensusResult,
    evaluate_consensus,
    merge_passes,
)

# URLs whose classification is fixed by classify_source's own docstring examples.
OFFICIAL_URL = "https://www.service-public.gouv.fr/particuliers/F16003"
SEMI_URL = "https://www.campusfrance.org/en/fees"
UNOFFICIAL_URL = "https://some-relocation-blog.com/moving-to-france"


def fact(dc="NO", topic="udi_residence", key="udi_permit_fee",
         url=OFFICIAL_URL, quote="The application fee is NOK 6300.",
         text="The residence-permit application fee is NOK 6300."):
    return {
        "destination_country": dc,
        "entity_topic_key": topic,
        "fact_key": key,
        "fact_text": text,
        "source_url": url,
        "evidence_quote": quote,
    }


def passes_with(count, n, **kw):
    """`count` of `n` total passes contain the fact; the rest are empty passes."""
    return [[fact(**kw)] for _ in range(count)] + [[] for _ in range(n - count)]


class TestConsensusMerge(unittest.TestCase):
    def test_full_official_with_quote_is_consensus(self):
        r = merge_passes(passes_with(5, 5))
        assert len(r.consensus) == 1
        assert len(r.needs_review) == 0
        assert len(r.gaps) == 0
        assert r.consensus[0]["applies_to"]["pass_count"] == 5

    def test_semi_official_full_count_downgraded_to_needs_review(self):
        # 5/5 agreement is not enough if the publisher is only semi-official.
        r = merge_passes(passes_with(5, 5, url=SEMI_URL))
        assert len(r.consensus) == 0
        assert len(r.needs_review) == 1
        assert r.needs_review[0]["needs_lawyer_review"] is True

    def test_unofficial_is_always_a_gap(self):
        r = merge_passes(passes_with(5, 5, url=UNOFFICIAL_URL))
        assert len(r.consensus) == 0
        assert len(r.gaps) == 1
        assert "unofficial" in r.gaps[0]["reason"].lower()

    def test_middle_band_official_is_needs_review(self):
        r = merge_passes(passes_with(3, 5))
        assert len(r.consensus) == 0
        assert len(r.needs_review) == 1
        assert r.needs_review[0]["applies_to"]["pass_count"] == 3
        assert r.needs_review[0]["needs_lawyer_review"] is True

    def test_low_band_official_with_quote_is_included_as_needs_review(self):
        r = merge_passes(passes_with(2, 5))
        assert len(r.needs_review) == 1
        assert len(r.gaps) == 0

    def test_low_band_official_without_quote_is_dropped_to_gap(self):
        r = merge_passes(passes_with(2, 5, quote=""))
        assert len(r.needs_review) == 0
        assert len(r.gaps) == 1

    def test_low_band_semi_official_is_dropped_to_gap(self):
        r = merge_passes(passes_with(2, 5, url=SEMI_URL))
        assert len(r.gaps) == 1

    def test_distinct_facts_are_kept_separate(self):
        # Two genuinely different facts under one topic have different fact_text, so text
        # clustering keeps them apart even though the topic is shared.
        fee = "The residence-permit application fee is NOK 6300."
        deadline = "You must register with the police within three months of arrival."
        p = [
            [fact(topic="udi", key="fee", text=fee), fact(topic="udi", key="deadline", text=deadline)]
            for _ in range(5)
        ]
        r = merge_passes(p)
        assert len(r.consensus) == 2


class TestConsensusEval(unittest.TestCase):
    def test_eval_passes_on_clean_consensus(self):
        ev = evaluate_consensus(merge_passes(passes_with(5, 5)))
        assert ev["verdict"] == "PASS"
        assert ev["citation_coverage"] == 1.0
        assert ev["statutory_ratio"] == 1.0

    def test_eval_fails_if_a_consensus_row_violates_the_invariant(self):
        # A consensus row must be official + verbatim-cited. Plant a violation and the
        # eval must catch it — this is the regression guard on the merge itself.
        bad = ConsensusResult(
            consensus=[fact(url=UNOFFICIAL_URL)], needs_review=[], gaps=[], report={},
        )
        assert evaluate_consensus(bad)["verdict"] == "FAIL"


class TestNormalizationAndClustering(unittest.TestCase):
    """Independent passes drift both the topic key and the fact key for the same fact.
    The merge must resolve that (canonical topic + fact-text clustering) or consensus collapses.
    """

    def test_banque_france_is_official(self):
        from backend.imports.otto.parsers import OFFICIAL, classify_source
        assert classify_source(
            "https://www.banque-france.fr/fr/a-votre-service/particuliers/droit-au-compte-bancaire"
        ) == OFFICIAL

    def test_norwegian_statutory_bodies_are_official(self):
        # First live FR→NO run dropped a 5/5 driving-licence fact + schooling facts as "unofficial"
        # because these statutory bodies were missing from the allowlist.
        from backend.imports.otto.parsers import OFFICIAL, classify_source
        for url in (
            "https://www.vegvesen.no/en/driving-licences/",           # Statens vegvesen (roads)
            "https://www.udir.no/regelverk/",                          # Directorate for Education
            "https://www.regjeringen.no/en/topics/",                   # the Government
            "https://www.oslo.kommune.no/skole-og-utdanning/",         # Oslo municipality
            "https://www.bergen.kommune.no/",                          # any NO municipality (suffix)
        ):
            assert classify_source(url) == OFFICIAL, url

    def test_topic_alias_collapses_variants(self):
        # Same fact, same text, but the topic key drifted between passes.
        T = "An EU or EEA citizen is not required to hold a residence permit to live in France."
        p = [
            [fact(dc="FR", topic="eu_right_of_residence", key="a", text=T)],
            [fact(dc="FR", topic="right_of_residence", key="b", text=T)],
        ]
        r = merge_passes(p)
        assert len(r.consensus) == 1
        assert r.consensus[0]["applies_to"]["pass_count"] == 2

    def test_text_clustering_aligns_drifted_fact_keys(self):
        # The real failure mode: 5 passes, same topic, same fact, five different fact_keys.
        T = ("Anyone who works or resides in France in a stable and regular manner "
             "is entitled to health cover.")
        p = [[fact(dc="FR", topic="puma_health_cover", key=f"k{i}", text=T)] for i in range(5)]
        r = merge_passes(p)
        assert len(r.consensus) == 1
        assert r.consensus[0]["applies_to"]["pass_count"] == 5

    def test_distinct_subfacts_within_topic_stay_separate(self):
        entitlement = ("Anyone who works or resides in France in a stable and regular manner "
                       "is entitled to health cover.")
        six_month = ("To open health insurance rights based on residence a person must reside "
                     "at least six months per year in France.")
        p = [
            [fact(dc="FR", topic="puma_health_cover", key=f"e{i}", text=entitlement),
             fact(dc="FR", topic="puma_health_cover", key=f"s{i}", text=six_month)]
            for i in range(5)
        ]
        r = merge_passes(p)
        assert len(r.consensus) == 2


class TestEmbeddingClustering(unittest.TestCase):
    """Opt-in embedding path: merges the same fact across drifted topic keys + differing phrasing
    that deterministic token-Jaccard misses. embed_fn is injected (no network in tests)."""

    @staticmethod
    def _embed(mapping):
        return lambda texts: [mapping[t] for t in texts]

    # token-distinct texts, so the deterministic base separates them and the embedding-merge
    # (not token overlap) is what's actually under test.
    A = "alpha bravo charlie delta echo"
    B = "foxtrot golf hotel india juliet"

    def test_embedding_merges_across_topic_drift(self):
        # Same concept, DIFFERENT topic keys the alias map won't unify, low token overlap,
        # near-identical vectors → the embedding-merge should combine them into one 5/5 cluster.
        a = fact(dc="NO", topic="scheme_registration", key="k1", text=self.A)
        b = fact(dc="NO", topic="police_registration_eu", key="k2", text=self.B)
        embed = self._embed({self.A: [1.0, 0.0, 0.0], self.B: [0.98, 0.02, 0.0]})
        r = merge_passes([[a], [b]], embed_fn=embed, embed_threshold=0.9)
        assert len(r.consensus) == 1
        assert r.consensus[0]["applies_to"]["pass_count"] == 2
        # The deterministic path can't merge them (different topics, low token overlap):
        assert len(merge_passes([[a], [b]]).consensus) == 0

    def test_embedding_never_reduces_below_deterministic(self):
        # Orthogonal vectors → the embedding-merge must NOT combine distinct facts, and must not
        # fragment what deterministic grouped. This is the guarantee the augment design provides.
        a = fact(dc="NO", topic="t1", key="k1", text=self.A)
        b = fact(dc="NO", topic="t2", key="k2", text=self.B)
        embed = self._embed({self.A: [1.0, 0.0, 0.0], self.B: [0.0, 1.0, 0.0]})
        r = merge_passes([[a], [b]], embed_fn=embed, embed_threshold=0.86)
        assert len(r.consensus) == 0
        assert len(r.needs_review) == 2  # each 1/2, official+verbatim → low-band rescue

    def test_embedding_path_still_enforces_sourcing_gate(self):
        a = fact(dc="NO", text=self.A, url=UNOFFICIAL_URL)
        r = merge_passes([[a]], embed_fn=self._embed({self.A: [1.0, 0.0, 0.0]}))
        assert len(r.gaps) == 1
        assert "unofficial" in r.gaps[0]["reason"].lower()


if __name__ == "__main__":
    unittest.main()
