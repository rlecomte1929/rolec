#!/usr/bin/env python3
"""
ReloPass Pre-flight Parser
--------------------------
Reads test_results.json (from relopass_api_runner_patched.js --api-only)
and produces a go/no-go decision + injection block for the Wave 1 usability
test plan (USABILITY_TEST_WAVE1_PLAN_V3.md).

Run from repo root:
  node relopass_api_runner_patched.js --api-only
  python3 parse_preflight.py
"""

import json
import sys
from pathlib import Path

RESULTS_FILE = Path(__file__).parent / "test_results.json"

# Tests that gate usability plan execution — FAIL = do not launch Conductor
HARD_GATES = {
    "AT2_FRESH": "Fresh HR registration",
    "AT3_FRESH": "Fresh Employee registration",
    "CT2":       "Case creation (POST /api/hr/cases)",
    "CT4":       "Case assignment (assign endpoint, B3)",
}

# Tests that inform agent prompts — FAIL = pre-flag, continue
SOFT_FLAGS = {
    "HP2":  "HR can open individual case detail (B8)",
    "WZ2":  "Wizard Step 2 — services selection (B19)",
    "WZ3":  "Wizard Step 3 — budget summary (B19)",
    "VT1":  "Service categories count ≥14",
    "CT5":  "HR assignments endpoint speed (B1)",
}


def main():
    if not RESULTS_FILE.exists():
        print("\n✗  test_results.json not found.")
        print("   Run: node relopass_api_runner_patched.js --api-only")
        sys.exit(1)

    with open(RESULTS_FILE) as f:
        data = json.load(f)

    results = {r["id"]: r for r in data.get("results", [])}
    run_date = data.get("run_date", "unknown")
    score = data.get("score_pct", "?")

    divider = "=" * 62
    print(f"\n{divider}")
    print(f"  RELOPASS PRE-FLIGHT RESULTS — {run_date}")
    print(f"  API Score: {score}%   |   Total: {data.get('summary', {}).get('total','?')} tests")
    print(divider)

    # --- Hard gates ---
    print("\n── HARD GATES (FAIL = do not launch Conductor) ──\n")
    hard_stop = False
    for tid, label in HARD_GATES.items():
        r = results.get(tid)
        if r is None:
            status = "MISSING"
        else:
            status = r["status"]
        ok = status == "PASS"
        icon = "✓" if ok else "✗  STOP"
        print(f"  {icon:<8} {tid:<14} {label}  →  {status}")
        if not ok:
            hard_stop = True

    # --- Soft flags ---
    print("\n── SOFT FLAGS (pre-inject into agent prompts if not PASS) ──\n")
    injections = []
    for tid, label in SOFT_FLAGS.items():
        r = results.get(tid)
        if r is None:
            status, detail, ms = "MISSING", "", None
        else:
            status = r["status"]
            detail = r.get("detail", "")
            ms = r.get("ms")

        icon = "✓" if status == "PASS" else ("⚠" if status == "WARN" else "✗")
        timing = f"  ({ms}ms)" if ms else ""
        print(f"  {icon}  {tid:<6}  {label}  →  {status}{timing}")
        if detail and status != "PASS":
            print(f"           detail: {str(detail)[:80]}")
        if status != "PASS":
            injections.append({"id": tid, "label": label, "status": status, "detail": str(detail)})

    # --- Decision ---
    print(f"\n{divider}")
    if hard_stop:
        print("  GO/NO-GO:  ✗  STOP")
        print()
        print("  Fix all hard gate failures before launching Conductor.")
        print("  The usability agents cannot complete their tasks if these fail.")
        print()
        failing = [tid for tid, label in HARD_GATES.items()
                   if results.get(tid, {}).get("status", "MISSING") != "PASS"]
        for tid in failing:
            print(f"  → Fix: {tid} — {HARD_GATES[tid]}")
    else:
        print("  GO/NO-GO:  ✓  PROCEED")
        print()
        print("  All hard gates pass. Safe to launch Conductor agents.")

    # --- Injection block ---
    if not hard_stop:
        print(f"\n{divider}")
        if injections:
            print("  PASTE THIS BLOCK into both Agent A and Agent B prompts,")
            print("  immediately after the CREDENTIALS section:\n")
            print("  ┌─────────────────────────────────────────────────────────┐")
            print("  │ PRE-FLIGHT STATUS (from API runner, run today):         │")
            for inj in injections:
                line = f"  │   {inj['id']}: {inj['label']} → {inj['status']}"
                print(f"{line:<62}│")
                if inj["detail"]:
                    trunc = inj["detail"][:54]
                    dline = f"  │     Error: {trunc}"
                    print(f"{dline:<62}│")
            print("  │   These are known. Document UI manifestation, move on. │")
            print("  └─────────────────────────────────────────────────────────┘")
        else:
            print("  All soft flags passing — no injection block needed.")
            print("  Remove the [INSERT PRE-FLIGHT STATUS BLOCK HERE] line from")
            print("  both agent prompts before launching Conductor.")

    print(f"{divider}\n")


if __name__ == "__main__":
    main()
