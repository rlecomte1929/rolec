"""Regression tests for _parse_task — truncated LLM output must fail clearly.

Live incident (2026-07-14): dispatch/preview 502'd on every admin click with
"Unterminated string starting at: line 1 column 5880 (char 5879)". Cause: the
model's JSON task spec was cut off at max_tokens, so `json.loads` hit end-of-input
mid-string. The greedy `rfind('}')` sliced to some inner brace, which turned a
plain truncation into a cryptic JSONDecodeError the admin could not act on.
"""
from __future__ import annotations

import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import feedback_task_engineer as fte  # noqa: E402


def _valid_task_json() -> str:
    return (
        '{"title": "Dedupe supplier list", "strategic_objective": "obj", '
        '"execution_prompt": "do the thing", "expected_output": "out", '
        '"validation_criteria": "crit", "test_command": "", '
        '"technical_constraints": "", "risk_rollback": "", '
        '"priority": "P2", "complexity": "Low", '
        '"task_type": "Frontend Implementation", "layer": "UI", '
        '"product_area": "Core Product"}'
    )


def test_parse_task_accepts_valid_json() -> None:
    task = fte._parse_task(_valid_task_json())
    assert task["title"] == "Dedupe supplier list"
    assert task["priority"] == "P2"


def test_parse_task_accepts_markdown_fenced_json() -> None:
    task = fte._parse_task("```json\n" + _valid_task_json() + "\n```")
    assert task["layer"] == "UI"


def test_parse_task_truncated_output_raises_actionable_error() -> None:
    """A response cut off mid-string must say so — not leak a raw JSONDecodeError.

    Reproduces the live shape: a nested object closes (giving rfind('}') something
    to latch onto) and then the reply is cut off inside a later string value.
    """
    truncated = (
        '{"title": "Dedupe supplier list", "meta": {"a": 1}, '
        '"execution_prompt": "Step 1. Open the file and remove the dup'
    )
    with pytest.raises(ValueError) as exc:
        fte._parse_task(truncated)

    msg = str(exc.value)
    assert "truncated" in msg.lower(), f"error must name the real cause, got: {msg}"
    # The admin sees this string in the UI — it must not be a bare parser dump.
    assert "Unterminated string" not in msg or "truncated" in msg.lower()


def test_parse_task_missing_required_fields_still_raises() -> None:
    with pytest.raises(ValueError, match="missing required fields"):
        fte._parse_task('{"title": "only a title"}')


def test_parse_task_no_json_object_raises() -> None:
    with pytest.raises(ValueError, match="did not return a JSON object"):
        fte._parse_task("I'm sorry, I cannot help with that.")


def test_max_tokens_headroom_for_full_task_spec() -> None:
    """The prompt asks for 13 keys incl. several long prose fields; 2000 was too low
    and truncated real replies in production. Guard the headroom."""
    assert fte._MAX_TOKENS >= 4000
