"""
GAP 4: Advisor matching — POST /api/advisors/match
                          GET  /api/advisors/{advisor_id}

Matches immigration advisors to a relocation corridor (origin + destination country).

Priority order:
  1. Preferred advisors stored in `preferred_advisors` Supabase table for the company
  2. Platform-wide advisors from `immigration_advisors` table filtered by corridor
  3. Curated hardcoded fallback list when DB tables are unavailable (dev / local)

Response includes: name, firm, specialisms, corridor coverage, rating, languages,
verified badge, contact_url, and whether they are the company's preferred advisor.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..auth_deps import get_current_user

router = APIRouter(prefix="/api/advisors", tags=["advisors"])
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Curated fallback advisor list (used when DB is unavailable / empty)
# ─────────────────────────────────────────────────────────────────────────────

_FALLBACK_ADVISORS: List[Dict[str, Any]] = [
    {
        "id": "adv-global-immigration-001",
        "name": "Helena Morrow",
        "firm": "Global Immigration Partners",
        "title": "Senior Immigration Counsel",
        "specialisms": ["EU work permits", "intra-company transfers", "family visas"],
        "corridors": [],  # empty = global coverage
        "languages": ["en", "fr", "de"],
        "rating": 4.9,
        "rating_count": 142,
        "verified": True,
        "preferred_partner": True,
        "contact_url": "https://globalimmigrationpartners.example.com",
        "response_sla": "24 hours",
        "logo_initials": "HM",
    },
    {
        "id": "adv-eu-mobility-002",
        "name": "Lars Vantine",
        "firm": "EU Mobility Advisors",
        "title": "EU Free Movement Specialist",
        "specialisms": ["EU Blue Card", "schengen long-stay", "digital nomad visas"],
        "corridors": ["EU", "DE", "FR", "NL", "BE", "ES", "PT", "IT", "AT"],
        "languages": ["en", "de", "nl"],
        "rating": 4.7,
        "rating_count": 98,
        "verified": True,
        "preferred_partner": False,
        "contact_url": "https://eumobility.example.com",
        "response_sla": "48 hours",
        "logo_initials": "LV",
    },
    {
        "id": "adv-apac-immigration-003",
        "name": "Priya Kamath",
        "firm": "APAC Relocation Legal",
        "title": "APAC Immigration Director",
        "specialisms": ["Singapore EP", "Australia TSS", "Japan work visa", "HK IANG"],
        "corridors": ["SG", "AU", "JP", "HK", "MY", "IN", "KR"],
        "languages": ["en", "hi", "zh"],
        "rating": 4.8,
        "rating_count": 76,
        "verified": True,
        "preferred_partner": True,
        "contact_url": "https://apacrelocationlegal.example.com",
        "response_sla": "24 hours",
        "logo_initials": "PK",
    },
    {
        "id": "adv-uk-immigration-004",
        "name": "James Whitfield",
        "firm": "Whitfield Immigration Law",
        "title": "UK Visa & Immigration Solicitor",
        "specialisms": ["UK Skilled Worker", "Global Talent", "ILR", "British citizenship"],
        "corridors": ["GB"],
        "languages": ["en"],
        "rating": 4.6,
        "rating_count": 211,
        "verified": True,
        "preferred_partner": False,
        "contact_url": "https://whitfieldimmigration.example.com",
        "response_sla": "48 hours",
        "logo_initials": "JW",
    },
    {
        "id": "adv-americas-immigration-005",
        "name": "Sofia Delgado",
        "firm": "Delgado & Associates",
        "title": "US & Canada Immigration Attorney",
        "specialisms": ["US H-1B", "L-1 intracompany", "Canada LMIA", "TN visa"],
        "corridors": ["US", "CA", "MX"],
        "languages": ["en", "es"],
        "rating": 4.7,
        "rating_count": 134,
        "verified": True,
        "preferred_partner": False,
        "contact_url": "https://delgadoimmigration.example.com",
        "response_sla": "48 hours",
        "logo_initials": "SD",
    },
]

# Country → continent/region mapping for broader corridor matching
_REGION_MAP: Dict[str, str] = {
    "DE": "EU", "FR": "EU", "NL": "EU", "BE": "EU", "ES": "EU", "PT": "EU",
    "IT": "EU", "AT": "EU", "SE": "EU", "DK": "EU", "FI": "EU", "IE": "EU",
    "PL": "EU", "CZ": "EU", "HU": "EU", "RO": "EU", "LU": "EU", "CH": "EU",
    "NO": "EU", "SG": "APAC", "AU": "APAC", "JP": "APAC", "HK": "APAC",
    "MY": "APAC", "IN": "APAC", "KR": "APAC", "NZ": "APAC", "TH": "APAC",
    "US": "AMERICAS", "CA": "AMERICAS", "MX": "AMERICAS", "BR": "AMERICAS",
    "GB": "UK",
}


# ─────────────────────────────────────────────────────────────────────────────
# Response models
# ─────────────────────────────────────────────────────────────────────────────

class AdvisorProfile(BaseModel):
    id: str
    name: str
    firm: str
    title: Optional[str] = None
    specialisms: List[str] = []
    languages: List[str] = []
    rating: Optional[float] = None
    rating_count: int = 0
    verified: bool = False
    preferred_partner: bool = False
    preferred_for_company: bool = False
    contact_url: Optional[str] = None
    response_sla: Optional[str] = None
    logo_initials: str = ""


class AdvisorMatchResponse(BaseModel):
    origin_country: Optional[str]
    destination_country: Optional[str]
    advisors: List[AdvisorProfile]
    total: int


class AdvisorMatchRequest(BaseModel):
    origin_country: Optional[str] = None
    destination_country: Optional[str] = None
    purpose: Optional[str] = None
    case_id: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _advisor_matches_corridor(advisor: Dict[str, Any], dest: str, origin: str) -> bool:
    """True if the advisor covers the destination corridor (or has global coverage)."""
    corridors = advisor.get("corridors") or []
    if not corridors:
        return True  # global coverage
    dest_upper = (dest or "").upper()
    origin_upper = (origin or "").upper()
    dest_region = _REGION_MAP.get(dest_upper, "")
    return (
        dest_upper in corridors
        or dest_region in corridors
        or origin_upper in corridors
    )


def _get_preferred_advisor_ids_for_company(company_id: str) -> set:
    """Return set of advisor IDs that are preferred for this company."""
    try:
        from ..services.supabase_client import get_supabase_admin_client
        sb = get_supabase_admin_client()
        result = (
            sb.table("preferred_advisors")
            .select("advisor_id")
            .eq("company_id", company_id)
            .execute()
        )
        if result and result.data:
            return {row["advisor_id"] for row in result.data if row.get("advisor_id")}
    except Exception:
        logger.debug("Could not fetch preferred advisors for company %s", company_id)
    return set()


def _get_db_advisors(dest: str, origin: str, purpose: str) -> List[Dict[str, Any]]:
    """Attempt to fetch advisors from Supabase immigration_advisors table."""
    try:
        from ..services.supabase_client import get_supabase_admin_client
        sb = get_supabase_admin_client()
        result = (
            sb.table("immigration_advisors")
            .select("*")
            .eq("active", True)
            .execute()
        )
        if result and result.data:
            return result.data
    except Exception:
        logger.debug("immigration_advisors table not available, using fallback")
    return []


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/match", response_model=AdvisorMatchResponse)
def match_advisors(
    body: AdvisorMatchRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    GAP 4: Return immigration advisors matched to a relocation corridor.

    Matching logic:
      1. Try Supabase `immigration_advisors` table filtered to corridor
      2. Fall back to curated hardcoded list if DB is unavailable / empty
      3. Mark advisors as preferred_for_company if in `preferred_advisors` table
      4. Sort: preferred_for_company first, then preferred_partner, then by rating desc
    """
    dest = (body.destination_country or "").upper().strip()
    origin = (body.origin_country or "").upper().strip()
    purpose = (body.purpose or "employment").lower()

    company_id = str(user.get("company") or user.get("company_id") or "")
    preferred_ids = _get_preferred_advisor_ids_for_company(company_id) if company_id else set()

    # Try DB first, fall back to hardcoded list
    raw_advisors = _get_db_advisors(dest, origin, purpose)
    if not raw_advisors:
        raw_advisors = _FALLBACK_ADVISORS

    # Filter by corridor relevance
    matched = [a for a in raw_advisors if _advisor_matches_corridor(a, dest, origin)]

    # Build response objects
    advisors: List[AdvisorProfile] = []
    for a in matched:
        aid = a.get("id", "")
        advisors.append(AdvisorProfile(
            id=aid,
            name=a.get("name", ""),
            firm=a.get("firm", a.get("company", "")),
            title=a.get("title"),
            specialisms=a.get("specialisms") or [],
            languages=a.get("languages") or [],
            rating=a.get("rating"),
            rating_count=a.get("rating_count", 0),
            verified=bool(a.get("verified")),
            preferred_partner=bool(a.get("preferred_partner")),
            preferred_for_company=aid in preferred_ids,
            contact_url=a.get("contact_url"),
            response_sla=a.get("response_sla"),
            logo_initials=a.get("logo_initials") or _initials(a.get("name", "")),
        ))

    # Sort: company preferred first, then platform preferred, then rating desc
    advisors.sort(key=lambda a: (
        0 if a.preferred_for_company else (1 if a.preferred_partner else 2),
        -(a.rating or 0),
    ))

    return AdvisorMatchResponse(
        origin_country=body.origin_country,
        destination_country=body.destination_country,
        advisors=advisors,
        total=len(advisors),
    )


