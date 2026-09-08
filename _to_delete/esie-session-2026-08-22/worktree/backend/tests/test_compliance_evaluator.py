"""BL-Compliance.3 — unit tests for the compliance evaluator (AIQ-745).

Drives the pure firing logic + run_evaluation() through in-memory fakes (no DB,
no network). Covers the exact validation criterion — "permit expiring in 14 days
→ alert fires; clean case → no alert" — plus the other two seed rules and the
open-alert dedup.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, List, Sequence

from backend.app.services.compliance_evaluator import (
    AlertStore,
    CaseComplianceData,
    ComplianceRule,
    EvaluationResult,
    RuleFiring,
    evaluate,
    run_evaluation,
)

TODAY = date(2026, 6, 4)

# The 3 rules exactly as seeded by BL-Compliance.2.
PERMIT_RULE = ComplianceRule(
    id="rule-permit",
    category="immigration",
    severity="high",
    trigger_condition={
        "type": "date_threshold",
        "field": "permit_expiry_date",
        "operator": "within_days",
        "value": 60,
        "unit": "days",
    },
)
TAX_RULE = ComplianceRule(
    id="rule-tax",
    category="tax",
    severity="high",
    trigger_condition={
        "type": "day_count",
        "field": "days_present_in_host",
        "operator": "gte",
        "value": 183,
        "unit": "days",
    },
)
EMPLOYER_RULE = ComplianceRule(
    id="rule-employer",
    category="employer",
    severity="high",
    trigger_condition={
        "type": "missing_field",
        "field": "employer_registration_id",
        "operator": "is_null",
        "value": None,
    },
)
ALL_RULES = (PERMIT_RULE, TAX_RULE, EMPLOYER_RULE)


# ── in-memory fakes implementing the Protocols ──────────────────────────────


class FakeSource:
    def __init__(self, rules: Sequence[ComplianceRule], cases: Sequence[CaseComplianceData]):
        self._rules = list(rules)
        self._cases = list(cases)

    def active_rules(self) -> Sequence[ComplianceRule]:
        return self._rules

    def open_cases(self) -> Iterable[CaseComplianceData]:
        return list(self._cases)


class FakeStore:
    def __init__(self, existing: Sequence[tuple] = ()):  # (case_id, rule_id) pairs
        self._open = set(existing)
        self.inserted: List[tuple] = []

    def open_alert_exists(self, case_id: str, rule_id: str) -> bool:
        return (case_id, rule_id) in self._open

    def insert_alert(self, firing: RuleFiring, severity: str) -> None:
        self.inserted.append((firing.case_id, firing.rule_id, severity))
        self._open.add((firing.case_id, firing.rule_id))


def _clean_case(case_id: str = "case-clean") -> CaseComplianceData:
    """A case that should trip none of the rules."""
    return CaseComplianceData(
        case_id=case_id,
        permit_expiry_date=TODAY + timedelta(days=300),  # well beyond 60
        employer_registration_id="DE-HRB-12345",          # present
        days_present_in_host=10,                           # below 183
    )


# ── the validation criterion ─────────────────────────────────────────────────


def test_permit_expiring_in_14_days_fires_alert():
    case = CaseComplianceData(
        case_id="case-permit",
        permit_expiry_date=TODAY + timedelta(days=14),
        employer_registration_id="DE-HRB-1",
        days_present_in_host=5,
    )
    firings = evaluate(ALL_RULES, case, today=TODAY)
    assert [f.rule_id for f in firings] == ["rule-permit"]
    assert firings[0].detail["days_until"] == 14

    store = FakeStore()
    result = run_evaluation(FakeSource(ALL_RULES, [case]), store, today=TODAY)
    assert isinstance(result, EvaluationResult)
    assert result.alerts_created == 1
    assert store.inserted == [("case-permit", "rule-permit", "high")]


def test_clean_case_no_alert():
    case = _clean_case()
    assert evaluate(ALL_RULES, case, today=TODAY) == []

    store = FakeStore()
    result = run_evaluation(FakeSource(ALL_RULES, [case]), store, today=TODAY)
    assert result.alerts_created == 0
    assert store.inserted == []


# ── the other two rules ──────────────────────────────────────────────────────


def test_missing_employer_registration_fires():
    case = CaseComplianceData(
        case_id="case-emp",
        permit_expiry_date=TODAY + timedelta(days=300),
        employer_registration_id=None,
        days_present_in_host=5,
    )
    firings = evaluate(ALL_RULES, case, today=TODAY)
    assert [f.rule_id for f in firings] == ["rule-employer"]


def test_tax_183_day_threshold_fires():
    case = CaseComplianceData(
        case_id="case-tax",
        permit_expiry_date=TODAY + timedelta(days=300),
        employer_registration_id="X",
        days_present_in_host=200,
    )
    firings = evaluate(ALL_RULES, case, today=TODAY)
    assert [f.rule_id for f in firings] == ["rule-tax"]


def test_permit_just_outside_window_does_not_fire():
    case = CaseComplianceData(
        case_id="case-edge",
        permit_expiry_date=TODAY + timedelta(days=61),  # one past the 60-day window
        employer_registration_id="X",
        days_present_in_host=5,
    )
    assert evaluate(ALL_RULES, case, today=TODAY) == []


def test_unresolved_field_does_not_fire():
    # days_present_in_host unknown (e.g. no start date) -> tax rule can't evaluate.
    case = CaseComplianceData(
        case_id="case-null",
        permit_expiry_date=TODAY + timedelta(days=300),
        employer_registration_id="X",
        days_present_in_host=None,
    )
    assert evaluate((TAX_RULE,), case, today=TODAY) == []


# ── dedup ────────────────────────────────────────────────────────────────────


def test_existing_open_alert_is_not_duplicated():
    case = CaseComplianceData(
        case_id="case-permit",
        permit_expiry_date=TODAY + timedelta(days=14),
        employer_registration_id="X",
        days_present_in_host=5,
    )
    store = FakeStore(existing=[("case-permit", "rule-permit")])
    result = run_evaluation(FakeSource(ALL_RULES, [case]), store, today=TODAY)
    assert result.alerts_created == 0
    assert result.alerts_skipped_existing == 1
    assert store.inserted == []


def test_inactive_rule_is_skipped():
    inactive = ComplianceRule(
        id="rule-off",
        category="immigration",
        severity="high",
        trigger_condition=PERMIT_RULE.trigger_condition,
        active=False,
    )
    case = CaseComplianceData(
        case_id="c",
        permit_expiry_date=TODAY + timedelta(days=14),
    )
    assert evaluate((inactive,), case, today=TODAY) == []


# ── Phase C1: dry_run flag on run_evaluation ─────────────────────────────────


def test_run_evaluation_dry_run_reports_would_be_firings_without_inserting():
    """dry_run=True must count would-be firings but skip insert."""
    case = CaseComplianceData(
        case_id="case-permit",
        permit_expiry_date=TODAY + timedelta(days=14),
        employer_registration_id="DE-HRB-1",
        days_present_in_host=5,
    )
    store = FakeStore()
    result = run_evaluation(
        FakeSource(ALL_RULES, [case]), store, today=TODAY, dry_run=True
    )
    # Reported as if it would fire ...
    assert result.alerts_created == 1
    # ... but the store was never touched.
    assert store.inserted == []


def test_run_evaluation_default_still_persists():
    """Back-compat: dry_run defaults to False; existing behaviour unchanged."""
    case = CaseComplianceData(
        case_id="case-permit",
        permit_expiry_date=TODAY + timedelta(days=14),
        employer_registration_id="DE-HRB-1",
        days_present_in_host=5,
    )
    store = FakeStore()
    result = run_evaluation(FakeSource(ALL_RULES, [case]), store, today=TODAY)
    assert result.alerts_created == 1
    assert store.inserted == [("case-permit", "rule-permit", "high")]


# ── Phase A1: precondition_field guard for missing_field rules ───────────────


def test_missing_field_rule_skips_when_precondition_absent():
    """A missing_field rule with a precondition_field must NOT fire when the
    precondition is also null/false — i.e. intake has not started for this
    case, so we can't claim a field is 'missing' yet."""
    rule_with_precondition = ComplianceRule(
        id="rule-employer-pc",
        category="employer",
        severity="high",
        trigger_condition={
            "type": "missing_field",
            "field": "employer_registration_id",
            "operator": "is_null",
            "value": None,
            "precondition_field": "profile_exists",
        },
    )
    case_no_profile = CaseComplianceData(
        case_id="case-noprofile",
        employer_registration_id=None,
        profile_exists=False,
    )
    case_started_intake = CaseComplianceData(
        case_id="case-started",
        employer_registration_id=None,
        profile_exists=True,
    )
    firings_skip = evaluate([rule_with_precondition], case_no_profile, today=TODAY)
    firings_fire = evaluate([rule_with_precondition], case_started_intake, today=TODAY)
    assert firings_skip == []
    assert len(firings_fire) == 1
    assert firings_fire[0].rule_id == "rule-employer-pc"


