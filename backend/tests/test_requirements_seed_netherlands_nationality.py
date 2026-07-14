"""Nationality gating against the REAL netherlands.yaml seed.

netherlands.yaml carried the same defect france.yaml did, and said so out loud:

    # SCOPE: non-EEA (e.g. US) salaried route. EEA/EU nationals have free movement.
    source_scope: "US->NL corpus (non-EEA highly-skilled-migrant route); EEA nationals exempt"

...and then contained zero nationality keys. So an EU citizen relocating to the
Netherlands was served the full IND Highly-Skilled-Migrant / EU-Blue-Card permit
track: apply for a residence permit, get an IND-recognised sponsor, collect the
permit. None of which applies to them.

The NL catalog differs from France in a way that matters: three of its steps are
genuinely universal (gemeente/BSN, statutory health insurance, the 30% ruling), so
they must NOT be suppressed for an EU national. Getting this wrong in the other
direction — hiding the BSN registration from a Dutch citizen — would be its own
lie. These tests pin both directions.

Like the France file, this deliberately loads the ACTUAL YAML through the ACTUAL
build_payloads, rather than a hand-built fixture. A fixture is how the France
regression got in.
"""
from __future__ import annotations

import json
import os

import pytest

yaml = pytest.importorskip("yaml")

from backend.app.services.nationality_class import EU_EEA, OWN_NATIONAL, THIRD_COUNTRY
from backend.app.services.rules_engine import apply_rules
from backend.scripts.seed_requirements import build_payloads

_SEED_PATH = os.path.join(
    os.path.dirname(__file__), "..", "seeds", "requirements", "netherlands.yaml"
)

# Steps every newcomer owes regardless of nationality. Suppressing these for an EU
# national would be the mirror-image of the bug we are fixing.
UNIVERSAL_TITLES = {
    "Municipality registration + BSN (gemeente / BRP)",
    "Dutch health insurance (zorgverzekering)",
    "30% ruling application (tax)",
}

PERMIT_MARKERS = ("residence permit", "ind-recognised", "blue card", "permanent residence")


def _nl_items():
    with open(_SEED_PATH, "r", encoding="utf-8") as fh:
        seed = yaml.safe_load(fh)
    payloads = build_payloads(seed, only_country="NETHERLANDS")
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
        for p in payloads if p["purpose"] == "employment"
    ]


def _nl_payloads():
    with open(_SEED_PATH, "r", encoding="utf-8") as fh:
        seed = yaml.safe_load(fh)
    return [p for p in build_payloads(seed, only_country="NETHERLANDS") if p["purpose"] == "employment"]


def _draft(nationality, assignment_type="LTA"):
    # assignmentType lives in assignmentContext, NOT relocationBasics (rules_engine.py:16,26).
    return {
        "employeeProfile": {"nationality": nationality},
        "relocationBasics": {"destCountry": "NETHERLANDS", "purpose": "employment"},
        "assignmentContext": {"assignmentType": assignment_type},
    }


def _titles(items):
    return [i["title"] for i in items]


def _permit_track(items):
    return [t for t in _titles(items) if any(m in t.lower() for m in PERMIT_MARKERS)]


