"""
[P3-6] Tests for DossierPackage persistence endpoints.

Endpoints under test:
  GET  /{case_id}/dossiers                          → list with is_stale flag
  GET  /{case_id}/dossiers/{dossier_id}             → get one with is_stale
  DELETE /{case_id}/dossiers/{dossier_id}           → 204, row gone
  POST /{case_id}/dossiers/{dossier_id}/regenerate  → rebuilds PDF, clears stale
  GET  /{case_id}/dossiers/{dossier_id}/pdf         → streams PDF bytes

Validation criteria (from Notion task spec):
  1. List returns all packages for a case, newest first.
  2. is_stale=False when no field values exist / no generated_at.
  3. is_stale=True when a field value's updated_at is newer than generated_at.
  4. is_stale=False immediately after regenerate.
  5. Delete removes the row; subsequent list returns empty.
  6. Get 404 for unknown dossier id.
  7. Regenerate returns a valid DossierPackageDetailResponse.
  8. PDF endpoint returns bytes starting with %PDF-.
"""
from __future__ import annotations

import io
import json
import os
import sys
import uuid
import unittest
from typing import Any, Dict, List
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import unittest.mock as _umock
from pydantic import BaseModel as _PydanticBase
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException


class _AnyModel(_PydanticBase):
    model_config = {"extra": "allow"}


# ── Stub heavy deps before importing router ───────────────────────────────────

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
    list_dossiers,
    get_dossier,
    delete_dossier,
    regenerate_dossier,
    get_dossier_pdf,
    CreateDossierPayload,
    _dossier_is_stale,
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

DUMMY_USER: Dict[str, Any] = {"id": str(uuid.uuid4()), "role": "employee", "is_admin": False}


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


def _seed_case_with_forms(engine, n_forms: int = 2) -> Dict[str, Any]:
    """Insert a case + N forms + one field value each. Returns ids."""
    case_id = _uuid()
    cf_ids = []
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO cases (id) VALUES (:id)"), {"id": case_id})
        for i in range(n_forms):
            tmpl_id = _uuid()
            cf_id = _uuid()
            conn.execute(text(
                "INSERT INTO form_templates (id,code,name,fields) VALUES (:id,:c,:n,:f)"
            ), {"id": tmpl_id, "c": f"UTL-{3000+i}", "n": f"Form {i+1}", "f": _FIELDS_JSON})
            conn.execute(text(
                "INSERT INTO case_forms (id,case_id,form_template_id,status) "
                "VALUES (:id,:cid,:tid,'in_progress')"
            ), {"id": cf_id, "cid": case_id, "tid": tmpl_id})
            conn.execute(text(
                "INSERT INTO case_form_field_values "
                "(id,case_form_id,field_id,value,filled_by,updated_at) "
                "VALUES (:id,:cid,:fid,:v,'human','2026-01-01T00:00:00')"
            ), {"id": _uuid(), "cid": cf_id, "fid": "first_name", "v": f"Value{i}"})
            cf_ids.append(cf_id)
    return {"case_id": case_id, "cf_ids": cf_ids}


def _insert_dossier(engine, case_id: str, form_ids: List[str],
                    name: str = "My Dossier",
                    generated_at: str | None = None) -> str:
    """Insert a dossier_packages row directly. Returns dossier id."""
    dossier_id = _uuid()
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO dossier_packages (id, case_id, name, form_ids, cover_page, generated_at) "
            "VALUES (:id, :cid, :name, :fids, 1, :gen)"
        ), {
            "id": dossier_id,
            "cid": case_id,
            "name": name,
            "fids": json.dumps(form_ids),
            "gen": generated_at,
        })
    return dossier_id


# ── Shared setUp mixin ─────────────────────────────────────────────────────────

class _DossierTestBase(unittest.TestCase):
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
        mock_resp.ok = False  # force on-the-fly regeneration in pdf endpoint
        mock_resp.raise_for_status = mock.MagicMock()
        mock_req.get.return_value = mock_resp

    def tearDown(self):
        self._eng_patcher.stop()
        self._access_patcher.stop()
        self._storage_patcher.stop()
        self._http_patcher.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: _dossier_is_stale helper
# ─────────────────────────────────────────────────────────────────────────────

