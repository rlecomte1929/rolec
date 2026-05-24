#!/usr/bin/env python3
"""
ReloPass Manual Results Collector  v1.0
========================================
Interactive CLI to record manual UI test results for tests that cannot be
run automatically. Merges results into an existing test_results_*.json file
(or creates a standalone manual_results_*.json for later merging).

Usage:
    # Guided mode — walks through all SKIP/missing tests in the latest results file
    python3 scripts/manual_results.py

    # Target a specific results file
    python3 scripts/manual_results.py --file results/test_results_2026-05-23T12-46.json

    # Record results for specific test IDs only
    python3 scripts/manual_results.py --tests HP2,EP1,SEC1

    # Dry run — show what would be updated without writing
    python3 scripts/manual_results.py --dry-run

Output:
    Updates the target test_results_*.json in place (backs up original first).
    Prints a summary of what changed.
"""

import argparse
import json
import os
import sys
import glob
import shutil
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR     = Path(__file__).parent
REPO_ROOT      = SCRIPT_DIR.parent
RESULTS_DIR    = REPO_ROOT / "results"
MAP_FILE       = SCRIPT_DIR / "scoring_map.json"

# ── Valid statuses for manual entry ───────────────────────────────────────────
VALID_STATUSES = ["PASS", "FAIL", "WARN", "PARTIAL", "BLOCKED", "SKIP"]
STATUS_SHORTCUTS = {
    "p": "PASS", "f": "FAIL", "w": "WARN",
    "b": "BLOCKED", "s": "SKIP", "~": "PARTIAL",
}

BOLD  = "\033[1m"
RESET = "\033[0m"
GREEN = "\033[92m"
RED   = "\033[91m"
AMBER = "\033[93m"
BLUE  = "\033[94m"
GREY  = "\033[90m"

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def find_latest_results():
    pattern = str(RESULTS_DIR / "test_results_*.json")
    files = sorted(glob.glob(pattern))
    return files[-1] if files else None

def get_existing_status(test_id, results_list):
    for r in results_list:
        if r.get("id") == test_id:
            return r.get("status", "SKIP"), r
    return "SKIP", None

def prompt_status(test_id, meta, current_status, notes=""):
    """Interactive prompt for a single test. Returns (new_status, notes) or None to skip."""
    domain   = meta.get("domain", "Unknown")
    priority = meta.get("priority", "")
    title    = meta.get("title", test_id)
    category = meta.get("category", "")

    print(f"\n{BOLD}  ─── {test_id}  [{priority}] ──────────────────────────────────{RESET}")
    print(f"  Title    : {title}")
    print(f"  Domain   : {domain}  ({category})")
    print(f"  Current  : {GREY}{current_status}{RESET}")
    print()
    print(f"  Enter status  {GREY}(p=PASS  f=FAIL  w=WARN  b=BLOCKED  s=SKIP  ~=PARTIAL  Enter=keep){RESET}")

    raw = input("  → ").strip().lower()

    if raw == "":
        print(f"  {GREY}Keeping {current_status}{RESET}")
        return None, None   # no change

    new_status = STATUS_SHORTCUTS.get(raw) or raw.upper()
    if new_status not in VALID_STATUSES:
        print(f"  {RED}Unknown status '{raw}' — keeping {current_status}{RESET}")
        return None, None

    note = input("  Notes (optional, Enter to skip): ").strip()
    return new_status, note or None

