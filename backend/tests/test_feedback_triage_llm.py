"""TDD tests for L1 LLM-assisted triage (classify_llm / classify_best).

Pure unit tests: no DB, no network, no I/O.  A fake callable is injected
wherever the real complete_sync would fire — tests stay fast and offline.

Hard gate: the PII-mask-before-egress assertion is the first test and must
pass before any other LLM-path code is trusted.
"""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Imports deferred inside each test so test discovery never imports the real
# llm_client (which would validate OPENAI_API_KEY at import time on some builds).
import importlib

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_triage():
    """Return the feedback_triage module (fresh or cached)."""
    import backend.app.services.feedback_triage as m
    return m


def make_fake_client(response: dict):
    """Return a fake complete_sync callable that records calls and returns response."""
    calls = []

    def _client(**kwargs):
        calls.append(kwargs)
        return response

    _client.calls = calls  # type: ignore[attr-defined]
    return _client


def make_error_client(exc: Exception):
    """Return a fake complete_sync callable that always raises."""
    calls = []

    def _client(**kwargs):
        calls.append(kwargs)
        raise exc

    _client.calls = calls  # type: ignore[attr-defined]
    return _client


# ---------------------------------------------------------------------------
# SAFETY — PII must not reach the LLM (hard gate)
# ---------------------------------------------------------------------------

def test_classify_llm_pii_not_in_prompt_email():
    """Email address in the feedback text must NOT appear in the LLM user-prompt."""
    m = _load_triage()
    fake = make_fake_client({"severity": "low", "area": "other"})

    raw = "My email is jane.doe@example.com, please fix the spinner"
    m.classify_llm(raw, "bug", client=fake)

    assert len(fake.calls) == 1
    user_arg = fake.calls[0]["user"]
    assert "jane.doe@example.com" not in user_arg, (
        "Raw email leaked into LLM prompt; mask_pii must run before egress"
    )
    assert "[REDACTED_EMAIL]" in user_arg


def test_classify_llm_pii_not_in_prompt_phone():
    """International phone number in text must NOT appear in the LLM user-prompt."""
    m = _load_triage()
    fake = make_fake_client({"severity": "low", "area": "other"})

    raw = "Call me at +33 6 12 34 56 78 to discuss the bug"
    m.classify_llm(raw, "bug", client=fake)

    assert len(fake.calls) == 1
    user_arg = fake.calls[0]["user"]
    assert "+33" not in user_arg or "612345678" not in user_arg.replace(" ", ""), (
        "Raw phone number leaked into LLM prompt"
    )
    # At least one REDACTED placeholder must be present
    assert "[REDACTED_" in user_arg


def test_classify_llm_pii_not_in_prompt_combined():
    """Both email and phone in one message — neither must appear raw in the prompt."""
    m = _load_triage()
    fake = make_fake_client({"severity": "low", "area": "other"})

    raw = "user@testcorp.com +33612345678 — the layout is broken"
    m.classify_llm(raw, "bug", client=fake)

    assert len(fake.calls) == 1
    user_arg = fake.calls[0]["user"]
    assert "user@testcorp.com" not in user_arg
    # phone digits may be split by spaces in the redacted version but
    # the consecutive 9-digit suffix is a concrete check
    assert "33612345678" not in user_arg.replace(" ", "")


# ---------------------------------------------------------------------------
# classify_llm — happy path
# ---------------------------------------------------------------------------

def test_classify_llm_valid_response_returned():
    """Valid LLM response with in-enum values is returned directly."""
    m = _load_triage()
    fake = make_fake_client({"severity": "high", "area": "api"})

    result = m.classify_llm("getting a 500 error", "bug", client=fake)

    assert result == {"severity": "high", "area": "api"}


def test_classify_llm_passes_category_in_prompt():
    """Category is surfaced to the model in the user-prompt."""
    m = _load_triage()
    fake = make_fake_client({"severity": "low", "area": "feature"})

    m.classify_llm("add dark mode please", "idea", client=fake)

    user_arg = fake.calls[0]["user"]
    assert "idea" in user_arg.lower()


def test_classify_llm_passes_schema_kwarg():
    """complete_sync must be called with a 'schema' kwarg (structured output)."""
    m = _load_triage()
    fake = make_fake_client({"severity": "low", "area": "other"})

    m.classify_llm("whatever", "other", client=fake)

    assert "schema" in fake.calls[0]
    schema = fake.calls[0]["schema"]
    # Schema must constrain severity and area
    assert "severity" in str(schema)
    assert "area" in str(schema)


# ---------------------------------------------------------------------------
# classify_llm — error / fallback paths
# ---------------------------------------------------------------------------

def test_classify_llm_falls_back_on_exception():
    """Any exception from the LLM client → fallback to classify(), no raise."""
    m = _load_triage()
    bad = make_error_client(RuntimeError("network error"))

    # "isolation" text → deterministic classify gives critical/isolation
    result = m.classify_llm(
        "data from another company visible — isolation leak", "bug", client=bad
    )

    assert result["severity"] == "critical"
    assert result["area"] == "isolation"


