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
  - A GREEN (passing) run NEVER resurrects a human-closed task: on a healthy run a
    terminal task is skipped entirely (no reopen, no note). This closes the
    AIQ-1377 loop where a single transient flap on an otherwise-passing deploy-window
    run re-opened a Done P0 (the sentinel job is `continue-on-error`, so its
    conclusion is always "success" and can't gate this — the report health band can).

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


def terminal_action(cur_status, health_band, confirmed=True):
    """Decide what to do with an EXISTING matched task, given the run's health band
    and whether the failure is CONFIRMED (it also failed the previous campaign run).

    Returns one of:
      - "skip"      terminal (human-closed) task on a GREEN/passing run → do nothing.
                    A healthy run has no real regression to justify resurrecting a
                    human's Done/Rejected/Archived decision (the AIQ-1377 re-open loop).
      - "reopen"    terminal task on a non-passing run (AMBER/RED/INCONCLUSIVE/unknown)
                    whose failure is CONFIRMED → a genuine regression; flip Status back
                    to "Ready for AI" + note.
      - "hold"      terminal task on a non-passing run whose failure is NOT confirmed
                    (first-seen, or no baseline to compare against) → do NOT resurrect a
                    human's Done decision on a single unverifiable flap. Reopening is
                    fail-CLOSED (AIQ-1738: the AIQ-1375 deploy-window recurrence); it
                    reopens next run only if the failure recurs. New-task *filing* stays
                    fail-open — that policy lives in the caller, not here.
      - "note-only" already-open task → just append the run note, leave Status alone.

    ``confirmed`` defaults True so callers that don't use the confirm-twice gate (legacy /
    manual runs) keep the prior reopen-on-any-non-GREEN behaviour. Unknown/missing band is
    still treated as non-passing so a *confirmed* regression is never silently dropped.
    """
    if cur_status in TERMINAL:
        if health_band == "GREEN":
            return "skip"
        return "reopen" if confirmed else "hold"
    return "note-only"


def latest_report():
    files = sorted(glob.glob(str(REPO_ROOT / "results" / "campaign_report_*.json")))
    return files[-1] if files else None


# ── Confirm-twice gate ──────────────────────────────────────────────────────────
# A deploy-window transient is tied to ONE deploy window and rarely fails two
# consecutive campaign runs; a real bug persists. Only file a candidate if it ALSO
# failed last run. Fail-open: with no valid previous state, file normally so broken
# artifact plumbing degrades to today's behaviour rather than masking real bugs.
def load_prev_ids(path):
    """Return (set_of_failed_ids, have_prev). have_prev is False on any missing/corrupt
    state so the caller fails open."""
    try:
        if not path or not os.path.exists(path):
            return set(), False
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        ids = data.get("failed_ids") if isinstance(data, dict) else data
        return set(ids or []), True
    except Exception:
        return set(), False


def write_state(path, candidates):
    """Persist this run's candidate test_ids for next run's confirm-twice comparison."""
    ids = sorted({c.get("test_id") for c in candidates if c.get("test_id")})
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps({
        "failed_ids": ids,
        "written_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2), encoding="utf-8")


def filter_confirmed(candidates, prev_ids, have_prev):
    """Split candidates into (to_file, held). Without a previous run to compare against
    (have_prev False), file everything (fail-open). Otherwise file only the ids that
    also failed last run; hold the rest for next-run confirmation."""
    if not have_prev:
        return list(candidates), []
    to_file = [c for c in candidates if c.get("test_id") in prev_ids]
    held = [c for c in candidates if c.get("test_id") not in prev_ids]
    return to_file, held


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=None, help="campaign_report_*.json (default: latest)")
    ap.add_argument("--run-url", default=os.environ.get("RUN_URL", ""), help="CI run URL for the note")
    ap.add_argument("--apply", action="store_true", help="write to Notion (default: dry-run)")
    ap.add_argument("--confirm-twice", default=None,
                    help="path to the previous run's failed_ids state; only file candidates that ALSO failed last run")
    ap.add_argument("--state-out", default=None,
                    help="write this run's candidate ids here for next run's confirm-twice comparison")
    args = ap.parse_args()

    token = os.environ.get("NOTION_QUEUE_TOKEN")
    if not token:
        sys.exit("NOTION_QUEUE_TOKEN not set")

    report_path = args.report or latest_report()
    if not report_path or not os.path.exists(report_path):
        sys.exit("no campaign_report_*.json found (run campaign_scorer.py first)")
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    candidates = report.get("notion_candidates", []) or []
    health_band = report.get("health_band")  # GREEN / AMBER / RED / INCONCLUSIVE / N/A

    # Phase 2: persist this run's candidate ids for next run's confirm-twice comparison
    # (before filtering — next run compares against everything that failed THIS run).
    if args.state_out:
        write_state(args.state_out, candidates)

    # Phase 2: confirm-twice — only ACT on candidates that also failed the previous run.
    # CREATE (a new task) fails OPEN: file a first-seen failure when there's no baseline,
    # so broken plumbing never masks a real new bug. REOPEN (resurrecting a human-closed
    # task) fails CLOSED — an unconfirmed flap must not reopen a Done task (see
    # terminal_action). prev_ids/have_prev are kept in scope for that per-candidate gate.
    confirm_twice_active = bool(args.confirm_twice)
    prev_ids, have_prev = set(), False
    if confirm_twice_active:
        prev_ids, have_prev = load_prev_ids(args.confirm_twice)
        candidates, held = filter_confirmed(candidates, prev_ids, have_prev)
        if held:
            print(f"⏳ holding {len(held)} first-seen failure(s) for confirm-twice "
                  f"(will file if they recur): {', '.join(sorted(c.get('test_id', '?') for c in held))}")
        elif not have_prev:
            print("ℹ  no previous run state — confirm-twice fails OPEN for new tasks; "
                  "reopens of human-closed tasks stay HELD (fail-closed) until confirmed")

    if not candidates:
        print("✔ no notion_candidates to sync (clean run, or all held for confirm-twice)")
        return

    # discover the title property name (type == 'title') — robust to "Task Title" vs "Name"
    db = _req("GET", f"{API}/databases/{QUEUE_DB_ID}", token)
    title_prop = next((n for n, p in db.get("properties", {}).items() if p.get("type") == "title"), "Name")
    has_priority = db.get("properties", {}).get("Priority", {}).get("type") == "select"
    has_notes = db.get("properties", {}).get("Execution Notes", {}).get("type") == "rich_text"

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    created = updated = skipped = reopen_held = 0

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
            # A failure is "confirmed" when the confirm-twice gate is inactive (legacy /
            # manual runs keep the prior behaviour) or the id also failed the previous run.
            confirmed = (not confirm_twice_active) or (tid in prev_ids)
            action = terminal_action(cur, health_band, confirmed=confirmed)
            if action == "skip":
                # Passing (GREEN) run: don't resurrect or even annotate a human-closed
                # task on a transient flap — this is the AIQ-1377 re-open loop.
                print(f"  SKIP(passing)  [{tid}] (status={cur}, band={health_band}) → "
                      f"{_title_text(match, title_prop)[:50]}")
                skipped += 1
                continue
            if action == "hold":
                # Terminal task on a non-GREEN band, but the failure is unconfirmed
                # (first-seen this campaign, or no baseline). Do NOT resurrect a human's
                # Done decision on a single unverifiable flap — the AIQ-1375 deploy-window
                # recurrence (AIQ-1738). It reopens next run only if it recurs.
                print(f"  HOLD(unconfirmed) [{tid}] (status={cur}, band={health_band}) → "
                      f"not resurrecting a terminal task on a first-seen failure")
                reopen_held += 1
                continue
            props = {}
            if has_notes:
                prev = "".join(t.get("plain_text", "") for t in
                               match.get("properties", {}).get("Execution Notes", {}).get("rich_text", []))
                merged = (note + "\n" + prev)[:1900]
                props["Execution Notes"] = {"rich_text": [{"type": "text", "text": {"content": merged}}]}
            if action == "reopen":
                props["Status"] = {"select": {"name": "Ready for AI"}}
            verb = "UPDATE+REOPEN" if action == "reopen" else "UPDATE"
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
    print(f"\n{mode}: {created} create, {updated} update, {skipped} skip, "
          f"{reopen_held} held-reopen (of {len(candidates)} candidates) → "
          f"title property '{title_prop}'")


if __name__ == "__main__":
    main()
