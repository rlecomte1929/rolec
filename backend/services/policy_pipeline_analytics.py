"""
Structured analytics for the HR policy document pipeline and employee policy resolution.

Events are logged via analytics_service.emit_event and optionally persisted to analytics_events.
Never raises to callers.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

from .analytics_service import (
    EVENT_EMPLOYEE_POLICY_COMPARISON,
    EVENT_EMPLOYEE_POLICY_FALLBACK,
    EVENT_POLICY_CLASSIFY_COMPLETED,
    EVENT_POLICY_CLASSIFY_FAILED,
    EVENT_POLICY_CLASSIFY_STARTED,
    EVENT_POLICY_EMPLOYEE_RESOLUTION,
    EVENT_POLICY_NORMALIZE_COMPLETED,
    EVENT_POLICY_NORMALIZE_FAILED,
    EVENT_POLICY_NORMALIZE_STARTED,
    EVENT_POLICY_PUBLISH_COMPLETED,
    EVENT_POLICY_PUBLISH_FAILED,
    EVENT_POLICY_PUBLISH_STARTED,
    EVENT_POLICY_UPLOAD_COMPLETED,
    EVENT_POLICY_UPLOAD_FAILED,
    EVENT_POLICY_UPLOAD_STARTED,
    emit_event,
)


def _emit(event_name: str, **kwargs: Any) -> None:
    try:
        emit_event(event_name, **kwargs)
    except Exception as exc:
        log.debug("policy_pipeline_analytics emit failed (non-fatal): %s", exc)


def emit_policy_upload_started(
    *,
    request_id: Optional[str],
    user_id: Optional[str],
    company_id: Optional[str],
    filename: Optional[str] = None,
    file_size_bytes: Optional[int] = None,
) -> None:
    _emit(
        "policy_upload_started",
        request_id=request_id,
        user_id=user_id,
        user_role="HR",
        extra={
            "company_id": company_id,
            "filename": filename,
            "file_size_bytes": file_size_bytes,
            "stage": "upload",
        },
    )


def emit_policy_upload_completed(
    *,
    request_id: Optional[str],
    user_id: Optional[str],
    company_id: Optional[str],
    document_id: str,
    processing_status: Optional[str] = None,
    clause_count: Optional[int] = None,
    duration_ms: Optional[float] = None,
) -> None:
    _emit(
        EVENT_POLICY_UPLOAD_COMPLETED,
        request_id=request_id,
        user_id=user_id,
        user_role="HR",
        duration_ms=duration_ms,
        extra={
            "company_id": company_id,
            "document_id": document_id,
            "processing_status": processing_status,
            "clause_count": clause_count,
            "stage": "upload",
        },
    )


def emit_policy_upload_failed(
    *,
    request_id: Optional[str],
    user_id: Optional[str],
    company_id: Optional[str],
    error_code: str,
    message: Optional[str] = None,
    document_id: Optional[str] = None,
) -> None:
    _emit(
        EVENT_POLICY_UPLOAD_FAILED,
        request_id=request_id,
        user_id=user_id,
        user_role="HR",
        extra={
            "company_id": company_id,
            "error_code": error_code,
            "message": (message or "")[:300],
            "document_id": document_id,
            "stage": "upload",
        },
    )


def emit_policy_classify_started(
    *,
    request_id: Optional[str],
    user_id: Optional[str],
    company_id: Optional[str],
    document_id: str,
    source: str,
) -> None:
    _emit(
        EVENT_POLICY_CLASSIFY_STARTED,
        request_id=request_id,
        user_id=user_id,
        user_role="HR",
        extra={"company_id": company_id, "document_id": document_id, "source": source},
    )


def emit_policy_classify_completed(
    *,
    request_id: Optional[str],
    user_id: Optional[str],
    company_id: Optional[str],
    document_id: str,
    processing_status: Optional[str],
    detected_document_type: Optional[str] = None,
    source: str = "upload",
) -> None:
    _emit(
        EVENT_POLICY_CLASSIFY_COMPLETED,
        request_id=request_id,
        user_id=user_id,
        user_role="HR",
        extra={
            "company_id": company_id,
            "document_id": document_id,
            "processing_status": processing_status,
            "detected_document_type": detected_document_type,
            "source": source,
        },
    )


def emit_policy_classify_failed(
    *,
    request_id: Optional[str],
    user_id: Optional[str],
    company_id: Optional[str],
    document_id: str,
    extraction_error: Optional[str] = None,
    source: str = "upload",
) -> None:
    _emit(
        EVENT_POLICY_CLASSIFY_FAILED,
        request_id=request_id,
        user_id=user_id,
        user_role="HR",
        extra={
            "company_id": company_id,
            "document_id": document_id,
            "extraction_error": (extraction_error or "")[:400],
            "source": source,
        },
    )


def emit_policy_normalize_started(
    *,
    request_id: Optional[str],
    user_id: Optional[str],
    company_id: Optional[str],
    document_id: str,
) -> None:
    _emit(
        EVENT_POLICY_NORMALIZE_STARTED,
        request_id=request_id,
        user_id=user_id,
        user_role="HR",
        extra={"company_id": company_id, "document_id": document_id},
    )


def emit_policy_normalize_completed(
    *,
    request_id: Optional[str],
    user_id: Optional[str],
    company_id: Optional[str],
    document_id: str,
    policy_id: str,
    policy_version_id: str,
    summary: Optional[Dict[str, Any]] = None,
    auto_published: bool = True,
) -> None:
    _emit(
        EVENT_POLICY_NORMALIZE_COMPLETED,
        request_id=request_id,
        user_id=user_id,
        user_role="HR",
        extra={
            "company_id": company_id,
            "document_id": document_id,
            "policy_id": policy_id,
            "policy_version_id": policy_version_id,
            "summary": summary or {},
            "auto_published": auto_published,
        },
    )


def emit_policy_normalize_failed(
    *,
    request_id: Optional[str],
    user_id: Optional[str],
    company_id: Optional[str],
    document_id: str,
    error_code: str,
    detail: Optional[str] = None,
    http_status: Optional[int] = None,
) -> None:
    _emit(
        EVENT_POLICY_NORMALIZE_FAILED,
        request_id=request_id,
        user_id=user_id,
        user_role="HR",
        extra={
            "company_id": company_id,
            "document_id": document_id,
            "error_code": error_code,
            "detail": (detail or "")[:400],
            "http_status": http_status,
        },
    )


def emit_policy_publish_started(
    *,
    request_id: Optional[str],
    user_id: Optional[str],
    company_id: Optional[str],
    policy_id: str,
    policy_version_id: str,
    source: str = "manual",
) -> None:
    _emit(
        "policy_publish_started",
        request_id=request_id,
        user_id=user_id,
        user_role="HR",
        extra={
            "company_id": company_id,
            "policy_id": policy_id,
            "policy_version_id": policy_version_id,
            "source": source,
        },
    )


def emit_policy_publish_completed(
    *,
    request_id: Optional[str],
    user_id: Optional[str],
    company_id: Optional[str],
    policy_id: str,
    policy_version_id: str,
    source: str = "manual",
) -> None:
    _emit(
        EVENT_POLICY_PUBLISH_COMPLETED,
        request_id=request_id,
        user_id=user_id,
        user_role="HR",
        extra={
            "company_id": company_id,
            "policy_id": policy_id,
            "policy_version_id": policy_version_id,
            "source": source,
        },
    )


def emit_policy_publish_failed(
    *,
    request_id: Optional[str],
    user_id: Optional[str],
    company_id: Optional[str],
    policy_id: str,
    policy_version_id: Optional[str],
    error_code: str,
    detail: Optional[str] = None,
    source: str = "manual",
) -> None:
    _emit(
        EVENT_POLICY_PUBLISH_FAILED,
        request_id=request_id,
        user_id=user_id,
        user_role="HR",
        extra={
            "company_id": company_id,
            "policy_id": policy_id,
            "policy_version_id": policy_version_id,
            "error_code": error_code,
            "detail": (detail or "")[:400],
            "source": source,
        },
    )


def record_employee_policy_resolution(
    *,
    request_id: Optional[str],
    assignment_id: Optional[str],
    case_id: Optional[str],
    user_id: Optional[str],
    user_role: Optional[str],
    has_policy: bool,
    comparison_available: bool,
    comparison_readiness: Optional[Dict[str, Any]],
    policy_id: Optional[str] = None,
    policy_version_id: Optional[str] = None,
    company_id_used: Optional[str] = None,
    resolution_cache_hit: Optional[bool] = None,
) -> None:
    cr = comparison_readiness or {}
    blockers = cr.get("comparison_blockers")
    if not isinstance(blockers, list):
        blockers = []
    if has_policy and comparison_available:
        ux_mode = "comparison"
    elif has_policy:
        ux_mode = "fallback_summary"
    else:
        ux_mode = "fallback_no_policy"

    extra: Dict[str, Any] = {
        "has_policy": has_policy,
        "comparison_ready": bool(cr.get("comparison_ready")),
        "comparison_available": comparison_available,
        "comparison_blockers": blockers[:12],
        "employee_ux_mode": ux_mode,
        "policy_id": policy_id,
        "policy_version_id": policy_version_id,
        "company_id_used": company_id_used,
        "resolution_cache_hit": resolution_cache_hit,
    }

    _emit(
        "policy_employee_resolution",
        request_id=request_id,
        assignment_id=assignment_id,
        case_id=case_id,
        user_id=user_id,
        user_role=user_role,
        extra=extra,
    )

    if comparison_available:
        _emit(
            EVENT_EMPLOYEE_POLICY_COMPARISON,
            request_id=request_id,
            assignment_id=assignment_id,
            case_id=case_id,
            user_id=user_id,
            user_role=user_role,
            extra={
                "policy_id": policy_id,
                "policy_version_id": policy_version_id,
                "employee_ux_mode": ux_mode,
            },
        )
    else:
        _emit(
            EVENT_EMPLOYEE_POLICY_FALLBACK,
            request_id=request_id,
            assignment_id=assignment_id,
            case_id=case_id,
            user_id=user_id,
            user_role=user_role,
            extra={
                "has_policy": has_policy,
                "comparison_blockers": blockers[:12],
                "employee_ux_mode": ux_mode,
                "policy_id": policy_id,
                "policy_version_id": policy_version_id,
            },
        )
