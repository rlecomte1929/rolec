from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Depends

from ..db import SessionLocal
from ...database import db
from .. import crud, schemas
from ..services.research import run_country_research
import json

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _is_admin_user(user: dict) -> bool:
    role = (user.get("role") or "").upper()
    if role == "ADMIN":
        return True
    profile = db.get_profile_record(user.get("id"))
    if profile and (profile.get("role") or "").upper() == "ADMIN":
        return True
    email = (user.get("email") or "").strip().lower()
    if email.endswith("@relopass.com") and db.is_admin_allowlisted(email):
        return True
    return False


def require_admin(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.replace("Bearer ", "").strip()
    user = db.get_user_by_token(token)
    if not user or not _is_admin_user(user):
        raise HTTPException(status_code=403, detail="Admin only")
    return user


@router.get("/countries", response_model=schemas.CountryListDTO)
def list_countries(user: dict = Depends(require_admin)):
    with SessionLocal() as db:
        profiles = crud.list_country_profiles(db)
        items = []
        for profile in profiles:
            sources = crud.list_sources(db, profile.country_code)
            requirements = crud.list_requirements(db, profile.country_code)
            top_domains = list({source.publisher_domain for source in sources})[:3]
            items.append(
                schemas.CountryListItemDTO(
                    countryCode=profile.country_code,
                    lastUpdatedAt=profile.last_updated_at,
                    requirementsCount=len(requirements),
                    confidenceScore=profile.confidence_score,
                    topDomains=top_domains,
                )
            )
        return schemas.CountryListDTO(countries=items)


@router.get("/countries/{country_code}", response_model=schemas.CountryProfileDTO)
def get_country(country_code: str, user: dict = Depends(require_admin)):
    with SessionLocal() as db:
        profile = crud.get_country_profile(db, country_code.upper())
        if not profile:
            raise HTTPException(status_code=404, detail="Country not found")
        sources = crud.list_sources(db, profile.country_code)
        requirements = crud.list_requirements(db, profile.country_code)
        groups = {}
        for item in requirements:
            groups.setdefault(item.pillar, []).append(
                schemas.RequirementItemDTO(
                    id=item.id,
                    pillar=item.pillar,
                    title=item.title,
                    description=item.description,
                    severity=item.severity,
                    owner=item.owner,
                    requiredFields=json.loads(item.required_fields_json),
                    statusForCase="NEEDS_REVIEW",
                    citations=[],
                )
            )

        return schemas.CountryProfileDTO(
            countryCode=profile.country_code,
            lastUpdatedAt=profile.last_updated_at,
            confidenceScore=profile.confidence_score,
            sources=[schemas.SourceRecordDTO(
                id=source.id,
                url=source.url,
                title=source.title,
                publisherDomain=source.publisher_domain,
                retrievedAt=source.retrieved_at,
                snippet=source.snippet,
            ) for source in sources],
            requirementGroups=[{"pillar": pillar, "items": items} for pillar, items in groups.items()],
        )


@router.post("/countries/{country_code}/research/rerun")
def rerun_country(country_code: str, user: dict = Depends(require_admin), opts: Optional[dict] = None):
    run_country_research(country_code, (opts or {}).get("purpose", "employment"), {})
    return {"jobId": country_code.lower() + "-job"}
