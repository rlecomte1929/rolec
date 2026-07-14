"""End-to-end nationality gating against the REAL france.yaml seed.

Every other nationality test asserts against a hand-built `base_requirements`
list. That is exactly how the seed regression got in: the fixture in
test_rules_engine_nationality.py models `passport` as
`appliesToNationalityClasses: None` ("applies to everyone"), but the seed's
file-level `default_applies_to_nationality_classes: [THIRD_COUNTRY]` means the
real catalog produces `["THIRD_COUNTRY"]` for it. The fixture passed; the
product would have shipped a French citizen a one-line dossier with four empty
pillars.

So this file deliberately takes the long way round: load the actual YAML, run it
through the actual `build_payloads`, map it exactly as `requirements_builder`
maps DB rows, and only then call `apply_rules`. If the seed and the engine ever
disagree again, this is the test that fails.
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
    os.path.dirname(__file__), "..", "seeds", "requirements", "france.yaml"
)


def _france_base_items():
    """The real seed, mapped the way requirements_builder maps DB rows."""
    with open(_SEED_PATH, "r", encoding="utf-8") as fh:
        seed = yaml.safe_load(fh)
    payloads = build_payloads(seed, only_country="FRANCE")
    # Mirror requirements_builder._base_items: one purpose ("employment") only,
    # so a requirement seeded for two purposes doesn't show up twice.
    return [
        {
            "id": p["id"],
            "pillar": p["pillar"],
            "title": p["title"],
            "description": p["description"],
            "severity": p["severity"],
            "owner": p["owner"],
            "requiredFields": json.loads(p["required_fields_json"]),
            "citations": json.loads(p["citations_json"]),
            "appliesToAssignmentTypes": (
                json.loads(p["applies_to_assignment_types_json"])
                if p["applies_to_assignment_types_json"]
                else None
            ),
            "appliesToNationalityClasses": (
                json.loads(p["applies_to_nationality_classes_json"])
                if p["applies_to_nationality_classes_json"]
                else None
            ),
            "verificationStatus": p["verification_status"],
        }
        for p in payloads
        if p["purpose"] == "employment"
    ]


def _draft(nationality: str, assignment_type: str = "LTA"):
    return {
        "employeeProfile": {"nationality": nationality},
        "relocationBasics": {
            "destCountry": "FRANCE",
            "purpose": "employment",
            "assignmentType": assignment_type,
        },
    }


def _titles(items):
    return [i["title"] for i in items]


def _pillars(items):
    return {i["pillar"] for i in items}


VISA_MARKERS = ("visa", "vls-ts", "anef", "dgef", "residence card")


def _visa_track(items):
    return [t for t in _titles(items) if any(m in t.lower() for m in VISA_MARKERS)]


class TestFrenchNationalReturningHome:
    """The bug that started this: a French citizen told to get a French visa."""

    def test_visa_track_is_gone(self):
        _, expanded, _ = apply_rules(_draft("French"), _france_base_items())
        actionable = [i for i in expanded if i.get("outcomeType") != "nothing_to_do"]
        assert _visa_track(actionable) == [], (
            "a French national relocating home must not be served the VLS-TS "
            f"track, got: {_visa_track(actionable)}"
        )

    def test_the_no_visa_answer_is_stated_not_implied(self):
        _, expanded, _ = apply_rules(_draft("French"), _france_base_items())
        nothing = [i for i in expanded if i.get("outcomeType") == "nothing_to_do"]
        assert len(nothing) == 1
        assert nothing[0]["pillar"] == "RESIDENCE"
        assert nothing[0]["reason"], "a nothing_to_do with no reason is just silence"
        assert "national of France" in nothing[0]["reason"]

    def test_no_pillar_is_left_empty(self):
        """The whole point. Suppressing the visa file must not strip IDENTITY,
        EMPLOYMENT, HOUSING and HEALTHCARE down to nothing — an empty pillar
        reads as a broken screen."""
        _, expanded, _ = apply_rules(_draft("French"), _france_base_items())
        got = _pillars(expanded)
        for pillar in ("IDENTITY", "EMPLOYMENT", "HOUSING", "HEALTHCARE", "RESIDENCE"):
            assert pillar in got, f"{pillar} pillar is empty for a French national"

    def test_establishment_steps_are_not_visa_framed(self):
        """An EU national's items must not talk about a visa they'll never file."""
        _, expanded, _ = apply_rules(_draft("French"), _france_base_items())
        for item in expanded:
            if item.get("outcomeType") == "nothing_to_do":
                continue
            desc = item["description"].lower()
            assert "long-stay visa" not in desc and "vls-ts" not in desc, (
                f"{item['title']!r} is framed around the visa file but is served "
                "to an EU national"
            )

    def test_waived_titles_are_surfaced_not_silently_dropped(self):
        _, _, flags = apply_rules(_draft("French"), _france_base_items())
        assert flags["nationalityClass"] == OWN_NATIONAL
        assert flags["nationalityWaived"], (
            "the suppressed visa titles must be reported so the UI can explain "
            "the shorter list"
        )
        assert any("visa" in t.lower() for t in flags["nationalityWaived"])


class TestNorwegianIsEeaNotOwnNational:
    def test_norwegian_also_skips_the_visa_track(self):
        _, expanded, flags = apply_rules(_draft("Norwegian"), _france_base_items())
        actionable = [i for i in expanded if i.get("outcomeType") != "nothing_to_do"]
        assert _visa_track(actionable) == []
        assert flags["nationalityClass"] == EU_EEA

    def test_reason_says_free_movement_not_own_country(self):
        _, expanded, _ = apply_rules(_draft("Norwegian"), _france_base_items())
        nothing = [i for i in expanded if i.get("outcomeType") == "nothing_to_do"]
        assert len(nothing) == 1
        assert "Freedom of movement" in nothing[0]["reason"]


class TestThirdCountryNationalIsUnaffected:
    """The gate must not have quietly narrowed anyone else's dossier."""

    def test_indian_national_still_gets_the_full_visa_track(self):
        _, expanded, flags = apply_rules(_draft("Indian"), _france_base_items())
        titles = _titles(expanded)
        assert any("Long-stay work visa" in t for t in titles)
        assert any("ANEF" in t for t in titles)
        assert any("DGEF" in t for t in titles)
        assert flags.get("nationalityClass") == THIRD_COUNTRY

    def test_indian_national_is_never_told_freedom_of_movement_applies(self):
        """The fabrication guard. _immigration_confirmation is called whenever
        anything was dropped, and adding EU-scoped items means a third-country
        national now DOES drop things — so without the THIRD_COUNTRY guard this
        person would be told they need no visa. They need one."""
        _, expanded, _ = apply_rules(_draft("Indian"), _france_base_items())
        nothing = [i for i in expanded if i.get("outcomeType") == "nothing_to_do"]
        assert nothing == [], (
            "a third-country national must NEVER receive a 'no visa required' "
            f"confirmation, got: {[i['reason'] for i in nothing]}"
        )
        for item in expanded:
            assert "Freedom of movement" not in (item.get("reason") or "")

    def test_indian_national_does_not_get_the_eu_establishment_items(self):
        _, expanded, _ = apply_rules(_draft("Indian"), _france_base_items())
        titles = _titles(expanded)
        assert not any("national identity card" in t.lower() for t in titles)
        assert not any("justificatif" in t.lower() for t in titles)


