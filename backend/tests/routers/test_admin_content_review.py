"""[AIQ-1821] The content review queue API.

SQLite-backed, mirroring test_requirement_facts_review.py: a real in-memory schema with the
module's `db` patched, and the endpoint functions called directly. The suite's conftest replaces
backend.database with a MagicMock, so a TestClient-based test here would assert against mock
return values and pass while proving nothing.

One test does use the real app object — to prove the router is registered on backend.main, which
is what Render boots. A router registered only in backend/app/main.py 405s in production.
"""
from __future__ import annotations

import unittest
import uuid
from unittest import mock

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

import backend.app.routers.admin_content_review as acr
from backend.db.policies import PoliciesMixin

_ADMIN = {"id": "seed-admin-legacy-text-id", "is_admin": True, "email": "a@relopass.com"}

SCHEMA = [
    """CREATE TABLE requirement_entities (
        id TEXT PRIMARY KEY, destination_country TEXT NOT NULL, domain_area TEXT NOT NULL,
        topic_key TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT, updated_at TEXT)""",
    """CREATE TABLE requirement_facts (
        id TEXT PRIMARY KEY, entity_id TEXT NOT NULL, fact_type TEXT NOT NULL,
        fact_key TEXT NOT NULL, fact_text TEXT NOT NULL, applies_to TEXT NOT NULL,
        required_fields TEXT NOT NULL, source_doc_id TEXT NOT NULL, source_url TEXT NOT NULL,
        evidence_quote TEXT, confidence TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT, evidence_verified INTEGER, evidence_offset INTEGER,
        evidence_checked_at TEXT, reviewed_by TEXT, reviewed_at TEXT)""",
    """CREATE TABLE requirement_reviews (
        id TEXT PRIMARY KEY, entity_id TEXT, fact_id TEXT, reviewer_user_id TEXT NOT NULL,
        action TEXT NOT NULL, notes TEXT, created_at TEXT,
        previous_fact_text TEXT, new_fact_text TEXT)""",
    # Both source-text columns, because the router now resolves between them: neither is
    # reliably the fuller one (the enterprise.gov.ie permit pages hold the real page in
    # text_content and 308 chars of cookie banner in the excerpt).
    """CREATE TABLE knowledge_docs (
        id TEXT PRIMARY KEY, content_excerpt TEXT, text_content TEXT, last_verified_at TEXT)""",
]

# Long enough to clear MIN_USABLE_SOURCE_CHARS, and containing the supported quote.
SOURCE = (
    "You cannot apply for a D number. An enterprise or authority can request one for you. "
    "The certified copy cannot be older than three months and must be sent by post. "
    "You must book an appointment with the Tax Administration for an ID check. "
) * 2

ENTITY, DOC = "ent-1", "doc-1"
SUPPORTED, INVENTED = "fact-supported", "fact-invented"


class _DB(PoliciesMixin):
    """Just enough Database for the router: the engine plus the two mutation methods."""

    def __init__(self, engine):
        self.engine = engine


class ContentReviewTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        with self.engine.begin() as conn:
            for ddl in SCHEMA:
                conn.execute(text(ddl))
            conn.execute(text(
                "INSERT INTO knowledge_docs (id, content_excerpt, text_content, "
                "last_verified_at) VALUES (:i, :x, :b, '2026-08-12')"),
                {"i": DOC, "x": SOURCE, "b": ""})
            conn.execute(text(
                "INSERT INTO requirement_entities (id, destination_country, domain_area, "
                "topic_key, title) VALUES (:i,'NO','registration','no.d_number','D number')"),
                {"i": ENTITY})
            for fid, txt, quote in (
                (SUPPORTED, "You cannot apply for a D number.",
                 "You cannot apply for a D number."),
                (INVENTED, "A D number costs NOK 5400.", "A D number costs NOK 5400."),
            ):
                conn.execute(text(
                    "INSERT INTO requirement_facts (id, entity_id, fact_type, fact_key, "
                    "fact_text, applies_to, required_fields, source_doc_id, source_url, "
                    "evidence_quote, confidence, status) "
                    "VALUES (:i,:e,'document',:k,:t,'{}','[]',:d,'https://x/',:q,'high','pending')"
                ), {"i": fid, "e": ENTITY, "k": fid, "t": txt, "d": DOC, "q": quote})

        self._db = _DB(self.engine)
        self._patch = mock.patch.object(acr, "db", self._db)
        self._patch.start()
        self.addCleanup(self._patch.stop)
        # audit_logs is not in this schema; the router must survive an audit failure.
        self._audit = mock.patch.object(acr, "_audit", lambda *a, **k: None)
        self._audit.start()
        self.addCleanup(self._audit.stop)

    def _list(self, **kw):
        return acr.list_facts(status=kw.pop("status", "pending"), destination=kw.pop("dest", None),
                              evidence=kw.pop("evidence", None), q=kw.pop("q", None),
                              limit=kw.pop("limit", 50), offset=kw.pop("offset", 0), user=_ADMIN)

    def _one(self, items, fid):
        return next(i for i in items if i["id"] == fid)

    # ── the queue's reason to exist ────────────────────────────────────────────
    def test_list_carries_the_evidence_not_just_a_flag(self):
        items = self._list(dest="NO")["items"]
        good = self._one(items, SUPPORTED)
        self.assertEqual(good["evidence_status"], "verified")
        self.assertIn("cannot apply for a D number", good["evidence_context"])
        # Context must extend past the quote, or a condition reads as an obligation.
        self.assertGreater(len(good["evidence_context"]), len(good["evidence_quote"]))

        bad = self._one(items, INVENTED)
        self.assertEqual(bad["evidence_status"], "unverified")
        self.assertEqual(bad["evidence_context"], "")

    def test_the_quote_is_found_when_the_excerpt_captured_only_a_cookie_banner(self):
        """`knowledge_docs` has two source-text columns and neither is reliably the fuller one.

        Measured on production 2026-08-23: the enterprise.gov.ie permit pages hold 17,333
        characters in `text_content` and **308 characters of cookie banner** in
        `content_excerpt`. Reading the excerpt alone marks nine served Critical Skills
        Employment Permit facts unverified — on the first real customer's corridor — and shows
        the reviewer "no source" for a page that plainly carries the claim.
        """
        cookie = "Our website uses cookies to enhance your browsing experience. " * 6
        page = ("The Critical Skills Employment Permit is designed to attract highly skilled "
                "people. Because the skills are identified as being in short supply, a Labour "
                "Market Needs Test is not required. Eligible occupations are listed separately. "
                ) * 4
        quote = "a Labour Market Needs Test is not required"
        doc, fact = str(uuid.uuid4()), str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO knowledge_docs (id, content_excerpt, text_content, "
                "last_verified_at) VALUES (:i,:x,:b,'2026-08-20')"),
                {"i": doc, "x": cookie, "b": page})
            conn.execute(text(
                "INSERT INTO requirement_facts (id, entity_id, fact_type, fact_key, fact_text, "
                "applies_to, required_fields, source_doc_id, source_url, evidence_quote, "
                "confidence, status) VALUES "
                "(:i,:e,'eligibility','csep_no_lmnt','No LMNT is required.','{}','[]',:d,"
                "'https://enterprise.gov.ie/x',:q,'high','pending')"),
                {"i": fact, "e": ENTITY, "d": doc, "q": quote})

        item = self._one(self._list(dest="NO")["items"], fact)
        self.assertEqual(item["evidence_status"], "verified")
        self.assertIn("short supply", item["evidence_context"])

    def test_search_and_pagination(self):
        self.assertEqual([i["id"] for i in self._list(q="costs NOK")["items"]], [INVENTED])
        page = self._list(limit=1, offset=0)
        self.assertEqual(len(page["items"]), 1)
        self.assertEqual(page["total"], 2)

    # ── decisions ─────────────────────────────────────────────────────────────
    def test_approve_records_a_legacy_text_reviewer_without_rolling_back(self):
        """The #1543 shape: a non-uuid reviewer id must not take the approval down with it."""
        acr.decide(acr.DecideRequest(fact_ids=[SUPPORTED], action="approve"), user=_ADMIN)
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT status, reviewed_by FROM requirement_facts WHERE id=:i"), {"i": SUPPORTED}
            ).first()
            rev = conn.execute(text(
                "SELECT action, reviewer_user_id FROM requirement_reviews WHERE fact_id=:i"),
                {"i": SUPPORTED}).fetchall()
        self.assertEqual(row[0], "approved")
        self.assertEqual(row[1], _ADMIN["id"])
        self.assertEqual([(a, r) for a, r in rev], [("approve", _ADMIN["id"])])

    def test_reject_requires_a_reason(self):
        """A rejection with no reason is unreviewable later and teaches the extractor nothing."""
        with self.assertRaises(HTTPException) as ctx:
            acr.decide(acr.DecideRequest(fact_ids=[INVENTED], action="reject"), user=_ADMIN)
        self.assertEqual(ctx.exception.status_code, 400)
        acr.decide(acr.DecideRequest(fact_ids=[INVENTED], action="reject",
                                     notes="Fee is invented; not on the page."), user=_ADMIN)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text(
                "SELECT status FROM requirement_facts WHERE id=:i"), {"i": INVENTED}).scalar_one(),
                "rejected")

    def test_bulk_decides_every_id_in_one_call(self):
        acr.decide(acr.DecideRequest(fact_ids=[SUPPORTED, INVENTED], action="approve"), user=_ADMIN)
        with self.engine.connect() as conn:
            n = conn.execute(text(
                "SELECT count(*) FROM requirement_facts WHERE status='approved'")).scalar_one()
        self.assertEqual(n, 2)

    # ── the verdict approve/reject cannot express ──────────────────────────────
    def test_edit_records_both_sides_and_invalidates_stale_verification(self):
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE requirement_facts SET evidence_verified=1, "
                              "evidence_offset=0 WHERE id=:i"), {"i": SUPPORTED})
        acr.edit_fact(SUPPORTED, acr.EditRequest(
            fact_text="You cannot apply for a D number yourself.",
            notes="Clarified who applies."), user=_ADMIN)
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT fact_text, evidence_verified, status FROM requirement_facts WHERE id=:i"),
                {"i": SUPPORTED}).first()
            rev = conn.execute(text(
                "SELECT previous_fact_text, new_fact_text FROM requirement_reviews "
                "WHERE fact_id=:i AND action='edit'"), {"i": SUPPORTED}).first()
        self.assertEqual(row[0], "You cannot apply for a D number yourself.")
        self.assertIsNone(row[1], "the claim was rewritten — its old proof no longer describes it")
        self.assertEqual(row[2], "approved")
        self.assertEqual(rev[0], "You cannot apply for a D number.")
        self.assertEqual(rev[1], "You cannot apply for a D number yourself.")

    def test_edit_404s_for_an_unknown_fact(self):
        with self.assertRaises(HTTPException) as ctx:
            acr.edit_fact(str(uuid.uuid4()), acr.EditRequest(fact_text="x y z"), user=_ADMIN)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_summary_buckets_pending_by_evidence_state(self):
        body = acr.summary(user=_ADMIN)
        self.assertEqual(body["pending"], 2)
        self.assertIn("NO", body["by_destination"])


class RegistrationTests(unittest.TestCase):
    def test_router_is_registered_on_the_app_render_actually_boots(self):
        """Registered only in backend/app/main.py would 405 in production."""
        from backend.main import app

        paths = {r.path for r in app.routes if "content-review" in getattr(r, "path", "")}
        self.assertIn("/api/admin/content-review/facts", paths)
        self.assertIn("/api/admin/content-review/decide", paths)
