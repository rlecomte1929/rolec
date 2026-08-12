"""[O1] A requirement must never show an invented quote or a fake link.

WHAT THIS FIXES
---------------
All ten original `source_records` carried `snippet = 'Stub content for ' || url`, and two of them
pointed at `https://example.com/`. `_source_dto` passes `snippet` straight to the DTO, so the UI
rendered that placeholder underneath the requirement as if it were an official quote.

It went unnoticed because until 20261031000000 landed there was nothing to compare against —
measured in production immediately after that migration:

    items showing a source                35
      ...showing "Stub content for ..."   27
      ...whose link is example.com         6
      ...showing a real official quote     8   <- added an hour earlier

So every piece of visible evidence in the product was a placeholder.

A fabricated quote next to a real requirement is worse than no quote, because it reads as
corroboration. Hence two different fixes for two different problems: a real government URL with an
invented snippet keeps its link and loses the sentence; an example.com record is removed entirely,
because the URL itself is fake and there is nothing worth keeping.

RUNNING — throwaway local Postgres, never production. `integration`-marked; CI skips it.

    DATABASE_URL=postgresql://postgres:test@127.0.0.1:55439/o1test \
      pytest backend/tests/integration/test_no_fake_evidence.py -v
"""
from __future__ import annotations

import os
import pathlib

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, text  # noqa: E402

DATABASE_URL = os.environ.get("DATABASE_URL", "")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DATABASE_URL.startswith("postgres"), reason="needs real Postgres"),
]

MIGRATION = (
    pathlib.Path(__file__).resolve().parents[3]
    / "supabase" / "migrations" / "20261032000000_remove_fake_evidence.sql"
)

SCHEMA = """
DROP TABLE IF EXISTS public.requirement_items CASCADE;
DROP TABLE IF EXISTS public.source_records CASCADE;
CREATE TABLE public.source_records (
    id varchar PRIMARY KEY, country_code varchar, url varchar NOT NULL, title varchar NOT NULL,
    publisher_domain varchar NOT NULL, retrieved_at timestamp NOT NULL, snippet text,
    content_hash varchar NOT NULL UNIQUE);
CREATE TABLE public.requirement_items (
    id varchar PRIMARY KEY, country_code varchar, purpose varchar NOT NULL,
    pillar varchar NOT NULL, title varchar NOT NULL, description text NOT NULL,
    severity varchar NOT NULL, owner varchar NOT NULL, required_fields_json text NOT NULL,
    citations_json text NOT NULL, last_verified_at timestamp NOT NULL, verification_status text);
"""


@pytest.fixture()
def engine():
    eng = create_engine(DATABASE_URL, future=True)
    with eng.begin() as c:
        for stmt in filter(None, (s.strip() for s in SCHEMA.split(";"))):
            c.execute(text(stmt))
        c.execute(text(
            "INSERT INTO public.source_records VALUES "
            "('stub-udi','NORWAY','https://www.udi.no/en/','UDI','www.udi.no',now(),"
            "  'Stub content for https://www.udi.no/en/','h1'),"
            "('stub-ex','GERMANY','https://example.com/immigration','Imm','example.com',now(),"
            "  'Stub content for https://example.com/immigration','h2'),"
            "('real','NORWAY','https://www.skatteetaten.no/en/x/','Skatt','www.skatteetaten.no',"
            "  now(),'Without a tax deduction card, the employer must deduct 50 percent tax.','h3')"
        ))
        for rid, cc, cites in (
            ("i-stub", "NORWAY", '["stub-udi"]'),
            ("i-ex", "GERMANY", '["stub-ex"]'),
            ("i-mixed", "GERMANY", '["stub-ex","stub-udi"]'),
            ("i-real", "NORWAY", '["real"]'),
        ):
            c.execute(
                text("INSERT INTO public.requirement_items (id,country_code,purpose,pillar,title,"
                     "description,severity,owner,required_fields_json,citations_json,"
                     "last_verified_at,verification_status) VALUES "
                     "(:i,:cc,'employment','IDENTITY','t','d','BLOCKER','o','[]',:c,now(),'representative')"),
                {"i": rid, "cc": cc, "c": cites},
            )
    yield eng
    eng.dispose()


def _apply(engine) -> None:
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute(MIGRATION.read_text(encoding="utf-8"))
        raw.commit()
    finally:
        raw.close()


def _snippets(engine) -> list:
    with engine.connect() as c:
        return [r[0] for r in c.execute(text("SELECT snippet FROM public.source_records")).fetchall()]


def test_before_the_migration_placeholder_text_is_rendered(engine):
    """Characterisation. Two of the three sources would show invented text to a user."""
    assert sum(1 for s in _snippets(engine) if s and s.startswith("Stub content for")) == 2


def test_no_invented_quote_survives(engine):
    _apply(engine)
    assert not [s for s in _snippets(engine) if s and s.startswith("Stub content for")]


def test_a_real_url_keeps_its_link_and_loses_only_the_quote(engine):
    """The authority is genuine and useful; only the sentence was invented."""
    _apply(engine)
    with engine.connect() as c:
        row = c.execute(text(
            "SELECT url, snippet FROM public.source_records WHERE id='stub-udi'"
        )).one()
    assert row[0] == "https://www.udi.no/en/", "the link must survive"
    assert row[1] is None, "the invented quote must not"


def test_example_com_is_removed_entirely(engine):
    """The URL itself is fake, so there is nothing worth keeping."""
    _apply(engine)
    with engine.connect() as c:
        assert c.execute(text(
            "SELECT count(*) FROM public.source_records WHERE url LIKE '%example.com%'"
        )).scalar() == 0
        # An item citing only the fake source ends with no evidence. That is the honest outcome.
        assert c.execute(text(
            "SELECT citations_json FROM public.requirement_items WHERE id='i-ex'"
        )).scalar() == "[]"


def test_a_mixed_item_keeps_its_genuine_citation(engine):
    """Dropping the real one alongside the fake would be the same defect, inverted."""
    _apply(engine)
    with engine.connect() as c:
        cites = c.execute(text(
            "SELECT citations_json FROM public.requirement_items WHERE id='i-mixed'"
        )).scalar()
    assert "stub-udi" in cites
    assert "stub-ex" not in cites


def test_the_real_frno_quote_is_untouched(engine):
    """20261031000000's eight verbatim official sentences must not be collateral."""
    _apply(engine)
    with engine.connect() as c:
        snippet = c.execute(text("SELECT snippet FROM public.source_records WHERE id='real'")).scalar()
        cites = c.execute(text("SELECT citations_json FROM public.requirement_items WHERE id='i-real'")).scalar()
    assert "50 percent" in snippet
    assert cites == '["real"]'


def test_idempotent(engine):
    _apply(engine)
    _apply(engine)
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM public.source_records")).scalar() == 2
