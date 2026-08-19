"""Tolerant JSON extraction for beam pass output.

This module exists because of a specific dead run. Beam run ``beam:FR-NO:eea:msxf6rwlbjt3``
produced usable content and was thrown away on JSON parse failures — five paid model calls
lost to a formatting habit. Models wrap JSON in ```json fences whenever they feel
conversational, and ``response_format={"type":"json_object"}`` reduces that without
eliminating it: it is not offered by every model or every provider path, and a retry that
falls back can still fence.

The rule here is narrow on purpose: recover JSON that is *present but wrapped*, and refuse
anything else loudly. It never repairs malformed JSON — a "helpful" parser that guesses at
broken syntax would invent obligations, and this is the authoring path for content a
relocating person will act on. Better a failed pass, recorded as failed, than a silently
mangled one.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence

__all__ = ["ModelJsonError", "strip_code_fences", "parse_model_json", "extract_items"]


class ModelJsonError(ValueError):
    """Model output could not be read as JSON. Carries a snippet for the run record."""


# ```json … ```  /  ```JSON … ```  /  bare ``` … ```
_FENCE_RE = re.compile(
    r"```[ \t]*(?:json|javascript|js)?[ \t]*\r?\n(?P<body>.*?)```",
    re.IGNORECASE | re.DOTALL,
)


def strip_code_fences(text: str) -> str:
    """Return the largest fenced block, or the input unchanged when unfenced.

    Largest rather than first: a model that narrates ("here is a small example: ```json
    {...}``` and the full set: ```json [...]```") puts the payload in the bigger block.
    """
    if not text:
        return ""
    blocks = [m.group("body") for m in _FENCE_RE.finditer(text)]
    if not blocks:
        return text.strip()
    return max(blocks, key=len).strip()


def _first_balanced(text: str, opener: str, closer: str) -> Optional[str]:
    """The first balanced ``opener…closer`` span, ignoring brackets inside strings."""
    start = text.find(opener)
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def parse_model_json(text: str) -> Any:
    """Parse model output into JSON, tolerating fences and surrounding prose.

    Order of attempts — each strictly more permissive than the last, and each still a
    *real* parse, never a repair:

      1. the raw text
      2. the largest fenced block
      3. the first balanced ``[...]`` or ``{...}`` span, for output that opens with prose

    Raises :class:`ModelJsonError` with a snippet when all three fail.
    """
    if text is None or not str(text).strip():
        raise ModelJsonError("model returned empty output")

    raw = str(text)
    attempts = [raw.strip(), strip_code_fences(raw)]

    unfenced = attempts[-1]
    for opener, closer in (("[", "]"), ("{", "}")):
        span = _first_balanced(unfenced, opener, closer)
        if span:
            attempts.append(span)

    seen = set()
    for candidate in attempts:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            return json.loads(candidate)
        except (ValueError, TypeError):
            continue

    snippet = raw.strip().replace("\n", " ")[:200]
    raise ModelJsonError(f"no parseable JSON in model output; starts: {snippet!r}")


#: Keys a model plausibly uses when it wraps the list in an object. Ordered, so the
#: first present wins — matched against the *shape* below, never trusted blindly.
_LIST_KEYS: Sequence[str] = (
    "items",
    "requirements",
    "obligations",
    "candidates",
    "results",
    "data",
)


def extract_items(payload: Any) -> List[Dict[str, Any]]:
    """Normalise a parsed payload to the ordered list of item dicts.

    Accepts a bare array, or an object wrapping one under a familiar key. Preserves
    order exactly — arrival order is load-bearing input to the clustering, so this must
    never sort, dedupe or filter. Non-dict entries are dropped: they cannot be parsed
    into a Variant and carrying them would only shift ordinals.
    """
    if isinstance(payload, list):
        raw = payload
    elif isinstance(payload, dict):
        raw = None
        for key in _LIST_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                raw = value
                break
        if raw is None:
            # A single item returned unwrapped still looks like an item.
            if any(k in payload for k in ("title", "action_required")):
                raw = [payload]
            else:
                raise ModelJsonError(
                    f"parsed JSON object has no item list; keys: {sorted(payload)[:10]}"
                )
    else:
        raise ModelJsonError(f"parsed JSON is {type(payload).__name__}, expected list or object")

    return [item for item in raw if isinstance(item, dict)]
