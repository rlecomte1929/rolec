"""AIQ-378a (AIQ-816) — unit tests for the read-only case-delay signal service.

Covers the subtask's Validation Criteria against fixture milestones:
  * an on-time case is not flagged,
  * a case N days late is flagged with the correct days_behind,
  * a case with no expected (target) date is not flagged,
  * scan returns [] on an empty / active-less DB,
plus the completion-status, worst-per-case, severity, and env-threshold edges.
"""
from __future__ import annotations

import os
import sys
from datetime import date

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import case_delay_monitor as cdm  # noqa: E402

NOW = date(2026, 6, 9)


def _ms(case_id, mtype, status, target_date, completed_date=None):
    return {
        "case_id": case_id,
        "milestone_type": mtype,
        "status": status,
        "target_date": target_date,
        "completed_date": completed_date,
    }


# ── Validation Criteria ─────────────────────────────────────────────────────

def test_on_time_case_not_flagged():
    # target_date today and in the future → days_behind < warn (3) → not flagged.
    rows = [
        _ms("c1", "visa_decision", "in_progress", date(2026, 6, 9)),     # 0 behind
        _ms("c2", "visa_decision", "pending", date(2026, 6, 20)),        # future
        _ms("c3", "visa_decision", "pending", date(2026, 6, 7)),         # 2 behind < 3
    ]
    assert cdm.evaluate_case_delays(rows, now=NOW) == []


def test_late_case_flagged_with_correct_days_behind():
    rows = [_ms("c1", "biometric_appointment", "pending", date(2026, 6, 1))]  # 8 days late
    out = cdm.evaluate_case_delays(rows, now=NOW)
    assert len(out) == 1
    sig = out[0]
    assert sig["case_id"] == "c1"
    assert sig["stage"] == "biometric_appointment"
    assert sig["expected_date"] == "2026-06-01"
    assert sig["days_behind"] == 8


def test_no_expected_date_not_flagged():
    rows = [_ms("c1", "dossier_assembly", "pending", None)]  # no target_date
    assert cdm.evaluate_case_delays(rows, now=NOW) == []


def test_empty_db_returns_empty(monkeypatch):
    monkeypatch.setattr(cdm, "_fetch_active_case_milestones", lambda: [])
    assert cdm.scan_active_cases(now=NOW) == []


# ── Completion / terminal-status edges ──────────────────────────────────────

def test_completed_milestone_not_flagged():
    rows = [
        _ms("c1", "visa_issued", "completed", date(2026, 5, 1)),  # terminal status
        _ms("c2", "visa_issued", "pending", date(2026, 5, 1), completed_date=date(2026, 5, 30)),  # has completed_date
        _ms("c3", "visa_issued", "not_applicable", date(2026, 5, 1)),  # not applicable
    ]
    assert cdm.evaluate_case_delays(rows, now=NOW) == []


def test_blocked_milestone_is_flagged():
    # 'blocked' is non-terminal — a blocked, overdue milestone IS behind.
    rows = [_ms("c1", "application_filed", "blocked", date(2026, 6, 1))]
    out = cdm.evaluate_case_delays(rows, now=NOW)
    assert len(out) == 1 and out[0]["days_behind"] == 8


# ── Worst-per-case + severity ───────────────────────────────────────────────

def test_one_signal_per_case_uses_most_overdue_milestone():
    rows = [
        _ms("c1", "dossier_assembly", "pending", date(2026, 6, 5)),       # 4 behind
        _ms("c1", "application_filed", "in_progress", date(2026, 5, 20)), # 20 behind (worst)
    ]
    out = cdm.evaluate_case_delays(rows, now=NOW)
    assert len(out) == 1
    assert out[0]["stage"] == "application_filed"
    assert out[0]["days_behind"] == 20


def test_severity_warning_vs_critical():
    rows = [
        _ms("c1", "visa_decision", "pending", date(2026, 6, 4)),   # 5 behind (>=3, <7) → warning
        _ms("c2", "visa_decision", "pending", date(2026, 5, 30)),  # 10 behind (>=7) → critical
    ]
    out = {s["case_id"]: s for s in cdm.evaluate_case_delays(rows, now=NOW)}
    assert out["c1"]["severity"] == "warning"
    assert out["c2"]["severity"] == "critical"


def test_results_sorted_most_behind_first():
    rows = [
        _ms("a", "x", "pending", date(2026, 6, 4)),    # 5 behind
        _ms("b", "x", "pending", date(2026, 5, 20)),   # 20 behind
        _ms("c", "x", "pending", date(2026, 6, 1)),    # 8 behind
    ]
    out = cdm.evaluate_case_delays(rows, now=NOW)
    assert [s["case_id"] for s in out] == ["b", "c", "a"]


