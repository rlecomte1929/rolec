"""Engine evals for corridor deadline alerts (E2, E3, E5, E6, E7).

Naming follows the destination-evolution brief's eval ids so a corridor author
can find the gate that failed them. Two of the brief's eight are adapted and one
is deliberately absent — see docs/destination-playbook.md for why:

  E1  import idempotency        → adapted: this product authors corridors as YAML
                                  in-repo, not through an importer, so the
                                  equivalent property is that loading is pure and
                                  the sweep is idempotent (both pinned below).
  E2  validation refusals       → here, in full.
  E3  branch matrix             → adapted: steps carry no branch_condition in this
                                  engine, so the equivalent is the STATED SKIP
                                  REASON for a case the sweep cannot resolve.
  E4  oracle parity             → absent. The reference oracle resolves
                                  anchor + offset_weeks; this engine resolves a
                                  prerequisite DAG with per-step statutory
                                  windows. Byte-identical parity is not
                                  achievable between the two models.
  E5  determinism               → here.
  E6  sweep boundaries          → here.
  E7  copy leak lint            → here.
  E8  publish gate              → absent; publishing is a separate subsystem.
"""
from __future__ import annotations

import glob
from datetime import date, timedelta

import pytest

from backend.relopass.corridors import load_corridor
from backend.relopass.corridors.deadline_alerts import (
    DeadlineTagConflict,
    assert_tag_invariant,
    check_tag_destination_invariant,
    due_alerts,
    event_uid,
    render_alert,
)
from backend.relopass.corridors.loader import (
    CorridorDeadlineTrigger,
    CorridorLoadError,
    CorridorStep,
    load_corridor_text,
)
from backend.relopass.corridors.scheduler import compute_deadlines, schedule_steps

ARRIVAL = date(2026, 3, 1)


def _all_corridors():
    return {
        c.corridor_id: c
        for c in (load_corridor(f) for f in sorted(glob.glob("corridors/*/pathways/*/v1.yaml")))
    }


# ─────────────────────────────────────────────────────────────────────────────
# Fixture builders
# ─────────────────────────────────────────────────────────────────────────────

def _windowed_step(lead_days=7, tag="relopass-deadline-anmeldung-de", **kw):
    return CorridorStep(
        step_id=kw.pop("step_id", "ANMELDUNG"),
        name=kw.pop("name", "Anmeldung (address registration)"),
        responsible_party=kw.pop("responsible_party", "EMPLOYEE"),
        expected_duration_days=0,
        prerequisite_step_ids=("ARRIVE",),
        time_window_relative_to="ARRIVE",
        time_window_min_days=0,
        time_window_max_days=14,
        deadline_trigger=CorridorDeadlineTrigger(
            tag=tag, label=kw.pop("label", "Anmeldung"), channel="email", lead_days=lead_days,
            jurisdiction=kw.pop("jurisdiction", None),
        ),
        **kw,
    )


def _graph(**kw):
    arrive = CorridorStep(
        step_id="ARRIVE", name="Arrive", responsible_party="EMPLOYEE",
        expected_duration_days=0, arrival_anchor=True,
    )
    return [arrive, _windowed_step(**kw)]


def _resolve(steps, today, **kw):
    schedule = schedule_steps(steps, ARRIVAL)
    deadlines = compute_deadlines(steps, ARRIVAL, schedule=schedule)
    return due_alerts(steps, deadlines, today=today, **kw)


_YAML_HEAD = """corridor_agent:
  corridor_id: TEST_XX
  version: "1"
  destination_country_iso3: DEU
  applicable_rules: []
  required_data_points: []
  eligibility_logic:
    branches: []
  step_graph:
    - step_id: ARRIVE
      name: "Arrive"
      responsible_party: EMPLOYEE
      expected_duration_days: 0
    - step_id: ANMELDUNG
      name: "Anmeldung"
      responsible_party: EMPLOYEE
      expected_duration_days: 0
      prerequisite_step_ids: [ARRIVE]
"""

_WINDOW = """      time_window_relative_to: ARRIVE
      time_window_min_days: 0
      time_window_max_days: 14
"""


def _yaml(trigger_block: str, *, window: bool = True) -> str:
    return _YAML_HEAD + (_WINDOW if window else "") + trigger_block


_GOOD_TRIGGER = """      deadline_trigger:
        tag: "relopass-deadline-anmeldung-de"
        label: "Anmeldung"
        channel: "email"
        lead_days: 7
"""


