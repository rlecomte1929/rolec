"""`applies_to.pillar` beats the `domain_area` default when a batch states one.

Before this, `mappings.resolve()` read the pillar off `domain_area='immigration'` and nothing
else, so every promoted topic landed at RESIDENCE. The ES→IE third-country batch
(`es-ie-thirdcountry-requirements-2026-08-22`) is the case that exposed it: its Revenue/RPN and
tax-residence topics carry EMPLOYMENT and TAX on their facts, while production already serves
Irish tax at EMPLOYMENT — so promotion would have split one subject across two pillars with no
way to reach the right one through `--promote`.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from backend.imports.otto import mappings
from backend.imports.otto.parsers import TIER_AUTO


def _fact(pillar=None, *, fact_key="k", nationality="non-EEA", status="professional"):
    applies_to = {"nationality": nationality, "status": status}
    if pillar is not None:
        applies_to["pillar"] = pillar
    return SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        fact_key=fact_key,
        fact_text="Some requirement text.",
        fact_type="other",
        applies_to=applies_to,
        source_url="https://www.revenue.ie/en/jobs-and-pensions/emergency-tax/index.aspx",
        evidence_quote="A quotable line.",
        accuracy_tier=TIER_AUTO,
    )


def _entity(topic_key="ES-IE:thirdcountry:taxation", title="Ireland - taxation"):
    return SimpleNamespace(
        destination_country="IE",
        topic_key=topic_key,
        title=title,
        domain_area="immigration",
    )


class ResolvePillarTests(unittest.TestCase):
    """The unit under test, in isolation from the rest of `resolve()`."""

    def test_absent_pillar_falls_back_to_domain_area_default(self):
        pillar, err = mappings.resolve_pillar([_fact(), _fact()])
        self.assertIsNone(err)
        self.assertEqual(pillar, mappings.IMMIGRATION_PILLAR)
        self.assertEqual(pillar, "RESIDENCE")

    def test_stated_pillar_wins_over_the_default(self):
        # The regression: this returned RESIDENCE before the fix.
        pillar, err = mappings.resolve_pillar([_fact("EMPLOYMENT")])
        self.assertIsNone(err)
        self.assertEqual(pillar, "EMPLOYMENT")
        self.assertNotEqual(pillar, mappings.IMMIGRATION_PILLAR)

    def test_tax_alias_maps_to_employment(self):
        pillar, err = mappings.resolve_pillar([_fact("TAX")])
        self.assertIsNone(err)
        self.assertEqual(pillar, "EMPLOYMENT")

    def test_pillar_is_normalised_case_and_whitespace_insensitively(self):
        pillar, err = mappings.resolve_pillar([_fact("  employment ")])
        self.assertIsNone(err)
        self.assertEqual(pillar, "EMPLOYMENT")

    def test_default_valued_facts_do_not_outvote_a_stated_pillar(self):
        # revenue_rpn_emergency_tax's real shape: 2 facts EMPLOYMENT, 5 facts RESIDENCE.
        # RESIDENCE is what the default already yields, so it carries no signal.
        facts = [_fact("EMPLOYMENT"), _fact("EMPLOYMENT")] + [_fact("RESIDENCE")] * 5
        pillar, err = mappings.resolve_pillar(facts)
        self.assertIsNone(err)
        self.assertEqual(pillar, "EMPLOYMENT")

    def test_two_different_non_default_pillars_refuse(self):
        pillar, err = mappings.resolve_pillar([_fact("EMPLOYMENT"), _fact("HEALTHCARE")])
        self.assertIsNone(pillar)
        self.assertIn("disagree", err)
        self.assertIn("EMPLOYMENT", err)
        self.assertIn("HEALTHCARE", err)

    def test_unknown_pillar_refuses_rather_than_inventing_one(self):
        # `requirement_items.pillar` has no CHECK constraint, so this would be written happily.
        pillar, err = mappings.resolve_pillar([_fact("WELLBEING")])
        self.assertIsNone(pillar)
        self.assertIn("WELLBEING", err)
        self.assertIn("not a catalog pillar", err)

    def test_every_alias_target_is_itself_a_canonical_pillar(self):
        for source, target in mappings.PILLAR_ALIASES.items():
            self.assertIn(target, mappings.CANONICAL_PILLARS, f"alias {source} -> {target}")


class ResolveEndToEndPillarTests(unittest.TestCase):
    """The same behaviour observed through `resolve()`, which is what `promote()` calls."""

    def test_draft_carries_the_stated_pillar_not_the_default(self):
        draft = mappings.resolve(_entity(), [_fact("TAX"), _fact("TAX", fact_key="k2")])
        self.assertNotIsInstance(draft, mappings.Unmapped)
        self.assertEqual(draft.payload["pillar"], "EMPLOYMENT")
        self.assertTrue(
            any("pillar=EMPLOYMENT from applies_to.pillar" in d for d in draft.derivations),
            draft.derivations,
        )

    def test_draft_falls_back_to_residence_when_no_fact_states_a_pillar(self):
        draft = mappings.resolve(_entity(), [_fact(), _fact(fact_key="k2")])
        self.assertNotIsInstance(draft, mappings.Unmapped)
        self.assertEqual(draft.payload["pillar"], "RESIDENCE")
        self.assertTrue(
            any("from domain_area='immigration'" in d for d in draft.derivations),
            draft.derivations,
        )

    def test_conflicting_pillars_return_unmapped_not_a_wrong_row(self):
        result = mappings.resolve(
            _entity(), [_fact("EMPLOYMENT"), _fact("HOUSING", fact_key="k2")]
        )
        self.assertIsInstance(result, mappings.Unmapped)
        self.assertIn("disagree on applies_to.pillar", result.reason)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
