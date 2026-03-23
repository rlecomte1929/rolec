"""Mobility graph route access: bridge lookup + assignment visibility gate."""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.database as dbmod
from backend.database import Database
from backend.services.mobility_route_access import enforce_mobility_graph_read_access
from sqlalchemy import create_engine, text


class MobilityRouteAccessEnforceTests(unittest.TestCase):
    def test_non_admin_no_bridge_returns_404(self) -> None:
        db = MagicMock()
        db.get_assignment_id_for_mobility_case.return_value = None
        db.mobility_case_row_exists.return_value = True
        with self.assertRaises(HTTPException) as ctx:
            enforce_mobility_graph_read_access(db, str(uuid.uuid4()), {"is_admin": False, "role": "EMPLOYEE"})
        self.assertEqual(ctx.exception.status_code, 404)

    def test_non_admin_empty_case_id_400(self) -> None:
        db = MagicMock()
        with self.assertRaises(HTTPException) as ctx:
            enforce_mobility_graph_read_access(db, "  ", {"is_admin": False})
        self.assertEqual(ctx.exception.status_code, 400)

    @patch("backend.services.mobility_route_access._load_assignment_visibility_check")
    def test_non_admin_with_bridge_calls_assignment_visibility(self, mock_ld: MagicMock) -> None:
        fn = MagicMock()
        mock_ld.return_value = fn
        db = MagicMock()
        db.get_assignment_id_for_mobility_case.return_value = "assign-1"
        user = {"is_admin": False, "role": "EMPLOYEE", "id": "u1"}
        enforce_mobility_graph_read_access(db, "mc-1", user)
        fn.assert_called_once_with("assign-1", user)

    def test_admin_requires_mobility_row(self) -> None:
        db = MagicMock()
        db.mobility_case_row_exists.return_value = False
        with self.assertRaises(HTTPException) as ctx:
            enforce_mobility_graph_read_access(db, str(uuid.uuid4()), {"is_admin": True})
        self.assertEqual(ctx.exception.status_code, 404)
        db.get_assignment_id_for_mobility_case.assert_not_called()

    def test_admin_with_row_skips_bridge(self) -> None:
        db = MagicMock()
        db.mobility_case_row_exists.return_value = True
        enforce_mobility_graph_read_access(db, "mc-1", {"is_admin": True})
        db.get_assignment_id_for_mobility_case.assert_not_called()


class DatabaseMobilityLookupTests(unittest.TestCase):
    def setUp(self) -> None:
        eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        self._prev_engine = dbmod._engine
        self._prev_sqlite = dbmod._is_sqlite
        dbmod._engine = eng
        dbmod._is_sqlite = True
        self.db = Database()

    def tearDown(self) -> None:
        dbmod._engine = self._prev_engine
        dbmod._is_sqlite = self._prev_sqlite

    def test_get_assignment_id_for_mobility_case_roundtrip(self) -> None:
        db = self.db
        mid = str(uuid.uuid4())
        aid = str(uuid.uuid4())
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO mobility_cases (id, company_id, employee_user_id, metadata, created_at, updated_at) "
                    "VALUES (:id, :co, :eu, '{}', 't', 't')"
                ),
                {"id": mid, "co": str(uuid.uuid4()), "eu": str(uuid.uuid4())},
            )
            conn.execute(
                text(
                    "INSERT INTO assignment_mobility_links (id, assignment_id, mobility_case_id, created_at, updated_at) "
                    "VALUES (:id, :aid, :mid, 't', 't')"
                ),
                {"id": str(uuid.uuid4()), "aid": aid, "mid": mid},
            )
        self.assertEqual(db.get_assignment_id_for_mobility_case(mid), aid)
        self.assertTrue(db.mobility_case_row_exists(mid))
        self.assertIsNone(db.get_assignment_id_for_mobility_case(str(uuid.uuid4())))


if __name__ == "__main__":
    unittest.main()
