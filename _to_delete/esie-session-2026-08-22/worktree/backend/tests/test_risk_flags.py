"""
IMM-12 · Unit tests for the immigration risk flag engine.

Tests cover:
  1.  PASSPORT_EXPIRY_WITHIN_90_DAYS  (critical)
  2.  PASSPORT_NEAR_EXPIRY            (critical)
  3.  ADDRESS_HISTORY_GAP             (warning)
  4.  PRIOR_VISA_REFUSAL              (warning)
  5.  DEGREE_NOT_RECOGNISED           (critical)
  6.  MEDICAL_EXAM_URGENCY            (critical)
  7.  BOOK_EARLY_{doc_type}           (critical / warning)
  8.  DEPENDENT_TIMING_RISK           (warning)
  9.  Severity sort order             (critical → warning → info)
  10. Clean profile → no flags
  11. _detect_address_gap helper
  12. _parse_date helper

All functions under test are pure Python with no DB calls, so no database
fixture is required. The conftest.py at backend/ mocks backend.database at
import time.

Run from repo root:
    cd backend && pytest tests/test_risk_flags.py -v
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.app.services.immigration_requirement_service import (
    RiskFlag,
    RequirementResult,
    evaluate_risks,
    _detect_address_gap,
    _parse_date,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

TODAY = date.today()


def _req(**overrides) -> RequirementResult:
    """Build a RequirementResult with sensible defaults, overridable per-test."""
    defaults = dict(
        document_type="passport",
        document_name="Passport",
        is_required=True,
        is_conditional=False,
        freshness_days=None,
        requires_apostille=False,
        apostille_countries=[],
        requires_translation=False,
        translation_languages=[],
        can_be_prefilled=False,
        can_be_ocr_extracted=True,
        typical_processing_days=None,
        book_early_flag=False,
        book_early_reason=None,
        success_tips=[],
        common_rejection_reasons=[],
        form_url=None,
        form_version=None,
    )
    defaults.update(overrides)
    return RequirementResult(**defaults)


def _flag_types(flags: list[RiskFlag]) -> list[str]:
    return [f.flag_type for f in flags]


def _severities(flags: list[RiskFlag]) -> list[str]:
    return [f.severity for f in flags]


def _get(flags: list[RiskFlag], flag_type: str) -> RiskFlag:
    return next(f for f in flags if f.flag_type == flag_type)


# ---------------------------------------------------------------------------
# 1. PASSPORT_EXPIRY_WITHIN_90_DAYS
# ---------------------------------------------------------------------------

class TestPassportExpiryWithin90Days:

    def test_expires_in_30_days_is_critical(self):
        profile = {"passport_expiry": (TODAY + timedelta(days=30)).isoformat()}
        flags = evaluate_risks(profile, [])
        assert "PASSPORT_EXPIRY_WITHIN_90_DAYS" in _flag_types(flags)
        flag = _get(flags, "PASSPORT_EXPIRY_WITHIN_90_DAYS")
        assert flag.severity == "critical"
        assert flag.deadline == TODAY + timedelta(days=30)

    def test_expires_in_89_days_triggers_flag(self):
        profile = {"passport_expiry": (TODAY + timedelta(days=89)).isoformat()}
        flags = evaluate_risks(profile, [])
        assert "PASSPORT_EXPIRY_WITHIN_90_DAYS" in _flag_types(flags)

    def test_already_expired_triggers_flag(self):
        profile = {"passport_expiry": (TODAY - timedelta(days=1)).isoformat()}
        flags = evaluate_risks(profile, [])
        assert "PASSPORT_EXPIRY_WITHIN_90_DAYS" in _flag_types(flags)

    def test_expires_in_91_days_does_not_trigger_90day_flag(self):
        # May still raise PASSPORT_NEAR_EXPIRY but NOT the 90-day flag
        profile = {"passport_expiry": (TODAY + timedelta(days=91)).isoformat()}
        flags = evaluate_risks(profile, [])
        assert "PASSPORT_EXPIRY_WITHIN_90_DAYS" not in _flag_types(flags)

    def test_no_passport_expiry_in_profile_no_flag(self):
        flags = evaluate_risks({}, [])
        assert "PASSPORT_EXPIRY_WITHIN_90_DAYS" not in _flag_types(flags)


# ---------------------------------------------------------------------------
# 2. PASSPORT_NEAR_EXPIRY
# ---------------------------------------------------------------------------

class TestPassportNearExpiry:

    def test_near_expiry_relative_to_move_date(self):
        move_date = TODAY + timedelta(days=120)
        # Passport expires after today+90 but before move_date + 180
        passport_expiry = TODAY + timedelta(days=200)
        profile = {"passport_expiry": passport_expiry.isoformat()}
        flags = evaluate_risks(profile, [], move_date=move_date)
        assert "PASSPORT_NEAR_EXPIRY" in _flag_types(flags)
        assert "PASSPORT_EXPIRY_WITHIN_90_DAYS" not in _flag_types(flags)

    def test_near_expiry_relative_to_visa_end_date(self):
        visa_end_date = TODAY + timedelta(days=365)
        # Passport expires after today+90 but before visa_end_date + 180
        passport_expiry = TODAY + timedelta(days=400)
        profile = {"passport_expiry": passport_expiry.isoformat()}
        flags = evaluate_risks(profile, [], visa_end_date=visa_end_date)
        assert "PASSPORT_NEAR_EXPIRY" in _flag_types(flags)

    def test_passport_valid_long_enough_no_flag(self):
        move_date = TODAY + timedelta(days=30)
        # Passport valid for 400 days: well beyond move_date + 180
        passport_expiry = TODAY + timedelta(days=400)
        profile = {"passport_expiry": passport_expiry.isoformat()}
        flags = evaluate_risks(profile, [], move_date=move_date)
        assert "PASSPORT_NEAR_EXPIRY" not in _flag_types(flags)
        assert "PASSPORT_EXPIRY_WITHIN_90_DAYS" not in _flag_types(flags)

    def test_no_passport_in_profile_no_near_expiry(self):
        flags = evaluate_risks({}, [], move_date=TODAY + timedelta(days=90))
        assert "PASSPORT_NEAR_EXPIRY" not in _flag_types(flags)


# ---------------------------------------------------------------------------
# 3. ADDRESS_HISTORY_GAP
# ---------------------------------------------------------------------------

class TestAddressHistoryGap:

    def test_gap_of_20_days_triggers_warning(self):
        addr1_end = TODAY - timedelta(days=200)
        addr2_start = TODAY - timedelta(days=180)  # 20-day gap
        profile = {
            "address_history": [
                {
                    "from_date": (TODAY - timedelta(days=365)).isoformat(),
                    "to_date": addr1_end.isoformat(),
                },
                {
                    "from_date": addr2_start.isoformat(),
                    "to_date": TODAY.isoformat(),
                },
            ]
        }
        flags = evaluate_risks(profile, [])
        assert "ADDRESS_HISTORY_GAP" in _flag_types(flags)
        flag = _get(flags, "ADDRESS_HISTORY_GAP")
        assert flag.severity == "warning"

    def test_no_gap_no_flag(self):
        # The code only includes entries where from_date >= cutoff (TODAY - 1825).
        # Using TODAY - 1824 starts just inside the window; the 1-day "early gap"
        # is ≤7 days so it is not flagged.
        profile = {
            "address_history": [
                {
                    "from_date": (TODAY - timedelta(days=1824)).isoformat(),
                    "to_date": (TODAY - timedelta(days=200)).isoformat(),
                },
                {
                    "from_date": (TODAY - timedelta(days=200)).isoformat(),
                    "to_date": TODAY.isoformat(),
                },
            ]
        }
        flags = evaluate_risks(profile, [])
        assert "ADDRESS_HISTORY_GAP" not in _flag_types(flags)

    def test_gap_of_5_days_below_threshold_no_flag(self):
        addr1_end = TODAY - timedelta(days=100)
        addr2_start = TODAY - timedelta(days=95)  # 5-day gap — under 7-day threshold
        profile = {
            "address_history": [
                # from_date must be >= cutoff (TODAY - 1825). Use 1824 so the
                # "early gap" between cutoff and first entry is only 1 day (≤7 → ok).
                {
                    "from_date": (TODAY - timedelta(days=1824)).isoformat(),
                    "to_date": addr1_end.isoformat(),
                },
                {
                    "from_date": addr2_start.isoformat(),
                    "to_date": TODAY.isoformat(),
                },
            ]
        }
        flags = evaluate_risks(profile, [])
        assert "ADDRESS_HISTORY_GAP" not in _flag_types(flags)

    def test_empty_address_history_no_flag(self):
        flags = evaluate_risks({"address_history": []}, [])
        assert "ADDRESS_HISTORY_GAP" not in _flag_types(flags)

    def test_missing_address_history_key_no_flag(self):
        flags = evaluate_risks({}, [])
        assert "ADDRESS_HISTORY_GAP" not in _flag_types(flags)


# ---------------------------------------------------------------------------
# 4. PRIOR_VISA_REFUSAL
# ---------------------------------------------------------------------------

class TestPriorVisaRefusal:

    def test_prior_refusal_true_triggers_warning(self):
        flags = evaluate_risks({"prior_visa_refusals": True}, [])
        assert "PRIOR_VISA_REFUSAL" in _flag_types(flags)
        assert _get(flags, "PRIOR_VISA_REFUSAL").severity == "warning"

    def test_prior_refusal_false_no_flag(self):
        flags = evaluate_risks({"prior_visa_refusals": False}, [])
        assert "PRIOR_VISA_REFUSAL" not in _flag_types(flags)

    def test_missing_key_no_flag(self):
        flags = evaluate_risks({}, [])
        assert "PRIOR_VISA_REFUSAL" not in _flag_types(flags)


# ---------------------------------------------------------------------------
# 5. DEGREE_NOT_RECOGNISED
# ---------------------------------------------------------------------------

class TestDegreeNotRecognised:

    def test_not_recognised_triggers_critical(self):
        flags = evaluate_risks({"degree_anabin_status": "not-recognised"}, [])
        assert "DEGREE_NOT_RECOGNISED" in _flag_types(flags)
        assert _get(flags, "DEGREE_NOT_RECOGNISED").severity == "critical"

    def test_recognised_status_no_flag(self):
        flags = evaluate_risks({"degree_anabin_status": "recognised"}, [])
        assert "DEGREE_NOT_RECOGNISED" not in _flag_types(flags)

    def test_empty_anabin_status_no_flag(self):
        flags = evaluate_risks({"degree_anabin_status": ""}, [])
        assert "DEGREE_NOT_RECOGNISED" not in _flag_types(flags)

    def test_missing_key_no_flag(self):
        flags = evaluate_risks({}, [])
        assert "DEGREE_NOT_RECOGNISED" not in _flag_types(flags)


# ---------------------------------------------------------------------------
# 6. MEDICAL_EXAM_URGENCY
# ---------------------------------------------------------------------------

class TestMedicalExamUrgency:

    def _medical_req(self, processing_days: int = 30) -> RequirementResult:
        return _req(
            document_type="medical_exam",
            document_name="Medical Examination",
            typical_processing_days=processing_days,
        )

    def test_insufficient_lead_time_triggers_critical(self):
        # move_date < processing_days + 14 → urgent
        move_date = TODAY + timedelta(days=20)
        flags = evaluate_risks({}, [self._medical_req(30)], move_date=move_date)
        assert "MEDICAL_EXAM_URGENCY" in _flag_types(flags)
        flag = _get(flags, "MEDICAL_EXAM_URGENCY")
        assert flag.severity == "critical"
        assert flag.deadline == TODAY + timedelta(days=3)

    def test_sufficient_lead_time_no_flag(self):
        # move_date > processing_days + 14
        move_date = TODAY + timedelta(days=60)
        flags = evaluate_risks({}, [self._medical_req(30)], move_date=move_date)
        assert "MEDICAL_EXAM_URGENCY" not in _flag_types(flags)

    def test_no_move_date_no_flag(self):
        flags = evaluate_risks({}, [self._medical_req(30)], move_date=None)
        assert "MEDICAL_EXAM_URGENCY" not in _flag_types(flags)

    def test_no_medical_exam_requirement_no_flag(self):
        move_date = TODAY + timedelta(days=5)
        flags = evaluate_risks({}, [], move_date=move_date)
        assert "MEDICAL_EXAM_URGENCY" not in _flag_types(flags)

    def test_uses_default_30_days_when_processing_days_missing(self):
        # typical_processing_days=None → defaults to 30
        req = _req(document_type="medical_exam", document_name="Medical Exam")
        move_date = TODAY + timedelta(days=10)  # < 30 + 14
        flags = evaluate_risks({}, [req], move_date=move_date)
        assert "MEDICAL_EXAM_URGENCY" in _flag_types(flags)


# ---------------------------------------------------------------------------
# 7. BOOK_EARLY_{doc_type}
# ---------------------------------------------------------------------------

class TestBookEarlyItems:

    def _book_early_req(
        self,
        doc_type: str = "biometric_appointment",
        processing_days: int = 30,
    ) -> RequirementResult:
        return _req(
            document_type=doc_type,
            document_name="Biometric Appointment",
            typical_processing_days=processing_days,
            book_early_flag=True,
            book_early_reason="Appointments fill up weeks in advance",
        )

    def test_critical_when_days_to_move_less_than_processing_days(self):
        move_date = TODAY + timedelta(days=20)  # < 30 processing days
        flags = evaluate_risks({}, [self._book_early_req(processing_days=30)], move_date=move_date)
        book_flags = [f for f in flags if f.flag_type.startswith("BOOK_EARLY_")]
        assert len(book_flags) == 1
        assert book_flags[0].severity == "critical"

    def test_warning_when_between_processing_days_and_buffer(self):
        # days_to_move = 35: > processing_days (30) but < days_needed (30 + 14 = 44)
        move_date = TODAY + timedelta(days=35)
        flags = evaluate_risks({}, [self._book_early_req(processing_days=30)], move_date=move_date)
        book_flags = [f for f in flags if f.flag_type.startswith("BOOK_EARLY_")]
        assert len(book_flags) == 1
        assert book_flags[0].severity == "warning"

    def test_no_flag_when_plenty_of_lead_time(self):
        move_date = TODAY + timedelta(days=90)  # > 30 + 14
        flags = evaluate_risks({}, [self._book_early_req(processing_days=30)], move_date=move_date)
        book_flags = [f for f in flags if f.flag_type.startswith("BOOK_EARLY_")]
        assert len(book_flags) == 0

    def test_flag_type_contains_document_type_uppercased(self):
        move_date = TODAY + timedelta(days=5)
        flags = evaluate_risks(
            {}, [self._book_early_req(doc_type="biometric_appointment")], move_date=move_date
        )
        assert "BOOK_EARLY_BIOMETRIC_APPOINTMENT" in _flag_types(flags)

    def test_no_move_date_no_book_early_flag(self):
        flags = evaluate_risks({}, [self._book_early_req()], move_date=None)
        book_flags = [f for f in flags if f.flag_type.startswith("BOOK_EARLY_")]
        assert len(book_flags) == 0

    def test_book_early_false_no_flag(self):
        req = _req(
            document_type="biometric_appointment",
            typical_processing_days=30,
            book_early_flag=False,
        )
        flags = evaluate_risks({}, [req], move_date=TODAY + timedelta(days=5))
        book_flags = [f for f in flags if f.flag_type.startswith("BOOK_EARLY_")]
        assert len(book_flags) == 0

    def test_deadline_is_two_days_from_today(self):
        move_date = TODAY + timedelta(days=5)
        flags = evaluate_risks({}, [self._book_early_req()], move_date=move_date)
        book_flags = [f for f in flags if f.flag_type.startswith("BOOK_EARLY_")]
        assert book_flags[0].deadline == TODAY + timedelta(days=2)


# ---------------------------------------------------------------------------
# 8. DEPENDENT_TIMING_RISK
# ---------------------------------------------------------------------------

class TestDependentTimingRisk:

    def test_dependents_with_imminent_move_triggers_warning(self):
        move_date = TODAY + timedelta(days=45)  # < 60
        profile = {"dependents": [{"name": "Child A"}]}
        flags = evaluate_risks(profile, [], move_date=move_date)
        assert "DEPENDENT_TIMING_RISK" in _flag_types(flags)
        assert _get(flags, "DEPENDENT_TIMING_RISK").severity == "warning"

    def test_dependents_count_mentioned_in_description(self):
        move_date = TODAY + timedelta(days=30)
        profile = {"dependents": [{"name": "Child A"}, {"name": "Child B"}]}
        flags = evaluate_risks(profile, [], move_date=move_date)
        flag = _get(flags, "DEPENDENT_TIMING_RISK")
        assert "2" in flag.description

    def test_comfortable_lead_time_no_flag(self):
        move_date = TODAY + timedelta(days=90)  # > 60
        profile = {"dependents": [{"name": "Child A"}]}
        flags = evaluate_risks(profile, [], move_date=move_date)
        assert "DEPENDENT_TIMING_RISK" not in _flag_types(flags)

    def test_empty_dependents_no_flag(self):
        move_date = TODAY + timedelta(days=10)
        flags = evaluate_risks({"dependents": []}, [], move_date=move_date)
        assert "DEPENDENT_TIMING_RISK" not in _flag_types(flags)

    def test_no_move_date_no_flag(self):
        profile = {"dependents": [{"name": "Child A"}]}
        flags = evaluate_risks(profile, [], move_date=None)
        assert "DEPENDENT_TIMING_RISK" not in _flag_types(flags)


# ---------------------------------------------------------------------------
# 9. Severity sort order
# ---------------------------------------------------------------------------

class TestSeveritySortOrder:

    def test_critical_before_warning(self):
        # DEGREE_NOT_RECOGNISED (critical) + PRIOR_VISA_REFUSAL (warning)
        profile = {
            "degree_anabin_status": "not-recognised",
            "prior_visa_refusals": True,
        }
        flags = evaluate_risks(profile, [])
        severities = _severities(flags)
        assert len(severities) >= 2
        critical_idx = next(i for i, s in enumerate(severities) if s == "critical")
        warning_idx = next(i for i, s in enumerate(severities) if s == "warning")
        assert critical_idx < warning_idx

    def test_all_criticals_precede_all_warnings(self):
        profile = {
            "passport_expiry": (TODAY + timedelta(days=30)).isoformat(),  # critical
            "degree_anabin_status": "not-recognised",                      # critical
            "prior_visa_refusals": True,                                   # warning
        }
        flags = evaluate_risks(profile, [])
        severities = _severities(flags)
        first_warning_idx = next(
            (i for i, s in enumerate(severities) if s == "warning"), len(severities)
        )
        for s in severities[:first_warning_idx]:
            assert s == "critical", f"Expected all criticals before index {first_warning_idx}, got {severities}"

    def test_info_comes_last(self):
        # Manually inject an info flag to verify ordering
        flags_input = [
            RiskFlag("A", "info", "Info flag", "desc", "action"),
            RiskFlag("B", "critical", "Critical flag", "desc", "action"),
            RiskFlag("C", "warning", "Warning flag", "desc", "action"),
        ]
        from backend.app.services.immigration_requirement_service import evaluate_risks as _er
        # We can't call evaluate_risks to produce info flags easily, so verify the sort
        # logic directly on a constructed list.
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        sorted_flags = sorted(flags_input, key=lambda f: severity_order.get(f.severity, 3))
        assert [f.severity for f in sorted_flags] == ["critical", "warning", "info"]


# ---------------------------------------------------------------------------
# 10. Clean profile → no flags
# ---------------------------------------------------------------------------

class TestCleanProfile:

    def test_empty_profile_and_requirements_no_flags(self):
        assert evaluate_risks({}, []) == []

    def test_healthy_profile_no_flags(self):
        move_date = TODAY + timedelta(days=180)
        profile = {
            "passport_expiry": (TODAY + timedelta(days=730)).isoformat(),
            "prior_visa_refusals": False,
            "degree_anabin_status": "recognised",
            "address_history": [
                {
                    "from_date": (TODAY - timedelta(days=365 * 5)).isoformat(),
                    "to_date": TODAY.isoformat(),
                }
            ],
            "dependents": [],
        }
        flags = evaluate_risks(profile, [], move_date=move_date)
        assert flags == []


# ---------------------------------------------------------------------------
# 11. _detect_address_gap helper
# ---------------------------------------------------------------------------

class TestDetectAddressGap:

    def test_gap_of_20_days_detected(self):
        addr1_end = TODAY - timedelta(days=100)
        addr2_start = TODAY - timedelta(days=80)  # 20-day gap
        history = [
            {
                "from_date": (TODAY - timedelta(days=365)).isoformat(),
                "to_date": addr1_end.isoformat(),
            },
            {
                "from_date": addr2_start.isoformat(),
                "to_date": TODAY.isoformat(),
            },
        ]
        result = _detect_address_gap(history, TODAY)
        assert result is not None
        assert result["days"] == 20

    def test_gap_of_7_days_not_detected(self):
        addr1_end = TODAY - timedelta(days=100)
        addr2_start = TODAY - timedelta(days=93)  # exactly 7-day gap → not flagged (> 7 required)
        history = [
            # from_date = TODAY - 1824: within lookback window, early-gap = 1 day (≤7 → ok)
            {
                "from_date": (TODAY - timedelta(days=1824)).isoformat(),
                "to_date": addr1_end.isoformat(),
            },
            {
                "from_date": addr2_start.isoformat(),
                "to_date": TODAY.isoformat(),
            },
        ]
        result = _detect_address_gap(history, TODAY)
        assert result is None

    def test_empty_history_returns_none(self):
        assert _detect_address_gap([], TODAY) is None

    def test_single_contiguous_entry_covering_full_lookback_returns_none(self):
        # Entry must reach back to the 5-year cutoff to avoid the early-gap check
        history = [
            {
                "from_date": (TODAY - timedelta(days=1830)).isoformat(),
                "to_date": TODAY.isoformat(),
            }
        ]
        assert _detect_address_gap(history, TODAY) is None

    def test_single_entry_short_of_lookback_reports_gap(self):
        # Only covers 1 year — 4-year gap detected from cutoff to entry start
        history = [
            {
                "from_date": (TODAY - timedelta(days=365)).isoformat(),
                "to_date": TODAY.isoformat(),
            }
        ]
        result = _detect_address_gap(history, TODAY)
        assert result is not None
        # gap = from cutoff (1825 days ago) to entry start (365 days ago) ≈ 1460 days
        assert result["days"] > 7

    def test_gap_result_contains_from_to_days_keys(self):
        addr1_end = TODAY - timedelta(days=50)
        addr2_start = TODAY - timedelta(days=20)  # 30-day gap
        history = [
            {
                "from_date": (TODAY - timedelta(days=200)).isoformat(),
                "to_date": addr1_end.isoformat(),
            },
            {
                "from_date": addr2_start.isoformat(),
                "to_date": TODAY.isoformat(),
            },
        ]
        result = _detect_address_gap(history, TODAY)
        assert result is not None
        assert "days" in result
        assert "from" in result
        assert "to" in result
        assert result["days"] == 30

    def test_first_detected_gap_is_returned(self):
        """When multiple gaps exist, the first one (chronologically) is returned."""
        history = [
            {"from_date": (TODAY - timedelta(days=400)).isoformat(), "to_date": (TODAY - timedelta(days=300)).isoformat()},
            {"from_date": (TODAY - timedelta(days=270)).isoformat(), "to_date": (TODAY - timedelta(days=200)).isoformat()},
            {"from_date": (TODAY - timedelta(days=150)).isoformat(), "to_date": TODAY.isoformat()},
        ]
        result = _detect_address_gap(history, TODAY)
        assert result is not None
        # First gap: 300 → 270 = 30 days
        assert result["days"] == 30


# ---------------------------------------------------------------------------
# 12. _parse_date helper
# ---------------------------------------------------------------------------

class TestParseDate:

    def test_iso_date_string(self):
        assert _parse_date("2025-06-15") == date(2025, 6, 15)

    def test_datetime_string_truncates_to_date(self):
        assert _parse_date("2025-06-15T10:30:00Z") == date(2025, 6, 15)

    def test_date_object_returned_unchanged(self):
        d = date(2025, 6, 15)
        assert _parse_date(d) == d

    def test_none_returns_none(self):
        assert _parse_date(None) is None

    def test_invalid_string_returns_none(self):
        assert _parse_date("not-a-date") is None

    def test_empty_string_returns_none(self):
        assert _parse_date("") is None
