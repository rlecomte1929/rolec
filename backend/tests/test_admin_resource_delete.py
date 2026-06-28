"""AIQ-1333 — DELETE /api/admin/resources/{id} soft-deletes draft/archived only.

The resource detail page gained a Delete control. This guards the endpoint behind
it: only draft/archived resources may be deleted (a published resource must be
unpublished/archived first, so the public surface can't lose a live resource via
this control); missing ids 404. Unit-tests the router handler's guard + that it
delegates to the existing soft-delete service (admin_resources.delete_resource).
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

import backend.app.routers.admin_resources as router_mod

ADMIN = {"id": "admin-1"}


def _patch(monkeypatch, resource, calls):
    monkeypatch.setattr(router_mod, "get_admin_resource_by_id", lambda rid: resource)

    def _del(rid, uid):
        calls.append((rid, uid))
        return True

    monkeypatch.setattr(router_mod, "delete_resource", _del)


@pytest.mark.parametrize("status", ["draft", "archived"])
def test_delete_allowed_for_draft_and_archived(monkeypatch, status):
    calls = []
    _patch(monkeypatch, {"id": "r1", "status": status}, calls)
    out = router_mod.delete_resource_endpoint(resource_id="r1", user=ADMIN)
    assert out == {"ok": True, "id": "r1"}
    assert calls == [("r1", "admin-1")]  # delegated to the soft-delete service


@pytest.mark.parametrize("status", ["published", "in_review", "approved"])
def test_delete_forbidden_for_non_draft_archived(monkeypatch, status):
    calls = []
    _patch(monkeypatch, {"id": "r1", "status": status}, calls)
    with pytest.raises(HTTPException) as ei:
        router_mod.delete_resource_endpoint(resource_id="r1", user=ADMIN)
    assert ei.value.status_code == 400
    assert calls == []  # never soft-deletes a non-draft/archived resource


def test_delete_missing_returns_404(monkeypatch):
    calls = []
    _patch(monkeypatch, None, calls)
    with pytest.raises(HTTPException) as ei:
        router_mod.delete_resource_endpoint(resource_id="nope", user=ADMIN)
    assert ei.value.status_code == 404
    assert calls == []
