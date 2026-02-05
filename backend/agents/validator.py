"""
Agent B — Profile Normalizer & Validator
Normalizes formats and validates constraints.
"""
from typing import Dict, Any, List, Tuple
from datetime import datetime, date
from schemas import RelocationProfile, ValidationError
import re


class ProfileValidator:
    """Validates and normalizes profile data."""
    
    def validate_and_normalize(self, profile_dict: Dict[str, Any]) -> Tuple[Dict[str, Any], List[ValidationError]]:
        """
        Validates profile and returns normalized profile + list of validation errors.
        """
        errors = []
        normalized = profile_dict.copy()
        
        # Normalize dates
        normalized = self._normalize_dates(normalized)
        
        # Validate passport expiry
        errors.extend(self._validate_passport_expiry(normalized))
        
        # Validate children ages
        errors.extend(self._validate_children_ages(normalized))
        
        # Validate timeline logic
        errors.extend(self._validate_timeline(normalized))
        
        # Normalize phone numbers (if any in future)
        # Normalize addresses (if any structured input)
        
        return normalized, errors
    
    def _normalize_dates(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Convert all date strings to ISO format YYYY-MM-DD."""
        # This is a simplified version - in practice would recursively process nested dicts
        return profile
    
    def _validate_passport_expiry(self, profile: Dict[str, Any]) -> List[ValidationError]:
        """Validate passport expiry is after arrival date + 6 months."""
        errors = []
        
        try:
            arrival_date_str = profile.get("movePlan", {}).get("targetArrivalDate")
            passport_expiry_str = profile.get("primaryApplicant", {}).get("passport", {}).get("expiryDate")
            
            if arrival_date_str and passport_expiry_str:
                arrival_date = datetime.fromisoformat(arrival_date_str).date() if isinstance(arrival_date_str, str) else arrival_date_str
                passport_expiry = datetime.fromisoformat(passport_expiry_str).date() if isinstance(passport_expiry_str, str) else passport_expiry_str
                
                # Check if passport expires within 6 months of arrival
                if passport_expiry and arrival_date:
                    days_diff = (passport_expiry - arrival_date).days
                    if days_diff < 180:  # 6 months
                        errors.append(ValidationError(
                            field="primaryApplicant.passport.expiryDate",
                            message=f"Passport should be valid for at least 6 months after arrival. Current validity: {days_diff} days."
                        ))
        except Exception as e:
            # If parsing fails, skip validation
            pass
        
        return errors
    
    def _validate_children_ages(self, profile: Dict[str, Any]) -> List[ValidationError]:
        """Validate children are under 10 years old."""
        errors = []
        
        dependents = profile.get("dependents", [])
        for idx, child in enumerate(dependents):
            dob_str = child.get("dateOfBirth")
            if dob_str:
                try:
                    dob = datetime.fromisoformat(dob_str).date() if isinstance(dob_str, str) else dob_str
                    age = (date.today() - dob).days / 365.25
                    
                    if age > 10:
                        errors.append(ValidationError(
                            field=f"dependents.{idx}.dateOfBirth",
                            message=f"Child {idx+1} appears to be over 10 years old. This profile is designed for children under 10."
                        ))
                except Exception:
                    pass
        
        return errors
    
    def _validate_timeline(self, profile: Dict[str, Any]) -> List[ValidationError]:
        """Validate timeline makes sense (arrival before school start, etc)."""
        errors = []
        
        try:
            arrival_date_str = profile.get("movePlan", {}).get("targetArrivalDate")
            school_start_str = profile.get("movePlan", {}).get("schooling", {}).get("schoolingStartDate")
            
            if arrival_date_str and school_start_str:
                arrival_date = datetime.fromisoformat(arrival_date_str).date() if isinstance(arrival_date_str, str) else arrival_date_str
                school_start = datetime.fromisoformat(school_start_str).date() if isinstance(school_start_str, str) else school_start_str
                
                if school_start < arrival_date:
                    errors.append(ValidationError(
                        field="movePlan.schooling.schoolingStartDate",
                        message="School start date should be after or same as arrival date."
                    ))
        except Exception:
            pass
        
        return errors
    
    def is_profile_complete_for_recommendations(self, profile: Dict[str, Any]) -> Dict[str, bool]:
        """
        Check if profile has minimum data for each recommendation type.
        """
        result = {
            "housing": self._has_housing_minimum(profile),
            "schools": self._has_schools_minimum(profile),
            "movers": self._has_movers_minimum(profile),
            "readiness": self._has_readiness_minimum(profile),
        }
        return result
    
    def _has_housing_minimum(self, profile: Dict[str, Any]) -> bool:
        """Check if has minimum data for housing recommendations."""
        housing = profile.get("movePlan", {}).get("housing", {})
        return (
            housing.get("desiredMoveInDate") is not None and
            housing.get("bedroomsMin") is not None
        )
    
    def _has_schools_minimum(self, profile: Dict[str, Any]) -> bool:
        """Check if has minimum data for school recommendations."""
        schooling = profile.get("movePlan", {}).get("schooling", {})
        dependents = profile.get("dependents", [])
        
        has_children_dobs = any(child.get("dateOfBirth") for child in dependents)
        has_school_start = schooling.get("schoolingStartDate") is not None
        
        return has_children_dobs and has_school_start
    
    def _has_movers_minimum(self, profile: Dict[str, Any]) -> bool:
        """Check if has minimum data for movers recommendations."""
        movers = profile.get("movePlan", {}).get("movers", {})
        arrival = profile.get("movePlan", {}).get("targetArrivalDate")
        
        return (
            movers.get("inventoryRough") is not None and
            arrival is not None
        )
    
    def _has_readiness_minimum(self, profile: Dict[str, Any]) -> bool:
        """Check if has minimum data for readiness rating."""
        passport = profile.get("primaryApplicant", {}).get("passport", {})
        assignment = profile.get("primaryApplicant", {}).get("assignment", {})
        
        return (
            passport.get("expiryDate") is not None and
            assignment.get("startDate") is not None
        )
