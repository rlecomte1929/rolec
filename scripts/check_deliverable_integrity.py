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
from typing import Any, Dict, List, Optional, Set

# AI Work Queue (Notion). Database id from references/notion-schema.md.
_DEFAULT_DATABASE_ID = "7adc643a-c448-4a1a-ba80-e27e417f42d6"
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


def check_tasks(
    tasks: List[Dict[str, Any]],
    tracked_files: Set[str],
    allowlist: Set[str],
) -> List[Dict[str, str]]:
    """Return the list of missing deliverables (one per task+path).

    A task dict has: ``title``, ``aiq``, ``url``, ``paths`` (list[str]). A path
    is "missing" when it is not a tracked file and neither the bare path nor the
    ``<aiq>:<path>`` key is allowlisted.
    """
    missing: List[Dict[str, str]] = []
    for t in tasks:
        aiq = str(t.get("aiq") or "")
        for path in t.get("paths") or []:
            if path in tracked_files:
                continue
            if path in allowlist or f"{aiq}:{path}" in allowlist:
                continue
            missing.append({
                "aiq": aiq,
                "title": str(t.get("title") or ""),
                "path": path,
                "url": str(t.get("url") or ""),
            })
    return missing


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


def fetch_done_tasks(token: str, database_id: str) -> List[Dict[str, Any]]:
    """Query the AI Work Queue for Status=Done file-producing tasks and extract
    their deliverable paths. Paginated."""
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }
    tasks: List[Dict[str, Any]] = []
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
            props = page.get("properties", {})
            task_type = _select(props.get("Task Type"))
            if task_type and task_type not in _FILE_PRODUCING_TYPES:
                continue
            # Scan ONLY Execution Notes — the record of what was actually built
            # (CREATED:/MODIFIED: claims). Expected Output is the spec and is full
            # of *suggested* paths that get renamed on commit, which produced the
            # bulk of false positives on the first live run.
            note_text = _rich_text(props.get("Execution Notes"))
            paths = extract_deliverable_paths(note_text)
            if not paths:
                continue
            tasks.append({
                "title": _rich_text(props.get("Task Title")),
                "aiq": _unique_id(props.get("ID")) or _rich_text(props.get("ID")),
                "url": page.get("url", ""),
                "paths": paths,
            })

        if not payload.get("has_more"):
            break
        cursor = payload.get("next_cursor")
    return tasks


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
        print("[SKIP] NOTION_TOKEN not set — deliverable-integrity check skipped.")
        return 0

    root = Path(args.root).resolve()
    allowlist = load_allowlist(root / "scripts" / "deliverable_integrity_allowlist.txt")
    tracked = tracked_files(root)

    try:
        tasks = fetch_done_tasks(token, args.database_id)
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"[WARN] Notion query failed ({exc}); skipping (exit 0).")
        return 0

    missing = check_tasks(tasks, tracked, allowlist)

    print(f"Scanned {len(tasks)} Done file-producing task(s).")
    if not missing:
        print(f"[PASS] every claimed deliverable is a tracked file "
              f"({len(allowlist)} allowlisted).")
        return 0

    print(f"\n[{'FAIL' if args.strict else 'WARN'}] {len(missing)} claimed "
          f"deliverable(s) marked Done but NOT in the repo "
          f"(allowlist in scripts/deliverable_integrity_allowlist.txt):\n")
    for m in missing:
        print(f"  {m['aiq'] or '(no id)'}  {m['path']}")
        print(f"      task: {m['title']}")
        print(f"      {m['url']}")
    print()
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
