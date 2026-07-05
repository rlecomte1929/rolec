"""
AIQ-1415 — Natural-Language Policy Builder: the generator is read-only + safety-gated.

Service tests (hermetic — the LLM is stubbed) cover: full-canonical expansion, covered
mapping, PII masking before egress, dropping hallucinated/invalid rows, and the kill-switch.
Endpoint tests cover the per-account feature-flag gate (403 off / 200 on) with the generate
call stubbed. Generate never writes, so no DB is required.
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import nl_policy_builder as nlpb  # noqa: E402


def _resp(benefits):
    return {"benefits": benefits}


@pytest.fixture(autouse=True)
def _llm_enabled(monkeypatch):
    # ensure the kill-switch is OFF unless a test sets it
    monkeypatch.delenv("RELOPASS_POLICY_LLM_DISABLED", raising=False)


# ── service ──────────────────────────────────────────────────────────────────

def test_generates_full_canonical_matrix_and_marks_covered(monkeypatch):
    monkeypatch.setattr(nlpb, "claude_complete_sync", lambda **kw: _resp([
        {"benefit_key": "temporary_living", "covered": True, "value_type": "currency",
         "amount_value": 3000, "currency_code": "USD", "unit_frequency": "monthly"},
        {"benefit_key": "shipment_of_goods", "covered": True, "value_type": "none"},
    ]))
    out = nlpb.generate_policy_config_from_text("temp housing $3000/mo plus shipment of goods")

    assert out["generated"] is True
    assert len(out["categories"]) == 6
    assert sum(len(c["benefits"]) for c in out["categories"]) == 31  # full canonical set
    covered = {b["benefit_key"] for c in out["categories"] for b in c["benefits"] if b["covered"]}
    assert covered == {"temporary_living", "shipment_of_goods"}
    assert out["covered_count"] == 2
    tl = next(b for c in out["categories"] for b in c["benefits"] if b["benefit_key"] == "temporary_living")
    assert tl["value_type"] == "currency" and tl["amount_value"] == 3000
    assert tl["currency_code"] == "USD" and tl["unit_frequency"] == "monthly"
    # each row carries the fields put_draft expects
    assert tl["benefit_label"] and tl["category"] == "relocation_assistance"


def test_masks_pii_before_llm(monkeypatch):
    captured = {}
    monkeypatch.setattr(nlpb, "claude_complete_sync", lambda **kw: captured.update(kw) or _resp([]))
    nlpb.generate_policy_config_from_text("contact jane.doe@example.com about our policy")
    assert "jane.doe@example.com" not in captured["user"]  # masked before egress


def test_unrecognized_benefit_key_dropped_to_warnings(monkeypatch):
    monkeypatch.setattr(nlpb, "claude_complete_sync",
                        lambda **kw: _resp([{"benefit_key": "free_ponies", "covered": True}]))
    out = nlpb.generate_policy_config_from_text("free ponies for everyone")
    assert out["covered_count"] == 0
    assert any("free_ponies" in w for w in out["warnings"])


def test_invalid_value_dropped_to_warnings(monkeypatch):
    # value_type outside the PolicyConfigValueType enum → PolicyConfigBenefitWrite rejects it
    monkeypatch.setattr(nlpb, "claude_complete_sync",
                        lambda **kw: _resp([{"benefit_key": "storage", "covered": True, "value_type": "bananas"}]))
    out = nlpb.generate_policy_config_from_text("storage measured in bananas")
    assert out["covered_count"] == 0
    assert any("storage" in w.lower() for w in out["warnings"])
    # storage still appears in the matrix, just not covered
    storage = next(b for c in out["categories"] for b in c["benefits"] if b["benefit_key"] == "storage")
    assert storage["covered"] is False


def test_kill_switch_skips_llm(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(nlpb, "claude_complete_sync",
                        lambda **kw: called.__setitem__("n", called["n"] + 1) or _resp([]))
    monkeypatch.setenv("RELOPASS_POLICY_LLM_DISABLED", "1")
    out = nlpb.generate_policy_config_from_text("anything")
    assert out["generated"] is False and called["n"] == 0


def test_empty_text_no_llm(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(nlpb, "claude_complete_sync",
                        lambda **kw: called.__setitem__("n", called["n"] + 1) or _resp([]))
    out = nlpb.generate_policy_config_from_text("   ")
    assert out["generated"] is False and called["n"] == 0


# ── endpoint (feature-flag gate) ─────────────────────────────────────────────

def _hr_app(monkeypatch):
    import backend.app.routers.policy_config as pc
    from backend.app.auth_deps import get_current_user
    monkeypatch.setattr(pc, "_policy_matrix_company_hr", lambda user, cid: "c1")
    app = FastAPI()
    app.include_router(pc.hr_policy_config_router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "hr-1", "role": "HR", "roles": ["HR"]}
    return app


def test_endpoint_flag_off_returns_403(monkeypatch):
    import backend.app.services.feature_flags as ff
    monkeypatch.setattr(ff, "is_flag_enabled_for", lambda account_id, key: False)
    client = TestClient(_hr_app(monkeypatch))
    r = client.post("/api/hr/policy-config/generate", json={"text": "lump sum for domestic"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "feature_disabled"


def test_endpoint_flag_on_returns_candidate(monkeypatch):
    import backend.app.services.feature_flags as ff
    monkeypatch.setattr(ff, "is_flag_enabled_for", lambda account_id, key: True)
    monkeypatch.setattr(nlpb, "generate_policy_config_from_text",
                        lambda text: {"categories": [{"category_key": "relocation_assistance", "benefits": []}],
                                      "warnings": [], "generated": True, "covered_count": 1})
    client = TestClient(_hr_app(monkeypatch))
    r = client.post("/api/hr/policy-config/generate", json={"text": "lump sum + housing"})
    assert r.status_code == 200
    assert r.json()["generated"] is True


def test_endpoint_requires_text(monkeypatch):
    import backend.app.services.feature_flags as ff
    monkeypatch.setattr(ff, "is_flag_enabled_for", lambda account_id, key: True)
    client = TestClient(_hr_app(monkeypatch))
    r = client.post("/api/hr/policy-config/generate", json={"text": "   "})
    assert r.status_code == 400
