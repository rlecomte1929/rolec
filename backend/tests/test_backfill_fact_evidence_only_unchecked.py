"""`--only-unchecked` must narrow a re-check to facts that have never been checked.

WHY THIS FLAG EXISTS. `--status approved` selects the cohort the product is SERVING, and this
script rewrites `evidence_verified` for every fact it selects. On a re-check that is a hazard,
not a no-op: a fact currently verified TRUE can come back FALSE because the publisher reworded
the page, started refusing our user-agent, or the parser's output shifted. `list_approved_
requirement_facts` filters `COALESCE(evidence_verified, TRUE) = TRUE`, so that fact leaves the
served surface immediately — a remediation that removes a working citation, which is strictly
worse than the unchecked fact it set out to fix.

Measured on production 2026-08-22: Ireland has 75 approved facts — 21 verified, 16 unchecked,
38 disproved. A `--dest IE --status approved` run aimed at those 16 puts the other 59 through
the check as collateral.

THE TRAP THIS PINS. The filter must apply to the FACT, not to the source document. Documents
are the unit of fetching, and one document routinely carries both an already-verified fact and
an unchecked one. A filter written as "documents that have an unchecked fact" would drag the
verified fact back through the check and put its verdict at risk anyway — passing the obvious
test while preserving the whole bug. `test_a_shared_document_only_rechecks_its_unchecked_fact`
is the one that catches that.

These tests run the real `main()` against a real SQLite engine with the network stubbed, so
they pin behaviour rather than the spelling of a WHERE clause.
"""
from __future__ import annotations

import os
import sys
import types

import pytest
from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.scripts.backfill_fact_evidence as bf  # noqa: E402

# The archived page text every stubbed fetch returns. Long enough to clear any minimum-length
# guard in the parser path, and it CONTAINS the quote used by the "unchecked" facts below.
SOURCE_TEXT = ("Critical Skills Employment Permit holders may apply after two years. " * 12)
QUOTE_PRESENT = "Critical Skills Employment Permit holders may apply after two years."


class _StubDb:
    def __init__(self, engine):
        self.engine = engine


def _seed_engine():
    """Two documents. doc_shared carries a verified fact AND an unchecked one."""
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE requirement_entities (id TEXT PRIMARY KEY, destination_country TEXT)"
        ))
        conn.execute(text(
            "CREATE TABLE requirement_facts ("
            " id TEXT PRIMARY KEY, entity_id TEXT, status TEXT, evidence_verified BOOLEAN,"
            " evidence_offset INTEGER, evidence_checked_at TEXT, evidence_quote TEXT,"
            " source_doc_id TEXT, source_url TEXT)"
        ))
        conn.execute(text(
            "CREATE TABLE knowledge_docs ("
            " id TEXT PRIMARY KEY, content_excerpt TEXT, content_sha256 TEXT,"
            " fetch_status TEXT, fetched_at TEXT, last_verified_at TEXT)"
        ))
        conn.execute(text(
            "INSERT INTO requirement_entities (id, destination_country) VALUES ('e_ie','IE')"
        ))
        for doc in ("doc_shared", "doc_solo"):
            conn.execute(
                text("INSERT INTO knowledge_docs (id, fetch_status) VALUES (:d,'not_fetched')"),
                {"d": doc},
            )

        # `verified_a` is the load-bearing row: it is currently served (evidence_verified=TRUE)
        # but its quote is NO LONGER on the page — the publisher reworded it after the original
        # check. That is the exact real-world condition under which an unscoped re-check
        # silently removes a working citation, so the fixture has to reproduce it. If this row's
        # quote were still present, every assertion about it would pass whether the filter
        # worked or not.
        rows = [
            # id,            verified, quote,                                doc
            ("verified_a",   1,        "wording the page no longer carries", "doc_shared"),
            ("unchecked_a",  None,     QUOTE_PRESENT,                        "doc_shared"),
            ("unchecked_b",  None,     QUOTE_PRESENT,                        "doc_solo"),
            ("disproved_a",  0,        "text that is absent from the page",  "doc_solo"),
        ]
        for fid, verified, quote, doc in rows:
            conn.execute(
                text(
                    "INSERT INTO requirement_facts"
                    " (id, entity_id, status, evidence_verified, evidence_quote,"
                    "  source_doc_id, source_url)"
                    " VALUES (:id,'e_ie','approved',:v,:q,:doc,'https://example.ie/page')"
                ),
                {"id": fid, "v": verified, "q": quote, "doc": doc},
            )
    return engine


