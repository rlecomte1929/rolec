#!/usr/bin/env python3
"""
check_deliverable_integrity.py — assert that "Done" AI Work Queue tasks' claimed
deliverable files actually exist in the repo.

Why: Cowork-authored tasks get closed ``Done`` on the basis of a deliverable
file (their Execution Notes say ``CREATED: <repo path>`` or "move outputs/X into
repo"), but the file is sometimes never merged to ``main``. Two such silent
leaks were found and fixed by hand on 2026-06-04 (C1-04a → PR #290, P3-01c →
PR #289). This guard catches the whole class automatically.

How: query the AI Work Queue for ``Status = Done`` tasks of file-producing
types, extract repo-relative deliverable paths from their notes, and assert each
path is a tracked file (``git ls-files``). A drain-over-time allowlist
(``scripts/deliverable_integrity_allowlist.txt``) suppresses known-acceptable
mismatches (suggested/renamed paths, specs intentionally kept in Notion).

Modes:
  * default  — report-only: print findings, exit 0 (surfaces leaks in CI logs
               without blocking while the allowlist is seeded).
  * --strict — exit 1 when any non-allowlisted missing deliverable is found.

Notion access: reads ``NOTION_TOKEN`` from the environment. When unset (e.g. a
local run without the secret), the check is SKIPPED with a notice and exits 0 —
the CI job is gated on ``vars.NOTION_QUEUE_TOKEN_SET`` so the token is present
when it actually runs.

Mirrors the self-contained audit-script pattern of ``check_route_auth.py`` /
``check_router_registrations.py`` (stdlib only, comment-aware allowlist, clear
report, ``sys.exit(main())``).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# AI Work Queue (Notion). Database id from references/notion-schema.md.
_DEFAULT_DATABASE_ID = "3bc887c6-4d48-8089-8188-fcf2dc3edc1b"
_NOTION_VERSION = "2022-06-28"

# Task types that produce a file deliverable (others — Research, Competitive
# Analysis — may live only in Notion and are skipped).
_FILE_PRODUCING_TYPES = {
    "Backend Implementation",
    "Frontend Implementation",
    "Prompt Engineering",
    "Database Migration",
    "RAG Improvement",
    "Performance Optimization",
}

# Repo roots a real deliverable path lives under. A path token is only treated
# as a candidate deliverable when it starts with one of these and ends in a file
# extension — keeps prose ("the cases domain") from being mistaken for a path.
_KNOWN_ROOTS = (
    "outputs", "backend", "prompts", "scripts", "supabase/migrations",
    "audit", "docs", "frontend/src", "apps", "lib", ".github",
)

_PATH_RE = re.compile(
    r"(?<![\w./-])"
    r"((?:" + "|".join(r.replace("/", r"/") for r in _KNOWN_ROOTS) + r")"
    r"/[A-Za-z0-9_./\-]+\.[A-Za-z0-9]+)"
)

# A line declaring a produced/changed file. Only paths on such lines are treated
# as deliverable claims (the Execution-Notes "Files changed" convention).
_CLAIM_MARKER_RE = re.compile(r"\b(CREATED|MODIFIED|ADDED|NEW FILE)\b", re.IGNORECASE)

# A line declaring a file the task REMOVED. For a retirement task the deliverable
# IS the file's absence, so such a path must never count as a claim. This wins over
# the section rule below: a "DELETED: x" bullet lives under the same
# "## Files changed" heading as its MODIFIED siblings, so without this the guard
# fails exactly the tasks that did their job — a Done retirement is reported as
# "claimed but NOT in the repo", which is the intended end state, not a leak.
# (AIQ-1565 retired WorkBoard.tsx/.test.tsx and broke this check repo-wide.)
#
# Anchored to the line's leading bullet marker, NOT matched anywhere in the line:
# a sibling "- MODIFIED: foo.tsx — removed the toggle" mentions "removed" in prose
# and must stay a claim. An unanchored \b(DELETED|REMOVED)\b silently disables the
# guard for any such line.
_ANTI_CLAIM_MARKER_RE = re.compile(
    r"^\s*[-*+]?\s*\**\s*(DELETED|REMOVED)\b\s*\**\s*:", re.IGNORECASE
)

# A markdown heading line, and the subset of headings that open a "claimed
# deliverables" section. Cowork lists its outputs as numbered bullets under a
# "What was built" / "Files created" heading WITHOUT a CREATED: marker (e.g.
# "1. outputs/foo.md — ..."), so paths under such a heading also count as claims.
# A non-matching heading closes the section (reviewer-steps prose is excluded).
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")
_CLAIM_SECTION_RE = re.compile(
    r"#{1,6}\s*(?:what was built|files?\s+(?:created|changed|added)"
    r"|new files?|deliverables?)\b",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested without network)                                  #
# --------------------------------------------------------------------------- #


def extract_deliverable_paths(note_text: str) -> List[str]:
    """Return the repo-relative deliverable paths a task CLAIMS it produced.

    A path counts as a deliverable claim when it appears EITHER:
      * on a line bearing a ``CREATED:``/``MODIFIED:`` marker (the Execution-Notes
        "Files changed" convention), OR
      * under a "What was built" / "Files created" / "Deliverables" heading — the
        Cowork numbered-bullet convention (``1. outputs/foo.md — ...``) that carries
        no marker. A subsequent non-claim heading closes the section.
    A line marked ``DELETED:``/``REMOVED:`` is never a claim, even inside a claim
    section: the task's deliverable is that the file is GONE, so its absence is
    success, not a missing deliverable.
    Paths mentioned anywhere else — reviewer-steps prose like "move X into
    `scripts/Y`", example commands, or "see also `path`" — are NOT claims and were
    the dominant false-positive source on the first live run (a file that landed at
    a slightly different path than the prose mentioned). Order-preserving and
    de-duplicated.
    """
    seen: Set[str] = set()
    out: List[str] = []
    in_claim_section = False
    for line in (note_text or "").splitlines():
        if _HEADING_RE.match(line):
            in_claim_section = bool(_CLAIM_SECTION_RE.search(line))
        # Checked before the claim rules: a removal is the opposite of a claim.
        if _ANTI_CLAIM_MARKER_RE.search(line):
            continue
        if not (in_claim_section or _CLAIM_MARKER_RE.search(line)):
            continue
        for m in _PATH_RE.finditer(line):
            p = m.group(1).rstrip(".,);:")
            # Skip captures whose basename is just an extension (e.g. prose like
            # "11 backend/db/.py mixins" → "backend/db/.py"): not a real file.
            if not p or p.rsplit("/", 1)[-1].startswith("."):
                continue
            if p not in seen:
                seen.add(p)
                out.append(p)
    return out


# ── Was this deliverable ever real? ──────────────────────────────────────────
#
# The guard used to ask "is this a tracked file TODAY". For a check whose job is
# "did this Done task's claimed deliverable actually ship", that is the wrong
# question: files legitimately move, and a refactor three months later does not
# retroactively make a shipped deliverable a lie.
#
# Measured on 2026-08-23 against the first live run: of 97 flagged paths, 62 had
# existed and been renamed or deleted since. Suppressing those in the allowlist
# would have grown it from 150 to 212 entries and left every future refactor
# tripping the same way.

_MANGLE_RULES = (
    # Notion renders a BARE `__init__.py` / `__tests__` as markdown bold and eats the
    # underscores, so the stored text is `init.py` / `tests/`. CLAUDE.md tells authors
    # to wrap paths in backticks for exactly this reason, but ~1,800 historical cards
    # cannot be re-edited, so the guard has to be robust to it.
    (re.compile(r"(^|/)init_?\.py$"), r"\1__init__.py"),
    (re.compile(r"(^|/)tests/"), r"\1__tests__/"),
)


def demangled_variants(path: str) -> List[str]:
    """Candidate paths with Notion's eaten underscores restored. Never includes *path*."""
    out: List[str] = []
    for rx, repl in _MANGLE_RULES:
        cand = rx.sub(repl, path)
        if cand != path and cand not in out:
            out.append(cand)
    return out


