"""
Agent D — Recommendation Engine
Filters and ranks housing, schools, and movers based on profile data.
Uses seed datasets + filtering logic.
"""
from typing import Dict, Any, List
from datetime import datetime, date
from schemas import HousingRecommendation, SchoolRecommendation, MoverRecommendation
from seed_data import get_housing_seed, get_schools_seed, get_movers_seed


class RecommendationEngine:
    """Generates recommendations based on profile preferences."""
    
    def get_housing_recommendations(self, profile: Dict[str, Any]) -> List[HousingRecommendation]:
        """Return filtered and ranked housing options."""
        housing_prefs = profile.get("movePlan", {}).get("housing", {})

        budget_range = housing_prefs.get("budgetMonthlySGD")

        # bedroomsMin may come through as a string from the questionnaire,
        # but our seed data stores bedrooms as integers. Normalise to int
        # with a sensible default to avoid type errors when comparing.
        bedrooms_raw = housing_prefs.get("bedroomsMin", 3)
        try:
            bedrooms = int(bedrooms_raw) if bedrooms_raw is not None else 3
        except (TypeError, ValueError):
            bedrooms = 3

        preferred_areas = housing_prefs.get("preferredAreas", [])
        must_haves = housing_prefs.get("mustHave", [])
        
        # Get all housing seed data
        all_housing = get_housing_seed()
        
        # Filter
        filtered = []
        for house in all_housing:
            # Filter by bedrooms
            house_bedrooms_raw = house.get("bedrooms")
            try:
                house_bedrooms = int(house_bedrooms_raw) if house_bedrooms_raw is not None else bedrooms
            except (TypeError, ValueError):
                # If we can't interpret the seed value, don't exclude it purely on bedrooms
                house_bedrooms = bedrooms

            if house_bedrooms < bedrooms:
                continue
            
            # Filter by budget if specified
            if budget_range and budget_range != "unknown":
                if not self._matches_budget_range(house, budget_range):
                    continue
            
            # Prefer areas if specified
            area_match = not preferred_areas or house["area"] in preferred_areas
            
            # Check must-haves
            must_have_score = 0
            if "Furnished" in must_haves and house["furnished"]:
                must_have_score += 1
            if "Near MRT" in must_haves and house["nearMRT"]:
                must_have_score += 1
            
            filtered.append({
                "house": house,
                "area_match": area_match,
                "must_have_score": must_have_score
            })
        
        # Sort by area match, then must-haves, then family score
        filtered.sort(key=lambda x: (
            -x["area_match"],
            -x["must_have_score"],
            -x["house"]["familyFriendlyScore"]
        ))
        
        # Take top 8
        top_housing = filtered[:8]
        
        # Convert to response models with rationale
        results = []
        for item in top_housing:
            house = item["house"]
            rationale = self._build_housing_rationale(house, housing_prefs, item)
            
            results.append(HousingRecommendation(
                id=house["id"],
                name=house["name"],
                area=house["area"],
                bedrooms=house["bedrooms"],
                furnished=house["furnished"],
                nearMRT=house["nearMRT"],
                estMonthlySGDMin=house["estMonthlySGDMin"],
                estMonthlySGDMax=house["estMonthlySGDMax"],
                familyFriendlyScore=house["familyFriendlyScore"],
                notes=house["notes"],
                rationale=rationale,
                nextAction="View details"
            ))
        
        # If no results, show default mid-range options
        if not results:
            for house in all_housing[:5]:
                results.append(HousingRecommendation(
                    id=house["id"],
                    name=house["name"],
                    area=house["area"],
                    bedrooms=house["bedrooms"],
                    furnished=house["furnished"],
                    nearMRT=house["nearMRT"],
                    estMonthlySGDMin=house["estMonthlySGDMin"],
                    estMonthlySGDMax=house["estMonthlySGDMax"],
                    familyFriendlyScore=house["familyFriendlyScore"],
                    notes=house["notes"],
                    rationale="Budget or area preferences not provided; showing popular family options.",
                    nextAction="View details"
                ))
        
        return results
    
    def get_school_recommendations(self, profile: Dict[str, Any]) -> List[SchoolRecommendation]:
        """Return filtered and ranked school options."""
        schooling_prefs = profile.get("movePlan", {}).get("schooling", {})
        dependents = profile.get("dependents", [])
        
        curriculum = schooling_prefs.get("curriculumPreference")
        budget_range = schooling_prefs.get("budgetAnnualSGD")
        priorities = schooling_prefs.get("priorities", [])
        
        # Calculate children ages
        children_ages = []
        for child in dependents:
            dob_str = child.get("dateOfBirth")
            if dob_str:
                try:
                    dob = datetime.fromisoformat(dob_str).date() if isinstance(dob_str, str) else dob_str
                    age = (date.today() - dob).days / 365.25
                    children_ages.append(age)
                except Exception:
                    pass
        
        # Get all schools seed data
        all_schools = get_schools_seed()
        
        # Filter
        filtered = []
        for school in all_schools:
            # Filter by curriculum if specified
            curriculum_match = True
            if curriculum and curriculum != "No preference" and curriculum != "unknown":
                curriculum_match = curriculum in school["curriculumTags"]
                if not curriculum_match:
                    continue
            
            # Filter by budget if specified
            if budget_range and budget_range != "unknown":
                if not self._matches_school_budget(school, budget_range):
                    continue
            
            # Score by priorities
            priority_score = 0
            if "Language support" in priorities and school["languageSupport"]:
                priority_score += 1
            if "Academic excellence" in priorities:
                priority_score += 1  # All listed schools are good
            
            filtered.append({
                "school": school,
                "curriculum_match": curriculum_match,
                "priority_score": priority_score
            })
        
        # Sort
        filtered.sort(key=lambda x: (
            -x["curriculum_match"],
            -x["priority_score"]
        ))
        
        # Take top 8
        top_schools = filtered[:8]
        
        # Convert to response models
        results = []
        for item in top_schools:
            school = item["school"]
            rationale = self._build_school_rationale(school, schooling_prefs, item)
            
            results.append(SchoolRecommendation(
                id=school["id"],
                name=school["name"],
                area=school["area"],
                curriculumTags=school["curriculumTags"],
                ageRange=school["ageRange"],
                estAnnualSGDMin=school["estAnnualSGDMin"],
                estAnnualSGDMax=school["estAnnualSGDMax"],
                languageSupport=school["languageSupport"],
                notes=school["notes"],
                rationale=rationale,
                nextAction="Request application info"
            ))
        
        # If no results, show default options
        if not results:
            for school in all_schools[:5]:
                results.append(SchoolRecommendation(
                    id=school["id"],
                    name=school["name"],
                    area=school["area"],
                    curriculumTags=school["curriculumTags"],
                    ageRange=school["ageRange"],
                    estAnnualSGDMin=school["estAnnualSGDMin"],
                    estAnnualSGDMax=school["estAnnualSGDMax"],
                    languageSupport=school["languageSupport"],
                    notes=school["notes"],
                    rationale="Curriculum or budget preferences not provided; showing popular international schools.",
                    nextAction="Request application info"
                ))
        
        return results
    
    def get_mover_recommendations(self, profile: Dict[str, Any]) -> List[MoverRecommendation]:
        """Return mover options with RFQ templates."""
        movers_prefs = profile.get("movePlan", {}).get("movers", {})
        arrival_date = profile.get("movePlan", {}).get("targetArrivalDate", "TBD")
        
        inventory_size = movers_prefs.get("inventoryRough", "medium")
        special_items = movers_prefs.get("specialItems", [])
        storage_needed = movers_prefs.get("storageNeeded", False)
        insurance_needed = movers_prefs.get("insuranceNeeded", True)
        
        # Get all movers
        all_movers = get_movers_seed()
        
        # Filter based on needs
        filtered = []
        for mover in all_movers:
            score = 0
            
            # Prefer movers with needed services
            if storage_needed and "Storage" in mover["serviceTags"]:
                score += 2
            if insurance_needed and "Insurance" in mover["serviceTags"]:
                score += 1
            if len(special_items) > 0 and "Full service" in mover["serviceTags"]:
                score += 1
            
            filtered.append({
                "mover": mover,
                "score": score
            })
        
        # Sort by score
        filtered.sort(key=lambda x: -x["score"])
        
        # Build recommendations
        results = []
        for item in filtered:
            mover = item["mover"]
            
            # Build RFQ from template
            rfq = mover["rfqTemplate"].format(
                inventory_size=inventory_size,
                special_items_count=len(special_items),
                arrival_date=arrival_date
            )
            
            rationale = self._build_mover_rationale(mover, movers_prefs)
            
            results.append(MoverRecommendation(
                id=mover["id"],
                name=mover["name"],
                serviceTags=mover["serviceTags"],
                notes=mover["notes"],
                rfqTemplate=rfq,
                rationale=rationale,
                nextAction="Request quote"
            ))
        
        return results
    
    def _matches_budget_range(self, house: Dict[str, Any], budget_range: str) -> bool:
        """Check if housing fits budget range."""
        if budget_range == "unknown":
            return True
        
        try:
            # Parse budget range like "5000-7000"
            if "-" in budget_range:
                parts = budget_range.replace("+", "").split("-")
                budget_min = int(parts[0])
                budget_max = int(parts[1]) if len(parts) > 1 else 999999
            else:
                budget_min = 0
                budget_max = int(budget_range.replace("+", ""))
            
            # Check overlap
            house_min = house["estMonthlySGDMin"]
            house_max = house["estMonthlySGDMax"]
            
            return not (house_min > budget_max or house_max < budget_min)
        except Exception:
            return True
    
    def _matches_school_budget(self, school: Dict[str, Any], budget_range: str) -> bool:
        """Check if school fits budget range."""
        if budget_range == "unknown":
            return True
        
        try:
            if "-" in budget_range:
                parts = budget_range.replace("+", "").split("-")
                budget_min = int(parts[0])
                budget_max = int(parts[1]) if len(parts) > 1 else 999999
            else:
                budget_min = 0
                budget_max = int(budget_range.replace("+", ""))
            
            school_min = school["estAnnualSGDMin"]
            school_max = school["estAnnualSGDMax"]
            
            return not (school_min > budget_max or school_max < budget_min)
        except Exception:
            return True
    
    def _build_housing_rationale(self, house: Dict[str, Any], prefs: Dict[str, Any], match_info: Dict) -> str:
        """Build rationale for housing recommendation."""
        parts = []
        
        if match_info["area_match"]:
            parts.append(f"In preferred area ({house['area']})")
        
        if house["familyFriendlyScore"] >= 9:
            parts.append("highly family-friendly")
        
        if house["nearMRT"]:
            parts.append("near MRT")
        
        if not parts:
            parts.append(f"Popular with expat families in {house['area']}")
        
        return "; ".join(parts).capitalize() + "."
    
    def _build_school_rationale(self, school: Dict[str, Any], prefs: Dict[str, Any], match_info: Dict) -> str:
        """Build rationale for school recommendation."""
        parts = []
        
        curriculum = prefs.get("curriculumPreference")
        if curriculum and curriculum in school["curriculumTags"]:
            parts.append(f"Offers {curriculum} curriculum")
        
        if len(school["languageSupport"]) > 2:
            parts.append("strong language support")
        
        if not parts:
            parts.append("Well-regarded international school")
        
        return "; ".join(parts).capitalize() + "."
    
    def _build_mover_rationale(self, mover: Dict[str, Any], prefs: Dict[str, Any]) -> str:
        """Build rationale for mover recommendation."""
        parts = []
        
        if "Full service" in mover["serviceTags"]:
            parts.append("full-service option")
        
        if prefs.get("storageNeeded") and "Storage" in mover["serviceTags"]:
            parts.append("offers storage")
        
        if not parts:
            parts.append("Reliable international mover")
        
        return "; ".join(parts).capitalize() + "."
