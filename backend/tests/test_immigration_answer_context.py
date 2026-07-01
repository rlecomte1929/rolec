"""
Slice 3 — build an ANONYMISED applicant-context string from the case profile
(family situation: spouse + dependents) for injection into the grounded answer.
Anonymised by construction (counts + booleans, no names/DOB/passport) and passed
through mask_pii as defense-in-depth. Returns None when there's nothing useful.
"""
import backend.app.services.immigration_answer_context as ctx


def test_spouse_and_dependents(monkeypatch):
    monkeypatch.setattr(ctx, "_load_profile_for_case", lambda cid: {"spouse_nationality": "IN", "dependents": [{}, {}]})
    assert ctx.build_applicant_context("c1") == "Relocating with a spouse and 2 dependent(s)"


def test_dependents_only(monkeypatch):
    monkeypatch.setattr(ctx, "_load_profile_for_case", lambda cid: {"dependents": [{}]})
    assert ctx.build_applicant_context("c1") == "Relocating with 1 dependent(s)"


def test_spouse_only(monkeypatch):
    monkeypatch.setattr(ctx, "_load_profile_for_case", lambda cid: {"spouse_nationality": "FR", "dependents": []})
    assert ctx.build_applicant_context("c1") == "Relocating with a spouse"


def test_none_when_no_family_signal(monkeypatch):
    monkeypatch.setattr(ctx, "_load_profile_for_case", lambda cid: {"nationality": "IN"})
    assert ctx.build_applicant_context("c1") is None


def test_none_when_no_profile(monkeypatch):
    monkeypatch.setattr(ctx, "_load_profile_for_case", lambda cid: None)
    assert ctx.build_applicant_context("c1") is None
