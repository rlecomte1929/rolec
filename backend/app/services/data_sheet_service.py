"""
data_sheet_service.py — the Document Data Sheet read-model (Phase 1).

Composes, for ONE case, the shipped data-sheet ``form_template`` (its sections + fields +
consult-professional flags) with the per-field values + provenance that ``prefill_engine`` has
already written to ``case_form_field_values``, annotates each field with its governed fact
(``fact_dictionary``), and enriches with best-effort banners from the corridor step-graph.

Deterministic and **LLM-free by construction** — it is a composition over already-reviewed data
(``form_templates`` are authored; ``case_form_field_values`` are prefilled deterministically and
never invented). Registered in ``SERVING_ROOTS`` because its output reaches a customer without a
human in the loop; its only service imports are ``fact_dictionary`` (pure data) and the
dependency-free corridor loaders, so it stays inside the isolation boundary.

Two invariants the moat rests on, preserved here (read side):
  * **Never invent a value** — a field with no stored value renders ``source='needs_input'``.
  * **Never fill a consult-professional determination** — a field flagged ``consult_professional``
    (template) OR ``professional_review_required`` (fact dictionary) renders guidance only, its
    value forced to null regardless of any stored value.

This module does not write. Field edits + write-back to the canonical store are Phase 2.
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text as _sql_text

from .. import schemas
from . import corridor_content, corridor_registry, fact_dictionary
from ...database import db as main_db
from ...relopass.corridors import load_corridor

logger = logging.getLogger(__name__)

# Stored `case_form_field_values.source` → the data-sheet provenance vocabulary.
_SOURCE_MAP: Dict[str, str] = {
    "intake_profile": "intake",
    "contract": "intake",
    "banking": "intake",
    "manual": "intake",
    "system": "intake",
    "authority_lookup": "intake",
    "passport_ocr": "passport_ocr",
    "prior_form": "prior_form",
    "ai_inference": "ai",
}


def _t(name: str) -> str:
    """Schema-qualify a table name for Postgres; bare for SQLite. Uses this module's own
    ``main_db`` handle so a test that rebinds it gets the right dialect."""
    try:
        dialect = main_db.engine.dialect.name
    except Exception:
        dialect = "postgresql"
    return f"public.{name}" if dialect == "postgresql" else name


def _as_json(value: Any, default: Any) -> Any:
    """jsonb columns arrive as str (SQLite / some drivers) or already-parsed (psycopg)."""
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default
    return value


def _pick_label(fd: Dict[str, Any], lang: str) -> str:
    """`lang='local'` prefers the template's local-language label (label_nb) when present."""
    if lang == "local" and fd.get("label_nb"):
        return fd["label_nb"]
    return fd.get("label") or fd.get("id", "")


def _corridor_banners(origin: Optional[str], dest: Optional[str]) -> List[schemas.DataSheetBannerDTO]:
    """Best-effort moat + deadline banners from the corridor step-graph. Never raises — a
    corridor with no authored pathway simply yields no banners."""
    if not origin or not dest:
        return []
    banners: List[schemas.DataSheetBannerDTO] = []
    try:
        cid = corridor_registry.normalize_corridor_id(f"{origin}_{dest}")
        pathways = corridor_registry.get_pathways(cid)
        if not pathways:
            return []
        path = corridor_registry.get_pathway_file(cid, pathways[0].id)
        if path is None:
            return []
        agent = load_corridor(path)
        for step in agent.step_graph:
            note = getattr(step, "non_obvious_note", "") or ""
            if getattr(step, "non_obvious", False) and note:
                banners.append(schemas.DataSheetBannerDTO(type="moat-fact", text=note))
            trigger = getattr(step, "deadline_trigger", None)
            if trigger is not None:
                label = getattr(trigger, "label", None) or getattr(step, "name", "") or ""
                if label:
                    banners.append(schemas.DataSheetBannerDTO(type="warning", text=label))
    except Exception:  # noqa: BLE001 — enrichment is best-effort, never a hard failure
        logger.debug("datasheet: corridor banner enrichment failed for %s_%s", origin, dest, exc_info=True)
        return []
    return banners


def _empty_sheet(case_id: str) -> schemas.DataSheetDTO:
    return schemas.DataSheetDTO(
        caseRef=case_id,
        generatedAt=_dt.datetime.now(_dt.timezone.utc),
        covered=False,
    )


