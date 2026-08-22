"""Beam pass runner — the AUTHORING half of the candidate beam.

N independent model passes over one corridor, each with a different framing, collected in
arrival order and handed to `ranking.build_candidates` for dedupe. Nothing here is served:
output lands in `candidate_beam_items` as `pending_review` and reaches a customer only
through the existing /admin approval gate.

THIS MODULE CALLS AN LLM AND MUST NEVER BECOME REACHABLE FROM A SERVING ENGINE.
`scripts/check_serving_llm_isolation.py` enforces that — if a serving root ever imports
this (directly or transitively) the build fails with the chain. That is the generation/
serving split: models draft, humans approve, the deterministic engine serves.

Three deliberate choices:

* **Framings are fixed and ordered.** The five are the ones the validated run used. Pass
  number is their index, so a re-run is comparable to the reference set rather than
  merely similar.
* **A failed pass is recorded, not dropped.** `pass_meta` keeps the slot with its error.
  Silently discarding it would inflate cross-pass agreement: an item seen in 3 of 3
  surviving passes would report 3/3 when two passes never ran, and `pass_frequency` is the
  main signal a reviewer trusts.
* **Free-text context is masked before it leaves the platform.** `mask_pii` per the repo's
  GDPR Art. 28/44 rule — corridor context is operator-written and can name a real person.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Sequence

from .parsing import ModelJsonError, extract_items, parse_model_json
from .ranking import MAX_ITEMS_PER_PASS, build_candidates

log = logging.getLogger(__name__)

__all__ = [
    "PASS_FRAMINGS",
    "FRAMING_INSTRUCTIONS",
    "build_pass_prompt",
    "run_pass",
    "run_beam",
    "default_model",
]

#: The five framings of the validated run, in order. Pass number == index + 1.
#: Diversity is the mechanism: five near-identical prompts would agree with themselves and
#: report false consensus, so each pass is asked to look from a different angle.
PASS_FRAMINGS: Sequence[str] = (
    "zero_shot_official_audit",
    "few_shot_gap_hunter",
    "lived_experience",
    "professional_advisor",
    "red_team_gap_finder",
)

FRAMING_INSTRUCTIONS: Dict[str, str] = {
    "zero_shot_official_audit": (
        "Work through the move as an official compliance audit would: enumerate every "
        "obligation an authority in either country imposes, in the order they fall due."
    ),
    "few_shot_gap_hunter": (
        "Assume a competent checklist already covers the obvious steps. Hunt for the "
        "obligations such a checklist habitually omits."
    ),
    "lived_experience": (
        "Answer as someone who has actually made this move and hit the problems in "
        "person. Prefer what actually happens over what the rule says should happen."
    ),
    "professional_advisor": (
        "Answer as a cross-border tax and social-security adviser briefing a colleague: "
        "employer-side exposure, coordination certificates, permanent-establishment risk."
    ),
    "red_team_gap_finder": (
        "Red-team the move. Find the obligations whose deadline is missed most often, or "
        "that only surface once something has already gone wrong."
    ),
}

_SYSTEM = (
    "You are compiling a research worklist of relocation obligations for a specific "
    "cross-border corridor. Output is reviewed by a human before anyone sees it, so "
    "completeness matters more than polish.\n\n"
    "Return ONLY a JSON array. Each element:\n"
    '  {"title": str, "official_guidance": str, "actual_reality": str, '
    '"action_required": str, "source": str|null, "category": str}\n\n'
    "Rules:\n"
    "- `source` is the official page or instrument you are relying on. If you are not "
    "relying on a specific one, use null. NEVER invent a URL or a citation — an "
    "unsourced item is a research task, an invented source is a defect that survives "
    "review by looking already done.\n"
    "- `action_required` is what the person must actually do.\n"
    "- Describe obligations; do not give individualised legal advice.\n"
    f"- At most {MAX_ITEMS_PER_PASS} items."
)


def default_model() -> str:
    """The model default, taken from llm_client's configuration rather than restated.

    Imported lazily and inside the function so a caller that only wants prompt-building
    or parsing never pulls the LLM stack in. Falls back only if that private default is
    ever renamed — losing the guardrail would be worse than a stale literal.
    """
    try:
        from ...app.services import llm_client  # type: ignore

        return getattr(llm_client, "_OPENAI_DEFAULT_MODEL", "gpt-4o")
    except Exception:  # pragma: no cover - import-environment dependent
        return "gpt-4o"


def build_pass_prompt(
    *,
    corridor: str,
    employee_type: str,
    framing: str,
    context: Optional[str] = None,
) -> Dict[str, str]:
    """The (system, user) pair for one pass. Pure — no I/O, no model call.

    `context` is operator-written free text and is masked before it is placed in the
    prompt: it can name the employee whose case prompted the run, and an LLM provider is
    a sub-processor of anything we send it (GDPR Art. 28/44, the repo's hard rule).
    """
    if framing not in FRAMING_INSTRUCTIONS:
        raise ValueError(f"unknown framing {framing!r}; expected one of {list(PASS_FRAMINGS)}")

    parts = [
        f"Corridor: {corridor}",
        f"Employee type: {employee_type}",
        "",
        FRAMING_INSTRUCTIONS[framing],
    ]
    if context and context.strip():
        from ...app.services.pii_masker import mask_pii

        parts += ["", "Additional context:", mask_pii(context.strip())]
    return {"system": _SYSTEM, "user": "\n".join(parts)}


def run_pass(
    *,
    corridor: str,
    employee_type: str,
    framing: str,
    context: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.4,
    complete: Optional[Callable[..., str]] = None,
) -> Dict[str, Any]:
    """One pass. Returns a record with its items in arrival order — never raises.

    A pass that fails returns ``ok=False`` with the error text and an empty item list, so
    the caller records the slot rather than losing it. `complete` is injectable so tests
    exercise the real path with a stub instead of a paid call.

    Temperature 0.4, not 0: the passes are a diversity instrument, and five identical
    samples would agree with themselves and report consensus that is really repetition.
    Determinism lives downstream — given the same stored pass outputs, ranking is exact.
    """
    chosen_model = model or default_model()
    prompt = build_pass_prompt(
        corridor=corridor, employee_type=employee_type, framing=framing, context=context
    )

    if complete is None:  # pragma: no cover - exercised via injection in tests
        from ...app.services.llm_client import complete_text_sync as complete  # type: ignore

    started = time.monotonic()
    try:
        raw = complete(
            system=prompt["system"],
            user=prompt["user"],
            model=chosen_model,
            temperature=temperature,
            json_object=True,
        )
        items = extract_items(parse_model_json(raw))
        return {
            "ok": True,
            "framing": framing,
            "model": chosen_model,
            "items": items,
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
            "error": None,
        }
    except ModelJsonError as exc:
        # The failure mode that killed run 2. Named separately so the run record says
        # "the model answered but not in JSON", which is a prompt problem, not an outage.
        log.warning("candidate_beam pass %s: unparseable output — %s", framing, exc)
        return _failed(framing, chosen_model, started, f"unparseable model output: {exc}")
    except Exception as exc:  # noqa: BLE001 - a bad pass must not kill the run
        log.warning("candidate_beam pass %s failed: %s", framing, exc)
        return _failed(framing, chosen_model, started, f"{type(exc).__name__}: {exc}")


def _failed(framing: str, model: str, started: float, error: str) -> Dict[str, Any]:
    return {
        "ok": False,
        "framing": framing,
        "model": model,
        "items": [],
        "duration_ms": round((time.monotonic() - started) * 1000, 1),
        "error": error,
    }


MIN_PASSES = 2
#: 7, not len(PASS_FRAMINGS). The schema CHECK already allows `passes_requested BETWEEN 2
#: AND 7`, so capping at five here made the database promise something the code refused —
#: a run requesting six failed with an unexplained ValueError against a column that had
#: agreed to store it.
MAX_PASSES = 7


def framing_for(pass_number: int) -> str:
    """Framing for a 1-based pass number, CYCLING past the fifth.

    `PASS_FRAMINGS[:passes]` truncated instead, which quietly made 5 the ceiling. Cycling
    is what the method specifies for N != 5: a 7-pass run repeats the audit and gap-hunter
    framings rather than being rejected, and two runs of the same framing at the same
    temperature are still independent witnesses — which is the only property the
    cross-pass agreement count depends on.
    """
    if pass_number < 1:
        raise ValueError("pass_number is 1-based")
    return PASS_FRAMINGS[(pass_number - 1) % len(PASS_FRAMINGS)]


def run_beam(
    *,
    corridor: str,
    employee_type: str,
    passes: int = len(PASS_FRAMINGS),
    context: Optional[str] = None,
    model: Optional[str] = None,
    complete: Optional[Callable[..., str]] = None,
) -> Dict[str, Any]:
    """Run the beam and return the persistable record.

    ``pass_outputs`` is the load-bearing artifact: each item carries an explicit
    ``arrival_ordinal`` (1-based, against the raw array) so the exact clustering input is
    reconstructible without reverse-engineering. That is the E3 fix — a golden fixture
    must never again have to guess the order it was built from.

    ``candidates`` is built ONLY from the passes that succeeded, and ``passes_total``
    counts those, so ``pass_frequency`` stays honest when a pass dies.
    """
    if not MIN_PASSES <= passes <= MAX_PASSES:
        raise ValueError(f"passes must be between {MIN_PASSES} and {MAX_PASSES}, got {passes}")

    chosen_model = model or default_model()
    pass_outputs: List[Dict[str, Any]] = []
    pass_meta: List[Dict[str, Any]] = []

    for index in range(1, passes + 1):
        framing = framing_for(index)
        record = run_pass(
            corridor=corridor,
            employee_type=employee_type,
            framing=framing,
            context=context,
            model=chosen_model,
            complete=complete,
        )
        items = [
            {**item, "arrival_ordinal": ordinal}
            for ordinal, item in enumerate(record["items"][:MAX_ITEMS_PER_PASS], start=1)
        ]
        pass_outputs.append({"pass": index, "framing": framing, "items": items})
        pass_meta.append(
            {
                "pass": index,
                "framing": framing,
                "ok": record["ok"],
                "model": record["model"],
                "item_count": len(items),
                "duration_ms": record["duration_ms"],
                "error": record["error"],
            }
        )

    successful = [p for p, meta in zip(pass_outputs, pass_meta) if meta["ok"]]
    candidates = build_candidates(
        [p["items"] for p in successful],
        framings=[p["framing"] for p in successful],
    )

    completed = len(successful)
    return {
        "corridor": corridor,
        "employee_type": employee_type,
        "llm_model": chosen_model,
        "passes_requested": passes,
        "passes_completed": completed,
        # 'generating' is never a terminal state; a run with no usable pass is failed, not
        # an empty success, so the review queue never shows a run that found nothing when
        # in fact nothing ran.
        "status": "pending_review" if completed >= 2 else "failed",
        "error": None if completed >= 2 else "fewer than 2 passes succeeded",
        "pass_outputs": pass_outputs,
        "pass_meta": pass_meta,
        "candidates": candidates,
        "candidate_count": len(candidates),
    }
