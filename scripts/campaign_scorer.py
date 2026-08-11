#!/usr/bin/env python3
"""
ReloPass Campaign Scorer  v1.1
===============================
Reads the two most recent test_results_*.json files from results/,
applies the scoring model from scoring_map.json, computes per-domain
scores and a weighted overall score, diffs against the previous campaign,
and writes campaign_report_{ts}.json.

New in v1.1: loads scenarios.json to produce step-level, role-tagged
breakdowns for each scenario flow — shows exactly which step and which
role (HR/Employee/Admin) is the blocking point when a flow fails.

Usage:
    python scripts/campaign_scorer.py                    # auto-detect latest two
    python scripts/campaign_scorer.py --current results/test_results_2026-05-23T11-54.json
    python scripts/campaign_scorer.py --no-prev          # first campaign, no comparison

Output:
    results/campaign_report_{ts}.json
    Printed comparison table to stdout
"""

import argparse
import json
import os
import sys
import glob
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR     = Path(__file__).parent
REPO_ROOT      = SCRIPT_DIR.parent
RESULTS_DIR    = REPO_ROOT / "results"
MAP_FILE       = SCRIPT_DIR / "scoring_map.json"
SCENARIOS_FILE = SCRIPT_DIR / "scenarios.json"

# ── Status point values ────────────────────────────────────────────────────────
POINTS = {
    "PASS":    1.0,
    "WARN":    0.5,
    "PARTIAL": 0.5,
    "FAIL":    0.0,
    "BLOCKED": 0.0,
    "SKIP":    None,   # excluded from denominator
    "ENV":     None,   # environmental / deploy-window transient — excluded, never 'bad'
}

# A run with this many environmental failures was almost certainly testing against a
# backend mid rolling-restart → mark it INCONCLUSIVE and file nothing (Signal B).
DEGRADED_ENV_THRESHOLD = 3


def count_env(per_test):
    """Number of scored tests classified ENV (deploy-window transient) this run."""
    return sum(1 for t in per_test.values() if t.get("status") == "ENV")


def is_degraded(env_count, forced=False, threshold=None):
    """A run is degraded (inconclusive, don't file) when too many tests were
    environmental, or when the readiness gate (Phase 3) forced it (data path never warmed)."""
    thr = DEGRADED_ENV_THRESHOLD if threshold is None else threshold
    return bool(forced or env_count >= thr)


def finalize_candidates(candidates, degraded):
    """A degraded run files NOTHING — its failures are environmental, not bugs."""
    return [] if degraded else candidates


def degraded_band():
    return "INCONCLUSIVE", "🟣  Inconclusive — backend was mid-deploy/unavailable. Not scored, not filed."

# ── Health bands ───────────────────────────────────────────────────────────────
def health_band(score_pct):
    if score_pct is None:
        return "N/A", ""
    if score_pct >= 90:
        return "GREEN",  "✅  Ready for wider use. No P0 failures."
    if score_pct >= 70:
        return "AMBER",  "⚠️   Usable with workarounds. Fix P0/P1 failures."
    return     "RED",    "🔴  Do not expose to customers. Fix blockers first."

# ── Helpers ────────────────────────────────────────────────────────────────────
def find_results_files():
    """Return sorted list of test_results_*.json paths, newest last."""
    pattern = str(RESULTS_DIR / "test_results_*.json")
    files = sorted(glob.glob(pattern))
    return files

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def extract_results(data):
    """Return the run's results as a list of dicts, tolerant of historical shapes.

    Runner output has drifted: newer files store the list under ``results``;
    some older files store ``results`` as a dict (keyed by test_id) with the
    list under ``results_list``. Normalise all of these to a list of dicts so
    the scorer can compare any baseline without manual --prev juggling.
    """
    r = data.get("results")
    if isinstance(r, list):
        return r
    rl = data.get("results_list")
    if isinstance(rl, list):
        return rl
    if isinstance(r, dict):  # legacy: {test_id: {status, ...}}
        return [{"id": v.get("id", k), **v} for k, v in r.items() if isinstance(v, dict)]
    return []

def status_of(test_id, results_list):
    """Return status string for a given test ID in a results list."""
    for r in results_list:
        if isinstance(r, dict) and r.get("id") == test_id:
            return r.get("status", "SKIP")
    return "SKIP"  # not present in this run = skip

