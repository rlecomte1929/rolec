"""
Auth Page Config — GET /api/public/auth-page-config (anonymous)
                    PUT /api/admin/auth-page-config (admin only)

Platform-wide (not per-company) visual-tuning config for the GlobeNetwork
canvas visualization shown on the public, unauthenticated /auth login/register
page. Single-row singleton in ``public.auth_page_config`` (id=1).

Unlike branding.py (per-company, gated behind get_current_user), this setting
is a single platform-wide value read by the /auth page BEFORE login — the GET
route has no auth dependency at all. The PUT route is admin-only via
require_admin (platform-wide setting, not company-scoped, so require_admin —
not require_admin_or_hr).

Always returns 200 from GET: hard-coded defaults (mirroring
frontend/src/components/auth/GlobeNetwork.tsx DEFAULT_GLOBE_NETWORK_CONFIG) if
no row exists yet or the fetch fails, so the public auth page never blocks on
this decorative config.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth_deps import require_admin

router = APIRouter(tags=["auth-page-config"])
logger = logging.getLogger(__name__)

_HEX_RE = r"^#[0-9a-fA-F]{6}$"


class AuthPageConfig(BaseModel):
    """Visual-tuning knobs for the GlobeNetwork canvas on the /auth page.

    Defaults match frontend/src/components/auth/GlobeNetwork.tsx
    DEFAULT_GLOBE_NETWORK_CONFIG exactly.
    """

    rotSpeed: float = Field(1.9, ge=0, le=20)
    pulseSpeed: float = Field(3.4, ge=0.1, le=30)
    reducedMotion: Optional[bool] = None
    dotCount: int = Field(2800, ge=0, le=20000)
    dotSize: float = Field(1.3, ge=0, le=10)
    dotOpacity: float = Field(0.65, ge=0, le=1)
    showCoastline: bool = True
    coastColor: str = Field("#1f8e8b", pattern=_HEX_RE)
    coastWidth: float = Field(0.9, ge=0, le=10)
    # NOTE: best-effort default — the source screenshot cropped this value.
    # Double-check/tune via the Auth Page Design admin panel.
    coastOpacity: float = Field(0.4, ge=0, le=1)
    coastGlow: float = Field(0, ge=0, le=50)
    arcColor: str = Field("#1f8e8b", pattern=_HEX_RE)
    arcWidth: float = Field(1.7, ge=0, le=10)
    arcGlow: float = Field(20, ge=0, le=100)
    arcDensity: float = Field(1.0, ge=0, le=1)
    citySize: float = Field(1.0, ge=0, le=10)
    showArcs: bool = True
    showCities: bool = True
    showLabels: bool = True


def _get_supabase():
    from ..services.supabase_client import get_supabase_admin_client

    return get_supabase_admin_client()


@router.get("/api/public/auth-page-config", response_model=AuthPageConfig)
def get_auth_page_config() -> AuthPageConfig:
    """Fully anonymous — no auth dependency. Called by the public /auth page
    before login. Always returns 200 with defaults on any failure."""
    try:
        sb = _get_supabase()
        result = (
            sb.table("auth_page_config")
            .select("config")
            .eq("id", 1)
            .maybe_single()
            .execute()
        )
        if result and result.data and result.data.get("config"):
            raw = result.data["config"]
            return AuthPageConfig(
                **{k: v for k, v in raw.items() if k in AuthPageConfig.model_fields}
            )
    except Exception:
        logger.exception("Failed to fetch auth_page_config; falling back to defaults")
    return AuthPageConfig()


@router.put("/api/admin/auth-page-config", response_model=AuthPageConfig)
def update_auth_page_config(
    payload: AuthPageConfig,
    user: Dict[str, Any] = Depends(require_admin),
) -> AuthPageConfig:
    """Admin-only. Validates payload shape/ranges via the Pydantic model above,
    then upserts the singleton row."""
    try:
        sb = _get_supabase()
        data = payload.model_dump(mode="json")
        sb.table("auth_page_config").upsert(
            {
                "id": 1,
                "config": data,
                "updated_by": user.get("auth_uuid") or None,
            }
        ).execute()
    except Exception as exc:
        logger.exception("Failed to save auth_page_config")
        raise HTTPException(
            status_code=500, detail="Failed to save auth page config."
        ) from exc
    return payload