@pytest.fixture()
def engine(monkeypatch):
    """Own the `backend.database` module entry outright for the duration of the test.

    `main()` resolves the handle with a function-local `from backend.database import db`.
    Setting the attribute on the already-imported module is NOT enough here: backend's
    conftest substitutes its own object for that module, so under full-suite discovery the
    attribute we patch and the one `main()` reads are not always the same object — the run
    then quietly processes nothing and every assertion about writes trivially "passes" as
    an empty set. That is precisely how this file passed alone and failed in CI.

    Replacing the sys.modules entry makes the import resolve to this stub whatever else
    the suite has done, and monkeypatch restores the original afterwards. Deliberately NOT
    importing backend.database at module scope either: importing it at collection time is
    itself the ordering hazard conftest warns about.
    """
    eng = _seed_engine()
    stub_module = types.ModuleType("backend.database")
    stub_module.db = _StubDb(eng)
    monkeypatch.setitem(sys.modules, "backend.database", stub_module)
    monkeypatch.setattr(
        bf, "fetch_and_parse",
        lambda url, robots=None, limiter=None, headless=False: {
            "ok": True, "reason": "fetched", "text": SOURCE_TEXT, "blocked": False,
            "ua": "ReloPassBot/1.0",
        },
    )
    return eng


def _checked_ids(engine):
    """Facts the run actually touched — evidence_checked_at is written for every selected fact."""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id FROM requirement_facts WHERE evidence_checked_at IS NOT NULL"
        )).fetchall()
    return {r[0] for r in rows}


def _verified_of(engine, fid):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT evidence_verified FROM requirement_facts WHERE id = :id"), {"id": fid}
        ).scalar()


def test_only_unchecked_touches_exactly_the_never_checked_facts(engine):
    bf.main(["--dest", "IE", "--status", "approved", "--only-unchecked", "--apply"])
    assert _checked_ids(engine) == {"unchecked_a", "unchecked_b"}


def test_an_already_verified_fact_keeps_its_verdict(engine):
    """The serving-regression guard.

    `verified_a`'s quote is no longer on the page, so an unscoped re-check WOULD flip it to
    FALSE and drop it out of `list_approved_requirement_facts`. With the filter it is never
    adjudicated and keeps serving.
    """
    bf.main(["--dest", "IE", "--status", "approved", "--only-unchecked", "--apply"])
    assert _verified_of(engine, "verified_a") == 1


def test_an_unscoped_recheck_really_would_unpublish_that_fact(engine):
    """Proves the hazard is real, not theoretical — the reason the flag exists.

    Same fixture, same reworded page, only the filter removed: the fact flips TRUE -> FALSE.
    `COALESCE(evidence_verified, TRUE) = TRUE` then excludes it, so a citation that was working
    disappears from the employee's dossier as a side effect of a remediation. If this ever stops
    flipping, the fixture has lost the condition it was built to model.
    """
    bf.main(["--dest", "IE", "--status", "approved", "--apply"])
    assert _verified_of(engine, "verified_a") == 0


def test_a_shared_document_only_rechecks_its_unchecked_fact(engine):
    """Per-FACT, not per-document.

    doc_shared carries both `verified_a` and `unchecked_a`. The document must still be fetched
    (the unchecked fact needs its text), but only the unchecked fact may be adjudicated. A
    document-level filter passes the other two tests and fails this one.
    """
    bf.main(["--dest", "IE", "--status", "approved", "--only-unchecked", "--apply"])
    checked = _checked_ids(engine)
    assert "unchecked_a" in checked, "the unchecked fact on the shared doc must be checked"
    assert "verified_a" not in checked, "the verified fact on the SAME doc must be left alone"


def test_without_the_flag_every_fact_in_scope_is_rewritten(engine):
    """The discriminating negative.

    Proves the flag does something. Without it the run adjudicates all four facts — including
    the already-verified one, which is precisely the exposure the flag removes. If this test
    ever matches the filtered result, the flag has stopped working.
    """
    bf.main(["--dest", "IE", "--status", "approved", "--apply"])
    assert _checked_ids(engine) == {"verified_a", "unchecked_a", "unchecked_b", "disproved_a"}


def test_a_dry_run_writes_nothing_even_with_the_flag(engine):
    bf.main(["--dest", "IE", "--status", "approved", "--only-unchecked"])
    assert _checked_ids(engine) == set()
    assert _verified_of(engine, "unchecked_a") is None


def test_match_window_exceeds_stored_excerpt_and_finds_a_quote_past_24k():
    """[2026-08-30] Statutory pages (eur-lex Directive 2004/38, Reg 883/2004) run past 24k, and
    the cited article can sit well beyond it. Before the fix, fetch_and_parse truncated the MATCH
    text at 24k, false-flagging five sound EU-law quotes as `unverified`. We now match on the full
    page and store only a bounded head.
    """
    import importlib
    m = importlib.import_module("backend.scripts.backfill_fact_evidence")
    # The match window must be much larger than the stored excerpt.
    assert m.MAX_MATCH_CHARS > m.MAX_EXCERPT_CHARS
    assert m.MAX_MATCH_CHARS >= 500_000

    from backend.app.services.fact_evidence import check_evidence, VERIFIED
    # A quote that only appears ~100k chars into the page — past the old 24k cap.
    quote = "he is not sent to replace another person"
    page = ("filler sentence about social security coordination. " * 3000) + \
           " provided that the anticipated duration of such work does not exceed twenty-four " \
           "months and that " + quote + ". " + ("more filler. " * 200)
    assert len(page) > m.MAX_EXCERPT_CHARS  # the quote sits past the stored-excerpt cap
    assert check_evidence(quote, page).status == VERIFIED
