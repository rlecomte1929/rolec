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


if __name__ == "__main__":
    unittest.main()
