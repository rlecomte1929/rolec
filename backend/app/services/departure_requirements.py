"""Departure (home-country exit) requirements → pre-departure roadmap steps.

Surfaces a mover's home-country EXIT obligations into the pre-departure track for a
corridor whose pathway authors no origin-exit steps (ES→IE's CSEP is Ireland-arrival
only). Reads the APPROVED origin-country requirement_items — ``crud.list_requirements``
is THE publication gate, so nothing unreviewed leaks — and returns lightweight records
for ``roadmap_builder`` to shape into pre-departure steps.

**Direction gate — requirement_items are destination/arrival-framed.** A row keyed on
country X states what you do when X is your DESTINATION (register on the padrón, enrol in
social security, get a health card). Read naively, an origin-country row inverts: serving
Spain's arrival rows as Andrea's *departure* steps would tell her to REGISTER in the
country she is LEAVING. Direction is carried in the id — ``<C>:<ORIGIN>-<DEST>:<key>``
(``ES:IE-ES:empadronamiento_...`` is the IE→ES corridor, Spain the DESTINATION). A row is
a genuine exit obligation only when the mover's origin is its corridor's ORIGIN
(``ES:ES-IE:...``); reverse-corridor rows and un-parseable ids are withheld. Until a
corridor-tagged departure batch lands, this correctly returns nothing and the generic
pre-departure skeleton stands.

Deterministic and dependency-light (crud + the country/purpose/nationality resolvers),
so it never widens the serving/LLM-isolation closure. Fail-safe by construction: any
missing input or DB issue returns ``[]``.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .. import crud
from . import nationality_class
from .requirements_country_key import resolve_catalog_country, to_iso_alpha2
from .requirements_purpose_key import to_purpose

log = logging.getLogger(__name__)

#: A requirement id's corridor segment: ``<ORIGIN>-<DEST>`` in ISO alpha-2.
_CORRIDOR_SEG = re.compile(r"^([A-Za-z]{2})-([A-Za-z]{2})$")


#: Otto's loader (``backend/imports/otto/executor.promote``) writes UUID ids but stamps every
#: citation with the batch's ``applies_to.corridor`` (``"ES->IE"``). That is the same
#: direction signal the id carries for hand-authored rows, so accept it as a fallback
#: rather than silently withholding every machine-promoted departure batch.
_CITATION_CORRIDOR = re.compile(r"^\s*([A-Za-z]{2})\s*(?:->|-|\u2192)\s*([A-Za-z]{2})\s*$")


def _citation_origin_iso(citations_json: Any) -> Optional[str]:
    """ORIGIN ISO from the ``corridor`` key on any citation, or ``None``."""
    if not citations_json:
        return None
    try:
        citations = json.loads(citations_json) if isinstance(citations_json, str) else citations_json
    except (TypeError, ValueError):
        return None
    if not isinstance(citations, list):
        return None
    for cite in citations:
        if not isinstance(cite, dict):
            continue
        m = _CITATION_CORRIDOR.match(str(cite.get("corridor") or ""))
        if m:
            return m.group(1).upper()
    return None


def _row_origin_iso(row: Any) -> Optional[str]:
    """Direction of a requirement row: the id's corridor segment, else its citations'."""
    from_id = _corridor_origin_iso(getattr(row, "id", "") or "")
    if from_id:
        return from_id
    return _citation_origin_iso(getattr(row, "citations_json", None))


def _corridor_origin_iso(row_id: str) -> Optional[str]:
    """The ORIGIN ISO of the corridor encoded in a requirement id, or ``None``.

    Ids are ``<COUNTRY>:<CORRIDOR>:<key>`` with ``<CORRIDOR>`` = ``<ORIGIN>-<DEST>``
    (``ES:IE-ES:empadronamiento_...`` → ``IE``). ``None`` when the second segment is not
    a ``<XX>-<YY>`` corridor (e.g. a topic-keyed id) — the caller treats that as
    undeterminable and withholds the row.
    """
    parts = (row_id or "").split(":")
    if len(parts) < 3:
        return None
    m = _CORRIDOR_SEG.match(parts[1])
    return m.group(1).upper() if m else None


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
        origin_iso = to_iso_alpha2(origin_raw)

        records: List[Dict[str, Any]] = []
        for r in rows:
            # DIRECTION GATE (see module docstring): keep a row only when the mover's
            # origin is its corridor's ORIGIN — a genuine EXIT obligation. A row where the
            # origin is the corridor's DESTINATION is reverse-corridor arrival-in-origin
            # content and would invert the meaning; un-parseable ids are withheld too. An
            # unresolved origin ISO withholds everything (fail-safe).
            if origin_iso is None or _row_origin_iso(r) != origin_iso:
                continue
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
