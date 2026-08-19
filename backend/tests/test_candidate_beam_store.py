"""Run persistence — the entry point the beam did not have.

Against a real SQLite database rather than a double, because the behaviours that matter
here are what the SQL does: replacing a retried pass instead of appending it, and refreshing
a rebuild's ranking without touching a human's verdict. A fake connection would confirm the
call was made and prove nothing about the row that resulted.

The table definitions mirror the production migration with `jsonb`→TEXT and `uuid`→TEXT,
which is the same split `_json_bind`/`_uuid_bind`/`_now` handle in the module. The CHECK
constraints are kept verbatim: they are the safety argument for the whole feature, and a
test schema that dropped them would let a bug through here and catch it only in production.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text

from backend.imports.candidate_beam import store

DDL = [
    """
    CREATE TABLE candidate_beam_runs (
        id TEXT PRIMARY KEY,
        set_uid TEXT,
        corridor TEXT NOT NULL,
        origin_country TEXT,
        dest_country TEXT,
        employee_type TEXT NOT NULL,
        context TEXT,
        passes_requested INTEGER NOT NULL,
        passes_completed INTEGER NOT NULL DEFAULT 0,
        llm_provider TEXT,
        llm_model TEXT,
        status TEXT NOT NULL DEFAULT 'generating',
        error TEXT,
        pass_outputs TEXT NOT NULL DEFAULT '[]',
        pass_meta TEXT NOT NULL DEFAULT '[]',
        candidate_count INTEGER NOT NULL DEFAULT 0,
        created_by TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        CHECK (status IN ('generating','pending_review','failed')),
        CHECK (passes_requested BETWEEN 2 AND 7),
        CHECK (passes_completed >= 0 AND passes_completed <= passes_requested)
    )
    """,
    """
    CREATE TABLE candidate_beam_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        candidate_uid TEXT NOT NULL,
        rank INTEGER NOT NULL,
        pass_frequency INTEGER NOT NULL,
        passes_total INTEGER NOT NULL,
        confidence_band TEXT NOT NULL,
        flagged INTEGER NOT NULL DEFAULT 0,
        source_missing INTEGER NOT NULL DEFAULT 0,
        title TEXT NOT NULL,
        official_guidance TEXT,
        actual_reality TEXT,
        action_required TEXT,
        source TEXT,
        category TEXT,
        variants TEXT NOT NULL DEFAULT '[]',
        status TEXT NOT NULL DEFAULT 'pending_review',
        review_note TEXT,
        reviewed_by TEXT,
        reviewed_at TEXT,
        import_country TEXT,
        import_requirement_type TEXT,
        imported_ref TEXT,
        imported_at TEXT,
        imported_by TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        CHECK (status IN ('pending_review','approved','rejected','imported')),
        CHECK (confidence_band IN ('near-certain','strong','moderate','low')),
        CHECK (pass_frequency >= 1 AND pass_frequency <= passes_total),
        UNIQUE (run_id, candidate_uid)
    )
    """,
]


@pytest.fixture()
def conn():
    engine = create_engine("sqlite://", future=True)
    with engine.begin() as connection:
        # `public.` is stripped: SQLite has no schemas, and the module emits the qualified
        # name that production needs.
        connection.execute(text("ATTACH DATABASE ':memory:' AS public"))
        for statement in DDL:
            connection.execute(text(statement.replace("CREATE TABLE ", "CREATE TABLE public.")))
        yield connection


def _run(conn, passes=5, **over):
    return store.create_run(
        conn, corridor="FR-NO", employee_type="eea", passes_requested=passes,
        origin_country="FR", dest_country="NO", llm_model="gpt-4o-mini", **over,
    )


def _items(n=2, prefix="Item"):
    return [{"title": f"{prefix} {i}", "action_required": "do it", "arrival_ordinal": i}
            for i in range(1, n + 1)]


def _meta(ok=True, error=None):
    return {"ok": ok, "item_count": 0, "duration_ms": 5, "model": "gpt-4o-mini", "error": error}


# ---------------------------------------------------------------------------
# Create.
# ---------------------------------------------------------------------------


def test_a_new_run_opens_as_generating_with_nothing_completed(conn):
    run_id = _run(conn)
    run = store.load_run(conn, run_id)
    assert run["status"] == "generating"
    assert run["passes_completed"] == 0
    assert run["pass_outputs"] == [] and run["pass_meta"] == []
    assert store.next_pass_number(run) == 1


@pytest.mark.parametrize("passes", [1, 8, 0, -1])
def test_the_cost_clamp_is_refused_by_name_not_by_constraint(conn, passes):
    """A ValueError naming the bound beats a CHECK violation from three layers down."""
    with pytest.raises(ValueError, match="between 2 and 7"):
        _run(conn, passes=passes)


def test_seven_passes_is_accepted(conn):
    """The schema always allowed 2..7; the pipeline used to cap at 5."""
    run = store.load_run(conn, _run(conn, passes=7))
    assert run["passes_requested"] == 7


def test_the_model_is_recorded_so_billing_stays_distinguishable(conn):
    run = store.load_run(conn, _run(conn, llm_provider="platform"))
    assert (run["llm_provider"], run["llm_model"]) == ("platform", "gpt-4o-mini")


# ---------------------------------------------------------------------------
# One pass at a time.
# ---------------------------------------------------------------------------


def test_a_successful_pass_lands_its_items_and_advances(conn):
    run_id = _run(conn)
    store.record_pass(conn, run_id=run_id, pass_number=1, framing="zero_shot_official_audit",
                      items=_items(3), meta=_meta())
    run = store.load_run(conn, run_id)
    assert run["passes_completed"] == 1
    assert len(run["pass_outputs"][0]["items"]) == 3
    assert store.next_pass_number(run) == 2


def test_a_failed_pass_stores_no_items_and_does_not_advance(conn):
    run_id = _run(conn)
    store.record_pass(conn, run_id=run_id, pass_number=1, framing="zero_shot_official_audit",
                      items=[], meta=_meta(ok=False, error="429 rate limited"))
    run = store.load_run(conn, run_id)
    assert run["passes_completed"] == 0
    assert run["pass_outputs"] == []
    assert run["pass_meta"][0]["error"] == "429 rate limited"
    assert store.next_pass_number(run) == 1, "the failed slot is what resume retries"


def test_a_retry_replaces_the_slot_rather_than_appending(conn):
    """Appending would double-count a slot that ran twice — in passes_completed and in the
    ranking input, where it would inflate cross-pass agreement with one pass's opinion."""
    run_id = _run(conn)
    store.record_pass(conn, run_id=run_id, pass_number=1, framing="f", items=[],
                      meta=_meta(ok=False, error="boom"))
    store.record_pass(conn, run_id=run_id, pass_number=1, framing="f", items=_items(2),
                      meta=_meta())
    run = store.load_run(conn, run_id)
    assert run["passes_completed"] == 1
    assert len(run["pass_meta"]) == 1
    assert len(run["pass_outputs"]) == 1


