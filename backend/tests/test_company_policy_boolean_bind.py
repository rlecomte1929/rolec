"""Postgres: is_default_template uses SQL CASE + integer bind so the column is boolean-typed."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.database import Database  # noqa: E402


_FULL_CP_COLS = {
    "id",
    "company_id",
    "title",
    "version",
    "effective_date",
    "file_url",
    "file_type",
    "extraction_status",
    "created_by",
    "created_at",
    "template_source",
    "template_name",
    "is_default_template",
}


class TestCompanyPolicyBooleanBind(unittest.TestCase):
    def test_create_company_policy_binds_python_bool_for_postgres(self) -> None:
        """Postgres INSERT uses CASE + :cp_isdef_i so is_default_template is boolean in SQL."""
        captured: list[dict] = []

        def capture_execute(stmt, params=None):
            captured.append({"sql": str(stmt), "params": dict(params or {})})
            return MagicMock()

        mock_conn = MagicMock()
        mock_conn.execute.side_effect = capture_execute
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_conn)
        ctx.__exit__ = MagicMock(return_value=False)

        d = Database.__new__(Database)
        d.engine = MagicMock()
        d.engine.begin.return_value = ctx

        with patch("backend.database._get_company_policies_columns", return_value=_FULL_CP_COLS):
            with patch("backend.database._is_sqlite", False):
                d.create_company_policy(
                    policy_id="p1",
                    company_id="c1",
                    title="T",
                    version="1",
                    effective_date=None,
                    file_url="",
                    file_type="json",
                    created_by=None,
                    template_source="default_platform_template",
                    template_name="starter_standard",
                    is_default_template=True,
                )

        self.assertTrue(captured, "expected INSERT execute")
        self.assertIn("CASE WHEN :cp_isdef_i", captured[0]["sql"])
        self.assertEqual(captured[0]["params"].get("cp_isdef_i"), 1)
        self.assertNotIn("isdef", captured[0]["params"])

        captured.clear()
        with patch("backend.database._get_company_policies_columns", return_value=_FULL_CP_COLS):
            with patch("backend.database._is_sqlite", False):
                d.create_company_policy(
                    policy_id="p2",
                    company_id="c1",
                    title="T2",
                    version="1",
                    effective_date=None,
                    file_url="",
                    file_type="json",
                    created_by=None,
                    is_default_template=False,
                )
        self.assertEqual(captured[0]["params"].get("cp_isdef_i"), 0)

    def test_create_company_policy_binds_integer_for_sqlite(self) -> None:
        captured: list[dict] = []

        def capture_execute(stmt, params=None):
            captured.append({"sql": str(stmt), "params": dict(params or {})})
            return MagicMock()

        mock_conn = MagicMock()
        mock_conn.execute.side_effect = capture_execute
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_conn)
        ctx.__exit__ = MagicMock(return_value=False)

        d = Database.__new__(Database)
        d.engine = MagicMock()
        d.engine.begin.return_value = ctx

        with patch("backend.database._get_company_policies_columns", return_value=_FULL_CP_COLS):
            with patch("backend.database._is_sqlite", True):
                d.create_company_policy(
                    policy_id="p3",
                    company_id="c1",
                    title="T",
                    version="1",
                    effective_date=None,
                    file_url="",
                    file_type="json",
                    created_by=None,
                    is_default_template=True,
                )
        self.assertEqual(captured[0]["params"].get("isdef"), 1)
        self.assertNotIn("cp_isdef_i", captured[0]["params"])


if __name__ == "__main__":
    unittest.main()
