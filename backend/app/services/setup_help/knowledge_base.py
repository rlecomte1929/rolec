"""Loader + prompt renderer for the Setup & Help Assistant knowledge base.

The corpus lives in ``knowledge/setup_guide.json`` as a list of topics, each:

    {
      "id": str,                 # stable, unique
      "title": str,
      "applies_when": str|None,  # optional state hint
      "route": str|None,         # real in-app deep-link, or null
      "steps": [str, ...],
      "gotchas": [str, ...]
    }

``render_for_prompt`` produces a compact text block sized for a prompt-cached
system prompt (targeting well under ~5k tokens).
"""
from __future__ import annotations

import functools
import json
import os
from typing import Any

_GUIDE_PATH = os.path.join(os.path.dirname(__file__), "knowledge", "setup_guide.json")


@functools.lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    with open(_GUIDE_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def load_setup_guide() -> list[dict]:
    """Return the list of topic dicts from the knowledge base."""
    return list(_load_raw().get("topics", []))


def topic_ids() -> set[str]:
    """Set of stable topic ids (used for grounding / citation checks)."""
    return {t["id"] for t in load_setup_guide()}


def all_routes() -> set[str]:
    """Every non-null route cited by the corpus.

    Used by a later 'no hallucinated route' guard that checks the assistant only
    deep-links to routes the product actually has.
    """
    return {t["route"] for t in load_setup_guide() if t.get("route")}


def render_for_prompt() -> str:
    """Render the corpus as a compact text block for the system prompt."""
    data = _load_raw()
    lines: list[str] = [
        "# ReloPass Setup & Help Guide (HR)",
        (
            "Ground every answer ONLY in the topics below. Do not invent features, "
            "steps, or routes. If something isn't covered here, say so."
        ),
        "",
    ]
    for t in data.get("topics", []):
        lines.append(f"## [{t['id']}] {t['title']}")
        if t.get("applies_when"):
            lines.append(f"When: {t['applies_when']}")
        route = t.get("route")
        lines.append(f"Open: {route}" if route else "Open: (no direct HR link)")
        for i, step in enumerate(t.get("steps", []), 1):
            lines.append(f"{i}. {step}")
        for g in t.get("gotchas", []):
            lines.append(f"- Note: {g}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
