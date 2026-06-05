"""Corridor → ``rce.*`` persistence (C1-05, unblocks C2-07).

The corridor agents (``backend/relopass/corridors``) produce a step graph + the
applicable rules **in memory** from YAML. Nothing wrote that into the ``rce.*``
tables, so ``GET /api/hr/cases/{id}/steps`` returned ``[]`` for every case and
the StepGraph (C2-07) had nothing to render.

This service closes that gap. For a given corridor + a case, it persists:

  - ``rce.rules`` / ``rce.rule_versions`` — one version per applicable rule, so
    citations have a valid ``rule_version_id`` FK to point at.
  - ``rce.steps`` — the corridor step graph (corridor-scoped, shared across
    cases) with prerequisites resolved to UUIDs.
  - ``rce.cases`` — the case row, bound to the corridor + a target arrival date.
  - ``rce.deadlines`` — the rule-anchored deadlines (server-computed, never in JS).
  - ``rce.rule_citations`` — STEP-kind citations for steps that cite a rule.

**Scope:** persistence + the deterministic schedule only. The eligibility
``evaluate(corridor, case)`` runtime (branch routing — the bluecard test's
criteria 2–5) is intentionally OUT of scope and tracked separately.

All ids are deterministic (``uuid5``) so re-runs are idempotent. The row-building
half (``build_rce_rows``) is a pure function with no DB dependency, so it is
fully unit-testable; ``persist_corridor_case`` is the thin DB-writing wrapper.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ...database import db
from ...relopass.corridors.loader import CorridorAgent
from ...relopass.corridors.scheduler import compute_deadlines, schedule_steps

# Stable namespace so every derived id is reproducible across runs/environments.
_NS = uuid.uuid5(uuid.NAMESPACE_URL, "https://relopass.com/rce")

# Corridor rules are applicable-by-corridor; the eligibility predicate DSL is a
# separate concern (C1-04). We store a trivially-true placeholder so the NOT NULL
# column is satisfied without inventing a predicate we haven't authored.
_PREDICATE_PLACEHOLDER = "true"
_RULE_VERSION_LABEL = "as-cited"
_RULE_EFFECTIVE_FROM = date(2026, 1, 1)


def _step_uuid(corridor_id: str, step_key: str) -> uuid.UUID:
    return uuid.uuid5(_NS, f"step:{corridor_id}:{step_key}")


def _rule_version_uuid(rule_id: str) -> uuid.UUID:
    return uuid.uuid5(_NS, f"rule_version:{rule_id}:{_RULE_VERSION_LABEL}")


def _deadline_uuid(case_id: uuid.UUID, step_uuid: uuid.UUID) -> uuid.UUID:
    return uuid.uuid5(_NS, f"deadline:{case_id}:{step_uuid}")


def derive_source_url(rule_id: str, legal_reference: str) -> str:
    """Best-effort canonical URL for a legal reference (NOT NULL column).

    German statutes resolve to gesetze-im-internet.de; the EU Blue Card directive
    to EUR-Lex. Anything unrecognised falls back to a gesetze-im-internet search
    so the column is always a usable, non-empty link.
    """
    ref = legal_reference or ""
    if "2021/1883" in ref or rule_id.startswith("EU_"):
        return "https://eur-lex.europa.eu/eli/dir/2021/1883/oj"
    if "BeschV" in ref:
        return "https://www.gesetze-im-internet.de/beschv_2013/"
    if "BGBl" in ref:
        return "https://www.bundesanzeiger.de/"
    if "AufenthG" in ref:
        # Extract the bare section number (e.g. "§18g" → "18g") for a deep link.
        import re

        m = re.search(r"§\s*(\d+[a-z]?)", ref)
        if m:
            return f"https://www.gesetze-im-internet.de/aufenthg_2004/__{m.group(1)}.html"
        return "https://www.gesetze-im-internet.de/aufenthg_2004/"
    from urllib.parse import quote_plus

    return f"https://www.gesetze-im-internet.de/Teilliste_{quote_plus(ref)}.html"


@dataclass
class RceRows:
    """The full set of rows to persist for one corridor + case (pure data)."""

    rules: List[Dict[str, Any]] = field(default_factory=list)
    rule_versions: List[Dict[str, Any]] = field(default_factory=list)
    steps: List[Dict[str, Any]] = field(default_factory=list)
    case: Dict[str, Any] = field(default_factory=dict)
    deadlines: List[Dict[str, Any]] = field(default_factory=list)
    citations: List[Dict[str, Any]] = field(default_factory=list)


def build_rce_rows(
    corridor: CorridorAgent,
    *,
    case_id: uuid.UUID,
    target_arrival_date: date,
    status: str = "ACTIVE",
) -> RceRows:
    """Pure: turn a corridor agent + case metadata into the rows to upsert.

    No DB access — fully unit-testable. Deterministic ids throughout.
    """
    rows = RceRows()
    cid = corridor.corridor_id

    # ── Rules + one rule_version each (citation FK targets) ──────────────────
    rule_version_by_rule: Dict[str, uuid.UUID] = {}
    for rule in corridor.applicable_rules:
        rv_id = _rule_version_uuid(rule.rule_id)
        rule_version_by_rule[rule.rule_id] = rv_id
        rows.rules.append(
            {
                "rule_id": rule.rule_id,
                "corridor_scope": [cid],
                "legal_reference": rule.legal_reference,
                "description": rule.summary,
            }
        )
        rows.rule_versions.append(
            {
                "rule_version_id": rv_id,
                "rule_id": rule.rule_id,
                "version_label": _RULE_VERSION_LABEL,
                "effective_from": _RULE_EFFECTIVE_FROM,
                "predicate_dsl": _PREDICATE_PLACEHOLDER,
                "source_url": derive_source_url(rule.rule_id, rule.legal_reference),
            }
        )

    # ── Steps (corridor-scoped) with prerequisites resolved to UUIDs ─────────
    step_uuid_by_key = {s.step_id: _step_uuid(cid, s.step_id) for s in corridor.step_graph}
    for s in corridor.step_graph:
        prereq_uuids = [
            str(step_uuid_by_key[p]) for p in s.prerequisite_step_ids if p in step_uuid_by_key
        ]
        rel = step_uuid_by_key.get(s.time_window_relative_to) if s.time_window_relative_to else None
        rows.steps.append(
            {
                "step_id": step_uuid_by_key[s.step_id],
                "corridor_id": cid,
                "name": s.name,
                "responsible_party": s.responsible_party,
                "prerequisite_step_ids": prereq_uuids,
                "expected_duration_days": s.expected_duration_days,
                "time_window_relative_to": rel,
                "time_window_min_days": s.time_window_min_days,
                "time_window_max_days": s.time_window_max_days,
            }
        )

    # ── Case ─────────────────────────────────────────────────────────────────
    rows.case = {
        "case_id": case_id,
        "corridor_id": cid,
        "status": status,
        "target_arrival_date": target_arrival_date,
        "petitioning_party_type": corridor.petitioning_party or "EMPLOYEE",
    }

    # ── Deadlines (server-computed, rule-anchored) ───────────────────────────
    schedule = schedule_steps(corridor.step_graph, target_arrival_date)
    for d in compute_deadlines(corridor.step_graph, target_arrival_date, schedule=schedule):
        step_uuid = step_uuid_by_key[d.step_id]
        rows.deadlines.append(
            {
                "deadline_id": _deadline_uuid(case_id, step_uuid),
                "case_id": case_id,
                "step_id": step_uuid,
                "due_date": d.due_date,
                "derivation": d.derivation,
            }
        )

    # ── STEP citations (only steps that explicitly cite a rule) ──────────────
    legal_ref_by_rule = {r.rule_id: r.legal_reference for r in corridor.applicable_rules}
    for s in corridor.step_graph:
        if not s.cite or s.cite not in rule_version_by_rule:
            continue
        rows.citations.append(
            {
                "case_id": case_id,
                "output_kind": "STEP",
                "output_id": step_uuid_by_key[s.step_id],
                "rule_version_id": rule_version_by_rule[s.cite],
                "legal_reference": legal_ref_by_rule.get(s.cite),
                "source_url": derive_source_url(s.cite, legal_ref_by_rule.get(s.cite, "")),
            }
        )

    return rows


# ── DB-writing wrapper (idempotent upserts) ──────────────────────────────────

def persist_corridor_case(
    corridor: CorridorAgent,
    *,
    case_id: Optional[uuid.UUID] = None,
    target_arrival_date: date,
    status: str = "ACTIVE",
) -> Dict[str, int]:
    """Persist the corridor + case into ``rce.*``. Idempotent (ON CONFLICT).

    Returns a count summary per table. ``case_id`` defaults to a deterministic id
    derived from the corridor so repeated seeds reuse the same demo case.
    """
    if case_id is None:
        case_id = uuid.uuid5(_NS, f"case:{corridor.corridor_id}:default")
    rows = build_rce_rows(
        corridor, case_id=case_id, target_arrival_date=target_arrival_date, status=status
    )

    with db.engine.begin() as conn:
        for r in rows.rules:
            conn.execute(
                text(
                    """
                    INSERT INTO rce.rules (rule_id, corridor_scope, legal_reference, description)
                    VALUES (:rule_id, :corridor_scope, :legal_reference, :description)
                    ON CONFLICT (rule_id) DO UPDATE
                      SET legal_reference = EXCLUDED.legal_reference,
                          description = EXCLUDED.description,
                          updated_at = now()
                    """
                ),
                r,
            )
        for rv in rows.rule_versions:
            conn.execute(
                text(
                    """
                    INSERT INTO rce.rule_versions
                      (rule_version_id, rule_id, version_label, effective_from, predicate_dsl, source_url)
                    VALUES
                      (:rule_version_id, :rule_id, :version_label, :effective_from, :predicate_dsl, :source_url)
                    ON CONFLICT (rule_version_id) DO UPDATE
                      SET source_url = EXCLUDED.source_url, updated_at = now()
                    """
                ),
                rv,
            )
        for s in rows.steps:
            conn.execute(
                text(
                    """
                    INSERT INTO rce.steps
                      (step_id, corridor_id, name, responsible_party, prerequisite_step_ids,
                       expected_duration_days, time_window_relative_to, time_window_min_days, time_window_max_days)
                    VALUES
                      (:step_id, :corridor_id, :name, :responsible_party,
                       CAST(:prerequisite_step_ids AS uuid[]),
                       :expected_duration_days, :time_window_relative_to, :time_window_min_days, :time_window_max_days)
                    ON CONFLICT (step_id) DO UPDATE
                      SET name = EXCLUDED.name,
                          prerequisite_step_ids = EXCLUDED.prerequisite_step_ids,
                          expected_duration_days = EXCLUDED.expected_duration_days,
                          time_window_relative_to = EXCLUDED.time_window_relative_to,
                          time_window_min_days = EXCLUDED.time_window_min_days,
                          time_window_max_days = EXCLUDED.time_window_max_days,
                          updated_at = now()
                    """
                ),
                s,
            )
        conn.execute(
            text(
                """
                INSERT INTO rce.cases (case_id, corridor_id, status, target_arrival_date, petitioning_party_type)
                VALUES (:case_id, :corridor_id, :status, :target_arrival_date, :petitioning_party_type)
                ON CONFLICT (case_id) DO UPDATE
                  SET corridor_id = EXCLUDED.corridor_id,
                      status = EXCLUDED.status,
                      target_arrival_date = EXCLUDED.target_arrival_date,
                      updated_at = now()
                """
            ),
            rows.case,
        )
        for d in rows.deadlines:
            conn.execute(
                text(
                    """
                    INSERT INTO rce.deadlines (deadline_id, case_id, step_id, due_date, derivation)
                    VALUES (:deadline_id, :case_id, :step_id, :due_date, :derivation)
                    ON CONFLICT (deadline_id) DO UPDATE
                      SET due_date = EXCLUDED.due_date, derivation = EXCLUDED.derivation, updated_at = now()
                    """
                ),
                d,
            )
        for c in rows.citations:
            conn.execute(
                text(
                    """
                    INSERT INTO rce.rule_citations
                      (case_id, output_kind, output_id, rule_version_id, legal_reference, source_url)
                    VALUES
                      (:case_id, :output_kind, :output_id, :rule_version_id, :legal_reference, :source_url)
                    ON CONFLICT (case_id, output_kind, output_id, rule_version_id) DO UPDATE
                      SET legal_reference = EXCLUDED.legal_reference, source_url = EXCLUDED.source_url
                    """
                ),
                c,
            )

    return {
        "rules": len(rows.rules),
        "rule_versions": len(rows.rule_versions),
        "steps": len(rows.steps),
        "cases": 1,
        "deadlines": len(rows.deadlines),
        "citations": len(rows.citations),
    }
