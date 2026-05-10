"""
Agent A — Intake Orchestrator
Owns the question flow and state machine.
Produces next_question and completion_state.
"""
from typing import Dict, Any, Optional, List, Set
from ..schemas import Question, NextQuestionResponse, RelocationProfile
from ..question_bank import get_all_questions, get_question_by_id
from .validator import ProfileValidator
from .readiness_rater import ReadinessRater
from .recommendation_engine import RecommendationEngine


class IntakeOrchestrator:
    """Orchestrates the intake question flow."""
    
    def __init__(self):
        self.validator = ProfileValidator()
        self.readiness_rater = ReadinessRater()
        self.recommendation_engine = RecommendationEngine()
        self.all_questions = get_all_questions()
    
    def get_next_question(
        self,
        profile: Dict[str, Any],
        answered_questions: Set[str],
        skip_question_ids: Optional[Set[str]] = None,
    ) -> NextQuestionResponse:
        """
        Determine the next question to ask based on current profile state.
        Returns None if intake is complete.
        """
        # Check if we have minimum data for recommendations
        completeness_check = self.validator.is_profile_complete_for_recommendations(profile)
        
        all_complete = all(completeness_check.values())
        
        # Calculate progress
        questions = get_all_questions(skip_question_ids)
        total_questions = len(questions)
        answered_count = len(answered_questions)
        progress = {
            "answeredCount": answered_count,
            "totalQuestions": total_questions,
            "percentComplete": int((answered_count / total_questions) * 100) if total_questions > 0 else 0
        }
        
        # If all minimum data collected, mark as complete
        if all_complete:
            return NextQuestionResponse(
                question=None,
                isComplete=True,
                progress=progress
            )
        
        # Find next unanswered question
        for question in questions:
            if question.id in answered_questions:
                continue
            
            # Check dependencies (if any)
            if self._check_dependencies(question, profile):
                return NextQuestionResponse(
                    question=question,
                    isComplete=False,
                    progress=progress
                )
        
        # No more questions, mark complete
        return NextQuestionResponse(
            question=None,
            isComplete=True,
            progress=progress
        )
    
    def apply_answer(self, profile: Dict[str, Any], question_id: str, answer: Any, is_unknown: bool = False) -> Dict[str, Any]:
        """
        Apply an answer to the profile.
        Uses the mapsTo field to update the correct location.
        """
        question = get_question_by_id(question_id)
        if not question:
            return profile
        
        # If unknown, store a special marker
        if is_unknown:
            answer = "unknown"
        
        # Parse the mapsTo path and set value
        self._set_nested_value(profile, question.mapsTo, answer)
        
        return profile
    
    def compute_completion_state(
        self,
        profile: Dict[str, Any],
        total_questions: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Compute overall completion state including readiness and recommendations.
        """
        # Validate profile
        normalized_profile, validation_errors = self.validator.validate_and_normalize(profile)
        
        # Check completeness for each area
        completeness = self.validator.is_profile_complete_for_recommendations(normalized_profile)
        
        # Calculate overall completeness percentage
        answered_fields = self._count_answered_fields(normalized_profile)
        total_fields = total_questions if total_questions is not None else self._count_total_fields()
        profile_completeness = int((answered_fields / total_fields) * 100) if total_fields > 0 else 0
        # Guardrail: the heuristic field counter can exceed total_fields due to nested defaults.
        profile_completeness = max(0, min(100, profile_completeness))
        
        # Compute readiness rating
        immigration_readiness = None
        if completeness.get("readiness"):
            immigration_readiness = self.readiness_rater.compute_readiness(normalized_profile)
        
        # Generate recommendations
        recommendations = {}
        if completeness.get("housing"):
            recommendations["housing"] = self.recommendation_engine.get_housing_recommendations(normalized_profile)
        if completeness.get("schools"):
            recommendations["schools"] = self.recommendation_engine.get_school_recommendations(normalized_profile)
        if completeness.get("movers"):
            recommendations["movers"] = self.recommendation_engine.get_mover_recommendations(normalized_profile)
        
        return {
            "profileCompleteness": profile_completeness,
            "validationErrors": validation_errors,
            "completeness": completeness,
            "immigrationReadiness": immigration_readiness,
            "recommendations": recommendations
        }
    
    def _check_dependencies(self, question: Question, profile: Dict[str, Any]) -> bool:
        """
        Check if all dependsOn conditions are satisfied for this question.

        dependsOn format (Dict[question_id, condition]):
          {"q_has_spouse": True}                  — prerequisite must equal True
          {"q_has_spouse": False}                 — prerequisite must equal False
          {"q_child_count": {"gte": 1}}           — numeric >=
          {"q_child_count": {"gt": 0}}            — numeric >
          {"q_contract_type": {"not": "domestic_move"}}     — not equal
          {"q_contract_type": {"in": ["lta", "short_term_project"]}}  — any of

        All conditions in the dict must pass (AND semantics).
        If a prerequisite question has not been answered yet (value is None or
        absent from the profile), the condition is treated as NOT satisfied —
        i.e. the dependent question is not shown yet.
        """
        if not question.dependsOn:
            return True

        for prereq_question_id, condition in question.dependsOn.items():
            prereq_q = get_question_by_id(prereq_question_id)
            if prereq_q is None:
                # Unknown prerequisite — skip this condition (fail open for
                # unknown question IDs to avoid silently hiding questions).
                continue

            actual_value = self._get_nested_value(profile, prereq_q.mapsTo)

            if actual_value is None:
                # Prerequisite not yet answered — block the dependent question.
                return False

            if not self._evaluate_condition(actual_value, condition):
                return False

        return True

    def _evaluate_condition(self, actual_value: Any, condition: Any) -> bool:
        """
        Evaluate a single condition against an actual profile value.

        Supports:
          - Scalar equality: condition is a literal (str, int, bool)
          - Dict operators: {"not": v}, {"in": [...]}, {"gt": n}, {"gte": n},
            {"lt": n}, {"lte": n}
        """
        if isinstance(condition, dict):
            if "not" in condition:
                return actual_value != condition["not"]
            if "in" in condition:
                return actual_value in condition["in"]
            if "gt" in condition:
                return self._to_numeric(actual_value) > condition["gt"]
            if "gte" in condition:
                return self._to_numeric(actual_value) >= condition["gte"]
            if "lt" in condition:
                return self._to_numeric(actual_value) < condition["lt"]
            if "lte" in condition:
                return self._to_numeric(actual_value) <= condition["lte"]
            # Unknown operator — fail open
            return True

        # Scalar: exact match
        return actual_value == condition

    def _to_numeric(self, value: Any) -> float:
        """
        Coerce a profile value to a number for comparison operators.
        Handles string digits ("2") and numeric types.
        Returns 0 for non-coercible values.
        """
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _get_nested_value(self, obj: Dict[str, Any], path: str) -> Any:
        """
        Read a value from a nested dictionary using dot notation.
        Returns None if any segment of the path is missing.
        """
        parts = path.split(".")
        current: Any = obj
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                idx = int(part)
                current = current[idx] if idx < len(current) else None
            else:
                return None
            if current is None:
                return None
        return current
    
    def _set_nested_value(self, obj: Dict[str, Any], path: str, value: Any) -> None:
        """
        Set a value in a nested dictionary using dot notation.
        E.g., "movePlan.housing.budgetMonthlySGD" -> obj["movePlan"]["housing"]["budgetMonthlySGD"] = value
        """
        parts = path.split(".")
        current = obj
        
        for i, part in enumerate(parts[:-1]):
            # Handle array indices like "dependents.0.firstName"
            if part.isdigit():
                idx = int(part)
                # Ensure parent is a list
                if not isinstance(current, list):
                    return
                # Ensure list is long enough
                while len(current) <= idx:
                    current.append({})
                current = current[idx]
            else:
                if part not in current:
                    # Determine if next part is a digit (array index)
                    if i + 1 < len(parts) and parts[i + 1].isdigit():
                        current[part] = []
                    else:
                        current[part] = {}
                current = current[part]
        
        # Set final value
        final_key = parts[-1]
        if final_key.isdigit():
            idx = int(final_key)
            while len(current) <= idx:
                current.append({})
            current[idx] = value
        else:
            current[final_key] = value
    
    def _count_answered_fields(self, profile: Dict[str, Any]) -> int:
        """Count how many fields have been answered in the profile."""
        count = 0
        
        # Simple heuristic: count non-None, non-empty values
        def count_values(obj):
            nonlocal count
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if value is not None and value != "" and value != [] and value != "unknown":
                        count += 1
                    if isinstance(value, (dict, list)):
                        count_values(value)
            elif isinstance(obj, list):
                for item in obj:
                    count_values(item)
        
        count_values(profile)
        return count
    
    def _count_total_fields(self) -> int:
        """Count total expected fields (approximate based on questions)."""
        return len(self.all_questions)
