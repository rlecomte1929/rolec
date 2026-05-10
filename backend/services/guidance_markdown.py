from typing import Any, Dict, List


def render_guidance_markdown(
    snapshot: Dict[str, Any],
    plan: Dict[str, Any],
    checklist: Dict[str, Any],
    sources: List[Dict[str, Any]],
    coverage: Dict[str, Any],
) -> str:
    origin = snapshot.get("origin_country") or "Unknown"
    destination = snapshot.get("destination_country") or "Unknown"
    move_date = snapshot.get("move_date") or "Unknown"

    lines: List[str] = []
    lines.append("# Relocation Guidance – Grounded Pack")
    lines.append("")
    lines.append("## 1. Overview of your move")
    lines.append(f"- Origin: {origin}")
    lines.append(f"- Destination: {destination}")
    lines.append(f"- Target move date: {move_date}")
    lines.append("")
    lines.append("## 2. What official sources cover (high-level)")
    lines.append("This pack summarizes only curated, official sources. Please confirm details with your employer and the official agencies.")
    lines.append("")
    lines.append("## 3. Action plan (phased)")
    for item in plan.get("items", []):
        lines.append(f"- **{item.get('phase')} / {item.get('category')}**: {item.get('title')}")
        lines.append(f"  - {item.get('description_md')}")
    lines.append("")
    lines.append("## 4. Condensed checklist")
    for item in checklist.get("items", []):
        due = item.get("due_date") or item.get("relative_to_move") or "Timing to be confirmed"
        lines.append(f"- {item.get('title')} — {due}")
        lines.append(f"  - {item.get('description')}")
    lines.append("")
    lines.append("## 5. Sources (official links)")
    for s in sources:
        title = s.get("title") or s.get("url")
        lines.append(f"- {title}: {s.get('url')}")
    lines.append("")
    lines.append("## 6. Assumptions & Not covered")
    score = coverage.get("score", 0)
    domains = coverage.get("domains_covered", [])
    missing = coverage.get("missing_info", [])
    not_covered = coverage.get("not_covered", [])
    guidance_mode = coverage.get("guidance_mode")
    baseline_injected = coverage.get("baseline_injected_count", 0)

    lines.append(f"Coverage score: {score}/100")
    lines.append(f"Domains covered: {', '.join(domains) if domains else 'None'}")
    lines.append("")
    if missing:
        lines.append("Missing information to refine:")
        for item in missing:
            lines.append(f"- {item}")
        lines.append("")
    if not_covered:
        lines.append("Not covered / confirm:")
        for item in not_covered:
            lines.append(f"- {item}")
    else:
        if baseline_injected:
            lines.append("Some steps are based on general baseline guidance due to limited profile specificity.")
        else:
            lines.append("No gaps identified based on current curated knowledge packs.")
    lines.append("")
    if guidance_mode == "strict":
        lines.append("Strict mode: output includes only matched curated rules.")
        lines.append("")
    lines.append("## Disclaimer")
    lines.append("This guidance is informational only and does not constitute legal, tax, or immigration advice. Always confirm with official sources and your employer.")
    lines.append("")
    return "\n".join(lines)
