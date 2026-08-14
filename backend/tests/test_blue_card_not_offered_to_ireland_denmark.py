"""
[AIQ-1833 / T18-03] Ireland and Denmark must never be offered an EU Blue Card.

Directive 2021/1883 does not bind Denmark or Ireland (Protocols 21/22 opt-outs), so
neither issues an EU Blue Card. The European Commission states it plainly: "The EU Blue
Card applies in 25 of the 27 EU Member States. It does not apply in Denmark and Ireland."

This was not a theoretical gap. Verified against PROD on 2026-08-13:

    GET /api/hr/cases/{id}/immigration-requirements?corridor_from=ES&corridor_to=IE
        -> {"covered": false, "corridor_to": "IE", "visa_type": "blue_card"}
    GET /api/hr/cases/{id}/immigration-requirements?corridor_from=ES&corridor_to=DK
        -> {"covered": false, "corridor_to": "DK", "visa_type": "blue_card"}

Returned even with the corridor passed explicitly, and the same value reached the
EMPLOYEE via the immigration snapshot. A third-country national acting on it would
pursue a permit Ireland does not issue and miss the 12-week Critical Skills Employment
Permit lodgement window.

REGRESSION BOUNDARY: the blue_card default was load-bearing. Every seeded blue_card row
in immigration_requirements is a "-> DE" corridor (CA/FR/IN/UK/US -> DE), and those are
queried with no explicit visa_type. Measured the same day: IN->DE with no visa_type
parameter returns covered=true with 11 requirements purely because of the default. So
the fix keeps the assumption exactly where the instrument exists and returns None
everywhere else — no corridor's requirement count changes.
"""
import pytest

from backend.app.services.immigration_regime import (
    _BLUE_CARD_STATES,
    _EU_MEMBER_STATES,
    _is_blue_card_destination,
    default_visa_type_for_destination,
)


# ── the frozenset itself ──────────────────────────────────────────────────────

@pytest.mark.parametrize("destination", ["IE", "ie", "Ireland", "ireland", "DK", "dk", "Denmark"])
def test_ireland_and_denmark_are_not_blue_card_destinations(destination):
    assert not _is_blue_card_destination(destination)
    assert default_visa_type_for_destination(destination) is None


def test_blue_card_states_is_eu_members_minus_exactly_ie_and_dk():
    """Derived by subtraction from the existing set — not an inline `!= "IE"` check."""
    removed = _EU_MEMBER_STATES - _BLUE_CARD_STATES
    assert removed == {"ireland", "ie", "denmark", "dk"}


@pytest.mark.parametrize("destination", ["DE", "de", "Germany", "FR", "NL", "ES", "PT", "AT"])
def test_the_other_eu_members_still_are_blue_card_destinations(destination):
    assert _is_blue_card_destination(destination)
    assert default_visa_type_for_destination(destination) == "blue_card"


@pytest.mark.parametrize("destination", ["NO", "Norway", "CH", "IS", "LI", "UK", "US", "SG"])
def test_non_eu_destinations_resolve_to_not_determined(destination):
    """Norway et al. were also being told "blue_card" — they are EEA/EFTA, not EU.

    immigration_regime's own comment already recorded that a non-EEA national heading to
    Norway needs a national skilled-worker permit, not a Blue Card. The API default
    contradicted the module's own documented reasoning.
    """
    assert not _is_blue_card_destination(destination)
    assert default_visa_type_for_destination(destination) is None


def test_no_destination_resolves_to_not_determined():
    assert default_visa_type_for_destination(None) is None
    assert default_visa_type_for_destination("") is None


# ── the regime detector (defect A) ────────────────────────────────────────────

def _detect(destination, nationality):
    from backend.app.services.immigration_regime import ImmigrationRegimeRouter

    return ImmigrationRegimeRouter().detect_regime(
        nationality=nationality, destination_country=destination
    )


