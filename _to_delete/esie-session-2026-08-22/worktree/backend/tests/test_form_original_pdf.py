"""
Tests for [P2-4] GET /api/cases/{case_id}/forms/{form_id}/original.

Covers:
  - 200 + signed_url when template has original_pdf_url + Supabase OK
  - 200 + signed_url=None when template has no PDF attached (empty-state)
  - 200 + signed_url=None when Supabase Storage call raises (dev mode fallback)
  - 404 when case_form does not exist for the given case
  - Path normalisation when original_pdf_url contains the bucket prefix
  - Access guard (employee, HR owner, company match, admin bypass, 403)

The endpoint lives in its own standalone router (backend/app/routers/
case_form_pdf.py) so tests don't need the heavy stubs the cases.py suite
requires — they only need to patch the module-level `db` and the lazy
supabase import.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from typing import Any, Dict, Optional
from unittest import mock

from sqlalchemy import create_engine, text
from fastapi import HTTPException

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# `auth_deps` is imported by case_form_pdf at module load. Stub it before
# importing the router so the test process doesn't need real JWT plumbing.
import unittest.mock as _umock  # noqa: E402
if "backend.app.auth_deps" not in sys.modules:
    _stub_auth = _umock.MagicMock()
    _stub_auth.get_current_user = _umock.MagicMock(return_value={"id": "u", "is_admin": True})
    sys.modules["backend.app.auth_deps"] = _stub_auth


import backend.app.routers.case_form_pdf as pdf_router  # noqa: E402
from backend.app.routers.case_form_pdf import get_form_original_pdf  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Minimal schema — only the columns the endpoint reads
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE cases (
    id          TEXT PRIMARY KEY,
    employee_id TEXT,
    hr_owner_id TEXT,
    company_id  TEXT
);
CREATE TABLE form_templates (
    id                TEXT PRIMARY KEY,
    code              TEXT NOT NULL,
    name              TEXT NOT NULL,
    version           TEXT NOT NULL DEFAULT '1.0.0',
    original_pdf_url  TEXT,
    source_language TEXT NOT NULL DEFAULT 'en'
);
CREATE TABLE case_forms (
    id               TEXT PRIMARY KEY,
    case_id          TEXT NOT NULL,
    form_template_id TEXT NOT NULL
);
"""


# Admin user — bypasses all access checks via _assert_case_access early return.
DUMMY_USER: Dict[str, Any] = {
    "id": "00000000-0000-0000-0000-000000000001",
    "is_admin": True,
}


def _uuid() -> str:
    return str(uuid.uuid4())


def _seed_template(conn, *, tid: str, code: str, name: str,
                   version: str = "1.0.0",
                   pdf_path: Optional[str] = None) -> None:
    conn.execute(text(
        "INSERT INTO form_templates (id, code, name, version, original_pdf_url) "
        "VALUES (:id, :code, :name, :ver, :pdf)"
    ), {"id": tid, "code": code, "name": name, "ver": version, "pdf": pdf_path})


def _seed_case_form(conn, *, cf_id: str, case_id: str, tid: str) -> None:
    conn.execute(text(
        "INSERT INTO case_forms (id, case_id, form_template_id) "
        "VALUES (:id, :cid, :tid)"
    ), {"id": cf_id, "cid": case_id, "tid": tid})


# ─────────────────────────────────────────────────────────────────────────────
# Stub Supabase client for storage.from_(bucket).create_signed_url(path, ttl)
# ─────────────────────────────────────────────────────────────────────────────

def _make_storage_stub(response: Any):
    """Return a sb-shaped MagicMock whose create_signed_url returns `response`
    (or raises if response is an Exception)."""
    storage_bucket = _umock.MagicMock()
    if isinstance(response, Exception):
        storage_bucket.create_signed_url.side_effect = response
    else:
        storage_bucket.create_signed_url.return_value = response
    sb = _umock.MagicMock()
    sb.storage.from_.return_value = storage_bucket
    return sb, storage_bucket


# ─────────────────────────────────────────────────────────────────────────────
# Test suite
# ─────────────────────────────────────────────────────────────────────────────

