"""
PolicyContextGraphService — idempotent company ↔ active snapshot ↔ document binding.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from ..database import Database
from .case_context_service import CaseContextError, CaseContextService
from .policy_assistant_case_context_service import (
    get_policy_facts_for_case as fetch_policy_facts_for_case,
    get_source_chunks_for_fact_ids as fetch_source_chunks_for_fact_ids,
)


class PolicyContextGraphService:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get_active_policy_snapshot_for_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        return self._db.get_active_policy_knowledge_snapshot_for_company(company_id)

    def sync_policy_document_graph(
        self,
        company_id: str,
        policy_document_id: str,
        snapshot_id: str,
    ) -> None:
        """Idempotent: bind company to active snapshot + source document."""
        self._db.upsert_company_policy_assistant_binding(
            company_id,
            active_snapshot_id=snapshot_id,
            policy_document_id=policy_document_id,
        )

    def sync_snapshot_graph(self, company_id: str, snapshot_id: str, policy_document_id: str) -> None:
        """Alias for sync_policy_document_graph (explicit snapshot-centric naming)."""
        self.sync_policy_document_graph(company_id, policy_document_id, snapshot_id)

    def bind_company_to_active_policy_snapshot(
        self,
        company_id: str,
        snapshot_id: str,
        policy_document_id: str,
    ) -> None:
        self.sync_policy_document_graph(company_id, policy_document_id, snapshot_id)

    def get_case_policy_context(self, case_id: str) -> Dict[str, Any]:
        try:
            with self._db.engine.connect() as conn:
                return CaseContextService().fetch(conn, case_id)
        except CaseContextError as exc:
            return {"meta": {"ok": False, "error": {"code": exc.code, "message": exc.message}}}

    def get_policy_facts_for_case(
        self,
        case_id: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        fts: Optional[Set[str]] = None
        if filters and filters.get("fact_types"):
            fts = {str(x) for x in (filters.get("fact_types") or [])}
        return fetch_policy_facts_for_case(self._db, case_id, fact_types=fts)

    def get_source_chunks_for_fact_ids(self, fact_ids: List[str]) -> List[Dict[str, Any]]:
        return fetch_source_chunks_for_fact_ids(self._db, fact_ids)