def run_guided(results_data, score_map, target_ids=None, dry_run=False):
    """
    Walk through tests and collect manual results.
    target_ids: list of test IDs to ask about. If None, asks about all SKIP tests.
    """
    results_list = results_data.get("results", [])

    # Determine which tests to ask about
    if target_ids:
        ids_to_ask = target_ids
    else:
        # All tests in scoring_map that are currently SKIP or absent
        ids_to_ask = []
        for test_id in score_map["tests"]:
            status, _ = get_existing_status(test_id, results_list)
            if status == "SKIP":
                ids_to_ask.append(test_id)

    if not ids_to_ask:
        print(f"\n  {GREEN}✔ Nothing to record — all tests already have a status.{RESET}")
        return 0

    print(f"\n  {BOLD}Manual Results Collector{RESET}")
    print(f"  {len(ids_to_ask)} tests to record. Press Enter to keep current status.")
    print(f"  Type 'q' at any time to quit and save progress.\n")

    updates = []

    for test_id in ids_to_ask:
        meta = score_map["tests"].get(test_id, {})
        current_status, existing_record = get_existing_status(test_id, results_list)

        new_status, note = prompt_status(test_id, meta, current_status)

        if new_status is None:
            continue

        if new_status == "q":
            print(f"\n  {AMBER}Stopping early — saving progress so far.{RESET}")
            break

        updates.append({
            "test_id":     test_id,
            "old_status":  current_status,
            "new_status":  new_status,
            "note":        note,
            "existing":    existing_record,
        })
        print(f"  {GREEN}✔ Recorded {test_id}: {new_status}{RESET}")

    if not updates:
        print(f"\n  {GREY}No changes recorded.{RESET}")
        return 0

    # Apply updates
    print(f"\n  {BOLD}Summary — {len(updates)} change(s):{RESET}")
    for u in updates:
        arrow = f"{GREY}{u['old_status']}{RESET} → {GREEN if u['new_status'] == 'PASS' else RED}{u['new_status']}{RESET}"
        print(f"    {u['test_id']:20} {arrow}")

    if dry_run:
        print(f"\n  {AMBER}Dry run — no files written.{RESET}")
        return len(updates)

    confirm = input("\n  Apply these changes? (y/n) → ").strip().lower()
    if confirm != "y":
        print(f"  {AMBER}Aborted — no files written.{RESET}")
        return 0

    # Update results_list in place
    ts_now = datetime.now(timezone.utc).isoformat()
    existing_ids = {r["id"]: r for r in results_list}

    for u in updates:
        record = existing_ids.get(u["test_id"])
        if record:
            record["status"] = u["new_status"]
            record["manual"] = True
            record["manual_at"] = ts_now
            if u["note"]:
                record["notes"] = u["note"]
        else:
            new_record = {
                "id":        u["test_id"],
                "status":    u["new_status"],
                "manual":    True,
                "manual_at": ts_now,
            }
            if u["note"]:
                new_record["notes"] = u["note"]
            results_list.append(new_record)

    # Rebuild results_data
    results_data["results"] = list(existing_ids.values())
    # Add any new records not already in existing_ids
    existing_set = set(existing_ids.keys())
    for u in updates:
        if u["test_id"] not in existing_set:
            results_data["results"].append({
                "id":        u["test_id"],
                "status":    u["new_status"],
                "manual":    True,
                "manual_at": ts_now,
                **({"notes": u["note"]} if u["note"] else {}),
            })

    # Update summary counts
    summary = results_data.get("summary", {})
    pass_count = sum(1 for r in results_data["results"] if r.get("status") == "PASS")
    fail_count = sum(1 for r in results_data["results"] if r.get("status") in ("FAIL", "BLOCKED"))
    summary["pass"]  = pass_count
    summary["fail"]  = fail_count
    summary["manual_updates"] = summary.get("manual_updates", 0) + len(updates)
    results_data["summary"] = summary

    return len(updates)

def main():
    parser = argparse.ArgumentParser(description="ReloPass Manual Results Collector")
    parser.add_argument("--file",     help="Path to test_results_*.json to update (auto-detects latest if omitted)")
    parser.add_argument("--tests",    help="Comma-separated list of test IDs to record (default: all SKIP tests)")
    parser.add_argument("--dry-run",  action="store_true", help="Preview changes without writing")
    args = parser.parse_args()

    # Load scoring map
    if not MAP_FILE.exists():
        print(f"ERROR: scoring_map.json not found at {MAP_FILE}", file=sys.stderr)
        sys.exit(1)
    score_map = load_json(MAP_FILE)

    # Resolve results file
    if args.file:
        results_file = args.file
    else:
        results_file = find_latest_results()
        if not results_file:
            print("ERROR: No test_results_*.json found in results/. Run relopass-e2e-test first.", file=sys.stderr)
            sys.exit(1)

    print(f"\n  {BLUE}Loading:{RESET} {Path(results_file).name}")
    results_data = load_json(results_file)

    # Parse target IDs
    target_ids = None
    if args.tests:
        target_ids = [t.strip() for t in args.tests.split(",") if t.strip()]

    # Backup original
    if not args.dry_run:
        backup_path = str(results_file) + ".bak"
        shutil.copy2(results_file, backup_path)
        print(f"  {GREY}Backup: {Path(backup_path).name}{RESET}")

    # Run guided collection
    n_updated = run_guided(results_data, score_map, target_ids=target_ids, dry_run=args.dry_run)

    # Save updated file
    if n_updated > 0 and not args.dry_run:
        save_json(results_file, results_data)
        print(f"\n  {GREEN}✔ Saved {n_updated} update(s) → {Path(results_file).name}{RESET}")
        print(f"  {GREY}Run campaign_scorer.py to re-score with updated results.{RESET}\n")
    elif not args.dry_run:
        # Remove backup if nothing changed
        if os.path.exists(backup_path):
            os.remove(backup_path)

if __name__ == "__main__":
    main()
