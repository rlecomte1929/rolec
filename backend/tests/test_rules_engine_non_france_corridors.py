"""Nationality gating must not touch the corridors that don't use it.

`apply_rules` now filters by nationality on EVERY case:

    effective_class = nationality_class or THIRD_COUNTRY
    dropped = [r for r in expanded if not _applies_to_nationality_class(r, effective_class)]

FRANCE is the only catalog with nationality-scoped rows (26/26 in production).
GERMANY(6), NORWAY(12), NETHERLANDS(16), SINGAPORE(12), UNITED KINGDOM(12) and
UNITED STATES(18) are entirely universal — every row has
`applies_to_nationality_classes_json IS NULL`. They are unaffected only because
`_applies_to_nationality_class` short-circuits:

    allowed = requirement.get("appliesToNationalityClasses")
    if not allowed:
        return True          # <-- null means universal

That one line is load-bearing for six countries, and nothing asserted it. Flip it
to `return False` and every non-France case returns an EMPTY requirements list —
"nothing is required of you" — while the entire test suite stays green. FR->DE
alone is 231 production cases.

These fixtures are hand-built from the real production rows on purpose: the
DE/NO/SG/UK/US universal rows have no in-repo source (they predate the YAML seeder
and were inserted out-of-band), so they cannot be loaded from a seed file.
"""
from __future__ import annotations

import pytest

from backend.app.services.rules_engine import _applies_to_nationality_class, apply_rules

# The real prod GERMANY catalog (purpose='other'), all universal.
GERMANY_ITEMS = [
    {"id": "de1", "pillar": "EMPLOYMENT", "title": "Employment letter"},
    {"id": "de2", "pillar": "HOUSING", "title": "Long-term rental contract (Mietvertrag)",
     "appliesToAssignmentTypes": ["LTA", "PERMANENT"]},
    {"id": "de3", "pillar": "TIMELINE", "title": "Minimum lead time"},
    {"id": "de4", "pillar": "RESIDENCE", "title": "Residence registration (Anmeldung)",
     "appliesToAssignmentTypes": ["LTA", "PERMANENT"]},
    {"id": "de5", "pillar": "SOCIAL_SECURITY", "title": "Social security registration (Sozialversicherung)",
     "appliesToAssignmentTypes": ["LTA", "PERMANENT"]},
    {"id": "de6", "pillar": "IDENTITY", "title": "Valid passport (6+ months)"},
]

# The real prod NORWAY catalog (purpose='employment'), all universal.
NORWAY_ITEMS = [
    {"id": "no1", "pillar": "EMPLOYMENT", "title": "Employment letter"},
    {"id": "no2", "pillar": "HOUSING", "title": "Long-term housing contract",
     "appliesToAssignmentTypes": ["LTA", "PERMANENT"]},
    {"id": "no3", "pillar": "TIMELINE", "title": "Minimum lead time"},
    {"id": "no4", "pillar": "SOCIAL_SECURITY", "title": "National Insurance registration (folketrygden)",
     "appliesToAssignmentTypes": ["LTA", "PERMANENT"]},
    {"id": "no5", "pillar": "RESIDENCE", "title": "Residence registration (folkeregister)",
     "appliesToAssignmentTypes": ["LTA", "PERMANENT"]},
    {"id": "no6", "pillar": "IDENTITY", "title": "Valid passport (6+ months)"},
]


def _hydrate(items):
    """Fill in the fields apply_rules reads. appliesToNationalityClasses is left
    absent — that IS the property under test (null means universal)."""
    return [
        {
            "description": "d", "severity": "WARN", "owner": "EMPLOYEE",
            "requiredFields": [], "citations": [], "appliesToAssignmentTypes": None,
            **item,
        }
        for item in items
    ]


def _draft(nationality, dest, assignment_type="LTA"):
    # NOTE: apply_rules reads assignmentType from `assignmentContext`, NOT from
    # `relocationBasics` (rules_engine.py:16,26). Putting it in relocationBasics
    # silently disables the assignment-type gate — the fixture looks right and
    # tests nothing.
    return {
        "employeeProfile": {"nationality": nationality},
        "relocationBasics": {"destCountry": dest, "purpose": "employment"},
        "assignmentContext": {"assignmentType": assignment_type},
    }


def _titles(items):
    return sorted(i["title"] for i in items)


# Covers all four nationality classes: OWN_NATIONAL (German->Germany), EU_EEA
# (French->Germany), THIRD_COUNTRY (Indian->Germany), and unresolved (junk/None).
ALL_CLASSES = ["German", "French", "FR", "Norwegian", "Indian", "United States", "asdas", None, ""]