def test_sql_data_source_sets_profile_exists_from_row():
    """SqlComplianceDataSource.open_cases() must populate profile_exists from
    the joined imm_employee_profiles lateral row."""
    from backend.app.services.compliance_evaluator import SqlComplianceDataSource

    class FakeRowResult:
        def __init__(self, rows):
            self._rows = rows

        def mappings(self):
            return self

        def all(self):
            return self._rows

    class FakeSession:
        def execute(self, sql, params=None):
            return FakeRowResult([
                {
                    "case_id": "case-A",
                    "permit_expiry_date": None,
                    "employer_registration_id": None,
                    "expected_start_date": None,
                    "profile_exists": False,
                },
                {
                    "case_id": "case-B",
                    "permit_expiry_date": None,
                    "employer_registration_id": None,
                    "expected_start_date": None,
                    "profile_exists": True,
                },
            ])

    source = SqlComplianceDataSource(FakeSession(), today=TODAY)
    cases = list(source.open_cases())
    assert len(cases) == 2
    assert cases[0].case_id == "case-A" and cases[0].profile_exists is False
    assert cases[1].case_id == "case-B" and cases[1].profile_exists is True


def test_missing_field_rule_without_precondition_still_fires():
    """Back-compat: a missing_field rule that does NOT specify precondition_field
    behaves exactly as before (fires when the target field is null)."""
    case = CaseComplianceData(
        case_id="case-no-pc",
        employer_registration_id=None,
        profile_exists=False,  # ignored — rule has no precondition_field
    )
    firings = evaluate([EMPLOYER_RULE], case, today=TODAY)
    assert [f.rule_id for f in firings] == ["rule-employer"]
