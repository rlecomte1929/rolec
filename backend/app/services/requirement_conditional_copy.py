"""Render a requirement's condition and its easy-to-miss flag — AIQ-1969.

A requirement the catalog knows is *conditional* must never be served as a flat claim. The
case that named this card: Andrea (ES→IE, EEA national) being told **"you are exempt from
Emergency Tax"**. Relief is conditional — on holding a PPS number *and* the employer operating
a correct RPN. Rendered flat, she expects a normal first payslip and may instead be taxed at
40% from the first run, which is the exact opposite of the guidance's promise.

The catalog already carries the signal. `applies_to` on Otto's facts holds `assertion_mode`,
`conditional_on` and `non_obvious`; `requirement_items` carries `non_obvious` as a column. What
was missing was anything that *renders* it — so a conditional fact and an unconditional one
reached the reader looking identical.

WHY THIS MODULE IS DEPENDENCY-FREE
----------------------------------
Two serving surfaces need it — `roadmap_requirement_copy.enrich_milestones_with_requirements`
(the plan view) and the sufficiency serializer's `supporting_requirements` (the dossier) — and
they sit in different layers. A pure function with no DB, no network and no LLM import can be
called from both, unit-tested without fixtures, and stays trivially inside the
serving/LLM-isolation closure that `scripts/check_serving_llm_isolation.py` enforces.

It also **fails safe in the dangerous direction**. Where the mode says `conditional` but no
condition was recorded, it does not fall back to the bare body — that would restate the claim
as unconditional fact, which is the bug. It hedges instead, and `build_render_flags` marks the
condition unverified so the UI can style it as such.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

#: Lead-in for a recorded condition. Prose, not a bare "if" — the employee reads this.
CONDITION_LEAD = "Applies only if:"

#: Lead-in when the fact is flagged conditional but the condition was never recorded.
#: Deliberately says what is unknown rather than inventing a plausible condition.
UNVERIFIED_CONDITION_LEAD = (
    "This does not apply in every case, and the exact condition is not recorded — check before "
    "relying on it."
)

#: Prefix for a `non_obvious` fact. Matches the "Easy to miss" pill in RequirementList.tsx.
EASY_TO_MISS_LEAD = "Easy to miss:"

#: The only value that means "conditional". Anything else — including None, an unrecognised
#: string, or Otto's older records that omit the key — is treated as unconditional, because a
#: mode we cannot read is not evidence of a condition.
_CONDITIONAL = "conditional"


def _clean(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def is_conditional(assertion_mode: Any = None, conditional_on: Any = None) -> bool:
    """True when the fact carries a condition, by either signal.

    `conditional_on` alone counts. Otto's records carry the condition text more consistently
    than the mode flag, and dropping a recorded condition because its sibling field was absent
    is the same silent flattening this module exists to stop.
    """
    return _clean(assertion_mode).lower() == _CONDITIONAL or bool(_clean(conditional_on))


def build_render_flags(
    assertion_mode: Any = None,
    conditional_on: Any = None,
    non_obvious: Any = False,
) -> Dict[str, Any]:
    """Structured signals for the UI, so the frontend styles rather than parses strings.

    `conditionVerified` is False when the fact says it is conditional but no condition text
    exists — the UI should surface that as a caveat, never hide it.
    """
    condition = _clean(conditional_on)
    conditional = is_conditional(assertion_mode, conditional_on)
    return {
        "isConditional": conditional,
        "conditionText": condition or None,
        # A non-conditional fact is trivially "verified": there is no condition to record.
        "conditionVerified": bool(condition) if conditional else True,
        "easyToMiss": bool(non_obvious),
    }


def render_requirement_copy(
    description: Any,
    *,
    assertion_mode: Any = None,
    conditional_on: Any = None,
    non_obvious: Any = False,
) -> str:
    """The description an employee should read, with its condition and easy-to-miss lead.

    Idempotent: re-running it over already-rendered copy adds nothing, because the overlay can
    run more than once over the same milestone.
    """
    body = _clean(description)
    if not body:
        return ""

    condition = _clean(conditional_on)
    conditional = is_conditional(assertion_mode, conditional_on)

    if conditional:
        if condition:
            # Skip when the body already states the condition — otherwise the reader gets the
            # same clause twice, which reads like two different requirements.
            already = condition.lower() in body.lower()
            if not already and CONDITION_LEAD not in body:
                body = f"{body}\n\n{CONDITION_LEAD} {condition}"
        elif UNVERIFIED_CONDITION_LEAD not in body:
            body = f"{body}\n\n{UNVERIFIED_CONDITION_LEAD}"

    if non_obvious and not body.startswith(EASY_TO_MISS_LEAD):
        body = f"{EASY_TO_MISS_LEAD} {body}"

    return body


def render_from_item(item: Any) -> str:
    """Convenience for a DTO/ORM row carrying the fields under either naming convention.

    `requirements_builder` emits camelCase DTOs; the sufficiency serializer emits snake_case
    dicts. Both reach the same renderer rather than each growing its own copy of these rules.
    """

    def pick(*names: str, default: Optional[Any] = None) -> Any:
        for name in names:
            if isinstance(item, dict):
                if item.get(name) is not None:
                    return item[name]
            elif getattr(item, name, None) is not None:
                return getattr(item, name)
        return default

    return render_requirement_copy(
        pick("description", "fact_text", default=""),
        assertion_mode=pick("assertionMode", "assertion_mode"),
        conditional_on=pick("conditionalOn", "conditional_on"),
        non_obvious=pick("nonObvious", "non_obvious", default=False),
    )
