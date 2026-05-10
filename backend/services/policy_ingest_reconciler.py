"""
Policy ingest orphan reconciler.

Problem: policy_documents ingestion runs via FastAPI BackgroundTasks
(in-process). If the backend restarts (Render redeploy, OOM, crash) while a
task is mid-extraction, the policy_documents row is left stuck in a transient
processing_status ('uploaded' / 'text_extracted') or with
assistant_import_status='extracting_text'. The user sees a spinner forever
and has no way to retry — the idempotency guard on upload (see
db.get_active_policy_document_by_checksum) specifically treats non-'failed'
rows as "already in flight" and short-circuits.

Fix: at app startup, and on demand via an admin endpoint, scan for rows
that have been in a transient state for longer than MAX_AGE_SECONDS (default
15 minutes) and mark them as failed with a clear extraction_error. The
upload endpoint's idempotency lookup excludes failed rows, so the user can
retry by re-uploading the same file.

Full durable-queue replacement for BackgroundTasks is tracked separately;
this is the MVP that stops silent data loss.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from .._time import utcnow, utcnow_iso_naive

log = logging.getLogger(__name__)

DEFAULT_MAX_AGE_SECONDS = 15 * 60  # 15 minutes

# Rows in these processing_status values are considered "in-flight" and may
# be orphaned if they've been around too long. Terminal states (classified,
# normalized, approved, failed) are never reconciled.
IN_FLIGHT_PROCESSING_STATUSES = ("uploaded", "text_extracted")

# Same idea but for the assistant_import_status field (the policy-assistant
# pipeline's own state machine, set before the background task starts).
IN_FLIGHT_ASSISTANT_STATUSES = ("extracting_text",)


def _build_cutoff_iso(max_age_seconds: int) -> str:
    """
    ISO cutoff timestamp. Emitted as naive ISO (no tz offset) to stay
    comparable with the existing policy_documents.uploaded_at rows which
    were written as `datetime.utcnow().isoformat()`.
    """
    cutoff = utcnow() - timedelta(seconds=max_age_seconds)
    return cutoff.replace(tzinfo=None).isoformat()


def find_orphaned_policy_documents(
    db: Any,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> List[Dict[str, Any]]:
    """
    Return policy_documents rows stuck in a transient state for longer than
    max_age_seconds. Does not mutate. Safe to call from read-only contexts.
    """
    cutoff_iso = _build_cutoff_iso(max_age_seconds)
    placeholders_proc = ",".join(f":p{i}" for i in range(len(IN_FLIGHT_PROCESSING_STATUSES)))
    placeholders_ass = ",".join(f":a{i}" for i in range(len(IN_FLIGHT_ASSISTANT_STATUSES)))
    params: Dict[str, Any] = {"cutoff": cutoff_iso}
    for i, v in enumerate(IN_FLIGHT_PROCESSING_STATUSES):
        params[f"p{i}"] = v
    for i, v in enumerate(IN_FLIGHT_ASSISTANT_STATUSES):
        params[f"a{i}"] = v
    sql = (
        "SELECT id, company_id, filename, processing_status, "
        "assistant_import_status, uploaded_at "
        "FROM policy_documents "
        "WHERE uploaded_at < :cutoff "
        f"AND ( processing_status IN ({placeholders_proc}) "
        f"      OR assistant_import_status IN ({placeholders_ass}) )"
    )
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
    except Exception as ex:
        # If the table doesn't exist yet (fresh dev DB) this is fine — nothing to do.
        log.info("find_orphaned_policy_documents: query skipped (%s)", ex)
        return []
    return [dict(r._mapping) for r in rows]


def reconcile_orphaned_policy_ingest_jobs(
    db: Any,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    actor_id: Optional[str] = None,
    actor_label: str = "startup",
) -> Dict[str, Any]:
    """
    Scan for orphaned ingest jobs and mark them failed. Returns a summary
    dict: {"scanned": N, "failed": M, "orphans": [{id, company_id, filename}, ...]}.

    The update path uses the existing update_policy_document() so existing
    audit / observability hooks still fire.
    """
    orphans = find_orphaned_policy_documents(db, max_age_seconds=max_age_seconds)
    if not orphans:
        return {"scanned": 0, "failed": 0, "orphans": []}

    log.warning(
        "policy_ingest_reconciler: %d orphaned documents detected (actor=%s, max_age=%ds)",
        len(orphans), actor_label, max_age_seconds,
    )

    failed: List[Dict[str, Any]] = []
    for row in orphans:
        doc_id = row.get("id")
        if not doc_id:
            continue
        try:
            db.update_policy_document(
                doc_id,
                processing_status="failed",
                assistant_import_status="failed",
                extraction_error=(
                    f"interrupted_before_completion: reconciler={actor_label} "
                    f"age>{max_age_seconds}s"
                ),
                processed_at=utcnow_iso_naive(),
            )
            failed.append({
                "id": doc_id,
                "company_id": row.get("company_id"),
                "filename": row.get("filename"),
                "previous_processing_status": row.get("processing_status"),
                "previous_assistant_import_status": row.get("assistant_import_status"),
            })
            log.info(
                "policy_ingest_reconciler: marked orphaned doc_id=%s company_id=%s filename=%s as failed",
                doc_id,
                (row.get("company_id") or "")[:8],
                row.get("filename"),
            )
        except Exception as ex:
            log.error(
                "policy_ingest_reconciler: failed to mark doc_id=%s as failed: %s",
                doc_id, ex, exc_info=True,
            )

    return {
        "scanned": len(orphans),
        "failed": len(failed),
        "orphans": failed,
    }
