"""Household composition helpers shared by the roadmap builders.

[ANDREA-P1] The employee wizard writes ``familyMembers.maritalStatus`` in its own
vocabulary (``solo`` / ``partner`` / ``partner_kids`` / ``kids_only``). HR-side intake,
the contract-extraction prefill and API clients write plain values (``married``,
``single``) and populate ``spouse`` / ``children`` directly, and ``relocationBasics``
carries ``hasDependents``. Until 2026-09-12 every builder branched on the wizard
vocabulary alone, so a married mover with two children entered by HR got NO family
track, NO ``FAMILY_REGISTRATION`` corridor step and NO family advisory — the case that
surfaced on Andrea (ES→IE, spouse + two children) during the specialist dry-run.

These helpers read every signal the draft can carry and are the single place that
decides "is a partner moving" / "are children moving". Fail-safe: a missing or
malformed ``familyMembers`` block means solo.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

_PARTNER_STATUSES = frozenset({"partner", "partner_kids", "married", "civil_partnership", "couple"})
_KIDS_STATUSES = frozenset({"partner_kids", "kids_only"})
#: Statuses that positively state NOBODY else is moving. An explicit ``solo`` wins over a
#: stale ``spouse`` / ``children`` object left behind by an earlier wizard pass — the
#: wizard keeps those objects when the user flips back to "Moving solo".
_SOLO_STATUSES = frozenset({"solo", "single", "none", "alone"})


def _family(draft: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    fam = (draft or {}).get("familyMembers")
    return fam if isinstance(fam, dict) else {}


def _member_present(member: Any) -> bool:
    """A spouse/child object counts when it carries at least one non-empty value."""
    if not isinstance(member, dict):
        return False
    return any(v not in (None, "", [], {}) for v in member.values())


def _status(fam: Dict[str, Any]) -> str:
    return str(fam.get("maritalStatus") or "").strip().lower()


def has_partner(draft: Optional[Dict[str, Any]]) -> bool:
    fam = _family(draft)
    status = _status(fam)
    if status in _PARTNER_STATUSES:
        return True
    if status in _SOLO_STATUSES or status in _KIDS_STATUSES:
        return False  # explicit: no partner
    # Unknown / absent status: the spouse object itself is the signal.
    return _member_present(fam.get("spouse"))


def children_of(draft: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The children rows to render. A row exists because someone added a child, even
    when every field on it is still empty (HR intake before names are known), so
    entries are NOT filtered on content — only non-dict junk is dropped. Falls back
    to HR's ``knownFamily`` when the household block carries none."""
    fam = _family(draft)
    if _status(fam) in _SOLO_STATUSES:
        return []
    kids = fam.get("children")
    rows = [c for c in kids if isinstance(c, dict)] if isinstance(kids, list) else []
    if rows:
        return rows
    known = ((draft or {}).get("knownFamily") or {}).get("children") or []
    return [c for c in known if isinstance(c, dict)] if isinstance(known, list) else []


def has_children(draft: Optional[Dict[str, Any]]) -> bool:
    fam = _family(draft)
    status = _status(fam)
    if status in _KIDS_STATUSES:
        return True
    if status in _SOLO_STATUSES or status == "partner":
        return False  # explicit: no children
    return bool(children_of(draft))


def has_family_relocating(draft: Optional[Dict[str, Any]]) -> bool:
    """True when anyone besides the mover is relocating (partner or children).

    ``relocationBasics.hasDependents`` is honoured as a positive signal only — a
    ``False`` there never hides a spouse the household block names.
    """
    if has_partner(draft) or has_children(draft):
        return True
    basics = (draft or {}).get("relocationBasics") or {}
    return bool(basics.get("hasDependents")) and (_member_present(_family(draft).get("spouse")) or bool(children_of(draft)))


def display_name(name: Any, fallback: str) -> str:
    """A non-empty display name. HR intake stores ``fullName: null`` for members whose
    name is not known yet; ``dict.get(key, default)`` does NOT apply the default for an
    explicit null, which is how ``_initials(None)`` crashed the whole roadmap."""
    if isinstance(name, str) and name.strip():
        return name.strip()
    return fallback
