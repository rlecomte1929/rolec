"""E-PIPE-6 · Async pipeline worker — chains the rce extraction stages + detection.

For one ingested rce.documents row, runs the full chain end-to-end and triggers
contradiction detection for the case:

  rce.documents (E-PIPE-1)  →  OCR→ParsedDocument (E-PIPE-2)
    →  extract → rce.extracted_fields (E-PIPE-4)
    →  resolve persons → rce.canonical_entities/entity_links (E-PIPE-5)
    →  run_contradiction_detection_for_case → rce.contradictions (C2-09b)

Mirrors document_extraction_queue's detached contract: **fail-soft, never raises** —
each stage is isolated so a bad document can't break the upload or the rest of the
pipeline. Returns a PipelineResult describing what happened (no status column exists
on rce.documents; status is logged + returned, not persisted).

Stage functions are module-level so the orchestration is unit-testable by monkeypatch
without a DB / OCR / LLM.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field as dc_field
from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy import text

from backend.relopass.agents.entity_resolution import ExtractedPerson

from .rce_ocr_parser import parse_stored_document
from .rce_extraction_orchestrator import run_extraction_for_document
from .canonical_store_pg import resolve_and_link
from .contradiction_store_pg import run_contradiction_detection_for_case

log = logging.getLogger(__name__)

# Person identity field_keys an extraction agent emits (passport/id_card MRZ + family).
_PERSON_FIELD_KEYS = ("surname", "given_names", "nationality_iso3",
                      "date_of_birth", "dob", "document_number")


@dataclass
class PipelineResult:
    rce_document_id: str
    case_id: Optional[str]
    ocr_ok: bool
    extraction_status: str
    persons_resolved: int
    contradictions_detected: int
    errors: List[str] = dc_field(default_factory=list)


def _engine():
    from backend.database import db

    return db.engine


def _load_rce_document(engine: Any, rce_document_id: str) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT d.document_id, d.case_id, d.mime_type, d.storage_uri,
                       d.original_filename, dt.code AS document_type_code
                FROM rce.documents d
                LEFT JOIN rce.document_types dt ON dt.document_type_id = d.document_type_id
                WHERE d.document_id = CAST(:id AS UUID)
                """
            ),
            {"id": rce_document_id},
        ).mappings().first()
    return dict(row) if row else None


