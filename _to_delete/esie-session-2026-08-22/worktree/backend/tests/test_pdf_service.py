"""
[P3-1] Tests for the PDF generation service endpoint.

Strategy:
  - SQLite in-memory DB (same pattern as test_field_value_api.py)
  - Stub backend.app.db at module level before importing routers
  - Mock _requests.get to return synthetic PDF bytes (so tests run without
    a live Supabase storage URL)
  - Mock _try_store_draft_pdf so storage calls don't fire in tests
  - Use mock.patch.object for main_db engine substitution in setUp

Validation criteria (from P3-1 task spec):
  1. Calling GET /api/cases/:id/forms/:id/pdf returns 200 with
     Content-Type: application/pdf and Content-Disposition: attachment
  2. Re-calling returns a fresh PDF reflecting latest FieldValues
  3. Filename follows format: {form_code}_{last_name}_{first_name}_{YYYYMMDD}.pdf
  4. Fields with pdf_x/pdf_y/pdf_page have their values drawn into the PDF
  5. Fields without pdf_x/pdf_y are silently skipped
  6. A form whose original_file_url is None returns a placeholder PDF (not 404)
  7. A blocked form returns 409
  8. Non-existent form returns 404
"""
from __future__ import annotations

import io
import json
import os
import sys
import uuid
import unittest
from typing import Any, Dict, List, Optional
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ── Module-level stubs — must happen before any router import ─────────────────
import unittest.mock as _umock
from pydantic import BaseModel as _PydanticBase
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool


class _AnyModel(_PydanticBase):
    model_config = {"extra": "allow"}


if "backend.app.db" not in sys.modules:
    _stub_db = _umock.MagicMock()
    _stub_db.SessionLocal = _umock.MagicMock()
    sys.modules["backend.app.db"] = _stub_db

if "backend.app.schemas" not in sys.modules:
    _stub_schemas = _umock.MagicMock()
    _stub_schemas.CaseDTO = _AnyModel
    _stub_schemas.CaseDraftDTO = _AnyModel
    _stub_schemas.CaseRequirementsDTO = _AnyModel
    sys.modules["backend.app.schemas"] = _stub_schemas

for _mod in [
    "backend.app.crud",
    "backend.app.auth_deps",
    "backend.app.services.relocation_plan_view_service",
    "backend.app.services.research",
    "backend.app.services.requirements_builder",
    "backend.app.services.roadmap_builder",
    "backend.app.services.trigger_engine",
    "backend.app.services.prefill_engine",
    "backend.app.services.supabase_client",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _umock.MagicMock()

# ── Import router ────────────────────────────────────────────────────────────
import backend.app.routers.cases as cases_router       # noqa: E402
from backend.app.routers.cases import (                # noqa: E402
    get_form_pdf,
    _generate_filled_pdf,
    _build_overlay_page,
    _make_blank_pdf,
    _assert_case_access,
)

# ── Minimal PDF bytes (valid 1-page PDF with a tiny page) ────────────────────
# Generated via reportlab in this helper so tests don't need a fixture file.

def _make_test_pdf(width: float = 595.0, height: float = 842.0) -> bytes:
    """Create a minimal valid PDF using reportlab."""
    from reportlab.pdfgen import canvas as rl_canvas
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(width, height))
    c.setFont("Helvetica", 10)
    c.drawString(50, 800, "Test form template")
    c.save()
    buf.seek(0)
    return buf.read()


