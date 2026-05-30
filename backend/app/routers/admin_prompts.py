"""
Admin Prompt Registry API (Parker Step D).

CRUD + lifecycle over the prompt registry (prompt_versions / prompt_routing).
Powers the admin UI at /admin/prompts where ReloPass ops version system prompts,
promote a version to prod, archive old ones, and dial canary traffic.

All routes are admin-only (require_admin). Mounted under /api/admin → effective
paths:
  GET  /api/admin/prompts
  GET  /api/admin/prompts/{task_key}
  POST /api/admin/prompts
  POST /api/admin/prompts/{version_id}/promote
  POST /api/admin/prompts/{task_key}/canary-share
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth_deps import require_admin
from ..services import preference_dataset_builder, prompt_registry

router = APIRouter(prefix="/prompts", tags=["admin-prompts"])
logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────


class PromptVersionCreate(BaseModel):
    model_config = {"protected_namespaces": ()}

    task_key: str = Field(..., min_length=1, max_length=128)
    system_prompt: str = Field(..., min_length=1)
    model_name: str = Field(..., min_length=1, max_length=128)
    user_template: Optional[str] = None
    temperature: float = 0.0
    max_tokens: int = Field(1024, ge=1, le=200000)
    status: str = Field("draft")
    notes: Optional[str] = None


class PromoteRequest(BaseModel):
    target_status: str = Field(..., min_length=1)


class CanaryShareRequest(BaseModel):
    canary_share: float = Field(..., ge=0.0, le=1.0)


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("")
def list_prompts(user: Dict[str, Any] = Depends(require_admin)) -> List[Dict[str, Any]]:
    """All prompt versions across every task_key."""
    return prompt_registry.list_versions()


@router.get("/{task_key}")
def list_prompts_for_task(
    task_key: str, user: Dict[str, Any] = Depends(require_admin)
) -> List[Dict[str, Any]]:
    """All versions for a single task_key."""
    return prompt_registry.list_versions(task_key=task_key)


@router.post("", status_code=201)
def create_prompt(
    body: PromptVersionCreate, user: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, Any]:
    """Create a new draft (or canary/prod) version for a task_key."""
    try:
        return prompt_registry.create_version(
            task_key=body.task_key,
            system_prompt=body.system_prompt,
            model_name=body.model_name,
            user_template=body.user_template,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            status=body.status,
            notes=body.notes,
            created_by=str(user.get("id") or user.get("user_id") or "") or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{version_id}/promote")
def promote_prompt(
    version_id: str,
    body: PromoteRequest,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Move a version to target_status (promoting to 'prod' archives the old prod)."""
    try:
        return prompt_registry.promote(version_id, body.target_status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{task_key}/win-rates")
def win_rates(
    task_key: str, user: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, Any]:
    """Per-version win rates (approvals / verdicts) with Wilson 95% CI (Parker Step E)."""
    rates = preference_dataset_builder.compute_win_rates(task_key)
    return {
        vid: {
            "version_id": wr.version_id,
            "approvals": wr.approvals,
            "total": wr.total,
            "win_rate": wr.win_rate,
            "ci_low": wr.ci_low,
            "ci_high": wr.ci_high,
        }
        for vid, wr in rates.items()
    }


@router.post("/{task_key}/canary-share")
def set_canary(
    task_key: str,
    body: CanaryShareRequest,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Set the canary traffic share for a task_key."""
    return prompt_registry.set_canary_share(task_key, body.canary_share)
