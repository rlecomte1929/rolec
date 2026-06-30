"""TDD tests for backend/app/services/feedback_triage.py — D-BugRoutine Slice-1.

Pure unit tests: no DB, no HTTP, no I/O.
"""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.feedback_triage import classify  # noqa: E402


# ── severity / area derivation ────────────────────────────────────────────────

def test_isolation_leak_is_critical_isolation():
    """Keywords 'isolation' / 'cross-company' / 'leak' → area=isolation, severity=critical."""
    r = classify("I can see data from another company — looks like an isolation leak", "bug")
    assert r["severity"] == "critical"
    assert r["area"] == "isolation"


def test_cross_company_is_critical_isolation():
    r = classify("cross-company data visible in the HR dashboard", "bug")
    assert r["severity"] == "critical"
    assert r["area"] == "isolation"


def test_ui_area_from_spinner():
    """Keywords 'spinner' / 'layout' / 'button' / 'display' → area=ui."""
    r = classify("the spinner keeps showing after the page loads", "other")
    assert r["area"] == "ui"


def test_ui_area_from_layout():
    r = classify("layout is broken on mobile — elements overlap", "other")
    assert r["area"] == "ui"


def test_api_high_from_500():
    """'500' error → area=api, severity=high."""
    r = classify("I get a 500 error when I click submit", "bug")
    assert r["severity"] == "high"
    assert r["area"] == "api"


def test_high_from_crash():
    """'crash' → severity=high."""
    r = classify("the app crashes when uploading a PDF", "bug")
    assert r["severity"] == "high"


def test_high_from_cant():
    """\"can't\" → severity=high."""
    r = classify("I can't log in anymore", "bug")
    assert r["severity"] == "high"


def test_high_from_broken():
    """'broken' → severity=high."""
    r = classify("the export is completely broken", "bug")
    assert r["severity"] == "high"


def test_api_area_from_error_keyword():
    """'error' in text without UI keywords → area=api."""
    r = classify("getting an authentication error", "bug")
    assert r["area"] == "api"


def test_default_low_other():
    """Generic feedback with no keywords → severity=low, area=other."""
    r = classify("the documentation could be improved", None)
    assert r["severity"] == "low"
    assert r["area"] == "other"


def test_feature_area():
    """'feature' / 'request' / 'enhancement' → area=feature."""
    r = classify("feature request: add dark mode", "idea")
    assert r["area"] == "feature"


def test_returns_dict_with_required_keys():
    """classify always returns a dict with 'severity' and 'area'."""
    r = classify("", None)
    assert "severity" in r
    assert "area" in r


def test_severity_values_are_valid():
    """Every returned severity is one of the four allowed values."""
    allowed = {"low", "medium", "high", "critical"}
    for text in ["ok", "error", "crash", "leak", "feature request"]:
        r = classify(text, None)
        assert r["severity"] in allowed, f"unexpected severity for {text!r}: {r['severity']}"


def test_area_values_are_valid():
    """Every returned area is one of the five allowed values."""
    allowed = {"ui", "api", "isolation", "feature", "other"}
    for text in ["spinner", "500", "isolation", "feature", "thanks"]:
        r = classify(text, None)
        assert r["area"] in allowed, f"unexpected area for {text!r}: {r['area']}"


def test_category_bug_raises_severity_floor():
    """category='bug' raises the floor to 'medium' when text gives 'low'."""
    r = classify("minor annoyance with the labels", "bug")
    assert r["severity"] in {"medium", "high", "critical"}


def test_none_text_handled():
    """Empty / None text returns defaults gracefully."""
    r = classify("", None)
    assert r["severity"] == "low"
    assert r["area"] == "other"
