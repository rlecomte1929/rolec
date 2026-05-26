"""
Structured human-readable rendering for canonical company policy data.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List


PHASE_LABELS = {
    "pre_assignment": "Pre-Assignment",
    "on_assignment": "Assignment",
    "repatriation": "Post-Assignment",
    "ongoing": "Ongoing",
    "exception": "Exceptions",
    "unspecified": "General",
}


def _format_value(fact: Dict[str, Any]) -> str:
    if fact.get("amount") is not None:
        currency = str(fact.get("currency") or "").strip()
        freq = str(fact.get("frequency") or "").replace("_", " ").strip()
        base = f"{currency} {fact['amount']}".strip()
        return f"{base} ({freq})" if freq else base
    if fact.get("percentage") is not None:
        return f"{fact['percentage']}%"
    if fact.get("quantity") is not None:
        return str(fact["quantity"])
    if fact.get("duration_value") is not None:
        unit = str(fact.get("duration_unit") or "").strip()
        return f"{fact['duration_value']} {unit}".strip()
    if fact.get("value_text"):
        return str(fact["value_text"])
    return "See source text"


def _format_eligibility(fact: Dict[str, Any]) -> str:
    eligibility = fact.get("eligibility_json") or {}
    parts: List[str] = []
    assignment_types = fact.get("assignment_types_json") or eligibility.get("assignment_types") or []
    if assignment_types:
        parts.append("Assignment type: " + ", ".join(str(item).replace("_", " ") for item in assignment_types))
    family_statuses = eligibility.get("family_statuses") or []
    if family_statuses:
        parts.append("Family status: " + ", ".join(str(item) for item in family_statuses))
    min_duration = eligibility.get("min_duration_months")
    if min_duration is not None:
        parts.append(f"Minimum duration: {min_duration} months")
    notes = str(eligibility.get("notes") or "").strip()
    if notes:
        parts.append(notes)
    return "; ".join(parts) if parts else "No explicit eligibility conditions captured."


def render_canonical_policy_markdown(
    document: Dict[str, Any],
    facts: Iterable[Dict[str, Any]],
) -> str:
    grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for fact in facts:
        phase = str(fact.get("phase") or "unspecified")
        category = str(fact.get("benefit_category") or "miscellaneous")
        grouped[phase][category].append(fact)

    title = str(document.get("title") or document.get("filename") or "Company Policy")
    version = str(document.get("version_label") or "").strip()
    header = f"# {title}" + (f" ({version})" if version else "")
    lines = [
        header,
        "",
        f"Company: `{document.get('company_id')}`",
        "",
    ]
    ordered_phases = ["pre_assignment", "on_assignment", "repatriation", "ongoing", "exception"]
    for phase in ordered_phases + [p for p in grouped.keys() if p not in ordered_phases]:
        categories = grouped.get(phase, {})
        lines.append(f"## {PHASE_LABELS.get(phase, phase.replace('_', ' ').title())}")
        lines.append("")
        if not categories:
            lines.append("No canonical facts captured for this phase yet.")
            lines.append("")
            continue
        for category, rows in sorted(categories.items()):
            lines.append(f"### {category.replace('_', ' ').title()}")
            lines.append("")
            for fact in rows:
                title_line = str(fact.get("title") or fact.get("description") or category).strip()
                source = str(fact.get("canonical_policy_document_chunk_id") or "")
                lines.append(f"- **{title_line}**: {_format_value(fact)}")
                lines.append(f"  Eligibility: {_format_eligibility(fact)}")
                if source:
                    lines.append(f"  Source: `{source}`")
            lines.append("")
    if len(lines) <= 4:
        lines.append("No canonical policy facts are available for rendering.")
    return "\n".join(lines).strip() + "\n"
