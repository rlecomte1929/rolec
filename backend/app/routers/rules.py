"""
GAP 6: Pet & breed restriction rules — GET /api/rules/pet-restrictions

Centralises the breed/quarantine logic that is currently hardcoded client-side
in S1n (RESTRICTED_BREEDS, QUARANTINE_COUNTRIES arrays).

Data is stored in the ``pet_restrictions`` Supabase table (seeded below).
Falls back to the hardcoded arrays if the DB is unavailable.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rules", tags=["rules"])


# ─────────────────────────────────────────────────────────────────────────────
# Hardcoded fallback data (mirrors S1n prototype)
# ─────────────────────────────────────────────────────────────────────────────

_QUARANTINE_COUNTRIES = {
    "GB": {"quarantine_days": 10, "permit_required": True, "estimated_cost_range": "£500–£1,500"},
    "AU": {"quarantine_days": 10, "permit_required": True, "estimated_cost_range": "AUD 2,000–4,000"},
    "JP": {"quarantine_days": 180, "permit_required": True, "estimated_cost_range": "¥150,000–¥300,000"},
    "NZ": {"quarantine_days": 10, "permit_required": True, "estimated_cost_range": "NZD 1,500–3,000"},
    "SG": {"quarantine_days": 30, "permit_required": True, "estimated_cost_range": "SGD 1,000–2,500"},
    "TW": {"quarantine_days": 21, "permit_required": True, "estimated_cost_range": "TWD 8,000–15,000"},
}

_RESTRICTED_BREEDS_GLOBAL = [
    "Pit Bull Terrier",
    "American Staffordshire Terrier",
    "Staffordshire Bull Terrier",
    "Rottweiler",
    "Dobermann",
    "Dogo Argentino",
    "Fila Brasileiro",
    "Japanese Tosa",
    "Perro de Presa Canario",
]

_RESTRICTED_BREEDS_BY_COUNTRY = {
    "DE": _RESTRICTED_BREEDS_GLOBAL + ["American Bulldog"],
    "FR": ["Pit Bull Terrier", "American Staffordshire Terrier", "Rottweiler"],
    "IT": _RESTRICTED_BREEDS_GLOBAL,
    "NO": ["Pit Bull Terrier", "American Staffordshire Terrier"],
    "SE": [],  # Sweden has no breed ban — list is empty
    "DK": _RESTRICTED_BREEDS_GLOBAL[:6],
    "NL": [],  # Netherlands lifted breed ban in 2009
    "BE": ["Pit Bull Terrier"],
    "GB": ["Pit Bull Terrier", "Japanese Tosa", "Dogo Argentino", "Fila Brasileiro"],
    "AU": _RESTRICTED_BREEDS_GLOBAL,
    "SG": _RESTRICTED_BREEDS_GLOBAL,
    "US": [],  # Federal level none; varies by municipality — flag as "check locally"
}


# ─────────────────────────────────────────────────────────────────────────────
# Response model
# ─────────────────────────────────────────────────────────────────────────────

class PetRestrictionsResponse(BaseModel):
    destination_code: str
    quarantine_required: bool
    quarantine_days: int
    import_permit_required: bool
    restricted_breeds: List[str]
    estimated_cost_range: Optional[str] = None
    eu_pet_passport_accepted: bool
    microchip_required: bool
    rabies_vaccination_required: bool
    rabies_titre_test_required: bool
    notes: Optional[str] = None


class BreedCheckResponse(BaseModel):
    breed: str
    destination_code: str
    is_restricted: bool
    restriction_note: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/pet-restrictions", response_model=PetRestrictionsResponse)
def get_pet_restrictions(
    destination_code: str = Query(..., description="ISO-2 country code, e.g. JP"),
):
    """
    GAP 6: Return pet import rules for a destination country.

    Enables the S1n household builder to validate breed + destination combinations
    server-side instead of using hardcoded client arrays.
    """
    code = destination_code.upper().strip()

    # Try DB first
    db_row = _fetch_from_db(code)
    if db_row:
        return db_row

    # Fallback to hardcoded data
    quarantine_info = _QUARANTINE_COUNTRIES.get(code)
    restricted_breeds = _RESTRICTED_BREEDS_BY_COUNTRY.get(code, _RESTRICTED_BREEDS_GLOBAL)

    # EU countries generally accept EU pet passport
    eu_countries = {
        "DE", "FR", "ES", "IT", "NL", "BE", "AT", "PT", "PL", "SE", "DK", "FI",
        "IE", "LU", "GR", "CZ", "SK", "HU", "RO", "BG", "HR", "SI", "EE", "LV",
        "LT", "MT", "CY", "NO", "IS", "LI",
    }
    is_eu = code in eu_countries

    rabies_titre_required = code in {"GB", "AU", "JP", "NZ", "SG", "TW", "HK", "FJ", "HI"}

    notes = None
    if code == "US":
        notes = "No federal breed ban; check local/municipal ordinances at destination city."
    elif code == "SG":
        notes = "Only specific dog breeds are approved for import into Singapore. Check AVS approved list."

    return PetRestrictionsResponse(
        destination_code=code,
        quarantine_required=quarantine_info is not None,
        quarantine_days=quarantine_info["quarantine_days"] if quarantine_info else 0,
        import_permit_required=quarantine_info["permit_required"] if quarantine_info else not is_eu,
        restricted_breeds=restricted_breeds,
        estimated_cost_range=quarantine_info.get("estimated_cost_range") if quarantine_info else None,
        eu_pet_passport_accepted=is_eu,
        microchip_required=True,  # Required virtually everywhere
        rabies_vaccination_required=True,
        rabies_titre_test_required=rabies_titre_required,
        notes=notes,
    )


@router.get("/pet-restrictions/breed-check", response_model=BreedCheckResponse)
def check_breed(
    breed: str = Query(..., description="Dog breed name"),
    destination_code: str = Query(..., description="ISO-2 country code"),
):
    """Quick check: is this breed restricted at this destination?"""
    code = destination_code.upper().strip()
    breed_norm = breed.strip()

    restricted = _RESTRICTED_BREEDS_BY_COUNTRY.get(code, _RESTRICTED_BREEDS_GLOBAL)
    is_restricted = any(
        breed_norm.lower() in r.lower() or r.lower() in breed_norm.lower()
        for r in restricted
    )
    return BreedCheckResponse(
        breed=breed_norm,
        destination_code=code,
        is_restricted=is_restricted,
        restriction_note=(
            f"{breed_norm} is on the restricted breed list for {code}. "
            "Import may be refused or require special permits."
        ) if is_restricted else None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# DB helper (reads from pet_restrictions table if it exists)
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_from_db(code: str) -> Optional[PetRestrictionsResponse]:
    try:
        from ..services.supabase_client import get_supabase_admin_client
        sb = get_supabase_admin_client()
        result = (
            sb.table("pet_restrictions")
            .select("*")
            .eq("destination_code", code)
            .maybe_single()
            .execute()
        )
        if result and result.data:
            row = result.data
            return PetRestrictionsResponse(
                destination_code=row["destination_code"],
                quarantine_required=row.get("quarantine_required", False),
                quarantine_days=row.get("quarantine_days", 0),
                import_permit_required=row.get("import_permit_required", False),
                restricted_breeds=row.get("restricted_breeds") or [],
                estimated_cost_range=row.get("estimated_cost_range"),
                eu_pet_passport_accepted=row.get("eu_pet_passport_accepted", False),
                microchip_required=row.get("microchip_required", True),
                rabies_vaccination_required=row.get("rabies_vaccination_required", True),
                rabies_titre_test_required=row.get("rabies_titre_test_required", False),
                notes=row.get("notes"),
            )
    except Exception:
        logger.debug("pet_restrictions table not available, using fallback data")
    return None
