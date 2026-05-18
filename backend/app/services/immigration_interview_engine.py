"""
Immigration Interview Engine — IMM-06
======================================
Stateless DAG-based interview state machine.

The engine is purely computational — it takes session state and vault data as
inputs and returns state mutations. All database I/O lives in the router.

Public API
----------
  load_questions()                                   -> List[QuestionNode]
  get_next_question(answers, vault, confirmed_prefills, questions)
                                                     -> Optional[QuestionNode]
  evaluate_condition(condition, answers)             -> bool
  get_vault_updates(question, answer_value)          -> Dict[str, Any]
  compute_section_progress(answers, questions)       -> Dict[str, SectionProgress]
  compute_completion_pct(answers, questions)         -> int
  detect_address_gaps(address_list)                  -> List[AddressGap]
  validate_answer(question, answer_value)            -> AnswerValidationResult
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Condition:
    question_id: str
    operator: str   # eq | ne | in | not_in | answered | not_answered | truthy | falsy
    value: Any      # str | List[str] | None


@dataclass
class QuestionNode:
    id: str
    section: str
    order: int
    label: str
    help_text: str
    type: str       # text | date | select | boolean | upload | address | address_list | dependent_list
    required: bool
    skippable: bool
    vault_field: Optional[str]
    condition: Optional[Condition]
    options: Optional[List[str]] = None
    option_labels: Optional[Dict[str, str]] = None
    upload_endpoint: Optional[str] = None


@dataclass
class SectionProgress:
    section_id: str
    total_applicable: int       # questions whose condition is currently met
    answered: int
    required_answered: int
    required_total: int
    is_complete: bool


@dataclass
class AddressGap:
    from_address: Dict[str, Any]
    to_address: Dict[str, Any]
    gap_days: int


@dataclass
class AnswerValidationResult:
    is_valid: bool
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Load question DAG from JSON
# ---------------------------------------------------------------------------

_QUESTIONS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "interview_questions.json")
_QUESTION_CACHE: Optional[List[QuestionNode]] = None


def load_questions(force_reload: bool = False) -> List[QuestionNode]:
    """Load and cache the question DAG from interview_questions.json."""
    global _QUESTION_CACHE
    if _QUESTION_CACHE is not None and not force_reload:
        return _QUESTION_CACHE

    with open(_QUESTIONS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Build section order lookup
    section_order = {s["id"]: s["order"] for s in data.get("sections", [])}

    nodes: List[QuestionNode] = []
    for q in data.get("questions", []):
        cond_data = q.get("condition")
        condition = None
        if cond_data:
            condition = Condition(
                question_id=cond_data["question_id"],
                operator=cond_data["operator"],
                value=cond_data.get("value"),
            )

        # Effective sort key: (section_order, question_order)
        nodes.append(QuestionNode(
            id=q["id"],
            section=q["section"],
            order=section_order.get(q["section"], 99) * 1000 + q["order"],
            label=q["label"],
            help_text=q.get("help_text", ""),
            type=q["type"],
            required=q.get("required", True),
            skippable=q.get("skippable", False),
            vault_field=q.get("vault_field"),
            condition=condition,
            options=q.get("options"),
            option_labels=q.get("option_labels"),
            upload_endpoint=q.get("upload_endpoint"),
        ))

    nodes.sort(key=lambda n: n.order)
    _QUESTION_CACHE = nodes
    return nodes


# ---------------------------------------------------------------------------
# Condition evaluation
# ---------------------------------------------------------------------------

def evaluate_condition(condition: Optional[Condition], answers: Dict[str, Any]) -> bool:
    """
    Returns True if the condition is met (or if there is no condition).
    Operators:
      eq         — answer to question_id == value (string comparison)
      ne         — answer to question_id != value
      in         — answer is in value (list)
      not_in     — answer is not in value (list)
      answered   — question_id has any non-empty answer
      not_answered — question_id has no answer yet
      truthy     — answer to question_id is truthy ("true", non-empty, etc.)
      falsy      — answer to question_id is falsy ("false", None, "")
    """
    if condition is None:
        return True

    raw = answers.get(condition.question_id)
    answer_str = str(raw).strip().lower() if raw is not None else ""

    op = condition.operator
    val = condition.value

    if op == "eq":
        return answer_str == str(val).lower()
    elif op == "ne":
        return answer_str != str(val).lower()
    elif op == "in":
        return answer_str in [str(v).lower() for v in (val or [])]
    elif op == "not_in":
        return answer_str not in [str(v).lower() for v in (val or [])]
    elif op == "answered":
        return bool(raw) and answer_str != ""
    elif op == "not_answered":
        return not bool(raw) or answer_str == ""
    elif op == "truthy":
        return answer_str in ("true", "yes", "1")
    elif op == "falsy":
        return answer_str in ("false", "no", "0", "")
    return True


# ---------------------------------------------------------------------------
# Next question logic
# ---------------------------------------------------------------------------

def get_next_question(
    answers: Dict[str, Any],
    vault: Dict[str, Any],
    confirmed_prefills: List[str],
    questions: Optional[List[QuestionNode]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Returns a dict describing the next unanswered applicable question, or None
    if the interview is complete.

    A question is skipped if:
      - It has already been answered in `answers`
      - Its condition evaluates to False given current answers
      - Its vault_field is already confirmed (listed in confirmed_prefills)

    A question is returned with pre_filled=True if:
      - Its vault_field maps to a non-null value in the vault
      - It has NOT yet been answered
      - It has NOT been confirmed (not in confirmed_prefills)

    Returns a plain dict ready for JSON serialisation.
    """
    if questions is None:
        questions = load_questions()

    for q in questions:
        # Skip if condition not met
        if not evaluate_condition(q.condition, answers):
            continue

        # Skip if already answered
        if q.id in answers:
            continue

        # Skip if vault field is confirmed (user accepted the pre-fill)
        if q.vault_field and q.vault_field in confirmed_prefills:
            continue

        # Check for vault pre-fill
        vault_value = vault.get(q.vault_field) if q.vault_field else None
        # Mask encrypted blobs (long binary strings) — show as pre-filled but don't expose value
        if vault_value and isinstance(vault_value, str) and len(vault_value) > 80:
            vault_value = "••••••••"

        result: Dict[str, Any] = {
            "question_id": q.id,
            "section": q.section,
            "label": q.label,
            "help_text": q.help_text,
            "type": q.type,
            "required": q.required,
            "skippable": q.skippable,
            "options": q.options,
            "option_labels": q.option_labels,
            "upload_endpoint": q.upload_endpoint,
            "pre_filled": vault_value is not None,
            "existing_value": vault_value,
        }
        return result

    return None  # Interview complete


