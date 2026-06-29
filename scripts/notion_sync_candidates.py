#!/usr/bin/env python3
"""
Sync E2E campaign failures into the Notion "AI Work Queue" — deterministically.

After a campaign run, `campaign_scorer.py` writes `campaign_report_*.json` with a
`notion_candidates[]` list (P0/P1 regressions + notion_worthy failures). This
script creates a Work Queue task for each candidate that doesn't have one yet, and
updates the existing one otherwise — no LLM, just the Notion REST API. It is the
CI-friendly counterpart to the `relopass-bug-triage` skill.

Idempotent + conservative:
  - De-dup by the test_id embedded in the task title (`[<test_id>] …`), so re-runs
    UPDATE rather than duplicate.
  - On update it appends a run note; it reopens Status to "Ready for AI" ONLY if the
    task is in a terminal state (Done/Rejected/Archived) — i.e. a real regression —
    otherwise it leaves a human-set Status untouched.

SAFE BY DEFAULT: --dry-run (prints the plan). Pass --apply to write to Notion.

Usage:
  NOTION_QUEUE_TOKEN=secret_xxx python3 scripts/notion_sync_candidates.py \
      [--report results/campaign_report_<ts>.json] [--run-url URL] [--apply]
"""
import argparse
import glob
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

QUEUE_DB_ID = "7adc643a-c448-4a1a-ba80-e27e417f42d6"
NOTION_VERSION = "2022-06-28"
API = "https://api.notion.com/v1"
TERMINAL = {"Done", "Rejected", "Archived"}
REPO_ROOT = Path(__file__).resolve().parent.parent


def _req(method, url, token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit(f"Notion {method} {url} → {e.code}: {e.read().decode()[:400]}")


def _title_text(page, title_prop):
    parts = page.get("properties", {}).get(title_prop, {}).get("title", [])
    return "".join(p.get("plain_text", "") for p in parts)


def _status_of(page):
    s = page.get("properties", {}).get("Status", {}).get("select")
    return s.get("name") if s else None


def latest_report():
    files = sorted(glob.glob(str(REPO_ROOT / "results" / "campaign_report_*.json")))
    return files[-1] if files else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=None, help="campaign_report_*.json (default: latest)")
    ap.add_argument("--run-url", default=os.environ.get("RUN_URL", ""), help="CI run URL for the note")
    ap.add_argument("--apply", action="store_true", help="write to Notion (default: dry-run)")
    args = ap.parse_args()

    token = os.environ.get("NOTION_QUEUE_TOKEN")
    if not token:
        sys.exit("NOTION_QUEUE_TOKEN not set")

    report_path = args.report or latest_report()
    if not report_path or not os.path.exists(report_path):
        sys.exit("no campaign_report_*.json found (run campaign_scorer.py first)")
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    candidates = report.get("notion_candidates", []) or []
    if not candidates:
        print("✔ no notion_candidates to sync (clean run)")
        return

    # discover the title property name (type == 'title') — robust to "Task Title" vs "Name"
    db = _req("GET", f"{API}/databases/{QUEUE_DB_ID}", token)
    title_prop = next((n for n, p in db.get("properties", {}).items() if p.get("type") == "title"), "Name")
    has_priority = db.get("properties", {}).get("Priority", {}).get("type") == "select"
    has_notes = db.get("properties", {}).get("Execution Notes", {}).get("type") == "rich_text"

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    created = updated = skipped = 0

    for c in candidates:
        tid, title = c.get("test_id"), c.get("title", "")
        if not tid:
            continue
        note = f"[E2E Sentinel {stamp}] {c.get('status')} — {c.get('reason')} (domain: {c.get('domain')}). {args.run_url}".strip()

        # de-dup: find an existing task whose title contains the test_id
        q = _req("POST", f"{API}/databases/{QUEUE_DB_ID}/query", token,
                 {"filter": {"property": title_prop, "title": {"contains": tid}}, "page_size": 5})
        match = next((p for p in q.get("results", []) if tid in _title_text(p, title_prop)), None)

        if match:
            cur = _status_of(match)
            reopen = cur in TERMINAL
            props = {}
            if has_notes:
                prev = "".join(t.get("plain_text", "") for t in
                               match.get("properties", {}).get("Execution Notes", {}).get("rich_text", []))
                merged = (note + "\n" + prev)[:1900]
                props["Execution Notes"] = {"rich_text": [{"type": "text", "text": {"content": merged}}]}
            if reopen:
                props["Status"] = {"select": {"name": "Ready for AI"}}
            verb = "UPDATE+REOPEN" if reopen else "UPDATE"
            print(f"  {verb:14} [{tid}] (status={cur}) → {_title_text(match, title_prop)[:50]}")
            if args.apply and props:
                _req("PATCH", f"{API}/pages/{match['id']}", token, {"properties": props})
            updated += 1
        else:
            props = {title_prop: {"title": [{"text": {"content": f"[{tid}] {title}"[:200]}}]},
                     "Status": {"select": {"name": "Ready for AI"}}}
            if has_priority and c.get("priority") in ("P0", "P1", "P2", "P3"):
                props["Priority"] = {"select": {"name": c["priority"]}}
            if has_notes:
                props["Execution Notes"] = {"rich_text": [{"type": "text", "text": {"content": note[:1900]}}]}
            print(f"  CREATE         [{tid}] {c.get('priority')} {title[:50]}")
            if args.apply:
                _req("POST", f"{API}/pages", token, {"parent": {"database_id": QUEUE_DB_ID}, "properties": props})
            created += 1

    mode = "APPLIED" if args.apply else "DRY-RUN (use --apply to write)"
    print(f"\n{mode}: {created} create, {updated} update, {skipped} skip "
          f"(of {len(candidates)} candidates) → title property '{title_prop}'")


if __name__ == "__main__":
    main()
