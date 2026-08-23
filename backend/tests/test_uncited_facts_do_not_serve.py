"""A requirement served with a source link must have a quote behind it.

#2022 (AIQ-2124) closed the WRITE side: an approval now refuses a fact carrying no evidence
quote. It did not retract the facts already approved. Measured on production 2026-08-23, of
205 requirement_facts serving catalog-wide, **9 carry no quote at all** — 6 Singapore, 3
Ireland — each rendered beside a source_url that supports nothing.

That is the worst shape a served fact can take. An uncited claim at least looks uncited; a
claim with a citation link next to it reads as CHECKED. `check_evidence` already draws this
line in words — "a fact with no quote can never be machine-verified … That belongs in front
of a human" — so the reader here is honouring a rule the evidence layer already states.

What is deliberately NOT excluded: `evidence_verified IS NULL`. Never-checked is not the same
claim as wrong, and dropping 247 unchecked facts would empty the surface on no evidence.
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.db.policies import PoliciesMixin  # noqa: E402


class _Db(PoliciesMixin):
    """PoliciesMixin over a scratch SQLite database — the reader is plain SQL + Python."""

    def __init__(self, engine):
        self.engine = engine

    @staticmethod
    def _rows_to_list(rows):
        return [dict(r._mapping) for r in rows]

    @staticmethod
    def _json_load(value):
        import json
        if value in (None, ""):
            return None
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return None


def _make_db():
    engine = create_engine(
        "sqlite://", future=True,
        connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    with engine.begin() as c:
        c.execute(text("""
            CREATE TABLE requirement_entities (id TEXT PRIMARY KEY, destination_country TEXT)
        """))
        c.execute(text("""
            CREATE TABLE requirement_facts (
                id TEXT PRIMARY KEY, entity_id TEXT, fact_key TEXT, fact_text TEXT,
                applies_to TEXT, required_fields TEXT, source_url TEXT,
                evidence_quote TEXT, evidence_verified BOOLEAN, status TEXT
            )
        """))
        c.execute(text("INSERT INTO requirement_entities VALUES ('e1','IE')"))
    return _Db(engine), engine


def _add(engine, fid, *, quote, verified=None, status="approved"):
    with engine.begin() as c:
        c.execute(
            text("INSERT INTO requirement_facts VALUES "
                 "(:id,'e1',:k,'a fact','{}','[]','https://enterprise.gov.ie/x',"
                 " :q,:v,:s)"),
            {"id": fid, "k": fid, "q": quote, "v": verified, "s": status},
        )


class AFactWithNoQuoteDoesNotServe(unittest.TestCase):
    def setUp(self):
        self.db, self.engine = _make_db()

    def _served(self):
        return {f["id"] for f in self.db.list_approved_requirement_facts("IE")}

    def test_a_quoted_fact_still_serves(self):
        _add(self.engine, "good", quote="the verbatim sentence from the page")
        self.assertEqual({"good"}, self._served())

    def test_a_null_quote_is_withheld(self):
        """The production shape: approved, cited, and quoting nothing."""
        _add(self.engine, "nullq", quote=None)
        self.assertEqual(set(), self._served())

    def test_an_empty_quote_is_withheld(self):
        _add(self.engine, "empty", quote="")
        self.assertEqual(set(), self._served())

    def test_a_whitespace_only_quote_is_withheld(self):
        """Both Postgres and SQLite TRIM() strip spaces ONLY, so '\\n\\t' survives
        `TRIM(...) = ''` on both engines. Decided in Python for exactly that reason —
        the same argument #2022 makes on the write side."""
        for blank in ("   ", "\n\t", " "):
            with self.subTest(repr(blank)):
                db, engine = _make_db()
                _add(engine, "blank", quote=blank)
                self.assertEqual([], db.list_approved_requirement_facts("IE"))

    def test_never_checked_facts_STILL_serve(self):
        """The line that must not move. NULL means never checked, not wrong — dropping the
        247 unchecked facts would empty the surface on no evidence."""
        _add(self.engine, "unchecked", quote="a real quote", verified=None)
        self.assertEqual({"unchecked"}, self._served())

    def test_a_disproved_fact_is_still_withheld(self):
        _add(self.engine, "disproved", quote="a real quote", verified=False)
        self.assertEqual(set(), self._served())

    def test_an_unapproved_fact_is_still_withheld(self):
        _add(self.engine, "pending", quote="a real quote", status="pending")
        self.assertEqual(set(), self._served())

    def test_the_gate_removes_only_the_unquoted(self):
        """Nine facts catalog-wide, not the surface. A gate that empties the dossier would
        be worse than the problem it fixes."""
        _add(self.engine, "a", quote="quote one")
        _add(self.engine, "b", quote=None)
        _add(self.engine, "c", quote="quote two", verified=True)
        _add(self.engine, "d", quote="   ")
        self.assertEqual({"a", "c"}, self._served())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
