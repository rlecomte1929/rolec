"""AIQ-1414 Phase 1–2a — unit tests for the read-only coordinator context builder.

Pure/DB-free: exercises shaping + PII masking + bounds + flag gating + the HR-surface
resolver wiring, all without a database (the flag / db / fetch dependencies are
monkeypatched).
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


# ── pure shaping / masking ────────────────────────────────────────────────────


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
    assert "sarah.chen@acme.com" not in blob
    assert "john.doe@example.com" not in blob
    assert "+33 6 12 34 56 78" not in blob
    assert "FR7630006000011234567890189" not in blob
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


def test_case_not_found_yields_null_case():
    out = ccb.shape_and_mask(ccb._empty_snapshot())
    assert out["case"] is None
    assert out["_meta"]["case_found"] is False


def test_slots_default_when_no_spine():
    out = ccb.shape_and_mask(_snapshot())  # no events/notes passed
    assert out["rolling_summary"] == ""
    assert out["recent_events"] == []
    assert out["_meta"]["event_spine"] == "none"


def test_events_and_notes_masked_bounded_and_sorted():
    events = [{"event_type": "visa_update", "actor_principal_id": "system",
               "description": "Call sarah.chen@acme.com about it",
               "payload": {"phone": "+33 6 12 34 56 78"},
               "created_at": "2026-07-03T10:00:00+00:00"} for _ in range(50)]
    notes = [{"author_name": "HR", "body": "Ping bob@acme.com",
              "created_at": "2026-07-04T10:00:00+00:00"} for _ in range(50)]
    out = ccb.shape_and_mask(_snapshot(), events=events, notes=notes)
    assert out["_meta"]["event_spine"] == "wired"
    # per-kind caps → merged, then overall cap
    assert len(out["recent_events"]) == ccb._MAX_EVENTS
    blob = json.dumps(out["recent_events"])
    assert "sarah.chen@acme.com" not in blob
    assert "bob@acme.com" not in blob
    assert "+33 6 12 34 56 78" not in blob
    # newest-first: the 2026-07-04 notes sort ahead of the 2026-07-03 events
    assert out["recent_events"][0]["kind"] == "note"


# ── flag gating / low-level builder ───────────────────────────────────────────


def test_low_level_build_returns_none_when_flag_off(monkeypatch):
    monkeypatch.setattr(ccb, "coordinator_enabled", lambda **_: False)
    monkeypatch.setattr(ccb, "fetch_case_context",
                        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not run")))
    assert ccb.build_coordinator_context(object(), "mob-1") is None


def test_low_level_build_shapes_when_flag_on(monkeypatch):
    monkeypatch.setattr(ccb, "coordinator_enabled", lambda **_: True)
    monkeypatch.setattr(ccb, "fetch_case_context", lambda _conn, _mid: _snapshot())
    out = ccb.build_coordinator_context(object(), "mob-1")
    assert out is not None and out["case"]["company_id"] == "acme"


# ── HR-surface orchestrator (resolver wiring) ─────────────────────────────────


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _FakeEngine:
    def connect(self):
        return _FakeConn()


class _FakeDB:
    def __init__(self, assignment=None, mobility_id=None, events=None):
        self._assignment = assignment
        self._mobility = mobility_id
        self._events = events or []
        self.engine = _FakeEngine()

    def get_assignment_by_case_id(self, _cid):
        return self._assignment

    def get_assignment_by_id(self, _cid):
        return None

    def get_mobility_case_id_for_assignment(self, _aid):
        return self._mobility

    def list_case_events(self, _cid):
        return self._events


def test_build_for_case_returns_none_when_flag_off(monkeypatch):
    monkeypatch.setattr(ccb, "coordinator_enabled", lambda **_: False)
    monkeypatch.setattr(ccb, "_get_db",
                        lambda: (_ for _ in ()).throw(AssertionError("must not resolve db")))
    assert ccb.build_coordinator_context_for_case("hr-case-1") is None


def test_build_for_case_not_found(monkeypatch):
    monkeypatch.setattr(ccb, "coordinator_enabled", lambda **_: True)
    monkeypatch.setattr(ccb, "_get_db", lambda: _FakeDB(assignment=None))
    out = ccb.build_coordinator_context_for_case("hr-case-1")
    assert out is not None
    assert out["case"] is None
    assert out["_meta"]["case_found"] is False
    assert out["_meta"]["reason"] == "assignment_not_found"


def test_build_for_case_wires_the_full_chain(monkeypatch):
    fake = _FakeDB(
        assignment={"id": "asg-1", "company_id": "acme"},
        mobility_id="mob-1",
        events=[{"event_type": "visa_update", "actor_principal_id": "system",
                 "description": "Call sarah.chen@acme.com", "payload": {},
                 "created_at": "2026-07-03T10:00:00+00:00"}],
    )
    monkeypatch.setattr(ccb, "coordinator_enabled", lambda **_: True)
    monkeypatch.setattr(ccb, "_get_db", lambda: fake)
    monkeypatch.setattr(ccb, "fetch_case_context", lambda _conn, mid: _snapshot())
    monkeypatch.setattr(ccb, "_fetch_notes",
                        lambda _conn, _cid, _org: [{"author_name": "HR", "body": "Ping bob@acme.com",
                                                    "created_at": "2026-07-04T10:00:00+00:00"}])
    out = ccb.build_coordinator_context_for_case("hr-case-1")
    assert out is not None
    # the resolver chain is recorded in _meta
    assert out["_meta"]["hr_case_id"] == "hr-case-1"
    assert out["_meta"]["assignment_id"] == "asg-1"
    assert out["_meta"]["mobility_case_id"] == "mob-1"
    assert out["_meta"]["mobility_linked"] is True
    # both spine sources present and masked
    assert {i["kind"] for i in out["recent_events"]} == {"event", "note"}
    blob = json.dumps(out)
    assert "sarah.chen@acme.com" not in blob
    assert "bob@acme.com" not in blob
