"""Pure extraction of relocation_cases route fields from a wizard draft.

AIQ-1311 PR2. The HR case overview (``hr_case_detail.get_case_overview``) reads
``origin_country_code`` / ``dest_country_code`` / ``corridor`` / ``target_start_date``
from ``relocation_cases``. This helper pulls those values out of a wizard draft's
``relocationBasics`` (camelCase preferred, snake_case tolerated) so the submit
promotion can denormalise them onto the row.

Pure (stdlib only) so it unit-tests in isolation, same as ``intake_completeness.py``.
"""
from datetime import date
from typing import Any, Dict, Optional


def _pick(basics: Dict[str, Any], *keys: str) -> Optional[str]:
    for k in keys:
        v = basics.get(k)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return None


def _iso_date(raw: Optional[str]) -> Optional[str]:
    """Keep only a parseable ISO yyyy-mm-dd (the column is DATE); else None."""
    if not raw:
        return None
    candidate = str(raw)[:10]
    try:
        date.fromisoformat(candidate)
    except (ValueError, TypeError):
        return None
    return candidate


def wizard_basics_to_route(basics: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Map a draft's ``relocationBasics`` to the relocation_cases route columns.

    Returns keys: origin_country, dest_country, origin_city, dest_city,
    target_start_date (ISO date string or None).
    """
    b = basics or {}
    return {
        "origin_country": _pick(b, "originCountry", "origin_country"),
        "dest_country": _pick(
            b, "destCountry", "destination_country", "hostCountry", "host_country"
        ),
        "origin_city": _pick(b, "originCity", "origin_city"),
        "dest_city": _pick(b, "destCity", "dest_city"),
        "target_start_date": _iso_date(
            _pick(b, "targetMoveDate", "target_date", "targetDate")
        ),
    }
