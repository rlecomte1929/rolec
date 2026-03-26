"""
Orchestrates assistant import: lock → text → candidate snapshot → chunks → facts → activate (append-only).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from ..database import Database
from .audit_log_service import ACTOR_HUMAN, insert_audit_log
from .policy_context_graph_service import PolicyContextGraphService
from .policy_fact_extraction_service import extract_minimal_policy_facts
from .policy_knowledge_snapshot_service import PolicyKnowledgeSnapshotService
from .policy_storage_paths import BUCKET_HR_POLICIES, normalize_policy_storage_object_key
from .policy_text_extraction_service import PolicyTextExtractionService, build_chunks
from .supabase_client import get_supabase_admin_client

log = logging.getLogger(__name__)


def run_policy_assistant_import_pipeline(
    db: Database,
    doc_id: str,
    *,
    file_bytes: Optional[bytes] = None,
    mime_type: Optional[str] = None,
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Synchronous full pipeline. Append-only: new snapshot revision + chunks per run; failed runs do not
    replace the active snapshot. Requires user_id for lock + activation audit when hardening tables exist.
    """
    if not db.policy_assistant_tables_available():
        return {
            "ok": False,
            "error_code": "policy_assistant_tables_missing",
            "message": "Policy assistant import tables are not available. Apply database migrations.",
        }

    doc = db.get_policy_document(doc_id, request_id=request_id)
    if not doc:
        return {"ok": False, "error_code": "document_not_found", "message": "Document not found"}

    company_id = str(doc.get("company_id") or "")
    mt = mime_type or str(doc.get("mime_type") or "")
    uid = str(user_id or "").strip() or "unknown"
    lock_token: Optional[str] = None
    snapshot_id: Optional[str] = None

    try:
        if db.policy_hardening_tables_available():
            lock_token = db.try_acquire_policy_extraction_lock(doc_id, company_id, uid)
            if lock_token is None:
                return {
                    "ok": False,
                    "error_code": "extraction_lock_conflict",
                    "message": "Another extraction is in progress for this document. Retry shortly.",
                    "http_status": 409,
                }
            try:
                with db.engine.begin() as conn:
                    insert_audit_log(
                        conn,
                        entity_type="policy_extraction_lock",
                        entity_id=doc_id,
                        action_type="lock_acquired",
                        new_value={"company_id": company_id, "user_id": uid},
                        actor_type=ACTOR_HUMAN,
                        actor_id=uid,
                    )
            except Exception:
                pass

        db.update_policy_document(
            doc_id,
            assistant_import_status="extracting_text",
            processed_at=None,
            extraction_error=None,
            request_id=request_id,
        )

        data = file_bytes
        if data is None:
            path = doc.get("storage_path") or ""
            key = normalize_policy_storage_object_key(path)
            if not key:
                raise RuntimeError("missing_storage_path")
            supabase = get_supabase_admin_client()
            data = supabase.storage.from_(BUCKET_HR_POLICIES).download(key)

        text_ex = PolicyTextExtractionService()
        full_text, terr = text_ex.extract_text_from_document(data, mt)
        if terr or not full_text.strip():
            err_out = terr or "empty_text"
            db.update_policy_document(
                doc_id,
                assistant_import_status="failed",
                extraction_error=err_out,
                processed_at=datetime.utcnow().isoformat(),
                request_id=request_id,
            )
            return {"ok": False, "error_code": "text_extraction_failed", "message": err_out or "empty_text"}

        db.update_policy_document(doc_id, raw_text=full_text, assistant_import_status="text_ready", request_id=request_id)

        prev_snap = db.get_latest_policy_knowledge_snapshot_for_document(doc_id)
        parent_id = str(prev_snap["id"]) if prev_snap else None
        revision = db.next_snapshot_revision_number(doc_id)

        snapshot_id = db.insert_policy_knowledge_snapshot(
            company_id,
            doc_id,
            version_label=str(doc.get("version_label") or "") or None,
            status="failed",
            extraction_method="deterministic_v1",
            revision_number=revision,
            parent_snapshot_id=parent_id,
            activation_state="candidate",
        )

        chunk_defs = build_chunks(full_text)
        chunk_rows: list[dict[str, Any]] = []
        for c in chunk_defs:
            cid = db.insert_policy_document_chunk(
                doc_id,
                int(c["chunk_index"]),
                str(c["text_content"]),
                page_number=c.get("page_number"),
                section_title=c.get("section_title"),
                token_count=max(1, len(str(c["text_content"])) // 4),
                metadata_json=c.get("metadata_json"),
                snapshot_id=snapshot_id,
            )
            chunk_rows.append(
                {
                    "id": cid,
                    "chunk_index": c["chunk_index"],
                    "text_content": c["text_content"],
                    "section_title": c.get("section_title"),
                    "page_number": c.get("page_number"),
                }
            )

        db.update_policy_document(doc_id, assistant_import_status="extracting_facts", request_id=request_id)

        run_text = db.insert_policy_processing_run(doc_id, "text_extraction", status="running")
        db.finish_policy_processing_run(
            run_text,
            "completed",
            metrics_json={"chunks": len(chunk_rows), "snapshot_id": snapshot_id},
        )

        facts = extract_minimal_policy_facts(chunk_rows)
        run_facts = db.insert_policy_processing_run(doc_id, "fact_extraction", status="running")
        db.finish_policy_processing_run(
            run_facts,
            "completed",
            metrics_json={"facts": len(facts), "snapshot_id": snapshot_id},
        )

        snap_svc = PolicyKnowledgeSnapshotService(db)
        snap_svc.attach_facts_to_snapshot(snapshot_id, facts)

        run_graph = db.insert_policy_processing_run(doc_id, "graph_sync", status="running")
        db.activate_policy_knowledge_snapshot(snapshot_id, company_id, doc_id, uid)
        graph = PolicyContextGraphService(db)
        graph.sync_policy_document_graph(company_id, doc_id, snapshot_id)
        db.finish_policy_processing_run(
            run_graph,
            "completed",
            metrics_json={"snapshot_id": snapshot_id},
        )

        db.update_policy_document(
            doc_id,
            assistant_import_status="ready_for_assistant",
            processed_at=datetime.utcnow().isoformat(),
            extraction_error=None,
            request_id=request_id,
        )

        return {
            "ok": True,
            "document_id": doc_id,
            "snapshot_id": snapshot_id,
            "chunks_count": len(chunk_rows),
            "facts_count": len(facts),
            "revision_number": revision,
        }
    except Exception as exc:
        log.warning(
            "policy_assistant_import_pipeline failed doc_id=%s request_id=%s: %s",
            doc_id,
            request_id,
            exc,
            exc_info=True,
        )
        safe = str(exc)[:500]
        try:
            db.update_policy_document(
                doc_id,
                assistant_import_status="failed",
                extraction_error=safe,
                processed_at=datetime.utcnow().isoformat(),
                request_id=request_id,
            )
            if snapshot_id:
                db.mark_policy_snapshot_failed(snapshot_id)
        except Exception:
            pass
        return {"ok": False, "error_code": "pipeline_exception", "message": safe}
    finally:
        if lock_token and db.policy_hardening_tables_available():
            db.release_policy_extraction_lock(doc_id, lock_token)
            try:
                with db.engine.begin() as conn:
                    insert_audit_log(
                        conn,
                        entity_type="policy_extraction_lock",
                        entity_id=doc_id,
                        action_type="lock_released",
                        new_value={"user_id": uid},
                        actor_type=ACTOR_HUMAN,
                        actor_id=uid,
                    )
            except Exception:
                pass
