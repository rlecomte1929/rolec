"""
Policy document storage health diagnostic.

Checks Supabase storage config and bucket accessibility.
Used at startup and by GET /api/hr/policy-documents/health.
Does not log or expose secrets.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

POLICY_BUCKET_NAME = "hr-policies"

# Stable error codes for client mapping
STORAGE_MISSING_SERVICE_ROLE = "storage_missing_service_role"
STORAGE_MISSING_URL = "storage_missing_url"
STORAGE_BUCKET_NOT_FOUND = "storage_bucket_not_found"
STORAGE_UPLOAD_FAILED = "storage_upload_failed"
STORAGE_ACCESS_DENIED = "storage_access_denied"
POLICY_DOCUMENTS_TABLE_MISSING = "policy_documents_table_missing"
POLICY_DOCUMENT_CLAUSES_TABLE_MISSING = "policy_document_clauses_table_missing"
POLICY_VERSIONS_TABLE_MISSING = "policy_versions_table_missing"
RESOLVED_ASSIGNMENT_POLICIES_TABLE_MISSING = "resolved_assignment_policies_table_missing"
DB_INSERT_FAILED = "db_insert_failed"


def _map_storage_exception_to_code(exc: Exception) -> str:
    """Map storage exception to stable error code."""
    msg = str(exc).lower()
    if "invalid" in msg and ("api" in msg or "key" in msg or "jwt" in msg):
        return STORAGE_MISSING_SERVICE_ROLE
    if "bucket" in msg and ("not found" in msg or "does not exist" in msg):
        return STORAGE_BUCKET_NOT_FOUND
    if "permission" in msg or "forbidden" in msg or "403" in msg:
        return STORAGE_ACCESS_DENIED
    return STORAGE_UPLOAD_FAILED


def get_storage_error_code(exc: Exception) -> str:
    """Public: get stable error code from storage exception."""
    return _map_storage_exception_to_code(exc)


def check_policy_storage_health(db: Any) -> Dict[str, Any]:
    """
    Run storage and policy table health checks.
    Returns dict with boolean flags and error details.
    """
    result: Dict[str, Any] = {
        "supabase_url_present": False,
        "service_role_present": False,
        "bucket_name": POLICY_BUCKET_NAME,
        "bucket_access_ok": False,
        "policy_documents_table_ok": False,
        "policy_document_clauses_table_ok": False,
        "policy_versions_table_ok": False,
        "resolved_assignment_policies_table_ok": False,
    }

    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    result["supabase_url_present"] = bool(supabase_url and str(supabase_url).strip())
    result["service_role_present"] = bool(service_key and len(str(service_key)) > 10)

    if not result["supabase_url_present"] or not result["service_role_present"]:
        return result

    # Probe bucket access via lightweight list (limit 1)
    try:
        from .supabase_client import get_supabase_admin_client
        client = get_supabase_admin_client()
        # List root with limit 1 - validates bucket exists and we have access
        client.storage.from_(POLICY_BUCKET_NAME).list(path="", limit=1)
        result["bucket_access_ok"] = True
    except Exception as e:
        log.warning("policy_storage_health bucket probe failed: %s", type(e).__name__, exc_info=False)
        result["bucket_access_ok"] = False
        result["bucket_probe_error"] = type(e).__name__  # No raw message to avoid leaking internals

    # Check policy tables exist
    try:
        from sqlalchemy import text
        with db.engine.connect() as conn:
            for table, key in [
                ("policy_documents", "policy_documents_table_ok"),
                ("policy_document_clauses", "policy_document_clauses_table_ok"),
                ("policy_versions", "policy_versions_table_ok"),
                ("resolved_assignment_policies", "resolved_assignment_policies_table_ok"),
            ]:
                try:
                    is_sqlite = "sqlite" in str(db.engine.url)
                    if is_sqlite:
                        r = conn.execute(
                            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:t"),
                            {"t": table},
                        ).fetchone()
                    else:
                        r = conn.execute(
                            text(
                                "SELECT 1 FROM information_schema.tables "
                                "WHERE table_schema='public' AND table_name=:t"
                            ),
                            {"t": table},
                        ).fetchone()
                    result[key] = r is not None
                except Exception:
                    result[key] = False
    except Exception as e:
        log.warning("policy_storage_health table check failed: %s", e)
        for key in [
            "policy_documents_table_ok",
            "policy_document_clauses_table_ok",
            "policy_versions_table_ok",
            "resolved_assignment_policies_table_ok",
        ]:
            result[key] = False

    return result


def log_startup_storage_diagnostic(db: Any) -> None:
    """Log storage diagnostic at startup. No secrets."""
    health = check_policy_storage_health(db)
    log.info(
        "policy_storage: supabase_url=%s service_role=%s bucket=%s bucket_ok=%s "
        "policy_docs_table=%s policy_clauses_table=%s policy_versions_table=%s resolved_policies_table=%s",
        "yes" if health["supabase_url_present"] else "no",
        "yes" if health["service_role_present"] else "no",
        health["bucket_name"],
        "ok" if health["bucket_access_ok"] else "failed",
        "ok" if health["policy_documents_table_ok"] else "missing",
        "ok" if health["policy_document_clauses_table_ok"] else "missing",
        "ok" if health["policy_versions_table_ok"] else "missing",
        "ok" if health["resolved_assignment_policies_table_ok"] else "missing",
    )
    if not health["bucket_access_ok"] and health.get("bucket_probe_error"):
        log.warning("policy_storage bucket probe error: %s", health["bucket_probe_error"])
