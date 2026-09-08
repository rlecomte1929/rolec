"""
Compliance engine for HR review.
Deterministic checks against mobility rules.
"""
from typing import Dict, Any, List
from datetime import datetime, date
import json
import os


class ComplianceEngine:
    def __init__(self, rules_path: str = "mobility_rules.json"):
        self.rules_path = rules_path

    def load_rules(self) -> Dict[str, Any]:
        if os.path.exists(self.rules_path):
            with open(self.rules_path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        # Fallback minimal rules if file missing
        return {
            "maxHousingBudgetByJobLevel": {
                "L1": 5000,
                "L2": 7000,
                "L3": 10000
            },
            "minLeadTimeDays": 30,
            "requiredDocs": ["Passport scans", "Employment letter"],
            "spouseWorkIntentExtraDocs": ["Spouse resume"]
        }

    def run(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        rules = self.load_rules()
        checks: List[Dict[str, Any]] = []
        actions: List[str] = []

        job_level = profile.get("primaryApplicant", {}).get("employer", {}).get("jobLevel")
        budget_range = profile.get("movePlan", {}).get("housing", {}).get("budgetMonthlySGD")
        target_arrival = profile.get("movePlan", {}).get("targetArrivalDate")
        assignment_start = profile.get("primaryApplicant", {}).get("assignment", {}).get("startDate")

        # Job level budget cap
        if job_level:
            cap = rules.get("maxHousingBudgetByJobLevel", {}).get(job_level)
            if cap and budget_range:
                budget_max = self._parse_budget_max(budget_range)
                if budget_max and budget_max > cap:
                    checks.append(self._check(
                        "housing_budget_cap",
                        "Housing budget exceeds cap",
                        "NON_COMPLIANT",
                        "high",
                        f"Budget max {budget_max} exceeds cap {cap} for {job_level}.",
                        ["movePlan.housing.budgetMonthlySGD", "primaryApplicant.employer.jobLevel"]
                    ))
                    actions.append("Align housing budget with policy cap or request exception.")
                else:
                    checks.append(self._check(
                        "housing_budget_cap",
                        "Housing budget within cap",
                        "COMPLIANT",
                        "low",
                        "Budget within policy cap for job level.",
                        ["movePlan.housing.budgetMonthlySGD", "primaryApplicant.employer.jobLevel"]
                    ))
            else:
                checks.append(self._check(
                    "housing_budget_cap",
                    "Housing budget cap review",
                    "NEEDS_REVIEW",
                    "medium",
                    "Missing budget or job level for cap check.",
                    ["movePlan.housing.budgetMonthlySGD", "primaryApplicant.employer.jobLevel"]
                ))
                actions.append("Provide job level and housing budget.")
        else:
            checks.append(self._check(
                "job_level_missing",
                "Job level missing",
                "NEEDS_REVIEW",
                "medium",
                "Job level not provided; cap checks skipped.",
                ["primaryApplicant.employer.jobLevel"]
            ))
            actions.append("Add employee job level for policy checks.")

        # Lead time check
        lead_days = rules.get("minLeadTimeDays", 30)
        planned_date = assignment_start or target_arrival
        if planned_date:
            try:
                planned = datetime.fromisoformat(planned_date).date()
                days_until = (planned - date.today()).days
                if days_until < lead_days:
                    checks.append(self._check(
                        "lead_time",
                        "Minimum lead time",
                        "NON_COMPLIANT",
                        "high",
                        f"Lead time is {days_until} days; minimum is {lead_days}.",
                        ["primaryApplicant.assignment.startDate", "movePlan.targetArrivalDate"]
                    ))
                    actions.append("Adjust timeline to meet minimum lead time.")
                else:
                    checks.append(self._check(
                        "lead_time",
                        "Minimum lead time",
                        "COMPLIANT",
                        "low",
                        f"Lead time is {days_until} days; meets minimum {lead_days}.",
                        ["primaryApplicant.assignment.startDate", "movePlan.targetArrivalDate"]
                    ))
            except Exception:
                checks.append(self._check(
                    "lead_time",
                    "Minimum lead time",
                    "NEEDS_REVIEW",
                    "medium",
                    "Unable to parse planned start/arrival date.",
                    ["primaryApplicant.assignment.startDate", "movePlan.targetArrivalDate"]
                ))
                actions.append("Confirm assignment start or arrival date.")
        else:
            checks.append(self._check(
                "lead_time",
                "Minimum lead time",
                "NEEDS_REVIEW",
                "medium",
                "No planned start or arrival date provided.",
                ["primaryApplicant.assignment.startDate", "movePlan.targetArrivalDate"]
            ))
            actions.append("Provide assignment start or arrival date.")

        # Required documents
        docs = profile.get("complianceDocs", {})
        required_docs = rules.get("requiredDocs", [])
        doc_map = {
            "Passport scans": docs.get("hasPassportScans"),
            "Employment letter": docs.get("hasEmploymentLetter"),
            "Marriage certificate": docs.get("hasMarriageCertificate"),
            "Birth certificates": docs.get("hasBirthCertificates"),
        }
        for doc in required_docs:
            status = doc_map.get(doc)
            if status is True:
                checks.append(self._check(
                    f"doc_{doc}",
                    f"{doc} provided",
                    "COMPLIANT",
                    "low",
                    f"{doc} confirmed.",
                    ["complianceDocs"]
                ))
            elif status is False:
                checks.append(self._check(
                    f"doc_{doc}",
                    f"{doc} missing",
                    "NON_COMPLIANT",
                    "high",
                    f"{doc} is required but not provided.",
                    ["complianceDocs"]
                ))
                actions.append(f"Upload {doc}.")
            else:
                checks.append(self._check(
                    f"doc_{doc}",
                    f"{doc} status unknown",
                    "NEEDS_REVIEW",
                    "medium",
                    f"{doc} status not provided.",
                    ["complianceDocs"]
                ))
                actions.append(f"Confirm {doc} availability.")

        # Spouse work intent additional checklist
        spouse_wants_work = profile.get("spouse", {}).get("wantsToWork")
        if spouse_wants_work:
            extra_docs = rules.get("spouseWorkIntentExtraDocs", [])
            if extra_docs:
                checks.append(self._check(
                    "spouse_work_intent",
                    "Spouse work intent",
                    "NEEDS_REVIEW",
                    "medium",
                    "Spouse intends to work; additional checklist required.",
                    ["spouse.wantsToWork"]
                ))
                actions.extend([f"Collect {doc}." for doc in extra_docs])

        overall = self._overall_status(checks)
        return {
            "overallStatus": overall,
            "checks": checks,
            "actions": actions
        }

    def _parse_budget_max(self, budget_range: str) -> int:
        if not budget_range:
            return 0
        if "-" in budget_range:
            parts = budget_range.replace("+", "").split("-")
            return int(parts[1]) if len(parts) > 1 else int(parts[0])
        return int(budget_range.replace("+", ""))

    def _check(
        self,
        check_id: str,
        name: str,
        status: str,
        severity: str,
        rationale: str,
        affected_fields: List[str]
    ) -> Dict[str, Any]:
        return {
            "id": check_id,
            "name": name,
            "status": status,
            "severity": severity,
            "rationale": rationale,
            "affectedFields": affected_fields
        }

    def _overall_status(self, checks: List[Dict[str, Any]]) -> str:
        if any(c["status"] == "NON_COMPLIANT" for c in checks):
            return "NON_COMPLIANT"
        if any(c["status"] == "NEEDS_REVIEW" for c in checks):
            return "NEEDS_REVIEW"
        return "COMPLIANT"
