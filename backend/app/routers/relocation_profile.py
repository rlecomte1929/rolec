"""
GAP 1: Rich relocation profile — GET/PUT /api/employee/cases/{case_id}/relocation-profile

Stores the 40+ field preference profile (housing prefs, neighbourhood priorities,
household members, pets, temp housing, financial/FX) separately from the PII
immigration profile at /api/employee/cases/{case_id}/profile.

Backed by the ``relocation_profiles`` Supabase table (case_id PK, data JSONB).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth_deps import get_current_user
from ...database import db as main_db

router = APIRouter(prefix="/api/employee/cases", tags=["relocation-profile"])
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────────────────

class NeighbourhoodPriorities(BaseModel):
    commute: Optional[int] = Field(None, ge=0, le=10)
    intl_school: Optional[int] = Field(None, ge=0, le=10)
    parks: Optional[int] = Field(None, ge=0, le=10)
    expat_community: Optional[int] = Field(None, ge=0, le=10)
    nightlife: Optional[int] = Field(None, ge=0, le=10)
    safety: Optional[int] = Field(None, ge=0, le=10)
    transit: Optional[int] = Field(None, ge=0, le=10)


class HousingPreferences(BaseModel):
    type: Optional[str] = None           # apartment | house | studio | flexible
    min_bedrooms: Optional[int] = None
    max_budget_monthly_eur: Optional[int] = None
    furnished: Optional[bool] = None
    pet_friendly_required: Optional[bool] = None
    neighbourhood_priorities: Optional[NeighbourhoodPriorities] = None
    specific_areas: Optional[List[str]] = None
    notes: Optional[str] = None


class OriginHousing(BaseModel):
    owned: Optional[bool] = None
    rented: Optional[bool] = None
    notice_period_weeks: Optional[int] = None
    storage_needed: Optional[bool] = None
    shipping_volume_m3: Optional[float] = None


class SpouseProfile(BaseModel):
    full_name: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[str] = None
    occupation: Optional[str] = None
    employer: Optional[str] = None
    right_to_work_status: Optional[str] = None  # confirmed | pending | unknown
    career_support_needed: Optional[bool] = None


class ChildProfile(BaseModel):
    full_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    current_school_name: Optional[str] = None
    school_year: Optional[str] = None
    special_needs: Optional[str] = None
    language_of_instruction: Optional[str] = None
    school_type_preference: Optional[str] = None   # international | local | bilingual


class PetProfile(BaseModel):
    name: Optional[str] = None
    species: Optional[str] = None
    breed: Optional[str] = None
    weight_kg: Optional[float] = None
    origin_country: Optional[str] = None
    microchipped: Optional[bool] = None
    vaccinations_up_to_date: Optional[bool] = None
    rabies_titre_test_done: Optional[bool] = None
    health_certificate_obtained: Optional[bool] = None


class HouseholdMembers(BaseModel):
    marital_status: Optional[str] = None    # solo | partner | partner_kids | kids_only
    spouse: Optional[SpouseProfile] = None
    children: Optional[List[ChildProfile]] = None
    pets: Optional[List[PetProfile]] = None


class TempHousing(BaseModel):
    needed: Optional[bool] = None
    duration_weeks: Optional[int] = None
    max_budget_per_night_eur: Optional[int] = None
    serviced_apartment_preferred: Optional[bool] = None
    arrival_date: Optional[str] = None


class FinancialProfile(BaseModel):
    has_fx_transfer_needs: Optional[bool] = None
    estimated_monthly_transfer_eur: Optional[int] = None
    home_sale_proceeds: Optional[bool] = None
    investment_accounts_abroad: Optional[bool] = None
    tax_equalisation_applicable: Optional[bool] = None
    home_country_tax_filing_needed: Optional[bool] = None


class RelocationProfilePayload(BaseModel):
    origin_housing: Optional[OriginHousing] = None
    housing_preferences: Optional[HousingPreferences] = None
    household: Optional[HouseholdMembers] = None
    temp_housing: Optional[TempHousing] = None
    financial: Optional[FinancialProfile] = None
    additional_notes: Optional[str] = None


class RelocationProfileResponse(BaseModel):
    case_id: str
    profile: RelocationProfilePayload
    completion_pct: int
    last_updated_at: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _compute_completion(profile: Dict[str, Any]) -> int:
    """Rough completion percentage across the 5 sections."""
    sections = ["origin_housing", "housing_preferences", "household", "temp_housing", "financial"]
    filled = sum(1 for s in sections if profile.get(s))
    return int((filled / len(sections)) * 100)


def _get_profile_from_db(case_id: str) -> Optional[Dict[str, Any]]:
    """Fetch relocation_profile row from Supabase."""
    try:
        from ...services.supabase_client import get_supabase_client
        sb = get_supabase_client()
        result = sb.table("relocation_profiles").select("*").eq("case_id", case_id).maybe_single().execute()
        if result and result.data:
            return result.data
    except Exception:
        logger.exception("Failed to fetch relocation_profile case_id=%s", case_id)
    return None


def _upsert_profile_to_db(case_id: str, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Upsert relocation_profile row in Supabase."""
    from ...services.supabase_client import get_supabase_client
    import json
    from datetime import datetime, timezone
    sb = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "case_id": case_id,
        "user_id": user_id,
        "data": data,
        "updated_at": now,
    }
    result = sb.table("relocation_profiles").upsert(row, on_conflict="case_id").execute()
    if result and result.data:
        return result.data[0]
    raise HTTPException(status_code=500, detail="Failed to save relocation profile")


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{case_id}/relocation-profile", response_model=RelocationProfileResponse)
def get_relocation_profile(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """GAP 1: Return the rich relocation preference profile for a case."""
    row = _get_profile_from_db(case_id)
    if not row:
        # Return empty profile — not a 404, the case may just not have data yet
        return RelocationProfileResponse(
            case_id=case_id,
            profile=RelocationProfilePayload(),
            completion_pct=0,
            last_updated_at=None,
        )
    data = row.get("data") or {}
    return RelocationProfileResponse(
        case_id=case_id,
        profile=RelocationProfilePayload(**data),
        completion_pct=_compute_completion(data),
        last_updated_at=row.get("updated_at"),
    )


@router.put("/{case_id}/relocation-profile", response_model=RelocationProfileResponse)
def put_relocation_profile(
    case_id: str,
    payload: RelocationProfilePayload,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """GAP 1: Save / overwrite the rich relocation preference profile for a case."""
    data = payload.model_dump(mode="json", exclude_none=True)
    user_id = str(user.get("id", ""))
    _upsert_profile_to_db(case_id, user_id, data)
    return RelocationProfileResponse(
        case_id=case_id,
        profile=payload,
        completion_pct=_compute_completion(data),
        last_updated_at=None,
    )
