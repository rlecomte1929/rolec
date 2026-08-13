"""`GET /api/requirements/sufficiency` must not serve facts we have already DISPROVED.

The chain is real and live:
    requirement_facts (status='approved')
      -> PoliciesMixin.list_approved_requirement_facts   (backend/db/policies.py)
      -> compute_requirements_sufficiency                (requirements_sufficiency.py)
      -> GET /api/requirements/sufficiency               (backend/main.py)

Measured on production 2026-08-13, before this fix: of 375 approved facts, only 54 had
`evidence_verified = TRUE`, and **74 had `evidence_verified = FALSE`** — the evidence ledger
(migration 20261033000000, AIQ-1821) had already established that the stored `evidence_quote`
does not appear in the archived source, and the endpoint served them regardless. 705 facts sit
on 222 knowledge_docs whose entire text_content is "Otto bridge capture, unverified — see
source_url"; all 705 store a quote that is not a substring of it, and 246 are approved.

This test runs the REAL SQL against a real SQLite engine rather than asserting on the query
string, so it pins behaviour and not spelling. It is written to fail against the pre-fix
predicate: drop the COALESCE condition and `disproved` comes back, which is the whole point —
this class of bug fails safe (you get MORE rows, never an error), so a test that passes either
way would be worthless.
"""
from __future__ import annotations

import os
import sys
import unittest

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.db.policies import PoliciesMixin  # noqa: E402


class _Db(PoliciesMixin):
    """Minimal host for the mixin: it only needs `.engine` and the two row helpers."""

    def __init__(self, engine):
        self.engine = engine

    @staticmethod
    def _rows_to_list(rows):
        return [dict(r._mapping) for r in rows]

    @staticmethod
    def _json_load(value):
        return None


def _seed_engine():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE requirement_entities ("
            " id TEXT PRIMARY KEY, destination_country TEXT)"
        ))
        conn.execute(text(
            "CREATE TABLE requirement_facts ("
            " id TEXT PRIMARY KEY, entity_id TEXT, status TEXT,"
            " evidence_verified BOOLEAN, applies_to TEXT, required_fields TEXT,"
            " fact_key TEXT)"
        ))
        conn.execute(text(
            "INSERT INTO requirement_entities (id, destination_country) VALUES ('e1','NO')"
        ))
        # One of each evidence state, all approved, all the same destination.
        for fid, verified in (
            ("grounded", 1),      # evidence_verified = TRUE  -> must be served
            ("disproved", 0),     # evidence_verified = FALSE -> must NOT be served
            ("unchecked", None),  # evidence_verified = NULL  -> must still be served
        ):
            conn.execute(
                text(
                    "INSERT INTO requirement_facts"
                    " (id, entity_id, status, evidence_verified, fact_key)"
                    " VALUES (:id,'e1','approved',:v,:id)"
                ),
                {"id": fid, "v": verified},
            )
        # A rejected fact must stay excluded on status alone — guards against a fix that
        # accidentally widens the predicate while narrowing it elsewhere.
        conn.execute(text(
            "INSERT INTO requirement_facts (id, entity_id, status, evidence_verified, fact_key)"
            " VALUES ('rejected_row','e1','rejected',1,'rejected_row')"
        ))
    return engine


class ApprovedFactsExcludeDisprovedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.db = _Db(_seed_engine())

    def _ids(self):
        return {f["id"] for f in self.db.list_approved_requirement_facts("NO")}

    def test_disproved_evidence_is_not_served(self):
        """The 74-row production case: evidence_verified=FALSE must never reach a user."""
        self.assertNotIn("disproved", self._ids())

    def test_verified_and_unchecked_are_still_served(self):
        """Only FALSE is excluded. NULL means 'not checked yet', not 'wrong' — excluding it
        would have emptied the surface for 247 of the 375 approved production facts."""
        self.assertEqual({"grounded", "unchecked"}, self._ids())

    def test_status_filter_still_applies(self):
        self.assertNotIn("rejected_row", self._ids())

    def test_other_destinations_are_unaffected(self):
        self.assertEqual(set(), {f["id"] for f in self.db.list_approved_requirement_facts("SE")})


if __name__ == "__main__":
    unittest.main()
