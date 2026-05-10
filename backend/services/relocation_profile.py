from typing import Optional, List, Dict


class RelocationProfile(dict):
    origin_country: Optional[str]
    destination_country: Optional[str]
    move_date: Optional[str]
    employment_type: Optional[str]
    employer_country: Optional[str]
    works_remote: Optional[bool]
    has_corporate_tax_support: Optional[bool]
    notes: Optional[str]


def compute_missing_fields(profile: Dict) -> List[str]:
    required = [
        "origin_country",
        "destination_country",
        "employment_type",
    ]

    recommended = [
        "move_date",
        "employer_country",
    ]

    missing = []

    for field in required:
        if not profile.get(field):
            missing.append(field)

    return missing