def test_iso_string_target_date_is_parsed():
    rows = [_ms("c1", "arrival", "pending", "2026-06-01")]  # string instead of date
    out = cdm.evaluate_case_delays(rows, now=NOW)
    assert out and out[0]["days_behind"] == 8


# ── Env thresholds ──────────────────────────────────────────────────────────

def test_warn_days_env_default_and_override():
    assert cdm.load_warn_days({}) == cdm.DEFAULT_WARN_DAYS
    assert cdm.load_warn_days({"CASE_DELAY_WARN_DAYS": "5"}) == 5
    assert cdm.load_warn_days({"CASE_DELAY_WARN_DAYS": "-2"}) == 0          # clamped low
    assert cdm.load_warn_days({"CASE_DELAY_WARN_DAYS": "999999"}) == cdm._MAX_DAYS  # clamped high
    assert cdm.load_warn_days({"CASE_DELAY_WARN_DAYS": "junk"}) == cdm.DEFAULT_WARN_DAYS


def test_crit_days_never_below_warn():
    # crit configured below warn → clamped up to warn.
    src = {"CASE_DELAY_WARN_DAYS": "10", "CASE_DELAY_CRIT_DAYS": "4"}
    assert cdm.load_crit_days(src) == 10


def test_custom_warn_threshold_changes_flagging():
    rows = [_ms("c1", "visa_decision", "pending", date(2026, 6, 7))]  # 2 behind
    assert cdm.evaluate_case_delays(rows, now=NOW, warn_days=2) != []  # flagged at warn=2
    assert cdm.evaluate_case_delays(rows, now=NOW, warn_days=3) == []  # not at warn=3


# ── AIQ-2041: the source table, the status filter, and the carried fields ───
#
# The whole proactive loop was inert for two reasons at once, and each of these
# tests fails against the pre-AIQ-2041 code.

def test_query_reads_case_milestones_not_the_empty_immigration_table():
    """The signal must come from the table that actually holds milestones.

    Measured on prod 2026-08-22: public.immigration_milestones 0 rows;
    public.case_milestones 14,282 rows (861 joining relocation_cases). Pointing at
    the former is why scan_active_cases() had never returned a signal.
    """
    sql = cdm._ACTIVE_MILESTONES_SQL
    assert "public.case_milestones" in sql
    assert "immigration_milestones" not in sql
    # actual_date is case_milestones' completion column; the pure core reads
    # `completed_date`, so the alias must survive any future edit of this query.
    assert "m.actual_date    AS completed_date" in sql


def test_query_does_not_require_status_active():
    """`relocation_cases.status = 'active'` matched 5 of 1,940 rows in prod.

    status is NULL on 1,925 of them — the canonical lifecycle lives on
    case_assignments, not here — so requiring 'active' is a filter that can
    essentially never match. Swapping the table WITHOUT also fixing this still
    yielded 0 signals.
    """
    sql = cdm._ACTIVE_MILESTONES_SQL
    assert "rc.status = :active_status" not in sql
    assert "NOT IN :closed_statuses" in sql
    assert "closed" in cdm._CLOSED_CASE_STATUSES


def test_done_status_is_terminal():
    """case_milestones' completion status is 'done', not 'completed'.

    The old _TERMINAL_STATUSES ({'completed','not_applicable'}) did not contain it,
    so a finished milestone whose actual_date happened to be unset would have been
    reported to HR as overdue.
    """
    assert "done" in cdm._TERMINAL_STATUSES
    rows = [_ms("c1", "task_passport_upload", "done", date(2026, 6, 1))]
    assert cdm.evaluate_case_delays(rows, now=NOW) == []


def test_title_and_owner_are_carried_onto_the_signal():
    """Needed so an unrecognised stage can be described by its real title."""
    rows = [
        {
            "case_id": "c1",
            "milestone_type": "pre_departure_ai_01",
            "status": "pending",
            "target_date": date(2026, 6, 1),
            "completed_date": None,
            "title": "Gather core identity and employment documents",
            "owner": "EMPLOYEE",  # deliberately upper-case: the column holds both
        }
    ]
    signal = cdm.evaluate_case_delays(rows, now=NOW)[0]
    assert signal["title"] == "Gather core identity and employment documents"
    assert signal["owner"] == "employee"  # normalised


def test_missing_title_and_owner_default_to_empty_not_none():
    """The partner-sync path supplies neither; it must not crash or emit None."""
    signal = cdm.evaluate_case_delays(
        [_ms("c1", "visa_decision", "pending", date(2026, 6, 1))], now=NOW
    )[0]
    assert signal["title"] == ""
    assert signal["owner"] == ""
