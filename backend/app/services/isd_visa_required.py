"""Does a national of X need an Irish visa to land in Ireland?

`corridors/ES_IE/pathways/CSEP_2026/v1.yaml` declares this as
``visa_required_nationality``, ``source: EXTERNAL_LOOKUP``,
``lookup: isd_visa_required.{nationality_iso}``. Until now that lookup did not exist, so
`roadmap_corridor_overlay` emitted an *unasserted* advisory — "if your nationality is on
Ireland's visa-required list … check with Irish Immigration Service Delivery". For a
Venezuelan moving Madrid→Dublin that is the single question the whole corridor turns on, and
the product answered it by telling her to go and ask someone else.

**Reads a committed artifact, never the network.** `docs/imports/ie-isd-visa-required-2026-08-22/`
holds the transcription plus a manifest recording its source, retrieval date and sha256. The
served path must never make an HTTP call at request time, and the answer must stay diffable.

THE THREE-VALUED CONTRACT, WHICH IS THE POINT OF THIS MODULE.

``visa_required()`` returns ``True`` / ``False`` / ``None``, and ``None`` is not a failure —
it is the honest answer for an input we cannot resolve. The published page states the exempt
list *positively* and never publishes its complement, so "absent from the table" is only a
sound inference once the input is a real ISO code. An unrecognised nationality string is not
evidence of anything, and returning ``True`` for it would manufacture a visa requirement out
of a typo.

WHAT AN ISO CODE CANNOT ANSWER. Two of Ireland's three exemptions are not nationality-based:
a residence card held as the family member of an EEA/Swiss citizen exercising free movement,
and the UK short-stay visa waiver. A person this module calls visa-required may hold one and
be exempt. `exemptions_not_resolvable_from_nationality()` exists so callers can say that out
loud instead of over-asserting — it is the difference between "you need a visa" and "you need
a visa unless one of these applies to you".

That distinction is live for the case this was built for. Andrea is Venezuelan, in Spain, with
a **Macedonian** spouse: both visa-required, no carve-out. Had her spouse been French, the
same facts would have made her visa-exempt.

PRECLEARANCE IS A SEPARATE AXIS. A visa-*exempt* spouse of a Critical Skills permit holder
must still obtain preclearance before travelling. `preclearance_required()` answers that
independently, because reading "no visa needed" and booking a flight is exactly how that one
bites — and no `requirement_items` row in the Irish catalog mentions preclearance at all
(0 of 42, measured 2026-08-22).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from .nationality_class import _nationality_to_iso  # normaliser of record; reused, not re-rolled

#: repo_root/docs/imports/<batch>/isd_visa_required.json
_ARTIFACT = (
    Path(__file__).resolve().parents[3]
    / "docs" / "imports" / "ie-isd-visa-required-2026-08-22" / "isd_visa_required.json"
)

#: EEA + Switzerland + UK: exempt as a matter of citizenship, and already the answer
#: `nationality_class.classify` gives for the free-movement question. Kept here because the
#: artifact states it as its own exemption and this module must be answerable standalone.
_EEA_UK_CH = frozenset({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE",
    "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
    "IS", "LI", "NO", "CH", "GB",
})


@lru_cache(maxsize=1)
def _data() -> Dict[str, Any]:
    return json.loads(_ARTIFACT.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _visa_free_isos() -> frozenset:
    return frozenset(
        str(e["iso"]).upper() for e in _data()["visa_free_nationalities"] if e.get("iso")
    )


@lru_cache(maxsize=1)
def _name_to_iso() -> Dict[str, str]:
    """The artifact's own names, so "Brazil" resolves and not only "BR".

    `nationality_class._COUNTRY_NAME` is a deliberately small hand-grown map — it holds
    the free-movement set plus the handful of others a real case has needed. Most of the
    45 exempt nationalities here are absent from it, so without this index "Brazil",
    "Japan" and "Uruguay" would all return None and the lookup would answer almost
    nothing. The artifact is the authority for its own rows, so it is the right place to
    read those names from; anything outside it still goes through the shared normaliser.
    """
    return {
        str(e["name"]).strip().upper(): str(e["iso"]).upper()
        for e in _data()["visa_free_nationalities"]
        if e.get("iso") and e.get("name")
    }


def _to_iso(nationality: Optional[str]) -> Optional[str]:
    iso = _nationality_to_iso(nationality)
    if iso:
        return iso.upper()
    if nationality:
        return _name_to_iso().get(str(nationality).strip().upper())
    return None


def visa_required(nationality: Optional[str]) -> Optional[bool]:
    """True / False / None — see the module docstring on why None is a real answer.

    ``None`` means "we could not resolve this nationality", never "no". Callers must not
    coerce it: `bool(None)` is False, which would silently tell a visa-required national
    that they need nothing.
    """
    iso = _to_iso(nationality)
    if not iso:
        return None
    if iso in _EEA_UK_CH or iso in _visa_free_isos():
        return False
    return True


def exemptions_not_resolvable_from_nationality() -> List[Dict[str, str]]:
    """The exemptions a nationality alone cannot settle, for callers to surface verbatim."""
    return [
        {"key": e["key"], "quote": e["quote"], "note": e.get("note", "")}
        for e in _data()["structural_exemptions"]
        if not e.get("resolvable_from_iso")
    ]


def preclearance_required(nationality: Optional[str], *, relationship: Optional[str]) -> Optional[bool]:
    """Whether preclearance is needed despite any visa exemption.

    `relationship` is the mover's tie to the person already in Ireland — the artifact's
    `applies_to` vocabulary (e.g. ``csep_holder_spouse_or_partner``). Returns None when the
    relationship is unknown, because this rule is defined by the relationship, not the
    passport; guessing it would be inventing the very requirement we are trying to surface.
    """
    if not relationship:
        return None
    rule = _data()["preclearance_required_even_if_visa_exempt"]
    if relationship not in rule["applies_to"]:
        return False
    iso = _to_iso(nationality)
    if iso and iso in {c.upper() for c in rule["excluded_nationalities"]}:
        return False
    return True


def source() -> Dict[str, str]:
    """Provenance for anything that renders this answer to a person."""
    primary = _data()
    return {
        "url": primary["source_url"],
        "name": primary["source_name"],
        "retrieved_at": primary["retrieved_at"],
        "verification_status": primary["verification_status"],
    }
