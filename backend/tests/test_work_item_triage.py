"""
Mission Control P1 — demand triage. Deterministic-first classification of a demand
into kind / priority / complexity / auto_fixable (no LLM key required). auto_fixable
mirrors the autofix blocklist: only trivial, non-sensitive demands qualify.
"""
from backend.app.services.work_item_triage import classify_demand


def test_bug_keywords_classify_as_bug():
    out = classify_demand("App crashes on save", "I get a 500 error and it crashes every time")
    assert out["kind"] == "bug"


def test_idea_keywords_classify_as_idea():
    out = classify_demand("Feature request", "It would be nice if you could add dark mode")
    assert out["kind"] == "idea"
    assert out["priority"] == "P3"  # ideas default low


def test_kind_hint_overrides_inference():
    out = classify_demand("Something", "ambiguous text", kind_hint="quality")
    assert out["kind"] == "quality"


def test_typo_is_trivial_and_auto_fixable():
    out = classify_demand("Typo on dashboard", "the label says 'Recieve' instead of 'Receive'")
    assert out["complexity"] == "trivial"
    assert out["auto_fixable"] is True


def test_sensitive_demand_is_never_auto_fixable():
    # Even a 'trivial'-sounding wording change to an auth/billing surface is blocked.
    out = classify_demand("Fix wording", "change the label text on the billing payment auth screen")
    assert out["auto_fixable"] is False
    assert out["blocked"] is True


def test_crash_is_high_priority():
    out = classify_demand("Site down", "the whole app is broken and nobody can log in")
    assert out["priority"] in ("P0", "P1")


def test_returns_a_rationale_string():
    out = classify_demand("x", "y")
    assert isinstance(out["rationale"], str) and out["rationale"]