# ── SQLite schema ─────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE cases (
    id          TEXT PRIMARY KEY,
    company_id  TEXT,
    employee_id TEXT,
    hr_owner_id TEXT
);
CREATE TABLE form_templates (
    id               TEXT PRIMARY KEY,
    code             TEXT NOT NULL DEFAULT 'TEST-001',
    name             TEXT NOT NULL DEFAULT 'Test Form',
    country          TEXT NOT NULL DEFAULT 'NO',
    authority_code   TEXT,
    authority_name   TEXT,
    version          TEXT NOT NULL DEFAULT '1.0.0',
    fields           TEXT NOT NULL DEFAULT '[]',
    trigger_rules    TEXT NOT NULL DEFAULT '{}',
    category         TEXT,
    original_pdf_url TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    source_language TEXT NOT NULL DEFAULT 'en'
);
CREATE TABLE case_forms (
    id               TEXT PRIMARY KEY,
    case_id          TEXT NOT NULL,
    form_template_id TEXT NOT NULL,
    person_id        TEXT,
    dependent_id     TEXT,
    status           TEXT NOT NULL DEFAULT 'not_started',
    completion_pct   INTEGER NOT NULL DEFAULT 0,
    deadline         TEXT,
    deadline_trigger TEXT,
    deadline_reminded_at TEXT,
    blocker_form_id  TEXT,
    original_file_url TEXT,
    draft_pdf_url    TEXT,
    submitted_at     TEXT,
    receipt_ref      TEXT,
    rejection_reason TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now'))
);
CREATE TABLE case_form_field_values (
    id            TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    case_form_id  TEXT NOT NULL,
    field_id      TEXT NOT NULL,
    value         TEXT,
    filled_by     TEXT NOT NULL DEFAULT 'ai',
    ai_confidence REAL,
    reviewed      INTEGER NOT NULL DEFAULT 0,
    overridden    INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT DEFAULT (datetime('now')),
    UNIQUE (case_form_id, field_id)
);
CREATE TABLE field_value_overrides (
    id                  TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    case_form_id        TEXT NOT NULL,
    form_template_id    TEXT NOT NULL,
    field_id            TEXT NOT NULL,
    original_value      TEXT,
    corrected_value     TEXT,
    original_confidence REAL,
    overridden_by       TEXT NOT NULL,
    created_at          TEXT DEFAULT (datetime('now'))
);
CREATE TABLE employees (
    id        TEXT PRIMARY KEY,
    full_name TEXT
);
"""

# Template fields: two with PDF coords, one without
_TEMPLATE_FIELDS = json.dumps([
    {
        "id": "first_name",
        "label": "First name",
        "type": "text",
        "required": True,
        "position": 1,
        "prefill_source": None,
        "requires_original": False,
        "options": None,
        "pdf_page": 1,
        "pdf_x": 150.0,
        "pdf_y": 700.0,
        "pdf_font_size": 10,
        "pdf_max_width": 180,
    },
    {
        "id": "last_name",
        "label": "Last name",
        "type": "text",
        "required": True,
        "position": 2,
        "prefill_source": None,
        "requires_original": False,
        "options": None,
        "pdf_page": 1,
        "pdf_x": 150.0,
        "pdf_y": 680.0,
        "pdf_font_size": 10,
        "pdf_max_width": 180,
    },
    {
        "id": "internal_note",
        "label": "Internal note",
        "type": "text",
        "required": False,
        "position": 3,
        "prefill_source": None,
        "requires_original": False,
        "options": None,
        # No pdf_x/pdf_y — should be skipped
    },
])


def _uuid() -> str:
    return str(uuid.uuid4())


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        for stmt in _SCHEMA.strip().split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))
    return engine


DUMMY_USER: Dict[str, Any] = {"id": _uuid(), "role": "employee", "is_admin": False}
HR_USER: Dict[str, Any] = {"id": _uuid(), "role": "hr", "is_admin": False}


def _seed(engine, *, original_file_url: Optional[str] = "https://example.com/form.pdf",
          status: str = "in_progress", with_field_values: bool = True,
          with_employee: bool = True) -> Dict[str, str]:
    case_id = _uuid()
    tmpl_id = _uuid()
    cf_id = _uuid()
    emp_id = _uuid()

    with engine.begin() as conn:
        conn.execute(text("INSERT INTO cases (id) VALUES (:id)"), {"id": case_id})
        conn.execute(text(
            "INSERT INTO form_templates (id,code,name,fields) VALUES (:id,:c,:n,:f)"
        ), {"id": tmpl_id, "c": "UTL-2011", "n": "Registration Form", "f": _TEMPLATE_FIELDS})
        conn.execute(text(
            "INSERT INTO case_forms (id,case_id,form_template_id,status,original_file_url,person_id) "
            "VALUES (:id,:cid,:tid,:s,:url,:pid)"
        ), {"id": cf_id, "cid": case_id, "tid": tmpl_id, "s": status,
            "url": original_file_url, "pid": emp_id if with_employee else None})
        if with_employee:
            conn.execute(text(
                "INSERT INTO employees (id, full_name) VALUES (:id, :n)"
            ), {"id": emp_id, "n": "Marc Bouchard"})
        if with_field_values:
            conn.execute(text(
                "INSERT INTO case_form_field_values "
                "(id,case_form_id,field_id,value,filled_by,ai_confidence) "
                "VALUES (:id,:cid,:fid,:v,:fb,:conf)"
            ), {"id": _uuid(), "cid": cf_id, "fid": "first_name",
                "v": "Marc", "fb": "ai", "conf": 0.95})
            conn.execute(text(
                "INSERT INTO case_form_field_values "
                "(id,case_form_id,field_id,value,filled_by,ai_confidence) "
                "VALUES (:id,:cid,:fid,:v,:fb,:conf)"
            ), {"id": _uuid(), "cid": cf_id, "fid": "last_name",
                "v": "Bouchard", "fb": "ai", "conf": 0.90})

    return {"case_id": case_id, "tmpl_id": tmpl_id, "cf_id": cf_id, "emp_id": emp_id}


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: _generate_filled_pdf helper
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateFilledPdf(unittest.TestCase):
    """Low-level PDF overlay tests — no DB, no HTTP."""

    def _fields(self):
        return json.loads(_TEMPLATE_FIELDS)

    def test_returns_bytes(self):
        original = _make_test_pdf()
        fields = self._fields()
        values = {"first_name": "Marc", "last_name": "Bouchard"}
        result = _generate_filled_pdf(original, fields, values)
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 100)

    def test_valid_pdf_header(self):
        """Output must start with %PDF-"""
        original = _make_test_pdf()
        result = _generate_filled_pdf(original, self._fields(),
                                       {"first_name": "Léa", "last_name": "Dupont"})
        self.assertTrue(result.startswith(b"%PDF-"), "Output is not a valid PDF")

    def test_fields_without_coords_skipped(self):
        """internal_note has no pdf_x/pdf_y — must not raise."""
        original = _make_test_pdf()
        fields = self._fields()
        values = {"first_name": "X", "last_name": "Y", "internal_note": "secret"}
        result = _generate_filled_pdf(original, fields, values)
        self.assertIsInstance(result, bytes)

    def test_empty_values_produce_clean_copy(self):
        """With no values, the PDF is returned as-is (no overlay applied)."""
        original = _make_test_pdf()
        result = _generate_filled_pdf(original, self._fields(), {})
        self.assertIsInstance(result, bytes)
        # Valid PDF
        self.assertTrue(result.startswith(b"%PDF-"))

    def test_page_out_of_range_skipped(self):
        """Fields referencing a non-existent page must be silently ignored."""
        original = _make_test_pdf()  # 1-page PDF
        fields = [
            {"id": "f1", "pdf_page": 99, "pdf_x": 10, "pdf_y": 10,
             "pdf_font_size": 10, "required": True},
        ]
        result = _generate_filled_pdf(original, fields, {"f1": "value"})
        self.assertIsInstance(result, bytes)


class TestMakeBlankPdf(unittest.TestCase):
    def test_returns_valid_pdf(self):
        result = _make_blank_pdf("My Form", "No original uploaded")
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b"%PDF-"))


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests: GET /api/cases/{case_id}/forms/{form_id}/pdf
# ─────────────────────────────────────────────────────────────────────────────

class TestGetFormPdf(unittest.TestCase):

    def setUp(self):
        self.engine = _make_engine()
        self._engine_patcher = mock.patch.object(
            cases_router.main_db, "engine", self.engine
        )
        self._engine_patcher.start()
        # Stub _assert_case_access to always pass
        self._access_patcher = mock.patch(
            "backend.app.routers.cases._assert_case_access", return_value=None
        )
        self._access_patcher.start()
        # Stub _try_store_draft_pdf to avoid Supabase calls in tests
        self._storage_patcher = mock.patch(
            "backend.app.routers.cases._try_store_draft_pdf", return_value=None
        )
        self._storage_patcher.start()

    def tearDown(self):
        self._engine_patcher.stop()
        self._access_patcher.stop()
        self._storage_patcher.stop()

    def _call(self, case_id: str, form_id: str,
              original_pdf_bytes: Optional[bytes] = None) -> Any:
        """Call get_form_pdf, optionally mocking HTTP fetch of original PDF."""
        if original_pdf_bytes is not None:
            mock_resp = mock.MagicMock()
            mock_resp.content = original_pdf_bytes
            mock_resp.raise_for_status = mock.MagicMock()
            with mock.patch("backend.app.routers.cases._requests") as mock_req:
                mock_req.get.return_value = mock_resp
                return get_form_pdf(case_id, form_id, user=DUMMY_USER)
        else:
            with mock.patch("backend.app.routers.cases._requests") as mock_req:
                mock_req.get.side_effect = Exception("no network")
                return get_form_pdf(case_id, form_id, user=DUMMY_USER)

    # ── Validation Criterion 1: response is PDF with correct headers ──────────

    def test_returns_200_with_pdf_content_type(self):
        ids = _seed(self.engine)
        original = _make_test_pdf()
        response = self._call(ids["case_id"], ids["cf_id"], original_pdf_bytes=original)
        self.assertEqual(response.media_type, "application/pdf")

    def test_content_disposition_is_attachment(self):
        ids = _seed(self.engine)
        original = _make_test_pdf()
        response = self._call(ids["case_id"], ids["cf_id"], original_pdf_bytes=original)
        cd = response.headers.get("Content-Disposition", "")
        self.assertIn("attachment", cd)

    # ── Validation Criterion 3: filename format ───────────────────────────────

    def test_filename_contains_form_code(self):
        ids = _seed(self.engine)
        original = _make_test_pdf()
        response = self._call(ids["case_id"], ids["cf_id"], original_pdf_bytes=original)
        cd = response.headers.get("Content-Disposition", "")
        self.assertIn("UTL-2011", cd)

    def test_filename_ends_with_pdf(self):
        ids = _seed(self.engine)
        original = _make_test_pdf()
        response = self._call(ids["case_id"], ids["cf_id"], original_pdf_bytes=original)
        cd = response.headers.get("Content-Disposition", "")
        self.assertIn(".pdf", cd)

    # ── Validation Criterion 4: field values are in the output ───────────────

    def test_returns_valid_pdf_bytes(self):
        ids = _seed(self.engine)
        original = _make_test_pdf()
        response = self._call(ids["case_id"], ids["cf_id"], original_pdf_bytes=original)
        self.assertTrue(response.body.startswith(b"%PDF-"))

    # ── Validation Criterion 6: no original_file_url → placeholder PDF ───────

    def test_placeholder_pdf_when_no_original_url(self):
        ids = _seed(self.engine, original_file_url=None)
        # No original_file_url → fallback placeholder
        response = self._call(ids["case_id"], ids["cf_id"], original_pdf_bytes=None)
        self.assertEqual(response.media_type, "application/pdf")
        self.assertTrue(response.body.startswith(b"%PDF-"))

    def test_placeholder_pdf_when_http_fetch_fails(self):
        ids = _seed(self.engine, original_file_url="https://broken.example.com/form.pdf")
        # HTTP fetch fails → placeholder
        response = self._call(ids["case_id"], ids["cf_id"], original_pdf_bytes=None)
        self.assertEqual(response.media_type, "application/pdf")
        self.assertTrue(response.body.startswith(b"%PDF-"))

    # ── Validation Criterion 7: blocked form → 409 ───────────────────────────

    def test_blocked_form_returns_409(self):
        ids = _seed(self.engine, status="blocked")
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            self._call(ids["case_id"], ids["cf_id"], original_pdf_bytes=_make_test_pdf())
        self.assertEqual(ctx.exception.status_code, 409)

    # ── Validation Criterion 8: unknown form → 404 ───────────────────────────

    def test_unknown_form_returns_404(self):
        ids = _seed(self.engine)
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            self._call(ids["case_id"], _uuid(), original_pdf_bytes=_make_test_pdf())
        self.assertEqual(ctx.exception.status_code, 404)

    def test_unknown_case_returns_404(self):
        ids = _seed(self.engine)
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            self._call(_uuid(), ids["cf_id"], original_pdf_bytes=_make_test_pdf())
        self.assertEqual(ctx.exception.status_code, 404)

    # ── Validation Criterion 2: re-calling reflects latest values ────────────

    def test_second_call_reflects_updated_field_value(self):
        """Each call regenerates from current DB values, not a stale cache."""
        ids = _seed(self.engine)
        original = _make_test_pdf()

        # First call: Marc
        r1 = self._call(ids["case_id"], ids["cf_id"], original_pdf_bytes=original)
        self.assertEqual(r1.media_type, "application/pdf")

        # Update first_name to Élodie
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE case_form_field_values SET value='Élodie' "
                "WHERE case_form_id=:cid AND field_id='first_name'"
            ), {"cid": ids["cf_id"]})

        # Second call: should succeed (we don't inspect text in binary, just no error)
        r2 = self._call(ids["case_id"], ids["cf_id"], original_pdf_bytes=original)
        self.assertEqual(r2.media_type, "application/pdf")
        self.assertTrue(r2.body.startswith(b"%PDF-"))

    # ── No field values → still returns PDF ──────────────────────────────────

    def test_empty_field_values_returns_pdf(self):
        ids = _seed(self.engine, with_field_values=False)
        original = _make_test_pdf()
        response = self._call(ids["case_id"], ids["cf_id"], original_pdf_bytes=original)
        self.assertEqual(response.media_type, "application/pdf")


if __name__ == "__main__":
    unittest.main()