class TestEuNationalToNetherlands:
    """The bug: a German citizen told to apply for an IND residence permit."""

    @pytest.mark.parametrize("nationality", ["Dutch", "NL", "German", "French", "Italian", "Norwegian"])
    def test_the_ind_permit_track_is_gone(self, nationality):
        _, expanded, _ = apply_rules(_draft(nationality), _nl_items())
        actionable = [i for i in expanded if i.get("outcomeType") != "nothing_to_do"]
        assert _permit_track(actionable) == [], (
            f"{nationality} is an EU/EEA citizen and needs no IND permit, got: "
            f"{_permit_track(actionable)}"
        )

    def test_the_no_permit_answer_is_stated_not_implied(self):
        _, expanded, _ = apply_rules(_draft("German"), _nl_items())
        nothing = [i for i in expanded if i.get("outcomeType") == "nothing_to_do"]
        assert len(nothing) == 1
        assert nothing[0]["reason"], "a nothing_to_do with no reason is just silence"
        assert "Freedom of movement" in nothing[0]["reason"]

    def test_the_universal_steps_are_NOT_suppressed(self):
        """The mirror-image lie. An EU citizen absolutely must register at the
        gemeente for a BSN, must take Dutch health insurance, and can claim the
        30% ruling. Hiding those would cost them a legal obligation and money."""
        _, expanded, _ = apply_rules(_draft("German"), _nl_items())
        titles = set(_titles(expanded))
        for required in UNIVERSAL_TITLES:
            assert required in titles, (
                f"{required!r} was suppressed for an EU national — it applies to everyone"
            )

    def test_no_pillar_is_left_empty(self):
        _, expanded, _ = apply_rules(_draft("German"), _nl_items())
        pillars = {i["pillar"] for i in expanded}
        for pillar in ("IDENTITY", "EMPLOYMENT", "RESIDENCE", "HEALTHCARE", "SOCIAL_SECURITY"):
            assert pillar in pillars, f"{pillar} pillar is empty for an EU national"

    def test_nothing_served_to_an_eu_national_is_permit_framed(self):
        _, expanded, _ = apply_rules(_draft("German"), _nl_items())
        for item in expanded:
            if item.get("outcomeType") == "nothing_to_do":
                continue
            desc = item["description"].lower()
            assert "residence-permit application" not in desc
            assert "ind-recognised sponsor meeting" not in desc


class TestThirdCountryNationalToNetherlandsIsUnaffected:
    """The control: the gate must not have narrowed anyone else's dossier."""

    def test_us_national_still_gets_the_full_ind_track(self):
        _, expanded, flags = apply_rules(_draft("United States"), _nl_items())
        titles = _titles(expanded)
        assert any("Residence permit" in t for t in titles)
        assert any("IND-recognised sponsor" in t for t in titles)
        assert any("Collect residence permit" in t for t in titles)
        assert flags.get("nationalityClass") == THIRD_COUNTRY

    def test_us_national_still_gets_the_universal_steps(self):
        _, expanded, _ = apply_rules(_draft("United States"), _nl_items())
        titles = set(_titles(expanded))
        for required in UNIVERSAL_TITLES:
            assert required in titles

    def test_a_third_country_national_is_never_told_no_permit_is_needed(self):
        _, expanded, _ = apply_rules(_draft("Indian"), _nl_items())
        nothing = [i for i in expanded if i.get("outcomeType") == "nothing_to_do"]
        assert nothing == [], "a third-country national must never be told they need no permit"
        for item in expanded:
            blob = f"{item.get('description') or ''} {item.get('reason') or ''}"
            assert "Freedom of movement" not in blob
            assert "no IND residence permit is involved" not in blob

    def test_a_third_country_national_never_sees_the_eu_items(self):
        _, expanded, _ = apply_rules(_draft("Indian"), _nl_items())
        titles = _titles(expanded)
        assert not any("national identity card" in t.lower() for t in titles)


class TestUnknownNationalityFailsSafe:
    def test_unknown_gets_the_demanding_track_and_claims_nothing(self):
        for nationality in (None, "", "asdas"):
            _, expanded, flags = apply_rules(_draft(nationality), _nl_items())
            assert flags.get("nationalityClass") is None
            assert [i for i in expanded if i.get("outcomeType") == "nothing_to_do"] == []
            titles = _titles(expanded)
            assert any("Residence permit" in t for t in titles), (
                "an unresolved nationality must get the demanding permit track"
            )
            assert not any("national identity card" in t.lower() for t in titles), (
                "an unresolved nationality must not be told an EU right applies"
            )


class TestProvenanceIsNotOverclaimed:
    def test_hand_authored_eu_items_are_representative_not_corpus_grounded(self):
        for p in _nl_payloads():
            nat = p["applies_to_nationality_classes_json"] or ""
            if "OWN_NATIONAL" in nat:
                assert p["verification_status"] == "representative", (
                    f"{p['title']!r} is hand-authored but claims "
                    f"{p['verification_status']!r} provenance"
                )

    def test_the_corpus_derived_ind_track_keeps_its_provenance(self):
        permit = [p for p in _nl_payloads()
                  if (p["applies_to_nationality_classes_json"] or "") == '["THIRD_COUNTRY"]']
        assert permit
        for p in permit:
            assert p["verification_status"] == "corpus_grounded"
