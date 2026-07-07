#!/usr/bin/env python3
"""
notion_ready_queue.py — deterministic "Ready for AI" reader for the AI Work Queue.

The connected Notion MCP can fetch ONE page by id or do semantic search, but it
CANNOT filter/list rows by Status or AIQ-ID. That makes the /relopass-dev-queue
Phase-1 step ("query Status = Ready for AI, rank P0>P1>P2>P3, lowest complexity
first") impossible — the agent has to guess via semantic search, which mixes in
Done/in-review tasks. This script closes that gap by querying the Notion REST API
directly (the same auth the deliverable-integrity guard uses), filtering
server-side, and printing a deterministically ranked list.

Stdlib only (urllib). Read-only — never writes to Notion.

Usage:
  NOTION_QUEUE_TOKEN=secret_... python scripts/notion_ready_queue.py
  NOTION_QUEUE_TOKEN=secret_... python scripts/notion_ready_queue.py --next
  NOTION_QUEUE_TOKEN=secret_... python scripts/notion_ready_queue.py --status "Human Review" --json

Exit codes:
  0 — query succeeded (even if zero tasks)
  2 — NOTION_QUEUE_TOKEN not set, or the Notion query failed
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

# AI Work Queue (see CLAUDE.md "Audit remediation workflow" + the dev-queue skill).
# Mirrors scripts/check_deliverable_integrity.py's Notion access (same token/version/db).
QUEUE_DB_ID = "7adc643a-c448-4a1a-ba80-e27e417f42d6"
NOTION_VERSION = "2022-06-28"

# Ranking: P0 first, then by ascending complexity (Trivial easiest). Unknown → last.
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
COMPLEXITY_ORDER = {"Trivial": 0, "Low": 1, "Medium": 2, "High": 3, "Very High": 4}


def _plain_text(prop: object) -> str:
    """Flatten a Notion property value to plain text (title / rich_text / select)."""
    if not isinstance(prop, dict):
        return ""
    for key in ("title", "rich_text"):
        if key in prop:
            return "".join(rt.get("plain_text", "") for rt in prop.get(key, []) or [])
    if prop.get("select"):
        return prop["select"].get("name", "")
    return ""


def _unique_id(prop: object) -> str:
    """Render a Notion unique_id property as 'PREFIX-NUMBER' (e.g. AIQ-853)."""
    if isinstance(prop, dict) and isinstance(prop.get("unique_id"), dict):
        uid = prop["unique_id"]
        num = uid.get("number")
        if num is None:
            return ""
        prefix = uid.get("prefix")
        return f"{prefix}-{num}" if prefix else str(num)
    return ""


def _aiq_sort_key(task: dict) -> int:
    """Numeric AIQ id for stable secondary ordering (missing → large)."""
    raw = (task.get("aiq") or "").rsplit("-", 1)[-1]
    return int(raw) if raw.isdigit() else 1_000_000_000


def query_queue(token: str, status: str, db_id: str = QUEUE_DB_ID) -> list[dict]:
    """Return all queue rows whose Status select == ``status`` (paginated)."""
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    # "Status" is a SELECT property in this DB (a separate "Task Status" is the
    # status-type one). Filter on the select.
    payload = {
        "filter": {"property": "Status", "select": {"equals": status}},
        "page_size": 100,
    }

    rows: list[dict] = []
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
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace") if hasattr(exc, "read") else ""
            print(f"[ready-queue] Notion query failed: {exc} {detail}", file=sys.stderr)
            sys.exit(2)
        except urllib.error.URLError as exc:
            print(f"[ready-queue] Notion query failed: {exc}", file=sys.stderr)
            sys.exit(2)

        for page in data.get("results", []):
            props = page.get("properties", {})
            rows.append(
                {
                    "aiq": _unique_id(props.get("ID") or props.get("userDefined:ID")),
                    "page_id": page.get("id", ""),
                    "title": _plain_text(props.get("Task Title") or props.get("Name")),
                    "priority": _plain_text(props.get("Priority")),
                    "complexity": _plain_text(props.get("Estimated Complexity")),
                    "autonomy_tier": _plain_text(props.get("Autonomy Tier")),
                    "task_type": _plain_text(props.get("Task Type")),
                    "status": _plain_text(props.get("Status")),
                    "dependencies": _plain_text(props.get("Dependencies")),
                    "url": page.get("url", ""),
                }
            )

        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    return rows


def rank(tasks: list[dict]) -> list[dict]:
    """P0>P1>P2>P3, then easiest complexity first, then ascending AIQ id."""
    return sorted(
        tasks,
        key=lambda t: (
            PRIORITY_ORDER.get(t.get("priority", ""), 99),
            COMPLEXITY_ORDER.get(t.get("complexity", ""), 99),
            _aiq_sort_key(t),
        ),
    )


# The Claude Code agent lane (Autopilot Phase 3) handles the slice the headless Haiku
# pipeline cannot: Medium/High complexity, on the 🟢/🟡 autonomy tiers only. Trivial/Low go
# to the headless lane; Very High → decomposition; 🔴 Red is never auto-dispatched to an agent.
_CC_COMPLEXITY = {"Medium", "High"}


def cc_eligible(task: dict) -> bool:
    tier = task.get("autonomy_tier", "") or ""
    if "🔴" in tier or "Red" in tier:
        return False
    if not any(m in tier for m in ("🟢", "🟡", "Green", "Yellow")):
        return False
    return task.get("complexity") in _CC_COMPLEXITY


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="List AI Work Queue tasks by status, ranked.")
    ap.add_argument("--status", default="Ready for AI", help='Status to filter on (default: "Ready for AI")')
    ap.add_argument("--next", action="store_true", help="Print only the single top-ranked task.")
    ap.add_argument("--cc-next", action="store_true",
                    help="Print (JSON) the top Ready-for-AI task eligible for the Claude Code "
                         "agent lane (🟢/🟡 tier, Medium/High complexity). Empty JSON if none.")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of a table.")
    args = ap.parse_args(argv)

    token = os.environ.get("NOTION_QUEUE_TOKEN")
    if not token:
        print(
            "[ready-queue] NOTION_QUEUE_TOKEN not set. Create a Notion internal "
            "integration with read access to the AI Work Queue DB and export it as "
            "NOTION_QUEUE_TOKEN (same token the deliverable-integrity guard uses).",
            file=sys.stderr,
        )
        return 2

    tasks = rank(query_queue(token, args.status))

    if args.cc_next:
        eligible = [t for t in tasks if cc_eligible(t)]
        top = eligible[0] if eligible else None
        print(json.dumps(
            {"aiq": top["aiq"], "page_id": top["page_id"], "title": top["title"], "url": top["url"],
             "autonomy_tier": top["autonomy_tier"], "complexity": top["complexity"]}
            if top else {}
        ))
        return 0

    if args.next:
        if not tasks:
            print(f"[ready-queue] no tasks with Status={args.status!r}.", file=sys.stderr)
            return 0
        t = tasks[0]
        print(f"{t['aiq']} | {t['title']} | {t['url']}")
        return 0

    if args.json:
        print(json.dumps(tasks, indent=2))
        return 0

    if not tasks:
        print(f"No tasks with Status={args.status!r}.")
        return 0
    print(f"{len(tasks)} task(s) with Status={args.status!r} (ranked):\n")
    for t in tasks:
        deps = f"  deps: {t['dependencies']}" if t["dependencies"] else ""
        print(
            f"  {t['aiq'] or '?':<10} {t['priority'] or '--':<3} "
            f"{t['complexity'] or '--':<10} {t['task_type'] or '--':<26} {t['title']}"
        )
        print(f"             {t['url']}{deps}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
