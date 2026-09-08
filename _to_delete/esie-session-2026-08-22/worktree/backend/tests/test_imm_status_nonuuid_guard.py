"""
Regression guard — immigration status read path must not 500 on a non-UUID id.

A legacy/ReloPass-session account whose ``current_user["id"]`` is a non-UUID text
id (e.g. ``seed-emp-testingapril``) can hit a uuid-typed column in the consent /
session query path, making Postgres raise ``invalid input syntax for type uuid``
(surfaced by SQLAlchemy as ``DataError``). The employee immigration page then
shows "Internal server error".

``_check_consent`` and ``_load_session`` now catch that and degrade gracefully
(no consent / no session) instead of letting it bubble to a 500.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import DataError

from backend.app.services import immigration_service as svc


def _patch_db_raising(exc: Exception):
    """Patch svc.db so engine.begin() yields a conn whose execute() raises ``exc``."""
    conn = MagicMock()
    conn.execute.side_effect = exc
    db = MagicMock()
    db.engine.begin.return_value.__enter__.return_value = conn
    return patch.object(svc, "db", db)


class TestImmStatusNonUuidGuard(unittest.TestCase):
    def _uuid_data_error(self) -> DataError:
        return DataError(
            "SELECT ...",
            {},
            Exception('invalid input syntax for type uuid: "seed-emp-testingapril"'),
        )

    def test_check_consent_returns_false_on_daterror(self):
        with _patch_db_raising(self._uuid_data_error()):
            self.assertIs(
                svc._check_consent("case-1", "seed-emp-testingapril"), False
            )

    def test_load_session_returns_none_on_daterror(self):
        with _patch_db_raising(self._uuid_data_error()):
            self.assertIsNone(
                svc._load_session("case-1", "seed-emp-testingapril")
            )

    def test_non_dataerror_still_propagates(self):
        # Only the malformed-id case is swallowed; real DB faults must not be hidden.
        with _patch_db_raising(RuntimeError("connection reset")):
            with self.assertRaises(RuntimeError):
                svc._check_consent("case-1", "emp-1")


if __name__ == "__main__":
    unittest.main()
