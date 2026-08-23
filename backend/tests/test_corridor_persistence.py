"""C1-05 — pure-logic tests for corridor → rce.* persistence (unblocks C2-07).

Covers the scheduler date math (incl. delay propagation, C2-07 criterion 4) and
the pure ``build_rce_rows`` row builder. The DB-writing wrapper is validated
separately by running the seed against a real Postgres (Postgres-specific
uuid[]/schema features don't run under the SQLite test harness).
"""
from __future__ import annotations

import dataclasses
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest

from backend.app.services.corridor_persistence import build_rce_rows, derive_source_url
from backend.relopass.corridors import CorridorRule, CorridorStep, load_corridor
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
    assert "beschv_2013" in derive_source_url("DE_BESCHV", "BeschV §26")
    assert "bundesanzeiger" in derive_source_url("DE_BGBL", "BGBl. I S. 1")


# ── The fabricator (AIQ-2010 / #1888) ────────────────────────────────────────
#
# derive_source_url used to end in a catch-all that MANUFACTURED a URL for any
# reference it did not recognise — and the fallback host was German:
#
#     https://www.gesetze-im-internet.de/Teilliste_{quote_plus(ref)}.html
#
# So an Irish or Norwegian rule was cited to a German government page that does
# not exist. The line these tests replace asserted the bug as the contract:
#
#     assert derive_source_url("X", "anything").startswith("https://")  # always non-empty
#
# Non-empty is not the same as correct, and a citation is the one field where the
# difference is the whole product.


@pytest.mark.parametrize(
    "rule_id, reference",
    [
        ("IE_EMPLOYMENT_PERMITS_ACT", "Employment Permits Act 2006 (Ireland), s.3A"),
        ("NO_UTLENDINGSLOVEN", "Utlendingsloven §23 (Norway)"),
        ("ES_LEY_ORGANICA_4_2000", "Ley Orgánica 4/2000, art. 36 (Spain)"),
        ("X", "anything"),
        ("UNKNOWN", ""),
    ],
)
def test_an_unknown_reference_yields_no_url_rather_than_a_german_one(rule_id, reference):
    """The regression that matters: no invented citation, and above all not one
    pointing at a German statute host for a non-German rule."""
    got = derive_source_url(rule_id, reference)
    assert got is None, f"invented a source URL for {rule_id!r}: {got!r}"


def test_no_irish_or_norwegian_rule_is_ever_cited_to_a_german_statute_host():
    for rule_id, reference in [
        ("IE_EMPLOYMENT_PERMITS_ACT", "Employment Permits Act 2006 (Ireland)"),
        ("NO_UTLENDINGSLOVEN", "Utlendingsloven §23"),
    ]:
        got = derive_source_url(rule_id, reference) or ""
        assert "gesetze-im-internet.de" not in got
        assert "bundesanzeiger" not in got


def _corridor_with(rules, steps, base):
    """A synthetic corridor sharing the fixture's shape but carrying our rules."""
    return dataclasses.replace(base, applicable_rules=tuple(rules), step_graph=tuple(steps))


def test_an_unsourceable_rule_writes_no_rule_version_and_no_citation(corridor):
    """The cascade. A rule we cannot source must not produce a rule_version row
    (its source_url is NOT NULL — respected by not writing the row), and any step
    citing it must lose its citation rather than gain a fabricated one."""
    rules = [
        CorridorRule(legal_reference="AufenthG §18g", rule_id="DE_OK", summary="sourceable"),
        CorridorRule(
            legal_reference="Employment Permits Act 2006 (Ireland)",
            rule_id="IE_NOPE",
            summary="not sourceable",
        ),
    ]
    steps = [
        CorridorStep(step_id="S_OK", name="ok", responsible_party="EMPLOYEE",
                     expected_duration_days=1, cite="DE_OK"),
        CorridorStep(step_id="S_BAD", name="bad", responsible_party="EMPLOYEE",
                     expected_duration_days=1, cite="IE_NOPE"),
    ]
    rows = build_rce_rows(
        _corridor_with(rules, steps, corridor),
        case_id=uuid.uuid4(),
        target_arrival_date=ARRIVAL,
    )

    # The RULE is still recorded — it exists, we just cannot cite it.
    assert {r["rule_id"] for r in rows.rules} == {"DE_OK", "IE_NOPE"}
    # The citable artifacts are only the sourceable one.
    assert [rv["rule_id"] for rv in rows.rule_versions] == ["DE_OK"]
    assert [c["rule_version_id"] for c in rows.citations] == [
        rv["rule_version_id"] for rv in rows.rule_versions
    ]
    assert len(rows.citations) == 1
    assert "gesetze-im-internet" in rows.citations[0]["source_url"]


def test_no_citation_dangles_past_a_skipped_rule_version(corridor):
    """Every citation's rule_version_id must correspond to a rule_version row that
    was actually written — otherwise skipping the row trades a bad URL for a
    broken FK."""
    rules = [
        CorridorRule(legal_reference="Utlendingsloven §23", rule_id="NO_A", summary=None),
        CorridorRule(legal_reference="Ley Orgánica 4/2000", rule_id="ES_B", summary=None),
    ]
    steps = [
        CorridorStep(step_id="S1", name="s1", responsible_party="EMPLOYEE",
                     expected_duration_days=1, cite="NO_A"),
        CorridorStep(step_id="S2", name="s2", responsible_party="EMPLOYEE",
                     expected_duration_days=1, cite="ES_B"),
    ]
    rows = build_rce_rows(
        _corridor_with(rules, steps, corridor),
        case_id=uuid.uuid4(),
        target_arrival_date=ARRIVAL,
    )
    assert rows.rule_versions == []
    assert rows.citations == []

    written = {rv["rule_version_id"] for rv in rows.rule_versions}
    assert all(c["rule_version_id"] in written for c in rows.citations)


def test_the_real_corridor_still_produces_its_citations(corridor):
    """Guard against over-correcting: IN→DE is a German corridor whose references
    all resolve, so tightening the fabricator must not empty it out."""
    rows = build_rce_rows(corridor, case_id=uuid.uuid4(), target_arrival_date=ARRIVAL)
    assert rows.rule_versions, "the IN_DE corridor must still yield rule_versions"
    assert all(rv["source_url"] for rv in rows.rule_versions)
    written = {rv["rule_version_id"] for rv in rows.rule_versions}
    assert all(c["rule_version_id"] in written for c in rows.citations)
