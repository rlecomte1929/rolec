import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.dossier import evaluate_applies_if, validate_answer


def test_applies_if_exists_and_in():
    profile = {
        "relocationBasics": {"destCountry": "Singapore", "targetMoveDate": None},
        "assignmentContext": {"contractType": "Permanent"},
    }
    rule = {
        "and": [
            {"field": "relocationBasics.destCountry", "op": "in", "value": ["Singapore", "SG"]},
            {"field": "relocationBasics.targetMoveDate", "op": "exists", "value": False},
        ]
    }
    assert evaluate_applies_if(rule, profile) is True


def test_applies_if_not():
    profile = {"employeeProfile": {"nationality": "Norway"}}
    rule = {"not": {"field": "employeeProfile.nationality", "op": "==", "value": "Norway"}}
    assert evaluate_applies_if(rule, profile) is False


def test_validate_answer_types():
    assert validate_answer("hello", "text", None) is None
    assert validate_answer(True, "boolean", None) is None
    assert validate_answer("2026-02-01", "date", None) is None
    assert validate_answer("A", "select", ["A", "B"]) is None
    assert validate_answer(["A"], "multiselect", ["A", "B"]) is None
    assert validate_answer(123, "text", None) is not None
    assert validate_answer("maybe", "boolean", None) is not None