def score_results(results_list, score_map):
    """
    Apply scoring_map to a list of result dicts.
    Returns:
        domain_scores  – {domain: {score_pct, pass, total, weight}}
        overall_score  – weighted percentage (None if no scored domains)
        per_test       – {test_id: {points, status, domain, priority}}
    """
    domain_data = {}    # domain -> {points_sum, count, weight}
    per_test    = {}

    for test_id, meta in score_map["tests"].items():
        domain   = meta["domain"]
        weight   = score_map["_meta"]["scoring_rules"]["domain_weights"].get(domain, 1)
        status   = status_of(test_id, results_list)
        points   = POINTS.get(status, None)

        per_test[test_id] = {
            "status":   status,
            "points":   points,
            "domain":   domain,
            "priority": meta["priority"],
            "title":    meta.get("title", test_id),
            "notion_worthy": meta.get("notion_worthy", False),
        }

        if domain not in domain_data:
            domain_data[domain] = {"points_sum": 0.0, "count": 0, "weight": weight, "p0_fails": 0}

        if points is not None:   # not SKIP
            domain_data[domain]["points_sum"] += points
            domain_data[domain]["count"]      += 1
            if points == 0.0 and meta["priority"] == "P0":
                domain_data[domain]["p0_fails"] += 1

    # Domain scores
    domain_scores = {}
    weighted_sum  = 0.0
    weight_total  = 0.0

    for domain, data in domain_data.items():
        if data["count"] == 0:
            domain_scores[domain] = {
                "score_pct": None, "pass": 0, "total": 0,
                "weight": data["weight"], "p0_fails": data["p0_fails"]
            }
            continue
        pct = round((data["points_sum"] / data["count"]) * 100, 1)
        domain_scores[domain] = {
            "score_pct": pct,
            "pass":      data["points_sum"],
            "total":     data["count"],
            "weight":    data["weight"],
            "p0_fails":  data["p0_fails"],
        }
        weighted_sum  += pct * data["weight"]
        weight_total  += data["weight"]

    overall = round(weighted_sum / weight_total, 1) if weight_total > 0 else None
    return domain_scores, overall, per_test

def diff_tests(current_per_test, prev_per_test):
    """
    Compare two per_test dicts.
    Returns:
        regressions  – tests that were passing, now failing
        fixed        – tests that were failing, now passing
        new_failures – tests not in prev, failing in current
        still_broken – tests failing in both
    """
    regressions  = []
    fixed        = []
    new_failures = []
    still_broken = []

    for tid, cur in current_per_test.items():
        cur_bad  = cur["points"] == 0.0
        prev_rec = prev_per_test.get(tid)

        if prev_rec is None:
            if cur_bad:
                new_failures.append(tid)
            continue

        prev_bad = prev_rec["points"] == 0.0
        prev_skip = prev_rec["status"] == "SKIP"
        cur_skip  = cur["status"] == "SKIP"

        if prev_skip or cur_skip:
            continue

        if not prev_bad and cur_bad:
            regressions.append(tid)
        elif prev_bad and not cur_bad:
            fixed.append(tid)
        elif prev_bad and cur_bad:
            still_broken.append(tid)

    return regressions, fixed, new_failures, still_broken

