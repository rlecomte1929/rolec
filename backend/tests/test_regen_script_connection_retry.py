"""The bulk regenerator retries a dropped connection — and ONLY a dropped connection.

MEASURED 2026-08-22 on the FR_NO population (296 cases): the FIRST case of every run died
with `SSL connection has been closed unexpectedly`, and the failure was POSITION-dependent,
not case-dependent — a case that succeeded inside a batch failed when run first, and the
one that failed in the batch succeeded when it was not first. A bulk run therefore lost a
case silently, and `--case <id>` — the obvious way to check one case before committing to a
bulk write — failed 100% of the time.

`pool_pre_ping` is already enabled in db_config and does not catch it: the connection is
alive when pinged and dies on the first real statement. A warm-up `SELECT 1` does not catch
it either — that was tried against production, the SELECT succeeded, and the following case
still failed, so the warm-up was removed rather than left in as a no-op.

WHY THE PREDICATE IS NARROW. A retry is only safe because `regenerate_case_milestones` is
idempotent. Retrying a genuine data fault would run faulty work twice, and on `--apply`
that is a second write to a table with no history. `test_a_real_data_error_is_not_retried`
is the test that stops the marker list being widened into a bare `except Exception`.
"""
from __future__ import annotations

import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.scripts.regenerate_corridor_roadmaps as regen  # noqa: E402


class _Dropped(Exception):
    """Stands in for sqlalchemy.exc.OperationalError wrapping psycopg2's socket error."""


@pytest.mark.parametrize(
    "message",
    [
        "(psycopg2.OperationalError) SSL connection has been closed unexpectedly",
        "server closed the connection unexpectedly",
        "connection already closed",
        "terminating connection due to administrator command",
        "could not receive data from server: Connection timed out",
        "EOF detected",
    ],
)
def test_dropped_connections_are_recognised(message):
    assert regen._is_transient_db_error(_Dropped(message)) is True


def test_the_marker_is_found_through_the_cause_chain():
    """SQLAlchemy wraps the driver error, so the text lives on __cause__."""
    inner = _Dropped("SSL connection has been closed unexpectedly")
    outer = RuntimeError("(psycopg2.OperationalError) see cause")
    outer.__cause__ = inner
    assert regen._is_transient_db_error(outer) is True


@pytest.mark.parametrize(
    "message",
    [
        "null value in column \"case_id\" violates not-null constraint",
        "invalid input syntax for type uuid: \"undefined\"",
        "relation \"case_milestones\" does not exist",
        "division by zero",
    ],
)
def test_a_real_data_error_is_not_retried(message):
    """The load-bearing negative.

    Retrying a data fault runs it twice — on --apply, a second write to a table with no
    history. If this ever starts passing for these inputs, the predicate has been widened
    into a bare `except Exception` and the retry is no longer safe.
    """
    assert regen._is_transient_db_error(_Dropped(message)) is False


def test_a_transient_failure_is_retried_once_and_then_succeeds():
    calls = []

    def _fake(db, case_id, draft=None, apply=False):
        calls.append(case_id)
        if len(calls) == 1:
            raise _Dropped("(psycopg2.OperationalError) SSL connection has been closed unexpectedly")
        return "regenerated"

    original = regen.regenerate_case_milestones
    regen.regenerate_case_milestones = _fake
    try:
        assert regen._regenerate_with_retry(None, "case-1", {}, apply=False) == "regenerated"
    finally:
        regen.regenerate_case_milestones = original
    assert len(calls) == 2, "should have retried exactly once"


def test_a_non_transient_failure_is_raised_without_a_second_attempt():
    calls = []

    def _fake(db, case_id, draft=None, apply=False):
        calls.append(case_id)
        raise _Dropped("invalid input syntax for type uuid")

    original = regen.regenerate_case_milestones
    regen.regenerate_case_milestones = _fake
    try:
        with pytest.raises(_Dropped):
            regen._regenerate_with_retry(None, "case-1", {}, apply=True)
    finally:
        regen.regenerate_case_milestones = original
    assert len(calls) == 1, "a data fault must not be run twice, least of all on --apply"


def test_the_retry_gives_up_after_one_attempt():
    """Bounded: a persistently dead connection fails the case rather than looping."""
    calls = []

    def _fake(db, case_id, draft=None, apply=False):
        calls.append(case_id)
        raise _Dropped("SSL connection has been closed unexpectedly")

    original = regen.regenerate_case_milestones
    regen.regenerate_case_milestones = _fake
    try:
        with pytest.raises(_Dropped):
            regen._regenerate_with_retry(None, "case-1", {}, apply=False)
    finally:
        regen.regenerate_case_milestones = original
    assert len(calls) == 2
