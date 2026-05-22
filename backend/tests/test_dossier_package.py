"""
[P3-5] Tests for Dossier PDF merge and ZIP export.

Validation criteria (from Notion task spec):
  1. POST /api/cases/:id/dossiers with 4 form IDs returns a DossierPackage
     with a valid pdf_url field (or None if storage is unavailable in dev).
  2. The merged PDF is a valid PDF with a %PDF- header.
  3. The merged PDF contains a cover page when cover_page=True.
  4. GET /api/cases/:id/dossiers/:id/zip returns a ZIP with N correctly
     named files (NN_{form_code}_{date}.pdf pattern).
  5. Unknown form_ids in the request → 404.
  6. Empty form_ids → 422.
  7. Unknown dossier ID on ZIP endpoint → 404.
  8. Divider pages are inserted (merged PDF page count > N form pages).
"""
from __future__ import annotations

import io
import json
import os
import sys
import uuid
import zipfile
import unittest
from typing import Any, Dict, List, Optional
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

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
    "backend.services.supabase_client",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _umock.MagicMock()

import backend.app.routers.cases as cases_router  # noqa: E402
from backend.app.routers.cases import (           # noqa: E402
    create_dossier,
    get_dossier_zip,
    CreateDossierPayload,
    _build_cover_page,
    _build_divider_page,
    _merge_pdfs,
    _assert_case_access,
)

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
    updated_at       TEXT DEFAULT (datetime('now'))
);
CREATE TABLE case_forms (
    id               TEXT PRIMARY KEY,
    case_id          TEXT NOT NULL,
    form_template_id TEXT NOT NULL,
    person_id        TEXT,
    dependent_id     TEXT,
    status           TEXT NOT NULL DEFAULT 'in_progress',
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
CREATE TABLE dossier_packages (
    id           TEXT PRIMARY KEY,
    case_id      TEXT NOT NULL,
    name         TEXT NOT NULL,
    form_ids     TEXT NOT NULL DEFAULT '[]',
    cover_page   INTEGER NOT NULL DEFAULT 1,
    pdf_url      TEXT,
    generated_at TEXT,
    created_by   TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);
CREATE TABLE employees (
    id        TEXT PRIMARY KEY,
    full_name TEXT
);
"""

_FIELDS_JSON = json.dumps([
    {"id": "first_name", "label": "First name", "type": "text", "required": True,
     "position": 1, "prefill_source": None, "requires_original": False, "options": None,
     "pdf_page": 1, "pdf_x": 100.0, "pdf_y": 700.0, "pdf_font_size": 10},
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


def _make_test_pdf() -> bytes:
    from reportlab.pdfgen import canvas as rl_canvas
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(595.0, 842.0))
    c.drawString(50, 800, "Test form page")
    c.save()
    buf.seek(0)
    return buf.read()


DUMMY_USER: Dict[str, Any] = {"id": _uuid(), "role": "employee", "is_admin": False}


def _seed_case_with_forms(engine, n_forms: int = 2) -> Dict[str, Any]:
    """Seed a case with N forms (each with one field value). Returns ids."""
    case_id = _uuid()
    cf_ids = []
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO cases (id) VALUES (:id)"), {"id": case_id})
        for i in range(n_forms):
            tmpl_id = _uuid()
            cf_id = _uuid()
            conn.execute(text(
                "INSERT INTO form_templates (id,code,name,fields) VALUES (:id,:c,:n,:f)"
            ), {"id": tmpl_id, "c": f"UTL-{2000+i}", "n": f"Form {i+1}", "f": _FIELDS_JSON})
            conn.execute(text(
                "INSERT INTO case_forms (id,case_id,form_template_id,status) "
                "VALUES (:id,:cid,:tid,'in_progress')"
            ), {"id": cf_id, "cid": case_id, "tid": tmpl_id})
            conn.execute(text(
                "INSERT INTO case_form_field_values "
                "(id,case_form_id,field_id,value,filled_by) VALUES (:id,:cid,:fid,:v,'human')"
            ), {"id": _uuid(), "cid": cf_id, "fid": "first_name", "v": f"Value{i}"})
            cf_ids.append(cf_id)
    return {"case_id": case_id, "cf_ids": cf_ids}


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: helper functions
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildCoverPage(unittest.TestCase):
    def test_returns_valid_pdf(self):
        result = _build_cover_page(
            "My Dossier", "case-123",
            [{"code": "UTL-2011", "name": "Registration", "authority_code": "UDI"}],
        )
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b"%PDF-"))

    def test_returns_pdf_with_multiple_forms(self):
        forms = [{"code": f"F-{i}", "name": f"Form {i}", "authority_code": "UDI"}
                 for i in range(10)]
        result = _build_cover_page("Big Dossier", "c-1", forms)
        self.assertTrue(result.startswith(b"%PDF-"))


class TestBuildDividerPage(unittest.TestCase):
    def test_returns_valid_pdf(self):
        result = _build_divider_page("UTL-2011", "Tax Registration", "Skatteetaten")
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b"%PDF-"))

    def test_works_without_authority(self):
        result = _build_divider_page("RF-1209", "Social Security Form", None)
        self.assertTrue(result.startswith(b"%PDF-"))


class TestMergePdfs(unittest.TestCase):
    def test_merges_two_pdfs(self):
        from pypdf import PdfReader
        p1 = _make_test_pdf()
        p2 = _make_test_pdf()
        merged = _merge_pdfs([p1, p2])
        self.assertTrue(merged.startswith(b"%PDF-"))
        # Result has 2 pages
        reader = PdfReader(io.BytesIO(merged))
        self.assertEqual(len(reader.pages), 2)

    def test_merges_four_pdfs(self):
        from pypdf import PdfReader
        parts = [_make_test_pdf() for _ in range(4)]
        merged = _merge_pdfs(parts)
        reader = PdfReader(io.BytesIO(merged))
        self.assertEqual(len(reader.pages), 4)


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests: POST /api/cases/{case_id}/dossiers
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateDossier(unittest.TestCase):

    def setUp(self):
        self.engine = _make_engine()
        self._eng_patcher = mock.patch.object(cases_router.main_db, "engine", self.engine)
        self._eng_patcher.start()
        self._access_patcher = mock.patch(
            "backend.app.routers.cases._assert_case_access", return_value=None
        )
        self._access_patcher.start()
        self._storage_patcher = mock.patch(
            "backend.app.routers.cases._try_store_dossier_pdf", return_value=None
        )
        self._storage_patcher.start()

        # Mock HTTP fetch for original PDFs
        self._http_patcher = mock.patch("backend.app.routers.cases._requests")
        mock_req = self._http_patcher.start()
        mock_resp = mock.MagicMock()
        mock_resp.content = _make_test_pdf()
        mock_resp.raise_for_status = mock.MagicMock()
        mock_req.get.return_value = mock_resp

    def tearDown(self):
        self._eng_patcher.stop()
        self._access_patcher.stop()
        self._storage_patcher.stop()
        self._http_patcher.stop()

    def _call(self, case_id: str, form_ids: List[str],
              name: str = "Test Dossier", cover_page: bool = True) -> Any:
        return create_dossier(
            case_id,
            CreateDossierPayload(name=name, form_ids=form_ids, cover_page=cover_page),
            user=DUMMY_USER,
        )

    # ── Criterion 1 & 2: response includes valid DossierPackage ──────────────

    def test_returns_dossier_package(self):
        ids = _seed_case_with_forms(self.engine, n_forms=2)
        result = self._call(ids["case_id"], ids["cf_ids"])
        self.assertEqual(result.case_id, ids["case_id"])
        self.assertEqual(len(result.form_ids), 2)
        self.assertIsNotNone(result.id)

    def test_form_ids_preserved_in_order(self):
        ids = _seed_case_with_forms(self.engine, n_forms=4)
        result = self._call(ids["case_id"], ids["cf_ids"])
        self.assertEqual(result.form_ids, ids["cf_ids"])

    def test_package_name_stored(self):
        ids = _seed_case_with_forms(self.engine, n_forms=2)
        result = self._call(ids["case_id"], ids["cf_ids"], name="My Package")
        self.assertEqual(result.name, "My Package")

    def test_cover_page_false_stored(self):
        ids = _seed_case_with_forms(self.engine, n_forms=2)
        result = self._call(ids["case_id"], ids["cf_ids"], cover_page=False)
        self.assertFalse(result.cover_page)

    # ── Criterion 5: unknown form_ids → 404 ──────────────────────────────────

    def test_unknown_form_id_returns_404(self):
        ids = _seed_case_with_forms(self.engine, n_forms=1)
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            self._call(ids["case_id"], [_uuid()])
        self.assertEqual(ctx.exception.status_code, 404)

    def test_mixed_valid_invalid_form_ids_returns_404(self):
        ids = _seed_case_with_forms(self.engine, n_forms=2)
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            self._call(ids["case_id"], [ids["cf_ids"][0], _uuid()])
        self.assertEqual(ctx.exception.status_code, 404)

    # ── Criterion 6: empty form_ids → 422 ────────────────────────────────────

    def test_empty_form_ids_returns_422(self):
        ids = _seed_case_with_forms(self.engine, n_forms=1)
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            self._call(ids["case_id"], [])
        self.assertEqual(ctx.exception.status_code, 422)


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests: GET /api/cases/{case_id}/dossiers/{id}/zip
# ─────────────────────────────────────────────────────────────────────────────

class TestGetDossierZip(unittest.TestCase):

    def setUp(self):
        self.engine = _make_engine()
        self._eng_patcher = mock.patch.object(cases_router.main_db, "engine", self.engine)
        self._eng_patcher.start()
        self._access_patcher = mock.patch(
            "backend.app.routers.cases._assert_case_access", return_value=None
        )
        self._access_patcher.start()
        self._storage_patcher = mock.patch(
            "backend.app.routers.cases._try_store_dossier_pdf", return_value=None
        )
        self._storage_patcher.start()

        self._http_patcher = mock.patch("backend.app.routers.cases._requests")
        mock_req = self._http_patcher.start()
        mock_resp = mock.MagicMock()
        mock_resp.content = _make_test_pdf()
        mock_resp.raise_for_status = mock.MagicMock()
        mock_req.get.return_value = mock_resp

    def tearDown(self):
        self._eng_patcher.stop()
        self._access_patcher.stop()
        self._storage_patcher.stop()
        self._http_patcher.stop()

    def _create_dossier(self, case_id: str, form_ids: List[str]) -> str:
        result = create_dossier(
            case_id,
            CreateDossierPayload(name="Zip Test", form_ids=form_ids, cover_page=True),
            user=DUMMY_USER,
        )
        return result.id

    def _call_zip(self, case_id: str, dossier_id: str) -> Any:
        return get_dossier_zip(case_id, dossier_id, user=DUMMY_USER)

    # ── Criterion 4: ZIP contains N correctly named files ─────────────────────

    def test_zip_contains_correct_file_count(self):
        ids = _seed_case_with_forms(self.engine, n_forms=3)
        dossier_id = self._create_dossier(ids["case_id"], ids["cf_ids"])
        response = self._call_zip(ids["case_id"], dossier_id)
        self.assertEqual(response.media_type, "application/zip")
        zf = zipfile.ZipFile(io.BytesIO(response.body))
        names = zf.namelist()
        self.assertEqual(len(names), 3)

    def test_zip_filenames_padded_with_number(self):
        ids = _seed_case_with_forms(self.engine, n_forms=2)
        dossier_id = self._create_dossier(ids["case_id"], ids["cf_ids"])
        response = self._call_zip(ids["case_id"], dossier_id)
        zf = zipfile.ZipFile(io.BytesIO(response.body))
        names = zf.namelist()
        # Should start with 01_ and 02_
        self.assertTrue(any(n.startswith("01_") for n in names))
        self.assertTrue(any(n.startswith("02_") for n in names))

    def test_zip_files_are_valid_pdfs(self):
        ids = _seed_case_with_forms(self.engine, n_forms=2)
        dossier_id = self._create_dossier(ids["case_id"], ids["cf_ids"])
        response = self._call_zip(ids["case_id"], dossier_id)
        zf = zipfile.ZipFile(io.BytesIO(response.body))
        for name in zf.namelist():
            pdf_bytes = zf.read(name)
            self.assertTrue(pdf_bytes.startswith(b"%PDF-"), f"{name} is not a PDF")

    def test_zip_content_disposition_is_attachment(self):
        ids = _seed_case_with_forms(self.engine, n_forms=2)
        dossier_id = self._create_dossier(ids["case_id"], ids["cf_ids"])
        response = self._call_zip(ids["case_id"], dossier_id)
        cd = response.headers.get("Content-Disposition", "")
        self.assertIn("attachment", cd)
        self.assertIn(".zip", cd)

    # ── Criterion 7: unknown dossier → 404 ───────────────────────────────────

    def test_unknown_dossier_returns_404(self):
        ids = _seed_case_with_forms(self.engine, n_forms=1)
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            self._call_zip(ids["case_id"], _uuid())
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