def test_the_failed_attempt_is_remembered_on_the_replacement(conn):
    """Replacing must not erase the history — the resume trail is how an operator sees a
    slot took two goes."""
    run_id = _run(conn)
    store.record_pass(conn, run_id=run_id, pass_number=1, framing="f", items=[],
                      meta=_meta(ok=False, error="429 rate limited"))
    store.record_pass(conn, run_id=run_id, pass_number=1, framing="f", items=_items(1),
                      meta=_meta())
    run = store.load_run(conn, run_id)
    assert run["pass_meta"][0]["previous_error"] == "429 rate limited"


def test_a_failure_mid_run_does_not_lose_the_completed_passes(conn):
    run_id = _run(conn)
    for number in (1, 2):
        store.record_pass(conn, run_id=run_id, pass_number=number, framing="f",
                          items=_items(2), meta=_meta())
    store.record_pass(conn, run_id=run_id, pass_number=3, framing="f", items=[],
                      meta=_meta(ok=False, error="timeout"))
    run = store.load_run(conn, run_id)
    assert run["passes_completed"] == 2
    assert store.completed_pass_numbers(run) == [1, 2]
    assert store.next_pass_number(run) == 3


def test_resume_returns_to_the_lowest_hole_not_the_next_slot(conn):
    """Skipping ahead would leave a permanent gap that no later call ever fills."""
    run_id = _run(conn)
    store.record_pass(conn, run_id=run_id, pass_number=1, framing="f", items=_items(1), meta=_meta())
    store.record_pass(conn, run_id=run_id, pass_number=2, framing="f", items=[],
                      meta=_meta(ok=False, error="boom"))
    store.record_pass(conn, run_id=run_id, pass_number=3, framing="f", items=_items(1), meta=_meta())
    run = store.load_run(conn, run_id)
    assert store.next_pass_number(run) == 2


def test_a_full_run_reports_no_next_pass(conn):
    run_id = _run(conn, passes=2)
    for number in (1, 2):
        store.record_pass(conn, run_id=run_id, pass_number=number, framing="f",
                          items=_items(1), meta=_meta())
    assert store.next_pass_number(store.load_run(conn, run_id)) is None


