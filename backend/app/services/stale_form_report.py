"""[AIQ-1866] Stale case-form report — the cleanup list a gate change should have produced.

Gating a form template's `trigger_rules` only stops FUTURE attachments; the `case_forms`
already attached stay put. `trigger_engine` is append-only by construction — `_upsert_case_form`
is `INSERT ... ON CONFLICT DO NOTHING` and the module has no delete/detach path. When
`20261024000000` gated `FAM-SPOUSE` off EEA corridors, 160 EEA->EEA `case_forms` remained
attached and nobody noticed for six weeks.

This is option (a) from the card: a **read-only report, never a delete**. Retracting a form an
employee has already worked on would destroy input, and `case_forms` cascades `ON DELETE` to five
child tables (`case_form_field_values`, `case_form_comments`, `case_form_events`,
`field_value_overrides`, `case_form_documents`). So we surface the mismatches and let a human
decide, exposing on every row the facts that decide whether a retraction is even safe.

Staleness is **re-derived, not guessed**: for each attached `case_form` we rebuild the case's
CURRENT context exactly as `trigger_engine` does (reusing its helpers, so there is one source of
truth for "would this attach") and ask whether the form's template would still attach it now. A
row is stale only when NO current trigger rule fires for it — and the re-derivation loads the
case's persisted draft so nationality is present, because a third-country national in an EEA
corridor legitimately keeps `FAM-SPOUSE` and must never be flagged (the card's explicit trap).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from sqlalchemy import bindparam, text

from ...database import db
from . import trigger_engine as te

logger = logging.getLogger(__name__)

#: `filled_by` values that mean a human touched the form. A form carrying any of these — or one
#: already submitted, or referenced as another form's blocker — is NOT safe to retract. That
#: predicate is the whole safety argument of option (a); it is surfaced, never enforced by delete.
HUMAN_FILLERS = ("employee", "specialist", "hr")


def find_stale_case_forms(
    country: Optional[str] = None,
    *,
    draft_loader: Optional[Callable[[str], Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Attached `case_forms` whose template's trigger rule no longer matches the case.

    Read-only. Never deletes or detaches. Each returned row carries `gate_still_matches=False`
    plus the safety facts a human needs before acting: `human_input_present`, `auto_filled_only`,
    `submitted`, `blocker_referenced`, and a derived `safe_to_retract`.

    `country` optionally scopes to one destination. `draft_loader` is injectable so the reader
    (and tests) can supply the persisted wizard draft without this module depending on the ORM.
    """
    load_draft = draft_loader or _default_draft_loader

    templates = {str(t["id"]): t for t in te._load_form_templates()}
    attached = _load_attached_case_forms(country)

    context_cache: Dict[str, Optional[Dict[str, Any]]] = {}
    stale: List[Dict[str, Any]] = []
    for cf in attached:
        template = templates.get(str(cf["form_template_id"]))
        if _still_attaches(cf, template, context_cache, load_draft):
            continue
        stale.append(cf)

    if stale:
        _annotate_safety(stale)
    return stale


def _default_draft_loader(case_id: str) -> Dict[str, Any]:
    """Load a case's persisted wizard draft so re-derivation sees the nationality the EEA gate
    turns on. Never lets a load failure crash the report — an unloadable draft becomes {}, which
    `_still_attaches` treats as "cannot evaluate → do not flag" (fail safe)."""
    try:
        from ..db import SessionLocal
        from .relocation_plan_view_service import load_profile_draft_for_case

        with SessionLocal() as session:
            return load_profile_draft_for_case(session, case_id) or {}
    except Exception:
        logger.exception("stale_form_report: could not load draft for case %s", case_id)
        return {}


def _still_attaches(
    cf: Dict[str, Any],
    template: Optional[Dict[str, Any]],
    cache: Dict[str, Optional[Dict[str, Any]]],
    load_draft: Callable[[str], Dict[str, Any]],
) -> bool:
    # A template that no longer exists can attach nothing → the row is stale.
    if template is None:
        return False

    case_id = str(cf["case_id"])
    if case_id not in cache:
        cache[case_id] = _rebuild_case_context(case_id, load_draft)
    ctx = cache[case_id]

    # If the case context cannot be rebuilt (case row gone, bad id), we cannot PROVE the form is
    # stale. Fail SAFE and treat it as still-attached: a false positive here would invite a wrong
    # retraction, which is the exact harm this report exists to avoid.
    if ctx is None:
        return True

    for rule in _as_rules(template.get("trigger_rules")):
        if rule.get("event", "") not in ctx["events"]:
            continue
        if not te._matches_conditions(rule.get("conditions") or {}, ctx["context"]):
            continue
        persons = te._resolve_persons(
            rule.get("for_persons") or ["employee"],
            ctx["context"]["employee_id"],
            ctx["dependents"],
        )
        if _person_matches(cf, persons):
            return True
    return False


