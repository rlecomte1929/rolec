#!/usr/bin/env python3
"""Fail a PR that adds a column AND reads it in application code.

WHY THIS EXISTS — an incident, 2026-08-11.

PR #1781 added `supabase/migrations/20261026000000_form_templates_sections.sql`
(`ADD COLUMN sections`) *and* `SELECT ft.sections AS template_sections` in
`backend/app/routers/cases_read.py`, in one PR. It merged, Render deployed, and
`GET /api/cases/{id}/forms` returned HTTP 500 for 2h33m with
`column ft.sections does not exist`.

Migrations in this repo are applied **out of band** (see CLAUDE.md, "Migration
discipline"). Merging a migration does not apply it. So shipping the column and the code
that reads it together *feels* atomic and is not — they travel through two different
pipelines, and the code always wins the race.

CI could not catch it: the backend suite runs against a SQLite fixture, and that PR
edited the fixture to add the column in the same commit. Green meant "the code agrees
with the fixture I just wrote", not "the code agrees with production."

THE RULE. Split it into two merges:
  1. the migration file alone;
  2. after an operator applies it and reconciles the ledger, the code that reads it.

Deliberately unconditional. It does not try to ask whether the migration has been
applied — that would need the read-only DB secret, which is absent on forks and most
PRs, and a guard that silently no-ops is worse than none. Two merges is cheap; a
production 500 is not.

Stdlib only: this runs in a dependency-free CI job.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from typing import Dict, List, Set, Tuple

# `ADD COLUMN [IF NOT EXISTS] <name>` — the quoted form too.
_ADD_COLUMN_RE = re.compile(
    r"\bADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"']?([a-zA-Z_][a-zA-Z0-9_]*)[\"']?",
    re.IGNORECASE,
)

# An escape hatch for the rare legitimate case, e.g. a column added and backfilled by
# code that is itself gated off. Must carry a reason.
_OVERRIDE_RE = re.compile(
    r"--\s*guard:\s*column-read-ok\s+(?P<reason>\S.*)$", re.IGNORECASE | re.MULTILINE
)

# Application-code suffixes. `.sql` is EXCLUDED on purpose: a migration that adds a
# column and then backfills it references that column by definition, and that is correct
# — the DDL and the backfill run in the same transaction.
_CODE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx")

# Paths that are not shipped application code.
_IGNORED_PREFIXES = ("backend/tests/", "frontend/src/**/__tests__/", "scripts/", "docs/")


def _sh(*args: str) -> str:
    return subprocess.run(
        args, capture_output=True, text=True, check=False
    ).stdout


def _changed_files(base: str) -> List[str]:
    out = _sh("git", "diff", "--diff-filter=ACMR", "--name-only", f"{base}...HEAD")
    return [line.strip() for line in out.splitlines() if line.strip()]


def _added_lines(base: str, path: str) -> List[str]:
    """Only lines this PR ADDS. A pre-existing read of a pre-existing column is fine."""
    out = _sh("git", "diff", "--unified=0", f"{base}...HEAD", "--", path)
    return [
        line[1:]
        for line in out.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]


def _columns_added(base: str, migration_paths: List[str]) -> Tuple[Dict[str, str], Set[str]]:
    """Map column name -> migration path, plus the set of overridden columns."""
    found: Dict[str, str] = {}
    overridden: Set[str] = set()
    for path in migration_paths:
        added = "\n".join(_added_lines(base, path))
        if not added:
            continue
        cols = {m.group(1) for m in _ADD_COLUMN_RE.finditer(added)}
        if not cols:
            continue
        if _OVERRIDE_RE.search(added):
            overridden |= cols
            continue
        for col in cols:
            found.setdefault(col, path)
    return found, overridden


def _is_scanned(path: str) -> bool:
    if not path.endswith(_CODE_SUFFIXES):
        return False
    if path.startswith(("backend/tests/", "scripts/", "docs/")):
        return False
    if "__tests__" in path or path.endswith((".test.ts", ".test.tsx", ".spec.ts")):
        return False
    return True


_COMMENT_STARTS = ("#", "//", "*", '"""', "'''", "--")
_BACKTICKED = re.compile(r"`[^`]*`")