def is_shallow(root: Path) -> bool:
    """True when the clone has no full history.

    Critical. `git log --all` on a shallow clone returns almost nothing, so the
    ever-existed check would classify EVERY deliverable as never-existed — 97
    confident false phantoms on the run that motivated this. The caller turns this
    into exit 3, because a check that cannot measure must say so.
    """
    res = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=str(root), capture_output=True, text=True,
    )
    return res.stdout.strip() == "true"


def paths_ever_added(root: Path) -> Set[str]:
    """Every repo-relative path added in any commit on any branch.

    One `git log` for the whole repo rather than one per candidate: measured at
    24,983 paths / 1.3s / 1.8 MB locally, which is cheap enough for CI.
    """
    res = subprocess.run(
        ["git", "log", "--all", "--diff-filter=A", "--name-only", "--format="],
        cwd=str(root), capture_output=True, text=True, check=True,
    )
    return {line.strip() for line in res.stdout.splitlines() if line.strip()}


def check_tasks(
    tasks: List[Dict[str, Any]],
    tracked_files: Set[str],
    allowlist: Set[str],
    ever_added: Optional[Set[str]] = None,
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, str]]]:
    """Classify every claimed deliverable into three buckets.

    Returns ``(missing, moved, mangled)``:

    * **missing** — never existed in any commit on any branch. The only FAILING
      bucket, and the only one that means a Done task claimed something untrue.
    * **moved** — not present today, but it WAS added at some point. The work
      shipped and the path went stale. Reported, never failed on.
    * **mangled** — resolves once Notion's eaten underscores are restored. Passes,
      but warns, so the badly-authored card gets fixed instead of the guard
      quietly absorbing it forever.

    A task dict has ``title``, ``aiq``, ``url``, ``paths``. ``ever_added`` is the
    output of :func:`paths_ever_added`; pass ``None`` to skip the history check
    (present-day behaviour only).

    Order of resolution matters: allowlist BEFORE history, so an explicitly
    baselined entry stays silent rather than reappearing as a "moved" line.
    """
    missing: List[Dict[str, str]] = []
    moved: List[Dict[str, str]] = []
    mangled: List[Dict[str, str]] = []
    for t in tasks:
        aiq = str(t.get("aiq") or "")
        for path in t.get("paths") or []:
            row = {
                "aiq": aiq,
                "title": str(t.get("title") or ""),
                "path": path,
                "url": str(t.get("url") or ""),
            }
            if path in tracked_files:
                continue
            if path in allowlist or f"{aiq}:{path}" in allowlist:
                continue

            # Notion ate the underscores? Resolve, but say so.
            hit = next(
                (c for c in demangled_variants(path)
                 if c in tracked_files or (ever_added is not None and c in ever_added)),
                None,
            )
            if hit:
                mangled.append({**row, "resolved_to": hit})
                continue

            if ever_added is not None and path in ever_added:
                moved.append(row)
                continue

            missing.append(row)
    return missing, moved, mangled


