#!/usr/bin/env python3
"""AIQ-1414 — coordinator prompt-size & cost measurement.

Assembles the REAL coordinator prompt (`coordinator_agent._render`) over synthetic case
contexts of growing size and reports per-turn tokens + cost, projected per-relocation, and
asserts the Option-B **boundedness** property: per-turn input stays ~flat as a relocation
accrues events/turns (because the context builder caps events and the summary is folded).

Modes (auto-selected):
  • REAL   — when ANTHROPIC_API_KEY is set: runs a bounded set of real completions via the
             shared masking client; usage tokens are the model's real counts.
  • ESTIMATE — otherwise: char/4 token estimate (so this runs keyless / in CI).

Run:  python scripts/measure_coordinator_cost.py
Never prints the key. Real mode is capped at a handful of calls (~$0.25).
"""
from __future__ import annotations

import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from backend.app.services import coordinator_agent as agent  # noqa: E402
from backend.app.services.pii_masker import mask_pii  # noqa: E402
from backend.relopass.llm.router import usd_cost  # noqa: E402

MODEL = agent._REASONING_MODEL  # claude-sonnet-4-6
TURNS_PER_RELOCATION = 50
DESIGN_TARGET_USD = 1.20  # from the design cost model
_REAL = bool(os.environ.get("ANTHROPIC_API_KEY"))


def _synthetic_ctx(n_events: int, summary_chars: int) -> tuple[dict, dict]:
    """A masked, builder-shaped context with `n_events` recent events (the builder caps at
    30, so this reflects the real ceiling) and a rolling summary of `summary_chars`."""
    # The context builder caps recent_events at _MAX_EVENTS regardless of relocation age;
    # a mature relocation with hundreds of events still surfaces at most this many.
    events = [
        {"kind": "event", "at": f"2026-07-{(i % 27) + 1:02d}T00:00:00+00:00",
         "type": "milestone_update", "actor": "system",
         "description": f"Milestone {i} moved to in_progress.", "payload": {}}
        for i in range(n_events)
    ]
    ctx = {
        "case": {"case_id": "c-1", "company_id": "acme", "case_type": "long_term",
                 "origin_country": "FR", "destination_country": "DE",
                 "created_at": "2026-05-01T00:00:00+00:00", "updated_at": "2026-07-04T00:00:00+00:00",
                 "details": {"note": "relocation in progress"}},
        "people": [{"role": "assignee", "details": {"level": "senior"}}],
        "documents": [{"status": "verified", "key": "passport", "details": {}},
                      {"status": "pending", "key": "visa", "details": {}}],
        "requirements": [{"code": "VISA-001", "status": "missing", "reason": ""},
                         {"code": "HOUSE-002", "status": "in_progress", "reason": ""}],
        "recent_events": events,
    }
    session = {"rolling_summary": "S" * summary_chars,
               "recent_turns": [{"user": "prior q", "assistant": "prior a"} for _ in range(4)]}
    return ctx, session


def _measure(system: str, user: str) -> tuple[int, int]:
    """Return (input_tokens, output_tokens) — real when a key is present, else char/4."""
    if _REAL:
        from backend.app.services.policy_assistant_llm_client import LlmRequest, get_default_client
        r = get_default_client().complete(
            LlmRequest(system=system, user_message=user, model=MODEL, max_tokens=200)
        )
        u = r.get("usage") or {}
        return int(u.get("input_tokens", 0) or 0), int(u.get("output_tokens", 0) or 0)
    return (len(system) + len(user)) // 4, 200


def main() -> int:
    msg = "Reach me at sarah.chen@acme.com / +33 6 12 34 56 78 — what's my next visa step?"
    masked = mask_pii(msg)
    # boundedness assert: the raw PII must never be in the assembled prompt
    assert "sarah.chen@acme.com" not in masked and "+33 6 12 34 56 78" not in masked

    # fresh → mature → EXTREME: the extreme case (a 6-month relocation with hundreds of
    # events) is the boundedness proof — it must stay ~capped, not grow with history.
    scenarios = [("fresh (0 events, short summary)", 0, 0),
                 ("mature (30 events, 800-char summary)", 30, 800),
                 ("EXTREME (500 events, 800-char summary)", 500, 800)]

    print(f"\nCoordinator cost measurement — mode={'REAL (live LLM)' if _REAL else 'ESTIMATE (char/4)'} · model={MODEL}")
    print(f"{'scenario':<40} {'in_tok':>7} {'out_tok':>7} {'$/turn':>9} {'$/reloc(x50)':>13}")
    print("-" * 80)
    per_turn = []
    for name, n_events, summ in scenarios:
        ctx, session = _synthetic_ctx(n_events, summ)
        user = agent._render(ctx, session, masked)
        t_in, t_out = _measure(agent._SYSTEM, user)
        cost = usd_cost(MODEL, t_in, t_out)
        per_turn.append((t_in, cost))
        print(f"{name:<40} {t_in:>7} {t_out:>7} {cost:>9.5f} {cost * TURNS_PER_RELOCATION:>13.2f}")

    in_mature, in_extreme = per_turn[1][0], per_turn[2][0]
    reloc_extreme = per_turn[2][1] * TURNS_PER_RELOCATION
    _INPUT_CAP = 4000  # absolute per-turn input ceiling (state JSON capped at 8000 chars + system + summary)
    print("-" * 80)
    print(f"boundedness: EXTREME (500 events) input {in_extreme} tok vs mature (30) {in_mature} tok "
          f"(ratio {in_extreme / max(in_mature, 1):.2f}x) — 16x the events, prompt stays capped")
    print(f"per-relocation @ EXTREME ≈ ${reloc_extreme:.2f}  (design target ≈ ${DESIGN_TARGET_USD:.2f})")

    fails = []
    # THE property: the extreme case stays under an absolute per-turn cap (O(constant), not
    # O(relocation age)) — and 16x more events barely grows the prompt.
    if in_extreme > _INPUT_CAP:
        fails.append(f"input NOT bounded: EXTREME {in_extreme} tok > cap {_INPUT_CAP}")
    if in_extreme > in_mature * 2:
        fails.append(f"prompt grew with history: EXTREME {in_extreme} > 2x mature {in_mature}")
    if not (0 < reloc_extreme < 5.0):
        fails.append(f"per-relocation ${reloc_extreme:.2f} outside expected [0, 5) range")

    if fails:
        print("\nFAIL:\n  - " + "\n  - ".join(fails))
        return 1
    print("\nPASS — prompt bounded + per-relocation cost in range; PII masked before egress.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
