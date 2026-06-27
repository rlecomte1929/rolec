"""E-PIPE-1 · rce.documents ingest (bridge from case-document upload).

Creates ``rce.documents`` rows so the rce extraction pipeline has documents to
process. The immigration-intake upload (``document_upload_service``) writes
``public.immigration_documents``; this bridges that into the rce case engine.

Design notes:
- ``rce.documents.case_id`` is a FK to ``rce.cases``; ``immigration_documents.case_id``
  is NOT FK'd to it. So the bridge only ingests when the case actually exists in
  ``rce.cases`` (otherwise the insert would FK-fail). Pre-launch, most uploads will
  skip until the rce.cases bridge populates cases — that's expected and logged.
- ``document_type_id`` is nullable: an unclassifiable document is ingested with a
  NULL type rather than dropped.
- Idempotent on ``(case_id, sha256)`` via the unique index from
  20260610130000; INSERT ... ON CONFLICT DO NOTHING.
- Access via the service-role ``db.engine`` + ``text()`` (rce.* is service-role-only),
  matching contradiction_store_pg.py.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import text

log = logging.getLogger(__name__)


def _as_uuid_or_none(value: Any) -> Optional[str]:
    """Coerce a value to a UUID string, or None. rce.documents.uploaded_by is a
    UUID column, but legacy user ids can be non-UUID text — store NULL rather
    than fail the insert on those."""
    if not value:
        return None
    try:
        return str(UUID(str(value)))
    except ValueError:
        return None


# Map a filename to an rce.document_types code. Coarse keyword heuristic (the
# C1-05 ML classifier isn't wired yet); returns None when nothing matches, which
# the ingest stores as a NULL document_type_id.
def classify_rce_document_type(file_name: Optional[str]) -> Optional[str]:
    name = (file_name or "").lower()
    # Order matters: check the more specific tokens first.
    if "passport" in name:
        return "PASSPORT_TD3"
    if "id_card" in name or "id-card" in name or "idcard" in name or "national_id" in name:
        return "ID_CARD"
    if "marriage" in name or "mariage" in name or "eheurkunde" in name or "vigsel" in name:
        return "MARRIAGE_CERT"
    if "birth" in name or "naissance" in name or "geburt" in name or "fodsel" in name or "fødsel" in name:
        return "BIRTH_CERT"
    if "foster" in name or "guardian" in name or "kafala" in name or "custody" in name:
        return "FOSTER_CARE_ORDER"
    if "diploma" in name or "degree" in name or "diplom" in name:
        return "DIPLOMA"
    if "tax" in name or "avis" in name or "lohnsteuer" in name or "skatte" in name:
        return "TAX_CERT"
    if (
        "visa" in name
        or "permit" in name
        or "titre_de_sejour" in name
        or "titre-de-sejour" in name
        or "aufenthalt" in name
        or "oppholdstillatelse" in name
        or "brp" in name
    ):
        return "VISA_PERMIT"
    return None


def _document_type_id(conn: Any, code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    return conn.execute(
        text("SELECT document_type_id FROM rce.document_types WHERE code = :code"),
        {"code": code},
    ).scalar()


def _case_exists(conn: Any, case_id: str) -> bool:
    return (
        conn.execute(
            text("SELECT 1 FROM rce.cases WHERE case_id = CAST(:cid AS UUID)"),
            {"cid": case_id},
        ).first()
        is not None
    )


def ingest_rce_document(
    conn: Any,
    *,
    case_id: str,
    sha256: str,
    document_type_code: Optional[str],
    mime_type: Optional[str] = None,
    storage_uri: Optional[str] = None,
    original_filename: Optional[str] = None,
    uploaded_by: Optional[str] = None,
) -> Optional[str]:
    """Insert one rce.documents row (idempotent on (case_id, sha256)).

    Returns the document_id (existing or new), or None if the row already existed
    (ON CONFLICT) — callers that need the id can re-select. Caller supplies an open
    Connection so this can run inside a transaction.
    """
    document_type_id = _document_type_id(conn, document_type_code)
    row = conn.execute(
        text(
            """
            INSERT INTO rce.documents
              (case_id, sha256, document_type_id, mime_type, storage_uri,
               original_filename, uploaded_by)
            VALUES
              (CAST(:case_id AS UUID), :sha256, CAST(:doc_type_id AS UUID), :mime_type,
               :storage_uri, :original_filename, CAST(:uploaded_by AS UUID))
            ON CONFLICT (case_id, sha256) DO NOTHING
            RETURNING document_id
            """
        ),
        {
            "case_id": case_id,
            "sha256": sha256,
            "doc_type_id": document_type_id,
            "mime_type": mime_type,
            "storage_uri": storage_uri,
            "original_filename": original_filename,
            "uploaded_by": _as_uuid_or_none(uploaded_by),
        },
    ).first()
    return str(row[0]) if row else None


def bridge_case_document_to_rce(
    *,
    case_id: str,
    content: bytes,
    mime_type: Optional[str] = None,
    storage_uri: Optional[str] = None,
    original_filename: Optional[str] = None,
    uploaded_by: Optional[str] = None,
    engine: Any = None,
) -> Optional[str]:
    """Best-effort bridge of an uploaded case document into rce.documents.

    Fail-soft: any error (case not in rce.cases, FK, DB) is swallowed + logged so
    this never breaks the upload path. Returns the rce document_id when ingested,
    else None (skipped or already present).
    """
    try:
        if engine is None:
            from backend.database import db  # lazy: avoid engine import at module load

            engine = db.engine
        sha256 = hashlib.sha256(content).hexdigest()
        doc_type = classify_rce_document_type(original_filename)
        with engine.begin() as conn:
            if not _case_exists(conn, case_id):
                log.info(
                    "rce bridge skipped: case_id=%s not in rce.cases (pre-launch / not bridged)",
                    case_id,
                )
                return None
            doc_id = ingest_rce_document(
                conn,
                case_id=case_id,
                sha256=sha256,
                document_type_code=doc_type,
                mime_type=mime_type,
                storage_uri=storage_uri,
                original_filename=original_filename,
                uploaded_by=uploaded_by,
            )
        log.info(
            "rce bridge: case_id=%s rce_document_id=%s type=%s", case_id, doc_id, doc_type
        )
        return doc_id
    except Exception as e:  # never break the upload
        log.warning("rce bridge failed-soft for case_id=%s: %s", case_id, e)
        return None
