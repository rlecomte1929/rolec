"""Tests for E-PIPE-5 v1 deterministic CanonicalStore + entity-link writer.

Pure helpers + store methods + the resolve_and_link wiring, with a fake SQLAlchemy
connection (no DB). The real jsonb/vector SQL + dedup behaviour is validated against
prod in a rollback transaction (see PR).
"""

from __future__ import annotations

from backend.relopass.agents.entity_resolution import CanonicalPerson, ExtractedPerson
from backend.app.services.canonical_store_pg import (
    SupabaseCanonicalStore,
    _canonical_form,
    _row_to_canonical,
    resolve_and_link,
)


class _FakeResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    def __init__(self, results=None):
        self._queue = list(results or [])
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((str(sql), params))
        return self._queue.pop(0) if self._queue else _FakeResult()


def _person(**kw):
    base = dict(
        extracted_field_id=None, case_id="case-1",
        surname_main="DUPONT", surname_normalized="DUPONT",
        given_names_main="Marc", given_names_normalized="MARC",
        dob_iso="1985-03-15", nationality_iso3="FRA", passport_mrz_doc_number=None,
    )
    base.update(kw)
    return ExtractedPerson(**base)


# ── helpers ────────────────────────────────────────────────────────────────────


def test_canonical_form_roundtrips_through_row_to_canonical():
    p = _person(passport_mrz_doc_number="AB123")
    form = _canonical_form(p, doc_numbers=["AB123"])
    cp = _row_to_canonical("ce-1", form)
    assert isinstance(cp, CanonicalPerson)
    assert cp.case_id == "case-1"
    assert cp.surname_normalized == "DUPONT"
    assert cp.passport_doc_numbers == ("AB123",)


# ── store methods ────────────────────────────────────────────────────────────


def test_ann_search_empty_embedding_short_circuits():
    conn = _FakeConn()
    assert SupabaseCanonicalStore(conn).ann_search("case-1", [], 5) == []
    assert conn.calls == []  # no DB hit when there's no embedding


def test_ann_search_maps_rows_with_cosine():
    form = _canonical_form(_person(), doc_numbers=[])
    conn = _FakeConn([_FakeResult([
        {"canonical_entity_id": "ce-7", "canonical_form": form, "cosine_sim": 0.94},
    ])])
    hits = SupabaseCanonicalStore(conn).ann_search("case-1", [0.1] * 768, 5)
    assert len(hits) == 1
    assert hits[0].canonical_entity_id == "ce-7"
    assert hits[0].cosine_sim == 0.94
    # the query bound the vector literal + case id
    sql, params = conn.calls[-1]
    assert "embedding <=>" in sql
    assert params["cid"] == "case-1"
    assert params["q"].startswith("[")


def test_get_override_returns_none_without_sql():
    conn = _FakeConn()
    assert SupabaseCanonicalStore(conn).get_override("case-1", "sig") is None
    assert conn.calls == []  # no DB hit


def test_block_hits_maps_rows():
    form = _canonical_form(_person(), doc_numbers=[])
    conn = _FakeConn([_FakeResult([{"canonical_entity_id": "ce-9", "canonical_form": form}])])
    hits = SupabaseCanonicalStore(conn).block_hits("case-1", "DUPONT", "1985-03-15", "FRA")
    assert len(hits) == 1 and hits[0].canonical_entity_id == "ce-9"


def test_create_new_builds_canonical_and_inserts_form():
    conn = _FakeConn([_FakeResult()])  # INSERT
    cp = SupabaseCanonicalStore(conn).create_new(_person(passport_mrz_doc_number="X9"))
    assert cp.surname_normalized == "DUPONT"
    assert cp.passport_doc_numbers == ("X9",)
    # the INSERT bound a JSONB form carrying case_id + the doc number
    insert_params = conn.calls[-1][1]
    assert '"case_id": "case-1"' in insert_params["form"]
    assert "X9" in insert_params["form"]
    assert insert_params["emb"] is None  # v1: no embedding


# ── resolve_and_link wiring (resolver cascade → create_new → link) ─────────────

# resolve_and_link generates an embedding first (E-PIPE-5b). Stub it to None so the
# cascade stays deterministic and no OpenAI call is attempted (env-independent).
import backend.app.services.rce_entity_resolution_ai as _ai


def test_resolve_and_link_new_person_creates_and_links(monkeypatch):
    monkeypatch.setattr(_ai, "embed_person_768", lambda person: None)
    # No doc number, no embedding → resolver: get_override(no SQL) → block_hits(empty)
    # → (ANN skipped, embedding None) → create_new(INSERT). Then writes the link.
    conn = _FakeConn([
        _FakeResult([]),      # block_hits → no match
        _FakeResult(),        # create_new INSERT
        _FakeResult(),        # entity_links INSERT
    ])
    decision = resolve_and_link(_person(extracted_field_id="11111111-1111-1111-1111-111111111111"), conn=conn)
    assert decision.canonical_entity_id
    # an entity_links INSERT ran
    assert any("entity_links" in sql for sql, _ in conn.calls)
    link_params = conn.calls[-1][1]
    assert link_params["efid"] == "11111111-1111-1111-1111-111111111111"
    assert link_params["method"]  # DETERMINISTIC


def test_resolve_and_link_skips_link_without_extracted_field_id(monkeypatch):
    monkeypatch.setattr(_ai, "embed_person_768", lambda person: None)
    conn = _FakeConn([_FakeResult([]), _FakeResult()])  # block_hits empty, create_new
    resolve_and_link(_person(extracted_field_id=None), conn=conn)
    assert not any("entity_links" in sql for sql, _ in conn.calls)


def test_resolve_and_link_ann_high_gate_links_to_existing(monkeypatch):
    # Embedding present + an ANN hit >= 0.92 → resolver links to the existing
    # canonical (Stage 3 ANN_HIGH), no create_new.
    monkeypatch.setattr(_ai, "embed_person_768", lambda person: [0.2] * 768)
    form = _canonical_form(_person(), doc_numbers=[])
    conn = _FakeConn([
        _FakeResult([]),  # block_hits → no exact block match
        _FakeResult([{"canonical_entity_id": "ce-existing", "canonical_form": form, "cosine_sim": 0.97}]),  # ann_search
        _FakeResult(),    # entity_links INSERT
    ])
    decision = resolve_and_link(_person(extracted_field_id="22222222-2222-2222-2222-222222222222"), conn=conn)
    assert decision.canonical_entity_id == "ce-existing"
    # no create_new INSERT into canonical_entities
    assert not any("INSERT INTO rce.canonical_entities" in sql for sql, _ in conn.calls)
    link_params = conn.calls[-1][1]
    assert link_params["ceid"] == "ce-existing"
