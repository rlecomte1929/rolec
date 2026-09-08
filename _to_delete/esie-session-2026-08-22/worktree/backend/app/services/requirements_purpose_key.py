"""Single source of truth for the requirements catalog's PURPOSE key.

The sibling of `requirements_country_key` — same job, the other half of the
catalog key. `crud.list_requirements` matches purpose with `==` and no
normalisation, and the catalog is seeded with only four values
({employment, other, study, family} — the union of the three seed YAMLs, and
exactly `public_corridor._VALID_PURPOSES`).

Nothing validated the field. `schemas.py` declares `purpose: Optional[str] = None`
and the case router copies it verbatim into the column, so whatever an intake
sends becomes the lookup key. Three separate intakes emit three different
vocabularies, and production ended up storing this:

    work 238 | lta 218 | permanent 27 | transfer 27 | repatriation 27 |
    domestic 26 | sta 26 | Employment 26 | LTA 1

616 of 780 cases — 79% — matched nothing and got an EMPTY requirements list. On
that screen, empty means "nothing is required of you". A silent lookup miss was
making a legal claim.

The field is carrying three orthogonal axes that the schema already has homes for:

    1. purpose         (why)              -> {employment, other, study, family}
    2. assignment type (how long)         -> assignmentContext.assignmentType
    3. move type       (crosses a border) -> wizard_cases.move_type

`lta`/`sta`/`permanent` are axis 2. `domestic`/`repatriation` are axis 3. They
leaked into axis 1 because nothing stopped them. This module maps everything back
onto axis 1, and hands axis-2 values back to the caller so the STA waiver logic —
which has never once fired in production — can start working.

Like `to_iso`, `to_purpose` returns None for an unrecognised value ON PURPOSE, so
callers fail closed (surface "not covered") instead of querying with a bad key and
letting the empty result read as "nothing required".
"""
from __future__ import annotations

from typing import Optional

# The catalog's own vocabulary. Identical to `public_corridor._VALID_PURPOSES`
# and to the union of purposes_by_country across the seed YAMLs. Not a fourth
# list — the same one, stated where the resolver can enforce it.
CANONICAL_PURPOSES = frozenset({"employment", "other", "study", "family"})

# Synonyms that mean a canonical purpose.
_SYNONYMS = {
    # `work` is what `backend/db/cases.py::_CASE_PURPOSE_MAP` calls employment —
    # and it is also that map's default for unknown/blank, which is why it is the
    # single largest bucket (238).
    "work": "employment",
    "job": "employment",
    "relocation": "employment",
    "employment_transfer": "employment",
    # Intra-company transfer. An ICT is a distinct visa route that the catalog does
    # NOT model — see KNOWN_CATALOG_GAPS below. Mapping it to `employment` serves
    # approximately-right requirements (an ICT still needs a work permit) rather
    # than an empty list, which would read as "nothing required". We are not
    # pretending to model the ICT route; we are refusing to stay silent about it.
    "transfer": "employment",
    "intracompany": "employment",
    "intra_company": "employment",
    "intra_company_transfer": "employment",
    "ict": "employment",
    # Axis 2 leaking into axis 1 — the relocation is still for employment; the
    # value is telling us how LONG, not WHY. `assignment_type_from_purpose`
    # recovers the part that would otherwise be lost.
    "lta": "employment",
    "sta": "employment",
    "permanent": "employment",
    # Axis 3 leaking into axis 1. These resolve so the catalog lookup has a key at
    # all, but a caller must check `is_in_country_move` FIRST — an in-country move
    # has no immigration requirements and must never be served a visa track.
    "domestic": "employment",
    "repatriation": "employment",
    # Other intake vocabularies seen in the wild.
    "family_join": "family",
    "family_reunification": "family",
    "student": "study",
    "work_permit": "employment",
    "eu_mobility": "employment",
    "self_employed": "employment",
    "remote": "employment",
    "remote_work": "employment",
}

# Purpose values that are really assignment types (axis 2).
_ASSIGNMENT_TYPES = {
    "lta": "LTA",
    "sta": "STA",
    "permanent": "PERMANENT",
}

# Values we resolve to `employment` while knowing the catalog has no route for
# them. Recorded so this is a stated approximation, not a silent one.
KNOWN_CATALOG_GAPS = frozenset({
    "transfer", "intracompany", "intra_company", "intra_company_transfer", "ict",
    "self_employed", "remote", "remote_work",
})


def _norm(raw: Optional[str]) -> str:
    return (raw or "").strip().lower()


def to_purpose(raw: Optional[str]) -> Optional[str]:
    """Resolve a case's purpose to the canonical catalog key.

    Accepts the canonical values, any casing ("Employment" — the live intake's
    <select> has no value= attributes, so it emits the option TEXT), and the
    synonyms above. Returns None when the value is empty or unrecognised, so the
    caller can fail closed rather than look up a bad key.

    Note `None` input is NOT the same as an unrecognised one: an absent purpose
    is handled by the caller's existing `or "employment"` default. This function
    only reports what it can resolve.
    """
    s = _norm(raw)
    if not s:
        return None
    if s in CANONICAL_PURPOSES:
        return s
    return _SYNONYMS.get(s)


def assignment_type_from_purpose(raw: Optional[str]) -> Optional[str]:
    """Recover axis 2 when the purpose field is carrying an assignment type.

    272 production cases store `lta`/`sta`/`permanent` as their purpose while
    `assignmentContext.assignmentType` sits empty — so the assignment-type gate
    and the STA waivers have never fired for any of them. Mapping the purpose and
    dropping this would be its own silent wrong answer: an STA case would be
    served the long-term-only requirements it should have had waived.

    Returns 'STA' | 'LTA' | 'PERMANENT', or None when the purpose is a real
    purpose and carries no assignment signal.
    """
    return _ASSIGNMENT_TYPES.get(_norm(raw))


def is_known_catalog_gap(raw: Optional[str]) -> bool:
    """True when we resolved this to `employment` but the catalog has no route
    modelled for it (e.g. an intra-company transfer). The guidance served is
    approximate — say so, don't imply precision we don't have."""
    return _norm(raw) in KNOWN_CATALOG_GAPS
