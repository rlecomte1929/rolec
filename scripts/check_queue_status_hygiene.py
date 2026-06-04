#!/usr/bin/env python3
"""
check_queue_status_hygiene.py — assert that no AI Work Queue task is left
"Ready for AI" while a task it depends on is not yet "Done".

Why: blocked tasks that stay at ``Ready for AI`` keep getting re-selected as
"next up" on every queue run (false-ready), wasting a pick each time and risking
work that can't actually be completed. The relopass-dev-queue skill already says
to set such tasks to ``Blocked``; this guard enforces that discipline so drift is
caught automatically rather than relied on per-run. Sibling of
``check_deliverable_integrity.py`` (HYGIENE-1); this is HYGIENE-2.

How: query the whole AI Work Queue, build a ``tag -> Status`` map from each
task's title prefix (e.g. ``P3-01d``), then for every ``Ready for AI`` task parse
its ``Dependencies`` field for referenced task tags and flag the task when any
referenced tag exists in the queue but is not ``Done``. A drain-over-time
allowlist (``scripts/queue_status_allowlist.txt``) suppresses known-acceptable
cases (a dependency intentionally tracked elsewhere, a deliberate staging order).

Scope (deliberately conservative — high signal, low false-positive):
  * Only flags dependencies that resolve to a KNOWN task tag in the queue. Prose
    / data preconditions (e.g. "needs >=20 closed cases") are NOT auto-detected —
    they remain the agent's judgement call, by design.

Modes:
  * default  — report-only: print findings, exit 0.
  * --strict — exit 1 when any non-allowlisted false-ready task is found.

Notion access: reads ``NOTION_TOKEN`` from the environment. When unset the check
is SKIPPED with a notice and exits 0 (the CI job is gated on
``vars.NOTION_QUEUE_TOKEN_SET`` so the token is present when it actually runs).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# AI Work Queue (Notion). Database id from references/notion-schema.md.
_DEFAULT_DATABASE_ID = "7adc643a-c448-4a1a-ba80-e27e417f42d6"
_NOTION_VERSION = "2022-06-28"

_READY_STATUS = "Ready for AI"
_DONE_STATUS = "Done"

# A task tag like P3-01, P3-01d, P1-07, or a follow-up P3-01b-FU3. The leading
# tag of a Task Title and the references inside a Dependencies field share this
# shape. Case-insensitive on the FU suffix; tags are normalised upper-case.
_TAG_RE = re.compile(r"\bP\d+-\d+[a-z]?(?:-FU\d+)?\b", re.IGNORECASE)

# A line in Execution Notes that declares the task blocked — the agent wrote a
# "Blocked" marker but left Status at "Ready for AI". Matches a line that STARTS
# (after optional markdown ``#``/``-`` and whitespace) with "Blocked", so a
# mid-sentence "unblocks X" or "no longer blocked" prose does not false-positive.
# This catches the data/precondition class (e.g. P3-01d "## Blocked — needs >=20
# closed cases") that a task-dependency scan cannot, since the blocker is prose,
# not a not-Done task tag.
_BLOCKED_MARKER_RE = re.compile(r"(?im)^\s*#*\s*-?\s*blocked\b")


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested without network)                                  #
# --------------------------------------------------------------------------- #


def parse_title_tag(title: str) -> Optional[str]:
    """Return the leading task tag of a Task Title, or None.

    Titles look like ``P3-01d · Build …`` or ``[P1-3] Trigger Engine``. We take
    the first tag token that appears, normalised upper-case.
    """
    m = _TAG_RE.search(title or "")
    return m.group(0).upper() if m else None


def parse_dependency_tags(dependencies: str) -> List[str]:
    """Return the task tags referenced in a Dependencies field (order-preserving,
    de-duplicated, upper-cased). Free-text prose around the tags is ignored."""
    seen: Set[str] = set()
    out: List[str] = []
    for m in _TAG_RE.finditer(dependencies or ""):
        tag = m.group(0).upper()
        if tag not in seen:
            seen.add(tag)
            out.append(tag)
    return out


def has_blocked_marker(notes: str) -> bool:
    """True when Execution Notes declare the task blocked (a line starting with
    "Blocked"). High-signal for the data/precondition class of false-ready."""
    return bool(_BLOCKED_MARKER_RE.search(notes or ""))


def find_false_ready(
    tasks: List[Dict[str, Any]],
    allowlist: Set[str],
) -> List[Dict[str, Any]]:
    """Return Ready-for-AI tasks that should be Blocked.

    Each task dict has: ``tag``, ``title``, ``aiq``, ``url``, ``status``,
    ``dependencies`` (raw text), ``notes`` (Execution Notes). A Ready-for-AI task
    is flagged when EITHER:
      * a dependency tag resolves to a known task whose status is not ``Done``
        (``unmet`` lists the offending edges), OR
      * its Execution Notes contain a "Blocked" marker line (``notes_blocked``).
    Allowlist keys: bare ``<TAG>`` (suppress the whole task) or ``<TAG>:<DEP_TAG>``
    (suppress one blocking edge).
    """
    status_by_tag: Dict[str, str] = {}
    for t in tasks:
        tag = t.get("tag")
        if tag:
            status_by_tag[tag] = t.get("status") or ""

    flagged: List[Dict[str, Any]] = []
    for t in tasks:
        if (t.get("status") or "") != _READY_STATUS:
            continue
        tag = t.get("tag") or ""
        if tag in allowlist:
            continue
        unmet: List[str] = []
        for dep in parse_dependency_tags(t.get("dependencies") or ""):
            if dep == tag:  # self-edge (e.g. a "-followup" sharing its parent's tag) — skip
                continue
            dep_status = status_by_tag.get(dep)
            if dep_status is None:  # dependency not a known queue task — skip
                continue
            if dep_status == _DONE_STATUS:
                continue
            if f"{tag}:{dep}" in allowlist:
                continue
            unmet.append(f"{dep} [{dep_status or 'unknown'}]")
        notes_blocked = has_blocked_marker(t.get("notes") or "")
        if unmet or notes_blocked:
            flagged.append({
                "tag": tag,
                "aiq": str(t.get("aiq") or ""),
                "title": str(t.get("title") or ""),
                "url": str(t.get("url") or ""),
                "unmet": unmet,
                "notes_blocked": notes_blocked,
            })
    return flagged


def load_allowlist(path: Path) -> Set[str]:
    """Comment-aware allowlist loader (``#`` comments + blank lines ignored)."""
    if not path.exists():
        return set()
    out: Set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            out.add(line)
    return out


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


def fetch_all_tasks(token: str, database_id: str) -> List[Dict[str, Any]]:
    """Query the whole AI Work Queue and extract the fields the guard needs."""
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }
    tasks: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    while True:
        body: Dict[str, Any] = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))

        for page in payload.get("results", []):
            props = page.get("properties", {})
            title = _rich_text(props.get("Task Title"))
            tasks.append({
                "tag": parse_title_tag(title),
                "title": title,
                "aiq": _rich_text(props.get("ID")) or str(props.get("ID", "")),
                "url": page.get("url", ""),
                "status": _select(props.get("Status")),
                "dependencies": _rich_text(props.get("Dependencies")),
                "notes": _rich_text(props.get("Execution Notes")),
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
        description="Flag Ready-for-AI tasks blocked by a not-Done dependency."
    )
    parser.add_argument("--root", default=".", help="Repo root (default: cwd).")
    parser.add_argument("--database-id", default=_DEFAULT_DATABASE_ID,
                        help="AI Work Queue Notion database id.")
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 when a non-allowlisted false-ready task is found.")
    args = parser.parse_args()

    token = os.environ.get("NOTION_TOKEN")
    if not token:
        print("[SKIP] NOTION_TOKEN not set — queue-status-hygiene check skipped.")
        return 0

    root = Path(args.root).resolve()
    allowlist = load_allowlist(root / "scripts" / "queue_status_allowlist.txt")

    try:
        tasks = fetch_all_tasks(token, args.database_id)
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"[WARN] Notion query failed ({exc}); skipping (exit 0).")
        return 0

    flagged = find_false_ready(tasks, allowlist)

    print(f"Scanned {len(tasks)} task(s).")
    if not flagged:
        print(f"[PASS] no false-ready tasks ({len(allowlist)} allowlisted).")
        return 0

    print(f"\n[{'FAIL' if args.strict else 'WARN'}] {len(flagged)} 'Ready for AI' "
          f"task(s) blocked by a not-Done dependency "
          f"(allowlist in scripts/queue_status_allowlist.txt) — "
          f"set these to 'Blocked':\n")
    for f in flagged:
        reasons = list(f["unmet"])
        if f.get("notes_blocked"):
            reasons.append("notes say 'Blocked'")
        print(f"  {f['tag'] or f['aiq'] or '(no tag)'}  {', '.join(reasons)}")
        print(f"      task: {f['title']}")
        print(f"      {f['url']}")
    print()
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