# ---------------------------------------------------------------------------
# Vault field mapping
# ---------------------------------------------------------------------------

def get_vault_updates(question: QuestionNode, answer_value: Any) -> Dict[str, Any]:
    """
    Given a question and a user-provided answer, return the dict of
    vault column updates to apply (may be empty if question has no vault_field).
    """
    if not question.vault_field:
        return {}
    if answer_value is None:
        return {}

    val = answer_value

    # Normalise booleans
    if question.type == "boolean":
        if isinstance(val, str):
            val = val.lower() in ("true", "yes", "1")
        val = bool(val)

    # Normalise dates to YYYY-MM-DD
    if question.type == "date" and isinstance(val, str):
        val = _normalise_date(val) or val

    return {question.vault_field: val}


def _normalise_date(val: str) -> Optional[str]:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(val.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Answer validation
# ---------------------------------------------------------------------------

def validate_answer(question: QuestionNode, answer_value: Any) -> AnswerValidationResult:
    """Light validation of user-supplied answer against question type and options."""
    if answer_value is None or str(answer_value).strip() == "":
        if question.required and not question.skippable:
            return AnswerValidationResult(is_valid=False, error="This field is required.")
        return AnswerValidationResult(is_valid=True)  # blank is OK for optional/skippable

    val = str(answer_value).strip()

    if question.type == "date":
        if not _normalise_date(val):
            return AnswerValidationResult(
                is_valid=False,
                error="Invalid date format. Use YYYY-MM-DD, DD/MM/YYYY, or DD.MM.YYYY.",
            )

    if question.type == "select" and question.options:
        if val.lower() not in [o.lower() for o in question.options]:
            return AnswerValidationResult(
                is_valid=False,
                error=f"Invalid option '{val}'. Choose from: {', '.join(question.options)}.",
            )

    if question.type == "boolean":
        if val.lower() not in ("true", "false", "yes", "no", "1", "0"):
            return AnswerValidationResult(
                is_valid=False,
                error="Expected a yes/no answer.",
            )

    return AnswerValidationResult(is_valid=True)


# ---------------------------------------------------------------------------
# Section progress
# ---------------------------------------------------------------------------

def compute_section_progress(
    answers: Dict[str, Any],
    questions: Optional[List[QuestionNode]] = None,
) -> Dict[str, SectionProgress]:
    """
    For each section, count total applicable questions, answered questions, and
    required completion status.

    A question is 'applicable' if its condition is currently met given `answers`.
    A section is 'complete' when all non-skippable required questions are answered.
    """
    if questions is None:
        questions = load_questions()

    # Collect unique sections in order
    seen: Dict[str, SectionProgress] = {}
    for q in questions:
        if q.section not in seen:
            seen[q.section] = SectionProgress(
                section_id=q.section,
                total_applicable=0,
                answered=0,
                required_answered=0,
                required_total=0,
                is_complete=False,
            )

    for q in questions:
        if not evaluate_condition(q.condition, answers):
            continue
        sp = seen[q.section]
        sp.total_applicable += 1
        if q.id in answers:
            sp.answered += 1
            if q.required and not q.skippable:
                sp.required_answered += 1
        if q.required and not q.skippable:
            sp.required_total += 1

    for sp in seen.values():
        sp.is_complete = sp.required_answered >= sp.required_total and sp.required_total > 0

    return seen


def compute_completion_pct(
    answers: Dict[str, Any],
    questions: Optional[List[QuestionNode]] = None,
) -> int:
    """Return 0–100 percentage of applicable required questions answered."""
    if questions is None:
        questions = load_questions()

    total = 0
    done = 0
    for q in questions:
        if not evaluate_condition(q.condition, answers):
            continue
        if q.required and not q.skippable:
            total += 1
            if q.id in answers:
                done += 1

    if total == 0:
        return 0
    return round((done / total) * 100)


# ---------------------------------------------------------------------------
# Address gap detection
# ---------------------------------------------------------------------------

def detect_address_gaps(address_list: List[Dict[str, Any]]) -> List[AddressGap]:
    """
    Given a list of address records with 'from_date' and 'to_date' (YYYY-MM-DD),
    detect any gaps greater than 30 days between consecutive addresses.

    Addresses without dates are skipped. Returned gaps are sorted chronologically.
    """
    dated: List[tuple[date, date, Dict]] = []
    for addr in address_list:
        try:
            from_d = date.fromisoformat(str(addr.get("from_date", ""))[:10])
            # to_date of None / empty means current address
            to_raw = addr.get("to_date")
            to_d = date.fromisoformat(str(to_raw)[:10]) if to_raw else date.today()
            dated.append((from_d, to_d, addr))
        except (ValueError, TypeError):
            continue

    if len(dated) < 2:
        return []

    # Sort by from_date ascending
    dated.sort(key=lambda t: t[0])

    gaps: List[AddressGap] = []
    for i in range(len(dated) - 1):
        _, end_of_current, current_addr = dated[i]
        start_of_next, _, next_addr = dated[i + 1]
        gap_days = (start_of_next - end_of_current).days
        if gap_days > 30:
            gaps.append(AddressGap(
                from_address=current_addr,
                to_address=next_addr,
                gap_days=gap_days,
            ))

    return gaps


# ---------------------------------------------------------------------------
# Section summary helper
# ---------------------------------------------------------------------------

def get_section_summary(
    section_id: str,
    answers: Dict[str, Any],
    questions: Optional[List[QuestionNode]] = None,
) -> Dict[str, Any]:
    """
    Return completion details for a single section.
    Used by GET /interview/status per-section breakdown.
    """
    if questions is None:
        questions = load_questions()

    progress = compute_section_progress(answers, questions)
    sp = progress.get(section_id)
    if not sp:
        return {"section_id": section_id, "error": "Unknown section."}

    section_questions = [
        {
            "question_id": q.id,
            "label": q.label,
            "required": q.required,
            "skippable": q.skippable,
            "answered": q.id in answers,
            "applicable": evaluate_condition(q.condition, answers),
        }
        for q in questions
        if q.section == section_id
    ]

    return {
        "section_id": section_id,
        "total_applicable": sp.total_applicable,
        "answered": sp.answered,
        "required_answered": sp.required_answered,
        "required_total": sp.required_total,
        "is_complete": sp.is_complete,
        "questions": section_questions,
    }
