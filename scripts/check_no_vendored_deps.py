#!/usr/bin/env python3
"""Fail when a dependency tree or build output is tracked by git.

WHY THIS EXISTS
---------------
`.gitignore` used to name build directories path by path — `frontend/node_modules`,
`frontend/dist/`. A rule that names one path does not protect any other, so an
`npm install` run anywhere else committed its entire dependency tree and nobody
noticed. Two did, and they sat on `main` for months:

  * apps/hr-dashboard/node_modules  — 15,635 files
  * design/templates/node_modules   —    383 files (a stray `npm i docx` in a
                                          directory that has no package.json)

plus a single stray `node_modules/.vite/vitest/<hash>/results.json` cache artefact
at the repo root. AIQ-1865 untracked all three and replaced the path-specific
ignore rules with unanchored ones. This script is what keeps them gone: the
ignore rule stops the *next* accidental `git add`, and this guard catches anything
that gets past it (`git add -f`, a rule edited away, a merge that resurrects a path).

There is deliberately NO allowlist. Every violator found when this was written was
removed in the same commit, so the guard starts from zero. An allowlist here would
grandfather the only cases it exists to catch, which makes a guard decoration
rather than a gate.

Exit codes
----------
  0 — no tracked dependency or build output
  1 — at least one tracked path matched (the offending paths are printed)
  2 — could not run `git ls-files`
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Directory names that must never appear as a path component of a tracked file.
FORBIDDEN_DIRS = ("node_modules", "dist")

# How many offending paths to print per directory before truncating. The point is
# to name the directory and prove it, not to page 15,000 lines through CI logs.
_SAMPLE = 5


def tracked_files(root: Path) -> list[str]:
    res = subprocess.run(
        ["git", "ls-files"], cwd=str(root), capture_output=True, text=True,
    )
    if res.returncode != 0:
        print(f"error: git ls-files failed: {res.stderr.strip()}", file=sys.stderr)
        raise SystemExit(2)
    return [line.strip() for line in res.stdout.splitlines() if line.strip()]


def violations(paths: list[str]) -> dict[str, list[str]]:
    """Map `<dir-prefix>` -> tracked paths beneath it, for each forbidden dir.

    Keyed on the prefix up to and including the forbidden component so that one
    vendored tree reports as one finding rather than thousands.
    """
    found: dict[str, list[str]] = {}
    for path in paths:
        parts = path.split("/")
        for i, part in enumerate(parts[:-1]):  # a FILE named dist is fine; a DIR is not
            if part in FORBIDDEN_DIRS:
                prefix = "/".join(parts[: i + 1])
                found.setdefault(prefix, []).append(path)
                break
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", default=".", help="Repo root to check (default: cwd)."
    )
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    found = violations(tracked_files(root))
    if not found:
        print("check_no_vendored_deps: OK — no tracked node_modules/ or dist/.")
        return 0

    total = sum(len(v) for v in found.values())
    print(
        f"::error::{total} tracked file(s) live under a dependency or build directory. "
        f"Dependency trees and build output must not be committed.\n"
    )
    for prefix in sorted(found):
        hits = found[prefix]
        print(f"  {prefix}/ — {len(hits)} tracked file(s)")
        for sample in hits[:_SAMPLE]:
            print(f"      {sample}")
        if len(hits) > _SAMPLE:
            print(f"      … and {len(hits) - _SAMPLE} more")
    print(
        "\nTo fix: `git rm -r --cached <dir>` and confirm .gitignore covers it.\n"
        "Do NOT add an allowlist to this script — see its module docstring."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
