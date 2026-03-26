"""
PolicyKnowledgeSnapshotService — snapshots + activation for assistant read model.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..database import Database


class PolicyKnowledgeSnapshotService:
    def __init__(self, db: Database) -> None:
        self._db = db

    def attach_facts_to_snapshot(self, snapshot_id: str, facts: List[Dict[str, Any]]) -> None:
        """Insert extracted facts for an existing candidate snapshot."""
        for f in facts:
            self._db.insert_policy_fact(
                snapshot_id,
                str(f["fact_type"]),
                str(f.get("category") or ""),
                subcategory=f.get("subcategory"),
                normalized_value_json=f.get("normalized_value_json"),
                applicability_json=f.get("applicability_json"),
                ambiguity_flag=bool(f.get("ambiguity_flag")),
                confidence_score=f.get("confidence_score"),
                source_chunk_id=str(f["source_chunk_id"]),
                source_page=f.get("source_page"),
                source_section=f.get("source_section"),
                source_quote=f.get("source_quote"),
            )

    def create_snapshot_from_document(
        self,
        company_id: str,
        policy_document_id: str,
        facts: List[Dict[str, Any]],
        *,
        version_label: Optional[str] = None,
        extraction_method: str = "deterministic_v1",
        activate: bool = True,
        revision_number: int = 1,
        parent_snapshot_id: Optional[str] = None,
        activated_by_user_id: Optional[str] = None,
    ) -> str:
        """
        Legacy path: create snapshot row + facts; activate when requested (tests / callers).
        Prefer pipeline orchestration for production (append-only revisions).
        """
        snapshot_id = self._db.insert_policy_knowledge_snapshot(
            company_id,
            policy_document_id,
            version_label=version_label,
            status="failed",
            extraction_method=extraction_method,
            revision_number=revision_number,
            parent_snapshot_id=parent_snapshot_id,
            activation_state="candidate",
        )
        self.attach_facts_to_snapshot(snapshot_id, facts)
        if activate:
            uid = activated_by_user_id or "system"
            self._db.activate_policy_knowledge_snapshot(snapshot_id, company_id, policy_document_id, uid)
        else:
            self._db.mark_policy_snapshot_failed(snapshot_id)
        return snapshot_id
