"""Applicability matcher for `requirement_facts.applies_to` (the System-A serving path).

`compute_requirements_sufficiency` decides which approved facts apply to a mover by matching
each fact's `applies_to` against a profile snapshot. The original matcher required the snapshot
to equal EVERY key in `applies_to`. That breaks on two counts for Otto's scope-annotated batches:

  1. `applies_to` carries provenance/metadata keys the snapshot never has — `persona`, `topic`,
     `corridor`, `nationality_scope_basis`, `assertion_mode`, `conditional_on`, `non_obvious`,
     `needs_lawyer_review`, `quote_*`. Treating them as filters drops the fact entirely.
  2. `nationality` is stored on the fact as a CLASS label ("non-EEA") but on the snapshot as a
     COUNTRY ("Venezuela"). Equality can never hold; and a rule scoped `non-EEA` only because that
     is the batch's AUDIENCE (`nationality_scope_basis: "audience_scope"`) must still reach an
     EEA mover — hiding it is the exact mis-serve the S1 audit exists to prevent.

This module fixes both: only a small allow-list of keys gates applicability, and `nationality`
gates only when the rule is genuinely `nationality_determined`, comparing CLASS to CLASS via
`nationality_class` (the same logic System B already uses). It is dependency-free (only
`nationality_class`) so it is unit-testable without the DB-backed service.
"""
from __future__ import annotations

from typing import Any, Dict

from .nationality_class import EU_EEA, THIRD_COUNTRY, classify_best

# The ONLY applies_to keys that gate applicability. Everything else a batch carries is
# provenance/metadata and must never filter a fact out.
TARGETING_KEYS = ("nationality", "status", "employee_profile")

# Otto's nationality vocabulary -> nationality_class.classify() output.
_NAT_LABEL_TO_CLASS = {
    "non-EEA": THIRD_COUNTRY,
    "non-EU": THIRD_COUNTRY,
    "EEA": EU_EEA,
    "EU": EU_EEA,
}


def nationality_applies(applies_to: Dict[str, Any], snapshot: Dict[str, Any]) -> bool:
    """Whether a fact's nationality scope admits this mover.

    `audience_scope` rules are nationality-neutral in law — they apply to everyone on the
    corridor; `nationality` there records the batch's audience, not a restriction. Only
    `nationality_determined` rules gate on nationality, and they gate by CLASS
    (EU_EEA / THIRD_COUNTRY / OWN_NATIONAL), never by raw country string. Fail OPEN on any
    unknown (unrecognised label or unrecognised mover nationality): we suppress a requirement
    only when we positively know it does not apply — never fabricate a "nothing required".
    """
    if applies_to.get("nationality_scope_basis") == "audience_scope":
        return True
    want = applies_to.get("nationality")
    if not want:
        return True
    want_class = _NAT_LABEL_TO_CLASS.get(str(want))
    if want_class is None:
        return True  # unknown label -> do not hide (caller may log)
    mover_class = classify_best(
        (snapshot.get("nationality"), snapshot.get("second_nationality")),
        snapshot.get("destination_country"),
    )
    if mover_class is None:
        return True  # unknown mover nationality -> show (anti-silence contract)
    return mover_class == want_class


def apply_applies_to(applies_to: Dict[str, Any], snapshot: Dict[str, Any]) -> bool:
    """True if a fact whose scope is `applies_to` applies to a mover described by `snapshot`.

    Only TARGETING_KEYS gate; metadata keys are ignored. `nationality` is delegated to
    `nationality_applies`. `status` / `employee_profile` gate only when the snapshot actually
    carries the field (fail OPEN when it does not — the snapshot has no `status` today, so that
    key is a no-op until it does, rather than silently dropping every scoped fact).
    Note: `assertion_mode: conditional` is deliberately NOT a targeting key — a conditional
    fact still APPLIES; it is the rendering layer's job to present it conditionally.
    """
    if not applies_to:
        return True
    for key in TARGETING_KEYS:
        if key not in applies_to:
            continue
        if key == "nationality":
            if not nationality_applies(applies_to, snapshot):
                return False
            continue
        snap_val = snapshot.get(key)
        if snap_val is not None and snap_val != applies_to[key]:
            return False
    return True
