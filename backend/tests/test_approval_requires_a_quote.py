"""[AIQ-2124] An approved requirement fact must carry the quote that vouches for it.

A fact with an empty `evidence_quote` can NEVER be evidenced — `check_evidence('' , page)`
has nothing to match, so the fact sits at `evidence_verified = NULL` no matter how many times
the backfill runs. Meanwhile `list_approved_requirement_facts` serves it (NULL is admitted
deliberately — see AIQ-1887) and the dossier renders a clickable source link beside it. The
link implies somebody opened that page and found the claim. Nobody did, and nothing recorded
that.

Measured on production 2026-08-23: **15 approved facts are served with no quote at all** —
SG 6, DK 4, IE 4, PT 1. Four of them are on Andrea's corridor.

The gate is at approval, not at write: a PENDING fact with no quote yet is a normal
mid-authoring state, and the reviewer is exactly the person who should be made to supply the
quote before promoting it. Rejection is never blocked — a bad fact must always be able to
leave.
"""
from __future__ import annotations

import os
import sys

import pytest
from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.db.policies import PoliciesMixin, UnquotedApprovalError  # noqa: E402


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
            # [AIQ-2046] The sibling gate (_assert_no_fact_needs_lawyer_review) reads this
            # column in the same approval path, so the fixture needs it or every test here
            # fails on a missing column rather than on the behaviour it is asserting.
            " applies_to TEXT)"
        ))
        conn.execute(text(
            "CREATE TABLE requirement_reviews ("
            " id TEXT PRIMARY KEY, entity_id TEXT, fact_id TEXT, reviewer_user_id TEXT,"
            " action TEXT, notes TEXT, created_at TEXT)"
        ))
        for fid, quote in (
            ("quoted", "You must hold a qualifying job offer of at least two years."),
            ("quoteless", ""),
            ("null_quote", None),
            ("whitespace_only", "   \n\t "),
        ):
            conn.execute(
                text("INSERT INTO requirement_facts (id, entity_id, status, evidence_quote, fact_key)"
                     " VALUES (:id,'e1','pending',:q,:id)"),
                {"id": fid, "q": quote},
            )
    return _Db(engine)


def _status(db, fid):
    with db.engine.connect() as conn:
        return conn.execute(
            text("SELECT status FROM requirement_facts WHERE id = :id"), {"id": fid}
        ).scalar()


class TestTheGateFires:
    """These fail against the pre-fix code — approval simply succeeded."""

    @pytest.mark.parametrize("fid", ["quoteless", "null_quote", "whitespace_only"])
    def test_a_quoteless_fact_cannot_be_approved(self, db, fid):
        with pytest.raises(UnquotedApprovalError):
            db.update_requirement_fact_status([fid], "approved", "reviewer-1")
        assert _status(db, fid) == "pending"

    def test_the_error_names_the_offending_facts(self, db):
        """A reviewer approving 40 rows needs to know WHICH one lacks a quote."""
        with pytest.raises(UnquotedApprovalError) as exc:
            db.update_requirement_fact_status(["quoted", "quoteless"], "approved", "r")
        assert "quoteless" in str(exc.value)

    def test_the_whole_batch_is_refused_not_half_written(self, db):
        """Refuse before writing anything: a partial approval leaves the reviewer unable to
        tell what landed."""
        with pytest.raises(UnquotedApprovalError):
            db.update_requirement_fact_status(["quoted", "quoteless"], "approved", "r")
        assert _status(db, "quoted") == "pending"

    def test_no_review_row_is_written_for_a_refused_batch(self, db):
        with pytest.raises(UnquotedApprovalError):
            db.update_requirement_fact_status(["quoted", "quoteless"], "approved", "r")
        with db.engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM requirement_reviews")).scalar() == 0


class TestTheGateDiscriminates:
    """A guard that refuses everything, or nothing, is decoration."""

    def test_a_quoted_fact_still_approves(self, db):
        db.update_requirement_fact_status(["quoted"], "approved", "reviewer-1")
        assert _status(db, "quoted") == "approved"

    def test_rejection_is_never_blocked_by_a_missing_quote(self, db):
        """A bad fact must always be able to LEAVE the queue. Gating rejection on evidence
        would trap exactly the facts most in need of removal."""
        db.update_requirement_fact_status(["quoteless"], "rejected", "reviewer-1")
        assert _status(db, "quoteless") == "rejected"

    def test_demotion_to_pending_is_never_blocked(self, db):
        db.update_requirement_fact_status(["quoteless"], "pending", "reviewer-1")
        assert _status(db, "quoteless") == "pending"

    def test_an_empty_id_list_is_a_no_op(self, db):
        db.update_requirement_fact_status([], "approved", "reviewer-1")


class TestTheProductionShape:
    """The 15 live rows this was written for: approved AND quoteless AND served."""

    def test_an_already_approved_quoteless_fact_is_not_retroactively_broken(self, db):
        """The guard is a gate on NEW approvals. It must not make the existing 15 unfixable —
        a reviewer has to be able to move them to pending, which the rejection test covers,
        and re-approve them once a quote is supplied."""
        with db.engine.begin() as conn:
            conn.execute(text("UPDATE requirement_facts SET status='approved' WHERE id='quoteless'"))
        # Supplying the quote is what unblocks re-approval.
        with db.engine.begin() as conn:
            conn.execute(text(
                "UPDATE requirement_facts SET evidence_quote='A real sentence from the page.'"
                " WHERE id='quoteless'"))
        db.update_requirement_fact_status(["quoteless"], "approved", "reviewer-1")
        assert _status(db, "quoteless") == "approved"
