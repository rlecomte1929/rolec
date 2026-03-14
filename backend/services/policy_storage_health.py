"""
Policy document storage health diagnostic.

Checks Supabase storage config and bucket accessibility.
Used at startup and by GET /api/hr/policy-documents/health.
Does not log or expose secrets.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

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

# Redact patterns: JWT segments, UUIDs, long hex strings
_SECRET_PATTERN = re.compile(
    r"[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|"  # JWT
    r"[a-f0-9]{32,}|"  # hex/tokens
    r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*",
    re.IGNORECASE,
)


def _safe_exception_summary(exc: Exception) -> Dict[str, Any]:
    """
    Extract safe diagnostic info from exception. No secrets.
    Returns: exc_type, exc_message_safe, exc_repr_safe, status_code (if present).
    """
    exc_type = type(exc).__name__
    raw_str = str(exc)
    raw_repr = repr(exc)
    safe_str = _SECRET_PATTERN.sub("[redacted]", raw_str)[:500] if raw_str else "(no message)"
    safe_repr = _SECRET_PATTERN.sub("[redacted]", raw_repr)[:600] if raw_repr else "(no repr)"
    result: Dict[str, Any] = {
        "exc_type": exc_type,
        "exc_message_safe": safe_str,
        "exc_repr_safe": safe_repr,
    }
    # StorageException/API errors often wrap dict with statusCode, message, error
    if hasattr(exc, "args") and exc.args and isinstance(exc.args[0], dict):
        d = exc.args[0]
        if isinstance(d.get("statusCode"), int):
            result["status_code"] = d["statusCode"]
        msg = d.get("message") or d.get("error") or d.get("msg")
        if msg and isinstance(msg, str):
            result["exc_message_safe"] = _SECRET_PATTERN.sub("[redacted]", msg)[:500]
    return result


def _extract_supabase_project_ref(url: Optional[str]) -> Optional[str]:
    """Extract project ref from SUPABASE_URL. e.g. https://xxx.supabase.co -> xxx"""
    if not url or not isinstance(url, str):
        return None
    try:
        parsed = urlparse(url.strip())
        host = (parsed.hostname or "").lower()
        # https://xxx.supabase.co or https://xxx.supabase.in
        if ".supabase.co" in host or ".supabase.in" in host:
            return host.split(".")[0] or None
        return host or None
    except Exception:
        return None


def _extract_db_project_ref(db_url: Optional[str]) -> Optional[str]:
    """
    Extract project ref from DATABASE_URL if Supabase.
    - Direct: db.xxx.supabase.co -> xxx
    - Pooler: postgres.xxx as username -> xxx
    """
    if not db_url or not isinstance(db_url, str):
        return None
    try:
        parsed = urlparse(db_url.strip())
        host = (parsed.hostname or "").lower()
        user = (parsed.username or "")
        if "db." in host and (".supabase.co" in host or ".supabase.in" in host):
            return host.replace("db.", "").split(".")[0] or None
        if "pooler.supabase.com" in host or "pooler.supabase.in" in host:
            if "." in user:
                return user.split(".")[-1].split(":")[0] or None
            return None
        return None
    except Exception:
        return None


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


def _diagnose_from_error(err_detail: Dict[str, Any]) -> str:
    """Map error detail to explicit diagnosis code."""
    msg = (err_detail.get("exc_message_safe") or "").lower()
    status = err_detail.get("status_code")

    if status == 404 or "not found" in msg or "does not exist" in msg:
        return "bucket_missing"
    if status == 403 or "forbidden" in msg or "permission" in msg:
        return "permission_denied"
    if status == 401:
        return "wrong_project_url_key_mismatch"
    if "invalid" in msg and ("key" in msg or "jwt" in msg):
        return "wrong_key_type"
    if "invalid" in msg and "url" in msg:
        return "wrong_project_url_key_mismatch"
    if "key" in msg and ("mismatch" in msg or "wrong" in msg or "invalid" in msg):
        return "wrong_project_url_key_mismatch"
    if "typeerror" in msg or "attributeerror" in msg or "not found" in msg and "method" in msg:
        return "storage_api_client_incompatibility"
    return "probe_failed_unknown"


