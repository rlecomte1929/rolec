"""
STA-vs-LTA roadmap differential eval (AIQ-1349 gap #5).

Two layers of assurance that assignment_type actually shapes the generated
roadmap for the SAME corridor:

  Test 1 (deterministic, normal CI): proves `roadmap_generator.generate()`
    threads `classification.assignment_type` into the LLM prompt's SUBJECT
    block. Uses a capturing stand-in client (no network, no key) that records
    `req.user_message` and returns a minimal valid `emit_case_roadmap` tool
    result — modelled on MockClient's tool_use response shape
    (test_rag_roadmap_pipeline.py). The signal-reaches-prompt guard.

  Test 2 (opt-in live differential, marker-gated): the real quality eval.
    Runs the live Anthropic model over ONE corridor's chunks — which carry
    BOTH short-term entry/work-authorization material AND long-term-only
    material (permanent residence / school enrolment / long-term housing) —
    twice: assignment_type="STA" vs "LTA". Asserts the LTA roadmap surfaces
    strictly MORE long-term steps than the STA roadmap. Robust to LLM variance
    via a strict inequality on a keyword count rather than exact text.

Gated by `pytestmark = pytest.mark.policy_assistant_audit` (conftest skips it
unless `-m policy_assistant_audit` / RUN_POLICY_ASSISTANT_AUDIT=1) AND an inner
skip when no ANTHROPIC_API_KEY is available — so it degrades cleanly.
"""
from __future__ import annotations

import json
import os
import re

import pytest

from backend.app.services import roadmap_generator
from backend.app.services.immigration_retriever import PathClassification, UserProfile

# NB: the opt-in `policy_assistant_audit` marker is applied to the LIVE test
# (Test 2) ONLY, not module-wide — Test 1 is deterministic and must run in
# normal CI. (Task text suggested a module-level `pytestmark`, but that would
# also gate/skip the deterministic guard; the correctness requirement wins.)


# --- Shared fixtures -------------------------------------------------------

_PROFILE = UserProfile(
    nationality="FR", origin_country="FR", destination_country="DE", is_eea=True
)

# Corridor chunks carrying material for BOTH short-term entry / work
# authorization steps AND long-term-only steps (permanent residence, school
# enrolment, long-term housing) — so the live model has grounded content to
# differentiate STA from LTA. `generate()`/`_build_context_message` only read
# id, source_url and chunk_text off each chunk.
_FR_DE_CHUNKS = [
    {
        "id": "fr-de-eea-entry-01",
        "source_url": "https://www.make-it-in-germany.com/en/visa-residence/eu-citizens",
        "chunk_text": (
            "EU/EEA nationals may enter Germany and start work without a visa. For any "
            "stay, register your residential address (Anmeldung) at the local Bürgeramt "
            "within two weeks of arrival to receive a registration certificate."
        ),
    },
    {
        "id": "fr-de-work-auth-02",
        "source_url": "https://www.make-it-in-germany.com/en/working-in-germany",
        "chunk_text": (
            "As an EU/EEA citizen you have full freedom of movement for workers and need "
            "no separate work permit to take up employment in Germany. Your employer "
            "registers you for social security and you receive a tax identification number."
        ),
    },
    {
        "id": "fr-de-permanent-residence-03",
        "source_url": "https://www.bamf.de/EN/Themen/MigrationAufenthalt/permanent-residence",
        "chunk_text": (
            "After five years of continuous residence, EU/EEA nationals may apply for a "
            "permanent residence certificate (Daueraufenthaltsrecht) confirming a "
            "long-term right of settlement in Germany."
        ),
    },
    {
        "id": "fr-de-school-enrolment-04",
        "source_url": "https://www.make-it-in-germany.com/en/living-in-germany/family/school",
        "chunk_text": (
            "School attendance (Schulpflicht) is compulsory for resident children. Families "
            "relocating long-term must enrol children at the local school authority "
            "(Schulamt); enrolment is not required for very short assignments."
        ),
    },
    {
        "id": "fr-de-longterm-housing-05",
        "source_url": "https://www.make-it-in-germany.com/en/living-in-germany/housing",
        "chunk_text": (
            "For a long-term stay, secure a permanent rental (unbefristeter Mietvertrag) and "
            "obtain the landlord confirmation (Wohnungsgeberbestätigung) needed for "
            "registration. Short assignments typically use temporary or serviced housing."
        ),
    },
]

# Long-term-only signal used by Test 2's differential assertion. Matched over
# each step's title + description text (there is no category/pillar field).
_LONGTERM_RE = re.compile(
    r"permanent residen|school|enrol|long-term hous|settlement", re.IGNORECASE
)


def _classification(assignment_type: str) -> PathClassification:
    return PathClassification(
        pathway_type="eu_free_movement",
        corridor="FR→DE",
        assignment_type=assignment_type,
    )