class TestUnknownNationalityChangesNothing:
    def test_unknown_nationality_claims_nothing(self):
        """Fail open, never fail confident: if we can't classify, we must not
        assert a right the person may not have."""
        for nationality in (None, "", "Klingon"):
            _, expanded, flags = apply_rules(
                _draft(nationality), _france_base_items()  # type: ignore[arg-type]
            )
            assert flags.get("nationalityClass") is None
            assert flags.get("nationalityWaived") is None
            nothing = [i for i in expanded if i.get("outcomeType") == "nothing_to_do"]
            assert nothing == [], f"claimed 'nothing to do' for nationality={nationality!r}"

    def test_unknown_nationality_is_NOT_served_the_eu_track(self):
        """The regression this test file exists for, arrived at from the other side.

        'Unknown => don't filter' was safe when the catalog was one track. With two
        mutually exclusive tracks, not filtering means serving BOTH — and the EU
        track's own copy says "no visa is involved". Every real France case in
        production has nationality=null, so this is not a corner case: it is the
        default path. A person we cannot classify must get the demanding track and
        no free-movement claim whatsoever.
        """
        for nationality in (None, "", "Klingon", "asdas", "India"):
            _, expanded, _ = apply_rules(
                _draft(nationality), _france_base_items()  # type: ignore[arg-type]
            )
            for item in expanded:
                blob = f"{item.get('description') or ''} {item.get('reason') or ''}"
                assert "EU/EEA national" not in blob, (
                    f"nationality={nationality!r} was told 'As an EU/EEA national...' — "
                    "a fabricated right of free movement"
                )
                assert "Freedom of movement" not in blob
                assert "no visa is involved" not in blob

            titles = _titles(expanded)
            assert not any("national identity card" in t.lower() for t in titles)
            assert not any("justificatif" in t.lower() for t in titles)
            # ...and they must still get the full visa track, not a narrowed list.
            assert any("Long-stay work visa" in t for t in titles)


class TestNationalityResolutionCannotFabricateFreeMovement:
    """A two-letter string used to become a country: `len(s) == 2 and s.isalpha()`.

    `nationality` is unvalidated free text (production holds 'f', 'gh', 'asdas',
    '1212'), and the free-movement set holds 31 two-letter codes — so a stray
    keystroke landing on 'xx'-shaped junk could resolve to an EU member and
    produce "no visa or residence permit required".
    """

    def test_junk_never_resolves_to_free_movement(self):
        from backend.app.services.nationality_class import classify

        junk = ["asdas", "1212", "f", "dfgd", "shtfryhdyt", "xx", "qq", "zz",
                "12", "33", "ewf", "giu", "dze", "sdfsdf"]
        for value in junk:
            assert classify(value, "FRANCE") not in ("EU_EEA", "OWN_NATIONAL"), (
                f"junk nationality {value!r} resolved to free movement"
            )

    def test_eu_nationalities_beyond_the_original_six_now_resolve(self):
        """The headline claim was "EU citizens skip the visa track". It was true
        for about a fifth of the EU: _ADJECTIVAL had 6 free-movement entries, so
        an Austrian or Italian citizen got the full French work-visa track."""
        from backend.app.services.nationality_class import EU_EEA, classify

        for value in ("Austrian", "Italian", "Irish", "Spanish", "Polish",
                      "Portuguese", "Czech", "Danish", "Austria", "Italy", "Ireland"):
            assert classify(value, "FRANCE") == EU_EEA, f"{value} is an EU citizen"
