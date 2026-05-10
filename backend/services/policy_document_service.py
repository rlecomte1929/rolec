"""
PolicyDocumentService — CRUD helpers for policy_documents rows (assistant import pipeline).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from ..database import Database


class PolicyDocumentService:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get_document(self, document_id: str, request_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return self._db.get_policy_document(document_id, request_id=request_id)

    def mark_status(
        self,
        document_id: str,
        assistant_import_status: str,
        *,
        extraction_error: Optional[str] = None,
        processed_at: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        self._db.update_policy_document(
            document_id,
            assistant_import_status=assistant_import_status,
            extraction_error=extraction_error,
            processed_at=processed_at,
            request_id=request_id,
        )
