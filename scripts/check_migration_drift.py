#!/usr/bin/env python3
"""
Migration-ledger drift check — AIQ-756-PREVENT.

Compares the migration versions APPLIED on the live/staging Supabase
(`supabase_migrations.schema_migrations.version`) against the version prefixes
of the repo's `supabase/migrations/*.sql` files, and fails when prod has an
applied version with **no matching repo file**.

That mismatch is what makes a fresh `supabase db push` / Supabase Preview abort
with `Remote migration versions not found in local migrations directory`, turning
EVERY PR's Preview red until someone reconciles by hand (see AIQ-756). It happens
because `MCP apply_migration` records an apply-TIME version (e.g. 20260604140233)
while the committed file carries a forward timestamp (e.g. 20260608100000). This
guard catches that drift at PR time instead of after merge.

Direction matters:
  * prod version with no repo file      -> DRIFT (fail): `db push` can't find it.
  * repo version ABOVE the ledger max   -> fine: undeployed work; Preview replays it.
  * repo version AT/BELOW the ledger max-> DEAD (fail): `db push` treats an out-of-order
    version as already-passed and skips it, so the file can never apply and never
    record a ledger row.
  * two repo files sharing a version    -> DUPLICATE (fail): schema_migrations is keyed
    on version, so only one can be recorded and the rest never apply.

The dead-version case is #1708: the ES_IE corpus seed merged at 20261004000000 while
prod's max was 20261009000000 — dead on arrival, yet every CI check went green because
this direction was only ever a warning. Restamped in #1709; the guard closes the hole.

`db push` is referenced below only to explain the ordering semantics the ledger inherits —
it must NEVER be run against prod (it would apply all ~147 pending migrations, including
known-destructive ones). Applies are operator-run and out-of-band; record them with
`supabase migration repair --status applied <version>`. See CLAUDE.md 'Migration discipline'.

Scoping — the dead and duplicate failures apply ONLY to migrations a change ADDS, passed
via `--added`. As of 2026-08 the repo has 426 ledger rows against 573 migration files, so
146 files already sit below the ledger max. That is long-standing debt no single PR
introduced; failing on it would redden every migration PR and the guard would be switched
off within a day. Without `--added` those two checks are audit warnings, which is also
what makes a full-repo run useful for the batch cleanup.

`--strict-duplicates` opts out of that softness for duplicates alone, and the whole-tree
job on `main` uses it. Without it, a run with no `--added` CANNOT FAIL: `dup_fail` is
empty, so duplicates print a warning and the process returns 0. That is exactly how
`.github/workflows/migration-duplicate-main.yml` was configured — the job CLAUDE.md's
guard table describes as the backstop "blind to nothing", running `--no-db` with no
`--added` and structurally incapable of firing since the day it was written (found in the
2026-08-11 guard sweep). The duplicate debt that justified the soft default is also gone:
the tree is at 591 files with zero duplicated versions, so strict costs nothing.

The dead-version check stays scoped to `--added`, because ITS debt is real and unpaid.

`--strict-unapplied` closes the gap those scopings leave open: a migration that was fine
when it merged and went stale afterwards. Because dead/duplicate hard failures only look at
the files a change ADDS, nothing ever re-examines a migration after merge — it degrades to a
warning printed in some later PR's log. On 2026-08-20 that hid two: 20261110000000
(services_state tenant policies, #1902) and 20261111000000 (candidate_beam researched_*
columns, #1894) were merged and never applied, with every check green, while an open PR
(#1895) read those columns in 51 places. This mode spans BOTH dead and ahead files, since
the difference between them is `db push` ordering and this repo never runs `db push`; what
matters is only whether the migration is live. It needs `--baseline` to tell a new lapse
from the parked backlog, and excuses anything younger than `--grace-hours` (default 24)
so a just-merged migration does not redden the job before an operator can act.

Exit codes (mirrors scripts/check_rls_coverage.py):
  0 — no drift; nothing newly dead or newly duplicated
  1 — prod version with no repo file; a NEW dead/duplicate migration; any duplicate under
      --strict-duplicates; a merged-but-unapplied migration under --strict-unapplied; or
      0 migration files read (CI should fail)
  2 — could not connect to DB / query failed (unexpected — investigate)

Usage:
  DATABASE_URL=postgresql://... python scripts/check_migration_drift.py
  DATABASE_URL=postgresql://... python scripts/check_migration_drift.py --json
  python scripts/check_migration_drift.py --no-db --strict-duplicates  # whole-tree gate
  DATABASE_URL=postgresql://... python scripts/check_migration_drift.py \
      --strict-unapplied --baseline scripts/migration_unapplied_baseline.json
  python scripts/check_migration_drift.py --no-db --added "$(git diff --diff-filter=A \
      --name-only origin/main...HEAD -- supabase/migrations)"
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"

# A migration filename is "<14-digit-version>_<name>.sql".
_FILENAME_RE = re.compile(r"^(\d{14})_(.+)\.sql$")

_APPLIED_SQL = "SELECT version, name FROM supabase_migrations.schema_migrations;"


# ---------------------------------------------------------------------------
# Pure logic (unit-tested without a DB)
# ---------------------------------------------------------------------------

def repo_versions(migrations_dir: Path) -> Set[str]:
    """Set of 14-digit version prefixes of every supabase/migrations/*.sql file."""
    out: Set[str] = set()
    if not migrations_dir.exists():
        return out
    for p in migrations_dir.glob("*.sql"):
        m = _FILENAME_RE.match(p.name)
        if m:
            out.add(m.group(1))
    return out


def repo_versions_by_name(migrations_dir: Path) -> Dict[str, str]:
    """Map migration name -> its repo version, to suggest a reconciliation target."""
    out: Dict[str, str] = {}
    if not migrations_dir.exists():
        return out
    for p in migrations_dir.glob("*.sql"):
        m = _FILENAME_RE.match(p.name)
        if m:
            out[m.group(2)] = m.group(1)
    return out


def repo_files_by_version(migrations_dir: Path) -> Dict[str, str]:
    """Map repo version -> migration name, for the Direction-B (repo-not-on-prod) check."""
    out: Dict[str, str] = {}
    if not migrations_dir.exists():
        return out
    for p in migrations_dir.glob("*.sql"):
        m = _FILENAME_RE.match(p.name)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def find_drift(applied: Dict[str, str], repo_vers: Set[str]) -> List[Dict[str, str]]:
    """
    Return the prod-applied (version, name) rows whose version has no repo file.

    `applied` maps prod version -> migration name. Sorted by version for stable output.
    """
    drift = [
        {"version": ver, "name": name}
        for ver, name in applied.items()
        if ver not in repo_vers
    ]
    return sorted(drift, key=lambda d: d["version"])


def find_repo_only(applied: Dict[str, str], repo_by_version: Dict[str, str]) -> List[Dict[str, str]]:
    """
    Direction B (warning): repo migration files whose version has no prod row.

    `applied` maps prod version -> name; `repo_by_version` maps repo version -> name.
    This is legitimate for undeployed work on a PR branch, but it makes
    `db push` / Supabase Branching fail with 'local migration files not found in
    remote database' — so it's surfaced as a WARNING, not a hard failure.
    """
    repo_only = [
        {"version": ver, "name": name}
        for ver, name in repo_by_version.items()
        if ver not in applied
    ]
    return sorted(repo_only, key=lambda d: d["version"])


def split_dead_and_ahead(
    repo_only: List[Dict[str, str]], applied: Dict[str, str]
) -> "tuple[List[Dict[str, str]], List[Dict[str, str]]]":
    """
    Partition Direction-B rows into (dead, ahead) on the prod ledger max.

    `db push` applies a migration only when its version sorts ABOVE the highest
    version already in `schema_migrations`; an out-of-order version is treated as
    already-passed and skipped. So a repo file with no prod row is either:

      * version >  ledger max -> AHEAD: ordinary undeployed work, applies on the
                                 next push. Warning only, as before.
      * version <= ledger max -> DEAD:  can never apply and can never record a
                                 ledger row. Hard failure.

    This is the AIQ/#1708 regression: the ES_IE corpus seed merged at
    20261004000000 while prod's max was 20261009000000, so it was dead on arrival
    and every CI check still went green (fixed by restamping in #1709).

    Versions are zero-padded 14-digit strings, so lexicographic comparison is
    equivalent to numeric. With an empty ledger nothing can be dead.
    """
    if not applied:
        return [], list(repo_only)
    ledger_max = max(applied)
    dead = [r for r in repo_only if r["version"] <= ledger_max]
    ahead = [r for r in repo_only if r["version"] > ledger_max]
    return dead, ahead


def load_baseline(path: Path) -> Set[str]:
    """
    Read the known-unapplied baseline: the versions we already know are merged but not
    applied, and have consciously parked.

    A missing or unparseable baseline is a HARD ERROR, never an empty set. The whole
    value of this file is that it is the difference between "nothing new is wrong" and
    "we are not looking" — and a guard that silently degrades to the second while
    printing the first is the exact failure this repo found in `--strict-duplicates`,
    which was structurally incapable of firing from the day it was written.

    Format: {"versions": {"<14-digit>": "<name or note>", ...}} — a dict rather than a
    list so each parked entry can carry why it is parked.
    """
    if not path.exists():
        raise SystemExit(
            f"❌  Baseline not found: {path}\n"
            "    Refusing to run: with no baseline this check cannot tell a NEW unapplied\n"
            "    migration from the long-standing parked backlog, so it would either fail on\n"
            "    everything or (worse) be softened until it fails on nothing.\n"
            "    Generate one with:  --strict-unapplied --write-baseline <path>"
        )
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise SystemExit(f"❌  Baseline at {path} is unreadable: {exc}")
    versions = raw.get("versions")
    if not isinstance(versions, dict):
        raise SystemExit(
            f"❌  Baseline at {path} has no 'versions' object — refusing to treat that as "
            "'nothing is parked'."
        )
    return set(versions)


def git_added_at(version: str, name: str) -> "datetime | None":
    """
    When did this migration file first appear in git history?

    Used for the grace window: a migration merged minutes ago is legitimately unapplied,
    and failing on it would make the job red for every normal migration PR until an
    operator got to it.

    Returns None when git cannot answer (shallow clone, untracked file). The caller
    treats None as OUTSIDE the grace window — unknown age must not become a silent
    exemption, and in CI the checkout is full-depth so None means something is wrong.
    """
    path = f"supabase/migrations/{version}_{name}.sql"
    try:
        out = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%cI", "-1", "--", path],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    stamp = out.stdout.strip()
    if out.returncode != 0 or not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp)
    except ValueError:
        return None


def find_new_unapplied(
    repo_only: List[Dict[str, str]],
    baseline: Set[str],
    grace_hours: float,
    now: "datetime | None" = None,
) -> "tuple[List[Dict[str, str]], List[Dict[str, str]]]":
    """
    Partition Direction-B rows into (failing, excused).

    Failing = merged, not applied, not in the baseline, and older than the grace window.
    That is precisely "someone merged a migration and nobody ever ran it", which is the
    gap this check exists to close: #1902 and #1894 sat in that state with every CI check
    green, because the existing dead/duplicate hard failures are scoped to the files a PR
    ADDS and nothing re-examines a migration after it merges.
    """
    now = now or datetime.now(timezone.utc)
    failing: List[Dict[str, str]] = []
    excused: List[Dict[str, str]] = []
    for row in repo_only:
        if row["version"] in baseline:
            excused.append({**row, "excuse": "baseline"})
            continue
        added = git_added_at(row["version"], row["name"])
        if added is not None:
            age_hours = (now - added).total_seconds() / 3600.0
            if age_hours < grace_hours:
                excused.append({**row, "excuse": f"within {grace_hours}h grace"})
                continue
            row = {**row, "age_hours": round(age_hours, 1)}
        failing.append(row)
    return failing, excused

def parse_added_versions(raw: str) -> Set[str]:
    """
    Extract 14-digit versions from a comma/newline-separated list of added paths.

    Fed by `git diff --diff-filter=A --name-only <base>...HEAD -- supabase/migrations`,
    so the hard failures below apply only to files THIS change introduces. Entries that
    don't look like a migration filename are ignored.
    """
    out: Set[str] = set()
    for chunk in raw.replace(",", "\n").splitlines():
        name = chunk.strip().rsplit("/", 1)[-1]
        m = _FILENAME_RE.match(name)
        if m:
            out.add(m.group(1))
    return out


def find_duplicate_versions(migrations_dir: Path) -> Dict[str, List[str]]:
    """
    Map version -> sorted names, for every 14-digit version claimed by >1 file.

    `supabase_migrations.schema_migrations` is keyed on `version` (one row per
    version), so when two files share a timestamp only one can ever be recorded
    and the other silently never applies. That is how `source_change_reviews`
    lost its slot to `feature_flags` and left two tables missing in prod.

    Needs no DB, so this runs even where the ledger check is gated off.
    """
    by_version: Dict[str, List[str]] = {}
    if not migrations_dir.exists():
        return {}
    for p in migrations_dir.glob("*.sql"):
        m = _FILENAME_RE.match(p.name)
        if m:
            by_version.setdefault(m.group(1), []).append(m.group(2))
    return {ver: sorted(names) for ver, names in by_version.items() if len(names) > 1}


# ---------------------------------------------------------------------------
# DB access (mirrors check_rls_coverage.py)
# ---------------------------------------------------------------------------

def query_applied_versions(db_url: str) -> Dict[str, str]:
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 not installed — `pip install psycopg2-binary` or run from backend venv", file=sys.stderr)
        sys.exit(2)

    if db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://"):]

    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
    except Exception as exc:
        print(f"could not connect to DATABASE_URL: {exc}", file=sys.stderr)
        sys.exit(2)

    try:
        with conn.cursor() as cur:
            cur.execute(_APPLIED_SQL)
            rows = cur.fetchall()
    finally:
        conn.close()

    return {r[0]: (r[1] or "") for r in rows}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_duplicates(duplicates: Dict[str, List[str]], hard: bool) -> None:
    """Shared reporting for duplicate versions (both --no-db and full runs)."""
    mark = "❌  Migration-drift check FAILED —" if hard else "⚠  WARN (pre-existing) —"
    print(f"\n{mark} {len(duplicates)} duplicated migration version(s):")
    print("    (schema_migrations is keyed on version — only ONE file per version can be")
    print("     recorded, so the others silently never apply)\n")
    for ver in sorted(duplicates):
        print(f"  • {ver}")
        for name in duplicates[ver]:
            print(f"      {ver}_{name}.sql")
    if hard:
        print("\n  Fix: restamp the newer file to a unique version above the prod ledger max.")
        print("  On main this is a post-merge collision — most often two PRs batch-merged")
        print("  back to back, since GitHub does not re-run a PR when its base moves.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check prod migration ledger vs repo files.")
    parser.add_argument("--json", action="store_true", help="Output drift as JSON.")
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Run only the checks that need no database (duplicate repo versions). "
             "Lets CI catch colliding timestamps even where the ledger check is gated off.",
    )
    parser.add_argument(
        "--added",
        default="",
        help="Comma/newline-separated migration paths ADDED by this change (from "
             "`git diff --diff-filter=A`). Scopes the dead-version and duplicate hard "
             "failures to those files. Without it both are audit warnings, because the "
             "repo carries long-standing pre-existing drift that no single PR introduced.",
    )
    parser.add_argument(
        "--strict-duplicates",
        action="store_true",
        help="Treat EVERY duplicated version as a hard failure, not only ones in "
             "--added. Required for a whole-tree run to be able to fail at all; used by "
             "the post-merge backstop on main.",
    )
    parser.add_argument(
        "--strict-unapplied",
        action="store_true",
        help="Fail on migrations that are merged but have NO prod ledger row, excluding "
             "those in --baseline and those younger than --grace-hours. Without this flag "
             "Direction B stays a warning, exactly as before.",
    )
    parser.add_argument(
        "--baseline",
        default="",
        help="Path to the known-unapplied baseline JSON. Required with --strict-unapplied: "
             "it is what separates a NEW unapplied migration from the parked backlog. A "
             "missing or unparseable file is a hard error, never an empty set.",
    )
    parser.add_argument(
        "--grace-hours",
        type=float,
        default=24.0,
        help="Migrations that first appeared in git within this many hours are excused — "
             "a migration merged minutes ago is legitimately not applied yet. Default 24.",
    )
    parser.add_argument(
        "--write-baseline",
        default="",
        help="Write the CURRENT unapplied set to this path and exit 0. Run once, after the "
             "outstanding applies are done, so the backlog is parked but today's gap is not.",
    )
    args = parser.parse_args()

    if args.strict_unapplied and not (args.baseline or args.write_baseline):
        parser.error("--strict-unapplied requires --baseline (or --write-baseline to create one)")

    # A guard that read no migration files has not checked anything. Without this,
    # `--no-db` on an empty or misplaced directory prints
    # "✅  No duplicate migration versions (0 repo files)" and exits 0.
    all_versions = repo_versions(MIGRATIONS_DIR)
    if not all_versions:
        print(f"❌  Migration-drift check FAILED — read 0 migration files from {MIGRATIONS_DIR}.")
        print("    Every check below compares against that set, so an empty one makes")
        print("    'no duplicates' and 'no drift' meaningless rather than reassuring.")
        return 1

    duplicates = find_duplicate_versions(MIGRATIONS_DIR)
    added_versions = parse_added_versions(args.added)
    # Scope hard failures to what this change actually adds. `--added` absent = audit mode.
    scoped = bool(args.added.strip())
    if args.strict_duplicates:
        dup_fail = dict(duplicates)
    elif scoped:
        dup_fail = {v: n for v, n in duplicates.items() if v in added_versions}
    else:
        dup_fail = {}

    # State the mode. A green run that examined a diff of zero files reads identically to
    # one that verified the whole tree, and the difference is the entire question.
    if args.strict_duplicates and args.strict_unapplied:
        mode = "STRICT — duplicates and unapplied migrations are failures"
    elif args.strict_unapplied:
        mode = "STRICT(unapplied) — a merged-but-unapplied migration is a failure"
    elif args.strict_duplicates:
        mode = "STRICT — every duplicated version is a failure"
    elif scoped:
        mode = f"scoped to {len(added_versions)} added version(s)"
    else:
        mode = "AUDIT MODE — dead/duplicate are warnings only, this run cannot fail on them"
    if not args.json:
        print(f"[migration-drift] {len(all_versions)} repo versions; {mode}.")

    # --no-db: duplicate detection only. Deliberately independent of DATABASE_URL so
    # this can run unconditionally, unlike the ledger comparison below.
    if args.no_db:
        if args.json:
            print(json.dumps(
                {"repo_versions": len(all_versions), "mode": mode,
                 "duplicates": duplicates, "count": len(duplicates),
                 "duplicates_failing": dup_fail, "fail_count": len(dup_fail),
                 "pass": not dup_fail},
                indent=2,
            ))
        elif duplicates:
            _print_duplicates(dup_fail or duplicates, hard=bool(dup_fail))
        else:
            print(f"✅  No duplicate migration versions ({len(all_versions)} repo files).")
        return 1 if dup_fail else 0

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set", file=sys.stderr)
        return 2

    applied = query_applied_versions(db_url)
    repo_vers = repo_versions(MIGRATIONS_DIR)
    repo_by_ver = repo_files_by_version(MIGRATIONS_DIR)
    by_name = repo_versions_by_name(MIGRATIONS_DIR)
    drift = find_drift(applied, repo_vers)          # Direction A — prod not in repo (hard fail)
    repo_only = find_repo_only(applied, repo_by_ver)  # Direction B — repo not on prod
    # Direction B splits: below the ledger max a file can never apply (hard fail);
    # above it, it is ordinary undeployed work (warning, as before).
    dead, repo_ahead = split_dead_and_ahead(repo_only, applied)
    ledger_max = max(applied) if applied else None
    # Only files this change ADDS are a hard failure. The repo carries 100+ pre-existing
    # below-max files (the ledger is far sparser than the migrations dir), and failing on
    # those would redden every migration PR for debt it did not create.
    dead_fail = [d for d in dead if d["version"] in added_versions] if scoped else []

    # Direction B, the whole-tree view: merged but never applied. Deliberately spans BOTH
    # dead and ahead — the distinction between them is `db push` ordering semantics, and
    # this repo never runs `db push`. What matters here is only "is it live in prod".
    unapplied_fail: List[Dict[str, str]] = []
    unapplied_excused: List[Dict[str, str]] = []
    if args.write_baseline:
        target = Path(args.write_baseline)
        target.write_text(json.dumps({
            "_comment": (
                "Migrations merged but not applied to prod, consciously parked. Generated by "
                "check_migration_drift.py --write-baseline. Entries should be REMOVED as the "
                "backlog is triaged; this file is meant to shrink. A version absent from here "
                "and unapplied past the grace window fails the scheduled job."
            ),
            "generated_from_ledger_max": ledger_max,
            "count": len(repo_only),
            "versions": {r["version"]: r["name"] for r in repo_only},
        }, indent=2) + "\n")
        print(f"✅  Wrote baseline of {len(repo_only)} unapplied migration(s) to {target}")
        return 0
    if args.strict_unapplied:
        baseline = load_baseline(Path(args.baseline))
        unapplied_fail, unapplied_excused = find_new_unapplied(
            repo_only, baseline, args.grace_hours
        )

    # Annotate each drift row with a suggested reconciliation target if the same
    # migration NAME exists in the repo at a different version (the common case:
    # apply-time version vs committed forward-timestamp version).
    for d in drift:
        repo_ver = by_name.get(d["name"])
        d["suggested_repo_version"] = repo_ver if repo_ver and repo_ver != d["version"] else None

    if args.json:
        print(json.dumps(
            {"drift": drift, "count": len(drift),
             "repo_only": repo_ahead, "warn_count": len(repo_ahead),
             "dead": dead, "dead_count": len(dead),
             "dead_added": dead_fail, "dead_added_count": len(dead_fail),
             "duplicates": duplicates, "duplicate_count": len(duplicates),
             "duplicates_failing": dup_fail, "duplicates_failing_count": len(dup_fail),
             "unapplied_failing": unapplied_fail,
             "unapplied_failing_count": len(unapplied_fail),
             "unapplied_excused_count": len(unapplied_excused),
             "ledger_max": ledger_max, "mode": mode,
             "pass": not (drift or dead_fail or dup_fail or unapplied_fail)},
            indent=2,
        ))

    # Direction A — prod version with no repo file. This is the ONLY hard failure.
    if drift and not args.json:
        print(f"❌  Migration-drift check FAILED — {len(drift)} prod version(s) have NO repo file:")
        print("    (this is what makes `db push` / Supabase Preview fail with")
        print("     'Remote migration versions not found in local migrations directory')\n")
        for d in drift:
            if d["suggested_repo_version"]:
                print(f"  • {d['version']}  {d['name']}")
                print(f"      → repo has this migration at {d['suggested_repo_version']}. Reconcile the ledger:")
                print(f"        UPDATE supabase_migrations.schema_migrations SET version='{d['suggested_repo_version']}'")
                print(f"          WHERE version='{d['version']}' AND name='{d['name']}';  -- collision-check first")
            else:
                print(f"  • {d['version']}  {d['name']}  → no repo file by this name; commit a prod-as-oracle "
                      f"migration at version {d['version']} (real DDL or stub).")
        print("\n  Prevention: don't pre-apply repo-tracked migrations via MCP apply_migration — it stamps")
        print("  an APPLY-TIME version, not your file's, so the ledger ends up with a version no repo file")
        print("  matches and this check fails on every migration PR until someone reconciles it. Commit the")
        print("  file first, then apply out-of-band with execute_sql and record it with")
        print("  `supabase migration repair --status applied <version>`. See CLAUDE.md.")

    # Direction B (dead) — repo file at or below the ledger max with no prod row.
    # `db push` will skip it forever, so it can never apply and never record a row.
    if dead_fail and not args.json:
        print(f"\n❌  Migration-drift check FAILED — {len(dead_fail)} NEW migration(s) can NEVER apply:")
        print(f"    (the ledger is keyed by version and prod's max is {ledger_max}; a version at")
        print("     or below it can never be recorded for this file)\n")
        for d in dead_fail:
            print(f"  • {d['version']}_{d['name']}.sql  ≤  {ledger_max}")
        print("\n  Fix: restamp the file above the ledger max, e.g.")
        print("    git mv supabase/migrations/<old>_<name>.sql supabase/migrations/<new>_<name>.sql")
        print("  and update the header comment.")
        print("  Then apply it out-of-band (operator-run MCP apply_migration/execute_sql) and record")
        print("  it with:  supabase migration repair --status applied <version> --db-url \"$DATABASE_URL\"")
        print("  NEVER `supabase db push` against prod — it applies every pending migration, and")
        print("  never hand-insert into schema_migrations. See CLAUDE.md 'Migration discipline'.")
    elif dead and not args.json:
        print(f"\n⚠  WARN (pre-existing) — {len(dead)} repo migration(s) sit at or below the")
        print(f"    ledger max ({ledger_max}) with no prod row, so `db push` would skip them.")
        print("    Not introduced by this change; tracked for batch reconciliation.")

    # Duplicate repo versions — schema_migrations is keyed on version, so only one
    # file per version can ever be recorded and the rest silently never apply.
    if duplicates and not args.json:
        _print_duplicates(dup_fail or duplicates, hard=bool(dup_fail))

    # Direction B (whole tree) — merged but never applied, and not parked in the baseline.
    if unapplied_fail and not args.json:
        print(f"\n❌  Migration check FAILED — {len(unapplied_fail)} migration(s) are merged "
              "but have NEVER been applied to production:\n")
        for u in unapplied_fail:
            age = u.get("age_hours")
            age_s = f"unapplied for {age}h" if age is not None else "age unknown (shallow clone?)"
            print(f"  • {u['version']}_{u['name']}.sql  — {age_s}")
        print("\n  Merging a migration does not apply it. Apply it out-of-band with MCP")
        print("  execute_sql (NOT apply_migration, which stamps an apply-time version, and")
        print("  NEVER `supabase db push`), then record it:")
        print("    supabase migration repair --status applied <version> --db-url \"$DATABASE_URL\"")
        print("  If it is deliberately parked, add it to the baseline with a note saying why.")
        if unapplied_excused:
            print(f"\n  ({len(unapplied_excused)} other unapplied migration(s) excused: "
                  "baseline or grace window.)")

    # Direction B (ahead) — repo file above the ledger max with no prod row. WARNING
    # only (exit 0): legitimate undeployed work, but it breaks `db push` / Branching.
    if repo_ahead and not args.json:
        print(f"\n⚠  WARN — {len(repo_ahead)} repo migration file(s) have no matching prod row:")
        for r in repo_ahead:
            print(f"  • {r['version']}_{r['name']}.sql has no matching prod row.")
        print("     Apply the migration or delete the file if it was committed by mistake.")
        print("     This will cause `db push` / Supabase Branching to fail with")
        print("     'local migration files not found in remote database'.")

    failed = bool(drift or dead_fail or dup_fail or unapplied_fail)

    # Summary line — always printed.
    if not args.json:
        mark = "❌" if failed else ("⚠ " if (repo_ahead or dead or duplicates) else "✅")
        print(f"{mark}  Migration ledger: {len(applied)} prod rows, {len(repo_by_ver)} repo files, "
              f"{len(drift)} mismatch(es), {len(dead)} dead ({len(dead_fail)} failing), "
              f"{len(duplicates)} duplicate version(s) ({len(dup_fail)} failing), "
              f"{len(repo_ahead)} repo-ahead warning(s), "
              f"{len(unapplied_fail)} unapplied failing. [{mode}]")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
