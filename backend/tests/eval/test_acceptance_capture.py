# WS-D — acceptance-capture regression. The supplier_selected and
# quote_accepted analytics events ARE already emitted from backend/main.py
# (POST /api/rfqs and PATCH /api/rfqs/{rfq_id}/quotes/{quote_id}/accept). These
# tests lock that behavior: they drive the route functions directly with the DB
# layer and auth gate stubbed, and assert the events fire with the right shape.
#
# emit_event is patched on backend.app.services.analytics_service because the
# routes do a call-time `from .app.services.analytics_service import emit_event`,
# which resolves the (patched) module attribute.
from __future__ import annotations

import os

import pytest

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import backend.main as m  # noqa: E402  (env must be set before import)
from backend.app.services import analytics_service  # noqa: E402


class _FakeReq:
    """Minimal Request stand-in: routes only read request.state.request_id."""

    class _State:
        request_id = "test-req-1"

    state = _State()


@pytest.fixture
def captured_events(monkeypatch):
    events = []

    def _capture(event_name, **kwargs):
        events.append((event_name, kwargs))

    monkeypatch.setattr(analytics_service, "emit_event", _capture)
    return events


def test_validate_quote_emits_quote_accepted(monkeypatch, captured_events):
    # AIQ-1524: accepting a quote is the PAYER's spend approval, so it is HR-only. This test
    # previously drove it as an EMPLOYEE ("emp-1"/"employee") — locking in the very hole that
    # task removed. The event contract is unchanged; the actor is not.
    monkeypatch.setattr(
        m.db,
        "get_rfq",
        lambda rfq_id, request_id=None: {
            "case_id": "case-1",
            "canonical_case_id": "canon-1",
        },
    )
    monkeypatch.setattr(m, "_require_case_id_assignment_visible", lambda case_id, user: {"id": "a-1"})
    monkeypatch.setattr(
        m.db,
        "validate_rfq_quote",
        lambda rfq_id, quote_id, user_id, reason, request_id=None: {
            "ok": True,
            "quote_id": quote_id,
            "rfq_id": rfq_id,
            "quote": {"id": quote_id, "vendor_id": "v-1", "status": "accepted"},
            "cost_attributed": True,
            "cost_not_attributed_reason": None,
            "services_costed": ["movers"],
        },
    )

    user = {"id": "hr-1", "role": "HR"}
    out = m.accept_quote("rfq-1", "q-1", _FakeReq(), user)
    assert out["ok"] is True
    assert out["validation"]["cost_attributed"] is True

    names = [e[0] for e in captured_events]
    assert analytics_service.EVENT_QUOTE_ACCEPTED in names
    kwargs = dict(captured_events[names.index(analytics_service.EVENT_QUOTE_ACCEPTED)][1])
    assert kwargs["case_id"] == "case-1"
    assert kwargs["user_id"] == "hr-1"
    assert kwargs["extra"]["rfq_id"] == "rfq-1"
    assert kwargs["extra"]["quote_id"] == "q-1"
    assert kwargs["extra"]["cost_attributed"] is True


def test_create_rfq_emits_supplier_selected_per_vendor(monkeypatch, captured_events):
    monkeypatch.setattr(
        m,
        "_require_assignment_visibility",
        lambda case_id, user: {"id": "a-1", "case_id": case_id, "company_id": "co-1"},
    )
    monkeypatch.setattr(
        m.db,
        "validate_vendor_ids",
        lambda vendor_ids, request_id=None: (list(vendor_ids), []),
    )
    monkeypatch.setattr(
        m.db,
        "create_rfq",
        lambda **kwargs: {"id": "rfq-9", "rfq_ref": "RFQ-9"},
    )

    payload = m.RfqCreatePayload(
        case_id="case-7",
        items=[m.RfqItemInput(service_key="movers", requirements={})],
        vendor_ids=["v-1", "v-2"],
    )
    user = {"id": "emp-2", "role": "employee"}
    out = m.create_rfq(payload, _FakeReq(), user)
    assert out["ok"] is True

    selected = [e for e in captured_events if e[0] == analytics_service.EVENT_SUPPLIER_SELECTED]
    assert len(selected) == 2  # one per vendor
    vendor_ids = {e[1]["extra"]["vendor_id"] for e in selected}
    assert vendor_ids == {"v-1", "v-2"}
    for _, kwargs in selected:
        assert kwargs["case_id"] == "case-7"
        assert kwargs["extra"]["rfq_id"] == "rfq-9"

    assert any(e[0] == analytics_service.EVENT_RFQ_CREATED for e in captured_events)