def load_allowlist(path: Path) -> Set[str]:
    """Comment-aware allowlist loader (``#`` comments + blank lines ignored).
    Each entry is a bare ``<repo/path>`` or an ``<AIQ-id>:<repo/path>`` key."""
    if not path.exists():
        return set()
    out: Set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            out.add(line)
    return out


def tracked_files(root: Path) -> Set[str]:
    """Repo-relative paths tracked by git under ``root``."""
    res = subprocess.run(
        ["git", "ls-files"], cwd=str(root), capture_output=True, text=True, check=True,
    )
    return {line.strip() for line in res.stdout.splitlines() if line.strip()}


# --------------------------------------------------------------------------- #
# Notion fetch                                                                #
# --------------------------------------------------------------------------- #


#: Exit codes. 3 separates "measured, clean" from "could not measure" — this guard used to
#: collapse both into 0. On 2026-08-23 its CI log read
#:     [WARN] Notion query failed (HTTP Error 404: Not Found); skipping (exit 0).
#: and it reported PASS on every PR while examining nothing.
EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_NOT_MEASURED = 3

#: The server-side filter is `Status = Done`, which held ~1,530 rows on 2026-08-23. This floor
#: applies to that PRE-filter count, not to the file-producing subset, which is legitimately
#: much smaller and would make a floor a false-positive machine.
MIN_EXPECTED_DONE_ROWS = 500


class QueueUnavailable(RuntimeError):
    """The queue could not be measured. NEVER report this as a pass."""

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


