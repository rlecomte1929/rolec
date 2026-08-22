#!/usr/bin/env python3
"""Fail when a workflow computes a diff range from `github.event.pull_request.base.sha`.

WHY THIS EXISTS
---------------
That field records the base tip when the PR was **opened**, and GitHub never refreshes it
as the base branch moves. `HEAD` in a `pull_request` run is the merge ref (base + PR), so a
three-dot diff from a stale SHA spans **every commit merged into main since the PR opened** —
and a job scoped that way fails a PR for somebody else's file.

This is not hypothetical and it is not a one-off:

  * #1906 removed exactly this from the migration guards, where it had blamed #1894 for a
    file that #1901 merged minutes earlier.
  * **One day later, #1971 reintroduced it** in a brand-new workflow (`otto-batches.yml`).
    Measured on that branch, 11 commits behind main: the stale base gated **3** import
    batches, two of which belonged to other people's already-merged PRs; the live merge-base
    gated **1**, its own.

The lesson survived in a code comment and nothing enforced it, so the next new workflow was
free to repeat it. That is what this script is for.

THE CORRECT FORM, already used by `ci.yml` and `otto-batches.yml`:

    git fetch --quiet origin main
    BASE_SHA=$(git merge-base origin/main HEAD || true)

WHAT IS AND IS NOT A VIOLATION
------------------------------
Only *diff-range* use is banned. Naming the field in a comment is how the lesson is
documented — `ci.yml` says "not github.event.pull_request.base.sha" three times, and
flagging its own explanation would make the guard unusable. So a line whose first
non-whitespace character is `#` is skipped, and the check is for the expression appearing
where it can reach a `git diff`: an `env:` binding or a `run:` body.

There is deliberately NO allowlist, for the reason `check_no_vendored_deps.py` gives: every
violator was fixed before this landed, so it starts from zero, and an allowlist would
grandfather the only case it exists to catch.

Exit codes
----------
  0 — no workflow computes a range from the stale base
  1 — at least one does (file and line are printed)
  2 — the workflows directory is missing (the guard cannot have run)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Tuple

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"

#: The stale field, in either the `${{ }}` expression form or a bare `github.event…` path.
_STALE = re.compile(r"github\.event\.pull_request\.base\.sha")

#: A line that only *mentions* the field in prose. `ci.yml` documents the rule in comments
#: and must not trip its own guard.
_COMMENT = re.compile(r"^\s*#")


def violations() -> List[Tuple[Path, int, str]]:
    found: List[Tuple[Path, int, str]] = []
    for path in sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _COMMENT.match(line):
                continue
            if _STALE.search(line):
                found.append((path, lineno, line.strip()))
    return found


def main() -> int:
    if not WORKFLOWS.is_dir():
        print(f"::error::{WORKFLOWS} does not exist — this guard did not run.", file=sys.stderr)
        return 2

    found = violations()
    if not found:
        print("check_workflow_base_sha: OK — no workflow derives a diff range from a stale base.")
        return 0

    print(
        f"::error::{len(found)} workflow line(s) use github.event.pull_request.base.sha. "
        "That SHA is frozen at PR-open time, so a diff from it spans every commit merged "
        "since — the job then fails a PR for another PR's files (#1906, reintroduced by #1971)."
    )
    print()
    for path, lineno, line in found:
        rel = path.relative_to(WORKFLOWS.parents[1])
        print(f"  {rel}:{lineno}")
        print(f"      {line}")
    print()
    print("Use the live base instead:")
    print("    git fetch --quiet origin main")
    print("    BASE_SHA=$(git merge-base origin/main HEAD || true)")
    print()
    print("Do NOT add an allowlist to this script — see its module docstring.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
