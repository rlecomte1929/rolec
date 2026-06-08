"""Classical-NLG product endpoints (Parker step J).

Exposes two LLM-free NLG surfaces:
  - GET /api/hr/{company_id}/exec-summary  — data-to-text KPI summary (HR/admin)
  - GET /api/policies/{policy_id}/tldr     — extractive TL;DR of a policy doc

The exec-summary path is gated by the env flag ``NLG_EXEC_SUMMARY_PROVIDER``
(``data_to_text`` default | ``llm``) so the swap away from the legacy LLM
summary is a one-env-var rollback.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from ..auth_deps import get_current_user, require_admin_or_hr
from ...schemas import UserRole
from ..services.nlg import data_to_text as d2t
from ..services.nlg import extractive_summarizer as extractive
from ...database import db

router = APIRouter(tags=["nlg"])
logger = logging.getLogger(__name__)

EXEC_SUMMARY_PROVIDER_ENV = "NLG_EXEC_SUMMARY_PROVIDER"


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ExecSummaryResponse(BaseModel):
    company_id: str
    provider: str  # 'data_to_text' | 'llm'
    period: str
    summary: Optional[str] = None  # None when provider='llm' (frontend keeps its own)


class PolicyTldrResponse(BaseModel):
    policy_id: str
    summary: str
    sentence_count: int
    source_chars: int


# ---------------------------------------------------------------------------
# Data loaders (monkeypatched in tests; guarded so a DB miss never 500s)
# ---------------------------------------------------------------------------

def _t(name: str) -> str:
    try:
        dialect_name = db.engine.dialect.name
    except Exception:
        dialect_name = "postgresql"
    return f"public.{name}" if dialect_name == "postgresql" else name


def load_company_kpis(company_id: str) -> d2t.KPISet:
    """Assemble a KPISet for a company from the HR command-center aggregates.

    Reuses ``db.get_command_center_kpis`` — the same company-scoped join that
    powers the command-center KPI cards — instead of querying a ``company_id``
    column that does not exist on ``case_assignments`` (the previous query
    always threw and silently rendered a misleading 'no KPIs' sentence).

    Best-effort: any failure yields an empty KPISet (the summariser renders a
    safe 'no KPIs' sentence) rather than erroring the endpoint.
    """
    period = "current period"
    kpis = []
    try:
        agg = db.get_command_center_kpis(company_id=company_id) or {}
        kpi_specs = (
            ("active_cases", "Active cases", agg.get("activeCases")),
            ("at_risk", "At-risk cases", agg.get("atRiskCount")),
            ("attention_needed", "Cases needing attention", agg.get("attentionNeededCount")),
            ("completed_ytd", "Completed this year", agg.get("completedCount")),
        )
        for key, label, value in kpi_specs:
            kpis.append(
                d2t.KPI(
                    key=key,
                    label=label,
                    current=float(value or 0),
                    unit="",
                    # at-risk / attention-needed are bad when they rise.
                    higher_is_better=key not in ("at_risk", "attention_needed"),
                )
            )
    except Exception:
        logger.warning("exec-summary KPI load failed for company_id=%s", company_id, exc_info=True)
    return d2t.KPISet(period_label=period, kpis=kpis)


def load_policy_text(policy_id: str) -> Optional[str]:
    """Return the concatenated text of a policy document, or None if not found."""
    try:
        with db.engine.connect() as conn:
            row = conn.execute(
                text(
                    f"SELECT raw_text FROM {_t('policy_documents')} WHERE id = :pid"
                ),
                {"pid": policy_id},
            ).mappings().first()
            if row and row.get("raw_text"):
                return str(row["raw_text"])
    except Exception:
        logger.warning("policy tldr text load failed for policy_id=%s", policy_id, exc_info=True)
    return None


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _authorize_company(user: Dict[str, Any], company_id: str) -> None:
    if user.get("role") == UserRole.ADMIN.value or user.get("is_admin"):
        return
    user_cid = str(user.get("company_id") or user.get("company") or "")
    if not user_cid:
        # AIQ-862: legacy text HR ids resolve their company only via hr_users;
        # without this a legitimate HR 403'd on their OWN company's summary.
        # Isolation is preserved — we compare the caller's RESOLVED company to
        # the path company_id below, so this never grants cross-company access.
        uid = user.get("id")
        user_cid = str(db.get_hr_company_id(uid) or "") if uid else ""
    if user_cid and user_cid == str(company_id):
        return
    raise HTTPException(status_code=403, detail="Cross-company access denied")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/hr/{company_id}/exec-summary", response_model=ExecSummaryResponse)
def get_exec_summary(
    company_id: str,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> ExecSummaryResponse:
    """Data-to-text executive KPI summary for a company (env-flag gated)."""
    _authorize_company(user, company_id)

    provider = (os.environ.get(EXEC_SUMMARY_PROVIDER_ENV) or "data_to_text").lower()
    if provider == "llm":
        # Rollback path: defer to the frontend's existing LLM-rendered summary.
        return ExecSummaryResponse(
            company_id=company_id, provider="llm", period="current period", summary=None
        )

    kpis = load_company_kpis(company_id)
    summary = d2t.summarise_kpis(kpis, audience="exec")
    return ExecSummaryResponse(
        company_id=company_id,
        provider="data_to_text",
        period=kpis.period_label,
        summary=summary,
    )


@router.get("/api/policies/{policy_id}/tldr", response_model=PolicyTldrResponse)
def get_policy_tldr(
    policy_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> PolicyTldrResponse:
    """Extractive (TextRank) TL;DR of a policy document. LLM-free."""
    body = load_policy_text(policy_id)
    if not body:
        raise HTTPException(status_code=404, detail="Policy document not found or empty")

    summary = extractive.summarise(body, max_sentences=5)
    return PolicyTldrResponse(
        policy_id=policy_id,
        summary=summary,
        sentence_count=summary.count(". ") + 1 if summary else 0,
        source_chars=len(body),
    )
