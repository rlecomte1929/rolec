"""AIQ-1488 — guards that claude-sonnet-5 is fully wired (priced) and that its
activation is ENV-GATED: the merge-time default stays claude-sonnet-4-6, and the
model only switches when RELOPASS_LLM_ASSISTANT_MODEL is set.

No live API call — this checks wiring only, so it runs without ANTHROPIC_API_KEY.
"""
import importlib
import os
from pathlib import Path

import yaml

from backend.app.services import policy_assistant_llm_client as pac


def test_sonnet5_priced_in_client():
    """estimate_cost_usd must resolve a non-zero cost for sonnet-5 (else the audit
    log silently records $0 for every sonnet-5 call)."""
    cost = pac.estimate_cost_usd(
        {"input_tokens": 1_000_000, "output_tokens": 1_000_000}, "claude-sonnet-5"
    )
    # Intro pricing: $2 input + $10 output per 1M.
    assert cost == 12.00, cost


def test_sonnet5_priced_in_costs_yaml():
    """The router cost table must know sonnet-5 (else a route/env flip to it raises
    LLMRoutingError on the missing price)."""
    costs_path = Path(__import__("backend.relopass.llm", fromlist=["_"]).__file__).parent / "costs.yaml"
    costs = yaml.safe_load(costs_path.read_text())
    assert "claude-sonnet-5" in costs, "claude-sonnet-5 missing from costs.yaml"
    assert costs["claude-sonnet-5"]["in_per_million"] == 2.00
    assert costs["claude-sonnet-5"]["out_per_million"] == 10.00


def test_default_stays_sonnet46_without_env():
    """Env-gated: with no override, the merge-time default is UNCHANGED — so prod
    behaviour and the sonnet-4-6 test suite are untouched by this task."""
    prev = os.environ.pop("RELOPASS_LLM_ASSISTANT_MODEL", None)
    try:
        reloaded = importlib.reload(pac)
        assert reloaded.DEFAULT_MODEL == "claude-sonnet-4-6"
    finally:
        if prev is not None:
            os.environ["RELOPASS_LLM_ASSISTANT_MODEL"] = prev
        importlib.reload(pac)  # restore module to ambient env


def test_env_gate_activates_sonnet5():
    """Setting the env var flips the assistant/roadmap default to sonnet-5."""
    prev = os.environ.get("RELOPASS_LLM_ASSISTANT_MODEL")
    os.environ["RELOPASS_LLM_ASSISTANT_MODEL"] = "claude-sonnet-5"
    try:
        reloaded = importlib.reload(pac)
        assert reloaded.DEFAULT_MODEL == "claude-sonnet-5"
    finally:
        if prev is None:
            os.environ.pop("RELOPASS_LLM_ASSISTANT_MODEL", None)
        else:
            os.environ["RELOPASS_LLM_ASSISTANT_MODEL"] = prev
        importlib.reload(pac)  # restore module to ambient env
