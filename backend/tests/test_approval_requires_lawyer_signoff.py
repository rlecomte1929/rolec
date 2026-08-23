"""[AIQ-2046] A claim flagged `needs_lawyer_review` must not be published on nobody's say-so.

`needs_lawyer_review: true` is the research pipeline saying a lawyer has to read this claim
before anyone relies on it. Nothing enforced it anywhere.

Measured on production 2026-08-23:

    requirement_items   approved 101, of which  4 flagged   <- ALREADY PUBLISHED
                        pending  100, of which  8 flagged   <- next in line
    requirement_facts   0 flagged in any status             <- preventive here

The 4 published ones are all IRELAND / RESIDENCE on the ES->IE corridor — the first real
customer's. They were approved 2026-08-21 12:02:59 UTC by one scripted call covering 9 rows at
an identical microsecond, so no human read them one by one, and the 4 that differed from the
other 5 produced no warning, no log, nothing. The reviewer could not have honoured the flag:
the review queue never selected `applies_to`, so it showed them strictly LESS provenance than
the employee who later read the row.

TWO STORAGE SHAPES, which is why the gate is a shared module and not an inline predicate:
  * requirement_facts.applies_to    — jsonb, flag at the top level
  * requirement_items.citations_json — TEXT array of citation objects, flag nested INSIDE one,
    because that table has no column for it.

THE GATE IS NOT A DEAD END. It is discharged by `attestation_status='attested'` — the existing
counsel-attestation axis — so a flagged claim is routed to the lane built for it rather than
being frozen forever.

The gate is on APPROVAL only. Rejecting or withdrawing a flagged row stays possible: gating a
claim's EXIT on legal sign-off would trap precisely the claims most in need of removal.
"""
from __future__ import annotations

import json
import os
import sys

import pytest
from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import lawyer_review_gate  # noqa: E402
from backend.db.policies import (  # noqa: E402
    PoliciesMixin,
    UnattestedLawyerReviewError,
)

FLAGGED = json.dumps({"pillar": "RESIDENCE", "needs_lawyer_review": True})
CLEAN = json.dumps({"pillar": "RESIDENCE", "needs_lawyer_review": False})
# The requirement_items shape: nested one level down inside a citation object.
ITEM_SHAPED = json.dumps([
    {"url": "https://www.irishimmigration.ie/x", "name": "ISD", "needs_lawyer_review": True},
])


# ── the shared detector ──────────────────────────────────────────────────────


class TestTheDetectorSeesBothStorageShapes:
    def test_flat_applies_to_shape(self):
        assert lawyer_review_gate.carries_lawyer_review_flag(FLAGGED)

    def test_nested_citation_object_shape(self):
        """The shape that actually holds the 4 published rows. A gate pinned to the flat
        shape would report them clean."""
        assert lawyer_review_gate.carries_lawyer_review_flag(ITEM_SHAPED)

    def test_already_parsed_structures_work_too(self):
        assert lawyer_review_gate.carries_lawyer_review_flag(json.loads(ITEM_SHAPED))

    @pytest.mark.parametrize("blob", [
        None, "", "   ", "not json at all", "{", CLEAN, "[]", "{}",
        json.dumps({"needs_lawyer_review": None}),
        json.dumps({"needs_lawyer_review": "false"}),
    ])
    def test_absent_false_or_unparseable_is_not_flagged(self, blob):
        """This gate BLOCKS publication, so a parse failure must not silently freeze the
        whole queue. Only an explicit truth counts."""
        assert not lawyer_review_gate.carries_lawyer_review_flag(blob)

    def test_attestation_discharges_the_flag(self):
        assert lawyer_review_gate.blocks_approval(
            attestation_status=None, blobs=(FLAGGED,))
        assert lawyer_review_gate.blocks_approval(
            attestation_status="requested", blobs=(FLAGGED,))
        assert not lawyer_review_gate.blocks_approval(
            attestation_status="attested", blobs=(FLAGGED,))
        assert not lawyer_review_gate.blocks_approval(
            attestation_status="ATTESTED ", blobs=(FLAGGED,))

    def test_an_unflagged_row_is_never_blocked(self):
        assert not lawyer_review_gate.blocks_approval(
            attestation_status=None, blobs=(CLEAN, None))


# ── the batch gate on requirement_facts ──────────────────────────────────────


class _Db(PoliciesMixin):
    def __init__(self, engine):
        self.engine = engine

    @staticmethod
    def _rows_to_list(rows):
        return [dict(r._mapping) for r in rows]

    @staticmethod
    def _json_load(value):
        return None


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE requirement_facts ("
            " id TEXT PRIMARY KEY, entity_id TEXT, status TEXT, evidence_quote TEXT,"
            " evidence_verified BOOLEAN, reviewed_by TEXT, reviewed_at TEXT, fact_key TEXT,"
            " applies_to TEXT)"
        ))
        conn.execute(text(
            "CREATE TABLE requirement_reviews ("
            " id TEXT PRIMARY KEY, entity_id TEXT, fact_id TEXT, reviewer_user_id TEXT,"
            " action TEXT, notes TEXT, created_at TEXT)"
        ))
        # Every row carries a real quote, so the SIBLING gate can never be what fires.
        for fid, applies in (("clean", CLEAN), ("flagged", FLAGGED), ("clean2", CLEAN)):
            conn.execute(
                text("INSERT INTO requirement_facts"
                     " (id, entity_id, status, evidence_quote, applies_to)"
                     " VALUES (:i, 'e1', 'pending', 'a real verbatim quote', :a)"),
                {"i": fid, "a": applies},
            )
    return _Db(engine)


def _status(db, fid):
    with db.engine.connect() as conn:
        return conn.execute(
            text("SELECT status FROM requirement_facts WHERE id = :i"), {"i": fid}
        ).scalar_one()


class TestTheGate:
    def test_approving_a_flagged_fact_is_refused(self, db):
        with pytest.raises(UnattestedLawyerReviewError):
            db.update_requirement_fact_status(["flagged"], "approved", "admin")
        assert _status(db, "flagged") == "pending"

    def test_the_error_names_the_offending_id(self, db):
        """A reviewer told only that 'something broke' cannot fix the batch."""
        with pytest.raises(UnattestedLawyerReviewError) as exc:
            db.update_requirement_fact_status(["clean", "flagged"], "approved", "admin")
        assert "flagged" in str(exc.value)

    def test_the_whole_batch_is_refused_not_half_applied(self, db):
        """The precondition runs OUTSIDE the transaction. A half-applied approval leaves
        the reviewer unable to tell what landed."""
        with pytest.raises(UnattestedLawyerReviewError):
            db.update_requirement_fact_status(
                ["clean", "flagged", "clean2"], "approved", "admin")
        for fid in ("clean", "flagged", "clean2"):
            assert _status(db, fid) == "pending", f"{fid} must not have been approved"
        with db.engine.connect() as conn:
            assert conn.execute(
                text("SELECT count(*) FROM requirement_reviews")).scalar_one() == 0

    def test_an_unflagged_batch_still_approves(self, db):
        """Guard against over-correcting into a queue nothing can leave."""
        db.update_requirement_fact_status(["clean", "clean2"], "approved", "admin")
        assert _status(db, "clean") == "approved"
        assert _status(db, "clean2") == "approved"

    def test_a_flagged_fact_can_still_be_REJECTED(self, db):
        """Gating the exit would trap the claims most in need of removal."""
        db.update_requirement_fact_status(["flagged"], "rejected", "admin", "no basis")
        assert _status(db, "flagged") == "rejected"