class TestUniversalCatalogIsUnaffectedByNationality:
    """The invariant that makes the THIRD_COUNTRY fallback safe for six countries."""

    @pytest.mark.parametrize("items,dest", [(GERMANY_ITEMS, "GERMANY"), (NORWAY_ITEMS, "NORWAY")])
    def test_every_nationality_class_gets_the_identical_item_set(self, items, dest):
        base = _hydrate(items)
        expected = _titles(base)

        for nationality in ALL_CLASSES:
            _, expanded, flags = apply_rules(_draft(nationality, dest), _hydrate(items))
            assert _titles(expanded) == expected, (
                f"{dest} catalog is entirely universal, but nationality={nationality!r} "
                f"changed the item set. Missing: {set(expected) - set(_titles(expanded))}"
            )
            assert not flags.get("nationalityWaived"), (
                f"nothing should be waived for {dest}: nothing is nationality-scoped"
            )
            assert [i for i in expanded if i.get("outcomeType") == "nothing_to_do"] == [], (
                f"{dest} has no visa track to waive, so there is no 'nothing to do' to claim"
            )

    def test_a_universal_catalog_is_never_emptied(self):
        """The catastrophic failure this file exists to prevent: an empty list on
        this screen means 'nothing is required of you'."""
        for nationality in ALL_CLASSES:
            _, expanded, _ = apply_rules(_draft(nationality, "GERMANY"), _hydrate(GERMANY_ITEMS))
            assert len(expanded) == len(GERMANY_ITEMS), (
                f"nationality={nationality!r} emptied the GERMANY dossier "
                f"({len(expanded)} of {len(GERMANY_ITEMS)} items survived)"
            )


class TestTheRealCorridors:
    """FR->DE is 231 production cases and had zero coverage."""

    def test_french_national_to_germany_gets_the_full_german_dossier(self):
        _, expanded, flags = apply_rules(_draft("French", "GERMANY"), _hydrate(GERMANY_ITEMS))
        assert len(expanded) == 6
        assert "Residence registration (Anmeldung)" in _titles(expanded)
        # An EU citizen still has to register in Germany. Free movement is not
        # "nothing to do" — it removes the VISA, not the establishment steps.
        assert [i for i in expanded if i.get("outcomeType") == "nothing_to_do"] == []
        assert not flags.get("nationalityWaived")

    def test_indian_national_to_norway_gets_the_full_norwegian_dossier(self):
        _, expanded, flags = apply_rules(_draft("Indian", "NORWAY"), _hydrate(NORWAY_ITEMS))
        assert len(expanded) == 6
        assert "National Insurance registration (folketrygden)" in _titles(expanded)
        assert not flags.get("nationalityWaived")

    def test_a_short_assignment_still_drops_long_term_only_steps(self):
        """The nationality gate must not have broken the assignment-type gate that
        already ran on the same list."""
        _, expanded, _ = apply_rules(_draft("French", "GERMANY", "STA"), _hydrate(GERMANY_ITEMS))
        titles = _titles(expanded)
        assert "Residence registration (Anmeldung)" not in titles  # LTA/PERMANENT only
        assert "Valid passport (6+ months)" in titles              # universal


class TestNullMeansUniversal:
    """A direct assertion on the helper. Its assignment-type twin has one
    (test_requirement_applies_to_assignment_types.py::test_helper_semantics);
    the nationality half had none, which is how six countries came to depend on an
    unasserted line."""

    def test_absent_field_applies_to_everyone(self):
        for klass in ("OWN_NATIONAL", "EU_EEA", "THIRD_COUNTRY"):
            assert _applies_to_nationality_class({}, klass) is True

    def test_null_applies_to_everyone(self):
        for klass in ("OWN_NATIONAL", "EU_EEA", "THIRD_COUNTRY"):
            assert _applies_to_nationality_class({"appliesToNationalityClasses": None}, klass) is True

    def test_empty_list_applies_to_everyone(self):
        for klass in ("OWN_NATIONAL", "EU_EEA", "THIRD_COUNTRY"):
            assert _applies_to_nationality_class({"appliesToNationalityClasses": []}, klass) is True

    def test_a_scoped_requirement_matches_only_its_classes(self):
        item = {"appliesToNationalityClasses": ["THIRD_COUNTRY"]}
        assert _applies_to_nationality_class(item, "THIRD_COUNTRY") is True
        assert _applies_to_nationality_class(item, "EU_EEA") is False
        assert _applies_to_nationality_class(item, "OWN_NATIONAL") is False
