"""Who funds a case — the constraints, on a real Postgres.

These are CHECK constraints and a DEFAULT, which SQLite renders differently or not at all, so
they belong in the Postgres parity lane rather than the main suite. The lane replays the real
migration file, so this tests the DDL that will actually run in production.

WHAT IS BEING PROTECTED

`funding_source` is about to become an access-control input: a policy will read it to decide
whether a case is paywalled, and where. Two failure modes matter, and both are silent.

The DEFAULT. Measured on prod 2026-08-23, 2,153 of 2,165 cases carry a company_id — every
live case is employer-originated. If the default were 'self', the migration would silently
reclassify the entire book as individually funded and the first policy rollout would paywall
all of them. `test_existing_rows_default_to_employer` is the guard on that.

The PAIRING. A sponsored case must name its sponsor, because the UI has to say "your move is
covered by X" out loud, and a sponsored case with no sponsor makes that sentence unsayable.
Equally a non-sponsored case must not carry a stray sponsor_id, or "who is paying?" has two
answers.

AND THE ONE THAT IS NOT A TEST: there is deliberately no column recording what kind of person
the mover is — no is_refugee, no status category. Sponsorship is a property of the FUNDING,
not of the human being funded. `test_no_column_records_a_protected_characteristic` fails if
somebody adds one later, which is the only way to enforce a design decision in code.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager

import pytest
from sqlalchemy import text

from backend.app.db import engine


@contextmanager
def _tx():
    """One autocommitting transaction, matching this lane's house style (engine.begin())."""
    with engine.begin() as conn:
        yield conn


def _scalar(sql: str, **params):
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar()


def _expect_rejected(sql: str, **params) -> None:
    """The constraint must refuse this write. A CHECK that accepts everything is not a
    constraint, so every rejection here is paired with the acceptance it must not block."""
    with pytest.raises(Exception):
        with engine.begin() as conn:
            conn.execute(text(sql), params)


@pytest.fixture
def case_id():
    """One relocation_cases row, cleaned up after."""
    cid = str(uuid.uuid4())
    with _tx() as conn:
        conn.execute(text("INSERT INTO relocation_cases (id) VALUES (:id)"), {"id": cid})
    yield cid
    with _tx() as conn:
        conn.execute(text("DELETE FROM case_entitlement_grants WHERE case_id = :id"), {"id": cid})
        conn.execute(text("DELETE FROM relocation_cases WHERE id = :id"), {"id": cid})


class TestTheDefault:
    def test_a_new_row_defaults_to_employer(self, case_id):
        assert _scalar(
            "SELECT funding_source FROM relocation_cases WHERE id = :id", id=case_id
        ) == "employer"

    def test_existing_rows_default_to_employer(self, case_id):
        """The load-bearing one. A row created without naming a funder is employer-funded,
        never self-funded — self-funded is the value that paywalls somebody."""
        assert _scalar(
            "SELECT count(*) FROM relocation_cases WHERE funding_source <> 'employer'"
        ) == 0, "a row was classified as something other than employer by default"

    def test_a_fresh_row_carries_no_sponsor(self, case_id):
        assert _scalar(
            "SELECT sponsor_id FROM relocation_cases WHERE id = :id", id=case_id
        ) is None


class TestTheConstraintsDiscriminate:
    def test_an_invented_funding_source_is_rejected(self, case_id):
        _expect_rejected(
            "UPDATE relocation_cases SET funding_source='charity' WHERE id=:id", id=case_id
        )

    @pytest.mark.parametrize("value", ["employer", "self", "internal"])
    def test_the_three_unsponsored_values_are_accepted(self, case_id, value):
        with _tx() as conn:
            conn.execute(
                text("UPDATE relocation_cases SET funding_source=:v WHERE id=:id"),
                {"v": value, "id": case_id},
            )
        assert _scalar(
            "SELECT funding_source FROM relocation_cases WHERE id=:id", id=case_id
        ) == value

    def test_sponsor_without_a_sponsor_id_is_rejected(self, case_id):
        """'A programme is paying' is unusable if we cannot say which programme."""
        _expect_rejected(
            "UPDATE relocation_cases SET funding_source='sponsor' WHERE id=:id", id=case_id
        )

    def test_a_sponsor_id_without_sponsor_funding_is_rejected(self, case_id):
        """Otherwise 'who is paying?' has two answers at once."""
        _expect_rejected(
            "UPDATE relocation_cases SET sponsor_id='ngo-1' WHERE id=:id", id=case_id
        )

    def test_a_complete_sponsor_pair_is_accepted(self, case_id):
        with _tx() as conn:
            conn.execute(
                text("UPDATE relocation_cases SET funding_source='sponsor', sponsor_id='ngo-1'"
                     " WHERE id=:id"),
                {"id": case_id},
            )
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT funding_source, sponsor_id FROM relocation_cases WHERE id=:id"),
                {"id": case_id},
            ).first()
        assert (row[0], row[1]) == ("sponsor", "ngo-1")


class TestTheGrantLog:
    def test_a_grant_can_be_recorded(self, case_id):
        gid = str(uuid.uuid4())
        with _tx() as conn:
            conn.execute(
                text("INSERT INTO case_entitlement_grants"
                     " (id, case_id, granted_tier, reason, granted_by, policy_key)"
                     " VALUES (:id,:c,'roadmap','employer-funded per move','system','employer_v1')"),
                {"id": gid, "c": case_id},
            )
        assert _scalar(
            "SELECT reason FROM case_entitlement_grants WHERE id=:id", id=gid
        ) == "employer-funded per move"

    def test_reason_is_mandatory(self, case_id):
        """An unexplainable grant is what this table exists to prevent. On 2026-08-23 a flag
        flip denied 1,845 cases their roadmap with no record of who decided it, or why."""
        _expect_rejected(
            "INSERT INTO case_entitlement_grants (id, case_id, granted_tier)"
            " VALUES (:id,:c,'roadmap')",
            id=str(uuid.uuid4()), c=case_id,
        )

    def test_rls_is_enabled(self):
        """New public table => RLS, per the repo's hard gate. Supabase exposes public via
        PostgREST and the anon key ships in the frontend bundle."""
        assert _scalar(
            "SELECT relrowsecurity FROM pg_class WHERE relname='case_entitlement_grants'"
        ) is True


class TestTheDesignDecision:
    def test_no_column_records_a_protected_characteristic(self):
        """Sponsorship is a property of the FUNDING, never of the person being funded.

        A column naming the mover's status — refugee, asylum seeker, vulnerability — is a
        protected-characteristic inference under GDPR Art. 9, and as an access-control input
        it would be logged on every decision, exported under every DSAR and copied into
        analytics. `funding_source='sponsor'` carries everything the product needs and
        nothing it does not.

        This test is the enforcement of that decision. If it goes red, read this before
        deleting it.
        """
        banned = ("refugee", "asylum", "vulnerab", "protected_status", "humanitarian_status")
        with engine.connect() as conn:
            cols = [r[0] for r in conn.execute(text(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_schema='public' AND table_name='relocation_cases'"
            )).fetchall()]
        offenders = [c for c in cols if any(b in c.lower() for b in banned)]
        assert not offenders, (
            f"relocation_cases gained a column recording the mover's status: {offenders}. "
            "Model the funding arrangement (funding_source/sponsor_id), never the person."
        )
