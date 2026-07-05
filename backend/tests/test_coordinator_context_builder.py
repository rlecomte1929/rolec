"""AIQ-1414 Phase 1 — unit tests for the read-only coordinator context builder.

Pure/DB-free: exercises the shaping + PII masking + bounds + flag gating without a
database (the flag/fetch dependencies are monkeypatched).
"""

import json

from backend.app.services import coordinator_context_builder as ccb


def _snapshot(**overrides):
    """A synthetic CaseContextService snapshot with reliably-maskable PII."""
    snap = {
        "meta": {"ok": True, "case_id": "c-1", "case_found": True, "error": None},
        "case": {
            "id": "c-1",
            "company_id": "acme",
            "employee_user_id": "u-1",
            "origin_country": "FR",
            "destination_country": "DE",
            "case_type": "long_term",
            "metadata": {"note": "IBAN FR7630006000011234567890189 on file"},
            "created_at": "2026-07-01T00:00:00+00:00",
            "updated_at": "2026-07-04T00:00:00+00:00",
        },
        "people": [
            {"id": "p-1", "role": "assignee",
             "metadata": {"email": "sarah.chen@acme.com", "phone": "+33 6 12 34 56 78"}},
        ],
        "documents": [
            {"id": "d-1", "document_key": "passport_scan", "document_status": "verified",
             "metadata": {"filename": "passport-sarah.pdf"}},
        ],
        "evaluations": [
            {"requirement_code": "VISA-001", "evaluation_status": "missing",
             "reason_text": "Email john.doe@example.com to chase the passport."},
        ],
    }
    snap.update(overrides)
    return snap


def test_structured_fields_preserved():
    out = ccb.shape_and_mask(_snapshot())
    assert out["case"]["origin_country"] == "FR"
    assert out["case"]["destination_country"] == "DE"
    assert out["case"]["case_type"] == "long_term"
    assert out["documents"][0]["status"] == "verified"
    assert out["requirements"][0]["code"] == "VISA-001"
    assert out["requirements"][0]["status"] == "missing"


def test_pii_is_masked_everywhere():
    out = ccb.shape_and_mask(_snapshot())
    blob = json.dumps(out)
    # reliably-detected PII must not survive anywhere in the serialized context
    assert "sarah.chen@acme.com" not in blob
    assert "john.doe@example.com" not in blob
    assert "+33 6 12 34 56 78" not in blob
    assert "FR7630006000011234567890189" not in blob
    # and masking actually happened
    assert "REDACTED" in blob
    assert out["_meta"]["pii_masked"] is True


def test_bounds_are_enforced():
    snap = _snapshot(
        people=[{"id": f"p-{i}", "role": "dep", "metadata": {}} for i in range(100)],
        documents=[{"id": f"d-{i}", "document_key": f"k{i}", "document_status": "pending",
                    "metadata": {}} for i in range(100)],
        evaluations=[{"requirement_code": f"R-{i}", "evaluation_status": "unknown",
                      "reason_text": ""} for i in range(100)],
    )
    out = ccb.shape_and_mask(snap)
    assert len(out["people"]) == ccb._MAX_PEOPLE
    assert len(out["documents"]) == ccb._MAX_DOCUMENTS
    assert len(out["requirements"]) == ccb._MAX_REQUIREMENTS
    assert out["_meta"]["counts"]["people"] == ccb._MAX_PEOPLE


def test_case_not_found_yields_null_case():
    snap = {"meta": {"ok": True, "case_found": False}, "case": None,
            "people": [], "documents": [], "evaluations": []}
    out = ccb.shape_and_mask(snap)
    assert out["case"] is None
    assert out["_meta"]["case_found"] is False


def test_phase2_slots_are_empty_and_marked():
    out = ccb.shape_and_mask(_snapshot())
    assert out["rolling_summary"] == ""
    assert out["recent_events"] == []
    assert out["_meta"]["event_spine"] == "deferred_phase2"


def test_build_returns_none_when_flag_off(monkeypatch):
    monkeypatch.setattr(ccb, "coordinator_enabled", lambda **_: False)
    called = {"fetch": False}

    def _boom(*_a, **_k):
        called["fetch"] = True
        raise AssertionError("fetch_case_context must not run when flag is OFF")

    monkeypatch.setattr(ccb, "fetch_case_context", _boom)
    assert ccb.build_coordinator_context(object(), "c-1") is None
    assert called["fetch"] is False


def test_build_shapes_snapshot_when_flag_on(monkeypatch):
    monkeypatch.setattr(ccb, "coordinator_enabled", lambda **_: True)
    monkeypatch.setattr(ccb, "fetch_case_context", lambda _conn, _cid: _snapshot())
    out = ccb.build_coordinator_context(object(), "c-1")
    assert out is not None
    assert out["case"]["company_id"] == "acme"
    assert "sarah.chen@acme.com" not in json.dumps(out)
