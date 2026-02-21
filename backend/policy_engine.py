from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
import json
import os


class PolicyEngine:
    def __init__(self, policy_path: Optional[str] = None):
        if policy_path:
            self.policy_path = policy_path
        else:
            self.policy_path = os.path.join(os.path.dirname(__file__), "policy_config.json")

    def load_policy(self) -> Dict[str, Any]:
        if os.path.exists(self.policy_path):
            with open(self.policy_path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        return {}

    def compute_spend(self, assignment_id: str, profile: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
        caps = policy.get("caps", {})
        destination = profile.get("movePlan", {}).get("destination", "")
        dependents = profile.get("dependents", []) or []
        family_size = 1 + (1 if profile.get("spouse", {}).get("fullName") else 0) + len(dependents)

        seed = sum(ord(ch) for ch in assignment_id) % 1000

        housing_cap = caps.get("housing", {}).get("amount", 5000)
        movers_cap = caps.get("movers", {}).get("amount", 10000)
        schools_cap = caps.get("schools", {}).get("amount", 20000)
        immigration_cap = caps.get("immigration", {}).get("amount", 4000)

        housing_used = int(housing_cap * 0.64 + (seed % 600))
        movers_used = int(movers_cap * (1.18 if "New York" in destination else 0.72) + (seed % 500))
        schools_used = int(schools_cap * (0.92 if family_size > 2 else 0.12) + (seed % 400))
        immigration_used = int(immigration_cap * 0.35 + (seed % 200))

        spend = {
            "housing": self._build_spend_item("Housing", housing_used, housing_cap, "USD"),
            "movers": self._build_spend_item("Movers & Logistics", movers_used, movers_cap, "USD"),
            "schools": self._build_spend_item("Schools", schools_used, schools_cap, "USD"),
            "immigration": self._build_spend_item("Immigration & Legal", immigration_used, immigration_cap, "USD"),
        }

        return spend

    def build_policy_response(
        self,
        assignment_id: str,
        profile: Dict[str, Any],
        policy: Dict[str, Any],
        exceptions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        spend = self.compute_spend(assignment_id, profile, policy)
        pending_exceptions = [exc for exc in exceptions if exc.get("status") == "PENDING"]
        over_limit = [item for item in spend.values() if item["status"] == "OVER_LIMIT"]

        gating = {
            "requiresAcknowledgement": bool(over_limit),
            "requiresHRApproval": bool(over_limit or pending_exceptions),
        }

        return {
            "policy": policy,
            "spend": spend,
            "exceptions": exceptions,
            "gating": gating,
        }

    def build_compliance_report(
        self,
        assignment_id: str,
        profile: Dict[str, Any],
        policy: Dict[str, Any],
        spend: Dict[str, Any],
        exceptions: List[Dict[str, Any]],
        assignment_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        checks: List[Dict[str, Any]] = []
        conflicts: List[Dict[str, Any]] = []

        docs = profile.get("complianceDocs", {}) or {}
        spouse = profile.get("spouse", {}) or {}
        dependents = profile.get("dependents", []) or []

        target_date = self._parse_date(profile.get("movePlan", {}).get("targetArrivalDate"))
        start_date = self._parse_date(profile.get("primaryApplicant", {}).get("assignment", {}).get("startDate"))

        doc_requirements = policy.get("documentRequirements", {})
        required_docs = list(doc_requirements.get("base", []))
        if spouse.get("fullName"):
            required_docs += doc_requirements.get("married", [])
        if dependents:
            required_docs += doc_requirements.get("children", [])
        if spouse.get("wantsToWork"):
            required_docs += doc_requirements.get("spouseWork", [])

        doc_map = {
            "Passport scans": docs.get("hasPassportScans"),
            "Employment letter": docs.get("hasEmploymentLetter"),
            "Marriage certificate": docs.get("hasMarriageCertificate"),
            "Birth certificates": docs.get("hasBirthCertificates"),
            "Bank statements": docs.get("hasBankStatements"),
            "Spouse resume": docs.get("hasEmploymentLetter"),
        }

        # Identity & Documents
        checks.append(self._doc_check("passport_scans", "Passport scans", doc_map.get("Passport scans"), "Employee"))
        checks.append(self._doc_check("employment_letter", "Employment letter", doc_map.get("Employment letter"), "Employee"))
        if spouse.get("fullName"):
            checks.append(self._doc_check("marriage_certificate", "Marriage certificate", doc_map.get("Marriage certificate"), "Employee"))
        if dependents:
            checks.append(self._doc_check("birth_certificates", "Birth certificates", doc_map.get("Birth certificates"), "Employee"))

        # Passport validity
        passport_expiry = self._parse_date(profile.get("primaryApplicant", {}).get("passport", {}).get("expiryDate"))
        checks.append(self._passport_validity_check(passport_expiry, target_date))

        # Timeline & Lead Time
        min_days = policy.get("leadTimeRules", {}).get("minDays", 30)
        planned = start_date or target_date
        checks.append(self._lead_time_check(planned, min_days))

        if start_date and target_date and start_date != target_date:
            conflicts.append({
                "id": "date_mismatch",
                "title": "Start date mismatch",
                "details": {
                    "offerLetter": start_date.isoformat(),
                    "questionnaire": target_date.isoformat()
                }
            })

        # Employment & Assignment compliance
        role_title = profile.get("primaryApplicant", {}).get("employer", {}).get("roleTitle")
        checks.append(self._presence_check("role_title", "Role/title provided", role_title, "HR"))

        # Policy & Package compliance
        for key, item in spend.items():
            checks.append(self._policy_spend_check(key, item, exceptions))

        # Data integrity
        for idx, child in enumerate(dependents):
            dob = self._parse_date(child.get("dateOfBirth"))
            if dob and dob > date.today():
                checks.append(self._check(
                    f"dependent_dob_{idx}",
                    "Dependent birth date in future",
                    "FAIL",
                    "CRITICAL",
                    "LOW",
                    "HR",
                    "DOB must be in the past.",
                    ["Dependent documentation"],
                    ["Mark Reviewed"]
                ))

        # Derived lists
        risk = self._compute_risk(checks, policy)
        critical_count = len([c for c in checks if c["severity"] == "CRITICAL"])

        return {
            "summary": {
                "riskScore": risk["score"],
                "label": risk["label"],
                "criticalCount": critical_count,
                "lastVerified": datetime.utcnow().isoformat(),
            },
            "meta": {
                "visaPath": self._visa_path(profile),
                "destination": profile.get("movePlan", {}).get("destination", "—"),
                "stage": self._stage_label(assignment_status),
            },
            "checks": checks,
            "consistencyConflicts": conflicts,
            "recentChecks": checks[:5],
        }

    def _build_spend_item(self, title: str, used: int, cap: int, currency: str) -> Dict[str, Any]:
        remaining = max(cap - used, 0)
        if used > cap:
            status = "OVER_LIMIT"
        elif used > int(cap * 0.85):
            status = "NEAR_LIMIT"
        else:
            status = "ON_TRACK"
        return {
            "title": title,
            "used": used,
            "cap": cap,
            "remaining": remaining,
            "currency": currency,
            "status": status,
        }

    def _doc_check(self, check_id: str, label: str, value: Any, owner: str) -> Dict[str, Any]:
        if value is True:
            return self._check(check_id, f"{label} provided", "PASS", "LOW", "HIGH", owner,
                               f"{label} has been uploaded.", [label], [])
        if value is False:
            return self._check(check_id, f"{label} missing", "FAIL", "HIGH", "MED", owner,
                               f"{label} is required but missing.", [label], ["Upload Document", "Ask Employee"])
        return self._check(check_id, f"{label} status unknown", "WARN", "MED", "LOW", owner,
                           f"{label} status not provided.", [label], ["Ask Employee"])

    def _passport_validity_check(self, expiry: Optional[date], target: Optional[date]) -> Dict[str, Any]:
        if not expiry or not target:
            return self._check(
                "passport_validity",
                "Valid Passport (6+ months)",
                "WARN",
                "MED",
                "LOW",
                "Employee",
                "Passport validity must extend 6 months beyond entry.",
                ["Passport scan"],
                ["Ask Employee"]
            )
        if expiry < target + timedelta(days=180):
            return self._check(
                "passport_validity",
                "Valid Passport (6+ months)",
                "FAIL",
                "CRITICAL",
                "HIGH",
                "Employee",
                "Passport expires too soon after intended entry.",
                ["Passport scan"],
                ["Upload Document", "Ask Employee"]
            )
        return self._check(
            "passport_validity",
            "Valid Passport (6+ months)",
            "PASS",
            "LOW",
            "HIGH",
            "Employee",
            "Passport validity meets policy requirement.",
            ["Passport scan"],
            []
        )

    def _lead_time_check(self, planned: Optional[date], min_days: int) -> Dict[str, Any]:
        if not planned:
            return self._check(
                "lead_time",
                "Minimum lead time",
                "WARN",
                "MED",
                "LOW",
                "HR",
                "Planned start/arrival date missing.",
                ["Assignment dates"],
                ["Ask Employee"]
            )
        days_until = (planned - date.today()).days
        if days_until < min_days:
            return self._check(
                "lead_time",
                "Minimum lead time",
                "FAIL",
                "HIGH",
                "MED",
                "HR",
                f"Lead time is {days_until} days; minimum is {min_days}.",
                ["Assignment dates"],
                ["Request Exception", "Ask Employee"]
            )
        return self._check(
            "lead_time",
            "Minimum lead time",
            "PASS",
            "LOW",
            "MED",
            "HR",
            f"Lead time is {days_until} days; meets minimum {min_days}.",
            ["Assignment dates"],
            []
        )

    def _presence_check(self, check_id: str, label: str, value: Any, owner: str) -> Dict[str, Any]:
        if value:
            return self._check(check_id, label, "PASS", "LOW", "HIGH", owner, "Provided.", [], [])
        return self._check(check_id, label, "WARN", "MED", "LOW", owner, "Missing detail.", [], ["Ask Employee"])

    def _policy_spend_check(self, category: str, item: Dict[str, Any], exceptions: List[Dict[str, Any]]) -> Dict[str, Any]:
        status = item["status"]
        pending = any(exc for exc in exceptions if exc.get("category") == category and exc.get("status") == "PENDING")
        if status == "OVER_LIMIT":
            return self._check(
                f"{category}_cap",
                f"{item['title']} over policy cap",
                "FAIL",
                "CRITICAL",
                "HIGH",
                "HR",
                "Category spend exceeds policy cap.",
                [f"{item['title']} cap"],
                ["Request Exception" if not pending else "Mark Reviewed"]
            )
        if status == "NEAR_LIMIT":
            return self._check(
                f"{category}_cap",
                f"{item['title']} near policy cap",
                "WARN",
                "MED",
                "MED",
                "HR",
                "Category spend approaching policy cap.",
                [f"{item['title']} cap"],
                ["Request Exception"]
            )
        return self._check(
            f"{category}_cap",
            f"{item['title']} within policy cap",
            "PASS",
            "LOW",
            "HIGH",
            "HR",
            "Category spend within cap.",
            [f"{item['title']} cap"],
            []
        )

    def _compute_risk(self, checks: List[Dict[str, Any]], policy: Dict[str, Any]) -> Dict[str, Any]:
        score = 100
        for check in checks:
            if check["status"] == "FAIL":
                score -= 18 if check["severity"] == "CRITICAL" else 12
            elif check["status"] == "WARN":
                score -= 6
        score = max(0, min(100, score))
        thresholds = policy.get("riskThresholds", {"low": 80, "moderate": 60})
        label = "Low" if score >= thresholds["low"] else "Moderate" if score >= thresholds["moderate"] else "High"
        return {"score": score, "label": label}

    def _check(
        self,
        check_id: str,
        title: str,
        status: str,
        severity: str,
        confidence: str,
        owner: str,
        why: str,
        evidence: List[str],
        actions: List[str],
    ) -> Dict[str, Any]:
        return {
            "checkId": check_id,
            "title": title,
            "pillar": self._pillar_for_check(check_id),
            "status": status,
            "severity": severity,
            "confidence": confidence,
            "owner": owner,
            "whyItMatters": why,
            "evidenceNeeded": evidence,
            "fixActions": actions,
            "blocking": status == "FAIL" and severity in ["HIGH", "CRITICAL"],
        }

    def _pillar_for_check(self, check_id: str) -> str:
        if "passport" in check_id or "doc" in check_id:
            return "Identity & Documents"
        if "lead_time" in check_id or "date" in check_id:
            return "Timeline & Lead Time"
        if "role" in check_id:
            return "Employment & Assignment"
        if "cap" in check_id:
            return "Policy / Package Compliance"
        return "Consistency & Data Integrity"

    def _visa_path(self, profile: Dict[str, Any]) -> str:
        job_level = profile.get("primaryApplicant", {}).get("employer", {}).get("jobLevel")
        return f"L-{job_level} Specialized Knowledge" if job_level else "L-1B Specialized Knowledge"

    def _stage_label(self, status: Any) -> str:
        if status == "EMPLOYEE_SUBMITTED":
            return "Intake/Pre-Submission"
        if status == "CHANGES_REQUESTED":
            return "Changes Requested"
        if status == "HR_APPROVED":
            return "Approved"
        return "Intake/In Progress"

    def _parse_date(self, value: Any) -> Optional[date]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value).date()
        except Exception:
            return None
