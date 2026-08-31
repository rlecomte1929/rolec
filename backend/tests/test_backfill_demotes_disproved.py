"""[AIQ-1887 VC1] A disproved fact must not keep its approved badge — and only a DISPROOF demotes.

The reader guard (`list_approved_requirement_facts`, `COALESCE(evidence_verified, TRUE) = TRUE`)
hides an approved+FALSE fact from the dossier, but the fact is still `status='approved'`. The
backfill writes `evidence_verified` and, before this change, left the status alone — so every
re-check reopened VC1 ("0 approved facts with evidence_verified IS FALSE"). The fix demotes a
fact to `pending` the moment its verdict is a definitive FALSE.

The load-bearing distinction is FALSE vs NULL. `check_evidence` returns:
  * verified=True   quote found            -> stays approved (verified)
  * verified=False  source in hand, quote absent -> DEMOTE (disproved)
  * verified=None   no usable source, or a translated quote -> stays approved and served

A NULL is "we could not check", not "it is wrong", and the product deliberately keeps serving
those (with an "unverified" citation badge). Demoting on NULL would strip live facts off the
dossier every time a government page refused our fetch — the exact over-reach the ticket's
constraints forbid ("a dead source URL is signal, not a failure").

Same harness as test_backfill_fact_evidence_only_unchecked.py: a real SQLite engine, the
`backend.database` module owned outright for the test, and the network stubbed. The fetch stub
is URL-aware so one document can return an empty page (NO_SOURCE) while another returns text.
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

# Archived page text a live fetch returns. Long enough to clear the minimum-source guard, and it
# CONTAINS the quote the "present" facts cite.
SOURCE_TEXT = ("Critical Skills Employment Permit holders may apply after two years. " * 12)
QUOTE_PRESENT = "Critical Skills Employment Permit holders may apply after two years."
QUOTE_ABSENT = "wording that this page has never carried"


class _StubDb:
    def __init__(self, engine):
        self.engine = engine


def _seed_engine():
    """Two documents: one live (returns text), one that renders empty (a JS shell / dead page).

    Every fact starts `approved`. The three NULL facts are what a served-cohort re-check
    (`--status approved --only-unchecked`) selects; `true_absent` is there to prove an
    already-verified fact is not dragged in.
    """
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
        conn.execute(text(
            "INSERT INTO knowledge_docs (id, fetch_status) VALUES ('doc_live','not_fetched')"))
        conn.execute(text(
            "INSERT INTO knowledge_docs (id, fetch_status) VALUES ('doc_empty','not_fetched')"))

        rows = [
            # id,             verified, quote,          doc,         url
            ("null_present",  None, QUOTE_PRESENT, "doc_live",  "https://example.ie/live"),
            ("null_absent",   None, QUOTE_ABSENT,  "doc_live",  "https://example.ie/live"),
            ("null_nosource", None, QUOTE_PRESENT, "doc_empty", "https://example.ie/empty"),
            ("true_absent",   1,    QUOTE_ABSENT,  "doc_live",  "https://example.ie/live"),
        ]
        for fid, verified, quote, doc, url in rows:
            conn.execute(
                text(
                    "INSERT INTO requirement_facts"
                    " (id, entity_id, status, evidence_verified, evidence_quote,"
                    "  source_doc_id, source_url)"
                    " VALUES (:id,'e_ie','approved',:v,:q,:doc,:url)"
                ),
                {"id": fid, "v": verified, "q": quote, "doc": doc, "url": url},
            )
    return engine


def _fake_fetch(url, robots=None, limiter=None, headless=False):
    """Live URL returns archived text; the 'empty' URL renders to nothing (NO_SOURCE)."""
    if "empty" in url:
        return {"ok": False, "reason": "js_shell_or_empty", "text": "", "blocked": False,
                "ua": None}
    return {"ok": True, "reason": "fetched", "text": SOURCE_TEXT, "blocked": False,
            "ua": "ReloPassBot/1.0"}


@pytest.fixture()
def engine(monkeypatch):
    eng = _seed_engine()
    stub_module = types.ModuleType("backend.database")
    stub_module.db = _StubDb(eng)
    monkeypatch.setitem(sys.modules, "backend.database", stub_module)
    monkeypatch.setattr(bf, "fetch_and_parse", _fake_fetch)
    return eng


def _row(engine, fid):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT status, evidence_verified FROM requirement_facts WHERE id = :id"),
            {"id": fid},
        ).one()


def test_a_disproved_fact_is_demoted_to_pending(engine):
    bf.main(["--dest", "IE", "--status", "approved", "--only-unchecked", "--apply"])
    status, verified = _row(engine, "null_absent")
    assert status == "pending"
    assert verified == 0


def test_a_verified_fact_stays_approved(engine):
    bf.main(["--dest", "IE", "--status", "approved", "--only-unchecked", "--apply"])
    status, verified = _row(engine, "null_present")
    assert status == "approved"
    assert verified == 1


def test_an_unverifiable_fact_is_not_demoted(engine):
    """The safety property: NO_SOURCE is None, not False, and must stay approved and served.

    `null_nosource` cites a page that renders empty. Demoting it would pull a live fact off the
    dossier because our fetcher could not read the page — punishing the fact for our failure.
    """
    bf.main(["--dest", "IE", "--status", "approved", "--only-unchecked", "--apply"])
    status, verified = _row(engine, "null_nosource")
    assert status == "approved"
    assert verified is None


def test_an_already_verified_fact_is_left_alone(engine):
    """`true_absent` is not NULL, so --only-unchecked never selects it; it keeps serving even
    though its quote is no longer on the page (that is the job of test_..._only_unchecked)."""
    bf.main(["--dest", "IE", "--status", "approved", "--only-unchecked", "--apply"])
    status, verified = _row(engine, "true_absent")
    assert status == "approved"
    assert verified == 1


def test_a_dry_run_demotes_nothing(engine):
    bf.main(["--dest", "IE", "--status", "approved", "--only-unchecked"])
    status, verified = _row(engine, "null_absent")
    assert status == "approved"
    assert verified is None


def test_a_pending_cohort_run_never_demotes(engine):
    """Demotion is scoped to the approved cohort. A `--status pending` run adjudicates facts
    that are already pending; it must not touch status even when a verdict is FALSE."""
    with engine.begin() as conn:
        conn.execute(text("UPDATE requirement_facts SET status='pending' WHERE id='null_absent'"))
    bf.main(["--dest", "IE", "--status", "pending", "--only-unchecked", "--apply"])
    status, verified = _row(engine, "null_absent")
    assert status == "pending"
    assert verified == 0