class OriginalPdfEndpointTests(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))

        self.engine_patcher = mock.patch.object(
            pdf_router.db, "engine", self.engine
        )
        self.engine_patcher.start()

        # [AIQ-1776] _assert_case_access now RETURNS the resolved canonical case
        # id and the endpoint keys its SQL on that return value. A stub returning
        # None would make every query read `case_id = NULL` and 404. These tests
        # seed case_forms under the same id they pass in, so identity is right.
        self.auth_patcher = mock.patch.object(
            pdf_router, "_assert_case_access", side_effect=lambda _user, cid: cid
        )
        self.auth_patcher.start()

    def tearDown(self):
        self.engine_patcher.stop()
        self.auth_patcher.stop()
        self.engine.dispose()

    # ── happy path — Supabase returns a signed URL ───────────────────────────

    def test_returns_signed_url_when_pdf_attached(self):
        case_id, tid, cf_id = _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _seed_template(
                conn, tid=tid, code="UTL-2011", name="Application",
                version="1.0.0", pdf_path="UTL-2011/1.0.0.pdf",
            )
            _seed_case_form(conn, cf_id=cf_id, case_id=case_id, tid=tid)

        sb, bucket = _make_storage_stub(
            {"signedURL": "https://storage.supabase.co/signed/UTL-2011/1.0.0.pdf?token=abc"}
        )
        with mock.patch(
            "backend.app.services.supabase_client.get_supabase_admin_client",
            return_value=sb,
        ):
            res = get_form_original_pdf(case_id, cf_id, DUMMY_USER)

        self.assertEqual(
            res.signed_url,
            "https://storage.supabase.co/signed/UTL-2011/1.0.0.pdf?token=abc",
        )
        self.assertEqual(res.template_code, "UTL-2011")
        self.assertEqual(res.template_name, "Application")
        self.assertEqual(res.version, "1.0.0")
        self.assertEqual(res.file_name, "UTL-2011-1.0.0.pdf")
        self.assertEqual(res.expires_in, 3600)
        sb.storage.from_.assert_called_with("form-templates")
        bucket.create_signed_url.assert_called_with("UTL-2011/1.0.0.pdf", 3600)

    def test_accepts_camelCase_signedUrl_response_shape(self):
        """supabase-py has shipped both 'signedURL' and 'signedUrl' over time."""
        case_id, tid, cf_id = _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _seed_template(
                conn, tid=tid, code="GP-7-04", name="D-number",
                pdf_path="GP-7-04/1.0.0.pdf",
            )
            _seed_case_form(conn, cf_id=cf_id, case_id=case_id, tid=tid)

        sb, _bucket = _make_storage_stub(
            {"signedUrl": "https://signed.example/x"}  # different casing
        )
        with mock.patch(
            "backend.app.services.supabase_client.get_supabase_admin_client",
            return_value=sb,
        ):
            res = get_form_original_pdf(case_id, cf_id, DUMMY_USER)
        self.assertEqual(res.signed_url, "https://signed.example/x")

    # ── empty-state — no PDF attached ────────────────────────────────────────

    def test_returns_null_url_when_no_pdf_attached(self):
        case_id, tid, cf_id = _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _seed_template(conn, tid=tid, code="UTL-2011F", name="Family",
                           pdf_path=None)  # NO PDF attached
            _seed_case_form(conn, cf_id=cf_id, case_id=case_id, tid=tid)

        # Supabase shouldn't even be called when there's no path
        with mock.patch(
            "backend.app.services.supabase_client.get_supabase_admin_client"
        ) as mock_client:
            res = get_form_original_pdf(case_id, cf_id, DUMMY_USER)

        self.assertIsNone(res.signed_url)
        self.assertEqual(res.expires_in, 0)
        self.assertEqual(res.template_code, "UTL-2011F")
        self.assertEqual(res.file_name, "UTL-2011F.pdf")
        mock_client.assert_not_called()

    # ── dev-mode fallback — Supabase unavailable ─────────────────────────────

    def test_returns_null_url_when_storage_raises(self):
        case_id, tid, cf_id = _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _seed_template(conn, tid=tid, code="RF-1234", name="Address reg",
                           pdf_path="RF-1234/1.0.0.pdf")
            _seed_case_form(conn, cf_id=cf_id, case_id=case_id, tid=tid)

        sb, _bucket = _make_storage_stub(RuntimeError("storage down"))
        with mock.patch(
            "backend.app.services.supabase_client.get_supabase_admin_client",
            return_value=sb,
        ):
            res = get_form_original_pdf(case_id, cf_id, DUMMY_USER)

        # Dev-mode fallback: 200 with signed_url=None, template metadata intact
        self.assertIsNone(res.signed_url)
        self.assertEqual(res.expires_in, 0)
        self.assertEqual(res.template_code, "RF-1234")

    # ── 404 — form not found ─────────────────────────────────────────────────

    def test_404_when_case_form_not_found(self):
        with self.assertRaises(HTTPException) as ctx:
            get_form_original_pdf(_uuid(), _uuid(), DUMMY_USER)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_404_when_case_form_belongs_to_different_case(self):
        """Even when the form_id exists, it must be scoped to the case_id."""
        case_a, case_b, tid, cf_id = _uuid(), _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _seed_template(conn, tid=tid, code="NAV-08", name="Member",
                           pdf_path="NAV-08/1.0.0.pdf")
            _seed_case_form(conn, cf_id=cf_id, case_id=case_a, tid=tid)

        with self.assertRaises(HTTPException) as ctx:
            get_form_original_pdf(case_b, cf_id, DUMMY_USER)
        self.assertEqual(ctx.exception.status_code, 404)

    # ── path normalisation — legacy full-URL pdf paths ───────────────────────

    def test_strips_bucket_prefix_from_legacy_full_url(self):
        """If a template stored a full URL (e.g. from a manual seed), the
        endpoint should still sign by relative key."""
        case_id, tid, cf_id = _uuid(), _uuid(), _uuid()
        legacy_url = (
            "https://supabase.example/storage/v1/object/public"
            "/form-templates/UTL-2011/1.0.0.pdf"
        )
        with self.engine.begin() as conn:
            _seed_template(conn, tid=tid, code="UTL-2011", name="Application",
                           pdf_path=legacy_url)
            _seed_case_form(conn, cf_id=cf_id, case_id=case_id, tid=tid)

        sb, bucket = _make_storage_stub({"signedURL": "https://signed/x"})
        with mock.patch(
            "backend.app.services.supabase_client.get_supabase_admin_client",
            return_value=sb,
        ):
            res = get_form_original_pdf(case_id, cf_id, DUMMY_USER)

        # The signing call should have used the bucket-relative path only
        bucket.create_signed_url.assert_called_with("UTL-2011/1.0.0.pdf", 3600)
        self.assertEqual(res.signed_url, "https://signed/x")


if __name__ == "__main__":
    unittest.main()
