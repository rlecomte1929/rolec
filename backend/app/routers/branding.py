"""
GAP 10: Company branding config — GET /api/company/branding-config

Returns company-level branding settings used to white-label the employee portal:
  logo_url, primary_colour, secondary_colour, company_name_override,
  welcome_message, footer_text, custom_support_email.

The `branding_config` JSONB column was added to `companies` in migration
`add_company_branding_config`.

Fallback: if no branding_config is set, returns sensible defaults so the
frontend never gets a 404 — empty branding = ReloPass default theme.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth_deps import get_current_user

router = APIRouter(prefix="/api/company", tags=["branding"])
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Response model
# ─────────────────────────────────────────────────────────────────────────────

class BrandingConfig(BaseModel):
    """Company branding customisation for the employee portal."""
    logo_url: Optional[str] = None
    logo_dark_url: Optional[str] = None
    favicon_url: Optional[str] = None
    primary_colour: Optional[str] = None       # hex, e.g. "#1E40AF"
    secondary_colour: Optional[str] = None
    accent_colour: Optional[str] = None
    company_name_override: Optional[str] = None
    welcome_message: Optional[str] = None
    footer_text: Optional[str] = None
    custom_support_email: Optional[str] = None
    custom_support_url: Optional[str] = None
    hide_relopass_branding: bool = False


class BrandingConfigResponse(BaseModel):
    # company_id is None when the caller has no company linked (admin users
    # browsing cross-tenant). The GET endpoint returns default branding in
    # that case rather than 403'ing every HR page that boots.
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    branding: BrandingConfig


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _get_company_branding(company_id: str) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Fetch company name and branding_config JSONB from Supabase.
    Returns (company_name, branding_dict) or (None, None) on failure.
    """
    try:
        from ..services.supabase_client import get_supabase_admin_client
        sb = get_supabase_admin_client()
        result = (
            sb.table("companies")
            .select("id, name, branding_config")
            .eq("id", company_id)
            .maybe_single()
            .execute()
        )
        if result and result.data:
            row = result.data
            return row.get("name"), row.get("branding_config") or {}
    except Exception:
        logger.debug("Could not fetch branding_config for company %s", company_id)
    return None, None


def _resolve_company_id(user: Dict[str, Any]) -> str:
    """Extract company_id from the authenticated user's token / profile.

    Returns None when the user has no company linked. The caller decides
    whether that's a 403 (e.g. for PUT-style mutations that require a
    tenant) or a 200-with-defaults (for GETs — admin users with no tenant
    membership should see the page render with default branding instead
    of 403 noise in every HR page console)."""
    company_id = user.get("company") or user.get("company_id")
    if not company_id:
        try:
            from ...database import db
            profile = db.get_profile_record(user.get("id"))
            company_id = (profile or {}).get("company_id")
        except Exception:
            pass
    return str(company_id) if company_id else None


# ─────────────────────────────────────────────────────────────────────────────
# Route
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/branding-config", response_model=BrandingConfigResponse)
def get_branding_config(
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    GAP 10: Return the company's portal branding config.

    Available to all authenticated users (employees and HR).
    Always returns 200 — if the user has no company linked (e.g. admin
    cross-tenant browse) OR if no branding_config is set, fields are
    null and the frontend falls back to the default ReloPass theme.
    """
    company_id = _resolve_company_id(user)
    if not company_id:
        # Admin / unlinked user: return empty defaults instead of 403'ing
        # every HR page that boots.
        return BrandingConfigResponse(
            company_id=None,
            company_name=None,
            branding=BrandingConfig(),
        )
    company_name, branding_dict = _get_company_branding(company_id)

    # Parse JSONB into typed model, ignoring unknown keys
    try:
        branding = BrandingConfig(**{
            k: v for k, v in (branding_dict or {}).items()
            if k in BrandingConfig.model_fields
        })
    except Exception:
        branding = BrandingConfig()

    return BrandingConfigResponse(
        company_id=company_id,
        company_name=company_name,
        branding=branding,
    )


@router.put("/branding-config", response_model=BrandingConfigResponse)
def update_branding_config(
    payload: BrandingConfig,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    GAP 10: Save the company's portal branding config.

    Restricted to HR role or admin users.
    """
    from ..auth_deps import require_admin_or_hr
    # Validate role inline (can't use Depends here directly)
    role = user.get("role", "")
    if role not in ("hr", "admin") and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="HR or admin role required.")

    company_id = _resolve_company_id(user)
    if not company_id:
        # PUTs still require a real company — can't save branding without
        # somewhere to save it.
        raise HTTPException(
            status_code=403,
            detail="No company linked to your profile — cannot save branding.",
        )

    try:
        from ..services.supabase_client import get_supabase_admin_client
        sb = get_supabase_admin_client()
        branding_data = payload.model_dump(mode="json", exclude_none=True)
        result = (
            sb.table("companies")
            .update({"branding_config": branding_data})
            .eq("id", company_id)
            .execute()
        )
        company_name = None
        if result and result.data:
            company_name = result.data[0].get("name")
    except Exception as exc:
        logger.exception("Failed to update branding_config company_id=%s", company_id)
        raise HTTPException(status_code=500, detail="Failed to save branding config.") from exc

    return BrandingConfigResponse(
        company_id=company_id,
        company_name=company_name,
        branding=payload,
    )