class TestDossierIsStale(unittest.TestCase):
    def setUp(self):
        self.engine = _make_engine()

    def _conn(self):
        return self.engine.connect()

    def test_not_stale_when_no_generated_at(self):
        ids = _seed_case_with_forms(self.engine, 1)
        with self.engine.connect() as conn:
            result = _dossier_is_stale(conn, ids["cf_ids"], None)
        self.assertFalse(result)

    def test_not_stale_when_no_form_ids(self):
        with self.engine.connect() as conn:
            result = _dossier_is_stale(conn, [], "2026-05-01T00:00:00")
        self.assertFalse(result)

    def test_not_stale_when_field_updated_before_generated(self):
        """Field updated at 2026-01-01, dossier generated at 2026-05-01 → not stale."""
        ids = _seed_case_with_forms(self.engine, 1)
        # field updated_at = 2026-01-01 (set in _seed_case_with_forms)
        with self.engine.connect() as conn:
            result = _dossier_is_stale(conn, ids["cf_ids"], "2026-05-01T00:00:00")
        self.assertFalse(result)

    def test_stale_when_field_updated_after_generated(self):
        """Field updated at 2026-06-01, dossier generated at 2026-05-01 → stale."""
        ids = _seed_case_with_forms(self.engine, 1)
        # Force a later updated_at on the field value
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE case_form_field_values SET updated_at = '2026-06-01T00:00:00' "
                "WHERE case_form_id = :cfid"
            ), {"cfid": ids["cf_ids"][0]})
        with self.engine.connect() as conn:
            result = _dossier_is_stale(conn, ids["cf_ids"], "2026-05-01T00:00:00")
        self.assertTrue(result)

    def test_stale_with_multiple_forms_one_updated(self):
        """Only one of two forms updated → still stale."""
        ids = _seed_case_with_forms(self.engine, 2)
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE case_form_field_values SET updated_at = '2026-12-01T00:00:00' "
                "WHERE case_form_id = :cfid"
            ), {"cfid": ids["cf_ids"][1]})
        with self.engine.connect() as conn:
            result = _dossier_is_stale(conn, ids["cf_ids"], "2026-05-01T00:00:00")
        self.assertTrue(result)


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests: GET /{case_id}/dossiers  (list)
# ─────────────────────────────────────────────────────────────────────────────

class TestListDossiers(_DossierTestBase):

    def test_empty_list_when_no_packages(self):
        case_id = _uuid()
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO cases (id) VALUES (:id)"), {"id": case_id})
        result = list_dossiers(case_id, user=DUMMY_USER)
        self.assertEqual(result, [])

    def test_returns_all_packages_for_case(self):
        ids = _seed_case_with_forms(self.engine, 2)
        _insert_dossier(self.engine, ids["case_id"], ids["cf_ids"], "Dossier A")
        _insert_dossier(self.engine, ids["case_id"], ids["cf_ids"], "Dossier B")
        result = list_dossiers(ids["case_id"], user=DUMMY_USER)
        self.assertEqual(len(result), 2)

    def test_does_not_return_other_case_packages(self):
        ids1 = _seed_case_with_forms(self.engine, 1)
        ids2 = _seed_case_with_forms(self.engine, 1)
        _insert_dossier(self.engine, ids1["case_id"], ids1["cf_ids"], "Case1 Dossier")
        result = list_dossiers(ids2["case_id"], user=DUMMY_USER)
        self.assertEqual(result, [])

    def test_is_stale_false_when_no_generated_at(self):
        ids = _seed_case_with_forms(self.engine, 1)
        _insert_dossier(self.engine, ids["case_id"], ids["cf_ids"],
                        generated_at=None)
        result = list_dossiers(ids["case_id"], user=DUMMY_USER)
        self.assertFalse(result[0].is_stale)

    def test_is_stale_false_when_fields_older_than_generated(self):
        ids = _seed_case_with_forms(self.engine, 1)
        # field updated_at = 2026-01-01; generated_at = 2026-05-01
        _insert_dossier(self.engine, ids["case_id"], ids["cf_ids"],
                        generated_at="2026-05-01T00:00:00")
        result = list_dossiers(ids["case_id"], user=DUMMY_USER)
        self.assertFalse(result[0].is_stale)

    def test_is_stale_true_when_field_updated_after_generation(self):
        """Criterion 3: stale flag propagates through list endpoint."""
        ids = _seed_case_with_forms(self.engine, 1)
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE case_form_field_values SET updated_at = '2026-12-01T00:00:00' "
                "WHERE case_form_id = :cfid"
            ), {"cfid": ids["cf_ids"][0]})
        _insert_dossier(self.engine, ids["case_id"], ids["cf_ids"],
                        generated_at="2026-05-01T00:00:00")
        result = list_dossiers(ids["case_id"], user=DUMMY_USER)
        self.assertTrue(result[0].is_stale)

    def test_form_ids_deserialized_correctly(self):
        ids = _seed_case_with_forms(self.engine, 3)
        _insert_dossier(self.engine, ids["case_id"], ids["cf_ids"])
        result = list_dossiers(ids["case_id"], user=DUMMY_USER)
        self.assertEqual(sorted(result[0].form_ids), sorted(ids["cf_ids"]))


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests: GET /{case_id}/dossiers/{dossier_id}  (get one)
# ─────────────────────────────────────────────────────────────────────────────

