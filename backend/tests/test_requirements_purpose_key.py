"""The purpose half of the catalog key, table-driven against REAL production data.

`crud.list_requirements` matches purpose with `==`. The catalog holds only
{employment, other, study, family}. Nothing validated the field, three intakes
wrote three vocabularies into it, and production ended up with:

    work 238 | lta 218 | permanent 27 | transfer 27 | repatriation 27 |
    domestic 26 | sta 26 | Employment 26 | LTA 1
    (+ employment 53 | family 10 | study 8 | other 7 | null 96, which matched)

616 of 780 cases — 79% — matched NOTHING and got an empty requirements list. On
that screen, empty means "nothing is required of you". A lookup miss was making a
legal claim.

These are the actual values, not invented ones.
"""
from __future__ import annotations

import pytest

from backend.app.services.requirements_purpose_key import (
    CANONICAL_PURPOSES,
    assignment_type_from_purpose,
    is_known_catalog_gap,
    to_purpose,
)

# Every distinct purpose observed in production wizard_cases, with its count.
PROD_PURPOSES = {
    "work": 238, "lta": 218, "employment": 53, "permanent": 27, "transfer": 27,
    "repatriation": 27, "domestic": 26, "sta": 26, "Employment": 26, "family": 10,
    "study": 8, "other": 7, "LTA": 1,
}
# `null` (96 cases) is handled by the caller's `or "employment"` default, so it is
# not in this table — it was never part of the 616.


class TestEveryProductionValueResolves:
    """The acceptance test. 616 cases must stop returning an empty list."""

    @pytest.mark.parametrize("raw", sorted(PROD_PURPOSES))
    def test_every_real_value_resolves_to_a_catalog_purpose(self, raw):
        resolved = to_purpose(raw)
        assert resolved is not None, (
            f"{raw!r} ({PROD_PURPOSES[raw]} production cases) resolves to nothing — "
            "those cases would query the catalog with a bad key and get an empty "
            "list that reads as 'nothing is required of you'"
        )
        assert resolved in CANONICAL_PURPOSES

    def test_no_production_value_is_left_behind(self):
        """The headline. Every value in the wild resolves; none falls through to
        an empty list. (Counts drift as cases are created — the assertion is
        'nothing unresolved', not an exact total.)"""
        unresolved = {k: v for k, v in PROD_PURPOSES.items() if to_purpose(k) is None}
        assert unresolved == {}, (
            f"still unresolved: {unresolved} — "
            f"{sum(unresolved.values())} production cases would get an empty list"
        )

    def test_the_616_that_missed_now_hit(self):
        """The specific values that matched nothing before this resolver existed."""
        previously_broken = ["work", "lta", "permanent", "transfer", "repatriation",
                             "domestic", "sta", "Employment", "LTA"]
        for raw in previously_broken:
            assert to_purpose(raw) in CANONICAL_PURPOSES, raw


class TestCasingWasTheWholeBugForSomeCases:
    """The live intake's <select> has no value= attributes, so the option TEXT is
    the value: it emits 'Employment', and the catalog holds 'employment'."""

    def test_title_case_resolves(self):
        assert to_purpose("Employment") == "employment"
        assert to_purpose("  EMPLOYMENT  ") == "employment"
        assert to_purpose("Study") == "study"


class TestAssignmentTypesAreRecoveredNotLost:
    """272 cases put an assignment type in the purpose field. Mapping the purpose
    and dropping the rest would be its own silent wrong answer: an STA case would
    lose its waivers and be served long-term-only requirements."""

    @pytest.mark.parametrize("raw,expected", [
        ("lta", "LTA"), ("LTA", "LTA"), ("sta", "STA"), ("permanent", "PERMANENT"),
    ])
    def test_the_assignment_type_is_recovered(self, raw, expected):
        assert to_purpose(raw) == "employment"      # axis 1
        assert assignment_type_from_purpose(raw) == expected  # axis 2, not lost

    @pytest.mark.parametrize("raw", ["employment", "study", "family", "other", "work", "domestic"])
    def test_a_real_purpose_carries_no_assignment_signal(self, raw):
        assert assignment_type_from_purpose(raw) is None


class TestUnrecognisedFailsClosed:
    """Same contract as to_iso: return None so the caller can say 'not covered'
    rather than query with a bad key and let zero rows read as 'nothing required'."""

    @pytest.mark.parametrize("raw", ["asdas", "1212", "banana", "", "   ", None])
    def test_unrecognised_returns_none(self, raw):
        assert to_purpose(raw) is None


class TestKnownGapsAreStatedNotHidden:
    """An intra-company transfer is a distinct visa route the catalog does not
    model. We serve `employment` because it is close and an empty list would read
    as 'nothing required' — but the approximation is recorded, not hidden."""

    @pytest.mark.parametrize("raw", ["transfer", "ict", "intracompany", "intra_company_transfer"])
    def test_ict_resolves_to_employment_and_is_flagged(self, raw):
        assert to_purpose(raw) == "employment"
        assert is_known_catalog_gap(raw) is True

    @pytest.mark.parametrize("raw", ["employment", "study", "family", "other", "work", "lta"])
    def test_a_modelled_purpose_is_not_a_gap(self, raw):
        assert is_known_catalog_gap(raw) is False


class TestTheCatalogVocabularyIsTheOneWeThinkItIs:
    def test_canonical_matches_public_corridor(self):
        """CANONICAL_PURPOSES must not drift from the only other declared list."""
        from backend.app.routers.public_corridor import _VALID_PURPOSES

        assert set(CANONICAL_PURPOSES) == set(_VALID_PURPOSES)

    def test_canonical_matches_the_seed_yamls(self):
        """...and neither may drift from what is actually seeded."""
        import glob
        import os

        yaml = pytest.importorskip("yaml")
        seed_dir = os.path.join(os.path.dirname(__file__), "..", "seeds", "requirements")
        seeded = set()
        for path in glob.glob(os.path.join(seed_dir, "*.yaml")):
            with open(path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            for purposes in (data.get("purposes_by_country") or {}).values():
                seeded.update(purposes)
        assert seeded <= set(CANONICAL_PURPOSES), (
            f"a seed file declares a purpose the resolver cannot produce: "
            f"{seeded - set(CANONICAL_PURPOSES)}"
        )
