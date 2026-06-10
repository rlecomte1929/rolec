"""E-PIPE-5 · Production CanonicalStore + entity-link writer (full 5-stage resolver).

Implements the C1-07 ``CanonicalStore`` Protocol
(:mod:`backend.relopass.agents.entity_resolution`) over the live ``rce.*`` schema so
extracted persons resolve to canonical PERSON entities and ``rce.entity_links`` rows
get written — the data the C2-09 nationality / child-parent checks join on.

Stages: 1 MRZ doc-number, 2 surname/dob/nationality block, **3 pgvector cosine ANN**
(E-PIPE-5b), **4 LLM fuzzy-match** (E-PIPE-5b, cosine band 0.80–0.92), 5 create-new.
The fuzzy stages (3–4) catch name typos / ICAO transliteration variants so one person
isn't duplicated across documents; they **degrade to deterministic-only when
``OPENAI_API_KEY`` is unset** (no embedding → ANN/LLM skipped — see
``rce_entity_resolution_ai``). No migration: pgvector + the nullable ``vector(768)``
embedding column already exist on prod.

Case-scoping: ``rce.canonical_entities`` has no ``case_id`` column, so the case is
stored inside ``canonical_form`` (JSONB) and filtered there — matching
``CanonicalPerson.case_id``. Access is the service-role ``db.engine`` + ``text()``
(rce.* is service-role-only), mirroring contradiction_store_pg.py.
"""

from __future__ import annotations

import json
import logging
from typing import Any, List, Optional, Sequence
from uuid import uuid4

from sqlalchemy import text

from backend.relopass.agents.entity_resolution import (
    AnnHit,
    CanonicalPerson,
    ExtractedPerson,
    LinkDecision,
    resolve_person_entity,
)

log = logging.getLogger(__name__)


def _canonical_form(p: "ExtractedPerson | CanonicalPerson", *, doc_numbers: Sequence[str]) -> dict:
    return {
        "case_id": p.case_id,
        "surname_main": p.surname_main,
        "given_names_main": p.given_names_main,
        "surname_normalized": p.surname_normalized,
        "given_names_normalized": p.given_names_normalized,
        "dob_iso": p.dob_iso,
        "nationality_iso3": p.nationality_iso3,
        "passport_doc_numbers": list(doc_numbers),
    }


def _row_to_canonical(canonical_entity_id: Any, form: dict) -> CanonicalPerson:
    return CanonicalPerson(
        canonical_entity_id=str(canonical_entity_id),
        case_id=form.get("case_id", ""),
        surname_main=form.get("surname_main", ""),
        given_names_main=form.get("given_names_main"),
        surname_normalized=form.get("surname_normalized", ""),
        given_names_normalized=form.get("given_names_normalized"),
        dob_iso=form.get("dob_iso"),
        nationality_iso3=form.get("nationality_iso3"),
        passport_doc_numbers=tuple(form.get("passport_doc_numbers") or ()),
    )


