"""[WS3] list_corridors derives the vendor-filter dropdown from live data.

The old endpoint returned a hardcoded KNOWN_CORRIDORS that went stale the moment
new corridors shipped. It now derives the list from vendors.corridor_codes so it
stays in sync, with the static list as a fallback so the dropdown is never empty.

The derivation query is Postgres-specific (unnest + regex) and can't run on
sqlite — it's verified live against prod. These tests cover the function's
BRANCHING with a fake engine: non-empty derived list is returned as-is; an empty
result or a DB error both fall back to KNOWN_CORRIDORS.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import hr_vendors  # noqa: E402


class _FakeResult:
    def __init__(self, vals):
        self._vals = vals

    def scalars(self):
        return self

    def all(self):
        return self._vals


class _FakeConn:
    def __init__(self, vals, fail):
        self._vals = vals
        self._fail = fail

    def __enter__(self):
        if self._fail:
            raise RuntimeError("db down")
        return self

    def __exit__(self, *a):
        return False

    def execute(self, *a, **k):
        return _FakeResult(self._vals)


class _FakeEngine:
    def __init__(self, vals=None, fail=False):
        self._vals = vals or []
        self._fail = fail

    def connect(self):
        return _FakeConn(self._vals, self._fail)


class ListCorridorsTest(unittest.TestCase):
    def _call(self, engine):
        with mock.patch.object(hr_vendors.db, "engine", engine):
            return hr_vendors.list_corridors(_user={})["corridors"]

    def test_returns_live_derived_corridors(self):
        result = self._call(_FakeEngine(["DE-FR", "FR-DE", "FR-NL"]))
        self.assertEqual(result, ["DE-FR", "FR-DE", "FR-NL"])
        # The derived list must not be the static fallback.
        self.assertNotEqual(result, hr_vendors.KNOWN_CORRIDORS)

    def test_empty_result_falls_back_to_static_list(self):
        self.assertEqual(self._call(_FakeEngine([])), hr_vendors.KNOWN_CORRIDORS)

    def test_db_error_falls_back_to_static_list(self):
        # Dropdown must never be empty, even if the query blows up.
        self.assertEqual(self._call(_FakeEngine(fail=True)), hr_vendors.KNOWN_CORRIDORS)


if __name__ == "__main__":
    unittest.main()