class TestGetDossier(_DossierTestBase):

    def test_returns_correct_dossier(self):
        ids = _seed_case_with_forms(self.engine, 2)
        did = _insert_dossier(self.engine, ids["case_id"], ids["cf_ids"], "My Pkg")
        result = get_dossier(ids["case_id"], did, user=DUMMY_USER)
        self.assertEqual(result.id, did)
        self.assertEqual(result.name, "My Pkg")
        self.assertEqual(result.case_id, ids["case_id"])

    def test_raises_404_for_unknown_id(self):
        case_id = _uuid()
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO cases (id) VALUES (:id)"), {"id": case_id})
        with self.assertRaises(HTTPException) as ctx:
            get_dossier(case_id, _uuid(), user=DUMMY_USER)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_raises_404_for_wrong_case(self):
        ids = _seed_case_with_forms(self.engine, 1)
        did = _insert_dossier(self.engine, ids["case_id"], ids["cf_ids"])
        other_case = _uuid()
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO cases (id) VALUES (:id)"), {"id": other_case})
        with self.assertRaises(HTTPException) as ctx:
            get_dossier(other_case, did, user=DUMMY_USER)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_is_stale_reported_correctly(self):
        ids = _seed_case_with_forms(self.engine, 1)
        # Mark field as updated after generated_at
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE case_form_field_values SET updated_at = '2027-01-01T00:00:00' "
                "WHERE case_form_id = :cfid"
            ), {"cfid": ids["cf_ids"][0]})
        did = _insert_dossier(self.engine, ids["case_id"], ids["cf_ids"],
                              generated_at="2026-05-01T00:00:00")
        result = get_dossier(ids["case_id"], did, user=DUMMY_USER)
        self.assertTrue(result.is_stale)


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests: DELETE /{case_id}/dossiers/{dossier_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteDossier(_DossierTestBase):

    def test_delete_removes_row(self):
        """Criterion 5: after delete, list returns empty."""
        ids = _seed_case_with_forms(self.engine, 1)
        did = _insert_dossier(self.engine, ids["case_id"], ids["cf_ids"])
        delete_dossier(ids["case_id"], did, user=DUMMY_USER)
        remaining = list_dossiers(ids["case_id"], user=DUMMY_USER)
        self.assertEqual(remaining, [])

    def test_delete_returns_204(self):
        ids = _seed_case_with_forms(self.engine, 1)
        did = _insert_dossier(self.engine, ids["case_id"], ids["cf_ids"])
        resp = delete_dossier(ids["case_id"], did, user=DUMMY_USER)
        self.assertEqual(resp.status_code, 204)

    def test_delete_404_for_unknown(self):
        case_id = _uuid()
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO cases (id) VALUES (:id)"), {"id": case_id})
        with self.assertRaises(HTTPException) as ctx:
            delete_dossier(case_id, _uuid(), user=DUMMY_USER)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_delete_only_affects_target_dossier(self):
        ids = _seed_case_with_forms(self.engine, 1)
        did1 = _insert_dossier(self.engine, ids["case_id"], ids["cf_ids"], "Keep")
        did2 = _insert_dossier(self.engine, ids["case_id"], ids["cf_ids"], "Delete me")
        delete_dossier(ids["case_id"], did2, user=DUMMY_USER)
        remaining = list_dossiers(ids["case_id"], user=DUMMY_USER)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].id, did1)


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests: POST /{case_id}/dossiers/{dossier_id}/regenerate
# ─────────────────────────────────────────────────────────────────────────────

