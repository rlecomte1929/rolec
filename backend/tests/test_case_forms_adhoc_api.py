"""
H4 · Tests for the ad-hoc case-forms router (case_forms_adhoc.py) — part of the
Forms & Dossiers area, which the campaign API runner does not cover.

Two layers:
  - Pure helpers (_actor_uuid, _read_pdf): _actor_uuid encodes a real regression
    fix — a legacy non-UUID session id must NOT be used as case_form_events.actor_id
    (it poisons the form-insert transaction and surfaces as a misleading 404).
  - HTTP validation via the prod app: empty name → 400, non-PDF upload → 400. Both
    short-circuit before any DB write, so no live DB is needed.
"""
from __future__ import annotations

import asyncio
import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import io
import unittest
from typing import Any, Dict
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.auth_deps import get_current_user
from backend.app.routers import case_forms_adhoc as adhoc

_MOD = "backend.app.routers.case_forms_adhoc"
_EMP: Dict[str, Any] = {"id": "seed-emp-testingapril", "role": "EMPLOYEE",
                        "email": "emp@x.test"}


class ActorUuidTest(unittest.TestCase):
    def test_prefers_auth_uuid(self) -> None:
        u = {"auth_uuid": "11111111-1111-1111-1111-111111111111", "id": "seed-emp"}
        self.assertEqual(adhoc._actor_uuid(u),
                         "11111111-1111-1111-1111-111111111111")

    def test_falls_back_to_uuid_shaped_id(self) -> None:
        u = {"auth_uuid": None, "id": "22222222-2222-2222-2222-222222222222"}
        self.assertEqual(adhoc._actor_uuid(u),
                         "22222222-2222-2222-2222-222222222222")

    def test_legacy_text_id_yields_none(self) -> None:
        """The regression guard: a non-UUID legacy id must not be returned."""
        self.assertIsNone(adhoc._actor_uuid({"id": "seed-emp-testingapril"}))
        self.assertIsNone(adhoc._actor_uuid({}))


class ReadPdfTest(unittest.TestCase):
    @staticmethod
    def _upload(data: bytes, content_type: str) -> UploadFile:
        return UploadFile(file=io.BytesIO(data), filename="f.pdf",
                          headers={"content-type": content_type})

    def test_rejects_non_pdf_content_type(self) -> None:
        up = self._upload(b"hello", "image/png")
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(adhoc._read_pdf(up))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_rejects_empty_file(self) -> None:
        up = self._upload(b"", "application/pdf")
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(adhoc._read_pdf(up))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_accepts_pdf(self) -> None:
        up = self._upload(b"%PDF-1.4 ...", "application/pdf")
        data, ctype = asyncio.run(adhoc._read_pdf(up))
        self.assertEqual(data, b"%PDF-1.4 ...")
        self.assertEqual(ctype, "application/pdf")


class CreateAdhocFormValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_current_user] = lambda: _EMP
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_blank_name_is_400(self) -> None:
        with patch(f"{_MOD}._assert_case_access", return_value=None):
            resp = self.client.post("/api/cases/case-a/forms/adhoc",
                                    data={"name": "   "})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("name", resp.json()["detail"].lower())

    def test_non_pdf_upload_is_400(self) -> None:
        with patch(f"{_MOD}._assert_case_access", return_value=None):
            resp = self.client.post(
                "/api/cases/case-a/forms/adhoc",
                data={"name": "Custom doc"},
                files={"file": ("x.png", b"\x89PNG", "image/png")},
            )
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
