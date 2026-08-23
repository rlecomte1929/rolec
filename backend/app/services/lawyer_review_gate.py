"""Does this requirement carry an unresolved `needs_lawyer_review` flag?

ONE definition, because the flag is stored in two different shapes and a gate that
knows only one shape is not a gate.

  * `requirement_facts.applies_to`   — jsonb, flag at the top level.
  * `requirement_items.citations_json` — TEXT holding a JSON *array of citation
    objects*; the flag is parked INSIDE a citation object because the table has no
    column for it (`imports/otto/mappings.py:262`, `gen_ie_es_corridor_load.py`).

WHY IT MATTERS. `needs_lawyer_review: true` is the research pipeline saying "a lawyer
must look at this claim before anyone relies on it". Nothing enforced it. Measured on
production 2026-08-23:

    requirement_items   approved: 101, of which 4 flagged   <- already published
                        pending:  100, of which 8 flagged   <- next to be published
    requirement_facts   0 flagged in any status             <- preventive there

The 4 approved ones are all IRELAND/RESIDENCE on the ES->IE corridor — the first real
customer's corridor. They were approved 2026-08-21 12:02:59 UTC in one scripted call
covering 9 rows at an identical microsecond, so no human read them individually, and
the 4 that differed produced no warning (AIQ-2046).

THE GATE HAS AN EXIT, DELIBERATELY. A flag is not a permanent veto: it is satisfied by
`attestation_status='attested'`, the existing counsel-attestation axis (models.py:162 —
NULL/none -> requested -> attested -> stale, written only by the admin promote
endpoint). So the flag routes a claim into the lane built for it instead of dead-ending
it. Gating on nothing at all would have been the same mistake in the other direction.

Leaf module: stdlib only, so the gate can be imported by routers and by the db layer
without a cycle.
"""
from __future__ import annotations

import json
from typing import Any, Optional

FLAG = "needs_lawyer_review"

# The one value that discharges the flag. See models.py:162.
ATTESTED = "attested"


def _truthy(value: Any) -> bool:
    """JSON `true`, and the string spellings a TEXT column round-trips into.

    Deliberately narrow: only an explicit truth counts. An absent or unparseable
    flag is NOT treated as flagged — this gate blocks publication, so a parse
    failure must not silently freeze the whole review queue.
    """
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return False


def _walk(node: Any) -> bool:
    """Find the flag anywhere in a nested structure.

    Structural rather than positional on purpose. The flag sits at the top level in
    `applies_to` and one level down inside a citation object in `citations_json`, and
    it was moved once already because there is no column for it. A gate pinned to one
    path would go quietly blind the next time it moves.
    """
    if isinstance(node, dict):
        if FLAG in node and _truthy(node[FLAG]):
            return True
        return any(_walk(v) for v in node.values())
    if isinstance(node, (list, tuple)):
        return any(_walk(v) for v in node)
    return False


def carries_lawyer_review_flag(*blobs: Any) -> bool:
    """True when ANY of the given JSON blobs raises `needs_lawyer_review`.

    Accepts already-parsed structures and raw TEXT alike, so a caller does not have to
    know which of the two storage shapes it is holding. Unparseable text is skipped,
    not guessed at.
    """
    for blob in blobs:
        if blob is None:
            continue
        parsed: Any = blob
        if isinstance(blob, (str, bytes)):
            text = blob.strip()
            if not text:
                continue
            try:
                parsed = json.loads(text)
            except (ValueError, TypeError):
                continue
        if _walk(parsed):
            return True
    return False


def is_attested(attestation_status: Optional[str]) -> bool:
    """Whether counsel sign-off has actually been recorded."""
    return (attestation_status or "").strip().lower() == ATTESTED


def blocks_approval(*, attestation_status: Optional[str], blobs: tuple) -> bool:
    """The gate: flagged AND not attested."""
    return carries_lawyer_review_flag(*blobs) and not is_attested(attestation_status)