class TestRegenerateDossier(_DossierTestBase):

    def test_returns_dossier_detail(self):
        """Criterion 7: regenerate returns DossierPackageDetailResponse."""
        ids = _seed_case_with_forms(self.engine, 2)
        did = _insert_dossier(self.engine, ids["case_id"], ids["cf_ids"],
                              generated_at="2026-01-01T00:00:00")
        result = regenerate_dossier(ids["case_id"], did, user=DUMMY_USER)
        self.assertEqual(result.id, did)
        self.assertEqual(result.case_id, ids["case_id"])

    def test_is_stale_false_after_regenerate(self):
        """Criterion 4: is_stale is False immediately after regeneration."""
        ids = _seed_case_with_forms(self.engine, 1)
        # Make field stale before regenerating
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE case_form_field_values SET updated_at = '2026-12-01T00:00:00' "
                "WHERE case_form_id = :cfid"
            ), {"cfid": ids["cf_ids"][0]})
        did = _insert_dossier(self.engine, ids["case_id"], ids["cf_ids"],
                              generated_at="2026-05-01T00:00:00")
        # Confirm it was stale before
        pre = get_dossier(ids["case_id"], did, user=DUMMY_USER)
        self.assertTrue(pre.is_stale)
        # Regenerate
        result = regenerate_dossier(ids["case_id"], did, user=DUMMY_USER)
        self.assertFalse(result.is_stale)

    def test_regenerate_updates_generated_at(self):
        ids = _seed_case_with_forms(self.engine, 1)
        did = _insert_dossier(self.engine, ids["case_id"], ids["cf_ids"],
                              generated_at="2026-01-01T00:00:00")
        result = regenerate_dossier(ids["case_id"], did, user=DUMMY_USER)
        self.assertIsNotNone(result.generated_at)
        self.assertGreater(result.generated_at, "2026-01-01T00:00:00")  # type: ignore[operator]

    def test_regenerate_404_for_unknown(self):
        case_id = _uuid()
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO cases (id) VALUES (:id)"), {"id": case_id})
        with self.assertRaises(HTTPException) as ctx:
            regenerate_dossier(case_id, _uuid(), user=DUMMY_USER)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_regenerate_422_for_empty_form_ids(self):
        case_id = _uuid()
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO cases (id) VALUES (:id)"), {"id": case_id})
        did = _insert_dossier(self.engine, case_id, [], "Empty")
        with self.assertRaises(HTTPException) as ctx:
            regenerate_dossier(case_id, did, user=DUMMY_USER)
        self.assertEqual(ctx.exception.status_code, 422)


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests: GET /{case_id}/dossiers/{dossier_id}/pdf
# ─────────────────────────────────────────────────────────────────────────────

class TestGetDossierPdf(_DossierTestBase):

    def test_returns_pdf_bytes(self):
        """Criterion 8: PDF endpoint returns bytes starting with %PDF-."""
        ids = _seed_case_with_forms(self.engine, 2)
        did = _insert_dossier(self.engine, ids["case_id"], ids["cf_ids"])
        resp = get_dossier_pdf(ids["case_id"], did, user=DUMMY_USER)
        self.assertEqual(resp.media_type, "application/pdf")
        self.assertTrue(resp.body[:5] == b"%PDF-")

    def test_returns_pdf_with_cover_page(self):
        ids = _seed_case_with_forms(self.engine, 1)
        # cover_page=1 already in _insert_dossier
        did = _insert_dossier(self.engine, ids["case_id"], ids["cf_ids"])
        resp = get_dossier_pdf(ids["case_id"], did, user=DUMMY_USER)
        self.assertTrue(resp.body[:5] == b"%PDF-")

    def test_returns_404_for_unknown_dossier(self):
        case_id = _uuid()
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO cases (id) VALUES (:id)"), {"id": case_id})
        with self.assertRaises(HTTPException) as ctx:
            get_dossier_pdf(case_id, _uuid(), user=DUMMY_USER)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_content_disposition_is_attachment(self):
        ids = _seed_case_with_forms(self.engine, 1)
        did = _insert_dossier(self.engine, ids["case_id"], ids["cf_ids"], "MyPkg")
        resp = get_dossier_pdf(ids["case_id"], did, user=DUMMY_USER)
        disposition = resp.headers.get("Content-Disposition", "")
        self.assertIn("attachment", disposition)


if __name__ == "__main__":
    unittest.main()
