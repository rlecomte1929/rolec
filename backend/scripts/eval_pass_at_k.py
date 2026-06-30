"""
pass@k / pass^k stability harness.

Runs a zero-argument callable ``n`` times on a fixed input and reports how stable and
how correct its outputs are:

  - ``stability``   — fraction of runs whose (stringified) output equals the modal
                      output. 1.0 means every run produced the same answer.
  - ``unique_outputs`` — number of distinct outputs observed.
  - ``pass_rate``   — fraction of runs whose output satisfies the pass predicate.
  - ``pass_at_k``   — 1.0 if AT LEAST ONE of the n runs passes (does k samples contain
                      a correct answer?), else 0.0.
  - ``pass_pow_k``  — (pass^k) 1.0 only if ALL n runs pass (every sample correct).

For a DETERMINISTIC callable, stability and (given a correct expected value) pass_at_k
and pass_pow_k are all 1.0 — there is no variance to measure. The harness exists so a
STOCHASTIC stage (an LLM regime classifier, a sampled roadmap generator) can be dropped
in as the callable to quantify run-to-run agreement and correctness across temperatures.

The built-in ``--demo`` runs the deterministic ``ImmigrationRegimeRouter`` so the harness
is verifiable offline with no LLM and shows stability == 1.0.

Usage
─────
    python backend/scripts/eval_pass_at_k.py --n 5            # human-readable
    python backend/scripts/eval_pass_at_k.py --n 5 --json     # machine-readable

Plugging in a stochastic stage (in code)::

    from backend.scripts.eval_pass_at_k import run_pass_at_k
    report = run_pass_at_k(
        callable_=lambda: my_llm_classify(profile),   # non-deterministic
        n=20,
        expected="ELIGIBLE_L1B_INTRACOMPANY",
    )
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from typing import Any, Callable, Optional

# Allow running as a bare script (python backend/scripts/eval_pass_at_k.py) as well
# as a module — put the repo root on sys.path so `backend.*` imports resolve.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def run_pass_at_k(
    callable_: Callable[[], Any],
    n: int,
    expected: Optional[Any] = None,
    predicate: Optional[Callable[[Any], bool]] = None,
) -> dict:
    """Run ``callable_`` n times and report stability + pass@k / pass^k.

    Exactly one of ``expected`` (equality check) or ``predicate`` (custom check)
    drives the pass decision. If neither is given, only stability is meaningful and
    every run is treated as a pass.
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    if predicate is None:
        if expected is not None:
            predicate = lambda out: out == expected
        else:
            predicate = lambda out: True

    outputs = [callable_() for _ in range(n)]
    keys = [json.dumps(o, sort_keys=True, default=str) for o in outputs]
    counts = Counter(keys)
    modal_count = counts.most_common(1)[0][1]

    n_pass = sum(1 for o in outputs if predicate(o))

    return {
        "n": n,
        "unique_outputs": len(counts),
        "stability": round(modal_count / n, 4),
        "pass_rate": round(n_pass / n, 4),
        "pass_at_k": 1.0 if n_pass >= 1 else 0.0,
        "pass_pow_k": 1.0 if n_pass == n else 0.0,
        "modal_output": json.loads(counts.most_common(1)[0][0]),
    }


def _demo_callable() -> str:
    """Deterministic demo: the immigration regime router for a fixed US L1B profile."""
    from backend.app.services.immigration_regime import ImmigrationRegimeRouter

    result = ImmigrationRegimeRouter().detect_regime(
        nationality="Germany",
        destination_country="United States",
        origin_country="Germany",
        contract_type="lta",
    )
    return result.regime_id


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="pass@k / pass^k stability harness.")
    parser.add_argument("--n", type=int, default=5, help="Number of runs (default 5).")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args(argv)

    report = run_pass_at_k(_demo_callable, n=args.n, expected="us_l1b")
    report["demo"] = "ImmigrationRegimeRouter (deterministic) — Germany→US LTA, expected us_l1b"

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"pass@k stability harness — demo: {report['demo']}")
        print(f"  runs (n)        : {report['n']}")
        print(f"  unique outputs  : {report['unique_outputs']}")
        print(f"  stability       : {report['stability']}  (1.0 = all runs agree)")
        print(f"  pass_rate       : {report['pass_rate']}")
        print(f"  pass@k          : {report['pass_at_k']}  (>=1 run correct)")
        print(f"  pass^k          : {report['pass_pow_k']}  (all runs correct)")
        print(f"  modal output    : {report['modal_output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
