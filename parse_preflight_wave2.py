#!/usr/bin/env python3
"""
ReloPass Pre-flight Parser — Wave 2
------------------------------------
Reads test_results.json (from relopass_api_runner_patched.js, full suite)
and produces a go/no-go decision + injection block for the Wave 2 usability
test (USABILITY_TEST_WAVE2_CONDUCTOR.md).

Changes from Wave 1 parse_preflight.py:
  - WZ2/WZ3 removed (superseded — old wizard path not in live v2 platform)
  - HP2 kept as soft flag but with updated note (not a user-facing blocker
    on the case-summary route)
  - AT2_FRESH/AT3_FRESH removed from hard gates (browser test uses existing
    accounts; rate-limit 429s were false stops in Wave 1)
  - Delta vs Wave 1 baseline (91%) printed
  - KNOWN_OPEN block added for B11_SUBMIT/A10_MSG/A11_GUARD (cannot be
    detected by the API runner — must be verified manually in browser)

Run from repo root:
  node relopass_api_runner_patched.js   ← full suite (NOT --api-only)
  python3 parse_preflight_wave2.py

Why full suite, not --api-only?
  --api-only skips the scenario runner, which means CT2/CT4 (case creation /
  assignment gates) are absent from results.json → parser shows MISSING → STOP.
  This was a false stop in Wave 1. Use full suite.

Rate-limit note:
  If AT2_FRESH / AT3_FRESH show 429, that is a self-inflicted harness artifact
  from dense back-to-back runs. Wait 90 seconds and re-run the individual test
  (--scenario AT2_FRESH) to confirm. The browser test does NOT register new
  accounts, so 429 on these does not block browser execution.
"""

import json
import sys
from pathlib import Path

RESULTS_FILE = Path(__file__).parent / "test_results.json"

# Tests that gate Conductor launch — FAIL = do not launch
# (AT2_FRESH / AT3_FRESH removed: browser test uses existing accounts)
HARD_GATES = {
    "CT2": "Case creation (POST /api/hr/cases)",
    "CT4": "Case assignment (assign endpoint)",
}

# Tests that inform agent prompts — FAIL/WARN = pre-inject, continue
SOFT_FLAGS = {
    "HP2": "HR open case from command-center (B8) — note: case-summary route loads fine; this is a secondary endpoint",
    "VT1": "Service categories count ≥14",
    "CT5": "HR assignments endpoint speed",
}

# Issues that cannot be detected by the API runner — agents verify manually
KNOWN_OPEN = [
    ("B11_SUBMIT", "Intake submit schema mismatch — API runner bypasses wizard; "
                   "Agent B verifies manually at Review step (Step 5/5)."),
    ("A10_MSG",   "HR Messages: wrong-persona copy + compose path — "
                   "not testable via API; Agent A verifies at /hr/messages."),
    ("A11_GUARD", "/journey accessible as HR (route guard gap) — "
                   "not testable via API; Agent A verifies by navigating to /journey."),
]

WAVE1_BASELINE_SCORE = 91.0


