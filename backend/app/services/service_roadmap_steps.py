"""Deterministic per-service roadmap step library.

Maps a service_key (as used by the Service providers tab / case_services) to an
ordered list of concrete real-world steps. Pure data + helpers — no DB, no I/O —
so it unit-tests trivially and is safe to import anywhere.

`phase` aligns with the relocation plan view phases:
  pre_departure | during | arrival
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ServiceStep:
    key: str           # stable within a service; used to build milestone_type
    title: str
    description: str
    phase: str         # pre_departure | during | arrival
    sort_offset: int   # ordering within the service cluster


SERVICE_STEPS: Dict[str, List[ServiceStep]] = {
    "immigration": [
        ServiceStep("embassy_appt", "Book consular/embassy appointment",
                    "Schedule your visa or permit appointment at the relevant consulate or embassy.",
                    "pre_departure", 10),
        ServiceStep("gather_docs", "Gather visa/permit documents",
                    "Collect the documents required for your visa or residence permit application.",
                    "pre_departure", 20),
        ServiceStep("submit_application", "Submit application",
                    "Submit your visa or permit application.", "pre_departure", 30),
        ServiceStep("biometrics", "Attend biometrics appointment",
                    "Attend the biometrics/identity appointment if required.", "during", 40),
        ServiceStep("collect_permit", "Collect residence permit",
                    "Collect your residence permit once approved.", "arrival", 50),
    ],
    "schools": [
        ServiceStep("shortlist", "Shortlist schools",
                    "Identify suitable schools near your destination.", "pre_departure", 10),
        ServiceStep("contact_admissions", "Contact school admissions",
                    "Reach out to admissions offices about availability and requirements.",
                    "pre_departure", 20),
        ServiceStep("submit_applications", "Submit school applications",
                    "Apply to your shortlisted schools.", "pre_departure", 30),
        ServiceStep("confirm_enrolment", "Confirm enrolment",
                    "Confirm your child's place and enrolment.", "arrival", 40),
    ],
    "housing": [
        ServiceStep("criteria", "Define housing search criteria",
                    "Set budget, area, size and must-haves for your home search.", "pre_departure", 10),
        ServiceStep("quote", "Request & compare housing quotes",
                    "Request and compare offers from housing providers.", "pre_departure", 20),
        ServiceStep("viewings", "Attend viewings",
                    "View shortlisted properties.", "during", 30),
        ServiceStep("sign_lease", "Sign lease",
                    "Sign your rental or purchase agreement.", "arrival", 40),
    ],
    "banking": [
        ServiceStep("appt", "Book account-opening appointment",
                    "Schedule an appointment to open a local bank account.", "arrival", 10),
        ServiceStep("open_account", "Open local bank account",
                    "Open your local account and set up transfers.", "arrival", 20),
    ],
    "movers": [
        ServiceStep("quote", "Request & compare moving quotes",
                    "Request and compare quotes from international movers.", "pre_departure", 10),
        ServiceStep("book_mover", "Book mover",
                    "Confirm and book your chosen moving company.", "pre_departure", 20),
        ServiceStep("pack_ship", "Pack & ship household goods",
                    "Pack and ship your belongings.", "during", 30),
    ],
    "tax": [
        ServiceStep("consult", "Book tax-advisor consultation",
                    "Arrange advice on cross-border and host-country tax.", "pre_departure", 10),
        ServiceStep("gather_docs", "Gather income/residency documents",
                    "Collect documents your tax advisor will need.", "pre_departure", 20),
    ],
    "language": [
        ServiceStep("choose_course", "Choose a language course",
                    "Pick a course that fits your level and schedule.", "arrival", 10),
        ServiceStep("enrol", "Enrol in language course",
                    "Enrol and book your first lessons.", "arrival", 20),
    ],
    "spouse": [
        ServiceStep("career_consult", "Partner career consultation",
                    "Arrange a career consultation for your partner.", "arrival", 10),
        ServiceStep("cv_review", "CV / credentials review",
                    "Review and adapt your partner's CV and credentials for the local market.",
                    "arrival", 20),
    ],
    "temp": [
        ServiceStep("book_temp", "Book temporary accommodation",
                    "Arrange a place to stay on arrival before permanent housing.",
                    "pre_departure", 10),
    ],
    "pets": [
        ServiceStep("vet_docs", "Vet health check & documents",
                    "Complete the vet checks and paperwork for pet relocation.", "pre_departure", 10),
        ServiceStep("book_transport", "Book pet transport",
                    "Arrange your pet's transport to the destination.", "pre_departure", 20),
    ],
}

# Aliases so callers using a different vocabulary still resolve (serviceConfig
# uses 'banks'/'temp_accommodation'/'visa').
_SERVICE_ALIASES: Dict[str, str] = {
    "banks": "banking",
    "temp_accommodation": "temp",
    "visa": "immigration",
    "immigration_support": "immigration",
}


def _canonical_service_key(service_key: str) -> str:
    key = (service_key or "").strip().lower()
    return _SERVICE_ALIASES.get(key, key)


def steps_for_service(service_key: str) -> List[ServiceStep]:
    """Steps for a service_key (alias-aware). Unknown key -> []."""
    return SERVICE_STEPS.get(_canonical_service_key(service_key), [])


# Maps a quote_requests.service_categories[] label to a service_key. Labels come
# from the frontend serviceConfig; match on a lowercased keyword so minor label
# drift still resolves.
_CATEGORY_KEYWORDS = [
    ("housing", "housing"),
    ("school", "schools"),
    ("childcare", "schools"),
    ("immigration", "immigration"),
    ("visa", "immigration"),
    ("permit", "immigration"),
    ("mover", "movers"),
    ("moving", "movers"),
    ("bank", "banking"),
    ("tax", "tax"),
    ("language", "language"),
    ("spouse", "spouse"),
    ("partner", "spouse"),
    ("temporary", "temp"),
    ("pet", "pets"),
]


def service_key_for_category(category: str) -> Optional[str]:
    """Resolve a service-category label to a service_key, or None if unknown."""
    label = (category or "").strip().lower()
    if not label:
        return None
    for keyword, key in _CATEGORY_KEYWORDS:
        if keyword in label:
            return key
    return None
