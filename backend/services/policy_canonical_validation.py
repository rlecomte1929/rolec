"""
Validation for canonical policy facts.
"""
from __future__ import annotations

from typing import List, Tuple

from pydantic import ValidationError

from ..app.schemas import PolicyFactCanonicalCreate, ValueType


def validate_canonical_fact_payload(
    fact: PolicyFactCanonicalCreate,
) -> List[str]:
    errors: List[str] = []
    value_type = fact.value_type

    if value_type == ValueType.MONETARY:
        if fact.amount is None:
            errors.append("amount is required when value_type is monetary")
        if not fact.currency:
            errors.append("currency is required when value_type is monetary")
    if value_type == ValueType.PERCENTAGE and fact.percentage is None:
        errors.append("percentage is required when value_type is percentage")
    if value_type == ValueType.DURATION:
        if fact.duration_value is None:
            errors.append("duration_value is required when value_type is duration")
        if not fact.duration_unit:
            errors.append("duration_unit is required when value_type is duration")
    if value_type == ValueType.QUANTITY and fact.quantity is None:
        errors.append("quantity is required when value_type is quantity")
    if value_type == ValueType.TEXT and not fact.value_text:
        errors.append("value_text is required when value_type is text")

    if fact.eligibility.assignment_types and not fact.assignment_types:
        errors.append("assignment_types must be populated when eligibility references assignment_types")
    if fact.frequency is not None and value_type not in (
        ValueType.MONETARY,
        ValueType.PERCENTAGE,
        ValueType.QUANTITY,
        ValueType.DURATION,
    ):
        errors.append("frequency is only valid for monetary, percentage, quantity, or duration values")
    if fact.provider_entity is not None and not fact.title and not fact.description:
        errors.append("provider_entity requires title or description context")
    return errors


def validate_canonical_fact_model(
    payload: dict,
) -> Tuple[PolicyFactCanonicalCreate | None, List[str]]:
    try:
        fact = PolicyFactCanonicalCreate.model_validate(payload)
    except ValidationError as exc:
        return None, [str(err.get("msg") or "validation error") for err in exc.errors()]
    return fact, validate_canonical_fact_payload(fact)
