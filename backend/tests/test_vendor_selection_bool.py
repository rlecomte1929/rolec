"""Regression guard: the `selected` column is a Postgres BOOLEAN, so writers must bind
a Python bool — an int (1/0) raises psycopg2 DatatypeMismatch (42804) → a 500 on the HR
vendor-curation page (confirmed in prod: recurring, 51× / 14 days), and silently breaks
employee service-saving via upsert_case_services.

SQLite coerces int→bool, so a normal unit test can't catch a regression here (it only
fails on real Postgres). This source guard asserts the two writers bind a bool, not 1/0.
Verified against the live PG schema: `INSERT INTO (selected boolean) VALUES (1)` errors;
`VALUES (true)` succeeds.
"""
from __future__ import annotations

import os

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def _read(rel: str) -> str:
    with open(os.path.join(_ROOT, "backend", rel), "r", encoding="utf-8") as fh:
        return fh.read()


def test_upsert_master_selection_binds_bool_not_int():
    src = _read("app/services/vendor_curation.py")
    assert "selected_bool = bool(selected)" in src, "must bind a Python bool for the boolean column"
    assert "1 if selected else 0" not in src, "int bind (1/0) into a boolean column 500s on Postgres"


def test_upsert_case_services_binds_bool_not_int():
    src = _read("db/cases.py")
    assert "bool(item.get(\"selected\", True))" in src, "must bind a Python bool for the boolean column"
    assert "1 if item.get(\"selected\", True) else 0" not in src, "int bind (1/0) fails on Postgres"