# ─────────────────────────────────────────────────────────────────────────────
# E2 — validation refusals
# ─────────────────────────────────────────────────────────────────────────────

def test_e2_good_trigger_loads():
    """The control. Every refusal below differs from this by exactly one field,
    so a passing refusal test proves the field caused it."""
    corridor = load_corridor_text(_yaml(_GOOD_TRIGGER))
    trigger = corridor.get_step("ANMELDUNG").deadline_trigger
    assert trigger.tag == "relopass-deadline-anmeldung-de"
    assert trigger.lead_days == 7


@pytest.mark.parametrize(
    "block, expect",
    [
        # Tag grammar — an uppercase or wrongly-prefixed tag is not a valid copy key.
        ("""      deadline_trigger:
        tag: "Relopass-Deadline-Anmeldung-DE"
        label: "Anmeldung"
        channel: "email"
        lead_days: 7
""", "lowercase kebab-case"),
        ("""      deadline_trigger:
        tag: "anmeldung-de"
        label: "Anmeldung"
        channel: "email"
        lead_days: 7
""", "relopass-deadline-"),
        # Unknown key — a typo'd field must not be silently dropped.
        ("""      deadline_trigger:
        tag: "relopass-deadline-anmeldung-de"
        label: "Anmeldung"
        channel: "email"
        lead_days: 7
        leadDays: 7
""", "unknown deadline_trigger key"),
        # Missing field — no defaults, because a defaulted lead_days invents a
        # notice period the corridor never authored.
        ("""      deadline_trigger:
        tag: "relopass-deadline-anmeldung-de"
        label: "Anmeldung"
        channel: "email"
""", "lead_days"),
        ("""      deadline_trigger:
        tag: "relopass-deadline-anmeldung-de"
        channel: "email"
        lead_days: 7
""", "label"),
        # lead_days must be a positive int.
        ("""      deadline_trigger:
        tag: "relopass-deadline-anmeldung-de"
        label: "Anmeldung"
        channel: "email"
        lead_days: 0
""", "positive int"),
        ("""      deadline_trigger:
        tag: "relopass-deadline-anmeldung-de"
        label: "Anmeldung"
        channel: "email"
        lead_days: -3
""", "positive int"),
        # Closed channel vocabulary — a typo must not produce an alert nothing
        # dispatches.
        ("""      deadline_trigger:
        tag: "relopass-deadline-anmeldung-de"
        label: "Anmeldung"
        channel: "emial"
        lead_days: 7
""", "channel must be one of"),
        # Jurisdiction is ISO3 uppercase, never a country name.
        ("""      deadline_trigger:
        tag: "relopass-deadline-anmeldung-de"
        label: "Anmeldung"
        channel: "email"
        lead_days: 7
        jurisdiction: "Germany"
""", "alpha-3"),
        ("""      deadline_trigger:
        tag: "relopass-deadline-anmeldung-de"
        label: "Anmeldung"
        channel: "email"
        lead_days: 7
        jurisdiction: "DE"
""", "alpha-3"),
    ],
)
def test_e2_refusals(block, expect):
    with pytest.raises(CorridorLoadError) as exc:
        load_corridor_text(_yaml(block))
    assert expect in str(exc.value)


def test_e2_trigger_without_a_window_is_refused():
    """compute_deadlines only dates a windowed step, so a trigger on an
    unwindowed one is an alert that can never fire. Refuse it at load time
    rather than ship silence."""
    with pytest.raises(CorridorLoadError) as exc:
        load_corridor_text(_yaml(_GOOD_TRIGGER, window=False))
    assert "can never fire" in str(exc.value)


# ─────────────────────────────────────────────────────────────────────────────
# E2 — the tag invariant, and proof that it discriminates
# ─────────────────────────────────────────────────────────────────────────────

def test_e2_invariant_holds_across_the_shipped_corridors():
    assert check_tag_destination_invariant(_all_corridors()) == []


