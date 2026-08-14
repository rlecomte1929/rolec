"""Unit tests for the confirm-twice gate in notion_sync_candidates.

A deploy-window transient is tied to ONE deploy and rarely fails two consecutive
campaign runs; a real bug persists. So a candidate is filed only if its test_id also
failed in the PREVIOUS run. Fail-open: if no valid previous state exists (e.g. first
run / broken artifact plumbing), file normally — never mask a real bug on missing state.
Pure functions + tmp files — no Notion.
"""
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import notion_sync_candidates as nsc  # noqa: E402

CANDS = [
    {"test_id": "CORE-RLS", "title": "x", "priority": "P0"},
    {"test_id": "PER-H1", "title": "y", "priority": "P0"},
    {"test_id": "CORE-HR-dashboard", "title": "z", "priority": "P1"},
]


def test_filter_files_only_ids_present_in_prev():
    to_file, held = nsc.filter_confirmed(CANDS, prev_ids={"PER-H1"}, have_prev=True)
    assert [c["test_id"] for c in to_file] == ["PER-H1"], "only the twice-failing id files"
    assert {c["test_id"] for c in held} == {"CORE-RLS", "CORE-HR-dashboard"}


def test_fail_open_when_no_prev_state():
    # missing/invalid previous state → file everything (don't mask real bugs)
    to_file, held = nsc.filter_confirmed(CANDS, prev_ids=set(), have_prev=False)
    assert to_file == CANDS
    assert held == []


def test_load_prev_ids_missing_file(tmp_path):
    ids, have_prev = nsc.load_prev_ids(str(tmp_path / "nope.json"))
    assert ids == set() and have_prev is False


def test_state_roundtrip(tmp_path):
    p = tmp_path / "state.json"
    nsc.write_state(str(p), CANDS)
    ids, have_prev = nsc.load_prev_ids(str(p))
    assert have_prev is True
    assert ids == {"CORE-RLS", "PER-H1", "CORE-HR-dashboard"}


def test_load_prev_ids_tolerates_garbage(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json{")
    ids, have_prev = nsc.load_prev_ids(str(p))
    assert ids == set() and have_prev is False  # fail-open on corrupt state


def test_no_baseline_creates_new_but_holds_reopen():
    """AIQ-1738 interaction: a missing baseline (have_prev False) fails OPEN for CREATE — a
    genuinely new failure still files — but fails CLOSED for REOPEN — a human-closed (Done)
    task is HELD, not resurrected on a single unverifiable flap (the AIQ-1375 recurrence).
    main() computes ``confirmed = (not confirm_twice_active) or (test_id in prev_ids)``.
    """
    prev_ids, have_prev = set(), False
    # CREATE path: filter_confirmed keeps everything (fail-open) so new tasks still file.
    to_file, held = nsc.filter_confirmed(CANDS, prev_ids, have_prev)
    assert to_file == CANDS and held == []
    # REOPEN path: with an empty baseline a Done task on AMBER is unconfirmed → held.
    confirmed = "CORE-HR-command-center" in prev_ids  # False — first-seen this campaign
    assert nsc.terminal_action("Done", "AMBER", confirmed=confirmed) == "hold"
    # …and a confirmed one (id present in the baseline) still reopens.
    assert nsc.terminal_action("Done", "AMBER", confirmed="PER-H1" in {"PER-H1"}) == "reopen"