def test_a_failed_run_is_kept_as_an_audit_row(conn):
    run_id = _run(conn)
    store.mark_failed(conn, run_id=run_id, error="provider unreachable")
    run = store.load_run(conn, run_id)
    assert run["status"] == "failed"
    assert run["error"] == "provider unreachable"


# ---------------------------------------------------------------------------
# Finalize.
# ---------------------------------------------------------------------------


def _candidate(title, rank=1, freq=2, total=5, **over):
    base = {
        "title": title, "rank": rank, "pass_frequency": freq, "passes_total": total,
        "confidence_band": "moderate", "flagged": False, "source_missing": False,
        "official_guidance": "g", "actual_reality": "r", "action_required": "a",
        "source": "gov.ie", "category": "registration", "variants": [],
    }
    base.update(over)
    return base


def test_persisting_candidates_closes_the_run(conn):
    run_id = _run(conn)
    written = store.persist_candidates(
        conn, run_id=run_id, candidates=[_candidate("PPSN"), _candidate("Lease", rank=2)],
        passes_total=5,
    )
    assert written == 2
    run = store.load_run(conn, run_id)
    assert run["status"] == "pending_review"
    assert run["candidate_count"] == 2


def test_every_candidate_starts_at_pending_review(conn):
    run_id = _run(conn)
    store.persist_candidates(conn, run_id=run_id, candidates=[_candidate("PPSN")], passes_total=5)
    rows = conn.execute(text("SELECT status FROM public.candidate_beam_items")).all()
    assert [r[0] for r in rows] == ["pending_review"]


def test_the_candidate_uid_is_stable_across_rebuilds(conn):
    """Keying on rank would make every rebuild look like a new set and orphan the verdicts
    attached to the old rows."""
    assert store.candidate_uid_for("PPSN registration") == store.candidate_uid_for("  ppsn REGISTRATION ")
    assert store.candidate_uid_for("PPSN") != store.candidate_uid_for("Lease")


def test_a_rebuild_refreshes_the_ranking(conn):
    run_id = _run(conn)
    store.persist_candidates(conn, run_id=run_id, candidates=[_candidate("PPSN", rank=3, freq=1)],
                             passes_total=5)
    store.persist_candidates(conn, run_id=run_id,
                             candidates=[_candidate("PPSN", rank=1, freq=4, confidence_band="strong")],
                             passes_total=5)
    row = conn.execute(
        text("SELECT rank, pass_frequency, confidence_band FROM public.candidate_beam_items")
    ).mappings().first()
    assert (row["rank"], row["pass_frequency"], row["confidence_band"]) == (1, 4, "strong")


def test_a_rebuild_never_touches_a_human_verdict(conn):
    """THE rule. Re-finalizing after a late pass must not silently un-approve what someone
    already judged, and must not reset an item already imported — the schema's import freeze
    depends on those columns surviving."""
    run_id = _run(conn)
    store.persist_candidates(conn, run_id=run_id, candidates=[_candidate("PPSN")], passes_total=5)
    conn.execute(
        text(
            "UPDATE public.candidate_beam_items SET status='imported', review_note='checked',"
            " reviewed_by='romain', import_country='IE', import_requirement_type='IDENTITY',"
            " imported_ref='beam-1'"
        )
    )

    store.persist_candidates(conn, run_id=run_id, candidates=[_candidate("PPSN", rank=9, freq=1)],
                             passes_total=5)

    row = conn.execute(
        text(
            "SELECT status, review_note, reviewed_by, import_country, import_requirement_type,"
            " imported_ref, rank FROM public.candidate_beam_items"
        )
    ).mappings().first()
    assert row["status"] == "imported"
    assert row["review_note"] == "checked"
    assert row["reviewed_by"] == "romain"
    assert (row["import_country"], row["import_requirement_type"]) == ("IE", "IDENTITY")
    assert row["imported_ref"] == "beam-1"
    assert row["rank"] == 9, "the ranking still refreshed"


def test_passes_total_reflects_what_was_attempted_not_what_survived(conn):
    """A run that lost a pass must not report its survivors as unanimous — 4/4 reads as
    near-certain when the honest answer is 4/5."""
    run_id = _run(conn, passes=5)
    store.persist_candidates(
        conn, run_id=run_id, candidates=[_candidate("PPSN", freq=4, total=5)], passes_total=5
    )
    row = conn.execute(
        text("SELECT pass_frequency, passes_total FROM public.candidate_beam_items")
    ).mappings().first()
    assert (row["pass_frequency"], row["passes_total"]) == (4, 5)


def test_a_candidate_with_no_title_is_skipped(conn):
    run_id = _run(conn)
    written = store.persist_candidates(
        conn, run_id=run_id, candidates=[_candidate(""), _candidate("PPSN")], passes_total=5
    )
    assert written == 1