def load_scenarios():
    """Load scenarios.json if it exists. Returns None gracefully if missing."""
    if not SCENARIOS_FILE.exists():
        return None
    with open(SCENARIOS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# Status severity ordering — higher = worse
_SEVERITY = {"FAIL": 3, "BLOCKED": 2, "WARN": 1, "PARTIAL": 1, "PASS": 0, "SKIP": -1}

def build_scenario_breakdown(scenarios_data, current_per_test):
    """
    For each scenario in scenarios.json, walk its steps in order and:
    - identify the first step whose test_id is failing/blocked
    - record the role (HR/Employee/Admin) of that blocking step
    - produce a per-scenario summary that appears in the campaign report

    scenarios.json structure:
      - scenarios_data["scenarios"] is a dict keyed by full ID like "T1_FLOW"
      - scenarios_data["_meta"]["run_order"] is a list of short IDs like ["T1", "T2"]
        which map to "T1_FLOW", "T2_FLOW" etc. in the scenarios dict

    Returns a list of scenario_breakdown dicts, one per scenario,
    sorted by the run_order defined in scenarios.json._meta.
    """
    if not scenarios_data:
        return []

    scenarios_dict = scenarios_data.get("scenarios", {})
    meta           = scenarios_data.get("_meta", {})

    # run_order uses short IDs ("T1") — map to full keys ("T1_FLOW")
    raw_run_order  = meta.get("run_order", list(scenarios_dict.keys()))
    # Build ordered list of full scenario keys in run order
    run_order = []
    for short_id in raw_run_order:
        # Try exact match first, then with _FLOW suffix, then prefix-search
        if short_id in scenarios_dict:
            run_order.append(short_id)
        elif f"{short_id}_FLOW" in scenarios_dict:
            run_order.append(f"{short_id}_FLOW")
        else:
            # prefix search — take first match
            matches = [k for k in scenarios_dict if k.startswith(short_id)]
            if matches:
                run_order.append(matches[0])

    # Include any scenarios not in run_order at the end
    for key in scenarios_dict:
        if key not in run_order:
            run_order.append(key)

    breakdown = []

    for full_sid in run_order:
        scenario = scenarios_dict.get(full_sid)
        if not scenario:
            continue

        # The flow test_id matches the key: "T1_FLOW" → look for T1_FLOW in per_test
        # Also try the scenario's own "id" field
        flow_test_id = scenario.get("id", full_sid)
        flow_result  = current_per_test.get(flow_test_id)
        flow_status  = flow_result["status"] if flow_result else "SKIP"

        steps_detail   = []
        first_failure  = None
        blocking_role  = None
        blocking_action = None
        blocking_bug   = None

        for step in scenario.get("steps", []):
            step_test_id = step.get("test_id")
            if not step_test_id:
                # Step has no automated test_id — record as untested
                steps_detail.append({
                    "step":    step["step"],
                    "role":    step["role"],
                    "method":  step.get("method", ""),
                    "action":  step["action"],
                    "test_id": None,
                    "status":  "UNTESTED",
                })
                continue

            step_result = current_per_test.get(step_test_id)
            step_status = step_result["status"] if step_result else "SKIP"

            steps_detail.append({
                "step":    step["step"],
                "role":    step["role"],
                "method":  step.get("method", ""),
                "action":  step["action"],
                "test_id": step_test_id,
                "status":  step_status,
            })

            # Track first hard failure in sequence
            if first_failure is None and _SEVERITY.get(step_status, -1) >= 2:
                first_failure   = step["step"]
                blocking_role   = step["role"]
                blocking_action = step["action"]
                blocking_bug    = step.get("blocking_bug")

        entry = {
            "scenario_id":        full_sid,
            "title":              scenario.get("title", full_sid),
            "priority":           scenario.get("priority", "P1"),
            "flow_status":        flow_status,
            "first_failure_step": first_failure,
            "blocking_role":      blocking_role,
            "blocking_action":    blocking_action,
            "blocking_bug":       blocking_bug,
            "steps":              steps_detail,
        }
        breakdown.append(entry)

    return breakdown

def notion_candidates(current_per_test, regressions, new_failures, still_broken):
    """
    Build list of items worth syncing to Notion.
    Priority: regressions first (always), then new_failures, then still_broken
    that are notion_worthy and P0/P1.
    """
    candidates = []

    def add(tid, reason):
        t = current_per_test[tid]
        candidates.append({
            "test_id":  tid,
            "title":    t["title"],
            "domain":   t["domain"],
            "priority": t["priority"],
            "status":   t["status"],
            "reason":   reason,
        })

    for tid in regressions:
        add(tid, "REGRESSION — was passing, now failing")

    for tid in new_failures:
        t = current_per_test[tid]
        if t.get("notion_worthy") and t["priority"] in ("P0","P1"):
            add(tid, "NEW FAILURE — not seen in previous campaign")

    for tid in still_broken:
        t = current_per_test[tid]
        if t.get("notion_worthy") and t["priority"] in ("P0","P1"):
            add(tid, "PERSISTENT — still failing from previous campaign")

    return candidates

# ── Rendering ──────────────────────────────────────────────────────────────────
BAND_COLOR = {"GREEN": "\033[92m", "AMBER": "\033[93m", "RED": "\033[91m", "N/A": "\033[0m"}
RESET = "\033[0m"
BOLD  = "\033[1m"

def delta_str(cur, prev):
    if cur is None or prev is None:
        return "  N/A"
    d = cur - prev
    if d > 0:
        return f"\033[92m +{d:.1f}%{RESET}"
    if d < 0:
        return f"\033[91m {d:.1f}%{RESET}"
    return "  0.0%"

DOMAIN_WEIGHTS = {
    "Authentication": 4, "Case Management": 4, "Employee Journey": 4,
    "Policy Management": 3, "Forms & Dossiers": 3, "Immigration": 2,
    "Suppliers & Vendors": 2, "Resources": 2, "Admin Console": 1,
    "Notifications": 1, "Collaboration": 1, "Coordination": 1,
    "Exception Requests": 1, "Integrations": 1,
    "Security & RLS": 4, "Performance": 2, "End-to-End Flows": 3,
}

def print_report(current_file, prev_file,
                 current_domain_scores, current_overall,
                 prev_domain_scores,    prev_overall,
                 regressions, fixed, new_failures, still_broken,
                 candidates, scenario_breakdown_data=None):

    band, band_msg = health_band(current_overall)
    prev_band, _   = health_band(prev_overall)
    color = BAND_COLOR.get(band, "")

    print()
    print(f"{BOLD}{'═'*72}{RESET}")
    print(f"{BOLD}  ReloPass Test Campaign — Scoring Report{RESET}")
    print(f"  Current : {Path(current_file).name}")
    if prev_file:
        print(f"  Previous: {Path(prev_file).name}")
    print(f"{'═'*72}{RESET}")
    print()

    # Domain table
    domains_ordered = [
        "Authentication", "Case Management", "Employee Journey",
        "Policy Management", "Forms & Dossiers", "Immigration",
        "Suppliers & Vendors", "Resources", "Admin Console",
        "Notifications", "Collaboration", "Coordination",
        "Exception Requests", "Integrations",
        "Security & RLS", "Performance", "End-to-End Flows",
    ]

    print(f"  {'Domain':<24} {'Wt':>2}  {'Current':>8}  {'Previous':>8}  {'Delta':>8}  {'P0 Fails':>8}")
    print(f"  {'-'*24} {'--':>2}  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*8}")

    for domain in domains_ordered:
        cur  = current_domain_scores.get(domain)
        prev = prev_domain_scores.get(domain) if prev_domain_scores else None

        cur_pct  = cur["score_pct"]  if cur  else None
        prev_pct = prev["score_pct"] if prev else None
        weight   = DOMAIN_WEIGHTS.get(domain, "?")
        p0_fails = cur["p0_fails"]   if cur  else 0

        cur_str  = f"{cur_pct:>6.1f}%"  if cur_pct  is not None else "    —   "
        prev_str = f"{prev_pct:>6.1f}%" if prev_pct is not None else "    —   "
        d_str    = delta_str(cur_pct, prev_pct)
        p0_str   = f"\033[91m {p0_fails:>6}{RESET}" if p0_fails > 0 else f"      0"

        print(f"  {domain:<24} {weight:>2}  {cur_str}  {prev_str}  {d_str}  {p0_str}")

    print(f"  {'─'*24} {'──':>2}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*8}")

    cur_str  = f"{current_overall:>5.1f}%" if current_overall is not None else "   N/A"
    prev_str = f"{prev_overall:>5.1f}%"    if prev_overall    is not None else "   N/A"
    d_str    = delta_str(current_overall, prev_overall)
    print(f"  {BOLD}{'OVERALL (weighted)':<24} {'':<2}  {color}{cur_str}{RESET}  {prev_str}  {d_str}  {'':>8}")
    print()
    print(f"  {color}{BOLD}  {band}  {RESET}{band_msg}")
    print()

    # Diff summary
    if regressions:
        print(f"  {BOLD}\033[91m⬇  REGRESSIONS ({len(regressions)}) — were passing, now failing:{RESET}")
        for tid in regressions:
            t = current_domain_scores  # use per_test via candidates
            print(f"     • {tid}")
        print()

    if fixed:
        print(f"  {BOLD}\033[92m⬆  FIXED ({len(fixed)}) — were failing, now passing:{RESET}")
        for tid in fixed:
            print(f"     • {tid}")
        print()

    if new_failures:
        print(f"  {BOLD}\033[93m★  NEW FAILURES ({len(new_failures)}):{RESET}")
        for tid in new_failures:
            print(f"     • {tid}")
        print()

    # Notion candidates
    if candidates:
        print(f"  {BOLD}📋  Notion candidates ({len(candidates)}) — worth syncing to AI Work Queue:{RESET}")
        for c in candidates:
            reason_color = "\033[91m" if "REGRESSION" in c["reason"] else "\033[93m"
            print(f"     [{c['priority']}] {c['test_id']:20}  {reason_color}{c['reason']}{RESET}")
            print(f"           {c['domain']} — {c['title']}")
        print()
    else:
        print(f"  ✅  No new Notion tasks needed — all failures already tracked or fixed.")
        print()

    # Scenario step-level breakdown (if scenarios.json was loaded)
    if scenario_breakdown_data:
        print_scenario_breakdown(scenario_breakdown_data)

    print(f"{'═'*72}{RESET}")
    print()

# ── Scenario step-level breakdown printer ──────────────────────────────────────
ROLE_COLOR = {
    "HR":       "\033[94m",   # blue
    "Employee": "\033[95m",   # magenta
    "Admin":    "\033[96m",   # cyan
    "DB":       "\033[90m",   # dark grey
}
STATUS_ICON = {
    "PASS":     "\033[92m✔\033[0m",
    "FAIL":     "\033[91m✘\033[0m",
    "BLOCKED":  "\033[91m⊘\033[0m",
    "WARN":     "\033[93m⚠\033[0m",
    "PARTIAL":  "\033[93m~\033[0m",
    "SKIP":     "\033[90m·\033[0m",
    "UNTESTED": "\033[90m?\033[0m",
}

def print_scenario_breakdown(breakdown):
    """Print a concise per-scenario step breakdown table."""
    if not breakdown:
        return

    print(f"\n{BOLD}  ── Scenario Step Breakdown ──────────────────────────────────────────{RESET}")
    print(f"  {'Scenario':<12} {'Status':<9} {'Blocking Step':<6} {'Role':<10} {'Blocking action / note'}")
    print(f"  {'─'*12} {'─'*9} {'─'*6} {'─'*10} {'─'*40}")

    for entry in breakdown:
        sid        = entry["scenario_id"]
        fstatus    = entry["flow_status"]
        priority   = entry.get("priority", "")
        icon       = STATUS_ICON.get(fstatus, "?")
        step_no    = entry["first_failure_step"]
        role       = entry["blocking_role"] or ""
        action     = entry["blocking_action"] or ""
        bug        = entry["blocking_bug"]

        role_col  = ROLE_COLOR.get(role, "")
        step_str  = f"step {step_no}" if step_no else "—"
        action_str = (action[:42] + "…") if len(action) > 43 else action
        if bug:
            action_str += f"  [{bug}]"

        if fstatus == "SKIP":
            print(f"  {sid:<12} {icon} {'SKIP':<8} {'':>6}  {'':10} (not run this campaign)")
        elif fstatus == "PASS":
            print(f"  {sid:<12} {icon} {'PASS':<8} {'':>6}  {'':10} all steps OK")
        elif not step_no and fstatus in ("BLOCKED", "FAIL"):
            # Flow failed but no individual step test_id pinpoints it
            print(f"  {sid:<12} {icon} {fstatus:<8} {'?':<6}  {'':10} (flow-level — no step test_id maps to failure)")
        else:
            print(f"  {sid:<12} {icon} {fstatus:<8} {step_str:<6}  {role_col}{role:<10}{RESET} {action_str}")

    print()

# ── Main ───────────────────────────────────────────────────────────────────────
BASELINE_FILE = Path(__file__).resolve().parent / "sentinel_baseline.json"


def load_baseline(path=None):
    """Known-open failures the campaign is allowed to be red on. Missing file = empty."""
    p = Path(path) if path else BASELINE_FILE
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8")).get("known_failures", {})


def check_against_baseline(results_list, baseline):
    """Split this run's failures into (unexpected, stale-baseline-entries).

    `unexpected` is what should fail the job: a failure nobody has written down. `stale` is a
    baseline entry that now passes — reported so the ratchet tightens instead of rotting.
    """
    by_id = {r["id"]: r.get("status") for r in results_list
             if isinstance(r, dict) and r.get("id")}
    failing = {tid for tid, st in by_id.items() if st in ("FAIL", "BLOCKED")}
    unexpected = sorted(failing - set(baseline))
    stale = sorted(tid for tid in baseline if by_id.get(tid) == "PASS")
    return unexpected, stale


def report_baseline(unexpected, stale, baseline):
    if stale:
        print(f"  🎉  {len(stale)} baselined failure(s) now PASS — delete them from "
              f"scripts/sentinel_baseline.json:")
        for tid in stale:
            print(f"       {tid}")
        print()
    if unexpected:
        print(f"  ✖  {len(unexpected)} FAILING test(s) are not in the baseline:")
        for tid in unexpected:
            print(f"       {tid}")
        print("     Fix it, or add it to scripts/sentinel_baseline.json with a ticket and a")
        print("     reason. Do not add it just to make CI green.")
        print()
    elif baseline:
        print(f"  ✔  every failure this run is a known-open one ({len(baseline)} baselined).")
        print()


def report_unmapped(results_list, score_map):
    """Print result ids that have no scoring_map entry. Return True if any of them FAILED.

    `score_results` iterates the MAP, not the results, so an id the runner produced but the
    map does not know is scored nowhere, banded nowhere, and filed nowhere. It is the second
    of the Sentinel's two silent filters — the first is the missing-[TAG] drop in
    `ingest_playwright_results.py`.

    Both were live on 2026-08-11: `[R4X-A]`/`[R4X-B]` were correctly tagged but absent from
    the map, so two production assertions merged the day before ran and reported to nobody
    (AIQ-1804). A passing unmapped id is worth naming; a FAILING one has to break the run,
    because otherwise the only record of it is a raw artifact nobody opens.
    """
    mapped = set(score_map.get("tests", {}))
    unmapped = [
        r for r in results_list
        if isinstance(r, dict) and r.get("id") and r["id"] not in mapped
    ]
    if not unmapped:
        return False

    failing = [r for r in unmapped if r.get("status") in ("FAIL", "BLOCKED")]

    print(f"  ⚠️  {len(unmapped)} test id(s) ran but are not in scoring_map.json:")
    for r in unmapped:
        print(f"       {r.get('status', '?'):<5} {r['id']}  {r.get('title', '')}".rstrip())
    print("       Add them to scripts/scoring_map.json or they are scored and filed nowhere.")
    print()

    if failing:
        ids = ", ".join(r["id"] for r in failing)
        print(f"  ✖  {len(failing)} unmapped id(s) FAILED: {ids}")
        print("     A failing test outside the map cannot reach the health band or Notion.")
        print()
    return bool(failing)


def main():
    parser = argparse.ArgumentParser(description="ReloPass Campaign Scorer")
    parser.add_argument("--current",  help="Path to current test_results.json (auto-detects latest if omitted)")
    parser.add_argument("--prev",     help="Path to previous test_results.json (auto-detects second-latest if omitted)")
    parser.add_argument("--no-prev",  action="store_true", help="No previous campaign to compare against")
    parser.add_argument("--out-dir",  help="Where to write campaign_report.json (default: results/)", default=str(RESULTS_DIR))
    parser.add_argument("--degraded", action="store_true",
                        help="Force INCONCLUSIVE (e.g. Phase-3 readiness gate reported the data path never warmed)")
    args = parser.parse_args()

    # Load scoring map
    if not MAP_FILE.exists():
        print(f"ERROR: scoring_map.json not found at {MAP_FILE}", file=sys.stderr)
        sys.exit(1)
    score_map = load_json(MAP_FILE)

    # Load scenarios (optional — gracefully absent)
    scenarios_data = load_scenarios()
    if scenarios_data:
        n_scenarios = len(scenarios_data.get("scenarios", []))
        print(f"  ℹ  Loaded scenarios.json — {n_scenarios} scenarios defined")
    else:
        print(f"  ℹ  scenarios.json not found — skipping step-level breakdown")

    # Resolve results files
    all_files = find_results_files()

    if args.current:
        current_file = args.current
    elif all_files:
        current_file = all_files[-1]
    else:
        print("ERROR: No test_results_*.json found in results/. Run relopass-e2e-test first.", file=sys.stderr)
        sys.exit(1)

    prev_file = None
    if not args.no_prev:
        if args.prev:
            prev_file = args.prev
        elif len(all_files) >= 2:
            # find the most recent file that isn't current_file
            for f in reversed(all_files):
                if os.path.abspath(f) != os.path.abspath(current_file):
                    prev_file = f
                    break

    # Load data
    current_data = load_json(current_file)
    prev_data    = load_json(prev_file) if prev_file else None

    current_results = extract_results(current_data)
    prev_results    = extract_results(prev_data) if prev_data else []

    # Score
    current_domain_scores, current_overall, current_per_test = score_results(current_results, score_map)
    prev_domain_scores,    prev_overall,    prev_per_test    = (
        score_results(prev_results, score_map) if prev_results else ({}, None, {})
    )

    # Diff
    regressions, fixed, new_failures, still_broken = diff_tests(current_per_test, prev_per_test)

    # Notion candidates
    candidates = notion_candidates(current_per_test, regressions, new_failures, still_broken)

    # Degraded-run guard (Signal B): if the run was dominated by environmental (ENV)
    # failures, or the readiness gate forced it, the run is INCONCLUSIVE — file nothing.
    env_count = count_env(current_per_test)
    degraded = is_degraded(env_count, forced=args.degraded)
    candidates = finalize_candidates(candidates, degraded)
    if degraded:
        print(f"  🟣  DEGRADED (deploy window): {env_count} environmental failure(s)"
              f"{' + readiness gate' if args.degraded else ''} — INCONCLUSIVE, not filing.")

    # Scenario step-level breakdown
    sbd = build_scenario_breakdown(scenarios_data, current_per_test)

    # Print
    print_report(
        current_file, prev_file,
        current_domain_scores, current_overall,
        prev_domain_scores,    prev_overall,
        regressions, fixed, new_failures, still_broken,
        candidates,
        scenario_breakdown_data=sbd,
    )

    # Write campaign_report.json
    ts_label = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M")
    out_path  = Path(args.out_dir) / f"campaign_report_{ts_label}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "scorer_version": "1.1",
        "current_file":   str(current_file),
        "prev_file":      str(prev_file) if prev_file else None,
        "current_summary": current_data.get("summary", {}),
        "overall_score":  current_overall,
        "prev_overall":   prev_overall,
        "delta":          round(current_overall - prev_overall, 1) if (current_overall is not None and prev_overall is not None) else None,
        "health_band":    degraded_band()[0] if degraded else health_band(current_overall)[0],
        "degraded":       degraded,
        "env_count":      env_count,
        "domain_scores":  current_domain_scores,
        "regressions":    regressions,
        "fixed":          fixed,
        "new_failures":   new_failures,
        "still_broken":   still_broken,
        "notion_candidates": candidates,
        "per_test":       current_per_test,
        "scenario_breakdown": sbd,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"  📄  Report saved → {out_path}")
    print()

    unmapped_failing = report_unmapped(current_results, score_map)

    baseline = load_baseline()
    unexpected, stale = check_against_baseline(current_results, baseline)
    report_baseline(unexpected, stale, baseline)

    # Exit code. A DEGRADED run is inconclusive (environmental), never a hard failure and
    # never files, so it always exits clean.
    #
    # The gate is "a failure nobody wrote down", NOT the health band. Banding on RED alone
    # was unusable — known-open bugs like the RFQ 500 hold the band at RED permanently,
    # which is exactly why the workflow step wrapped this in continue-on-error and why no
    # test outcome could fail the campaign for months. Baseline the known ones; fail on the
    # rest. Regressions are covered: a test that passed before and fails now is unexpected
    # unless someone has baselined it deliberately.
    if not degraded and (unexpected or unmapped_failing):
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