def build_data_sheet(
    case_id: str,
    audience: str = "employee",
    lang: str = "en",
    mode: str = "full",
) -> schemas.DataSheetDTO:
    """Compose the case's data sheet. ``case_id`` must already be the resolved canonical id
    (the router calls ``_assert_case_access`` first)."""
    is_hr = audience == "hr"

    with main_db.engine.connect() as conn:
        case_row = conn.execute(
            _sql_text(
                f"""
                SELECT dest_country_code, origin_country_code, target_move_date,
                       actual_move_date, expected_duration_months, intake_data, employee_id
                FROM {_t('cases')} WHERE id = :cid
                """
            ),
            {"cid": case_id},
        ).mappings().first()

        form_row = conn.execute(
            _sql_text(
                f"""
                SELECT cf.id AS case_form_id, ft.code, ft.fields, ft.sections,
                       ft.source_language, ft.authority_name
                FROM {_t('case_forms')} cf
                JOIN {_t('form_templates')} ft ON cf.form_template_id = ft.id
                WHERE cf.case_id = :cid AND ft.category = 'data_sheet'
                ORDER BY cf.updated_at DESC
                LIMIT 1
                """
            ),
            {"cid": case_id},
        ).mappings().first()

        value_rows = conn.execute(
            _sql_text(
                f"""
                SELECT field_id, value, filled_by, ai_confidence, source, reviewed, overridden
                FROM {_t('case_form_field_values')}
                WHERE case_form_id = :cf
                """
            ),
            {"cf": form_row["case_form_id"]},
        ).mappings().all() if form_row else []

    # ── Case-level metadata (needed for both the template sheet and the fallback) ──
    origin = dest = None
    move_date = employee_name = None
    if case_row:
        origin = case_row.get("origin_country_code")
        dest = case_row.get("dest_country_code")
        move_date = case_row.get("actual_move_date") or case_row.get("target_move_date")
        intake = _as_json(case_row.get("intake_data"), {})
        employee_name = (intake.get("profile") or {}).get("legal_full_name")
    corridor = corridor_registry.normalize_corridor_id(f"{origin}_{dest}") if origin and dest else None
    corridor_label = f"{origin}→{dest}" if origin and dest else None

    if not form_row:
        # No authored data-sheet template for this case. If the destination has curated
        # corridor content, render a read-only PREVIEW sheet from it; otherwise, not covered.
        if dest and corridor_content.has_corridor_content(dest):
            return _build_from_corridor_content(
                case_id, dest, corridor, corridor_label, move_date, employee_name,
                audience, lang, mode,
            )
        return _empty_sheet(case_id)

    stored: Dict[str, Dict[str, Any]] = {str(r["field_id"]): dict(r) for r in value_rows}

    # ── Section metadata (from sections[] when the template carries it) ────────
    sections_meta: Dict[str, Dict[str, Any]] = {
        s["id"]: s for s in _as_json(form_row.get("sections"), []) if isinstance(s, dict) and s.get("id")
    }

    fields = _as_json(form_row.get("fields"), [])
    # Preserve first-seen section order while grouping (fields are template-ordered by position).
    section_order: List[str] = []
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for fd in sorted(fields, key=lambda f: f.get("position", 0)):
        sid = fd.get("section") or "general"
        if sid not in grouped:
            grouped[sid] = []
            section_order.append(sid)
        grouped[sid].append(fd)

    consult: List[schemas.DataSheetConsultDTO] = []
    total_fillable = 0
    filled = 0
    sections: List[schemas.DataSheetSectionDTO] = []

    for order, sid in enumerate(section_order):
        section_fields = grouped[sid]
        meta = sections_meta.get(sid, {})
        section_source_url = meta.get("portal_url")
        process_note = meta.get("callout_top") or meta.get("deadline_hint")
        field_dtos: List[schemas.DataSheetFieldDTO] = []

        for fd in section_fields:
            fid = fd.get("id", "")
            entry = fact_dictionary.lookup(fd.get("prefill_source"), fid)
            label = _pick_label(fd, lang)
            fact_key = entry.fact_key if entry else None
            category = entry.category if entry else None
            is_consult = bool(fd.get("consult_professional")) or (
                entry.professional_review_required if entry else False
            )
            # Section-level fallbacks from the first field that carries them (FR→NO puts the
            # authority link + process note on the section's first field).
            if section_source_url is None and fd.get("portal_url"):
                section_source_url = fd.get("portal_url")
            if process_note is None and fd.get("note"):
                process_note = fd.get("note")

            if is_consult:
                # Firewall: never a value, guidance only — even if a value were somehow stored.
                field_dtos.append(schemas.DataSheetFieldDTO(
                    fieldId=fid, factKey=fact_key, label=label, category=category,
                    source="consult_professional", value=None,
                    guidance=fd.get("note"),
                    requiresOriginal=bool(fd.get("requires_original", False)),
                ))
                consult.append(schemas.DataSheetConsultDTO(topic=label, reason=fd.get("note")))
                continue

            total_fillable += 1
            sv = stored.get(fid)
            value = sv.get("value") if sv else None
            if value:
                filled += 1
                field_dtos.append(schemas.DataSheetFieldDTO(
                    fieldId=fid, factKey=fact_key, label=label, category=category,
                    source=_SOURCE_MAP.get((sv or {}).get("source"), "intake"),
                    value=value, confidence=(sv or {}).get("ai_confidence"),
                    requiresOriginal=bool(fd.get("requires_original", False)),
                ))
            else:
                field_dtos.append(schemas.DataSheetFieldDTO(
                    fieldId=fid, factKey=fact_key, label=label, category=category,
                    source="needs_input", value=None, hint=fd.get("note"),
                    requiresOriginal=bool(fd.get("requires_original", False)),
                ))

        if mode == "sparse":
            field_dtos = [f for f in field_dtos if f.source == "needs_input"]
            if not field_dtos:
                continue

        sections.append(schemas.DataSheetSectionDTO(
            stepId=sid,
            title=meta.get("title") or sid.replace("_", " ").title(),
            authority=meta.get("authority") or (form_row.get("authority_name") if order == 0 else None),
            sourceUrl=section_source_url,
            processNote=process_note,
            order=order,
            fields=field_dtos,
        ))

    completion_pct = round(100 * filled / total_fillable) if total_fillable else 100
    needs_input_count = total_fillable - filled

    return schemas.DataSheetDTO(
        caseRef=case_id,
        employeeName=employee_name,
        corridor=corridor,
        corridorLabel=corridor_label,
        movementBasis=None,  # derived in a later phase (needs nationality-class resolution)
        generatedAt=_dt.datetime.now(_dt.timezone.utc),
        completionPct=completion_pct,
        needsInputCount=needs_input_count,
        banners=_corridor_banners(origin, dest),
        sections=sections,
        consultProfessional=consult,
        covered=True,
    )


