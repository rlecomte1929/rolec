"""
Roadmap generator (P1-01d glue for the P1-01b prompt) — generation stage of
the immigration RAG pipeline.

Loads the generator system prompt (`prompts/roadmap_generator_v1.txt`, authored
in P1-01b), renders the retrieved chunks into the CONTEXT block, calls the LLM
through the shared policy_assistant seam (Sonnet, temperature=0), and parses the
`emit_case_roadmap` object the prompt instructs the model to produce.

An empty chunk set is the retriever-side basis for RULE_NOT_FOUND (P1-01a), so
we short-circuit to a refusal without spending an LLM call — the LLM is only
invoked when there is context to ground a roadmap in.

The prompt is authored for Anthropic tool-use; in the shared text seam the model
returns the `emit_case_roadmap` *input* object as JSON text, which we parse
tolerantly. Passing the tool schema to the live Anthropic API and reading the
tool_use block is a follow-up (see P1-01d execution notes); this keeps the
generator deterministic under MockClient and compatible with any JSON-returning
client.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .immigration_retriever import PathClassification, UserProfile, corridor_key
from .pii_masker import safe_log_text
from .policy_assistant_llm_client import (
    DEFAULT_MODEL,
    LlmClient,
    LlmRequest,
    get_default_client,
)

log = logging.getLogger(__name__)

RESULT_OK = "OK"
RESULT_RULE_NOT_FOUND = "RULE_NOT_FOUND"

_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "prompts", "roadmap_generator_v1.txt"
)
# A full citation-bound roadmap carries several steps, each with a source_url,
# key_actions, confidence and review flags — 1500 tokens truncated longer
# corridors mid-JSON, which surfaced as a "malformed roadmap JSON" refusal even
# though retrieval succeeded. Sonnet supports far more; 4096 fits a complete
# multi-step roadmap with headroom.
_GEN_MAX_TOKENS = 4096

_prompt_cache: Optional[str] = None


@dataclass(frozen=True)
class GenerationResult:
    """The generated roadmap plus the LLM metadata the pipeline needs for the
    audit trail. `called_llm` is False when generation short-circuited on an
    empty context (no tokens spent)."""

    roadmap: Dict[str, Any]
    model: str
    usage: Dict[str, int] = field(default_factory=dict)
    called_llm: bool = False


def load_prompt() -> str:
    """Read and cache the generator system prompt (P1-01b)."""
    global _prompt_cache
    if _prompt_cache is None:
        with open(os.path.abspath(_PROMPT_PATH), "r", encoding="utf-8") as f:
            _prompt_cache = f.read()
    return _prompt_cache


def generate(
    *,
    profile: UserProfile,
    classification: PathClassification,
    chunks: List[Dict[str, Any]],
    client: Optional[LlmClient] = None,
    model: Optional[str] = None,
) -> GenerationResult:
    """Generate a CaseRoadmap dict from the retrieved chunks, or refuse with
    RULE_NOT_FOUND when there is no context to ground it in."""
    corridor = classification.corridor or corridor_key(
        profile.origin_country, profile.destination_country
    )

    # Empty context → uncovered corridor → refuse without an LLM call.
    if not chunks:
        return GenerationResult(
            roadmap=_refusal(corridor, classification.pathway_type,
                             f"No retrieved immigration rules cover the {corridor} corridor."),
            model=model or DEFAULT_MODEL,
            called_llm=False,
        )

    client = client or get_default_client()
    resolved_model = model or DEFAULT_MODEL
    req = LlmRequest(
        system=load_prompt(),
        user_message=_build_context_message(profile, classification, chunks, corridor),
        model=resolved_model,
        temperature=0.0,
        max_tokens=_GEN_MAX_TOKENS,
    )
    resp = client.complete(req)
    roadmap = _parse_roadmap(
        resp.get("text") or "",
        corridor,
        classification.pathway_type,
        stop_reason=resp.get("stop_reason"),
    )
    return GenerationResult(
        roadmap=roadmap,
        model=resp.get("model") or resolved_model,
        usage=resp.get("usage") or {},
        called_llm=True,
    )


# --- Internals -------------------------------------------------------------

def _refusal(corridor: str, pathway_type: Optional[str], reason: str) -> Dict[str, Any]:
    return {
        "result": RESULT_RULE_NOT_FOUND,
        "corridor": corridor,
        "pathway_type": pathway_type,
        "refusal_reason": reason,
        "summary": None,
        "steps": [],
    }


def _build_context_message(
    profile: UserProfile,
    classification: PathClassification,
    chunks: List[Dict[str, Any]],
    corridor: str,
) -> str:
    """Render the SUBJECT + CONTEXT block the prompt's exemplars expect."""
    lines = [
        "SUBJECT:",
        f"  profile: nationality={profile.nationality}, origin={profile.origin_country}, "
        f"destination={profile.destination_country}, is_eea={str(profile.is_eea).lower()}",
        f"  classification: pathway_type={classification.pathway_type}, corridor={corridor}",
        "",
        "CONTEXT (retrieved chunks):",
    ]
    for c in chunks:
        url = c.get("source_url") or c.get("source_ref") or ""
        text = (c.get("chunk_text") or "").strip()
        lines.append(f"  [chunk:{c.get('id')}] (source_url: {url})\n    {text}")
    return "\n".join(lines)


