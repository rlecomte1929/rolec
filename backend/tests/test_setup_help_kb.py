"""Tests for the Setup & Help Assistant knowledge base.

Guards accuracy (no invented routes), structural integrity, unique ids, and a
sane prompt-render size so the corpus stays prompt-cacheable.
"""
from __future__ import annotations

import os
import re

from backend.app.services.setup_help import (
    all_routes,
    load_setup_guide,
    render_for_prompt,
    topic_ids,
)

# ── Derive the set of REAL static app routes from the frontend nav registry ──
_ROUTES_TS = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "frontend", "src", "navigation", "routes.ts",
)


def _real_static_routes() -> set[str]:
    """Static (param-free) paths declared in frontend/src/navigation/routes.ts."""
    with open(os.path.abspath(_ROUTES_TS), encoding="utf-8") as fh:
        src = fh.read()
    paths = set(re.findall(r"path:\s*'([^']+)'", src))
    # Only param-free deep-links are valid citations for the KB.
    return {p for p in paths if ":" not in p}


def test_guide_loads_and_topics_well_formed():
    topics = load_setup_guide()
    assert isinstance(topics, list) and len(topics) >= 6
    for t in topics:
        assert t.get("id"), f"missing id: {t}"
        assert t.get("title"), f"missing title: {t['id']}"
        assert isinstance(t.get("steps"), list) and t["steps"], f"no steps: {t['id']}"
        assert all(isinstance(s, str) and s.strip() for s in t["steps"])
        # gotchas optional but must be a list of strings when present
        assert isinstance(t.get("gotchas", []), list)


def test_topic_ids_unique_and_match_helper():
    topics = load_setup_guide()
    ids = [t["id"] for t in topics]
    assert len(ids) == len(set(ids)), "duplicate topic ids"
    assert topic_ids() == set(ids)


def test_required_topics_present():
    ids = topic_ids()
    for required in {
        "company-profile",
        "policy-draft-publish",
        "create-first-case",
        "invite-employee",
        "employee-next-steps",
    }:
        assert required in ids, f"missing required topic: {required}"


def test_every_route_is_real_and_static():
    real = _real_static_routes()
    for t in load_setup_guide():
        route = t.get("route")
        if route is None:
            continue
        assert route.startswith("/"), f"{t['id']} route must start with /: {route!r}"
        assert route in real, f"{t['id']} cites non-existent route: {route!r}"
    # all_routes() must be a subset of the real static routes too
    assert all_routes() <= real


def test_render_for_prompt_nonempty_and_bounded():
    text = render_for_prompt()
    assert text.strip()
    # Every topic id must appear in the rendered block.
    for tid in topic_ids():
        assert tid in text
    # Keep it prompt-cacheable: ~4 chars/token, target well under ~5k tokens.
    assert len(text) < 20_000, f"rendered guide too large: {len(text)} chars"