# ── Corridor-content fallback (Option A) ──────────────────────────────────────────────────────
# When a case's destination has no authored data-sheet template, render a read-only PREVIEW from
# the curated `data/corridor-content/<ISO>.ndjson` corpus: one section per curated step (carrying
# its authority, official portal, deadline and responsible party), the 4-part non-obvious "moat"
# banners, and the consult-professional panel. Nothing is fillable — there is no form to write to
# — so `preview=True` and every step is `needs_input` guidance only.

_PHASE_ORDER = ["PRE_DEPARTURE", "ARRIVAL_WEEK", "FIRST_MONTH", "ONGOING"]
_PHASE_TITLE = {
    "PRE_DEPARTURE": "Pre-Departure",
    "ARRIVAL_WEEK": "Arrival Week",
    "FIRST_MONTH": "First Month",
    "ONGOING": "Ongoing Obligations",
}


def _fact_category(fact_key: Optional[str], country_iso: Optional[str]) -> Optional[str]:
    """Domain segment of a fact_key. Handles both the shared `domain.field` shape and the
    per-country `{ISO}.domain.field` pattern (skips the leading ISO)."""
    if not fact_key:
        return None
    parts = fact_key.split(".")
    if len(parts) >= 2 and parts[0].upper() == (country_iso or "").upper():
        return parts[1]
    return parts[0] if parts else None


