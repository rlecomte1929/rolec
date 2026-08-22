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
        """No spend categories: this platform does not track actual spend yet.

        [AIQ-2087] This method used to SYNTHESISE per-category utilisation:

            seed = sum(ord(ch) for ch in assignment_id) % 1000
            housing_used = int(housing_cap * 0.64 + (seed % 600))
            ...

        A hash of the case id, scaled against caps read from the checked-in
        ``backend/policy_config.json``. It was not an estimate and not a default —
        it was a number with no referent, and it reached HR three ways:

          * ``GET /api/hr/policy?caseId=`` -> the ``spend`` block;
          * ``build_compliance_report`` turned each item into a COMPLIANCE CHECK
            ("Housing over policy cap", FAIL/CRITICAL, action "Request Exception"),
            which also feeds ``summary.riskScore``;
          * ``over_limit`` drove ``gating.requiresAcknowledgement`` and
            ``gating.requiresHRApproval`` — so a hash decided whether a case needed
            HR sign-off.

        Note the caps were fiction too: ``load_policy()`` reads one static file with
        no company parameter, so every tenant saw the same $5k/$10k/$20k/$4k while
        their real policy sat in ``policy_config_benefits`` (21,662 rows, served by
        ``/api/hr/policy-config/*``).

        Returning ``{}`` is the honest answer — there is no actuals source anywhere
        in the platform (``case_budget_lines`` holds 0 rows). Downstream this means
        no cap checks are emitted and the gates fall back to real pending exceptions
        from ``policy_cap_requests``. Real per-case spend tracking is its own piece
        of work; do not repopulate this from anything but a real ledger.

        Same class as AIQ-1527 (``test_budget_summary_honest.py``): the system
        asserting something it never measured.
        """
        return {}

    def build_policy_response(
        self,
        assignment_id: str,
        profile: Dict[str, Any],
        policy: Dict[str, Any],
        exceptions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        spend = self.compute_spend(assignment_id, profile, policy)
        # AIQ-1587: exceptions now come from policy_cap_requests, whose status is
        # lowercase ('pending'); compare case-insensitively so pending requests still gate.
        pending_exceptions = [exc for exc in exceptions if str(exc.get("status") or "").upper() == "PENDING"]
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
        pending = any(exc for exc in exceptions if exc.get("category") == category and str(exc.get("status") or "").upper() == "PENDING")
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
        # We do not have the immigration knowledge to recommend a specific
        # visa category per corridor — the previous implementation hardcoded
        # US L-visa terminology regardless of route. Until a properly
        # sourced per-corridor immigration model is in place, surface a
        # corridor-aware referral instead of a confidently wrong category.
        move = profile.get("movePlan") or {}
        origin = (move.get("origin") or "").strip() if isinstance(move.get("origin"), str) else ""
        destination = (move.get("destination") or "").strip() if isinstance(move.get("destination"), str) else ""
        if origin and destination:
            return f"Requires immigration counsel review for {origin} → {destination}."
        if destination:
            return f"Requires immigration counsel review for relocation to {destination}."
        return "Requires immigration counsel review."

    def _stage_label(self, status: Any) -> str:
        """
        Map canonical / legacy assignment statuses to human-readable stage labels.
        """
        if not status:
            return "Intake / Created"
        s = str(status).strip().lower()
        if s in {"submitted"}:
            return "Intake / Submitted"
        if s in {"approved"}:
            return "Approved"
        if s in {"rejected"}:
            return "Rejected"
        if s in {"awaiting_intake", "assigned"}:
            return "Awaiting Intake"
        # Legacy fallbacks
        if s in {"employee_submitted"}:
            return "Intake / Submitted"
        if s in {"changes_requested"}:
            return "Awaiting Intake"
        if s in {"hr_approved"}:
            return "Approved"
        return "Intake / In Progress"

    def _parse_date(self, value: Any) -> Optional[date]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value).date()
        except Exception:
            return None
