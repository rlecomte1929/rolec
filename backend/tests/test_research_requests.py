"""AIQ-1349 P2 — research_request_service intake + resolution (mocked Supabase)."""
import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import backend.app.services.research_request_service as svc


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    """Minimal chainable Supabase query double."""
    def __init__(self, table):
        self.table = table
        self._filters = {}

    def select(self, *_a, **_k):
        return self

    def eq(self, k, v):
        self._filters[k] = v
        return self

    def in_(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        # No existing open request (dedup miss) / list returns the store.
        if self.table.name == "research_requests":
            return _Resp(list(self.table.store))
        return _Resp([])

    def insert(self, row):
        saved = dict(row, id=f"rr-{len(self.table.store)+1}")
        self.table.store.append(saved)
        self.table._last_insert = saved
        return _InsertExec(saved)

    def update(self, patch):
        return _UpdateExec(self.table, patch)


class _InsertExec:
    def __init__(self, saved):
        self._saved = saved

    def execute(self):
        return _Resp([self._saved])


class _UpdateExec:
    def __init__(self, table, patch):
        self.table = table
        self.patch = patch
        self._id = None

    def eq(self, k, v):
        if k == "id":
            self._id = v
        return self

    def execute(self):
        for r in self.table.store:
            if r.get("id") == self._id:
                r.update(self.patch)
                return _Resp([r])
        return _Resp([{}])


class _Table:
    def __init__(self, name):
        self.name = name
        self.store: list = []


class _Supabase:
    def __init__(self):
        self._tables = {}

    def table(self, name):
        t = self._tables.setdefault(name, _Table(name))
        return _Query(t)


def _install(monkeypatch):
    sb = _Supabase()
    monkeypatch.setattr(svc, "_get_supabase", lambda: sb)
    # stub the queue-item creation so the service doesn't hit the real review queue
    import backend.app.services.review_queue_service as rq
    monkeypatch.setattr(rq, "create_queue_item_from_research_request", lambda req: {"id": "q-1"})
    return sb


def test_open_request_creates_pending_with_corridor_and_cost(monkeypatch):
    _install(monkeypatch)
    r = svc.open_research_request(
        company_id="co-1", requester_user_id="u-1", dest_country="jp", origin_country="us",
        scope="need JP corridor",
    )
    assert r["status"] == "pending"
    assert r["corridor"] == "US→JP"
    assert r["dest_country"] == "JP"
    assert r["estimated_cost"] == svc.RESEARCH_REQUEST_DEFAULT_COST
    assert r["created_queue_item_id"] == "q-1"


def test_open_request_dedupes_open_corridor(monkeypatch):
    _install(monkeypatch)
    a = svc.open_research_request(company_id="co-1", requester_user_id="u-1", dest_country="JP", origin_country="US")
    b = svc.open_research_request(company_id="co-1", requester_user_id="u-2", dest_country="JP", origin_country="US")
    assert a["id"] == b["id"]  # second returns the existing open request


def test_resolve_approve_advances_to_in_progress(monkeypatch):
    _install(monkeypatch)
    r = svc.open_research_request(company_id="co-1", requester_user_id="u-1", dest_country="JP", origin_country="US")
    out = svc.resolve_research_request(request_id=r["id"], new_status="approved", actor_user_id="admin-1")
    assert out["status"] == "in_progress"
    assert out["resolved_by"] == "admin-1"


def test_resolve_reject(monkeypatch):
    _install(monkeypatch)
    r = svc.open_research_request(company_id="co-1", requester_user_id="u-1", dest_country="JP", origin_country="US")
    out = svc.resolve_research_request(request_id=r["id"], new_status="rejected", actor_user_id="admin-1", notes="dup")
    assert out["status"] == "rejected"
    assert out["notes"] == "dup"


def test_resolve_rejects_bad_status(monkeypatch):
    _install(monkeypatch)
    import pytest
    with pytest.raises(ValueError):
        svc.resolve_research_request(request_id="x", new_status="bogus", actor_user_id="a")
