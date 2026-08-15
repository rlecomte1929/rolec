"""
[AIQ-1832 / T18-02] Ireland requirements — the two nationality tracks must differ.

The Madrid→Dublin campaign found the Spanish (EU) and Indian (third-country) personas
receiving BYTE-IDENTICAL requirement payloads: the only differing keys across the whole
response were caseId and computedAt. That is the defect this content exists to fix, so the
test that matters is not "Ireland returns rows" but "the two tracks return different rows".

These run on the seed FILE, not the database, so they hold at author time and in CI without
a Postgres. The publication gate (review_status) and the live endpoint are proven separately.
"""
import json
import pathlib

import pytest
import yaml

from backend.app.services.nationality_class import classify
from backend.app.services.requirements_country_key import resolve_catalog_country
from backend.app.services.rules_engine import apply_rules
from backend.scripts.seed_requirements import build_payloads

SEED = pathlib.Path(__file__).resolve().parents[1] / "seeds" / "requirements" / "ireland.yaml"

PERMIT_WORDS = ("permit", "visa", "residence permission", "irp")


@pytest.fixture(scope="module")
def base_items():
    seed = yaml.safe_load(SEED.read_text(encoding="utf-8"))
    payloads = [p for p in build_payloads(seed) if p["purpose"] == "employment"]
    assert payloads, "ireland.yaml produced no employment rows"
    return [
        {
            "id": p["id"],
            "pillar": p["pillar"],
            "title": p["title"],
            "description": p["description"],
            "severity": p["severity"],
            "owner": p["owner"],
            "appliesToAssignmentTypes": (
                json.loads(p["applies_to_assignment_types_json"])
                if p["applies_to_assignment_types_json"] else None
            ),
            "appliesToNationalityClasses": (
                json.loads(p["applies_to_nationality_classes_json"])
                if p["applies_to_nationality_classes_json"] else None
            ),
        }
        for p in payloads
    ]


def _ask(base, nationality, assignment_type="PERMANENT"):
    draft = {
        "relocationBasics": {"purpose": "employment", "destCountry": "IE"},
        "assignmentContext": {"assignmentType": assignment_type},
        "employeeProfile": {"nationality": nationality},
    }
    _required, expanded, _flags = apply_rules(draft, base)
    return [i["title"] for i in expanded]


# ── the catalog wiring this content depends on ────────────────────────────────

def test_ireland_resolves_to_the_catalog_country():
    """Without this, IRELAND rows are unreachable and classify() returns None."""
    assert resolve_catalog_country("IE") == "IRELAND"
    assert resolve_catalog_country("Ireland") == "IRELAND"


def test_nationality_classes_resolve_for_ireland():
    assert classify("ES", "IE") == "EU_EEA"
    assert classify("IE", "IE") == "OWN_NATIONAL"
    assert classify("IN", "IE") == "THIRD_COUNTRY"


# ── the defect the campaign found ─────────────────────────────────────────────

def test_the_two_nationality_tracks_are_not_identical(base_items):
    """The actual T18 finding: ES and IN received byte-identical payloads."""
    eu = _ask(base_items, "ES")
    tc = _ask(base_items, "IN")
    assert eu != tc, "EU and third-country tracks returned the same requirements"
    assert set(eu) != set(tc)


def test_eu_track_is_told_no_permit_is_required(base_items):
    """An EEA national needs nothing from immigration. Saying otherwise is the harm."""
    eu = _ask(base_items, "ES")
    offenders = [
        t for t in eu
        if any(w in t.lower() for w in PERMIT_WORDS)
        and not t.lower().startswith("no ")
    ]
    assert not offenders, f"EU/EEA track was shown permit-ish requirements: {offenders}"
    assert any("no visa or residence permit required" in t.lower() for t in eu), (
        "the affirmative 'nothing required' confirmation is missing — it only fires when a "
        "third-country row was dropped, so this also proves the tracks are scoped apart"
    )


def test_own_national_is_treated_like_an_eu_national(base_items):
    """An Irish national moving to Dublin is OWN_NATIONAL. Scoping rows [EU_EEA] alone
    would silently drop them — the reason the seed uses [OWN_NATIONAL, EU_EEA]."""
    assert _ask(base_items, "IE") == _ask(base_items, "ES")


def test_third_country_track_carries_the_permit_chain(base_items):
    tc = " | ".join(_ask(base_items, "IN")).lower()
    for expected in ("12 weeks", "critical skills", "90 days"):
        assert expected in tc, f"third-country track is missing {expected!r}"


# ── acceptance thresholds ─────────────────────────────────────────────────────

@pytest.mark.parametrize("assignment_type", ["STA", "LTA", "PERMANENT"])
def test_row_counts_meet_the_acceptance_targets(base_items, assignment_type):
    assert len(_ask(base_items, "ES", assignment_type)) >= 6
    assert len(_ask(base_items, "IN", assignment_type)) >= 8


# ── provenance ────────────────────────────────────────────────────────────────

def test_every_requirement_carries_an_official_citation():
    """No row ships without a source. A fabricated or placeholder link beside a real
    immigration requirement is the failure test_no_fake_evidence.py exists to prevent."""
    seed = yaml.safe_load(SEED.read_text(encoding="utf-8"))
    allowed = ("enterprise.gov.ie", "irishimmigration.ie", "citizensinformation.ie",
               "revenue.ie", "welfare.ie", "gov.ie")
    for req in seed["requirements"]:
        cites = req.get("citations") or []
        assert cites, f"{req['key']} has no citation"
        for c in cites:
            assert c.startswith("https://"), f"{req['key']} citation is not https: {c}"
            assert any(d in c for d in allowed), f"{req['key']} cites a non-official domain: {c}"
            assert "example.com" not in c


def test_the_disproven_figures_are_absent():
    """Three figures asserted elsewhere in the repo were refuted from source. If any
    reappears here, someone has re-imported the bad seed."""
    text = SEED.read_text(encoding="utf-8")
    body = "\n".join(
        l for l in text.splitlines() if not l.lstrip().startswith("#")
    )
    assert "60,000" not in body, "the refuted EUR 60,000 off-list threshold is back"
    assert "12 to 16" not in body, "the unsourced 12-16 week decision time is back"
    assert "40%" not in body, "the PDF-only emergency tax rate is back"
