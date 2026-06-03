"""
Conjoint study API — Parker Step H.

Company-scoped HR endpoints to create a study, serve choice sets to respondents, collect
choices, fit the conditional-logit model, and read part-worths. HR/admin actions reuse
``require_admin_or_hr`` + an explicit path-``company_id``-vs-caller check (admins bypass);
respondent actions use ``get_current_user`` and are scoped to the caller's own rows.

The frontend (employee choice flow + HR results page) is deferred to
``prompts/followups/H-frontend.md`` per the UI-reuse mandate.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth_deps import get_current_user, get_org_id_for_hr_user, require_admin_or_hr
from ..db import SessionLocal
from ..services import conjoint_repo, conjoint_service

router = APIRouter(prefix="/api/hr", tags=["conjoint"])
log = logging.getLogger(__name__)


# ── Request models ──────────────────────────────────────────────────────────
class StudyCreate(BaseModel):
    name: Optional[str] = None
    attributes: Dict[str, List[str]] = Field(default_factory=dict)
    n_responses_target: int = 100


class ResponseSubmit(BaseModel):
    alternatives: List[Dict[str, str]]
    chosen_index: int


# ── Helpers ─────────────────────────────────────────────────────────────────
def _is_admin(user: Dict[str, Any]) -> bool:
    return bool(user.get("is_admin")) or user.get("role") == "admin"


def _assert_company(company_id: str, user: Dict[str, Any], caller_company: str) -> None:
    """HR may only act within their own company; admins bypass."""
    if _is_admin(user):
        return
    if str(company_id) != str(caller_company):
        raise HTTPException(status_code=403, detail="Company scope mismatch")


def _load_study_in_company(session: Any, company_id: str, study_id: str) -> Dict[str, Any]:
    study = conjoint_repo.get_study(session, study_id)
    if study is None or str(study["company_id"]) != str(company_id):
        raise HTTPException(status_code=404, detail="Study not found")
    return study


# ── HR/admin: create study ──────────────────────────────────────────────────
@router.post("/{company_id}/conjoint/studies")
def create_study(
    company_id: str,
    body: StudyCreate,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
    caller_company: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    _assert_company(company_id, user, caller_company)
    if not body.attributes or any(len(v) < 2 for v in body.attributes.values()):
        raise HTTPException(
            status_code=422,
            detail="Each attribute needs at least two levels for a conjoint study.",
        )
    session = SessionLocal()
    try:
        study = conjoint_repo.create_study(
            session,
            company_id=company_id,
            name=body.name,
            attributes=body.attributes,
            n_responses_target=body.n_responses_target,
        )
        session.commit()
        return study
    except HTTPException:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        log.exception("create_study failed")
        raise HTTPException(status_code=500, detail="Could not create study")
    finally:
        session.close()


# ── Respondent: next choice set ─────────────────────────────────────────────
@router.get("/{company_id}/conjoint/studies/{study_id}/next-choice-set")
def next_choice_set(
    company_id: str,
    study_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        study = _load_study_in_company(session, company_id, study_id)
        cs = conjoint_repo.next_choice_set_for_respondent(session, study, str(user["id"]))
        if cs is None:
            return {"study_id": study_id, "done": True, "choice_set": None}
        return {"study_id": study_id, "done": False, "choice_set": cs}
    finally:
        session.close()


# ── Respondent: submit a choice ─────────────────────────────────────────────
@router.post("/{company_id}/conjoint/studies/{study_id}/responses")
def submit_response(
    company_id: str,
    study_id: str,
    body: ResponseSubmit,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not body.alternatives or not (0 <= body.chosen_index < len(body.alternatives)):
        raise HTTPException(status_code=422, detail="chosen_index out of range")
    session = SessionLocal()
    try:
        _load_study_in_company(session, company_id, study_id)
        result = conjoint_repo.record_response(
            session,
            study_id=study_id,
            respondent_user_id=str(user["id"]),
            alternatives=body.alternatives,
            chosen_index=body.chosen_index,
        )
        session.commit()
        return result
    except HTTPException:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        log.exception("submit_response failed")
        raise HTTPException(status_code=500, detail="Could not record response")
    finally:
        session.close()


# ── HR/admin: fit ───────────────────────────────────────────────────────────
@router.post("/{company_id}/conjoint/studies/{study_id}/fit")
def fit_study(
    company_id: str,
    study_id: str,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
    caller_company: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    _assert_company(company_id, user, caller_company)
    session = SessionLocal()
    try:
        study = _load_study_in_company(session, company_id, study_id)
        responses = conjoint_repo.load_responses(session, study_id)
        results = conjoint_service.fit_conjoint(study["attributes"], responses)
        saved = conjoint_repo.save_results(
            session,
            study_id=study_id,
            part_worths=results.part_worths,
            fit_quality=results.fit_quality,
        )
        # Best-effort bridge into Step B's benefit_priors (no-op if table absent).
        conjoint_repo.push_to_benefit_priors(
            session, company_id=company_id, part_worths=results.part_worths
        )
        session.commit()
        return saved
    except HTTPException:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        log.exception("fit_study failed")
        raise HTTPException(status_code=500, detail="Could not fit study")
    finally:
        session.close()


# ── HR/admin: read results ──────────────────────────────────────────────────
@router.get("/{company_id}/conjoint/studies/{study_id}/results")
def get_results(
    company_id: str,
    study_id: str,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
    caller_company: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    _assert_company(company_id, user, caller_company)
    session = SessionLocal()
    try:
        _load_study_in_company(session, company_id, study_id)
        results = conjoint_repo.load_results(session, study_id)
        if results is None:
            raise HTTPException(status_code=404, detail="No results yet — run /fit first")
        return results
    finally:
        session.close()