def resolve_case_persons(case_id: str, *, engine: Any) -> int:
    """Best-effort: turn the case's extracted person-identity fields into
    ExtractedPersons (one per document that has a surname) and resolve+link each
    (E-PIPE-5). Returns the number resolved. Fail-soft per person.
    """
    from backend.relopass.normalize import normalize_name

    resolved = 0
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT ef.document_id,
                       MAX(ef.value_raw) FILTER (WHERE ef.field_key='surname') AS surname,
                       MAX(ef.value_raw) FILTER (WHERE ef.field_key='given_names') AS given_names,
                       MAX(ef.value_raw) FILTER (WHERE ef.field_key='nationality_iso3') AS nationality_iso3,
                       MAX(ef.value_raw) FILTER (WHERE ef.field_key IN ('date_of_birth','dob')) AS dob,
                       MAX(ef.value_raw) FILTER (WHERE ef.field_key='document_number') AS doc_number,
                       (array_agg(ef.extracted_field_id) FILTER (WHERE ef.field_key='surname'))[1] AS surname_field_id
                FROM rce.extracted_fields ef
                JOIN rce.documents d ON d.document_id = ef.document_id
                WHERE d.case_id = CAST(:cid AS UUID)
                  AND ef.field_key = ANY(:keys)
                GROUP BY ef.document_id
                HAVING MAX(ef.value_raw) FILTER (WHERE ef.field_key='surname') IS NOT NULL
                """
            ),
            {"cid": case_id, "keys": list(_PERSON_FIELD_KEYS)},
        ).mappings().all()

        for r in rows:
            try:
                norm = normalize_name(r["surname"], None)
                person = ExtractedPerson(
                    extracted_field_id=str(r["surname_field_id"]) if r["surname_field_id"] else None,
                    case_id=case_id,
                    surname_main=r["surname"],
                    surname_normalized=getattr(norm, "surname_main", None) or r["surname"],
                    given_names_main=r["given_names"],
                    given_names_normalized=(r["given_names"] or "").upper() or None,
                    dob_iso=r["dob"],
                    nationality_iso3=r["nationality_iso3"],
                    passport_mrz_doc_number=r["doc_number"],
                )
                resolve_and_link(person, conn=conn)
                resolved += 1
            except Exception as exc:  # one bad person doesn't sink the rest
                log.warning("resolve_case_persons: skip doc=%s: %s", r.get("document_id"), exc)
    return resolved


async def process_rce_document(rce_document_id: str, *, engine: Any = None) -> PipelineResult:
    """Run the full rce extraction pipeline for one document + trigger detection.
    Fail-soft: each stage is isolated; never raises."""
    eng = engine or _engine()
    errors: List[str] = []

    doc = _load_rce_document(eng, rce_document_id)
    if not doc:
        return PipelineResult(rce_document_id, None, False, "no_document", 0, 0, ["document not found"])
    case_id = str(doc["case_id"])
    code = doc.get("document_type_code")

    # 1. OCR → ParsedDocument (E-PIPE-2)
    ocr = None
    try:
        ocr = await parse_stored_document(
            document_id=UUID(rce_document_id), case_id=UUID(case_id),
            storage_path=doc["storage_uri"], mime_type=doc["mime_type"],
            document_type=code, file_name=doc.get("original_filename"),
        )
    except Exception as exc:
        errors.append(f"ocr:{exc}")
    ocr_ok = bool(ocr and getattr(ocr, "ok", False))

    # 2. Extract → rce.extracted_fields (E-PIPE-4)
    #
    # [AIQ-2121] `code` (rce.documents.document_type_id) was the ONLY gate, so a document
    # that arrived without a stored type skipped extraction entirely even after a clean OCR
    # — and the filename classifier that would have supplied one maps to no runtime code at
    # all, so nothing ever filled the gap. Fall back to the type the OCR step derived by
    # READING the document.
    #
    # The stored code still wins: it is a stated fact, the derived one is an inference.
    # `run_extraction_for_document` wants the RUNTIME code, which is exactly what
    # `ocr.runtime_code` carries (mapped through CLASSIFIER_TO_RUNTIME) — never the raw
    # classifier code.
    extraction_status = "skipped_no_ocr"
    derived_code = getattr(ocr, "runtime_code", None) if ocr is not None else None
    effective_code = code or derived_code
    if ocr is not None and effective_code:
        try:
            outcome = await run_extraction_for_document(
                ocr_result=ocr, document_type_code=effective_code, engine=eng
            )
            extraction_status = outcome.status
            if not code:
                log.info(
                    "rce_pipeline doc=%s extracted on a CONTENT-DERIVED type=%s "
                    "(no stored document_type_id)", rce_document_id, effective_code,
                )
        except Exception as exc:
            extraction_status = "failed"
            errors.append(f"extract:{exc}")

    # 3. Resolve persons → rce.canonical_entities/entity_links (E-PIPE-5)
    persons = 0
    try:
        persons = resolve_case_persons(case_id, engine=eng)
    except Exception as exc:
        errors.append(f"resolve:{exc}")

    # 4. Contradiction detection → rce.contradictions (C2-09b)
    detected = 0
    try:
        contradictions = run_contradiction_detection_for_case(UUID(case_id), engine=eng)
        detected = len(contradictions)
    except Exception as exc:
        errors.append(f"detect:{exc}")

    log.info(
        "rce_pipeline doc=%s case=%s ocr_ok=%s extract=%s persons=%d contradictions=%d errors=%d",
        rce_document_id, case_id, ocr_ok, extraction_status, persons, detected, len(errors),
    )
    return PipelineResult(rce_document_id, case_id, ocr_ok, extraction_status, persons, detected, errors)
