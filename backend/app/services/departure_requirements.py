"""Departure (home-country exit) requirements → pre-departure roadmap steps.

The mirror of ``requirements_builder``, keyed on the ORIGIN country. A mover's
home-country exit obligations — Spain's baja del padrón, the Seguridad Social baja,
the AEAT tax-exit — live in ``public.requirement_items`` too, keyed on the origin
country. Nothing served them: the requirements engine is destination-keyed
(``requirements_builder`` fetches by ``dest_country``) and the employee roadmap reads
the corridor *pathway* files, not the DB. So a corridor whose pathway authors no
origin-exit steps (ES→IE's CSEP is Ireland-arrival only) had no way to surface its
home-exit obligations even though they exist as researched, reviewed rows.

This reads the APPROVED origin-country requirement_items — ``crud.list_requirements``
is THE publication gate, so nothing unreviewed leaks — nationality-gates them the same
way the destination path does, and returns lightweight records for
``roadmap_builder`` to shape into pre-departure steps.

Deterministic and dependency-light (crud + the country/purpose/nationality resolvers),
so it never widens the serving/LLM-isolation closure. Fail-safe by construction: any
missing input or DB issue returns ``[]``, which leaves the generic pre-departure
skeleton exactly as it was.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .. import crud
from . import nationality_class
from .requirements_country_key import resolve_catalog_country
from .requirements_purpose_key import to_purpose

log = logging.getLogger(__name__)


def _mover_nationality(draft: Dict[str, Any]) -> Optional[str]:
    """The mover's nationality from whichever draft shape carries it."""
    for a, b in (("employeeProfile", "nationality"), ("primaryApplicant", "nationality"), ("employee", "nationality")):
        node = draft.get(a)
        if isinstance(node, dict) and node.get(b):
            return node.get(b)
    return None


def departure_requirement_records(db: Session, case: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Approved home-country exit requirements for a case, as lightweight records.

    Empty on any missing input, a same-country move, an unresolved origin, no approved
    rows, or a DB error — an absent list changes nothing, mirroring ``corridor_overlay``'s
    fail-safe. Nationality gating is fail-safe too: a row scoped to a class the mover is
    not (or a class we cannot resolve) is withheld rather than asserted.
    """
    try:
        draft = (case or {}).get("draft") or {}
        basics = draft.get("relocationBasics") or {}
        origin_raw = basics.get("originCountry") or basics.get("origin_country")
        dest_raw = basics.get("destCountry") or basics.get("dest_country")
        if not origin_raw:
            return []
        # A same-country move has no home to leave (mirrors _predeparture_track_applies).
        if dest_raw and str(origin_raw).strip().upper() == str(dest_raw).strip().upper():
            return []

        purpose = to_purpose(case.get("purpose") or basics.get("purpose") or "employment") or "employment"
        origin_country = resolve_catalog_country(origin_raw)
        if not origin_country:
            return []

        rows = crud.list_requirements(db, origin_country, purpose)  # approved only (the publication gate)
        if not rows:
            return []

        mover_class = nationality_class.classify(_mover_nationality(draft), origin_raw)

        records: List[Dict[str, Any]] = []
        for r in rows:
            nat_json = getattr(r, "applies_to_nationality_classes_json", None)
            classes = json.loads(nat_json) if nat_json else None
            # None ⇒ applies to all classes. A scoped row applies only when the mover's
            # resolved class is in it; an unresolved class withholds scoped rows.
            if classes is not None and (mover_class is None or mover_class not in classes):
                continue
            records.append({
                "id": r.id,
                "pillar": r.pillar,
                "title": (r.title or "").strip(),
                "description": (r.description or "").strip(),
                "non_obvious": bool(getattr(r, "non_obvious", False)),
                "timing": getattr(r, "timing", None),
            })
        return records
    except Exception:  # noqa: BLE001 — never break the employee roadmap
        log.warning("departure_requirement_records failed; pre-departure keeps its skeleton", exc_info=True)
        return []
