"""AIQ-2370 — RFQ in-app + outbox notifications.

Covers the card validation:
  * supplier submit → employee + HR, type rfq.quote_received
  * HR accept → employee, type rfq.quote_validated
  * create_rfq → employee rfq.sent listing contacted / not_contacted
  * hr_quotes_ready fires once per RFQ when all recipients replied OR employee proposed
  * notify helpers never raise
  * wiring in create_rfq / submit_supplier_quote / propose / accept (source guards)
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from backend.app.services import rfq_notifications as rn


class _FakeConn:
    def __init__(self, already: bool = False):
        self.already = already

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def execute(self, *_a, **_k):
        row = (1,) if self.already else None
        result = MagicMock()
        result.first.return_value = row
        result.mappings.return_value.first.return_value = None
        return result


class _FakeEngine:
    def __init__(self, already: bool = False):
        self.already = already

    def connect(self):
        return _FakeConn(self.already)

    def begin(self):
        return _FakeConn(self.already)


class FakeDB:
    def __init__(self, *, already_ready: bool = False):
        self.engine = _FakeEngine(already=already_ready)
        self.calls: List[Dict[str, Any]] = []
        self.rfq: Dict[str, Any] = {
            "id": "rfq-1",
            "rfq_ref": "RFQ-TEST-1",
            "case_id": "case-1",
            "items": [{"service_key": "movers"}],
            "recipients": [
                {"id": "r1", "vendor_id": "v1", "status": "replied", "quote_submitted_at": "2026-09-12"},
            ],
        }
        self.assignment = {
            "id": "assign-1",
            "employee_user_id": "emp-1",
            "hr_user_id": "hr-1",
        }
        self.quotes: List[Dict[str, Any]] = [
            {"id": "q-1", "vendor_id": "v1", "total_amount": 1200, "currency": "EUR"},
        ]
        self.users = {
            "emp-1": {"id": "emp-1", "full_name": "Alex Employee", "email": "alex@probe.test"},
            "hr-1": {"id": "hr-1", "full_name": "Pat HR", "email": "hr@probe.test"},
        }

    def get_rfq(self, rfq_id: str, request_id: Optional[str] = None):
        return dict(self.rfq)

    def get_assignment_by_case_id(self, case_id: str, request_id: Optional[str] = None):
        return dict(self.assignment)

    def get_user_by_id(self, user_id: str):
        return self.users.get(user_id)

    def list_quotes_for_rfq(self, rfq_id: str, request_id: Optional[str] = None):
        return list(self.quotes)

    def create_notification_with_preferences(self, **kwargs):
        self.calls.append(kwargs)
        return "nid-1"


@pytest.fixture
def fake_db(monkeypatch):
    db = FakeDB()
    monkeypatch.setattr(rn, "_main_db", lambda: db)
    return db


def test_quote_received_notifies_employee_and_hr(fake_db):
    fake_db.rfq["recipients"] = [
        {"id": "r1", "vendor_id": "v1", "status": "sent", "quote_submitted_at": None},
        {"id": "r2", "vendor_id": "v2", "status": "sent", "quote_submitted_at": None},
    ]
    rn.notify_quote_received("rfq-1", {"id": "q-1", "vendor_id": "v1", "total_amount": 10, "currency": "EUR"})
    types_by_user = {(c["user_id"], c["type_"]) for c in fake_db.calls}
    assert ("emp-1", rn.TYPE_QUOTE_RECEIVED) in types_by_user
    assert ("hr-1", rn.TYPE_QUOTE_RECEIVED) in types_by_user
    assert any("RFQ-TEST-1" in (c["title"] or "") or "quote" in (c["title"] or "").lower() for c in fake_db.calls)


def test_quote_validated_notifies_employee(fake_db):
    rn.notify_quote_validated("rfq-1", "q-1")
    assert len(fake_db.calls) == 1
    call = fake_db.calls[0]
    assert call["user_id"] == "emp-1"
    assert call["type_"] == rn.TYPE_QUOTE_VALIDATED
    assert call["case_id"] == "case-1"
    assert call["assignment_id"] == "assign-1"


def test_rfq_sent_lists_contacted_and_not_contacted(fake_db):
    rn.notify_rfq_sent(
        "rfq-1",
        contacted=["Acme Movers"],
        not_contacted=[{"supplier": "No Email Ltd", "reason": "no address"}],
    )
    assert len(fake_db.calls) == 1
    call = fake_db.calls[0]
    assert call["user_id"] == "emp-1"
    assert call["type_"] == rn.TYPE_RFQ_SENT
    assert call["metadata"]["contacted"] == ["Acme Movers"]
    assert call["metadata"]["not_contacted"][0]["supplier"] == "No Email Ltd"
    assert "Acme Movers" in (call["title"] + (call["body"] or "") + str(call["metadata"]))


def test_quotes_ready_fires_once_when_all_replied(fake_db, monkeypatch):
    monkeypatch.setattr(rn, "_quotes_ready_already_sent", lambda _rid: False)
    rn.notify_quotes_ready("rfq-1")
    ready = [c for c in fake_db.calls if c["type_"] == rn.TYPE_QUOTES_READY]
    assert len(ready) == 1
    assert ready[0]["user_id"] == "hr-1"

    fake_db.calls.clear()
    monkeypatch.setattr(rn, "_quotes_ready_already_sent", lambda _rid: True)
    rn.notify_quotes_ready("rfq-1")
    assert fake_db.calls == []


def test_quotes_ready_on_employee_propose(fake_db, monkeypatch):
    fake_db.rfq["recipients"] = [
        {"id": "r1", "vendor_id": "v1", "status": "sent", "quote_submitted_at": None},
    ]
    fake_db.rfq["preferred_quote_id"] = "q-1"
    monkeypatch.setattr(rn, "_quotes_ready_already_sent", lambda _rid: False)
    rn.notify_quotes_ready("rfq-1")
    assert any(c["type_"] == rn.TYPE_QUOTES_READY for c in fake_db.calls)


def test_quote_received_triggers_quotes_ready_when_all_replied(fake_db, monkeypatch):
    monkeypatch.setattr(rn, "_quotes_ready_already_sent", lambda _rid: False)
    fake_db.rfq["recipients"] = [
        {"id": "r1", "vendor_id": "v1", "status": "replied", "quote_submitted_at": "now"},
    ]
    rn.notify_quote_received("rfq-1", {"id": "q-1", "vendor_id": "v1"})
    types = [c["type_"] for c in fake_db.calls]
    assert types.count(rn.TYPE_QUOTE_RECEIVED) == 2  # employee + HR
    assert types.count(rn.TYPE_QUOTES_READY) == 1


def test_notify_never_raises(fake_db, monkeypatch):
    def boom(**_k):
        raise RuntimeError("db down")

    fake_db.create_notification_with_preferences = boom
    rn.notify_rfq_sent("rfq-1")
    rn.notify_quote_received("rfq-1", {"id": "q-1"})
    rn.notify_quotes_ready("rfq-1")
    rn.notify_quote_validated("rfq-1", "q-1")


def test_resolves_recipients_from_case_assignment(fake_db):
    rn.notify_quote_received("rfq-1", {"id": "q-1", "vendor_id": "v1"})
    assert fake_db.calls
    assert all(c["case_id"] == "case-1" for c in fake_db.calls)
    assert all(c["assignment_id"] == "assign-1" for c in fake_db.calls)


def _src(rel: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "..", rel)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_create_rfq_wires_notify_rfq_sent():
    src = _src("backend/main.py")
    start = src.index("def create_rfq(")
    end = src.index("\n@app.", start + 1)
    block = src[start:end]
    assert "notify_rfq_sent" in block
    assert "try:" in block
    assert "contacted" in block and "not_contacted" in block


def test_submit_supplier_quote_wires_notify_and_analytics():
    src = _src("backend/app/routers/supplier_rfq.py")
    start = src.index("def submit_supplier_quote(")
    end = src.index("\n# ─", start + 1)
    block = src[start:end]
    assert "notify_quote_received" in block
    assert "EVENT_QUOTE_RECEIVED" in block
    assert "try:" in block


def test_propose_wires_quotes_ready():
    src = _src("backend/main.py")
    start = src.index("def propose_quote(")
    end = src.index("\n@app.", start + 1)
    assert "notify_quotes_ready" in src[start:end]


def test_accept_wires_quote_validated():
    src = _src("backend/main.py")
    start = src.index("def accept_quote(")
    end = src.index("\n# ---------------------------------------------------------------------------", start + 1)
    block = src[start:end]
    assert "notify_quote_validated" in block
