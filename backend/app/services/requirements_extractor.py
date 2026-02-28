from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any, Dict, List


KEYWORDS = {
    "immigration": ["apply", "eligib", "required", "petition", "visa", "form", "fee", "interview", "documents", "sponsor"],
    "registration": ["register", "arrival", "i-94", "ssn", "social security", "account", "online"],
    "tax": ["tax", "irs", "record", "withhold", "residency"],
    "other": ["must", "required", "need to"],
}


def _slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return value[:60] if value else "topic"


def _topic_key_from_url(url: str, destination_country: str, domain_area: str, title: str) -> str:
    lower = url.lower()
    if "travel.state.gov" in lower and "us-visas" in lower:
        return "us.visa_overview"
    if "cbp.gov" in lower and "i-94" in lower:
        return "us.i94"
    if "ssa.gov" in lower and "ssnumber" in lower:
        return "us.ssn"
    if "uscis.gov" in lower:
        return "us.uscis_overview"
    if "mom.gov.sg" in lower:
        return "sg.mom_overview"
    if "ica.gov.sg" in lower:
        return "sg.ica_overview"
    return f"{destination_country.lower()}.{_slugify(domain_area + '-' + title)}"


def _required_fields_from_text(text: str) -> List[str]:
    lower = text.lower()
    fields = []
    if "visa" in lower:
        fields.append("visa_type")
    if "passport" in lower:
        fields.extend(["passport_expiry_date", "nationality"])
    if "employer" in lower or "petition" in lower or "sponsor" in lower:
        fields.extend(["employer_country", "employment_type"])
    if "dependent" in lower:
        fields.append("dependents")
    return sorted(list(dict.fromkeys(fields)))


def extract_requirements_from_doc(
    doc: Dict[str, Any],
    destination_country: str,
    domain_area: str,
) -> Dict[str, Any]:
    content = doc.get("content_excerpt") or ""
    sentences = re.split(r"(?<=[.!?])\s+", content)
    keywords = KEYWORDS.get(domain_area, KEYWORDS["other"])
    facts = []
    for sentence in sentences:
        if not sentence:
            continue
        lower = sentence.lower()
        if not any(k in lower for k in keywords):
            continue
        fact_type = "other"
        if any(k in lower for k in ["must", "required", "need to"]):
            fact_type = "document"
        if any(k in lower for k in ["apply", "submit", "file"]):
            fact_type = "step"
        if any(k in lower for k in ["within", "before", "no later than", "deadline"]):
            fact_type = "deadline"
        text = sentence.strip()
        if len(text) > 220:
            text = text[:220].rstrip() + "..."
        key_seed = " ".join(text.split()[:6])
        fact_key = _slugify(key_seed) + "-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:6]
        facts.append(
            {
                "id": str(uuid.uuid4()),
                "fact_type": fact_type,
                "fact_key": fact_key,
                "fact_text": text,
                "applies_to": {},
                "required_fields": _required_fields_from_text(text),
                "evidence_quote": text[:250],
                "confidence": "low" if len(text) < 60 else "medium",
            }
        )
        if len(facts) >= 25:
            break
    if not facts:
        facts.append(
            {
                "id": str(uuid.uuid4()),
                "fact_type": "other",
                "fact_key": "insufficient-detail",
                "fact_text": "Insufficient detail; verify page manually.",
                "applies_to": {},
                "required_fields": [],
                "evidence_quote": None,
                "confidence": "low",
            }
        )
    return {
        "entity": {
            "topic_key": _topic_key_from_url(doc.get("source_url", ""), destination_country, domain_area, doc.get("title", "")),
            "title": doc.get("title") or doc.get("source_url"),
        },
        "facts": facts,
    }
