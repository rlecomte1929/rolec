from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Protocol
from urllib.parse import urlparse
import hashlib
import uuid
import json

from .. import crud
from ..db import SessionLocal


class ResearchProvider(Protocol):
    def search(self, query: str) -> List[Dict[str, str]]:
        ...

    def fetch(self, url: str) -> str:
        ...


@dataclass
class StubResearchProvider:
    def search(self, query: str) -> List[Dict[str, str]]:
        if "Singapore" in query:
            return [
                {"url": "https://www.mom.gov.sg/passes-and-permits", "title": "MOM Work Passes"},
                {"url": "https://www.ica.gov.sg/enter-transit-depart", "title": "ICA Entry Requirements"},
            ]
        if "United States" in query or "USA" in query:
            return [
                {"url": "https://travel.state.gov/content/travel/en/us-visas.html", "title": "US Visas"},
                {"url": "https://www.uscis.gov/working-in-the-united-states", "title": "USCIS Work Authorization"},
            ]
        if "Norway" in query:
            return [
                {"url": "https://www.udi.no/en/", "title": "UDI Immigration"},
                {"url": "https://www.skatteetaten.no/en/", "title": "Norwegian Tax Administration"},
            ]
        if "United Kingdom" in query or "UK" in query:
            return [
                {"url": "https://www.gov.uk/browse/visas-immigration", "title": "UK Visas & Immigration"},
                {"url": "https://www.gov.uk/government/organisations/uk-visas-and-immigration", "title": "UKVI"},
            ]
        return [
            {"url": "https://example.com/immigration", "title": "Immigration overview"},
            {"url": "https://example.com/relocation", "title": "Relocation checklist"},
        ]

    def fetch(self, url: str) -> str:
        return f"Stub content for {url}"


ALLOWED_DOMAINS = {
    "SG": ["mom.gov.sg", "ica.gov.sg", "iras.gov.sg", "gov.sg"],
    "US": ["uscis.gov", "travel.state.gov", "ssa.gov", "irs.gov", "cbp.gov"],
    "NO": ["udi.no", "skatteetaten.no"],
    "UK": ["gov.uk"],
}


def _is_official_domain(url: str, country_code: str) -> bool:
    host = urlparse(url).netloc.lower()
    allowed = ALLOWED_DOMAINS.get(country_code.upper(), [])
    return any(host.endswith(domain) for domain in allowed)


def run_country_research(dest_country: str, purpose: str, flags: Dict[str, str]) -> Dict[str, str]:
    provider: ResearchProvider = StubResearchProvider()
    query = f"{dest_country} relocation requirements {purpose}"
    results = provider.search(query)

    with SessionLocal() as db:
        profile = crud.upsert_country_profile(
            db,
            {
                "id": str(uuid.uuid4()),
                "country_code": dest_country.upper(),
                "last_updated_at": datetime.utcnow(),
                "confidence_score": 0.72,
                "notes": "Stub research provider results.",
            },
        )

        source_ids: List[str] = []
        for result in results:
            if not _is_official_domain(result["url"], dest_country.upper()):
                continue
            content = provider.fetch(result["url"])
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            candidate = crud.create_research_candidate(
                db,
                {
                    "id": str(uuid.uuid4()),
                    "country_code": profile.country_code,
                    "destination_country": profile.country_code,
                    "purpose": purpose,
                    "url": result["url"],
                    "title": result["title"],
                    "publisher_domain": result["url"].split("/")[2],
                    "retrieved_at": datetime.utcnow(),
                    "snippet": content[:140],
                    "notes": "Pending review – official source candidate.",
                    "status": "pending",
                    "content_hash": content_hash,
                },
            )
            source_ids.append(candidate.id)

        if flags.get("seed_curated") == "true":
            for result in results:
                if not _is_official_domain(result["url"], dest_country.upper()):
                    continue
                content = provider.fetch(result["url"])
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                record = crud.create_source_record(
                    db,
                    {
                        "id": str(uuid.uuid4()),
                        "country_code": profile.country_code,
                        "url": result["url"],
                        "title": result["title"],
                        "publisher_domain": result["url"].split("/")[2],
                        "retrieved_at": datetime.utcnow(),
                        "snippet": content[:140],
                        "content_hash": content_hash,
                    },
                )
                source_ids.append(record.id)

            for item in _default_requirements(dest_country.upper(), purpose, source_ids):
                crud.create_requirement_item(db, item)

    return {"status": "ok"}


def _default_requirements(dest_country: str, purpose: str, source_ids: List[str]) -> List[Dict[str, str]]:
    now = datetime.utcnow()
    # review_status MUST be set explicitly on every row. This is an automated producer:
    # `seed_demo_cases` re-runs it on every backend start (so every Render deploy) via
    # `run_country_research(..., {"seed_curated": "true"})`. `requirement_items.review_status`
    # DEFAULTS to 'approved' at the DB level (models.RequirementItem), so a payload that omits
    # it publishes unreviewed stub content to real users the instant it is inserted — and it
    # re-approves a row a reviewer has since demoted whenever the reseed hits the INSERT branch.
    # That is exactly what happened to SINGAPORE "Minimum lead time" (migration
    # 20261112000000 §2 demoted all three lead-time rows to 'pending'; this producer minted
    # it back at 'approved' + no citation, tripping the requirement-provenance guard on
    # 2026-09-09). Every other create_requirement_item producer already lands 'pending'
    # (seed_requirements.py, imports/otto/executor.py, scripts/seed_corridor_facts.py);
    # this one was the outlier. New rows wait for an admin at /admin/countries before serving;
    # `_apply_requirement_item_update` deliberately never syncs review_status, so a reseed
    # leaves an already-reviewed row untouched.
    requirements = [
        {
            "id": str(uuid.uuid4()),
            "country_code": dest_country,
            "purpose": purpose,
            "pillar": "IDENTITY",
            "title": "Valid passport (6+ months)",
            "description": "Passport must be valid for at least 6 months beyond entry.",
            "severity": "BLOCKER",
            "owner": "EMPLOYEE",
            "required_fields_json": json.dumps(["employeeProfile.passportExpiry"]),
            "citations_json": json.dumps(source_ids[:1]),
            "review_status": "pending",
            "last_verified_at": now,
        },
        {
            "id": str(uuid.uuid4()),
            "country_code": dest_country,
            "purpose": purpose,
            "pillar": "EMPLOYMENT",
            "title": "Employment letter",
            "description": "Provide an employment confirmation letter.",
            "severity": "WARN",
            "owner": "EMPLOYEE",
            "required_fields_json": json.dumps(["assignmentContext.employerName", "assignmentContext.jobTitle"]),
            "citations_json": json.dumps(source_ids[:1]),
            "review_status": "pending",
            "last_verified_at": now,
        },
        {
            "id": str(uuid.uuid4()),
            "country_code": dest_country,
            "purpose": purpose,
            "pillar": "TIMELINE",
            "title": "Minimum lead time",
            "description": "Submit documents at least 30 days before start date.",
            "severity": "WARN",
            "owner": "HR",
            "required_fields_json": json.dumps(["assignmentContext.contractStartDate"]),
            "citations_json": json.dumps(source_ids[:2]),
            "review_status": "pending",
            "last_verified_at": now,
        },
    ]
    return requirements
