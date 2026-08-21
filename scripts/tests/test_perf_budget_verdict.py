"""The perf gate's verdict logic, pinned to the incident that produced it.

On 2026-08-21 the gate had failed 5 of its last 8 runs and everyone had learned to ignore it.
The measured truth that day: five endpoints breached in CI, four of which came back warm and
fine (`hr/command-center/cases` 7939ms in CI vs 953ms warm), and one of which was real
(`employee/assignments/overview`, over ceiling even warm). These tests exist so the gate keeps
being able to tell those two apart.
"""
from __future__ import annotations

import sys
from pathlib import Path

# `scripts/` is not a package, so the sibling guards put the directory itself on the path and
# import by bare name. Matching that: `scripts.<mod>` resolved locally but not under CI's
# full-suite discovery (ModuleNotFoundError).
SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from perf_budget_verdict import verdict  # noqa: E402

CEILINGS = dict(reg_p95=3000.0, reg_max=5000.0, strict_p95=2000.0, strict_max=3000.0)


def _run(**endpoints):
    """A harness payload: endpoint -> warm p95 (max is pinned under its own ceiling)."""
    return {
        "personas": {
            "hr": {
                "logged_in": True,
                "endpoints": [
                    {"endpoint": ep, "warm": {"p95_ms": p95, "max_ms": min(p95, 4999.0)}}
                    for ep, p95 in endpoints.items()
                ],
            }
        }
    }


def test_a_warm_breach_confirmed_twice_fails():
    """The whole point: a real regression must still turn the gate red."""
    errors, _, breached = verdict(_run(slow=7000.0), _run(slow=7000.0),
                                  was_asleep=False, **CEILINGS)
    assert breached
    assert any("CONFIRMED" in e for e in errors)


def test_a_breach_that_does_not_reproduce_is_a_warning_not_a_failure():
    """`hr/command-center/cases`: 7939ms in CI, 953ms on re-measure. One pass is weather."""
    errors, warnings, breached = verdict(_run(flaky=7939.0), _run(flaky=953.0),
                                         was_asleep=False, **CEILINGS)
    assert breached                       # pass 1 did see it — we are not hiding that
    assert errors == []                   # but it is not a regression
    assert any("TRANSIENT" in w for w in warnings)


def test_waking_a_spun_down_instance_is_infrastructure_never_a_regression():
    """Render `free` spins down after ~15 min. Those numbers describe the plan, not the diff."""
    errors, warnings, _ = verdict(_run(slow=7939.0), None, was_asleep=True, **CEILINGS)
    assert errors == []
    assert any("INFRASTRUCTURE" in w for w in warnings)


def test_a_login_outage_fails_even_when_the_instance_was_asleep():
    """The one thing neither rule may soften — an outage is an outage."""
    data = {"personas": {"hr": {"logged_in": False, "identifier": "hr@testingapril.com"}}}
    errors, _, _ = verdict(data, None, was_asleep=True, **CEILINGS)
    assert any("login FAILED" in e for e in errors)


def test_a_healthy_warm_run_is_green_and_silent_about_regressions():
    """The June baseline is 0.6-2.8s warm; that must not trip anything."""
    errors, warnings, breached = verdict(_run(fast=953.0), None, was_asleep=False, **CEILINGS)
    assert errors == []
    assert not breached
    assert not any("regression ceiling" in w for w in warnings)


def test_an_endpoint_over_the_aspirational_bar_still_warns_while_green():
    """2982ms `employee/policy/caps` is under the 3s ceiling but over the 2s aspiration.

    It carries a known unfixed N+1 (`query_count=12`), so losing the trend signal would be a
    real loss — warn, do not fail.
    """
    errors, warnings, _ = verdict(_run(caps=2982.0), None, was_asleep=False, **CEILINGS)
    assert errors == []
    assert any("aspirational" in w for w in warnings)


def test_confirmation_is_per_endpoint_not_per_run():
    """A run where a DIFFERENT endpoint breaches second must not confirm the first.

    Confirming on "did pass 2 breach at all" would let two unrelated blips masquerade as one
    reproducible regression.
    """
    errors, warnings, _ = verdict(_run(a=7000.0), _run(b=7000.0), was_asleep=False, **CEILINGS)
    assert errors == []
    assert any("TRANSIENT" in w for w in warnings)