def _probe_bucket_via_get_bucket(client: Any, bucket_name: str) -> Dict[str, Any]:
    """
    Primary probe: GET /bucket/{id}. Most deterministic - direct bucket metadata fetch.
    Does not list objects, does not create anything.
    """
    result: Dict[str, Any] = {"method": "get_bucket", "ok": False, "error": None}
    try:
        bucket = client.storage.get_bucket(bucket_name)
        result["ok"] = bucket is not None and (getattr(bucket, "id", None) == bucket_name or (isinstance(bucket, dict) and bucket.get("id") == bucket_name))
    except Exception as e:
        summary = _safe_exception_summary(e)
        result["error"] = summary.get("exc_type", "unknown")
        result["error_detail"] = summary
        log.warning(
            "policy_storage bucket probe get_bucket failed: exc_type=%s exc_repr=%s message=%s",
            summary.get("exc_type"),
            summary.get("exc_repr_safe", "")[:300],
            summary.get("exc_message_safe", "")[:200],
        )
    return result


def _probe_bucket_via_list_buckets(client: Any, bucket_name: str) -> Dict[str, Any]:
    """Probe by listing all buckets and checking if hr-policies exists."""
    result: Dict[str, Any] = {"method": "list_buckets", "ok": False, "error": None}
    try:
        buckets = client.storage.list_buckets()
        bucket_ids = []
        for b in buckets or []:
            if hasattr(b, "id"):
                bucket_ids.append(getattr(b, "id"))
            elif isinstance(b, dict):
                bucket_ids.append(b.get("id"))
        result["buckets_found"] = len(bucket_ids)
        result["bucket_in_list"] = bucket_name in bucket_ids
        result["ok"] = result["bucket_in_list"]
        if not result["ok"]:
            result["error"] = "bucket_not_in_list"
    except Exception as e:
        summary = _safe_exception_summary(e)
        result["error"] = summary.get("exc_type", "unknown")
        result["error_detail"] = summary
        log.warning(
            "policy_storage bucket probe list_buckets failed: exc_type=%s exc_repr=%s message=%s",
            summary.get("exc_type"),
            summary.get("exc_repr_safe", "")[:300],
            summary.get("exc_message_safe", "")[:200],
        )
    return result


