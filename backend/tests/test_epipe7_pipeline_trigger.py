"""E-PIPE-7 · upload triggers the rce pipeline (process_rce_document) in the background.

Asserts the upload endpoint schedules process_rce_document with the bridged
rce_document_id, and does NOT schedule it when the bridge skipped (rce_document_id
None). Stage fns are mocked; FastAPI BackgroundTasks run after the response in the
TestClient, so the mock records the call.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from backend.main import app
from backend.app.auth_deps import get_current_user
import backend.app.routers.immigration_documents as router_mod
import backend.app.services.upload_validator as upload_validator


_FAKE_USER = {"id": "user-1", "role": "employee", "email": "e@x.test", "is_admin": False}
_CASE = "00df5cd6-8226-543d-8d68-91cbf1dd1103"


def _client():
    app.dependency_overrides[get_current_user] = lambda: _FAKE_USER
    return TestClient(app, raise_server_exceptions=False)


def _wire(monkeypatch, *, rce_document_id):
    async def _validate(file, allowed_mime, max_bytes):
        return (b"bytes", "passport.jpg", "image/jpeg")

    monkeypatch.setattr(upload_validator, "read_and_validate", _validate)
    monkeypatch.setattr(router_mod, "_resolve_accessible_case", lambda cid, user: cid)
    monkeypatch.setattr(router_mod, "store_immigration_document", lambda **kw: {
        "document_id": "imm-1", "storage_path": f"{_CASE}/x.jpg",
        "ocr_status": "pending", "rce_document_id": rce_document_id,
    })
    monkeypatch.setattr(router_mod, "run_extraction", MagicMock())
    worker = MagicMock()
    monkeypatch.setattr(router_mod, "process_rce_document", worker)
    return worker


def test_upload_triggers_pipeline_when_bridged(monkeypatch):
    worker = _wire(monkeypatch, rce_document_id="rce-123")
    try:
        resp = _client().post(
            f"/api/immigration/cases/{_CASE}/documents",
            files={"file": ("passport.jpg", b"bytes", "image/jpeg")},
            headers={"Authorization": "Bearer t"},
        )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200, resp.text
    worker.assert_called_once_with("rce-123")


def test_upload_does_not_trigger_when_bridge_skipped(monkeypatch):
    worker = _wire(monkeypatch, rce_document_id=None)
    try:
        resp = _client().post(
            f"/api/immigration/cases/{_CASE}/documents",
            files={"file": ("passport.jpg", b"bytes", "image/jpeg")},
            headers={"Authorization": "Bearer t"},
        )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200, resp.text
    worker.assert_not_called()
