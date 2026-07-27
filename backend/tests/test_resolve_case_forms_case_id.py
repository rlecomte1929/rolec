"""AIQ-1719: the forms/dossier resolver maps an assignment id → the canonical case id.

The 8 forms/dossier reads (list_form_documents/comments/events, get_form_original,
get_dossier[_zip/_pdf], _load_form_with_template) key their SQL on the canonical case
id but a route can carry an assignment id, so they now resolve via
resolve_case_forms_case_id first. This proves that resolver actually maps an
assignment id to the canonical case id (and falls back safely) — the behaviour the
fix depends on. resolve_case_forms_case_id only resolves UUID-shaped ids (its own
guard), so this uses real UUIDs.
"""

from __future__ import annotations

import os
import threading
import unittest
import uuid
from unittest import mock

os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.app.services import case_service  # noqa: E402
from backend.app.services.case_service import resolve_case_forms_case_id  # noqa: E402

_ASSIGNMENT = str(uuid.uuid4())
_CANONICAL = str(uuid.uuid4())  # what case_forms / dossiers are keyed on


class ResolveCaseFormsCaseIdTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        with self.engine.begin() as c:
            c.execute(text(
                "CREATE TABLE case_assignments "
                "(id TEXT, case_id TEXT, canonical_case_id TEXT)"
            ))
            # assignment id DIFFERS from the canonical case id it maps to.
            c.execute(text(
                "INSERT INTO case_assignments VALUES (:a, :c, :c)"
            ), {"a": _ASSIGNMENT, "c": _CANONICAL})
        # case_service.main_db is a MagicMock under conftest; point its engine at sqlite.
        p = mock.patch.object(case_service.main_db, "engine", self.engine)
        p.start()
        self.addCleanup(p.stop)

    def test_assignment_id_maps_to_canonical(self):
        # THE FIX: a forms/dossier read handed the assignment id resolves to the
        # canonical case id its rows are actually keyed on.
        self.assertEqual(resolve_case_forms_case_id(_ASSIGNMENT), _CANONICAL)

    def test_canonical_and_case_id_map_to_canonical(self):
        self.assertEqual(resolve_case_forms_case_id(_CANONICAL), _CANONICAL)

    def test_unknown_uuid_passes_through(self):
        # Dossier tolerance: an id that resolves to no assignment is returned
        # unchanged (legacy public.cases ids), never None.
        other = str(uuid.uuid4())
        self.assertEqual(resolve_case_forms_case_id(other), other)

    def test_non_uuid_passes_through_without_a_query(self):
        self.assertEqual(resolve_case_forms_case_id("not-a-uuid"), "not-a-uuid")


if __name__ == "__main__":
    unittest.main()