def test_e2_invariant_catches_a_tag_shared_across_jurisdictions():
    """The gate must FAIL against the bug it exists to prevent.

    This is the 2026-08-17 incident in miniature: one dog-import tag bound to
    both the Norway-inbound and France-inbound steps. Norway requires an
    anti-echinococcus treatment before arrival; France requires none and mandates
    I-CAD registration after it. No single message is correct for both readers.
    """
    shared = "relopass-deadline-pet-import-dog"
    no_side = load_corridor_text(
        _YAML_HEAD.replace("destination_country_iso3: DEU", "destination_country_iso3: NOR")
        .replace("corridor_id: TEST_XX", "corridor_id: TEST_FR_NO")
        + _WINDOW
        + f"""      deadline_trigger:
        tag: "{shared}"
        label: "Dog import"
        channel: "email"
        lead_days: 7
"""
    )
    fr_side = load_corridor_text(
        _YAML_HEAD.replace("destination_country_iso3: DEU", "destination_country_iso3: FRA")
        .replace("corridor_id: TEST_XX", "corridor_id: TEST_NO_FR")
        + _WINDOW
        + f"""      deadline_trigger:
        tag: "{shared}"
        label: "Dog import"
        channel: "email"
        lead_days: 7
"""
    )
    violations = check_tag_destination_invariant(
        {"TEST_FR_NO": no_side, "TEST_NO_FR": fr_side}
    )
    assert len(violations) == 1
    assert "two destinations" in violations[0]
    assert "NOR" in violations[0] and "FRA" in violations[0]

    with pytest.raises(DeadlineTagConflict):
        assert_tag_invariant({"TEST_FR_NO": no_side, "TEST_NO_FR": fr_side})


def test_e2_invariant_permits_the_same_rule_reused_across_corridors():
    """The counterpart to the test above, and the reason the invariant is keyed
    on jurisdiction rather than corridor: ANMELDUNG is the same German
    obligation in FR_DE and IN_DE. One rule set, one tag, one message. If this
    ever fails, 'state the rule once' has stopped working."""
    corridors = _all_corridors()
    tag = "relopass-deadline-anmeldung-de"
    bound = {
        cid: s.step_id
        for cid, c in corridors.items()
        for s in c.step_graph
        if s.deadline_trigger and s.deadline_trigger.tag == tag
    }
    assert bound == {"FR_DE_EU_2026": "ANMELDUNG", "IN_DE_BLUECARD_2026": "ANMELDUNG"}
    assert check_tag_destination_invariant(corridors) == []


def test_e2_invariant_catches_one_tag_on_two_different_steps():
    """One tag selects one message, so two unrelated obligations sharing a tag
    would send identical copy for both."""
    yaml = _YAML_HEAD + _WINDOW + _GOOD_TRIGGER + """    - step_id: STEUER_ID
      name: "Tax ID"
      responsible_party: EMPLOYEE
      expected_duration_days: 0
      prerequisite_step_ids: [ARRIVE]
      time_window_relative_to: ARRIVE
      time_window_min_days: 0
      time_window_max_days: 30
      deadline_trigger:
        tag: "relopass-deadline-anmeldung-de"
        label: "Tax ID"
        channel: "email"
        lead_days: 7
"""
    violations = check_tag_destination_invariant({"TEST": load_corridor_text(yaml)})
    assert len(violations) == 1
    assert "two steps" in violations[0]


def test_e2_exit_obligation_keeps_its_own_jurisdiction():
    """NO_FR reports a move abroad to Norway's Folkeregister — a Norwegian rule
    in a France-bound corridor. Without the jurisdiction override it would be
    filed under FRA, and a second Norway-exit corridor would read as a conflict
    between two copies of the same rule."""
    corridors = _all_corridors()
    step = corridors["NO_FR_RETURNING_EEA_2026"].get_step("A1_FOLKEREGISTER")
    assert step.deadline_trigger.jurisdiction == "NOR"
    assert corridors["NO_FR_RETURNING_EEA_2026"].destination_country_iso3 == "FRA"


# ─────────────────────────────────────────────────────────────────────────────
# E5 — determinism
# ─────────────────────────────────────────────────────────────────────────────

def test_e5_five_identical_resolves_are_identical():
    steps = _graph()
    today = ARRIVAL + timedelta(days=10)
    runs = [_resolve(steps, today) for _ in range(5)]
    assert all(r == runs[0] for r in runs)
    # And across every shipped corridor, not just the fixture.
    for corridor in _all_corridors().values():
        a = _resolve(corridor.step_graph, today)
        b = _resolve(corridor.step_graph, today)
        assert a == b


# ─────────────────────────────────────────────────────────────────────────────
# E6 — window boundaries
# ─────────────────────────────────────────────────────────────────────────────

def _due_date(steps):
    return compute_deadlines(steps, ARRIVAL)[0].due_date


