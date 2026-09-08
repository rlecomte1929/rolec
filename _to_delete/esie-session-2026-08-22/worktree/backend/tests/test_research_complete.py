"""AIQ-1349 P3 — complete_research_request: strict human-review gate + notify."""
import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest

import backend.app.services.research_request_service as svc


class _Resp:
    def __init__(self, data):
        self.data = data


class _Q:
    def __init__(self, table):
        self.t = table
        self._id = None

    def select(self, *_a, **_k):
        return self

    def eq(self, k, v):
        if k == "id":
            self._id = v
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        if self._id is not None:
            return _Resp([r for r in self.t.rows if r.get("id") == self._id])
        return _Resp(list(self.t.rows))

    def update(self, patch):
        self._patch = patch
        return self

    # update().eq().execute() chain reuse: eq sets _id, execute applies patch
    def _apply(self):
        for r in self.t.rows:
            if r.get("id") == self._id:
                r.update(self._patch)
                return _Resp([r])
        return _Resp([{}])


class _UpdQ(_Q):
    def execute(self):
        if hasattr(self, "_patch"):
            return self._apply()
        return super().execute()


class _Table:
    def __init__(self, rows):
        self.rows = rows


class _SB:
    def __init__(self, rows):
        self._t = _Table(rows)

    def table(self, _name):
        return _UpdQ(self._t)


def _setup(monkeypatch, *, status, qi_status):
    rows = [{
        "id": "rr-1", "requester_user_id": "u-1", "corridor": "US→JP",
        "status": status, "created_queue_item_id": "q-1",
    }]
    monkeypatch.setattr(svc, "_get_supabase", lambda: _SB(rows))
    import backend.app.services.review_queue_service as rq
    monkeypatch.setattr(rq, "get_review_queue_item", lambda i: {"id": i, "status": qi_status})
    monkeypatch.setattr(rq, "resolve_queue_item", lambda *a, **k: {"id": "q-1", "status": "resolved"})
    # capture notifications via the service's patchable indirection
    sent = {}
    monkeypatch.setattr(svc, "_notify", lambda **kw: sent.update(kw) or "n-1")
    return rows, sent


def test_complete_succeeds_when_review_resolved(monkeypatch):
    rows, sent = _setup(monkeypatch, status="in_progress", qi_status="resolved")
    out = svc.complete_research_request(
        request_id="rr-1", actor_user_id="admin-1",
        result_summary="US→JP corridor researched + published", actual_cost=750,
    )
    assert out["status"] == "completed"
    assert out["actual_cost"] == 750
    assert out["result_summary"].startswith("US→JP")
    # requester notified
    assert sent.get("user_id") == "u-1"
    assert sent.get("type_") == "RESEARCH_COMPLETED"


def test_complete_refused_when_review_not_resolved(monkeypatch):
    _setup(monkeypatch, status="in_progress", qi_status="in_progress")
    with pytest.raises(svc.ReviewNotResolvedError):
        svc.complete_research_request(
            request_id="rr-1", actor_user_id="admin-1", result_summary="x",
        )


def test_complete_refused_when_not_in_progress(monkeypatch):
    _setup(monkeypatch, status="pending", qi_status="resolved")
    with pytest.raises(ValueError):
        svc.complete_research_request(
            request_id="rr-1", actor_user_id="admin-1", result_summary="x",
        )