def _deadline_date(move_date: Any, offset_days: Any) -> Optional[str]:
    """ISO date = move date + offset (offset may be negative for pre-departure steps)."""
    if move_date is None or offset_days is None:
        return None
    base = move_date
    if isinstance(base, str):
        try:
            base = _dt.date.fromisoformat(base[:10])
        except ValueError:
            return None
    if isinstance(base, _dt.datetime):
        base = base.date()
    if not isinstance(base, _dt.date):
        return None
    try:
        return (base + _dt.timedelta(days=int(offset_days))).isoformat()
    except (ValueError, TypeError):
        return None


def _build_from_corridor_content(
    case_id: str,
    dest: str,
    corridor: Optional[str],
    corridor_label: Optional[str],
    move_date: Any,
    employee_name: Optional[str],
    audience: str,
    lang: str,
    mode: str,
) -> schemas.DataSheetDTO:
    records = corridor_content.load_corridor_content(dest)
    is_hr = audience == "hr"

    # Non-obvious "moat" banners — the contrast framework (reality + the action it forces).
    banners: List[schemas.DataSheetBannerDTO] = []
    for r in records:
        if not r.get("is_non_obvious"):
            continue
        label = (r.get("field_label") or "").strip()
        reality = (r.get("non_obvious_actual_reality") or "").strip()
        action = (r.get("non_obvious_action_required") or "").strip()
        text = " — ".join(p for p in (label, reality) if p)
        if action:
            text = f"{text}  What to do: {action}" if text else action
        if text:
            banners.append(schemas.DataSheetBannerDTO(type="moat-fact", text=text))

    def _phase_index(section: Any) -> int:
        try:
            return _PHASE_ORDER.index(section)
        except ValueError:
            return len(_PHASE_ORDER)

    ordered = sorted(records, key=lambda r: (_phase_index(r.get("section")), r.get("step") or 0))

    consult: List[schemas.DataSheetConsultDTO] = []
    sections: List[schemas.DataSheetSectionDTO] = []
    total_fillable = 0

    for order, r in enumerate(ordered):
        task = r.get("field_label") or r.get("fact_key") or "Requirement"
        fact_key = r.get("fact_key")
        category = _fact_category(fact_key, dest)
        is_consult = bool(r.get("consult_professional"))
        section = r.get("section")
        local_id = fact_key or f"{section}:{r.get('step')}"
        fid = f"{(dest or '').upper()}:{local_id}"
        deadline_iso = _deadline_date(move_date, r.get("deadline_offset_days"))
        deadline_label = r.get("deadline_label")

        if is_consult:
            field_dto = schemas.DataSheetFieldDTO(
                fieldId=fid, factKey=fact_key, label=task, category=category,
                source="consult_professional", value=None,
                guidance=r.get("non_obvious_action_required") or deadline_label,
            )
            consult.append(schemas.DataSheetConsultDTO(
                topic=task, reason=r.get("non_obvious_action_required") or r.get("source")))
            if mode == "sparse":
                continue  # sparse = only what still needs input; consult items are guidance
        else:
            total_fillable += 1
            action = r.get("non_obvious_action_required") if r.get("is_non_obvious") else None
            field_dto = schemas.DataSheetFieldDTO(
                fieldId=fid, factKey=fact_key, label=task, category=category,
                source="needs_input", value=None, hint=deadline_label,
                employerActionNote=action if (is_hr and action) else None,
            )

        # The authority heads the step card; the task is the field. Keeps the official portal
        # link clickable (section.sourceUrl) — the shape the RP-*-DATASHEET templates use.
        sections.append(schemas.DataSheetSectionDTO(
            stepId=fid,
            title=r.get("authority") or task,
            sourceUrl=r.get("source_url"),
            processNote=_PHASE_TITLE.get(section, section),
            order=order,
            responsibleParty=(r.get("responsible_party") if is_hr else None),
            deadline=(schemas.DataSheetDeadlineDTO(date=deadline_iso, isSuggested=True)
                      if deadline_iso else None),
            fields=[field_dto],
        ))

    return schemas.DataSheetDTO(
        caseRef=case_id,
        employeeName=employee_name,
        corridor=corridor,
        corridorLabel=corridor_label,
        movementBasis=None,
        generatedAt=_dt.datetime.now(_dt.timezone.utc),
        completionPct=0,  # a preview captures nothing — 0% of its fillable steps are done
        needsInputCount=total_fillable,
        banners=banners,
        sections=sections,
        consultProfessional=consult,
        covered=True,
        preview=True,
    )