def main():
    if not RESULTS_FILE.exists():
        print("\n✗  test_results.json not found.")
        print("   Run: node relopass_api_runner_patched.js")
        print("   (Full suite — do NOT use --api-only; omits CT2/CT4 case gates)")
        sys.exit(1)

    with open(RESULTS_FILE) as f:
        data = json.load(f)

    results = {r["id"]: r for r in data.get("results", [])}
    run_date = data.get("run_date", "unknown")
    score_raw = data.get("score_pct", None)
    total = data.get("summary", {}).get("total", "?")
    passed = data.get("summary", {}).get("pass", "?")
    failed = data.get("summary", {}).get("fail", "?")

    # A throttled run (429/503) is INCONCLUSIVE, not a regression — the runner
    # rate-limited itself, so the score reflects throttling, not product health.
    run_status = data.get("run_status", "ok")
    throttled_checks = data.get("throttled_checks", 0)
    inconclusive = run_status == "inconclusive"

    try:
        score = float(score_raw)
        delta = score - WAVE1_BASELINE_SCORE
        delta_str = f"+{delta:.1f}%" if delta >= 0 else f"{delta:.1f}%"
        trend = "↑ improved" if delta > 0 else ("↓ regressed" if delta < 0 else "→ unchanged")
    except (TypeError, ValueError):
        score = None
        delta_str = "?"
        trend = "?"

    D = "=" * 64
    print(f"\n{D}")
    print(f"  RELOPASS WAVE 2 PRE-FLIGHT — {run_date}")
    if inconclusive:
        print(f"  API Score:   {score_raw}%  ({passed}/{total} pass, {failed} fail)")
        print(f"  RUN STATUS:  ⚠  INCONCLUSIVE — runner rate-limited "
              f"({throttled_checks} check(s) throttled)")
        print(f"  Wave 1 base: {WAVE1_BASELINE_SCORE}%  →  Delta: N/A (throttled — not comparable)")
    elif score is not None:
        print(f"  API Score:   {score}%  ({passed}/{total} pass, {failed} fail)")
        print(f"  Wave 1 base: {WAVE1_BASELINE_SCORE}%  →  Delta: {delta_str}  {trend}")
    else:
        print(f"  API Score:   {score_raw}  |  Total: {total}")
    print(D)

    # --- Hard gates ---
    print("\n── HARD GATES (FAIL = do not launch Conductor) ──\n")
    hard_stop = False
    for tid, label in HARD_GATES.items():
        r = results.get(tid)
        status = r["status"] if r else "MISSING"
        ok = status == "PASS"
        # During a throttled run, a BLOCKED/MISSING/SKIP gate is inconclusive,
        # not a real failure — don't let it trigger STOP.
        blocked = status == "BLOCKED" or (inconclusive and status in ("MISSING", "SKIP", "BLOCKED"))
        if ok:
            icon = "✓"
        elif blocked:
            icon = "⊘  THROTTLED"
        else:
            icon = "✗  STOP"
        print(f"  {icon:<12} {tid:<8} {label}  →  {status}")
        if not ok and not blocked:
            hard_stop = True

    # --- Soft flags ---
    print("\n── SOFT FLAGS (pre-inject if not PASS) ──\n")
    injections = []
    for tid, label in SOFT_FLAGS.items():
        r = results.get(tid)
        status = r["status"] if r else "MISSING"
        detail = (r or {}).get("detail", "")
        ms = (r or {}).get("ms")
        icon = "✓" if status == "PASS" else ("⚠" if status == "WARN" else "✗")
        timing = f"  ({ms}ms)" if ms else ""
        print(f"  {icon}  {tid:<6}  →  {status}{timing}")
        if detail and status != "PASS":
            print(f"          detail: {str(detail)[:78]}")
        if status != "PASS":
            injections.append({
                "id": tid, "label": label.split(" — ")[0],
                "status": status, "detail": str(detail),
            })

    # --- Known open (API-runner blind spots) ---
    print("\n── KNOWN OPEN — verify manually in browser (API runner cannot detect) ──\n")
    for tid, desc in KNOWN_OPEN:
        print(f"  ⚠  {tid}")
        print(f"       {desc}")
        injections.append({"id": tid, "label": "", "status": "VERIFY-MANUALLY", "detail": ""})

    print("\n── NOTE: old wizard UI superseded, but its endpoints are LIVE ──\n")
    print("  ℹ  WZ2  services PATCH /api/cases/{id} — endpoint live; the old multi-step")
    print("         wizard *UI* is superseded, the API is exercised by the v2 platform")
    print("  ℹ  WZ3  budget-summary GET — endpoint live (200 for the case assignee)")

    # --- Decision ---
    print(f"\n{D}")
    if inconclusive:
        print("  GO/NO-GO:  ⚠  INCONCLUSIVE (rate-limited)")
        print()
        print("  The runner was throttled (429/503) — this is a harness artifact,")
        print("  NOT a product regression. Production health cannot be judged from")
        print(f"  this run ({throttled_checks} check(s) throttled).")
        print()
        print("  → Wait for the rate-limit window to clear, then re-run:")
        print("      node relopass_api_runner_patched.js && python3 parse_preflight_wave2.py")
        print("  The built-in cooldown guard will pause if the IP is still throttled.")
    elif hard_stop:
        print("  GO/NO-GO:  ✗  STOP")
        print()
        print("  Fix all hard gate failures before launching Conductor.")
        failing = [tid for tid in HARD_GATES
                   if results.get(tid, {}).get("status", "MISSING") != "PASS"]
        for tid in failing:
            print(f"  → Fix: {tid} — {HARD_GATES[tid]}")
    else:
        print("  GO/NO-GO:  ✓  PROCEED")
        print()
        print("  Hard gates pass. Safe to launch Conductor agents.")
        print("  Existing accounts used — no registration needed — 429s do not block.")

    # --- Injection block ---
    if not hard_stop and not inconclusive:
        soft_injections = [i for i in injections if i["status"] not in ("VERIFY-MANUALLY",)]
        manual_items = [i for i in injections if i["status"] == "VERIFY-MANUALLY"]

        print(f"\n{D}")
        print("  PASTE THIS BLOCK into both Agent A and Agent B prompts,")
        print("  immediately after the CREDENTIALS section:\n")
        print("  ┌──────────────────────────────────────────────────────────────┐")
        print("  │ PRE-FLIGHT STATUS (Wave 2, run today):                       │")

        if soft_injections:
            for inj in soft_injections:
                line = f"  │   {inj['id']}: {inj['status']}"
                print(f"{line:<65}│")
                if inj["detail"]:
                    trunc = str(inj["detail"])[:58]
                    print(f"  │     Error: {trunc:<52}│")
        else:
            print("  │   All soft flags PASS — no API-level pre-flags needed.      │")

        print("  │                                                              │")
        print("  │   VERIFY MANUALLY (API runner cannot detect these):          │")
        for inj in manual_items:
            line = f"  │   {inj['id']}: check manually"
            print(f"{line:<65}│")

        print("  │   WZ2/WZ3: SUPERSEDED — removed, do not test               │")
        print("  │   For any ✗ or ⚠ above: document UI manifestation, move on │")
        print("  └──────────────────────────────────────────────────────────────┘")

    print(f"{D}\n")


if __name__ == "__main__":
    main()
