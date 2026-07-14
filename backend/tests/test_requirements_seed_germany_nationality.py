"""Nationality gating against the REAL germany.yaml seed.

Germany had NO `employment` purpose. long_term_only.yaml declared `GERMANY: [other]`
— the only country there without it — while essentially every real relocation
resolves to `employment`. So 372 production cases, the single biggest corridor,
looked up (GERMANY, employment), found zero rows, and were served an empty
requirements list. The employee's screen rendered that as "No destination
requirements apply to your case."

Germany is also where the EU/third-country split bites hardest, and it must cut
BOTH ways:

  * an EU citizen needs no residence permit — but absolutely still owes the
    Anmeldung and the Sozialversicherung registration. Suppressing those would be
    the mirror-image lie.
  * a third-country national needs the permit, and must never be told otherwise.

Loads the ACTUAL yaml through the ACTUAL build_payloads. A hand-built fixture is how
the France regression got in.
"""
from __future__ import annotations

import json
import os

import pytest

yaml = pytest.importorskip("yaml")

from backend.app.services.nationality_class import EU_EEA, THIRD_COUNTRY
from backend.app.services.rules_engine import apply_rules
from backend.scripts.seed_requirements import build_payloads

_SEED_PATH = os.path.join(
    os.path.dirname(__file__), "..", "seeds", "requirements", "germany.yaml"
)

# Steps every newcomer owes regardless of nationality. An EU citizen who skipped the
# Anmeldung would be in breach — hiding it from them is not a kindness.
UNIVERSAL_TITLES = {
    "Residence registration (Anmeldung)",
    "Social security registration (Sozialversicherung)",
    "Long-term rental contract (Mietvertrag)",
    "Employment letter",
    "Minimum lead time",
}

PERMIT_MARKERS = ("aufenthaltstitel", "residence permit", "work visa", "blue card")

# Byte-identical to what is in production. The seeder's natural key is
# country + purpose + title and there is no delete path, so a changed title inserts a
# duplicate and orphans the original forever.
PRODUCTION_TITLES = {
    "Employment letter",
    "Long-term rental contract (Mietvertrag)",
    "Minimum lead time",
    "Residence registration (Anmeldung)",
    "Social security registration (Sozialversicherung)",
    "Valid passport (6+ months)",
}


def _payloads(purpose="employment"):
    with open(_SEED_PATH, "r", encoding="utf-8") as fh:
        seed = yaml.safe_load(fh)
    return [p for p in build_payloads(seed, only_country="GERMANY") if p["purpose"] == purpose]


def _items(purpose="employment"):
    return [
        {
            "id": p["id"], "pillar": p["pillar"], "title": p["title"],
            "description": p["description"], "severity": p["severity"], "owner": p["owner"],
            "requiredFields": json.loads(p["required_fields_json"]),
            "citations": json.loads(p["citations_json"]),
            "appliesToAssignmentTypes": (
                json.loads(p["applies_to_assignment_types_json"])
                if p["applies_to_assignment_types_json"] else None
            ),
            "appliesToNationalityClasses": (
                json.loads(p["applies_to_nationality_classes_json"])
                if p["applies_to_nationality_classes_json"] else None
            ),
            "verificationStatus": p["verification_status"],
        }
        for p in _payloads(purpose)
    ]


def _draft(nationality, assignment_type="LTA"):
    return {
        "employeeProfile": {"nationality": nationality},
        "relocationBasics": {
            "destCountry": "GERMANY", "originCountry": "India", "purpose": "employment",
        },
        "assignmentContext": {"assignmentType": assignment_type},
    }


def _titles(items):
    return [i["title"] for i in items]


def _permit_track(items):
    return [t for t in _titles(items) if any(m in t.lower() for m in PERMIT_MARKERS)]