def _rebuild_case_context(
    case_id: str, load_draft: Callable[[str], Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Rebuild the case's current context exactly as `trigger_engine._run` does, at rest."""
    case_uuid = te._to_uuid(case_id)
    if not case_uuid:
        return None
    draft = load_draft(case_id) or {}
    context = te._build_context(case_uuid, draft, {})
    if not context:
        return None
    dependents = te._load_dependents(case_uuid)
    context["has_spouse"] = any(
        d["relationship"] in ("spouse", "partner") for d in dependents
    )
    context["has_children"] = any(d["relationship"] == "child" for d in dependents)
    events = te._derive_events(context, draft, {})
    return {"context": context, "events": events, "dependents": dependents}


def _person_matches(cf: Dict[str, Any], persons: List[Tuple[Any, Any]]) -> bool:
    cf_person = str(cf["person_id"]) if cf.get("person_id") else None
    cf_dep = str(cf["dependent_id"]) if cf.get("dependent_id") else None
    for pid, did in persons:
        if (str(pid) if pid else None) == cf_person and (str(did) if did else None) == cf_dep:
            return True
    return False


def _as_rules(raw: Any) -> List[Dict[str, Any]]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
    return raw or []


def _load_attached_case_forms(country: Optional[str]) -> List[Dict[str, Any]]:
    sql = (
        "SELECT cf.id, cf.case_id, cf.form_template_id, cf.person_id, cf.dependent_id, "
        "cf.status, cf.submitted_at, ft.code AS template_code "
        f"FROM {te._t('case_forms')} cf "
        f"JOIN {te._t('form_templates')} ft ON ft.id = cf.form_template_id "
    )
    params: Dict[str, Any] = {}
    if country:
        sql += (
            f"JOIN {te._t('cases')} c ON c.id = cf.case_id "
            "AND upper(c.dest_country_code) = :country "
        )
        params["country"] = country.upper()
    sql += "ORDER BY ft.code, cf.case_id"
    with db.engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def _annotate_safety(stale: List[Dict[str, Any]]) -> None:
    """Attach the human-input / submission / blocker facts, in a couple of set-based queries."""
    ids = [str(cf["id"]) for cf in stale]
    human_ids, any_value_ids = _field_value_facts(ids)
    referenced_ids = _blocker_referenced(ids)

    for cf in stale:
        cid = str(cf["id"])
        submitted = cf.get("submitted_at") is not None
        human = cid in human_ids
        referenced = cid in referenced_ids
        cf["gate_still_matches"] = False
        cf["submitted"] = submitted
        cf["human_input_present"] = human
        cf["auto_filled_only"] = (cid in any_value_ids) and not human
        cf["blocker_referenced"] = referenced
        # The one derived judgement the report is willing to make: a row is safe to retract only
        # if no human touched it, it was never submitted, and nothing depends on it as a blocker.
        cf["safe_to_retract"] = not (human or submitted or referenced)
        cf.pop("submitted_at", None)  # expose the boolean, not the raw timestamp


def _field_value_facts(ids: List[str]) -> Tuple[Set[str], Set[str]]:
    if not ids:
        return set(), set()
    stmt = text(
        f"SELECT case_form_id, filled_by FROM {te._t('case_form_field_values')} "
        "WHERE case_form_id IN :ids"
    ).bindparams(bindparam("ids", expanding=True))
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(stmt, {"ids": ids}).mappings().all()
    except Exception:
        logger.exception("stale_form_report: field-value lookup failed; annotating conservatively")
        # Conservative: if we cannot read provenance, assume human input so nothing reads as safe.
        return set(ids), set(ids)
    human: Set[str] = set()
    any_value: Set[str] = set()
    for r in rows:
        cid = str(r["case_form_id"])
        any_value.add(cid)
        if (r["filled_by"] or "") in HUMAN_FILLERS:
            human.add(cid)
    return human, any_value


def _blocker_referenced(ids: List[str]) -> Set[str]:
    """Case_form ids referenced by another form via a NO-ACTION-ish FK — deleting them would be
    blocked or would orphan a dependency. `corrected_by_form_id` is prod-only; a schema without
    it (the SQLite test harness) simply contributes no references."""
    referenced: Set[str] = set()
    for column in ("blocker_form_id", "corrected_by_form_id"):
        referenced |= _refs_for_column(column, ids)
    return referenced


def _refs_for_column(column: str, ids: List[str]) -> Set[str]:
    stmt = text(
        f"SELECT {column} AS ref FROM {te._t('case_forms')} WHERE {column} IN :ids"
    ).bindparams(bindparam("ids", expanding=True))
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(stmt, {"ids": ids}).mappings().all()
    except Exception:
        return set()  # column absent in this schema → no references of this kind
    return {str(r["ref"]) for r in rows if r["ref"]}
