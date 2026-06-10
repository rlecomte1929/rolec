"""Production ContradictionStore adapter (C2-09b).

Wires the pure C1-08/C2-09 contradiction detector
(``backend.relopass.agents.contradiction``) to the live ``rce.*`` schema so
``detect_contradictions`` runs against real extracted fields and writes
``rce.contradictions`` — the table the HR case-detail / resolve endpoints already
read. The detector itself does no DB I/O (the ``backend/relopass`` package forbids
SQLAlchemy/SDK imports); this adapter is the "one layer up" persistence the
detector's docstring defers to.

Access pattern matches the live rce.* readers (e.g. hr_case_detail.py): the
service-role ``db.engine`` + raw ``text()`` SQL. rce.* is service-role-only and
not PostgREST-exposed.

Schema mapping (verified against prod 2026-06-10):
  - rce.extracted_fields  → detector ExtractedField rows (joined to rce.documents
                            for the case scope; rce.entity_links for the canonical
                            entity of each field).
  - rce.documents.document_type_id → rce.document_types.code  (the agent's
                            document_type_code).
  - rce.family_members    → FamilyMemberRef (case-scoped relationship_type).
  - rce.canonical_entities (canonical_form, entity_type) → CanonicalPersonRef.
  - rce.contradictions     ← upsert target (Contradiction.type → contradiction_type).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from uuid import UUID

from sqlalchemy import text

from backend.relopass.agents.contradiction import (
    BirthCertParentClaim,
    Candidate,
    CanonicalPersonRef,
    Contradiction,
    FamilyContext,
    FamilyMemberRef,
    _synthetic_field_id,  # reused so the cache key matches the detector's keying
    detect_contradictions,
)
from backend.relopass.agents.models import ExtractedField

# ─────────────────────────────────────────────────────────────────────────────
# Pure mapping helpers (no DB — unit-tested directly)
# ─────────────────────────────────────────────────────────────────────────────


def _display_name(canonical_form: Optional[Mapping[str, Any]]) -> str:
    """Extract a comparable name from rce.canonical_entities.canonical_form (JSONB).

    canonical_form is a JSON object like {"display_name": "...", "normalized_surname":
    "...", "dob": "..."}, NOT a plain string. Mirrors policy_gap_detector_adapter's
    _display_name so the FamilyEntityResolver gets the same name form everywhere.
    """
    form = canonical_form if isinstance(canonical_form, Mapping) else {}
    name = form.get("display_name") or form.get("full_name")
    if name:
        return str(name)
    given = form.get("given_names")
    if isinstance(given, (list, tuple)):
        given = " ".join(str(g) for g in given)
    surname = form.get("normalized_surname") or form.get("surname")
    return " ".join(p for p in (given, surname) if p)


def _candidates_to_jsonb(candidates: Sequence[Candidate]) -> List[Dict[str, Any]]:
    """Serialise the detector's Candidate tuple into JSON-safe dicts matching the
    §3.6 candidate shape already parsed by hr_case_detail.py / hr_case_resolve.py.
    """
    out: List[Dict[str, Any]] = []
    for c in candidates:
        out.append(
            {
                "value": c.value,
                "document_id": str(c.document_id),
                "page": c.page,
                "bbox": list(c.bbox) if c.bbox is not None else None,
                "source_agent_run_id": str(c.source_agent_run_id)
                if c.source_agent_run_id is not None
                else None,
                "confidence": c.confidence,
                "document_type_code": c.document_type_code,
            }
        )
    return out


def _contradiction_params(c: Contradiction) -> Dict[str, Any]:
    """Bind params for the rce.contradictions INSERT. Maps the model field ``type``
    onto the ``contradiction_type`` column; serialises candidates / suggested_winner
    to JSON text (cast to jsonb in SQL). suggested_winner None → SQL NULL.
    """
    return {
        "contradiction_id": str(c.contradiction_id),
        "case_id": str(c.case_id),
        "canonical_entity_id": str(c.canonical_entity_id)
        if c.canonical_entity_id is not None
        else None,
        "field_key": c.field_key,
        "contradiction_type": c.type,
        "candidates": json.dumps(_candidates_to_jsonb(c.candidates)),
        "resolution_status": c.resolution_status,
        "suggested_winner": json.dumps(c.suggested_winner)
        if c.suggested_winner is not None
        else None,
        "content_hash": c.content_hash,
        "detected_at": c.detected_at,
        "detected_by": c.detected_by,
    }


_INSERT_SQL = text(
    """
    INSERT INTO rce.contradictions
      (contradiction_id, case_id, canonical_entity_id, field_key, contradiction_type,
       candidates, resolution_status, suggested_winner, content_hash, detected_at, detected_by)
    VALUES
      (CAST(:contradiction_id AS UUID), CAST(:case_id AS UUID),
       CAST(:canonical_entity_id AS UUID), :field_key, :contradiction_type,
       CAST(:candidates AS JSONB), :resolution_status,
       CAST(:suggested_winner AS JSONB), :content_hash, :detected_at, :detected_by)
    ON CONFLICT (case_id, canonical_entity_id, field_key, content_hash) DO NOTHING
    RETURNING contradiction_id
    """
)


# ─────────────────────────────────────────────────────────────────────────────
# Adapter
# ─────────────────────────────────────────────────────────────────────────────


class SupabaseContradictionStore:
    """ContradictionStore backed by the live rce.* schema.

    Construct with an open SQLAlchemy ``Connection`` (service-role engine). The
    detector calls ``list_extracted_fields_for_case`` first; that call also primes
    the synthetic-field-id → canonical-entity cache that
    ``get_canonical_entity_for_field`` reads.
    """

    def __init__(self, conn: Any) -> None:
        self._conn = conn
        # synthetic field id (matches detector keying) → canonical_entity_id
        self._entity_by_synthetic: Dict[UUID, Optional[UUID]] = {}

    # ---- reads --------------------------------------------------------------

    def list_extracted_fields_for_case(
        self, case_id: UUID
    ) -> Sequence[ExtractedField]:
        rows = self._conn.execute(
            text(
                """
                SELECT ef.extracted_field_id, ef.document_id, ef.field_key,
                       ef.value_raw, ef.value_canonical, ef.confidence,
                       ef.bbox_page, ef.bbox_x0, ef.bbox_y0, ef.bbox_x1, ef.bbox_y1,
                       ef.agent_run_id,
                       el.canonical_entity_id
                FROM rce.extracted_fields ef
                JOIN rce.documents d ON d.document_id = ef.document_id
                LEFT JOIN rce.entity_links el
                       ON el.extracted_field_id = ef.extracted_field_id
                WHERE d.case_id = CAST(:case_id AS UUID)
                """
            ),
            {"case_id": str(case_id)},
        ).mappings().all()

        fields: List[ExtractedField] = []
        for r in rows:
            ef = ExtractedField(
                document_id=r["document_id"],
                field_key=r["field_key"],
                value_raw=r["value_raw"],
                value_canonical=r["value_canonical"],
                # confidence is required + bounded; coerce a NULL to 0.0.
                confidence=r["confidence"] if r["confidence"] is not None else 0.0,
                bbox_page=r["bbox_page"],
                bbox_x0=r["bbox_x0"],
                bbox_y0=r["bbox_y0"],
                bbox_x1=r["bbox_x1"],
                bbox_y1=r["bbox_y1"],
                agent_run_id=r["agent_run_id"],
                resolution_status=None,  # detector does not consume this
            )
            fields.append(ef)
            self._entity_by_synthetic[_synthetic_field_id(ef)] = r["canonical_entity_id"]
        return tuple(fields)

    def get_document_type(self, document_id: UUID) -> Optional[str]:
        row = self._conn.execute(
            text(
                """
                SELECT dt.code
                FROM rce.documents d
                JOIN rce.document_types dt ON dt.document_type_id = d.document_type_id
                WHERE d.document_id = CAST(:document_id AS UUID)
                """
            ),
            {"document_id": str(document_id)},
        ).scalar()
        return row

    def get_canonical_entity_for_field(
        self, extracted_field_id: UUID
    ) -> Optional[UUID]:
        # extracted_field_id here is the detector's SYNTHETIC id; resolved via the
        # cache primed in list_extracted_fields_for_case.
        return self._entity_by_synthetic.get(extracted_field_id)

    def get_family_context(self, case_id: UUID) -> Optional[FamilyContext]:
        cid = {"case_id": str(case_id)}

        members = [
            FamilyMemberRef(
                canonical_entity_id=r["canonical_entity_id"],
                relationship_type=r["relationship_type"],
            )
            for r in self._conn.execute(
                text(
                    """
                    SELECT canonical_entity_id, relationship_type
                    FROM rce.family_members
                    WHERE case_id = CAST(:case_id AS UUID)
                      AND canonical_entity_id IS NOT NULL
                    """
                ),
                cid,
            ).mappings().all()
        ]

        # Case-scoped PERSON canonical entities: those linked to the case's docs,
        # UNION the family members' canonical entities (which may lack a doc link).
        persons = [
            CanonicalPersonRef(
                canonical_entity_id=r["canonical_entity_id"],
                display_name=_display_name(r["canonical_form"]),
                issuing_state_iso3=None,
            )
            for r in self._conn.execute(
                text(
                    """
                    SELECT DISTINCT ce.canonical_entity_id, ce.canonical_form
                    FROM rce.canonical_entities ce
                    WHERE ce.entity_type = 'PERSON'
                      AND ce.canonical_entity_id IN (
                        SELECT el.canonical_entity_id
                        FROM rce.entity_links el
                        JOIN rce.extracted_fields ef
                          ON ef.extracted_field_id = el.extracted_field_id
                        JOIN rce.documents d ON d.document_id = ef.document_id
                        WHERE d.case_id = CAST(:case_id AS UUID)
                        UNION
                        SELECT fm.canonical_entity_id
                        FROM rce.family_members fm
                        WHERE fm.case_id = CAST(:case_id AS UUID)
                          AND fm.canonical_entity_id IS NOT NULL
                      )
                    """
                ),
                cid,
            ).mappings().all()
        ]

        # BIRTH_CERT parent claims: parent_1/2 names + the child's canonical entity.
        claims = [
            BirthCertParentClaim(
                document_id=r["document_id"],
                parent_names=tuple(
                    n for n in (r["parent_1_name"], r["parent_2_name"]) if n
                ),
                child_entity_id=r["child_entity_id"],
            )
            for r in self._conn.execute(
                text(
                    """
                    SELECT d.document_id,
                           MAX(CASE WHEN ef.field_key = 'parent_1_name' THEN ef.value_raw END) AS parent_1_name,
                           MAX(CASE WHEN ef.field_key = 'parent_2_name' THEN ef.value_raw END) AS parent_2_name,
                           -- Postgres has no max(uuid); aggregate the child's canonical
                           -- entity id with array_agg + [1] instead (one child per birth cert).
                           (array_agg(el.canonical_entity_id) FILTER (
                              WHERE ef.field_key = 'child_name' AND el.canonical_entity_id IS NOT NULL
                            ))[1] AS child_entity_id
                    FROM rce.documents d
                    JOIN rce.document_types dt
                      ON dt.document_type_id = d.document_type_id AND dt.code = 'BIRTH_CERT'
                    JOIN rce.extracted_fields ef ON ef.document_id = d.document_id
                    LEFT JOIN rce.entity_links el ON el.extracted_field_id = ef.extracted_field_id
                    WHERE d.case_id = CAST(:case_id AS UUID)
                    GROUP BY d.document_id
                    """
                ),
                cid,
            ).mappings().all()
        ]

        # FOSTER_CARE_ORDER suppresses the parent check for the dependent child.
        foster_ids = {
            r["canonical_entity_id"]
            for r in self._conn.execute(
                text(
                    """
                    SELECT DISTINCT el.canonical_entity_id
                    FROM rce.documents d
                    JOIN rce.document_types dt
                      ON dt.document_type_id = d.document_type_id AND dt.code = 'FOSTER_CARE_ORDER'
                    JOIN rce.extracted_fields ef
                      ON ef.document_id = d.document_id AND ef.field_key = 'dependent_name'
                    JOIN rce.entity_links el ON el.extracted_field_id = ef.extracted_field_id
                    WHERE d.case_id = CAST(:case_id AS UUID)
                      AND el.canonical_entity_id IS NOT NULL
                    """
                ),
                cid,
            ).mappings().all()
        }

        if not (members or claims):
            return None  # no family scope → detector skips the family pass
        return FamilyContext(
            members=tuple(members),
            canonical_persons=tuple(persons),
            birth_cert_claims=tuple(claims),
            foster_suppressed_child_ids=frozenset(foster_ids),
        )

    # ---- write --------------------------------------------------------------

    def upsert_contradictions(
        self, contradictions: Any
    ) -> Tuple[int, int]:
        items = list(contradictions)
        inserted = 0
        for c in items:
            result = self._conn.execute(_INSERT_SQL, _contradiction_params(c))
            if result.first() is not None:
                inserted += 1
        return inserted, len(items) - inserted


def run_contradiction_detection_for_case(
    case_id: UUID, *, engine: Any = None
) -> Tuple[Contradiction, ...]:
    """Run the detector against a real case and persist to rce.contradictions.

    Opens a single transaction (commit on success) so the reads + upsert are
    consistent. Returns the contradictions detected this run.
    """
    if engine is None:
        from backend.database import db  # lazy: avoid engine construction at import

        engine = db.engine
    with engine.begin() as conn:
        store = SupabaseContradictionStore(conn)
        return detect_contradictions(case_id, store)
