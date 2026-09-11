"""Posted vs local social-security regime filters A1 / Certificate of Coverage rows.

Mirrors backend/tests/test_sta_requirement_waivers.py: apply_rules is the live
requirements engine stage (compute_case_requirements → GET /{case_id}/requirements).
A requirement scoped to ['posted'] is kept for a posted case, dropped for a local
case, and kept when the case regime is missing/unknown (fail-open). A row with no
appliesToRegimes is served to every regime.
"""
import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from backend.app.services.rules_engine import apply_rules, _applies_to_regime


A1 = {
    "id": "a1-posted",
    "pillar": "SOCIAL_SECURITY",
    "title": "A1 / Portable Document for posted workers",
    "description": "Home-country coverage for a genuine posting.",
    "severity": "WARN",
    "owner": "EMPLOYER",
    "requiredFields": [],
    "citations": [],
    "appliesToRegimes": ["posted"],
}

UNIVERSAL = {
    "id": "ss-register",
    "pillar": "SOCIAL_SECURITY",
    "title": "Host social security registration",
    "description": "Register in the host scheme when transferring locally.",
    "severity": "WARN",
    "owner": "EMPLOYEE",
    "requiredFields": [],
    "citations": [],
}


def _draft(regime=None):
    assignment = {"assignmentType": "LTA"}
    if regime is not None:
        assignment["socialSecurityRegime"] = regime
    return {
        "relocationBasics": {"purpose": "employment", "destCountry": "DE"},
        "employeeProfile": {"nationality": "FR"},
        "assignmentContext": assignment,
    }


def _titles(expanded):
    return {r.get("title") for r in expanded}


def test_helper_null_and_empty_apply_to_all():
    assert _applies_to_regime({}, "posted") is True
    assert _applies_to_regime({"appliesToRegimes": []}, "local") is True
    assert _applies_to_regime({"appliesToRegimes": ["posted"]}, "posted") is True
    assert _applies_to_regime({"appliesToRegimes": ["posted"]}, "local") is False


def test_posted_case_keeps_a1():
    _rf, expanded, _flags = apply_rules(_draft("posted"), [A1, UNIVERSAL])
    assert "A1 / Portable Document for posted workers" in _titles(expanded)
    assert "Host social security registration" in _titles(expanded)


def test_local_case_drops_a1():
    _rf, expanded, flags = apply_rules(_draft("local"), [A1, UNIVERSAL])
    assert "A1 / Portable Document for posted workers" not in _titles(expanded)
    assert "Host social security registration" in _titles(expanded)
    assert "A1 / Portable Document for posted workers" in flags.get("regimeWaived", [])


def test_null_regime_row_is_served_to_every_case_regime():
    for regime in ("posted", "local", "unknown", None):
        _rf, expanded, _flags = apply_rules(_draft(regime), [UNIVERSAL])
        assert "Host social security registration" in _titles(expanded)


def test_unknown_or_missing_case_regime_is_fail_open():
    for regime in (None, "unknown", ""):
        _rf, expanded, _flags = apply_rules(_draft(regime), [A1, UNIVERSAL])
        assert "A1 / Portable Document for posted workers" in _titles(expanded)