def _extract_json_object(text: str) -> Optional[str]:
    """Return the first complete, balanced top-level JSON object in `text`.

    Tolerates the prose preamble/postamble and ```json code fences the model
    tends to wrap the object in when it follows the tool-use prompt through the
    plain-text seam. String-aware so braces inside JSON string values don't
    skew the depth count. Returns None when no *complete* object is present
    (e.g. the output was truncated before the closing brace)."""
    if not text:
        return None
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None  # unbalanced — truncated mid-object


def _parse_roadmap(
    text: str,
    corridor: str,
    pathway_type: Optional[str],
    stop_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Tolerantly parse the emit_case_roadmap object. On any malformation,
    refuse rather than surface a half-formed roadmap — but log the raw output
    (PII-safe) and the stop_reason so the failure is diagnosable rather than an
    opaque refusal."""
    candidate = _extract_json_object(text or "")
    if not candidate:
        # No complete object — the common cause is the model hitting the token
        # ceiling and being cut off mid-JSON (stop_reason == "max_tokens").
        truncated = stop_reason == "max_tokens"
        log.warning(
            "roadmap_generator: no complete JSON object for %s (stop_reason=%s) raw=%s",
            corridor, stop_reason, safe_log_text(text or "", max_len=400),
        )
        reason = (
            "Generator output was truncated at the token limit before completing the roadmap."
            if truncated
            else "Generator returned no parseable roadmap."
        )
        return _refusal(corridor, pathway_type, reason)
    try:
        obj = json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        log.warning(
            "roadmap_generator: unparseable generator JSON for %s (stop_reason=%s) raw=%s",
            corridor, stop_reason, safe_log_text(text or "", max_len=400),
        )
        return _refusal(corridor, pathway_type, "Generator returned malformed roadmap JSON.")
    if not isinstance(obj, dict) or obj.get("result") not in (RESULT_OK, RESULT_RULE_NOT_FOUND):
        return _refusal(corridor, pathway_type, "Generator returned an invalid roadmap shape.")

    obj.setdefault("corridor", corridor)
    obj.setdefault("pathway_type", pathway_type)
    obj.setdefault("refusal_reason", None)
    obj.setdefault("summary", None)
    steps = obj.get("steps")
    obj["steps"] = steps if isinstance(steps, list) else []
    # A RULE_NOT_FOUND roadmap never carries steps, by contract.
    if obj["result"] == RESULT_RULE_NOT_FOUND:
        obj["steps"] = []
    return obj
