"""Frame-based NLG — slot-filled, pre-vetted templates for incident/case reports.

Parker NLG approach #9 (frame-based). Each event type has a registered Frame
template with a fixed set of required slots. Rendering fills the slots into
vetted wording — deterministic and schema-validated, which is what incident /
compliance reports need (no LLM paraphrase drift). Dates and numbers are
formatted with the stdlib; an optional `translate` callable lets a caller route
the rendered string through the Step-I translation layer once it merges.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable, Dict, Mapping, Optional, Sequence


class FrameError(ValueError):
    """Base class for frame rendering errors."""


class UnknownFrameError(FrameError):
    """Raised when no template is registered for an event type."""


class MissingSlotError(FrameError):
    """Raised when a required slot is absent from a Frame."""


@dataclass(frozen=True)
class Frame:
    """A structured event ready for rendering. `slots` carries the fill values."""

    event_type: str
    slots: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class _Template:
    required: Sequence[str]
    # `text` is a str.format template over the (formatted) slot values.
    text: str
    translation_key: str


# Pre-vetted templates. Wording here is reviewed copy — do not let an LLM rewrite it.
_REGISTRY: Dict[str, _Template] = {
    "passport_expiry_at_risk": _Template(
        required=("employee_name", "passport_country", "expiry_date", "days_left"),
        text=(
            "{employee_name}'s {passport_country} passport expires on {expiry_date} "
            "({days_left} days away), which is inside the renewal buffer required for "
            "their assignment. Initiate renewal now to avoid travel disruption."
        ),
        translation_key="frame.passport_expiry_at_risk",
    ),
    "assignment_milestone_missed": _Template(
        required=("employee_name", "milestone", "due_date", "days_overdue"),
        text=(
            "The '{milestone}' milestone for {employee_name} was due on {due_date} and "
            "is now {days_overdue} days overdue. Review the case to unblock the next step."
        ),
        translation_key="frame.assignment_milestone_missed",
    ),
    "policy_change_required": _Template(
        required=("company_name", "category", "reason", "effective_date"),
        text=(
            "A policy change is required for {company_name} in the {category} category: "
            "{reason}. The update should take effect by {effective_date}."
        ),
        translation_key="frame.policy_change_required",
    ),
    "supplier_unresponsive": _Template(
        required=("supplier_name", "service", "days_silent", "case_ref"),
        text=(
            "Supplier {supplier_name} has not responded on the {service} request for case "
            "{case_ref} in {days_silent} days. Escalate or reassign to keep the case moving."
        ),
        translation_key="frame.supplier_unresponsive",
    ),
}


def registered_event_types() -> Sequence[str]:
    return tuple(_REGISTRY.keys())


def translation_key_for(event_type: str) -> str:
    template = _REGISTRY.get(event_type)
    if template is None:
        raise UnknownFrameError(f"No frame registered for event type '{event_type}'")
    return template.translation_key


def _format_value(value: object, *, locale: str) -> str:
    if isinstance(value, (datetime, date)):
        # ISO date is locale-neutral and unambiguous for compliance reports.
        d = value.date() if isinstance(value, datetime) else value
        return d.isoformat()
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        # Thousands grouping; locales that use '.' as the separator swap it.
        grouped = f"{value:,}"
        if locale.split("-")[0] in ("de", "fr", "es", "it", "nl"):
            grouped = grouped.replace(",", ".")
        return grouped
    if isinstance(value, float):
        rounded = round(value, 2)
        return str(int(rounded)) if rounded == int(rounded) else f"{rounded:.2f}"
    return str(value)


def render(
    frame: Frame,
    *,
    locale: str = "en",
    translate: Optional[Callable[[str], str]] = None,
) -> str:
    """Render a Frame to a deterministic, slot-validated string.

    Raises ``UnknownFrameError`` for an unregistered event type and
    ``MissingSlotError`` when a required slot is absent. ``translate`` (optional)
    post-processes the rendered string — e.g. the Step-I translation layer.
    """
    template = _REGISTRY.get(frame.event_type)
    if template is None:
        raise UnknownFrameError(f"No frame registered for event type '{frame.event_type}'")

    missing = [slot for slot in template.required if slot not in frame.slots]
    if missing:
        raise MissingSlotError(
            f"Frame '{frame.event_type}' is missing required slot(s): {', '.join(missing)}"
        )

    formatted = {
        key: _format_value(frame.slots[key], locale=locale) for key in template.required
    }
    rendered = template.text.format(**formatted)
    if translate is not None:
        rendered = translate(rendered)
    return rendered