def test_classify_llm_falls_back_on_out_of_enum_severity():
    """Out-of-enum severity → fallback to classify(), no raise."""
    m = _load_triage()
    bad_enum = make_fake_client({"severity": "ULTRA_CRITICAL", "area": "other"})

    result = m.classify_llm("some error", "bug", client=bad_enum)

    assert result["severity"] in {"low", "medium", "high", "critical"}
    assert result["area"] in {"ui", "api", "isolation", "feature", "other"}


def test_classify_llm_falls_back_on_out_of_enum_area():
    """Out-of-enum area → fallback to classify(), no raise."""
    m = _load_triage()
    bad_enum = make_fake_client({"severity": "high", "area": "backend"})  # 'backend' not valid

    result = m.classify_llm("500 server error", "bug", client=bad_enum)

    assert result["area"] in {"ui", "api", "isolation", "feature", "other"}


def test_classify_llm_falls_back_on_missing_key():
    """Missing 'severity' or 'area' key in response → fallback, no raise."""
    m = _load_triage()
    incomplete = make_fake_client({"severity": "high"})  # no 'area'

    result = m.classify_llm("500 server error", "bug", client=incomplete)

    assert "severity" in result
    assert "area" in result


def test_classify_llm_never_raises_on_timeout():
    """TimeoutError from client → fallback, never propagates."""
    m = _load_triage()
    bad = make_error_client(TimeoutError("timed out"))

    result = m.classify_llm("slow UI", "other", client=bad)

    assert "severity" in result
    assert "area" in result


# ---------------------------------------------------------------------------
# classify_best — flag OFF (default)
# ---------------------------------------------------------------------------

def test_classify_best_flag_off_by_default():
    """With no env var set, classify_best uses the deterministic path."""
    m = _load_triage()

    # Ensure env var is unset
    os.environ.pop("FEEDBACK_LLM_TRIAGE", None)

    result = m.classify_best(
        "cross-company data visible — isolation leak", "bug", db=None
    )
    assert result["severity"] == "critical"
    assert result["area"] == "isolation"


def test_classify_best_flag_off_llm_never_called(monkeypatch):
    """When the flag is OFF, classify_llm must never be invoked — 0 LLM calls."""
    m = _load_triage()
    os.environ.pop("FEEDBACK_LLM_TRIAGE", None)

    llm_calls = []
    original = m.classify_llm

    def tracked(*args, **kwargs):
        llm_calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(m, "classify_llm", tracked)

    m.classify_best("error occurred", "bug", db=None)
    assert len(llm_calls) == 0, "classify_llm must NOT be called when flag is OFF"


def test_classify_best_env_zero_string_is_off(monkeypatch):
    """Env var = '0' must be treated as OFF."""
    m = _load_triage()
    llm_calls = []
    original = m.classify_llm

    def tracked(*args, **kwargs):
        llm_calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(m, "classify_llm", tracked)
    monkeypatch.setenv("FEEDBACK_LLM_TRIAGE", "0")

    m.classify_best("error", "bug", db=None)
    assert len(llm_calls) == 0


# ---------------------------------------------------------------------------
# classify_best — flag ON
# ---------------------------------------------------------------------------

def test_classify_best_flag_on_uses_classify_llm(monkeypatch):
    """When FEEDBACK_LLM_TRIAGE=1, classify_best delegates to classify_llm."""
    m = _load_triage()
    monkeypatch.setenv("FEEDBACK_LLM_TRIAGE", "1")

    fake = make_fake_client({"severity": "medium", "area": "ui"})

    result = m.classify_best("spinner is frozen", "bug", db=None, client=fake)

    assert result == {"severity": "medium", "area": "ui"}
    assert len(fake.calls) == 1, "classify_llm (and thus the LLM client) must be called"


def test_classify_best_flag_on_truthy_string(monkeypatch):
    """Any truthy string besides '0'/'false'/'off' enables LLM."""
    m = _load_triage()
    monkeypatch.setenv("FEEDBACK_LLM_TRIAGE", "true")

    fake = make_fake_client({"severity": "low", "area": "feature"})
    result = m.classify_best("add dark mode", "idea", db=None, client=fake)

    assert result == {"severity": "low", "area": "feature"}


# ---------------------------------------------------------------------------
# classify_best — fail-open (never raises)
# ---------------------------------------------------------------------------

def test_classify_best_never_raises_when_llm_fails(monkeypatch):
    """Even if classify_llm raises internally, classify_best must not raise."""
    m = _load_triage()
    monkeypatch.setenv("FEEDBACK_LLM_TRIAGE", "1")

    boom = make_error_client(RuntimeError("catastrophic failure"))

    # Should not raise — fallback path in classify_llm catches it
    result = m.classify_best("spinner broken", "bug", db=None, client=boom)
    assert "severity" in result
    assert "area" in result


# ---------------------------------------------------------------------------
# admin_settings — KNOWN_KEYS allowlist
# ---------------------------------------------------------------------------

def test_feedback_llm_triage_in_known_keys():
    """'feedback_llm_triage' must be present in admin_settings.KNOWN_KEYS."""
    from backend.app.routers.admin_settings import KNOWN_KEYS, DEFAULTS
    assert "feedback_llm_triage" in KNOWN_KEYS, (
        "feedback_llm_triage must be in KNOWN_KEYS so the AI-controls panel can toggle it"
    )
    assert "feedback_llm_triage" in DEFAULTS
    assert DEFAULTS["feedback_llm_triage"] == "0", "Default must be OFF"