@router.get("/{advisor_id}", response_model=AdvisorProfile)
def get_advisor(
    advisor_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """GAP 4: Fetch a single advisor profile by ID."""
    # Try DB first
    try:
        from ..services.supabase_client import get_supabase_admin_client
        sb = get_supabase_admin_client()
        result = sb.table("immigration_advisors").select("*").eq("id", advisor_id).maybe_single().execute()
        if result and result.data:
            a = result.data
            company_id = str(user.get("company") or user.get("company_id") or "")
            preferred_ids = _get_preferred_advisor_ids_for_company(company_id) if company_id else set()
            return AdvisorProfile(
                id=a.get("id", ""),
                name=a.get("name", ""),
                firm=a.get("firm", a.get("company", "")),
                title=a.get("title"),
                specialisms=a.get("specialisms") or [],
                languages=a.get("languages") or [],
                rating=a.get("rating"),
                rating_count=a.get("rating_count", 0),
                verified=bool(a.get("verified")),
                preferred_partner=bool(a.get("preferred_partner")),
                preferred_for_company=a.get("id") in preferred_ids,
                contact_url=a.get("contact_url"),
                response_sla=a.get("response_sla"),
                logo_initials=a.get("logo_initials") or _initials(a.get("name", "")),
            )
    except Exception:
        pass

    # Try fallback
    for a in _FALLBACK_ADVISORS:
        if a["id"] == advisor_id:
            fields = {k: a.get(k) for k in AdvisorProfile.model_fields if k != "preferred_for_company"}
            fields["preferred_for_company"] = False
            return AdvisorProfile(**fields)

    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Advisor not found")


def _initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    return "".join(p[0].upper() for p in parts[:2])
