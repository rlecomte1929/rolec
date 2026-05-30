"""Parker-I — document-content translation endpoint.

POST /api/translate  — session-token auth, 60/min/user (SEC-004 path bucket in
``backend.app.rate_limits.path_limit``; no decorator needed, the middleware applies it).
Returns the translated text plus provider/cost and whether it was a cache hit.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth_deps import get_current_user
from ..db import SessionLocal
from ..services import translation_service
from ..services.translation_types import TranslationUnavailable

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["translation"])


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20_000)
    src: str = Field(..., min_length=2, max_length=5)
    tgt: str = Field(..., min_length=2, max_length=5)
    domain: Literal["policy", "comm", "supplier", "ui"] = "comm"
    quality_tier: Literal["fast", "premium"] = "fast"


class TranslateResponse(BaseModel):
    model_config = {"protected_namespaces": ()}  # allow the `model_version` field name

    text: str
    provider: str
    model_version: str
    cost_usd: float
    cache_hit: bool


@router.post("/translate", response_model=TranslateResponse)
def translate(
    body: TranslateRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> TranslateResponse:
    with SessionLocal() as session:
        try:
            result = translation_service.translate(
                body.text,
                body.src,
                body.tgt,
                domain=body.domain,
                quality_tier=body.quality_tier,
                session=session,
            )
        except TranslationUnavailable as exc:
            # No provider is configured/reachable. 503 so the caller can degrade to
            # showing the original text rather than failing hard.
            logger.warning("translation unavailable: %s", exc)
            raise HTTPException(status_code=503, detail="Translation service unavailable") from exc

    return TranslateResponse(
        text=result.text,
        provider=result.provider,
        model_version=result.model_version,
        cost_usd=result.cost_usd,
        cache_hit=result.cache_hit,
    )
