"""Autopilot Phase 3 — the Claude Code agent-lane task selector (cc_eligible + --cc-next)."""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(_REPO_ROOT, "scripts"))

import notion_ready_queue as nrq  # noqa: E402


def _task(tier, complexity):
    return {"aiq": "AIQ-1", "page_id": "pg", "title": "t", "url": "u",
            "autonomy_tier": tier, "complexity": complexity, "priority": "P2"}


def test_cc_eligible_green_medium():
    assert nrq.cc_eligible(_task("🟢 Green — auto", "Medium")) is True


def test_cc_eligible_yellow_high():
    assert nrq.cc_eligible(_task("🟡 Yellow — self-validate + sample", "High")) is True


def test_cc_rejects_red():
    assert nrq.cc_eligible(_task("🔴 Red — full human gate", "Medium")) is False


def test_cc_rejects_trivial_and_low():
    # Trivial/Low are the headless Haiku lane, not the agent lane.
    assert nrq.cc_eligible(_task("🟢 Green — auto", "Low")) is False
    assert nrq.cc_eligible(_task("🟢 Green — auto", "Trivial")) is False


def test_cc_rejects_very_high():
    # Very High → decomposition, not a single agent run.
    assert nrq.cc_eligible(_task("🟡 Yellow", "Very High")) is False


def test_cc_rejects_missing_tier():
    assert nrq.cc_eligible(_task("", "Medium")) is False
