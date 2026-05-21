"""
Tests for backend/app/routers/admin_form_templates.py.

Mirrors the pattern in test_exception_requests_router.py: swap `db.engine` for
an in-memory SQLite engine, preload a schema that mirrors the public.form_templates
table, then exercise the router functions directly (bypasses FastAPI's
dependency injection).
"""
from __future__ import annotations

import json
import os
import sys
import unittest
import uuid
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import admin_form_templates as router_module  # noqa: E402
from backend.app.routers.admin_form_templates import (  # noqa: E402
    FormTemplateCreate,
    FormTemplateUpdate,
    _merge,
    _row_to_dict,
    create_form_template,
    get_form_template,
    list_form_templates,
    update_form_template,
)
from fastapi import HTTPException  # noqa: E402


# SQLite mirror of the public.form_templates schema (Postgres jsonb → TEXT in SQLite).
SCHEMA = """
CREATE TABLE form_templates (
  id               TEXT PRIMARY KEY,
  code             TEXT NOT NULL,
  name             TEXT NOT NULL,
  country          TEXT NOT NULL,
  authority_code   TEXT,
  authority_name   TEXT,
  category         TEXT,
  original_pdf_url TEXT,
  fields           TEXT NOT NULL DEFAULT '[]',
  trigger_rules    TEXT NOT NULL DEFAULT '{}',
  version          TEXT NOT NULL DEFAULT '1.0.0',
  -- Match the Postgres `DEFAULT now()` behaviour so the router can omit
  -- created_at / updated_at from INSERTs (Postgres timestamptz rejects the
  -- isoformat string we used to pass — see admin_form_templates.create_form_template).
  created_at       TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (code, version)
);
"""


def _admin_user(uid: str | None = None) -> dict:
    return {"id": uid or str(uuid.uuid4()), "role": "ADMIN", "is_admin": True}


class AdminFormTemplatesRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        self.engine_patcher = mock.patch.object(router_module.db, "engine", self.engine)
        self.engine_patcher.start()
        self.addCleanup(self.engine_patcher.stop)
        self.user = _admin_user()

    # ------------------------------------------------------------------
    # POST / create
    # ------------------------------------------------------------------
    def test_create_inserts_row_with_defaults(self) -> None:
        body = FormTemplateCreate(
            code="UTL-2011",
            name="Notification of move (NO)",
            country="NO",
        )
        result = create_form_template(body=body, user=self.user)

        self.assertEqual(result["code"], "UTL-2011")
        self.assertEqual(result["name"], "Notification of move (NO)")
        self.assertEqual(result["country"], "NO")
        self.assertEqual(result["version"], "1.0.0")
        self.assertEqual(result["fields"], [])
        self.assertEqual(result["trigger_rules"], {})
        self.assertIsNotNone(result["id"])
        self.assertIsNotNone(result["created_at"])
        self.assertIsNotNone(result["updated_at"])

    def test_create_uppercases_country(self) -> None:
        body = FormTemplateCreate(code="X1", name="x", country="no")
        result = create_form_template(body=body, user=self.user)
        self.assertEqual(result["country"], "NO")

    def test_create_persists_fields_and_trigger_rules(self) -> None:
        body = FormTemplateCreate(
            code="UTL-2012",
            name="With fields",
            country="NO",
            fields=[{"id": "first_name", "label": "First name", "type": "text"}],
            trigger_rules={"dest_country": "NO", "pathway": "eea_registration"},
        )
        result = create_form_template(body=body, user=self.user)
        self.assertEqual(len(result["fields"]), 1)
        self.assertEqual(result["fields"][0]["id"], "first_name")
        self.assertEqual(result["trigger_rules"]["dest_country"], "NO")

    def test_create_409_on_duplicate_code_version(self) -> None:
        body = FormTemplateCreate(code="DUP-1", name="first", country="NO")
        create_form_template(body=body, user=self.user)
        with self.assertRaises(HTTPException) as ctx:
            create_form_template(body=body, user=self.user)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_create_same_code_different_version_allowed(self) -> None:
        a = FormTemplateCreate(code="MV-1", name="v1", country="NO", version="1.0.0")
        b = FormTemplateCreate(code="MV-1", name="v2", country="NO", version="2.0.0")
        create_form_template(body=a, user=self.user)
        result = create_form_template(body=b, user=self.user)
        self.assertEqual(result["version"], "2.0.0")

        listing = list_form_templates(
            country=None, category=None, code="MV-1", limit=100, offset=0, user=self.user
        )
        self.assertEqual(len(listing), 2)

    # ------------------------------------------------------------------
    # GET / list & detail
    # ------------------------------------------------------------------
    def test_list_filters_by_country(self) -> None:
        for code, country in [("NO-1", "NO"), ("FR-1", "FR"), ("NO-2", "NO")]:
            create_form_template(
                body=FormTemplateCreate(code=code, name=code, country=country),
                user=self.user,
            )
        no_rows = list_form_templates(
            country="NO", category=None, code=None, limit=100, offset=0, user=self.user
        )
        self.assertEqual(len(no_rows), 2)
        self.assertTrue(all(r["country"] == "NO" for r in no_rows))

    def test_list_filters_by_category(self) -> None:
        create_form_template(
            body=FormTemplateCreate(code="A", name="a", country="NO", category="registration"),
            user=self.user,
        )
        create_form_template(
            body=FormTemplateCreate(code="B", name="b", country="NO", category="tax"),
            user=self.user,
        )
        rows = list_form_templates(
            country=None,
            category="registration",
            code=None,
            limit=100,
            offset=0,
            user=self.user,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "registration")

    def test_get_returns_full_row(self) -> None:
        created = create_form_template(
            body=FormTemplateCreate(code="G-1", name="get me", country="NO"),
            user=self.user,
        )
        fetched = get_form_template(template_id=created["id"], user=self.user)
        self.assertEqual(fetched["id"], created["id"])
        self.assertEqual(fetched["name"], "get me")

    def test_get_404_when_missing(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            get_form_template(template_id=str(uuid.uuid4()), user=self.user)
        self.assertEqual(ctx.exception.status_code, 404)

    # ------------------------------------------------------------------
    # PATCH / update
    # ------------------------------------------------------------------
    def test_patch_in_place_updates_same_row(self) -> None:
        created = create_form_template(
            body=FormTemplateCreate(code="P-1", name="old", country="NO"),
            user=self.user,
        )
        result = update_form_template(
            template_id=created["id"],
            body=FormTemplateUpdate(name="new"),
            user=self.user,
        )
        self.assertEqual(result["id"], created["id"])  # same row
        self.assertEqual(result["name"], "new")

        listing = list_form_templates(
            country=None, category=None, code="P-1", limit=100, offset=0, user=self.user
        )
        self.assertEqual(len(listing), 1)  # no new row created

    def test_patch_same_version_is_in_place(self) -> None:
        created = create_form_template(
            body=FormTemplateCreate(code="P-2", name="x", country="NO", version="1.0.0"),
            user=self.user,
        )
        result = update_form_template(
            template_id=created["id"],
            body=FormTemplateUpdate(version="1.0.0", name="y"),
            user=self.user,
        )
        self.assertEqual(result["id"], created["id"])
        self.assertEqual(result["name"], "y")

    def test_patch_version_bump_creates_new_row(self) -> None:
        created = create_form_template(
            body=FormTemplateCreate(
                code="VB-1",
                name="v1 name",
                country="NO",
                version="1.0.0",
                fields=[{"id": "old_field"}],
            ),
            user=self.user,
        )
        result = update_form_template(
            template_id=created["id"],
            body=FormTemplateUpdate(version="2.0.0", name="v2 name"),
            user=self.user,
        )
        self.assertNotEqual(result["id"], created["id"])  # new row
        self.assertEqual(result["version"], "2.0.0")
        self.assertEqual(result["name"], "v2 name")
        # Merged from old: fields preserved
        self.assertEqual(result["fields"], [{"id": "old_field"}])

        # Both rows exist
        listing = list_form_templates(
            country=None, category=None, code="VB-1", limit=100, offset=0, user=self.user
        )
        self.assertEqual(len(listing), 2)
        versions = sorted(r["version"] for r in listing)
        self.assertEqual(versions, ["1.0.0", "2.0.0"])

        # Old row unchanged
        old = get_form_template(template_id=created["id"], user=self.user)
        self.assertEqual(old["name"], "v1 name")
        self.assertEqual(old["version"], "1.0.0")

    def test_patch_version_bump_409_when_target_version_exists(self) -> None:
        a = create_form_template(
            body=FormTemplateCreate(code="DUP-V", name="a", country="NO", version="1.0.0"),
            user=self.user,
        )
        create_form_template(
            body=FormTemplateCreate(code="DUP-V", name="b", country="NO", version="2.0.0"),
            user=self.user,
        )
        with self.assertRaises(HTTPException) as ctx:
            update_form_template(
                template_id=a["id"],
                body=FormTemplateUpdate(version="2.0.0"),
                user=self.user,
            )
        self.assertEqual(ctx.exception.status_code, 409)

    def test_patch_404_when_id_missing(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            update_form_template(
                template_id=str(uuid.uuid4()),
                body=FormTemplateUpdate(name="x"),
                user=self.user,
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_patch_can_update_fields_and_trigger_rules(self) -> None:
        created = create_form_template(
            body=FormTemplateCreate(code="J-1", name="x", country="NO"),
            user=self.user,
        )
        result = update_form_template(
            template_id=created["id"],
            body=FormTemplateUpdate(
                fields=[{"id": "name", "label": "Name"}],
                trigger_rules={"dest_country": "NO"},
            ),
            user=self.user,
        )
        self.assertEqual(len(result["fields"]), 1)
        self.assertEqual(result["fields"][0]["id"], "name")
        self.assertEqual(result["trigger_rules"]["dest_country"], "NO")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def test_merge_uses_only_set_fields(self) -> None:
        current = {"name": "old", "country": "NO", "fields": [{"id": "x"}]}
        patch = FormTemplateUpdate(name="new")  # country/fields not set
        merged = _merge(current, patch)
        self.assertEqual(merged["name"], "new")
        self.assertEqual(merged["country"], "NO")
        self.assertEqual(merged["fields"], [{"id": "x"}])

    def test_row_to_dict_parses_sqlite_json_strings(self) -> None:
        row = {
            "id": "abc",
            "code": "X",
            "fields": '[{"id":"a"}]',
            "trigger_rules": '{"k":"v"}',
        }
        out = _row_to_dict(row)
        self.assertEqual(out["fields"], [{"id": "a"}])
        self.assertEqual(out["trigger_rules"], {"k": "v"})

    def test_row_to_dict_handles_null_jsonb(self) -> None:
        row = {"id": "abc", "code": "X", "fields": None, "trigger_rules": None}
        out = _row_to_dict(row)
        self.assertEqual(out["fields"], [])
        self.assertEqual(out["trigger_rules"], {})


if __name__ == "__main__":
    unittest.main()