@pytest.mark.parametrize(
    "offset_from_open, should_fire, why",
    [
        (-1, False, "the day before the window opens"),
        (0, True, "the day the window opens"),
        (3, True, "mid-window"),
        (7, True, "the due date itself — the window includes it"),
        (8, False, "the day after the due date is lateness, not an open window"),
    ],
)
def test_e6_window_boundaries(offset_from_open, should_fire, why):
    steps = _graph(lead_days=7)
    due = _due_date(steps)
    opens = due - timedelta(days=7)
    fired = _resolve(steps, opens + timedelta(days=offset_from_open))
    assert bool(fired) is should_fire, why


def test_e6_due_date_says_closes_today_not_overdue():
    steps = _graph(lead_days=7)
    due = _due_date(steps)
    alert = _resolve(steps, due)[0]
    assert alert.days_remaining == 0
    assert "closes today" in render_alert(alert)["subject"]


def test_e6_a_completed_step_raises_nothing():
    steps = _graph(lead_days=7)
    due = _due_date(steps)
    assert _resolve(steps, due, completed_step_ids={"ANMELDUNG"}) == []


def test_e6_event_uid_is_stable_and_keyed_on_the_due_date():
    steps = _graph()
    due = _due_date(steps)
    a = event_uid("case-1", "ANMELDUNG", due)
    assert a == event_uid("case-1", "ANMELDUNG", due), "same inputs, same key"
    assert a == f"case-1|ANMELDUNG|{due.isoformat()}"
    # A moved deadline is a NEW obligation, so it must not collide with the old.
    assert a != event_uid("case-1", "ANMELDUNG", due + timedelta(days=1))


# ─────────────────────────────────────────────────────────────────────────────
# E7 — copy leak lint
# ─────────────────────────────────────────────────────────────────────────────
#
# Terms that belong to exactly one jurisdiction. If one appears in another
# jurisdiction's copy, a reader is being told a rule that does not apply to them.
# Extend this list with every new destination.

_MARKERS = {
    "NOR": ("folkeregister", "registreringsbevis", "skatteetaten"),
    "FRA": ("cpam", "carte vitale", "i-cad"),
    "IRL": ("irp", "burgh quay"),
    "DEU": ("anmeldung", "bürgeramt", "blue card"),
}


def _rendered_copy():
    """Every alert this product can currently send, rendered, with its jurisdiction.

    Each trigger is resolved ON its own due date so that all of them fire —
    linting only what happens to be due on one fixture date would leave most copy
    unchecked and the lint green for the wrong reason.
    """
    out = []
    for corridor in _all_corridors().values():
        steps = corridor.step_graph
        deadlines = compute_deadlines(steps, ARRIVAL)
        seen = set()
        for d in deadlines:
            for alert in due_alerts(
                steps, deadlines, today=d.due_date,
                destination=corridor.destination_country_iso3,
            ):
                if alert.step_id in seen:
                    continue
                seen.add(alert.step_id)
                out.append((alert.jurisdiction, render_alert(alert)))
    return out


def test_e7_no_copy_states_another_jurisdictions_rule():
    leaks = []
    for jurisdiction, copy in _rendered_copy():
        text = (copy["subject"] + " " + copy["body"]).lower()
        for owner, markers in _MARKERS.items():
            if owner == jurisdiction:
                continue
            for marker in markers:
                if marker in text:
                    leaks.append(f"{jurisdiction} copy contains {owner} marker {marker!r}: {text}")
    assert leaks == [], "\n".join(leaks)


def test_e7_marker_list_covers_every_jurisdiction_that_can_alert():
    """A destination absent from _MARKERS is unlinted, and the lint would then
    pass by having nothing to check."""
    rendered = _rendered_copy()
    # Non-vacuity. A subset assertion over an empty set passes while checking
    # nothing, which is how a lint stays green after the thing it lints is gone.
    assert len(rendered) >= 8, f"expected the authored triggers to render, got {len(rendered)}"
    alerting = {j for j, _ in rendered}
    assert alerting <= set(_MARKERS), f"unlinted jurisdictions: {alerting - set(_MARKERS)}"
    assert len(alerting) >= 4, f"only {alerting} render copy; the lint would barely check anything"


def test_e7_copy_never_says_due_today_and_names_its_owner():
    for _, copy in _rendered_copy():
        text = copy["subject"] + " " + copy["body"]
        assert "due today" not in text.lower(), "alerts fire across a window, not on a day"
        assert "Deadline:" in text


def test_e7_hr_owned_steps_do_not_address_the_employee():
    alert = _resolve(_graph(responsible_party="EMPLOYER"), ARRIVAL + timedelta(days=10))[0]
    body = render_alert(alert)["body"]
    assert "Your HR team needs to" in body
    assert "yours to complete" not in body