def _probe_bucket_via_list(client: Any, bucket_name: str) -> Dict[str, Any]:
    """
    Fallback probe: list objects in bucket. storage3 API: list(path="", options={"limit": 1}).
    """
    result: Dict[str, Any] = {"method": "list_objects", "ok": False, "error": None}
    try:
        bucket_proxy = client.storage.from_(bucket_name)
        objects = bucket_proxy.list(path="", options={"limit": 1})
        result["ok"] = True
        result["objects_returned"] = len(objects) if isinstance(objects, list) else 0
    except Exception as e:
        summary = _safe_exception_summary(e)
        result["error"] = summary.get("exc_type", "unknown")
        result["error_detail"] = summary
        log.warning(
            "policy_storage bucket probe list_objects failed: exc_type=%s exc_repr=%s message=%s",
            summary.get("exc_type"),
            summary.get("exc_repr_safe", "")[:300],
            summary.get("exc_message_safe", "")[:200],
        )
    return result


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
    database_url = os.getenv("DATABASE_URL")

    result["supabase_url_present"] = bool(supabase_url and str(supabase_url).strip())
    result["service_role_present"] = bool(service_key and len(str(service_key)) > 10)

    # Project refs for diagnostic
    result["project_ref_from_supabase_url"] = _extract_supabase_project_ref(supabase_url)
    result["supabase_project_ref"] = result["project_ref_from_supabase_url"]  # backward compat
    result["database_project_ref"] = _extract_db_project_ref(database_url)
    result["project_refs_match"] = (
        result["project_ref_from_supabase_url"] == result["database_project_ref"]
        if (result["project_ref_from_supabase_url"] and result["database_project_ref"])
        else None
    )
    result["bucket_probe_method"] = None
    result["bucket_probe_error_type"] = None
    result["bucket_probe_error_message"] = None

    if not result["supabase_url_present"] or not result["service_role_present"]:
        return result

    # Bucket probe: get_bucket (primary) -> list_buckets -> list_objects
    result["bucket_probe"] = {}
    client = None
    try:
        from .supabase_client import get_supabase_admin_client
        client = get_supabase_admin_client()
    except Exception as e:
        summary = _safe_exception_summary(e)
        result["bucket_probe"]["client_init_error"] = summary
        result["bucket_probe"]["diagnosis"] = (
            "wrong_project_url_key_mismatch" if "invalid" in str(e).lower() and "url" in str(e).lower()
            else "wrong_key_type" if "invalid" in str(e).lower() and ("key" in str(e).lower() or "jwt" in str(e).lower())
            else "storage_api_client_incompatibility"
        )
        result["bucket_probe_method"] = "client_init"
        result["bucket_probe_error_type"] = summary.get("exc_type")
        result["bucket_probe_error_message"] = summary.get("exc_message_safe")
        log.warning(
            "policy_storage client init failed: exc_type=%s exc_repr=%s message=%s",
            summary.get("exc_type"),
            summary.get("exc_repr_safe", "")[:300],
            summary.get("exc_message_safe", "")[:200],
        )
        return result

    def _set_probe_error(method: str, err_detail: Dict[str, Any]) -> None:
        result["bucket_probe_method"] = method
        result["bucket_probe_error_type"] = err_detail.get("exc_type")
        result["bucket_probe_error_message"] = err_detail.get("exc_message_safe")
        result["bucket_probe"]["diagnosis"] = _diagnose_from_error(err_detail)

    # 1. Primary: get_bucket(id) - direct bucket metadata fetch
    get_result: Dict[str, Any] = {}
    if hasattr(client.storage, "get_bucket"):
        get_result = _probe_bucket_via_get_bucket(client, POLICY_BUCKET_NAME)
        result["bucket_probe"]["get_bucket"] = get_result
    else:
        result["bucket_probe"]["get_bucket"] = {"ok": False, "error": "method_not_available"}

    if get_result.get("ok"):
        result["bucket_access_ok"] = True
        result["bucket_probe"]["diagnosis"] = "ok"
    else:
        # 2. Fallback: list_buckets
        list_buckets_result: Dict[str, Any] = {}
        if hasattr(client.storage, "list_buckets"):
            list_buckets_result = _probe_bucket_via_list_buckets(client, POLICY_BUCKET_NAME)
            result["bucket_probe"]["list_buckets"] = list_buckets_result

        if list_buckets_result.get("ok"):
            result["bucket_access_ok"] = list_buckets_result.get("bucket_in_list", False)
            if not result["bucket_access_ok"]:
                result["bucket_probe"]["diagnosis"] = "bucket_missing"
                result["bucket_probe_method"] = "list_buckets"
                result["bucket_probe_error_type"] = "bucket_not_in_list"
                result["bucket_probe_error_message"] = f"Bucket {POLICY_BUCKET_NAME} not in list (found {list_buckets_result.get('buckets_found', 0)} buckets)"
        else:
            # 3. Last resort: list objects
            list_result = _probe_bucket_via_list(client, POLICY_BUCKET_NAME)
            result["bucket_probe"]["list_objects"] = list_result

            if list_result.get("ok"):
                result["bucket_access_ok"] = True
                result["bucket_probe"]["diagnosis"] = "ok_via_list_objects"
            else:
                err_detail = (
                    get_result.get("error_detail")
                    or list_buckets_result.get("error_detail")
                    or list_result.get("error_detail")
                    or {}
                )
                _set_probe_error(
                    get_result.get("method") or list_buckets_result.get("method") or list_result.get("method") or "unknown",
                    err_detail,
                )
                result["bucket_probe"]["error_detail"] = err_detail
                log.warning(
                    "policy_storage bucket probe failed: diagnosis=%s method=%s exc_type=%s exc_repr=%s message=%s",
                    result["bucket_probe"]["diagnosis"],
                    result["bucket_probe_method"],
                    err_detail.get("exc_type"),
                    err_detail.get("exc_repr_safe", "")[:200],
                    err_detail.get("exc_message_safe", "")[:200],
                )

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
        log.warning("policy_storage_health table check failed: %s", type(e).__name__)
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
    if health.get("supabase_project_ref"):
        log.info("policy_storage: supabase_project_ref=%s db_project_ref=%s match=%s",
                 health.get("supabase_project_ref"),
                 health.get("database_project_ref"),
                 health.get("project_refs_match"))
    if not health["bucket_access_ok"]:
        probe = health.get("bucket_probe") or {}
        diagnosis = probe.get("diagnosis", "unknown")
        err_detail = probe.get("error_detail") or {}
        log.warning(
            "policy_storage bucket probe failed: diagnosis=%s exc_type=%s status=%s",
            diagnosis,
            err_detail.get("exc_type"),
            err_detail.get("status_code"),
        )
