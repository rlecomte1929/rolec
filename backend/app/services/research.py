from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Protocol
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
            "last_verified_at": now,
        },
    ]
    return requirements
