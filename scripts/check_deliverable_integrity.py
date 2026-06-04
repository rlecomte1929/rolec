#!/usr/bin/env python3
"""
check_deliverable_integrity.py — deliverable-integrity guard (HYGIENE-1 / AIQ-786).

Catches the failure mode where a Work Queue task is marked **Done** claiming it
produced a repo file, but the file was authored in Cowork's ``outputs/`` and never
actually merged — so it doesn't exist for audit purposes. This bit us on the
AI-003 EU AI Act bundle (whole series sat in ``outputs/`` until a manual merge),
and is exactly the class of bug the C1-04a / P3-01c "phantom deliverable" notes
flag. See the 2026-06-04 Cowork handoff.

How it works:
  1. Pull every Done, file-producing task from the AI Work Queue (Notion) — or read
     them from ``--input`` (a JSON list) for offline / CI / test runs.
  2. Parse each task's Execution Notes for claimed repo paths:
       * ``CREATED: `<path>``` / ``MODIFIED: `<path>``` lines
       * any backtick-wrapped token that looks like a path
       * "move … (into|to) <path>" phrasing
  3. Assert each claimed path exists in the repo via ``git ls-files``.
  4. Print a MISSING report and exit non-zero if any claimed path is absent and
     not allowlisted.

A companion allowlist (``scripts/deliverable_integrity_allowlist.txt``, one path
per line, ``#`` comments) suppresses known/intentional gaps. As recommended in the
handoff, CI runs this with ``--report-only`` and a generous allowlist on day one so
historical noise doesn't block the lane — flip to enforcing once the allowlist drains.

Exit codes (default / enforcing mode):
  0 — every claimed path exists or is allowlisted (or there are no tasks)
  1 — at least one claimed path is missing and not allowlisted
  2 — could not reach Notion / query failed (unexpected — investigate)

Usage:
  # offline (tests, fixtures, CI report-only):
  python scripts/check_deliverable_integrity.py --input tasks.json
  python scripts/check_deliverable_integrity.py --input tasks.json --report-only

  # live (needs a Notion integration token with read access to the queue DB):
  NOTION_QUEUE_TOKEN=secret_... python scripts/check_deliverable_integrity.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST_FILE = REPO_ROOT / "scripts" / "deliverable_integrity_allowlist.txt"

# AI Work Queue database id (see CLAUDE.md "Audit remediation workflow").
DEFAULT_QUEUE_DB_ID = "7adc643a-c448-4a1a-ba80-e27e417f42d6"
NOTION_VERSION = "2022-06-28"

# ---------------------------------------------------------------------------
# Path extraction (pure — this is the unit-tested core)
# ---------------------------------------------------------------------------

# A token looks like a repo path if it is made only of path-safe characters and
# either contains a "/" or has a file extension on its last segment. We exclude
# obvious non-paths (urls, shell snippets, SQL) so backticked commands like
# `git ls-files` or `SELECT ...` don't get treated as deliverables.
_PATH_SAFE = re.compile(r"^[A-Za-z0-9._/\-]+$")
_HAS_EXT = re.compile(r"\.[A-Za-z0-9]{1,8}$")

# `CREATED: \`path\`` / `MODIFIED: \`path\`` (the Execution Notes template shape).
_LABELLED = re.compile(
    r"\b(?:CREATED|MODIFIED|ADDED|NEW|UPDATED)\b\s*:?\s*`([^`]+)`",
    re.IGNORECASE,
)
# "move <x> into|to <path>" — capture the destination path token.
_MOVE = re.compile(
    r"\bmov(?:e|ed|ing)\b[^`]*?\b(?:into|to)\s+`?([A-Za-z0-9._/\-]+/?)`?",
    re.IGNORECASE,
)
# Any backtick-wrapped token.
_BACKTICK = re.compile(r"`([^`]+)`")


def _looks_like_path(token: str) -> bool:
    token = token.strip()
    if not token or token.startswith("-"):  # flags, ranges
        return False
    if "://" in token or token.startswith("http"):  # urls
        return False
    if not _PATH_SAFE.match(token):  # spaces, SQL, shell pipes, etc.
        return False
    last = token.rstrip("/").split("/")[-1]
    return ("/" in token) or bool(_HAS_EXT.search(last))


def extract_paths(notes: str) -> list[str]:
    """Extract claimed repo paths from a task's Execution Notes.

    Pure and deterministic. Returns a de-duplicated, sorted list. Trailing
    punctuation (``.``/``,``) is stripped; directory paths keep a trailing ``/``.
    """
    if not notes:
        return []
    found: set[str] = set()

    for m in _LABELLED.finditer(notes):
        token = m.group(1).strip().rstrip(".,;)")
        if _looks_like_path(token):
            found.add(token)

    for m in _MOVE.finditer(notes):
        token = m.group(1).strip().rstrip(".,;)")
        # keep a trailing slash if it was a directory destination
        if _looks_like_path(token) or token.endswith("/"):
            found.add(token)

    for m in _BACKTICK.finditer(notes):
        token = m.group(1).strip().rstrip(".,;)")
        if _looks_like_path(token):
            found.add(token)

    return sorted(found)


# ---------------------------------------------------------------------------
# Existence check against the git index (pure given the tracked set)
# ---------------------------------------------------------------------------


def path_present(path: str, tracked: set[str]) -> bool:
    """True if ``path`` is tracked by git.

    A path ending in ``/`` is a directory claim — satisfied if *any* tracked
    file lives under it. A file claim must match a tracked path exactly.
    """
    p = path.rstrip("/")
    if path.endswith("/"):
        prefix = p + "/"
        return any(t.startswith(prefix) for t in tracked)
    return p in tracked


def find_missing(
    tasks: Iterable[dict], tracked: set[str], allowlist: set[str]
) -> list[dict]:
    """Return [{task, title, path}] for every claimed path that is absent and
    not allowlisted."""
    missing: list[dict] = []
    for task in tasks:
        notes = task.get("notes") or task.get("execution_notes") or ""
        for path in extract_paths(notes):
            if path in allowlist or path.rstrip("/") in allowlist:
                continue
            if not path_present(path, tracked):
                missing.append(
                    {
                        "task": task.get("id", "?"),
                        "title": task.get("title", ""),
                        "path": path,
                    }
                )
    return missing


# ---------------------------------------------------------------------------
# I/O — allowlist, git, Notion
# ---------------------------------------------------------------------------


def load_allowlist(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out: set[str] = set()
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            out.add(line.rstrip("/"))
    return out


def git_tracked_files() -> set[str]:
    out = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return {line.strip() for line in out.stdout.splitlines() if line.strip()}


def _notion_query(token: str, db_id: str) -> list[dict]:
    """Fetch Done, file-producing tasks from the AI Work Queue via the Notion API.

    Stdlib-only (urllib). Returns [{id, title, notes}]. Best-effort on property
    names — the Execution Notes / Status property names must match the live DB.
    """
    import urllib.error
    import urllib.request

    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    payload = {
        "filter": {"property": "Status", "status": {"equals": "Done"}},
        "page_size": 100,
    }

    results: list[dict] = []
    cursor: str | None = None
    while True:
        body = dict(payload)
        if cursor:
            body["start_cursor"] = cursor
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.URLError as exc:
            print(f"[deliverable-integrity] Notion query failed: {exc}", file=sys.stderr)
            sys.exit(2)

        for page in data.get("results", []):
            props = page.get("properties", {})
            results.append(
                {
                    "id": _plain_text(props.get("Task ID") or props.get("ID"))
                    or page.get("id", "?"),
                    "title": _plain_text(props.get("Task Title") or props.get("Name")),
                    "notes": _plain_text(props.get("Execution Notes")),
                }
            )

        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    return results


def _plain_text(prop: object) -> str:
    """Flatten a Notion property value to plain text (title/rich_text/select)."""
    if not isinstance(prop, dict):
        return ""
    for key in ("title", "rich_text"):
        if key in prop:
            return "".join(rt.get("plain_text", "") for rt in prop.get(key, []))
    if "select" in prop and prop["select"]:
        return prop["select"].get("name", "")
    return ""


def load_tasks(args: argparse.Namespace) -> list[dict]:
    if args.input:
        data = json.loads(Path(args.input).read_text())
        return data if isinstance(data, list) else data.get("tasks", [])
    token = os.environ.get("NOTION_QUEUE_TOKEN")
    if not token:
        print(
            "[deliverable-integrity] no --input and NOTION_QUEUE_TOKEN not set — "
            "nothing to check (skipping).",
            file=sys.stderr,
        )
        sys.exit(0)
    return _notion_query(token, args.db_id)


# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="Deliverable-integrity guard (HYGIENE-1).")
    ap.add_argument(
        "--input",
        help="JSON file of tasks [{id,title,notes}] to check instead of querying Notion.",
    )
    ap.add_argument("--db-id", default=DEFAULT_QUEUE_DB_ID, help="Notion queue DB id.")
    ap.add_argument("--allowlist", type=Path, default=ALLOWLIST_FILE)
    ap.add_argument(
        "--report-only",
        action="store_true",
        help="Print the report but always exit 0 (day-one CI posture).",
    )
    ap.add_argument("--json", action="store_true", help="Emit the report as JSON.")
    args = ap.parse_args()

    tasks = load_tasks(args)
    tracked = git_tracked_files()
    allowlist = load_allowlist(args.allowlist)
    missing = find_missing(tasks, tracked, allowlist)

    if args.json:
        print(json.dumps({"missing": missing, "pass": not missing}, indent=2))
    else:
        print(f"[deliverable-integrity] tasks checked: {len(tasks)}")
        print(f"[deliverable-integrity] allowlist entries: {len(allowlist)}")
        if missing:
            print(
                f"\n[deliverable-integrity] {'WARN' if args.report_only else 'FAIL'} — "
                f"{len(missing)} claimed deliverable(s) not found in the repo:"
            )
            for m in missing:
                print(f"  - {m['path']}   (task {m['task']}: {m['title']})")
            print(
                "\nFix path:\n"
                "  1. Merge the file into the repo (it likely still lives in Cowork outputs/), OR\n"
                "  2. Correct the path claimed in the task's Execution Notes, OR\n"
                "  3. If the gap is intentional/known, add the path to\n"
                f"     {args.allowlist.name} with a comment explaining why.\n"
            )
        else:
            print("\n[deliverable-integrity] PASS — every claimed deliverable exists or is allowlisted.")

    if args.report_only:
        return 0
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
