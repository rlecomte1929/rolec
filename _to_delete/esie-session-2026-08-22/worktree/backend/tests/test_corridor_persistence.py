"""C1-05 — pure-logic tests for corridor → rce.* persistence (unblocks C2-07).

Covers the scheduler date math (incl. delay propagation, C2-07 criterion 4) and
the pure ``build_rce_rows`` row builder. The DB-writing wrapper is validated
separately by running the seed against a real Postgres (Postgres-specific
uuid[]/schema features don't run under the SQLite test harness).
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest

from backend.app.services.corridor_persistence import build_rce_rows, derive_source_url
from backend.relopass.corridors import load_corridor
from backend.relopass.corridors.scheduler import compute_deadlines, schedule_steps

REPO_ROOT = Path(__file__).resolve().parents[2]
CORRIDOR_PATH = REPO_ROOT / "corridors" / "IN_DE" / "pathways" / "BLUECARD_2026" / "v1.yaml"
ARRIVAL = date(2026, 9, 1)


@pytest.fixture(scope="module")
def corridor():
    return load_corridor(CORRIDOR_PATH)


# ── Scheduler ────────────────────────────────────────────────────────────────


def test_schedule_covers_every_step(corridor):
    sched = schedule_steps(corridor.step_graph, ARRIVAL)
    assert set(sched) == set(corridor.step_ids())
    assert len(sched) == 14


def test_downstream_completes_after_prerequisites(corridor):
    sched = schedule_steps(corridor.step_graph, ARRIVAL)
    for step in corridor.step_graph:
        for prereq in step.prerequisite_step_ids:
            assert sched[step.step_id] > sched[prereq], (
                f"{step.step_id} must complete after prerequisite {prereq}"
            )


def test_delay_propagates_to_all_dependents(corridor):
    """C2-07 criterion 4: +7 days to an upstream step shifts every dependent +7."""
    base = schedule_steps(corridor.step_graph, ARRIVAL)
    # ANMELDUNG is upstream of BANK_ACCOUNT, BIOMETRICS, AUFENTHALTSTITEL_*, BLUE_CARD.
    bumped_steps = tuple(
        s if s.step_id != "ANMELDUNG"
        else type(s)(**{**s.__dict__, "expected_duration_days": s.expected_duration_days + 7})
        for s in corridor.step_graph
    )
    bumped = schedule_steps(bumped_steps, ARRIVAL)
    # ANMELDUNG itself and everything downstream shift exactly +7; upstream unchanged.
    assert bumped["ANMELDUNG"] - base["ANMELDUNG"] == timedelta(days=7)
    assert bumped["BANK_ACCOUNT"] - base["BANK_ACCOUNT"] == timedelta(days=7)
    assert bumped["BLUE_CARD_COLLECTION"] - base["BLUE_CARD_COLLECTION"] == timedelta(days=7)
    assert bumped["EMPLOYMENT_CONTRACT_SIGNED"] == base["EMPLOYMENT_CONTRACT_SIGNED"]  # upstream


def test_deadlines_only_for_time_windowed_steps(corridor):
    deadlines = compute_deadlines(corridor.step_graph, ARRIVAL)
    ids = {d.step_id for d in deadlines}
    # Exactly the three steps that set time_window_relative_to in the YAML.
    assert ids == {"ANMELDUNG", "BIOMETRICS_APPOINTMENT", "BLUE_CARD_COLLECTION"}
    for d in deadlines:
        assert d.derivation  # human-readable legal basis present
        assert isinstance(d.due_date, date)


def test_anmeldung_deadline_anchored_to_arrival(corridor):
    """ANMELDUNG is due within 14 days of TRAVEL_TO_DE (arrival)."""
    sched = schedule_steps(corridor.step_graph, ARRIVAL)
    deadlines = {d.step_id: d for d in compute_deadlines(corridor.step_graph, ARRIVAL, schedule=sched)}
    anmeldung = deadlines["ANMELDUNG"]
    assert anmeldung.due_date == sched["TRAVEL_TO_DE"] + timedelta(days=14)
    assert "within 0–14 days" in anmeldung.derivation


# ── Row builder ──────────────────────────────────────────────────────────────


def test_build_rows_shapes(corridor):
    case_id = uuid.uuid4()
    rows = build_rce_rows(corridor, case_id=case_id, target_arrival_date=ARRIVAL)
    assert len(rows.steps) == 14
    assert len(rows.rules) == len(corridor.applicable_rules) == 9
    assert len(rows.rule_versions) == 9
    assert rows.case["case_id"] == case_id
    assert rows.case["status"] == "ACTIVE"
    assert len(rows.deadlines) == 3
    # The corridor explicitly cites exactly one step (NOTIFICATION_82 → §82).
    assert len(rows.citations) == 1
    cite = rows.citations[0]
    assert cite["output_kind"] == "STEP"
    assert cite["legal_reference"] == "AufenthG §82"
    assert cite["source_url"].startswith("https://")


def test_prerequisites_resolved_to_step_uuids(corridor):
    rows = build_rce_rows(corridor, case_id=uuid.uuid4(), target_arrival_date=ARRIVAL)
    valid_step_uuids = {str(s["step_id"]) for s in rows.steps}
    for s in rows.steps:
        for prereq in s["prerequisite_step_ids"]:
            assert prereq in valid_step_uuids  # no dangling/string ids leaked


def test_citation_fk_points_at_a_persisted_rule_version(corridor):
    rows = build_rce_rows(corridor, case_id=uuid.uuid4(), target_arrival_date=ARRIVAL)
    rv_ids = {str(rv["rule_version_id"]) for rv in rows.rule_versions}
    for c in rows.citations:
        assert str(c["rule_version_id"]) in rv_ids  # FK target exists in the same batch


def test_ids_are_deterministic(corridor):
    case_id = uuid.uuid5(uuid.NAMESPACE_URL, "fixed")
    a = build_rce_rows(corridor, case_id=case_id, target_arrival_date=ARRIVAL)
    b = build_rce_rows(corridor, case_id=case_id, target_arrival_date=ARRIVAL)
    assert [s["step_id"] for s in a.steps] == [s["step_id"] for s in b.steps]
    assert [d["deadline_id"] for d in a.deadlines] == [d["deadline_id"] for d in b.deadlines]


def test_rule_versions_satisfy_not_null_columns(corridor):
    rows = build_rce_rows(corridor, case_id=uuid.uuid4(), target_arrival_date=ARRIVAL)
    for rv in rows.rule_versions:
        assert rv["source_url"]      # NOT NULL
        assert rv["predicate_dsl"]   # NOT NULL
        assert rv["effective_from"]  # NOT NULL


def test_derive_source_url_known_statutes():
    assert "aufenthg_2004/__18g.html" in derive_source_url("DE_AUFENTHG_18G", "AufenthG §18g")
    assert "eur-lex" in derive_source_url("EU_2021_1883", "Directive (EU) 2021/1883")
    assert derive_source_url("X", "anything").startswith("https://")  # always non-empty