def assert_non_degenerate(
    tasks: List[Dict[str, Any]],
    done_seen: int,
    file_producing_seen: Optional[int] = None,
    with_notes: Optional[int] = None,
) -> None:
    """Refuse to call a degenerate scan clean.

    A renamed property does not raise — it yields "" for every row, every count becomes 0,
    and that reads exactly like a healthy queue. `Task Title` -> `fable` drifted this way and
    nobody noticed. Each assertion below is a way this guard could go quietly blind.
    """
    # Older callers passed only (tasks, done_seen). Derive the two finer counts from the
    # task list in that case: every task in the list survived BOTH filters by definition.
    if file_producing_seen is None:
        file_producing_seen = len(tasks)
    if with_notes is None:
        with_notes = sum(1 for t in tasks if str(t.get("notes") or "").strip())

    if done_seen < MIN_EXPECTED_DONE_ROWS:
        raise QueueUnavailable(
            "schema-drift",
            f"only {done_seen} Done row(s) returned; expected at least "
            f"{MIN_EXPECTED_DONE_ROWS}. The Status filter or the database id is probably wrong.",
        )
    if done_seen and not file_producing_seen:
        raise QueueUnavailable(
            "schema-drift",
            f"{done_seen} Done rows returned but NOT ONE survived the Task Type filter — "
            "the `Task Type` property has probably been renamed or its vocabulary changed.",
        )
    if file_producing_seen and not with_notes:
        raise QueueUnavailable(
            "schema-drift",
            f"{file_producing_seen} file-producing task(s) returned but NOT ONE had Execution "
            "Notes — this guard parses ONLY that property, so it would examine nothing.",
        )


def _not_measured(kind: str, detail: str) -> int:
    """Report an unmeasurable run as exit 3, never as a pass."""
    print(f"[SKIP:{kind}] {detail}")
    print("NOT A PASS — nothing was measured.")
    if kind == "no-access":
        print("  Fix: share the AI Work Queue database with this integration "
              "(Notion -> database -> ... -> Connections).")
    elif kind == "no-token":
        print("  Fix: export NOTION_TOKEN (CI maps secrets.NOTION_QUEUE_TOKEN to it).")
    return EXIT_NOT_MEASURED


def _rich_text(prop: Optional[Dict[str, Any]]) -> str:
    if not prop:
        return ""
    parts = prop.get("rich_text") or prop.get("title") or []
    return "".join(seg.get("plain_text", "") for seg in parts)


def _select(prop: Optional[Dict[str, Any]]) -> str:
    sel = (prop or {}).get("select")
    return (sel or {}).get("name", "") if sel else ""


def _unique_id(prop: Optional[Dict[str, Any]]) -> str:
    """Render a Notion unique_id property as ``<PREFIX>-<NUMBER>`` (e.g. AIQ-775)."""
    uid = (prop or {}).get("unique_id")
    if not uid:
        return ""
    prefix = uid.get("prefix") or ""
    number = uid.get("number")
    if number is None:
        return ""
    return f"{prefix}-{number}" if prefix else str(number)