def _longterm_step_count(roadmap: dict) -> int:
    n = 0
    for step in roadmap.get("steps") or []:
        blob = f"{step.get('title') or ''} {step.get('description') or ''}"
        if _LONGTERM_RE.search(blob):
            n += 1
    return n


# --- Test 1: deterministic prompt-threading guard --------------------------

class _CapturingClient:
    """Stand-in LLM client that records the user_message it was handed and
    returns a minimal valid `emit_case_roadmap` tool result. Mirrors MockClient's
    tool-use response shape: keys text / tool_use / model / stop_reason / usage
    (generate() reads tool_use first)."""

    name = "capturing"

    def __init__(self) -> None:
        self.captured_user_message: str | None = None

    def complete(self, req):  # noqa: ANN001 - matches LlmClient.complete
        self.captured_user_message = req.user_message
        roadmap = {
            "result": "OK",
            "corridor": "FR→DE",
            "pathway_type": "eu_free_movement",
            "refusal_reason": None,
            "summary": "Register your address and start work as an EU national.",
            "steps": [
                {
                    "order": 1,
                    "title": "Register your address (Anmeldung)",
                    "description": "Register at the local Bürgeramt within two weeks.",
                    "source_url": "https://www.make-it-in-germany.com/en/visa-residence/eu-citizens",
                    "source_chunk_id": "fr-de-eea-entry-01",
                    "confidence": "high",
                    "requires_expert_review": False,
                }
            ],
        }
        return {
            "text": json.dumps(roadmap),
            "tool_use": roadmap,
            "model": req.model,
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 10, "output_tokens": 10},
        }


@pytest.mark.parametrize("assignment_type", ["STA", "LTA"])
def test_generate_threads_assignment_type_into_prompt(assignment_type):
    """generate() must render assignment_type into the prompt's SUBJECT block
    (`_build_context_message` emits `assignment_type={... or 'LTA'}`)."""
    client = _CapturingClient()
    result = roadmap_generator.generate(
        profile=_PROFILE,
        classification=_classification(assignment_type),
        chunks=_FR_DE_CHUNKS,
        client=client,
    )
    assert result.called_llm is True
    assert client.captured_user_message is not None
    assert f"assignment_type={assignment_type}" in client.captured_user_message, (
        f"expected 'assignment_type={assignment_type}' in the generator prompt SUBJECT "
        f"block, got:\n{client.captured_user_message}"
    )


# --- Test 2: opt-in live differential (the real quality eval) --------------

@pytest.mark.policy_assistant_audit
def test_live_lta_roadmap_has_more_longterm_steps_than_sta(monkeypatch):
    """Same corridor + chunks, STA vs LTA → the LTA roadmap should include
    STRICTLY MORE long-term steps (permanent residence / school / long-term
    housing) than the STA roadmap. Live call; skips cleanly without a key."""
    forced = (os.environ.get("POLICY_ASSISTANT_LLM") or "").strip().lower()
    if not os.environ.get("ANTHROPIC_API_KEY") and forced != "anthropic":
        pytest.skip("live STA-vs-LTA eval needs ANTHROPIC_API_KEY (or POLICY_ASSISTANT_LLM=anthropic)")

    # Force the live Anthropic client for get_default_client().
    monkeypatch.setenv("POLICY_ASSISTANT_LLM", "anthropic")

    sta = roadmap_generator.generate(
        profile=_PROFILE, classification=_classification("STA"), chunks=_FR_DE_CHUNKS
    )
    lta = roadmap_generator.generate(
        profile=_PROFILE, classification=_classification("LTA"), chunks=_FR_DE_CHUNKS
    )

    assert sta.roadmap.get("result") == "OK", f"STA generation refused: {sta.roadmap}"
    assert lta.roadmap.get("result") == "OK", f"LTA generation refused: {lta.roadmap}"

    sta_longterm = _longterm_step_count(sta.roadmap)
    lta_longterm = _longterm_step_count(lta.roadmap)

    assert lta_longterm >= 1, (
        "LTA roadmap should surface at least one long-term step "
        f"(permanent residence / school / long-term housing); got {lta_longterm}.\n"
        f"LTA steps: {[s.get('title') for s in lta.roadmap.get('steps') or []]}"
    )
    assert sta_longterm < lta_longterm, (
        "assignment_type did not differentiate the roadmap: expected the LTA roadmap to "
        f"include MORE long-term steps than STA, got STA={sta_longterm} LTA={lta_longterm}.\n"
        f"STA steps: {[s.get('title') for s in sta.roadmap.get('steps') or []]}\n"
        f"LTA steps: {[s.get('title') for s in lta.roadmap.get('steps') or []]}"
    )
