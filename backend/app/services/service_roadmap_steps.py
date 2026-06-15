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


# Destination-specific EXTRA steps that augment the generic per-service steps.
# Keyed service_key -> destination ISO2 -> [ServiceStep]. Immigration is excluded
# on purpose — the AI roadmap generator already produces corridor-specific
# immigration steps. sort_offset slots each extra into the generic sequence.
SERVICE_STEPS_BY_DESTINATION: Dict[str, Dict[str, List[ServiceStep]]] = {
    "banking": {
        "DE": [
            ServiceStep("anmeldung", "Register your address (Anmeldung) first",
                        "German banks require an Anmeldung (address registration) confirmation to open an account.",
                        "arrival", 5),
        ],
    },
    "housing": {
        "DE": [
            ServiceStep("anmeldung", "Register your address (Anmeldung) at the Bürgeramt",
                        "Within ~2 weeks of moving in, register your address — it's needed for banking, tax ID and more.",
                        "arrival", 35),
        ],
    },
    "schools": {
        "DE": [
            ServiceStep("school_year_de", "Check the German school year & Schulpflicht",
                        "Schooling is compulsory (Schulpflicht); the school year starts in late summer — plan enrolment around it.",
                        "pre_departure", 5),
        ],
        "NO": [
            ServiceStep("school_year_no", "Check the Norwegian school year",
                        "The school year starts in mid-August; contact the local kommune about enrolment.",
                        "pre_departure", 5),
        ],
    },
    "pets": {
        "DE": [
            ServiceStep("import_de", "Prepare EU pet entry documents",
                        "For Germany (EU): microchip, valid rabies vaccination, and an EU pet passport or health certificate.",
                        "pre_departure", 5),
        ],
        "NO": [
            ServiceStep("import_no", "Meet Norway's pet import rules",
                        "Norway requires microchip, rabies vaccination, and (for dogs) tapeworm treatment 24–120h before arrival.",
                        "pre_departure", 5),
        ],
    },
    "movers": {
        "DE": [
            ServiceStep("customs_de", "Prepare EU customs/removal-goods paperwork",
                        "Moving within the EU is simpler; keep an inventory and proof of prior residence for removal-goods relief.",
                        "pre_departure", 5),
        ],
        "NO": [
            ServiceStep("customs_no", "Prepare Norwegian customs declaration",
                        "Norway is outside the EU customs union — you'll declare household goods; a moving-goods exemption may apply.",
                        "pre_departure", 5),
        ],
    },
}

# Minimal, self-contained country -> ISO2 normaliser (kept light so this pure
# module doesn't pull in the heavier country/RAG stacks). Covers the destinations
# we support plus ISO2 pass-through.
_DEST_NAME_TO_ISO = {
    "germany": "DE", "de": "DE", "deu": "DE",
    "norway": "NO", "no": "NO", "nor": "NO",
    "france": "FR", "fr": "FR",
    "india": "IN", "in": "IN",
}


def normalize_destination_iso(value: Optional[str]) -> Optional[str]:
    """Country name or code -> ISO2 (e.g. 'Germany'/'de' -> 'DE'). None if unknown."""
    if not value:
        return None
    raw = str(value).strip()
    hit = _DEST_NAME_TO_ISO.get(raw.lower())
    if hit:
        return hit
    return raw.upper() if len(raw) == 2 and raw.isalpha() else None


def destination_steps(service_key: str, dest_iso: Optional[str]) -> List[ServiceStep]:
    """Destination-specific extra steps for a service (alias-aware). [] if none."""
    if not dest_iso:
        return []
    by_dest = SERVICE_STEPS_BY_DESTINATION.get(_canonical_service_key(service_key))
    if not by_dest:
        return []
    return by_dest.get(dest_iso.upper(), [])


def steps_for_service_in_destination(service_key: str, dest_iso: Optional[str]) -> List[ServiceStep]:
    """Generic steps merged with the destination's extras, sorted by sort_offset."""
    merged = list(steps_for_service(service_key)) + destination_steps(service_key, dest_iso)
    return sorted(merged, key=lambda s: s.sort_offset)


# Maps a quote_requests.service_categories[] label to a service_key. Labels come
# from the frontend serviceConfig; match on a lowercased keyword so minor label
# drift still resolves.
_CATEGORY_KEYWORDS = [
    ("housing", "housing"),
    ("living", "housing"),  # Services tab calls housing "living_areas"
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
