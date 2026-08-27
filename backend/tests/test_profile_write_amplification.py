"""ensure_profile_record must not write on every authenticated request.

`app/auth_deps.py:get_current_user` calls ensure_profile_record for EVERY authenticated
request, and it used to UPDATE profiles unconditionally. Measured against prod over 79
days: 154,493 + 125,401 UPDATEs and 160,481 SELECTs on `profiles`, nearly all of them
rewriting values that were already correct — on the critical path, on a single-worker
instance, holding a row lock and generating WAL each time.

The symptom a user sees is in the qa.replay.io report: HR endpoints returning an EMPTY
array with `server-timing: app;dur=3132ms`.

These tests pin the two halves of the fix: the comparison semantics (which are subtle,
and where a wrong call reintroduces the storm) and the fact that a no-op call issues no
UPDATE at all.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import sqlite3
import uuid as _uuid_mod

import pytest
from sqlalchemy import create_engine, event, text

# The writer binds profiles.id as a uuid.UUID (correct for Postgres, where the column
# IS uuid). This sqlite3 build refuses to bind that type, so teach it — the alternative
# would be testing the legacy non-uuid id path, which is not the one every authenticated
# request takes.
sqlite3.register_adapter(_uuid_mod.UUID, str)

from backend.db.users import _profile_matches


ROW = ("hr", "a@b.com", "Ada", "co-1")


class TestProfileMatches:
    def test_identical_row_matches(self):
        assert _profile_matches(ROW, "hr", "a@b.com", "Ada", "co-1") is True

    @pytest.mark.parametrize(
        "role,email,name,company",
        [
            ("admin", "a@b.com", "Ada", "co-1"),   # role changed
            ("hr", "c@d.com", "Ada", "co-1"),      # email changed
            ("hr", "a@b.com", "Grace", "co-1"),    # name changed
            ("hr", "a@b.com", "Ada", "co-2"),      # company changed
        ],
    )
    def test_any_real_difference_forces_a_write(self, role, email, name, company):
        assert _profile_matches(ROW, role, email, name, company) is False

    def test_none_company_means_caller_is_not_managing_it(self):
        """The writer has a separate no-company_id branch, so None is not a difference."""
        assert _profile_matches(ROW, "hr", "a@b.com", "Ada", None) is True

    def test_null_and_empty_name_are_the_same(self):
        """The writer coerces None -> ''. If these compared unequal we would write ''
        over NULL on every request for every user without a name — the exact storm."""
        assert _profile_matches(("hr", "a@b.com", None, "co-1"), "hr", "a@b.com", "", "co-1") is True

    def test_case_differing_email_is_a_difference(self):
        """Deliberately exact: the row normalises once, then matches forever. A
        case-insensitive compare would leave it un-normalised permanently."""
        assert _profile_matches(("hr", "A@B.com", "Ada", "co-1"), "hr", "a@b.com", "Ada", "co-1") is False

    def test_company_compared_as_text(self):
        """profiles.company_id is uuid; callers pass str. A type-strict compare would
        never match and would write on every request."""
        import uuid as _uuid
        cid = _uuid.uuid4()
        assert _profile_matches(("hr", "a@b.com", "Ada", cid), "hr", "a@b.com", "Ada", str(cid)) is True


class TestNoWriteOnUnchangedProfile:
    """End-to-end over a real engine: count the UPDATEs actually issued."""

    def _engine_with_counter(self):
        engine = create_engine("sqlite://")
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE profiles (id TEXT PRIMARY KEY, role TEXT, email TEXT, "
                "full_name TEXT, company_id TEXT, created_at TEXT)"
            ))
        seen: list[str] = []

        @event.listens_for(engine, "before_cursor_execute")
        def _record(conn, cursor, statement, parameters, context, executemany):
            seen.append(statement.strip().split()[0].upper())

        return engine, seen

    def test_repeat_calls_issue_no_update(self):
        from backend.db.users import UsersMixin

        engine, seen = self._engine_with_counter()

        class _DB(UsersMixin):
            def __init__(self, eng):
                self.engine = eng

        db = _DB(engine)
        uid = "3f6d1f6e-0a3a-4a1e-9f1a-9c2b7c1d5e11"

        db.ensure_profile_record(user_id=uid, email="a@b.com", role="hr",
                                 full_name="Ada", company_id="co-1")
        seen.clear()

        # Same values again — this is what every subsequent request looks like.
        for _ in range(5):
            db.ensure_profile_record(user_id=uid, email="a@b.com", role="hr",
                                     full_name="Ada", company_id="co-1")

        assert "UPDATE" not in seen, f"unchanged profile still wrote: {seen}"

    def test_a_real_change_still_writes(self):
        """The optimisation must not stop legitimate updates — a stale role would
        otherwise never be corrected."""
        from backend.db.users import UsersMixin

        engine, seen = self._engine_with_counter()

        class _DB(UsersMixin):
            def __init__(self, eng):
                self.engine = eng

        db = _DB(engine)
        uid = "3f6d1f6e-0a3a-4a1e-9f1a-9c2b7c1d5e11"
        db.ensure_profile_record(user_id=uid, email="a@b.com", role="employee",
                                 full_name="Ada", company_id="co-1")
        seen.clear()
        db.ensure_profile_record(user_id=uid, email="a@b.com", role="hr",
                                 full_name="Ada", company_id="co-1")

        assert "UPDATE" in seen, "a changed role must still be persisted"
        with engine.begin() as conn:
            role = conn.execute(text("SELECT role FROM profiles WHERE id = :i"), {"i": uid}).scalar()
        assert role == "hr"
