#!/usr/bin/env python3
"""Turn perf-harness output into a verdict the perf-budget workflow can act on.

This used to be forty lines of Python inlined in `.github/workflows/perf-budget.yml`, which
made it the one piece of the gate nobody could test. It is a file now because the gate needs
to answer a question that has a wrong answer — *is this a regression, or was the box asleep?*
— and a guard that cannot be tested is how you end up with a green check that checks nothing.

**The problem it solves.** `rolec-eu` runs on Render's `free` plan and spins down after ~15
minutes idle. A free instance is not slow for one request after waking, it is slow for a
while: cold imports, an unfilled connection pool, cold query plans. The harness discards
exactly ONE request per endpoint as `cold`, so boot slowness leaked into the "warm" numbers
the budget asserts on. The result was a gate that failed 5 times in the 8 runs to 2026-08-21
and was therefore ignored — while a genuine regression sat inside that noise, unnoticed
(`/api/employee/assignments/overview`, over ceiling even when warm).

**Two rules, both about not crying wolf:**

1. `--was-asleep` demotes every regression breach to a warning. If the instance had to be
   woken, the numbers describe Render's free tier, not our code, and saying "regression" would
   be a false statement about the diff.
2. `--confirm` requires a breach to appear in BOTH measurements. One slow pass on a shared
   free instance is weather; twice in a row is a trend. Confirming inside the same run rather
   than across runs matters: this workflow is on a 3x/day cron, so cross-run confirmation
   would leave a real regression amber for up to eight hours.

A login failure is never softened by either rule — an outage is an outage whatever the box was
doing a minute ago.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Dict, List, Tuple

Breach = Tuple[str, str]  # (endpoint name, human description)


def _breaches(data: dict, reg_p95: float, reg_max: float,
              strict_p95: float, strict_max: float) -> Tuple[List[Breach], List[str], List[str]]:
    """(regression breaches, aspirational warnings, outages) for one harness run."""
    regressions: List[Breach] = []
    warnings: List[str] = []
    outages: List[str] = []

    for persona, block in (data.get("personas") or {}).items():
        if not block.get("logged_in"):
            outages.append(
                f"{persona}: login FAILED ({block.get('identifier')}) — outage or cred drift"
            )
            continue
        for ep in block.get("endpoints") or []:
            name = f"{persona} {ep['endpoint']}"
            warm = ep.get("warm")
            if not warm:
                # No warm 2xx samples. Could be a tight rate limit on that route rather than
                # latency, so it is surfaced and never failed on.
                warnings.append(
                    f"{name}: no warm 2xx samples "
                    f"(statuses={ep.get('statuses')}, rl={ep.get('rate_limited')})"
                )
                continue
            p95, mx = warm["p95_ms"], warm["max_ms"]
            if p95 > strict_p95 or mx > strict_max:
                warnings.append(
                    f"{name}: p95={p95}ms max={mx}ms over aspirational "
                    f"{strict_p95:.0f}/{strict_max:.0f}"
                )
            if p95 > reg_p95:
                regressions.append((name, f"{name}: p95 {p95}ms > regression ceiling {reg_p95:.0f}ms"))
            if mx > reg_max:
                regressions.append((name, f"{name}: max {mx}ms > regression ceiling {reg_max:.0f}ms"))
    return regressions, warnings, outages


def verdict(first: dict, confirm: dict | None, *, was_asleep: bool,
            reg_p95: float, reg_max: float,
            strict_p95: float, strict_max: float) -> Tuple[List[str], List[str], bool]:
    """(errors, warnings, breached) — `breached` is "pass 1 saw something", not "fail"."""
    regressions, warnings, outages = _breaches(first, reg_p95, reg_max, strict_p95, strict_max)
    errors: List[str] = list(outages)          # an outage is never softened
    breached = bool(regressions)

    if not regressions:
        return errors, warnings, breached

    if was_asleep:
        warnings += [
            f"INFRASTRUCTURE (instance was asleep, not a code regression): {d}"
            for _, d in regressions
        ]
        return errors, warnings, breached

    if confirm is None:
        errors += [d for _, d in regressions]
        return errors, warnings, breached

    # Confirmed = the same endpoint breached in both measurements.
    again = {n for n, _ in _breaches(confirm, reg_p95, reg_max, strict_p95, strict_max)[0]}
    for name, desc in regressions:
        if name in again:
            errors.append(f"CONFIRMED on re-measure: {desc}")
        else:
            warnings.append(f"TRANSIENT (did not reproduce on re-measure): {desc}")
    return errors, warnings, breached


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("perf", help="harness JSON from the first measurement")
    ap.add_argument("--confirm", help="harness JSON from a second measurement")
    ap.add_argument("--was-asleep", action="store_true",
                    help="the warm-up had to wake a spun-down instance")
    ap.add_argument("--regression-p95", type=float, default=3000.0)
    ap.add_argument("--regression-max", type=float, default=5000.0)
    ap.add_argument("--strict-p95", type=float, default=2000.0)
    ap.add_argument("--strict-max", type=float, default=3000.0)
    ap.add_argument("--github-output", help="file to append breached=<bool> to")
    args = ap.parse_args()

    with open(args.perf) as f:
        first = json.load(f)
    confirm = None
    if args.confirm:
        with open(args.confirm) as f:
            confirm = json.load(f)

    errors, warnings, breached = verdict(
        first, confirm, was_asleep=args.was_asleep,
        reg_p95=args.regression_p95, reg_max=args.regression_max,
        strict_p95=args.strict_p95, strict_max=args.strict_max,
    )

    for w in warnings:
        print(f"::warning::{w}")
    for e in errors:
        print(f"::error::{e}")

    if args.github_output:
        with open(args.github_output, "a") as f:
            f.write(f"breached={'true' if breached else 'false'}\n")

    print(f"\nSummary: {len(warnings)} warning(s), {len(errors)} failure(s)."
          f"  was_asleep={args.was_asleep}  confirmed_pass={confirm is not None}")
    print(f"Aspirational p95<={args.strict_p95:.0f} max<={args.strict_max:.0f}; "
          f"regression ceiling p95<={args.regression_p95:.0f} max<={args.regression_max:.0f}.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
