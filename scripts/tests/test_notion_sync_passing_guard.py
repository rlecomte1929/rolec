"""Tests for the passing-run reopen guard in scripts/notion_sync_candidates.py.

Regression guard for the AIQ-1377 re-open loop: the E2E Sentinel repeatedly flipped a
human-closed (Done) P0 back to "Ready for AI" on deploy-window transients where the run
actually passed. `terminal_action` must NEVER resurrect a terminal task on a GREEN run,
but must still reopen genuine regressions on AMBER/RED/INCONCLUSIVE/unknown bands.
"""
import sys
from pathlib import Path

# scripts/ has no __init__.py, so import the module bare after putting scripts/ on
# the path — matching the sibling tests (test_detect_deploy_window.py et al.).
SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
from notion_sync_candidates import terminal_action, TERMINAL  # noqa: E402


def test_green_run_skips_every_terminal_status():
    # A passing run must not resurrect (or even annotate) a human-closed task.
    for status in TERMINAL:  # Done / Rejected / Archived
        assert terminal_action(status, "GREEN") == "skip"


def test_non_passing_bands_reopen_terminal_task():
    # Genuine regressions still reopen a Done task.
    for band in ("AMBER", "RED", "INCONCLUSIVE"):
        assert terminal_action("Done", band) == "reopen"


def test_unknown_or_missing_band_is_conservative_reopen():
    # If the band can't be read, prefer reopening so a real regression is never dropped.
    for band in (None, "", "N/A"):
        assert terminal_action("Done", band) == "reopen"


def test_open_task_is_note_only_regardless_of_band():
    # An already-open task just gets the run note; Status is left untouched.
    for band in ("GREEN", "AMBER", "RED", None):
        assert terminal_action("Ready for AI", band) == "note-only"
        assert terminal_action("AI in Progress", band) == "note-only"
        assert terminal_action("Human Review", band) == "note-only"


def test_aiq1377_scenario_done_p0_on_green_deploy_window():
    # The exact bug: a Done P0 seen on a GREEN (passing) deploy-window run → skip.
    assert terminal_action("Done", "GREEN") == "skip"