def _code_only(line: str) -> str:
    """Drop prose so the guard reports reads, not mentions.

    Without this, the first run against the incident commit reported 5 violations of which
    3 were a docstring and a comment *describing* the column. A guard whose output is
    mostly noise gets ignored, and then it may as well not exist — the same reason the
    template-honesty checker gates on `category` rather than matching English nouns.
    """
    stripped = line.strip()
    if stripped.startswith(_COMMENT_STARTS):
        return ""
    # `form_templates.sections` inside a docstring is prose, not SQL.
    return _BACKTICKED.sub(" ", line)


def _reads_of(col: str, lines: List[str]) -> List[str]:
    """Lines that look like they READ the column.

    Requires a qualified or aliased reference — `ft.sections`, `sections AS x`,
    `"sections"` inside SQL — rather than the bare word. A bare match on a name like
    `status` or `name` would fire on almost every diff, and a guard that cries wolf gets
    switched off. Under-matching is the safer failure here: the rule is also written down
    in CLAUDE.md, and a missed case costs one revert, whereas a noisy guard costs the
    guard.
    """
    pat = re.compile(
        rf"(?:[A-Za-z_][A-Za-z0-9_]*\.{re.escape(col)}\b"      # ft.sections
        rf"|\b{re.escape(col)}\s+AS\s"                          # sections AS template_sections
        # row["sections"] — the `]` matters: it is the commonest Python read of a DB row,
        # and leaving it out silently narrowed this alternative to almost nothing. Caught
        # by the test below, which I first misdiagnosed as a bad test.
        rf"|[\"'`]{re.escape(col)}[\"'`]\s*(?:[,)\]]|$))",
        re.IGNORECASE,
    )
    return [ln.strip() for ln in lines if pat.search(_code_only(ln))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="base SHA/ref of the PR")
    args = ap.parse_args()

    changed = _changed_files(args.base)
    migrations = [p for p in changed if p.startswith("supabase/migrations/") and p.endswith(".sql")]
    if not migrations:
        print("[column-read-guard] no migrations in this PR — nothing to check")
        return 0

    columns, overridden = _columns_added(args.base, migrations)
    for col in sorted(overridden):
        print(f"[column-read-guard] {col}: override present, skipping")
    if not columns:
        print("[column-read-guard] no ADD COLUMN in this PR's migrations")
        return 0

    print(f"[column-read-guard] columns added: {', '.join(sorted(columns))}")

    violations: List[Tuple[str, str, str, str]] = []
    for path in changed:
        if not _is_scanned(path):
            continue
        lines = _added_lines(args.base, path)
        if not lines:
            continue
        for col, mig in sorted(columns.items()):
            for hit in _reads_of(col, lines):
                violations.append((col, mig, path, hit))

    if not violations:
        print("[column-read-guard] OK — no application code in this PR reads a column it adds")
        return 0

    print()
    print("=" * 78)
    print("BLOCKED: this PR adds a column AND ships code that reads it.")
    print("=" * 78)
    for col, mig, path, hit in violations:
        print(f"\n  column '{col}' added by {mig}")
        print(f"  read at {path}:")
        print(f"      {hit[:150]}")
    print(
        "\nMigrations here are applied OUT OF BAND, so merging the migration does not\n"
        "create the column. Deploying this code before an operator applies it produces\n"
        "an immediate 500 (this happened on 2026-08-11: GET /api/cases/{id}/forms was\n"
        "down for 2h33m). CI cannot see it because the backend suite runs on a SQLite\n"
        "fixture that this PR also edits.\n"
        "\nSplit it in two:\n"
        "  1. merge the migration file alone;\n"
        "  2. operator applies it + `supabase migration repair --status applied <version>`\n"
        "     (port 5432, not the 6543 pooler);\n"
        "  3. then merge the code that reads the column.\n"
        "\nIf this is genuinely safe, add to the migration:\n"
        "  -- guard: column-read-ok <why the read cannot run before the apply>\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