@pytest.mark.parametrize("destination", ["IE", "DK"])
@pytest.mark.parametrize("nationality", ["IN", "US", "BR", "CN", "ZA"])
def test_regime_never_emits_blue_card_for_ie_or_dk_for_any_nationality(destination, nationality):
    """Validation criterion 4: no Blue Card for IE/DK, for ANY nationality."""
    regime = _detect(destination, nationality)
    assert regime.regime_id != "blue_card", (
        f"{nationality} -> {destination} was classified blue_card; "
        f"{destination} does not participate in Directive 2021/1883"
    )


@pytest.mark.parametrize("nationality", ["IN", "US", "BR"])
def test_regime_still_emits_blue_card_for_germany(nationality):
    """Regression boundary: the instrument genuinely exists for DE — keep it."""
    assert _detect("DE", nationality).regime_id == "blue_card"


def test_eu_national_to_ireland_is_free_movement_not_a_permit():
    """An EEA national needs no Irish permit at all — free movement must win."""
    regime = _detect("IE", "ES")
    assert regime.regime_id != "blue_card"


# ── the three call sites (defect B) ───────────────────────────────────────────

def test_no_blue_card_default_remains_in_the_three_call_sites():
    """The defaults are what leaked the wrong permit even when the corridor was null."""
    import inspect

    from backend.app.routers import employee_immigration_snapshot
    from backend.app.services import immigration_snapshot_service

    for mod in (employee_immigration_snapshot, immigration_snapshot_service):
        src = inspect.getsource(mod)
        assert 'Query("blue_card")' not in src
        assert 'visa_type: str = "blue_card"' not in src

    from pathlib import Path

    consent = (
        Path(__file__).resolve().parents[1]
        / "app" / "routers" / "immigration_intake_consent.py"
    ).read_text(encoding="utf-8")
    assert 'visa_type: str = "blue_card"' not in consent


def test_snapshot_reports_not_determined_for_ireland(monkeypatch):
    """The snapshot is the surface that reaches the EMPLOYEE — the harmful one."""
    from backend.app.services import immigration_snapshot_service as snap

    monkeypatch.setattr(
        snap, "_get_case_details",
        lambda case_id, org_id: {"origin_country": "ES", "dest_country": "IE"},
    )
    out = snap.build_immigration_snapshot("case-ie")

    assert out["visa_type"] is None, "Ireland must not be handed a blue_card"
    assert out["covered"] is False
    assert out["corridor_from"] == "ES" and out["corridor_to"] == "IE"


def test_snapshot_still_resolves_blue_card_for_germany(monkeypatch):
    """Regression: a DE case must still query blue_card, or its 11 rows vanish."""
    from backend.app.services import immigration_snapshot_service as snap

    seen = {}

    def _fake_requirements(corridor_from, corridor_to, visa_type, *a, **k):
        seen["visa_type"] = visa_type
        return []

    monkeypatch.setattr(
        snap, "_get_case_details",
        lambda case_id, org_id: {"origin_country": "IN", "dest_country": "DE"},
    )
    monkeypatch.setattr(snap, "get_requirements", _fake_requirements)
    snap.build_immigration_snapshot("case-de")

    assert seen["visa_type"] == "blue_card"


def test_an_explicit_visa_type_is_always_honoured(monkeypatch):
    """Callers that know better keep control — the resolver only fills a None."""
    from backend.app.services import immigration_snapshot_service as snap

    seen = {}

    def _fake_requirements(corridor_from, corridor_to, visa_type, *a, **k):
        seen["visa_type"] = visa_type
        return []

    monkeypatch.setattr(
        snap, "_get_case_details",
        lambda case_id, org_id: {"origin_country": "ES", "dest_country": "IE"},
    )
    monkeypatch.setattr(snap, "get_requirements", _fake_requirements)
    snap.build_immigration_snapshot("case-ie", visa_type="critical_skills_permit")

    assert seen["visa_type"] == "critical_skills_permit"
