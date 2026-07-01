"""
Mission Control P2 — autofix_dispatch fires the EXISTING Supabase autofix edge
function on-demand for one work_item (reusing the proven pipeline; no new GitHub
credential). HTTP is mocked: we assert the call shape + soft-fail when unconfigured.
"""
import backend.app.services.autofix_dispatch as ad


class _Resp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def test_soft_noop_when_unconfigured(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    called = {"n": 0}
    monkeypatch.setattr(ad.requests, "post", lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    out = ad.dispatch_autofix({"id": "w1", "title": "x", "body": "y"})
    assert out["ok"] is False and out["reason"] == "not_configured"
    assert called["n"] == 0  # never hits the network


def test_posts_to_edge_function_with_service_role_and_payload(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc-key")
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["url"] = url
        seen["headers"] = headers
        seen["json"] = json
        return _Resp(200, {"pr_url": "https://github.com/o/r/pull/9"})

    monkeypatch.setattr(ad.requests, "post", fake_post)
    out = ad.dispatch_autofix({"id": "w1", "title": "Fix typo", "body": "z"})

    assert seen["url"] == "https://proj.supabase.co/functions/v1/autofix-pipeline"
    assert seen["headers"]["Authorization"] == "Bearer svc-key"
    assert seen["json"] == {"work_item": {"id": "w1", "title": "Fix typo", "body": "z"}}
    assert out["ok"] is True
    assert out["pr_url"] == "https://github.com/o/r/pull/9"


def test_edge_error_is_not_ok(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc-key")
    monkeypatch.setattr(ad.requests, "post", lambda *a, **k: _Resp(500, {}))
    out = ad.dispatch_autofix({"id": "w1", "title": "x", "body": "y"})
    assert out["ok"] is False and out["reason"] == "edge_error"
