"""Pure response-shaping for the DOC-1 corridor-requirements fallback.

Kept dependency-free (stdlib only) so it is unit-testable without the DB/app import
chain. The DB fetch that feeds it lives in ``corridor_requirements_service.py``; the
HR ``/api/hr/cases/{id}/immigration-requirements`` endpoint wires the two together.

Why a fallback exists (2026-08-22): the ``immigration_requirements`` document table has
no rows for some corridors that DO carry verified ``requirement_items`` content (e.g.
ES->IE, which the public ``/api/public/corridor-requirements`` endpoint already serves).
Rather than show HR "not covered", we surface that same corridor content here, clearly
marked as sourced from the corridor requirement set rather than an authored, apostille-
aware document checklist. No content is invented; this only reshapes rows a human seeded.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def map_corridor_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Map one ``requirement_items`` corridor obligation into the immigration-requirements
    response item shape. Additive keys (``source_kind``, ``description``, ``non_obvious``,
    ``timing``, ``sources``, ``*_status``) are ignored by older clients; ``source_kind``
    lets a caller tell these apart from an authored document checklist.
    """
    sources = item.get("sources") or []
    return {
        "document_type": item.get("category") or "corridor_requirement",
        "document_name": item.get("title"),
        "is_required": True,
        "freshness_days": None,
        "requires_apostille": False,
        "apostille_countries": [],
        "requires_translation": False,
        "translation_languages": [],
        "can_be_prefilled": False,
        "can_be_ocr_extracted": False,
        "typical_processing_days": None,
        "book_early_flag": bool(item.get("non_obvious")),
        "book_early_reason": item.get("timing"),
        "success_tips": [],
        "common_rejection_reasons": [],
        "form_url": sources[0] if sources else None,
        # --- additive, corridor-fallback-only fields ---
        "source_kind": "corridor_requirement",
        "description": item.get("description"),
        "non_obvious": bool(item.get("non_obvious")),
        "timing": item.get("timing"),
        "sources": sources,
        "verification_status": item.get("verification_status"),
        "attestation_status": item.get("attestation_status"),
    }


def build_covered_fallback(
    corridor_from: Optional[str],
    corridor_to: Optional[str],
    visa_type: Optional[str],
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build the covered response from corridor obligations. The document ``requirements``
    array is populated from ``items`` (so the existing HR panel and callers render them),
    but ``coverage_reason`` / ``is_fallback`` make the provenance explicit. The document
    checklist metadata (apostille/translation/timeline) is intentionally empty because no
    authored document checklist exists yet for this corridor.
    """
    reqs = [map_corridor_item(it) for it in (items or [])]
    return {
        "covered": True,
        "coverage_reason": "corridor_requirements_fallback",
        "is_fallback": True,
        "corridor": f"{corridor_from}→{corridor_to}",
        "corridor_from": corridor_from,
        "corridor_to": corridor_to,
        "visa_type": visa_type,
        "requirements": reqs,
        "risk_flags": [],
        "estimated_timeline_days": None,
        "document_count": len(reqs),
    }
