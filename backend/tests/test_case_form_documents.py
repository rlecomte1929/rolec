"""
[P1-05c / AIQ-678] Per-form supporting document upload/list/delete.

Exercises the LIVE wired handlers:
  - cases_write.upload_form_document  (POST)
  - cases_read.list_form_documents    (GET)
  - cases_write.delete_form_document  (DELETE)

In-memory SQLite + mocked main_db.engine; Supabase Storage is mocked so the
tests run without network/bucket access. Mirrors test_case_dossier_forms*.py.
"""
from __future__ import annotations

import asyncio
import io
import os
import sys
import unittest
import uuid
from unittest import mock

from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import cases_read as read_mod  # noqa: E402
from backend.app.routers import cases_write as write_mod  # noqa: E402
from backend.app.routers.cases_read import list_form_documents  # noqa: E402
from backend.app.routers.cases_write import (  # noqa: E402
    upload_form_document,
    delete_form_document,
)

SCHEMA = """
CREATE TABLE cases (id TEXT PRIMARY KEY, company_id TEXT, employee_id TEXT, hr_owner_id TEXT);
CREATE TABLE profiles (id TEXT PRIMARY KEY, email TEXT, full_name TEXT, company_id TEXT);
CREATE TABLE case_forms (
  id TEXT PRIMARY KEY, case_id TEXT NOT NULL, form_template_id TEXT,
  status TEXT NOT NULL DEFAULT 'not_started'
);
CREATE TABLE case_form_documents (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  case_form_id TEXT NOT NULL, case_id TEXT NOT NULL,
  file_name TEXT NOT NULL, storage_path TEXT NOT NULL,
  content_type TEXT, size_bytes INTEGER, uploaded_by TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _u() -> str:
    return str(uuid.uuid4())


def _emp(uid: str) -> dict:
    return {"id": uid, "role": "EMPLOYEE", "is_admin": False}


class FormDocumentsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))
        # cases_read and cases_write both import the same `db` object; patch both refs.
        for mod in (read_mod, write_mod):
            p = mock.patch.object(mod.main_db, "engine", self.engine)
            p.start()
            self.addCleanup(p.stop)

        # Mock the Supabase admin client used for storage (lazy-imported in handlers).
        self.sb = mock.MagicMock()
        self.sb.storage.from_.return_value.create_signed_url.return_value = {
            "signedUrl": "https://signed.example/doc"
        }
        sb_patch = mock.patch(
            "backend.app.services.supabase_client.get_supabase_admin_client",
            return_value=self.sb,
        )
        sb_patch.start()
        self.addCleanup(sb_patch.stop)

        self.company_id, self.employee_id, self.case_id, self.form_id = _u(), _u(), _u(), _u()
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO profiles (id, email, full_name, company_id) "
                              "VALUES (:i,:e,:n,:c)"),
                         {"i": self.employee_id, "e": "e@x.com", "n": "Marc", "c": self.company_id})
            conn.execute(text("INSERT INTO cases (id, company_id, employee_id) VALUES (:i,:c,:e)"),
                         {"i": self.case_id, "c": self.company_id, "e": self.employee_id})
            conn.execute(text("INSERT INTO case_forms (id, case_id) VALUES (:i,:c)"),
                         {"i": self.form_id, "c": self.case_id})

    def _upload(self, name="passport.pdf", data=b"hello-bytes"):
        up = UploadFile(filename=name, file=io.BytesIO(data))
        return asyncio.run(
            upload_form_document(
                case_id=self.case_id, form_id=self.form_id, file=up,
                user=_emp(self.employee_id),
            )
        )

    def test_upload_inserts_scoped_row(self) -> None:
        item = self._upload()
        self.assertEqual(item.case_id, self.case_id)
        self.assertEqual(item.case_form_id, self.form_id)
        self.assertEqual(item.file_name, "passport.pdf")
        self.assertEqual(item.size_bytes, len(b"hello-bytes"))
        self.assertEqual(item.uploaded_by, self.employee_id)
        # Storage upload was actually invoked on the case-documents bucket.
        self.sb.storage.from_.assert_any_call("case-documents")
        # Row is queryable with correct scope.
        with self.engine.connect() as conn:
            n = conn.execute(
                text("SELECT COUNT(*) FROM case_form_documents "
                     "WHERE case_form_id=:f AND case_id=:c"),
                {"f": self.form_id, "c": self.case_id},
            ).scalar()
        self.assertEqual(n, 1)

    def test_list_returns_uploaded_docs_with_signed_url(self) -> None:
        self._upload(name="a.pdf")
        self._upload(name="b.pdf")
        rows = list_form_documents(
            case_id=self.case_id, form_id=self.form_id, user=_emp(self.employee_id)
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual({r.file_name for r in rows}, {"a.pdf", "b.pdf"})
        self.assertTrue(all(r.download_url == "https://signed.example/doc" for r in rows))

    def test_filename_is_sanitized(self) -> None:
        item = self._upload(name="../../etc/passwd 攻.pdf")
        self.assertNotIn("/", item.file_name)
        self.assertNotIn("..", item.file_name)

    def test_empty_file_rejected(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            self._upload(data=b"")
        self.assertEqual(ctx.exception.status_code, 422)

    def test_upload_404_when_form_not_in_case(self) -> None:
        up = UploadFile(filename="x.pdf", file=io.BytesIO(b"x"))
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(upload_form_document(
                case_id=self.case_id, form_id=_u(), file=up, user=_emp(self.employee_id)))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_delete_removes_row(self) -> None:
        item = self._upload()
        resp = delete_form_document(
            case_id=self.case_id, form_id=self.form_id, document_id=item.id,
            user=_emp(self.employee_id),
        )
        self.assertEqual(resp.status_code, 204)
        with self.engine.connect() as conn:
            n = conn.execute(text("SELECT COUNT(*) FROM case_form_documents")).scalar()
        self.assertEqual(n, 0)

    def test_delete_404_for_unknown_doc(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            delete_form_document(
                case_id=self.case_id, form_id=self.form_id, document_id=_u(),
                user=_emp(self.employee_id),
            )
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