class SupabaseCanonicalStore:
    """CanonicalStore backed by rce.canonical_entities + rce.entity_links.

    Construct with an open SQLAlchemy Connection (service-role engine).
    """

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    # ── Stage 1: exact MRZ doc-number ────────────────────────────────────────
    def get_by_doc_number(self, case_id: str, doc_number: str) -> Optional[CanonicalPerson]:
        row = self._conn.execute(
            text(
                """
                SELECT canonical_entity_id, canonical_form
                FROM rce.canonical_entities
                WHERE entity_type = 'PERSON'
                  AND canonical_form->>'case_id' = :cid
                  AND canonical_form->'passport_doc_numbers' @> to_jsonb(:doc::text)
                LIMIT 1
                """
            ),
            {"cid": case_id, "doc": doc_number},
        ).mappings().first()
        return _row_to_canonical(row["canonical_entity_id"], row["canonical_form"]) if row else None

    # ── Stage 2: surname/dob/nationality block ───────────────────────────────
    def block_hits(
        self, case_id: str, surname_normalized: str,
        dob_iso: Optional[str], nationality_iso3: Optional[str],
    ) -> List[CanonicalPerson]:
        rows = self._conn.execute(
            text(
                """
                SELECT canonical_entity_id, canonical_form
                FROM rce.canonical_entities
                WHERE entity_type = 'PERSON'
                  AND canonical_form->>'case_id' = :cid
                  AND lower(canonical_form->>'surname_normalized') = lower(:surname)
                  -- dob/nationality match when both sides present (mirror InMemory store)
                  AND (:dob IS NULL OR canonical_form->>'dob_iso' IS NULL OR canonical_form->>'dob_iso' = :dob)
                  AND (:nat IS NULL OR canonical_form->>'nationality_iso3' IS NULL OR canonical_form->>'nationality_iso3' = :nat)
                """
            ),
            {"cid": case_id, "surname": surname_normalized, "dob": dob_iso, "nat": nationality_iso3},
        ).mappings().all()
        return [_row_to_canonical(r["canonical_entity_id"], r["canonical_form"]) for r in rows]

    # ── Stage 3: pgvector cosine ANN (E-PIPE-5b) ─────────────────────────────
    def ann_search(self, case_id: str, embedding: Sequence[float], top_k: int) -> List[AnnHit]:
        if not embedding:
            return []
        q = "[" + ",".join(str(float(x)) for x in embedding) + "]"
        rows = self._conn.execute(
            text(
                """
                SELECT canonical_entity_id, canonical_form,
                       1 - (embedding <=> CAST(:q AS vector)) AS cosine_sim
                FROM rce.canonical_entities
                WHERE entity_type = 'PERSON'
                  AND canonical_form->>'case_id' = :cid
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:q AS vector)
                LIMIT :k
                """
            ),
            {"q": q, "cid": case_id, "k": top_k},
        ).mappings().all()
        return [
            AnnHit(
                canonical_entity_id=str(r["canonical_entity_id"]),
                cosine_sim=float(r["cosine_sim"]),
                canonical=_row_to_canonical(r["canonical_entity_id"], r["canonical_form"]),
            )
            for r in rows
        ]

    # ── Human override — DEFERRED (rce.corrections wiring) ───────────────────
    def get_override(self, case_id: str, candidate_signature: str) -> Optional[CanonicalPerson]:
        return None

    # ── Stage 5: create a fresh canonical PERSON ─────────────────────────────
    def create_new(self, candidate: ExtractedPerson) -> CanonicalPerson:
        cid = str(uuid4())
        doc_numbers = [candidate.passport_mrz_doc_number] if candidate.passport_mrz_doc_number else []
        form = _canonical_form(candidate, doc_numbers=doc_numbers)
        embedding_param = (
            "[" + ",".join(str(float(x)) for x in candidate.embedding) + "]"
            if candidate.embedding else None
        )
        self._conn.execute(
            text(
                """
                INSERT INTO rce.canonical_entities (canonical_entity_id, entity_type, canonical_form, embedding)
                VALUES (CAST(:id AS UUID), 'PERSON', CAST(:form AS JSONB), CAST(:emb AS vector))
                """
            ),
            {"id": cid, "form": json.dumps(form), "emb": embedding_param},
        )
        return _row_to_canonical(cid, form)


def resolve_and_link(candidate: ExtractedPerson, *, conn: Any) -> LinkDecision:
    """Resolve one extracted person to a canonical PERSON (full 5-stage cascade)
    and persist the rce.entity_links row. Returns the LinkDecision.

    Generates the candidate's 768-dim identity embedding first (E-PIPE-5b) so the
    pgvector ANN + LLM fuzzy stages can run; when OPENAI_API_KEY is unset the
    embedding is None and the cascade stays deterministic. Idempotent on
    (extracted_field_id, canonical_entity_id) when an extracted_field_id is present.
    """
    from .rce_entity_resolution_ai import OpenAILLMResolver, embed_person_768

    if candidate.embedding is None:
        embedding = embed_person_768(candidate)
        if embedding is not None:
            candidate = candidate.model_copy(update={"embedding": embedding})

    store = SupabaseCanonicalStore(conn)
    decision = resolve_person_entity(candidate, store=store, llm=OpenAILLMResolver())

    if candidate.extracted_field_id:
        conn.execute(
            text(
                """
                INSERT INTO rce.entity_links
                  (entity_link_id, extracted_field_id, canonical_entity_id, link_method, confidence)
                VALUES (gen_random_uuid(), CAST(:efid AS UUID), CAST(:ceid AS UUID), :method, :conf)
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "efid": candidate.extracted_field_id,
                "ceid": decision.canonical_entity_id,
                "method": decision.link_method.value,
                "conf": decision.confidence,
            },
        )
    return decision
