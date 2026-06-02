"""Tests for backend/relopass/policy_evidence/ — C2-06 gap detector.

Covers the pure projection layer + registry + the three launch clause checks
(LANGUAGE_TRAINING, HOUSING_BENEFIT, IMMIGRATION_SUPPORT) + the detect_gaps
orchestrator. No I/O — exercises the contract the C2-06-FOLLOWUP Supabase
adapter is built on.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from datetime import datetime, timezone

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.relopass.policy_evidence import (  # noqa: E402
    Artefact,
    Case,
    FamilyMember,
    Gap,
    PolicyClause,
    Subject,
    detect_gaps,
    get,
    registered_clause_types,
)


def _uid() -> uuid.UUID:
    return uuid.uuid4()


def _clause(clause_type: str, params: dict, **kw) -> PolicyClause:
    return PolicyClause(
        policy_clause_id=kw.get("policy_clause_id", _uid()),
        hr_policy_id=kw.get("hr_policy_id", _uid()),
        clause_type=clause_type,
        parameters_json=params,
        bbox_citation=kw.get("bbox_citation"),
    )


def _case(**kw) -> Case:
    return Case(
        case_id=kw.get("case_id", _uid()),
        employer_id=kw.get("employer_id", _uid()),
        primary_employee_id=kw.get("primary_employee_id", _uid()),
        primary_employee_canonical_id=kw.get("primary_employee_canonical_id", _uid()),
        primary_employee_display_name=kw.get("primary_employee_display_name", "Alex Doe"),
        target_arrival_date=kw.get("target_arrival_date"),
        family_members=tuple(kw.get("family_members", ())),
        artefacts=tuple(kw.get("artefacts", ())),
    )


def _fm(rel: str, name: str = "Fam Member") -> FamilyMember:
    return FamilyMember(
        family_member_id=_uid(),
        relationship_type=rel,
        canonical_entity_id=_uid(),
        display_name=name,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Registry + projection models
# ─────────────────────────────────────────────────────────────────────────────


class RegistryTests(unittest.TestCase):
    def test_three_launch_checks_registered(self) -> None:
        self.assertEqual(
            set(registered_clause_types()),
            {"LANGUAGE_TRAINING", "HOUSING_BENEFIT", "IMMIGRATION_SUPPORT"},
        )

    def test_get_unknown_returns_none(self) -> None:
        self.assertIsNone(get("NOT_A_CLAUSE_TYPE"))

    def test_get_known_returns_check(self) -> None:
        self.assertIsNotNone(get("LANGUAGE_TRAINING"))


class ModelTests(unittest.TestCase):
    def test_subject_dedup_key_case(self) -> None:
        self.assertEqual(Subject(kind="CASE").dedup_key(), "CASE")

    def test_subject_dedup_key_family_member(self) -> None:
        fmid = _uid()
        s = Subject(kind="CHILD", family_member_id=fmid)
        self.assertEqual(s.dedup_key(), str(fmid))

    def test_find_artefacts_filters_by_kind(self) -> None:
        a = Artefact(artefact_id=_uid(), kind="housing_booking", subject_kind="CASE")
        b = Artefact(artefact_id=_uid(), kind="other", subject_kind="CASE")
        case = _case(artefacts=[a, b])
        found = case.find_artefacts(kind="housing_booking")
        self.assertEqual([x.kind for x in found], ["housing_booking"])

    def test_family_by_relationship(self) -> None:
        spouse = _fm("SPOUSE")
        child = _fm("CHILD")
        case = _case(family_members=[spouse, child])
        self.assertEqual(case.family_by_relationship("SPOUSE"), (spouse,))


# ─────────────────────────────────────────────────────────────────────────────
# LANGUAGE_TRAINING
# ─────────────────────────────────────────────────────────────────────────────


class LanguageTrainingTests(unittest.TestCase):
    def test_missing_booking_emits_gap(self) -> None:
        clause = _clause("LANGUAGE_TRAINING", {"for_employee_bool": True, "hours": 60})
        gaps = detect_gaps(_case(), [clause])
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].gap_type, "MISSING_BENEFIT_DELIVERY")
        self.assertEqual(gaps[0].subject.kind, "EMPLOYEE")

    def test_sufficient_hours_clears_gap(self) -> None:
        clause = _clause("LANGUAGE_TRAINING", {"for_employee_bool": True, "hours": 60})
        art = Artefact(
            artefact_id=_uid(),
            kind="language_training_booking",
            subject_kind="EMPLOYEE",
            magnitude=60,
            unit="hours",
        )
        gaps = detect_gaps(_case(artefacts=[art]), [clause])
        self.assertEqual(gaps, ())

    def test_below_entitlement_when_under_hours(self) -> None:
        clause = _clause("LANGUAGE_TRAINING", {"for_employee_bool": True, "hours": 60})
        art = Artefact(
            artefact_id=_uid(),
            kind="language_training_booking",
            subject_kind="EMPLOYEE",
            magnitude=20,
            unit="hours",
        )
        gaps = detect_gaps(_case(artefacts=[art]), [clause])
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].gap_type, "BELOW_ENTITLEMENT")

    def test_spouse_and_children_subjects(self) -> None:
        spouse = _fm("SPOUSE")
        child = _fm("CHILD")
        clause = _clause(
            "LANGUAGE_TRAINING",
            {"for_employee_bool": True, "for_spouse_bool": True, "for_children_bool": True, "hours": 10},
        )
        gaps = detect_gaps(_case(family_members=[spouse, child]), [clause])
        kinds = sorted(g.subject.kind for g in gaps)
        self.assertEqual(kinds, ["CHILD", "EMPLOYEE", "SPOUSE"])


# ─────────────────────────────────────────────────────────────────────────────
# HOUSING_BENEFIT
# ─────────────────────────────────────────────────────────────────────────────


class HousingBenefitTests(unittest.TestCase):
    def test_missing_housing_emits_case_gap(self) -> None:
        clause = _clause("HOUSING_BENEFIT", {"temporary_or_permanent": "TEMPORARY"})
        gaps = detect_gaps(_case(), [clause])
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].subject.kind, "CASE")

    def test_lease_document_clears_gap(self) -> None:
        clause = _clause("HOUSING_BENEFIT", {"temporary_or_permanent": "PERMANENT"})
        art = Artefact(
            artefact_id=_uid(), kind="housing_lease_document", subject_kind="CASE"
        )
        gaps = detect_gaps(_case(artefacts=[art]), [clause])
        self.assertEqual(gaps, ())


# ─────────────────────────────────────────────────────────────────────────────
# IMMIGRATION_SUPPORT
# ─────────────────────────────────────────────────────────────────────────────


class ImmigrationSupportTests(unittest.TestCase):
    def test_employee_always_in_scope(self) -> None:
        clause = _clause("IMMIGRATION_SUPPORT", {})
        gaps = detect_gaps(_case(), [clause])
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].subject.kind, "EMPLOYEE")

    def test_legal_counsel_engaged_clears_gap(self) -> None:
        clause = _clause("IMMIGRATION_SUPPORT", {})
        art = Artefact(
            artefact_id=_uid(), kind="legal_counsel_engaged", subject_kind="EMPLOYEE"
        )
        gaps = detect_gaps(_case(artefacts=[art]), [clause])
        self.assertEqual(gaps, ())

    def test_dependents_included_when_flag_set(self) -> None:
        spouse = _fm("SPOUSE")
        clause = _clause("IMMIGRATION_SUPPORT", {"dependent_permits_bool": True})
        gaps = detect_gaps(_case(family_members=[spouse]), [clause])
        self.assertEqual(sorted(g.subject.kind for g in gaps), ["EMPLOYEE", "SPOUSE"])

    def test_dependents_excluded_without_flag(self) -> None:
        spouse = _fm("SPOUSE")
        clause = _clause("IMMIGRATION_SUPPORT", {})
        gaps = detect_gaps(_case(family_members=[spouse]), [clause])
        self.assertEqual([g.subject.kind for g in gaps], ["EMPLOYEE"])


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator behaviour
# ─────────────────────────────────────────────────────────────────────────────


class DetectorOrchestrationTests(unittest.TestCase):
    def test_unknown_clause_type_skipped(self) -> None:
        clause = _clause("DEFERRED_CLAUSE_TYPE", {})
        self.assertEqual(detect_gaps(_case(), [clause]), ())

    def test_citation_propagated(self) -> None:
        cite = {"page": 3, "bbox": [0, 1, 2, 3]}
        clause = _clause(
            "HOUSING_BENEFIT", {"temporary_or_permanent": "BOTH"}, bbox_citation=cite
        )
        gaps = detect_gaps(_case(), [clause])
        self.assertEqual(gaps[0].citation, cite)

    def test_gap_carries_clause_and_case_ids(self) -> None:
        case = _case()
        clause = _clause("IMMIGRATION_SUPPORT", {})
        gap = detect_gaps(case, [clause])[0]
        self.assertEqual(gap.case_id, case.case_id)
        self.assertEqual(gap.policy_clause_id, clause.policy_clause_id)
        self.assertEqual(gap.clause_type, "IMMIGRATION_SUPPORT")

    def test_suggested_action_non_empty(self) -> None:
        clause = _clause("LANGUAGE_TRAINING", {"for_employee_bool": True, "hours": 40})
        gap = detect_gaps(_case(), [clause])[0]
        self.assertTrue(gap.suggested_action)

    def test_dedup_by_key(self) -> None:
        # Two identical clauses → distinct policy_clause_ids → distinct gaps;
        # but the same clause applied twice dedups.
        clause = _clause("IMMIGRATION_SUPPORT", {})
        gaps = detect_gaps(_case(), [clause, clause])
        self.assertEqual(len(gaps), 1)

    def test_multiple_clause_types_in_one_pass(self) -> None:
        clauses = [
            _clause("LANGUAGE_TRAINING", {"for_employee_bool": True, "hours": 30}),
            _clause("HOUSING_BENEFIT", {"temporary_or_permanent": "TEMPORARY"}),
            _clause("IMMIGRATION_SUPPORT", {}),
        ]
        gaps = detect_gaps(_case(), clauses)
        self.assertEqual(len(gaps), 3)
        self.assertEqual(
            sorted(g.clause_type for g in gaps),
            ["HOUSING_BENEFIT", "IMMIGRATION_SUPPORT", "LANGUAGE_TRAINING"],
        )


if __name__ == "__main__":
    unittest.main()
