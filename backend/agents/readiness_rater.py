"""
Agent C — Immigration Readiness Rater (Informational)
Computes readiness rating based on profile completeness and obvious blockers.
INFORMATIONAL ONLY - not legal advice.
"""
from typing import Dict, Any, List
from datetime import datetime, date
from ..schemas import ImmigrationReadiness, ReadinessStatus


class ReadinessRater:
    """Rates immigration readiness based on profile data."""
    
    DISCLAIMER = "This is informational guidance only, not legal advice. Consult an immigration professional for eligibility assessment."
    
    def compute_readiness(self, profile: Dict[str, Any]) -> ImmigrationReadiness:
        """
        Compute readiness rating 0-100 and status.
        """
        score = 0
        max_score = 100
        reasons = []
        missing_docs = []
        
        # Check essential documents (40 points)
        doc_score, doc_reasons, doc_missing = self._check_documents(profile)
        score += doc_score
        reasons.extend(doc_reasons)
        missing_docs.extend(doc_missing)
        
        # Check passport validity (20 points)
        passport_score, passport_reasons = self._check_passport_validity(profile)
        score += passport_score
        reasons.extend(passport_reasons)
        
        # Check employment details (20 points)
        employment_score, employment_reasons = self._check_employment(profile)
        score += employment_score
        reasons.extend(employment_reasons)
        
        # Check timeline feasibility (10 points)
        timeline_score, timeline_reasons = self._check_timeline(profile)
        score += timeline_score
        reasons.extend(timeline_reasons)
        
        # Check family documentation (10 points)
        family_score, family_reasons = self._check_family_docs(profile)
        score += family_score
        reasons.extend(family_reasons)
        
        # Determine status
        if score >= 80:
            status = ReadinessStatus.GREEN
        elif score >= 50:
            status = ReadinessStatus.AMBER
        else:
            status = ReadinessStatus.RED
        
        return ImmigrationReadiness(
            score=score,
            status=status,
            reasons=reasons,
            missingDocs=missing_docs
        )
    
    def _check_documents(self, profile: Dict[str, Any]) -> tuple:
        """Check if essential documents are available."""
        score = 0
        reasons = []
        missing = []
        
        docs = profile.get("complianceDocs", {})
        
        if docs.get("hasPassportScans"):
            score += 10
            reasons.append("✓ Passport scans available")
        else:
            missing.append("Passport scans for all family members")
            reasons.append("✗ Passport scans needed")
        
        if docs.get("hasEmploymentLetter"):
            score += 10
            reasons.append("✓ Employment letter available")
        else:
            missing.append("Employment letter from Norwegian Investment")
            reasons.append("✗ Employment letter needed")
        
        if docs.get("hasMarriageCertificate"):
            score += 10
            reasons.append("✓ Marriage certificate available")
        else:
            missing.append("Marriage certificate")
            reasons.append("✗ Marriage certificate needed for dependent pass")
        
        if docs.get("hasBirthCertificates"):
            score += 10
            reasons.append("✓ Birth certificates available")
        else:
            missing.append("Birth certificates for both children")
            reasons.append("✗ Birth certificates needed for children's dependent passes")
        
        return score, reasons, missing
    
    def _check_passport_validity(self, profile: Dict[str, Any]) -> tuple:
        """Check passport validity."""
        score = 0
        reasons = []
        
        passport = profile.get("primaryApplicant", {}).get("passport", {})
        expiry_str = passport.get("expiryDate")
        arrival_str = profile.get("movePlan", {}).get("targetArrivalDate")
        
        if not expiry_str:
            reasons.append("⚠ Passport expiry date needed")
            return score, reasons
        
        try:
            expiry = datetime.fromisoformat(expiry_str).date() if isinstance(expiry_str, str) else expiry_str
            today = date.today()
            
            if arrival_str:
                arrival = datetime.fromisoformat(arrival_str).date() if isinstance(arrival_str, str) else arrival_str
                days_after_arrival = (expiry - arrival).days
                
                if days_after_arrival >= 180:  # 6+ months
                    score = 20
                    reasons.append(f"✓ Passport valid for {days_after_arrival} days after arrival")
                elif days_after_arrival >= 0:
                    score = 10
                    reasons.append(f"⚠ Passport expires {days_after_arrival} days after arrival (less than 6 months)")
                else:
                    reasons.append("✗ Passport will expire before arrival - renewal required")
            else:
                # Just check if valid
                days_remaining = (expiry - today).days
                if days_remaining > 180:
                    score = 15
                    reasons.append(f"✓ Passport valid for {days_remaining} days")
                else:
                    score = 5
                    reasons.append(f"⚠ Passport expires in {days_remaining} days")
        except Exception:
            reasons.append("⚠ Unable to verify passport validity")
        
        return score, reasons
    
    def _check_employment(self, profile: Dict[str, Any]) -> tuple:
        """Check employment details."""
        score = 0
        reasons = []
        
        employer = profile.get("primaryApplicant", {}).get("employer", {})
        assignment = profile.get("primaryApplicant", {}).get("assignment", {})
        
        if employer.get("roleTitle"):
            score += 5
            reasons.append("✓ Role title provided")
        else:
            reasons.append("⚠ Role title needed")
        
        if employer.get("salaryBand"):
            score += 5
            reasons.append("✓ Salary band provided")
        else:
            reasons.append("⚠ Salary band needed for work permit assessment")
        
        if assignment.get("startDate"):
            score += 5
            reasons.append("✓ Assignment start date confirmed")
        else:
            reasons.append("⚠ Assignment start date needed")
        
        if assignment.get("relocationPackage") is not None:
            score += 5
            if assignment.get("relocationPackage"):
                reasons.append("✓ Relocation package confirmed")
            else:
                reasons.append("⚠ No relocation package - plan for self-funded move")
        
        return score, reasons
    
    def _check_timeline(self, profile: Dict[str, Any]) -> tuple:
        """Check if timeline is feasible."""
        score = 0
        reasons = []
        
        arrival_str = profile.get("movePlan", {}).get("targetArrivalDate")
        assignment_start_str = profile.get("primaryApplicant", {}).get("assignment", {}).get("startDate")
        
        if not arrival_str or not assignment_start_str:
            reasons.append("⚠ Timeline not yet established")
            return score, reasons
        
        try:
            arrival = datetime.fromisoformat(arrival_str).date() if isinstance(arrival_str, str) else arrival_str
            assignment_start = datetime.fromisoformat(assignment_start_str).date() if isinstance(assignment_start_str, str) else assignment_start_str
            today = date.today()
            
            days_until_arrival = (arrival - today).days
            
            if days_until_arrival >= 90:
                score = 10
                reasons.append(f"✓ {days_until_arrival} days until arrival - good lead time")
            elif days_until_arrival >= 60:
                score = 7
                reasons.append(f"⚠ {days_until_arrival} days until arrival - tight timeline")
            elif days_until_arrival >= 30:
                score = 4
                reasons.append(f"⚠ {days_until_arrival} days until arrival - very tight timeline")
            else:
                score = 2
                reasons.append(f"✗ Only {days_until_arrival} days until arrival - urgent action needed")
        except Exception:
            reasons.append("⚠ Unable to verify timeline")
        
        return score, reasons
    
    def _check_family_docs(self, profile: Dict[str, Any]) -> tuple:
        """Check family member details."""
        score = 0
        reasons = []
        
        spouse = profile.get("spouse", {})
        dependents = profile.get("dependents", [])
        
        if spouse.get("fullName") and spouse.get("nationality"):
            score += 5
            reasons.append("✓ Spouse details provided")
        else:
            reasons.append("⚠ Spouse details needed for dependent pass")
        
        children_complete = all(
            child.get("firstName") and child.get("dateOfBirth")
            for child in dependents
        )
        
        if children_complete and len(dependents) == 2:
            score += 5
            reasons.append("✓ Children details complete")
        else:
            reasons.append("⚠ Complete children details needed")
        
        return score, reasons
