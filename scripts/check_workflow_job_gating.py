#!/usr/bin/env python3
"""Fail when a job's explicit `if:` can be silently overridden by a skipped dependency.

WHY THIS EXISTS
---------------
GitHub Actions skips a job whose `needs:` includes a job that was **skipped**, and it does so
*before* evaluating that job's own `if:`. A status function (`always()`, `!cancelled()`,
`success()`, `failure()`) is the only thing that breaks the propagation. So a job written as

    needs: [changes, fast-gate]
    if: needs.changes.outputs.frontend == 'true'

does not mean what it reads as. It means "…and also every needed job ran". When an upstream
job is skipped, this job is skipped too — silently, and **reported green**, because `skipped`
and `success` are indistinguishable in `gh pr checks`.

That is not hypothetical. #2062 (2026-08-23) added `fast-gate`, an aggregator carrying
`if: always()` so it survives its own path-filtered dependencies being skipped. It succeeded
as designed — but the five expensive jobs behind it carried exactly the bare `if:` above, so
the skip propagated past it to them. Measured: **Frontend (build/types/lint/unit), E2E,
Lighthouse and both backend suites ran ZERO times across 25 consecutive CI runs**, for five
days, while every PR reported green. Eleven PRs merged in that window without CI ever
building or testing them. #2076 fixed the five jobs; this script is what stops the sixth from
reintroducing it.

The lesson had already been learned once for cron gates —
`docs/findings/AIQ-2012-cron-gates-never-set.md` §2, *"a skipped cron is indistinguishable
from a working one"* — and survived only as prose. Prose does not gate a pull request.

WHAT IS AND IS NOT A VIOLATION
------------------------------
Flagged: a job that (a) `needs:` at least one job which carries its own `if:` — i.e. an
upstream that CAN be skipped — and (b) has an explicit `if:` of its own containing no status
function. Both halves are required, because both are required to produce the bug.

NOT flagged, deliberately:

  * A job with `needs:` and **no `if:` at all**. Its gating is GitHub's implicit `success()`,
    the author expressed no condition of their own, and skipping with a skipped parent is the
    intended behaviour of a dependency chain.
  * A job needing only unconditional jobs (today: `changes`, which has no `if:`). Nothing can
    skip, so nothing can propagate. This is why the ~17 guards gated on `changes` alone are
    not violations — but note it is a property of `changes`, not of those jobs: give `changes`
    an `if:`, or interpose another aggregator, and every one of them becomes one. This script
    is what notices.
  * A job with no `needs:`. Nothing upstream to propagate from.

There is deliberately NO allowlist. #2076 fixed every violator before this landed, so the
guard starts from zero, and an allowlist would grandfather precisely the case it exists to
catch. That reasoning is `check_no_vendored_deps.py`'s and `check_workflow_base_sha.py`'s.

Exit codes
----------
  0 — every gated job is safe (prints how many jobs across how many workflows it examined)
  1 — at least one job's `if:` can be silently overridden (file, job and line are printed)
  2 — the guard could not run: workflows dir missing, or a workflow failed to parse. An
      unparsed workflow hides whatever it contains, so that is never a silent pass.

USAGE
-----
  python scripts/check_workflow_job_gating.py [--root .]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only on a broken runner
    print("::error::PyYAML is required. Install it before running this guard.")
    raise SystemExit(2)

#: The functions that break skip-propagation. `success()` counts: writing it is an explicit
#: statement about upstream status, which is the decision this guard wants authors to make.
_STATUS_FN = re.compile(r"\b(?:always|cancelled|success|failure)\s*\(\s*\)")

_SAMPLE = 8


def _needs_list(job: Dict[str, Any]) -> List[str]:
    needs = job.get("needs")
    if needs is None:
        return []
    if isinstance(needs, str):
        return [needs]
    if isinstance(needs, list):
        return [n for n in needs if isinstance(n, str)]
    return []


def _line_of(path: Path, job_id: str) -> int:
    """Best-effort line number for a job key, for a clickable path:line in the output."""
    pattern = re.compile(rf"^  {re.escape(job_id)}\s*:\s*$")
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if pattern.match(line):
            return lineno
    return 1


def scan(workflows: Path) -> Tuple[List[Tuple[Path, str, int, List[str]]], int, int]:
    """Return (violations, jobs_examined, workflows_examined)."""
    violations: List[Tuple[Path, str, int, List[str]]] = []
    jobs_examined = 0
    files = sorted(workflows.glob("*.yml")) + sorted(workflows.glob("*.yaml"))

    for path in files:
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            print(f"::error::{path.name} failed to parse; the guard cannot see its jobs: {exc}")
            raise SystemExit(2)

        jobs = (doc or {}).get("jobs") or {}
        if not isinstance(jobs, dict):
            continue

        # A job is "skippable" when it carries its own `if:` — that is what lets it be
        # skipped while the run still proceeds, which is what propagates to its dependents.
        skippable = {jid for jid, j in jobs.items() if isinstance(j, dict) and "if" in j}

        for job_id, job in jobs.items():
            if not isinstance(job, dict):
                continue
            jobs_examined += 1

            own_if = job.get("if")
            if own_if is None:
                continue  # implicit success() — see the docstring
            risky = [n for n in _needs_list(job) if n in skippable]
            if not risky:
                continue
            if _STATUS_FN.search(str(own_if)):
                continue
            violations.append((path, job_id, _line_of(path, job_id), risky))

    return violations, jobs_examined, len(files)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".", help="repository root (default: .)")
    args = parser.parse_args(argv)

    workflows = Path(args.root).resolve() / ".github" / "workflows"
    if not workflows.is_dir():
        print(f"::error::{workflows} does not exist - the guard cannot have run.")
        return 2

    violations, jobs_examined, files_examined = scan(workflows)

    if jobs_examined == 0:
        print(
            "::error::check_workflow_job_gating examined 0 jobs. "
            "'No unsafe gating' is not a pass here - it means the scan found nothing to read."
        )
        return 1

    if violations:
        print(
            f"::error::{len(violations)} job(s) have an explicit `if:` that a skipped "
            f"dependency can silently override - they will be SKIPPED and still report green."
        )
        for path, job_id, lineno, risky in violations[:_SAMPLE]:
            print(f"    .github/workflows/{path.name}:{lineno}  job '{job_id}'")
            print(f"        needs (skippable): {', '.join(risky)}")
        if len(violations) > _SAMPLE:
            print(f"    … and {len(violations) - _SAMPLE} more")
        print(
            "\nTo fix: add a status function to the job's `if:` so the skip cannot propagate,\n"
            "and keep an explicit result check so the gate still does its job. e.g.\n"
            "    if: ${{ !cancelled() && needs.<gate>.result == 'success' && <your condition> }}\n"
            "\nDo NOT add an allowlist to this script - see its module docstring."
        )
        return 1

    print(
        f"check_workflow_job_gating: OK - {jobs_examined} job(s) across "
        f"{files_examined} workflow(s) examined; every `if:` gated on a skippable "
        f"dependency carries a status function."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
