"""resolve_notification must tolerate a jsonb payload (dict) as well as a string.

ops_notifications.payload_json is a jsonb column; the Supabase client returns it
already parsed as a dict. The old json.loads(dict) raised, so
resolve_notification(..., reason=...) crashed. This pins both shapes.
"""
from __future__ import annotations

import json
from unittest import mock

from backend.app.services import ops_notification_service as svc


class _FakeChain:
    """Records the `update(...)` payload; supports .update().eq().execute()."""
    def __init__(self, sink):
        self._sink = sink

    def update(self, updates):
        self._sink["updates"] = updates
        return self

    def eq(self, *_a, **_k):
        return self

    def execute(self, *_a, **_k):
        return None


class _FakeSupabase:
    def __init__(self, sink):
        self._sink = sink

    def table(self, *_a, **_k):
        return _FakeChain(self._sink)


def _resolve_with(monkeypatch, payload_value):
    sink: dict = {}
    notif = {"id": "n1", "status": "open", "payload_json": payload_value}
    monkeypatch.setattr(svc, "get_notification_by_id", lambda nid: notif)
    monkeypatch.setattr(svc, "_get_supabase", lambda: _FakeSupabase(sink))
    monkeypatch.setattr(svc, "_log_event", lambda *a, **k: None)
    svc.resolve_notification("n1", "actor-1", reason="looked into it")
    # The write serialises the merged payload back out.
    return json.loads(sink["updates"]["payload_json"])


def test_resolve_with_jsonb_dict_payload_does_not_crash(monkeypatch):
    out = _resolve_with(monkeypatch, {"kind": "over_cap", "amount": 3000})
    assert out["kind"] == "over_cap" and out["amount"] == 3000
    assert out["resolution_reason"] == "looked into it"


def test_resolve_with_json_string_payload(monkeypatch):
    out = _resolve_with(monkeypatch, '{"kind": "over_cap"}')
    assert out["kind"] == "over_cap"
    assert out["resolution_reason"] == "looked into it"


def test_resolve_with_null_payload(monkeypatch):
    out = _resolve_with(monkeypatch, None)
    assert out == {"resolution_reason": "looked into it"}
