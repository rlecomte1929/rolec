"""Regression guards for the governed fact dictionary (form-fill integration, Build B spine).

The registry in ``backend.app.services.fact_dictionary`` is the join key that ties corridor
content, form field mappings, and case values together, and it carries the consult-professional
firewall. These tests lock its invariants so the spine can't silently regress as it grows.

DB-free and LLM-free (reads the module only). See docs/plans/form-fill-integration-build-plan.md.
"""
import unittest
from pathlib import Path

from backend.app.services import fact_dictionary as fd


class FactDictionaryInvariants(unittest.TestCase):
    def test_no_duplicate_fact_keys(self):
        keys = [f.fact_key for f in fd._FACTS]
        dups = [k for k, n in {k: keys.count(k) for k in keys}.items() if n > 1]
        self.assertEqual(dups, [], f"duplicate fact_keys in the registry: {dups}")

    def test_join_indices_are_unambiguous(self):
        # No two facts may claim the same prefill_source or the same field_id — the join must
        # resolve to exactly one fact.
        srcs = [f.prefill_source for f in fd._FACTS if f.prefill_source]
        self.assertEqual(len(srcs), len(set(srcs)), "two facts share a prefill_source")
        fids = [fid for f in fd._FACTS for fid in f.field_ids]
        self.assertEqual(len(fids), len(set(fids)), "two facts share a field_id")

    def test_consult_professional_firewall_is_locked(self):
        # Regulated determinations must be flagged professional AND carry no prefill_source,
        # so a value is never auto-resolved for them. Guards against someone making a legal
        # determination fillable.
        regulated = {f.fact_key: f for f in fd._FACTS if f.professional_review_required}
        self.assertTrue(regulated, "no consult-professional facts present — firewall vocabulary lost")
        for fk, f in regulated.items():
            self.assertIsNone(
                f.prefill_source,
                f"{fk} is professional_review_required but has a prefill_source {f.prefill_source!r} — "
                "a regulated fact must never resolve a value",
            )
        # the known FR→NO regulated set must stay firewalled
        for k in ("tax_residency_status", "pe_risk", "a1_determination"):
            self.assertIn(k, regulated, f"{k} must remain a consult-professional firewall fact")

    def test_lookup_prefers_prefill_source_then_field_id(self):
        # portable prefill_source key
        e = fd.lookup("profile.passport_number")
        self.assertIsNotNone(e)
        self.assertEqual(e.fact_key, "passport_number")
        # a firewall fact carries no prefill_source → resolves by field_id, stays non-fillable
        e2 = fd.lookup(None, "tax_residency_status")
        self.assertIsNotNone(e2)
        self.assertTrue(e2.professional_review_required)
        # unknown → None (read-model degrades, never raises)
        self.assertIsNone(fd.lookup("profile.not_a_real_source", "also_not_real"))

    def test_every_fact_has_a_category(self):
        for f in fd._FACTS:
            self.assertTrue(f.category, f"{f.fact_key} has no category")

    def test_module_is_llm_free(self):
        src = Path(fd.__file__).read_text(encoding="utf-8")
        for banned in ("llm_client", "import openai", "import anthropic", "policy_assistant_llm"):
            self.assertNotIn(banned, src, f"fact_dictionary imports {banned} — must stay serve-safe")


if __name__ == "__main__":
    unittest.main()