class TestGermanyCanFinallyServeAnEmploymentRelocation:
    """The headline: 372 cases got an empty list because GERMANY had no
    `employment` purpose."""

    def test_the_employment_purpose_exists_and_is_not_empty(self):
        assert _payloads("employment"), (
            "GERMANY has no rows for purpose=employment — every German employment "
            "relocation would get an empty requirements list"
        )

    def test_the_other_purpose_is_preserved(self):
        assert _payloads("other"), "the pre-existing (GERMANY, other) rows must not disappear"

    def test_the_production_titles_are_byte_identical(self):
        """A changed title inserts a duplicate and orphans the original forever —
        there is no delete path in the seeder."""
        seeded = {p["title"] for p in _payloads("other")}
        lost = PRODUCTION_TITLES - seeded
        assert lost == set(), f"these production titles would be orphaned: {lost}"

    def test_the_source_record_citations_survive(self):
        """crud.create_requirement_item OVERWRITES citations_json. Dropping the
        source-record UUIDs would silently sever the provenance links."""
        by_title = {p["title"]: json.loads(p["citations_json"]) for p in _payloads("other")}
        assert "fb8ee5c7-50bf-4c28-9cf0-f42ab0b78ab6" in by_title["Employment letter"]
        assert "fb8ee5c7-50bf-4c28-9cf0-f42ab0b78ab6" in by_title["Valid passport (6+ months)"]


class TestEuNationalToGermany:
    @pytest.mark.parametrize("nationality", ["German", "DE", "French", "Italian", "Swiss"])
    def test_no_residence_permit(self, nationality):
        _, expanded, _ = apply_rules(_draft(nationality), _items())
        actionable = [i for i in expanded if i.get("outcomeType") != "nothing_to_do"]
        assert _permit_track(actionable) == [], (
            f"{nationality} has free movement and needs no Aufenthaltstitel, got: "
            f"{_permit_track(actionable)}"
        )

    def test_the_answer_is_stated_not_implied(self):
        _, expanded, flags = apply_rules(_draft("German"), _items())
        nothing = [i for i in expanded if i.get("outcomeType") == "nothing_to_do"]
        assert len(nothing) == 1
        assert nothing[0]["reason"]
        assert flags["nationalityClass"] in (EU_EEA, "OWN_NATIONAL")

    def test_the_universal_obligations_are_NOT_suppressed(self):
        """The mirror-image lie. An EU citizen who skipped the Anmeldung would be in
        breach. Free movement removes the PERMIT, not the paperwork."""
        _, expanded, _ = apply_rules(_draft("German"), _items())
        titles = set(_titles(expanded))
        for required in UNIVERSAL_TITLES:
            assert required in titles, (
                f"{required!r} was suppressed for an EU national — it applies to everyone"
            )

    def test_no_pillar_is_left_empty(self):
        _, expanded, _ = apply_rules(_draft("German"), _items())
        pillars = {i["pillar"] for i in expanded}
        for pillar in ("IDENTITY", "EMPLOYMENT", "HOUSING", "RESIDENCE", "SOCIAL_SECURITY", "TIMELINE"):
            assert pillar in pillars, f"{pillar} pillar is empty for an EU national"


class TestThirdCountryNationalToGermany:
    def test_gets_the_permit_track(self):
        _, expanded, flags = apply_rules(_draft("Indian"), _items())
        assert _permit_track(expanded), "a third-country national needs a residence permit"
        assert flags.get("nationalityClass") == THIRD_COUNTRY

    def test_also_keeps_the_universal_obligations(self):
        _, expanded, _ = apply_rules(_draft("Indian"), _items())
        titles = set(_titles(expanded))
        for required in UNIVERSAL_TITLES:
            assert required in titles

    def test_is_never_told_no_permit_is_needed(self):
        _, expanded, _ = apply_rules(_draft("Indian"), _items())
        assert [i for i in expanded if i.get("outcomeType") == "nothing_to_do"] == []
        for item in expanded:
            blob = f"{item.get('description') or ''} {item.get('reason') or ''}"
            assert "Freedom of movement" not in blob
            assert "no residence permit are involved" not in blob


class TestUnknownNationalityFailsSafe:
    def test_gets_the_demanding_track_and_claims_nothing(self):
        for nationality in (None, "", "asdas"):
            _, expanded, flags = apply_rules(_draft(nationality), _items())
            assert flags.get("nationalityClass") is None
            assert [i for i in expanded if i.get("outcomeType") == "nothing_to_do"] == []
            assert _permit_track(expanded), "an unresolved nationality must get the permit track"


class TestProvenanceIsNotOverclaimed:
    def test_nothing_claims_to_be_corpus_grounded(self):
        """Every German row is hand-authored or representative. None of it is drawn
        from a verified corpus, and the label must not say otherwise."""
        for p in _payloads("employment") + _payloads("other"):
            assert p["verification_status"] == "representative", p["title"]
