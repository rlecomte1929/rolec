"""Make the roadmap say "Anmeldung" instead of "host-country equivalents".

The employee roadmap is a generic operational template. For an EU national moving to
Germany it says:

    "Complete arrival registration"
        Local registration or residency steps required shortly after arrival.
    "Tax / local registration"
        Tax ID, social security, or host-country equivalents.

...while, for that exact case, the requirements dossier already knows precisely:

    "Residence registration (Anmeldung)"
        Register your home address at the local Bürgeramt, typically within 14 days
        of moving in; the confirmation (Meldebescheinigung) is needed for banking,
        tax ID and more.
    "Social security registration (Sozialversicherung)"
        The employer typically initiates this and a social security number is issued.

`requirement_items` was never read by the plan view — the single biggest
available-but-unused input the roadmap had.

WHY THIS ONLY REWRITES COPY, AND ADDS NO ROWS
---------------------------------------------
Adding requirement-derived milestones looked obvious and is a minefield:

  * An unregistered milestone_type is not dropped, but lands in `pre_departure` with
    sequence_in_phase=999 unless it contains the literal `_ai_` infix — and a task's
    SUGGESTED DUE DATE is derived from its phase, so a mis-phased Anmeldung also gets
    a nonsense date.
  * `upsert_case_milestone` is not an upsert (it branches on milestone_id; there is no
    ON CONFLICT), and two rows sharing a milestone_type silently COLLAPSE TO ONE in the
    view (`{t.task_code: t}`).
  * `persist_generated_milestones` deletes every milestone except source="service", so
    a source="requirement" row would be wiped by the next AI regeneration.
  * There is no title dedup anywhere, and service_roadmap_steps already ships its own
    Anmeldung step — so a new one would make three overlapping registration tasks.

Overriding the copy of the milestones that ALREADY exist sidesteps all four. The
roadmap keeps its structure (phases, owners, dependencies, dates) and gains the
specifics. It also fixes every existing case with no backfill, and stays in lockstep
with the catalog and the nationality gate for free — compute_case_requirements is
already nationality-gated, so an EU national sees "Valid passport or national identity
card" exactly where a third-country national sees "Valid passport (6+ months)".
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# (requirement_items.country_code, requirement title) -> the generic milestone whose
# copy it replaces.
#
# Keyed on TITLE, which is safe here because title is already load-bearing: the
# seeder's natural key is country_code + purpose + title and there is no delete path,
# so a changed title orphans its row. Titles are effectively immutable. A drifted one
# simply fails to match and the generic copy stays — it fails SAFE — and
# test_roadmap_requirement_copy asserts every key below exists in the seed YAMLs, so
# drift is loud rather than silent.
#
# Requirements with no generic counterpart (Mietvertrag, zorgverzekering, "Collect
# residence permit from the IND") are deliberately NOT mapped. They live in the
# dossier, which lists every requirement. We do not invent a roadmap step, and we do
# not stretch an existing one to mean something it was not written for.
_REQUIREMENT_TO_MILESTONE: Dict[Tuple[str, str], str] = {
    # ── identity ────────────────────────────────────────────────────────────────
    ("FRANCE", "Valid passport"): "task_passport_upload",
    ("FRANCE", "Valid passport or national identity card"): "task_passport_upload",
    ("GERMANY", "Valid passport (6+ months)"): "task_passport_upload",
    ("GERMANY", "Valid passport or national identity card"): "task_passport_upload",
    ("NETHERLANDS", "Valid passport"): "task_passport_upload",
    ("NETHERLANDS", "Valid passport or national identity card"): "task_passport_upload",

    # ── the immigration permit itself (third-country only) ───────────────────────
    ("FRANCE", "Long-stay work visa (VLS-TS Salarié / Passeport Talent)"): "task_visa_submit",
    ("GERMANY", "Work visa / residence permit (Aufenthaltstitel)"): "task_visa_submit",
    ("NETHERLANDS", "Residence permit (Highly Skilled Migrant / EU Blue Card)"): "task_visa_submit",

    # ── employment ──────────────────────────────────────────────────────────────
    ("FRANCE", "Signed employment contract (CDI or CDD >= 3 months)"): "task_employment_letter",
    ("FRANCE", "Signed French employment contract"): "task_employment_letter",
    ("GERMANY", "Employment letter"): "task_employment_letter",
    ("NETHERLANDS", "Employment contract with an IND-recognised sponsor"): "task_employment_letter",
    ("NETHERLANDS", "Signed Dutch employment contract"): "task_employment_letter",

    # ── registering your arrival with the local authority ────────────────────────
    ("GERMANY", "Residence registration (Anmeldung)"): "task_arrival_registration",
    ("NETHERLANDS", "Municipality registration + BSN (gemeente / BRP)"): "task_arrival_registration",
    ("NORWAY", "Residence registration (folkeregister)"): "task_arrival_registration",
    ("SINGAPORE", "Long-term pass registration (ICA)"): "task_arrival_registration",
    ("UNITED KINGDOM", "Residence permit / eVisa activation"): "task_arrival_registration",
    ("UNITED STATES", "State residency registration"): "task_arrival_registration",
    # France has no Anmeldung equivalent; for a third-country national the arrival
    # immigration step IS the ANEF validation.
    ("FRANCE", "ANEF VLS-TS validation (within 90 days of arrival)"): "task_arrival_registration",

    # ── tax / social security ───────────────────────────────────────────────────
    ("GERMANY", "Social security registration (Sozialversicherung)"): "task_tax_local_registration",
    ("NETHERLANDS", "30% ruling application (tax)"): "task_tax_local_registration",
    ("NORWAY", "National Insurance registration (folketrygden)"): "task_tax_local_registration",
    ("SINGAPORE", "Tax reference registration (IRAS)"): "task_tax_local_registration",
    ("UNITED KINGDOM", "National Insurance number registration"): "task_tax_local_registration",
    ("UNITED STATES", "Social Security Number (SSN) registration"): "task_tax_local_registration",
    # CPAM affiliation is France's social-security registration.
    ("FRANCE", "French health cover (CPAM affiliation)"): "task_tax_local_registration",
}


class _FreeMovementStatement:
    """The free-movement milestone, stripped of a deadline it has no business owning.

    Its default copy comes from ImmigrationRegimeResult.notes and ends "Registration
    with local authorities within 3 months of arrival" — the EU directive's general
    rule. Germany's Anmeldung is 14 days. The Netherlands' is 5. Rendered next to the
    real step, the generic figure is not vague, it is WRONG, and it is the kind of
    wrong that costs someone a fine.

    So it keeps only what it alone can say: that no permit is required. The
    destination-specific registration step owns the deadline.
    """

    title = "No visa or work permit required"
    # It is a STATED ANSWER, not a registration task, so it carries no steps. The
    # library's instructions for this milestone tell you how to register and end with
    # "Timeline: within 3 months of arrival for most EU countries" — which duplicates the
    # destination's real registration step and contradicts its deadline (Germany: 14 days).
    suppress_instructions = True
    description = (
        "You have EU/EEA freedom of movement, so no visa and no residence permit apply. "
        "You must still register locally — that step is listed separately, with the "
        "deadline that actually applies in your destination."
    )


def _requirement_source_urls(item: Any) -> List[str]:
    """The requirement's citation URLs, de-duplicated and order-preserving.

    `RequirementItemDTO.citations` is already resolved across the three `citations_json`
    shapes by `requirements_builder.citation_dtos`, so we read the resolved URLs rather
    than re-parsing the raw column. Empty for a stated-answer overlay
    (`_FreeMovementStatement`) or any requirement with no citation — that is the criterion
    that an uncited task carries `sources: []` and still renders.
    """
    urls: List[str] = []
    seen = set()
    for citation in getattr(item, "citations", None) or []:
        url = (getattr(citation, "url", None) or "").strip()
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


#: [DEADLINE-ENGINE] Corridor-pathway milestones ("{phase}_corridor_NN") are keyed by their
#: authored TITLE, not by a seed-YAML requirement title, so the static map above never
#: reaches them. This map binds a corridor step (by a stable fragment of its title) to the
#: dossier rows that state its timing, consequence and source. Order = priority; the
#: first entries are the ones a mover must not miss. Fails safe: no match, no change.
_CORRIDOR_TITLE_TO_TERMS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("Critical Skills Employment Permit application", ("critical skills", "employment permit", "csep", "12 weeks")),
    ("Employment permit granted", ("employment permit", "critical skills")),
    ("'D' Employment visa application", ("'d' visa", "d visa", "entry visa", "visa-required", "visa required")),
    ("'D' Employment visa granted", ("entry visa", "visa-required", "d visa")),
    ("Register immigration permission", ("irp", "burgh quay", "registration office", "90 days", "immigration registration")),
    ("PPSN", ("ppsn", "personal public service")),
    ("Register the employment with Revenue", ("revenue", "rpn", "emergency tax", "myaccount", "first payroll")),
    ("Open an Irish bank account", ("bank account", "proof of address", "iban")),
    ("Register with a GP", ("gp ", "gp registration", "medical card", "ordinarily resident", "health insurance")),
    ("Register accompanying family", ("stamp 1g", "join family", "dependant", "dependent", "family reunification", "spouse")),
    ("Stamp 4 eligibility", ("stamp 4",)),
    ("Travel to", ("landing", "entry visa", "visa-required")),
)

_MAX_BOUND_ROWS = 3
_MAX_SOURCES = 4


def _bind_corridor_row(row: Dict[str, Any], items: List[Any]) -> Dict[str, Any]:
    """Attach dossier timing / consequence / sources to one corridor milestone row.

    The plan the employee acts on carried a bare title for the immigration chain
    (CSEP, D visa, IRP, PPSN, Revenue, bank, GP, family): no instruction, no source,
    no consequence. Meanwhile the dossier for the same case holds 149 rows with an
    explicit ``timing`` and a citation. This joins them, per task:

      * ``instructions``  = the deadline derivation (from the scheduler, kept in
        ``notes``) + up to 3 dossier rows as "<what>: <when>";
      * ``sources``       = their citation URLs (the official page to act on);
      * ``description``   = the first non-obvious row's text when the pathway note is
        empty (surfaced as why_this_matters by relocation_plan_service).
    """
    title = str(row.get("title") or "")
    title_l = title.lower()
    terms: Tuple[str, ...] = ()
    for fragment, fragment_terms in _CORRIDOR_TITLE_TO_TERMS:
        if fragment.lower() in title_l:
            terms = fragment_terms
            break
    if not terms:
        return row

    def _score(item: Any) -> int:
        blob = f"{getattr(item, 'title', '')} {getattr(item, 'description', '')} {getattr(item, 'timing', '')}".lower()
        hits = sum(1 for t in terms if t in blob)
        if not hits:
            return 0
        score = hits * 10
        if getattr(item, "timing", None):
            score += 5
        if getattr(item, "nonObvious", False):
            score += 3
        if str(getattr(item, "severity", "") or "").upper() in ("WARN", "MUST", "CRITICAL"):
            score += 2
        return score

    ranked = sorted(
        ((_score(it), idx, it) for idx, it in enumerate(items)),
        key=lambda t: (-t[0], t[1]),
    )
    matched = [it for sc, _, it in ranked if sc > 0][:_MAX_BOUND_ROWS]
    if not matched:
        return row

    out = dict(row)
    instructions: List[str] = []
    notes = str(row.get("notes") or "").strip()
    if notes.startswith(("Legal deadline", "Planned")):
        instructions.append(notes)
    for it in matched:
        timing = str(getattr(it, "timing", "") or "").strip()
        if timing:
            instructions.append(f"{str(getattr(it, 'title', '')).strip()}: {timing}")
    if instructions:
        out["instructions"] = instructions
    sources: List[str] = []
    for it in matched:
        for url in _requirement_source_urls(it):
            if url not in sources:
                sources.append(url)
    if sources:
        out["sources"] = sources[:_MAX_SOURCES]
    if not str(row.get("description") or "").strip():
        first = next((it for it in matched if getattr(it, "nonObvious", False)), matched[0])
        desc = str(getattr(first, "description", "") or "").strip()
        if desc:
            out["description"] = desc
    return out


def enrich_milestones_with_requirements(
    case_id: str,
    milestones: List[Dict[str, Any]],
    *,
    request_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Overlay destination-specific copy from the requirements dossier.

    Only `title`, `description` and `sources` (the requirement's citation URLs) are ever
    touched. status / owner / target_date / sort_order / criticality are the roadmap's,
    and stay the roadmap's.

    Fails OPEN: any error returns the milestones untouched. A generic roadmap is far
    better than a roadmap that 500s.
    """
    if not milestones:
        return milestones

    try:
        # Reuse — do not reimplement. This already applies the nationality gate, the
        # in-country short-circuit, and the catalog fail-closed.
        from .requirements_builder import compute_case_requirements

        dto = compute_case_requirements(case_id)
    except Exception as exc:  # noqa: BLE001 — never break the roadmap over this
        log.info(
            "roadmap copy: requirements unavailable for case %s (%s); serving generic copy",
            case_id, exc,
        )
        return milestones

    country = (getattr(dto, "destCountry", "") or "").strip().upper()
    if not country or not getattr(dto, "requirements", None):
        return milestones

    # milestone_type -> the requirement whose copy should replace it.
    # First mapped requirement wins, deterministically (the DTO order is the catalog
    # order). A test asserts no seeded country x nationality-class produces a collision.
    overrides: Dict[str, Any] = {}
    for item in dto.requirements:
        # A `nothing_to_do` item is a stated confirmation ("No visa or residence permit
        # required"), not a task. It must never become a roadmap step — and the visa
        # steps it refers to have already been suppressed upstream.
        if getattr(item, "outcomeType", "action") == "nothing_to_do":
            continue
        target = _REQUIREMENT_TO_MILESTONE.get((country, item.title))
        if target and target not in overrides:
            overrides[target] = item

    # The free-movement milestone carries the regime's generic note: "Registration with
    # local authorities within 3 months of arrival." That is the EU directive's general
    # rule — and it CONTRADICTS the destination's real deadline. Germany's Anmeldung is
    # 14 days; the Dutch gemeente registration is 5. Shown side by side, the employee
    # reads "3 months", misses the real deadline, and is fined.
    #
    # When we have a country-specific registration step, that step owns the deadline.
    # The free-movement milestone keeps the part only it can say — the STATED answer
    # that no permit is required — and stops asserting a timing it does not know.
    if "task_arrival_registration" in overrides:
        overrides["task_eu_registration"] = _FreeMovementStatement()

    # [DEADLINE-ENGINE] Corridor-pathway rows are bound by title fragment to the dossier
    # rows that carry their timing / consequence / source. Independent of `overrides`.
    actionable = [
        it for it in dto.requirements if getattr(it, "outcomeType", "action") != "nothing_to_do"
    ]

    out: List[Dict[str, Any]] = []
    for m in milestones:
        mt = str(m.get("milestone_type") or "")
        if "_corridor_" in mt:
            out.append(_bind_corridor_row(m, actionable))
            continue
        item = overrides.get(mt)
        if item is None:
            out.append(m)
            continue
        enriched = dict(m)
        enriched["title"] = item.title
        enriched["description"] = item.description
        # The requirement's provenance: the source URL(s) behind the copy just overlaid,
        # so the timeline can show the employee the published rule this step traces to.
        # Empty list for a stated answer or a requirement with no citation.
        enriched["sources"] = _requirement_source_urls(item)
        # Marks this row as rewritten, so relocation_plan_service surfaces our
        # description as `why_this_matters` — the line the employee actually reads.
        # Without it the specific copy is written and then silently thrown away: the
        # title said "Anmeldung" while the text under it still said "host-country
        # equivalents".
        enriched["requirement_copy"] = True
        if getattr(item, "suppress_instructions", False):
            enriched["suppress_instructions"] = True
        out.append(enriched)
    return out