def fetch_done_tasks(
    token: str, database_id: str
) -> Tuple[List[Dict[str, Any]], int, int, int]:
    """Query the AI Work Queue for Status=Done file-producing tasks and extract
    their deliverable paths. Paginated."""
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }
    tasks: List[Dict[str, Any]] = []
    done_seen = 0              # PRE-filter count, for the non-degeneracy canary
    file_producing_seen = 0    # survived the Task Type filter
    with_notes = 0             # ...and had a non-empty Execution Notes
    cursor: Optional[str] = None
    while True:
        body: Dict[str, Any] = {
            "filter": {"property": "Status", "select": {"equals": "Done"}},
            "page_size": 100,
        }
        if cursor:
            body["start_cursor"] = cursor
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))

        for page in payload.get("results", []):
            done_seen += 1
            props = page.get("properties", {})
            task_type = _select(props.get("Task Type"))
            if task_type and task_type not in _FILE_PRODUCING_TYPES:
                continue
            file_producing_seen += 1
            # Scan ONLY Execution Notes — the record of what was actually built
            # (CREATED:/MODIFIED: claims). Expected Output is the spec and is full
            # of *suggested* paths that get renamed on commit, which produced the
            # bulk of false positives on the first live run.
            note_text = _rich_text(props.get("Execution Notes"))
            if note_text.strip():
                with_notes += 1
            paths = extract_deliverable_paths(note_text)
            if not paths:
                continue
            tasks.append({
                # The title property of this database is `fable`, not "Task Title".
                "title": _rich_text(props.get("fable")),
                "aiq": _unique_id(props.get("ID")) or _rich_text(props.get("ID")),
                "url": page.get("url", ""),
                "paths": paths,
                # Carried so assert_non_degenerate can tell "we read the notes and they
                # held no paths" from "we never read the notes at all". Omitting this is
                # what made the canary fire on every healthy run.
                "notes": note_text,
            })

        if not payload.get("has_more"):
            break
        cursor = payload.get("next_cursor")
    # `done_seen` is the PRE-filter count. assert_non_degenerate needs it to tell
    # "no Done tasks produce files" (fine) from "the Task Type filter matched nothing
    # because the property was renamed" (blind).
    return tasks, done_seen, file_producing_seen, with_notes


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Assert Done-task deliverable paths exist on main."
    )
    parser.add_argument("--root", default=".", help="Repo root (default: cwd).")
    parser.add_argument("--database-id", default=_DEFAULT_DATABASE_ID,
                        help="AI Work Queue Notion database id.")
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 when a non-allowlisted missing deliverable is found.")
    args = parser.parse_args()

    token = os.environ.get("NOTION_TOKEN")
    if not token:
        return _not_measured("no-token", "NOTION_TOKEN is not set.")

    root = Path(args.root).resolve()
    allowlist = load_allowlist(root / "scripts" / "deliverable_integrity_allowlist.txt")
    tracked = tracked_files(root)

    # A shallow clone has no history, so `git log --all` returns almost nothing and
    # every deliverable would look like it never existed. Refuse rather than emit a
    # verdict we cannot support: `actions/checkout` must set `fetch-depth: 0`.
    if is_shallow(root):
        return _not_measured(
            "shallow-clone",
            "the clone is shallow, so git history is unavailable and every claimed "
            "deliverable would be reported as never-existing. Set `fetch-depth: 0` on "
            "actions/checkout for this job.",
        )
    ever_added = paths_ever_added(root)

    try:
        tasks, done_seen, fp_seen, with_notes = fetch_done_tasks(token, args.database_id)
        assert_non_degenerate(tasks, done_seen, fp_seen, with_notes)
    except QueueUnavailable as exc:
        return _not_measured(exc.kind, exc.detail)
    except urllib.error.HTTPError as exc:
        kind = "no-access" if exc.code in (401, 403, 404) else "unreachable"
        return _not_measured(kind, f"HTTP {exc.code} querying database {args.database_id}.")
    except urllib.error.URLError as exc:
        return _not_measured("unreachable", str(exc))

    missing, moved, mangled = check_tasks(tasks, tracked, allowlist, ever_added)

    print(f"Scanned {len(tasks)} Done file-producing task(s).")

    # Neither of these fails the build. They are reported because silently absorbing
    # them is how a guard stops telling you anything.
    if mangled:
        print(f"\n[WARN] {len(mangled)} claimed path(s) resolve only once Notion's eaten "
              f"underscores are restored. The file EXISTS; the card's path is mis-stored "
              f"because it was written without backticks (see CLAUDE.md):\n")
        for m in mangled:
            print(f"  {m['aiq'] or '(no id)'}  {m['path']}")
            print(f"      -> {m['resolved_to']}")
            print(f"      task: {m['title']}")
    if moved:
        print(f"\n[INFO] {len(moved)} claimed deliverable(s) are not present today but WERE "
              f"added at some point — the work shipped and the path later moved or was "
              f"removed. Not a failure:\n")
        for m in moved:
            print(f"  {m['aiq'] or '(no id)'}  {m['path']}")

    if not missing:
        print(f"\n[PASS] every claimed deliverable either exists today or existed once "
              f"({len(allowlist)} allowlisted).")
        return 0

    print(f"\n[{'FAIL' if args.strict else 'WARN'}] {len(missing)} claimed "
          f"deliverable(s) marked Done that NEVER existed in any commit on any branch "
          f"(allowlist in scripts/deliverable_integrity_allowlist.txt):\n")
    for m in missing:
        print(f"  {m['aiq'] or '(no id)'}  {m['path']}")
        print(f"      task: {m['title']}")
        print(f"      {m['url']}")
    print()
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
