"""
City activity suggestions (AIQ-1581).

Generates a short, seasonally-neutral list of "things to do" for a destination
city using the existing LLM client — NOT a live web-search integration (that
would add a new sub-processor + DPA obligations, which is out of scope here).

City and country are non-personal, so no PII masking is required. The single
public entry point is intentionally fail-soft: any error (missing API key,
timeout, malformed output) returns an empty list so the Resources page degrades
gracefully instead of surfacing an error.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from .llm_client import complete

log = logging.getLogger(__name__)

# The system prompt is a STATIC template (never interpolate user input here — see
# llm_client security note). City/country go in the user message only.
_SYSTEM_PROMPT = (
    "You are a local-mobility concierge helping a relocating employee settle into a "
    "new city. Suggest genuinely useful, well-known things to do — a mix of landmarks, "
    "neighbourhoods, cultural spots, outdoor activities, markets and family-friendly "
    "options. Keep suggestions evergreen and season-neutral (nothing tied to a specific "
    "date or one-off event). Each suggestion needs a short, factual title and a one- or "
    "two-sentence description. Do not invent addresses, prices, opening hours or URLs. "
    "Return between 5 and 8 suggestions."
)

# OpenAI structured-output schema (strict mode: every property required,
# additionalProperties false).
_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "activities": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "category": {
                        "type": "string",
                        "description": "One of: landmark, culture, outdoor, food, family, neighbourhood, shopping, nightlife",
                    },
                },
                "required": ["title", "description", "category"],
            },
        }
    },
    "required": ["activities"],
}

_MAX_ACTIVITIES = 8


async def get_city_activities(city: str, country: str) -> List[Dict[str, str]]:
    """Return ~5-8 activity suggestions for (city, country).

    Fail-soft: returns [] on any error so the caller can return a 200 with an
    empty feed. ``city`` and ``country`` are non-personal and used as-is.
    """
    city = (city or "").strip()
    country = (country or "").strip()
    if not city and not country:
        return []

    where = ", ".join(p for p in (city, country) if p) or "the destination"
    user_msg = (
        f"Suggest things to do in {where}. "
        "Give a varied mix a newcomer would appreciate in their first months."
    )

    try:
        result = await complete(system=_SYSTEM_PROMPT, user=user_msg, schema=_SCHEMA)
    except Exception as exc:  # noqa: BLE001 — deliberate fail-soft degrade
        log.warning("city_activities llm_failed where=%s error=%s", where, exc)
        return []

    raw = result.get("activities") if isinstance(result, dict) else None
    if not isinstance(raw, list):
        return []

    activities: List[Dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        description = str(item.get("description") or "").strip()
        category = str(item.get("category") or "").strip()
        if not title:
            continue
        activities.append(
            {"title": title, "description": description, "category": category}
        )
        if len(activities) >= _MAX_ACTIVITIES:
            break

    return activities
