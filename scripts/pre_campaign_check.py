#!/usr/bin/env python3
"""
ReloPass Pre-Campaign Check  v1.1
===================================
Pre-flight validation before launching a test campaign. Verifies that:
  1. API endpoints are reachable (platform health check)
  2. scoring_map.json and scenarios.json are present and consistent
  3. All test IDs in scoring_map.json have a corresponding scenario step or standalone test
  4. No stale "previous campaign" lock conflict (campaigns.json integrity)
  5. Environment variables required by the E2E runner are set
  6. Demo/seed personas are provisioned in dependency order (SKILL.md Phase 0.5)
     — catches the class where the runner is green (fresh, company-linked accounts)
     while the demo accounts used for sales/pilots are broken (e.g. HR with no
     company link → policy 400). A broken HR↔company link fails the pre-flight.

Run this before every campaign to catch configuration drift early.

Usage:
    python3 scripts/pre_campaign_check.py
    python3 scripts/pre_campaign_check.py --skip-api    # skip live API checks (offline mode)
    python3 scripts/pre_campaign_check.py --strict      # exit 1 on any WARNING (not just ERROR)

Exit codes:
    0 — all checks passed (green to run campaign)
    1 — one or more ERRORs (do not run campaign)
    2 — one or more WARNINGs and --strict flag set
"""

import argparse
import json
import os
import sys
import glob
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR     = Path(__file__).parent
REPO_ROOT      = SCRIPT_DIR.parent
RESULTS_DIR    = REPO_ROOT / "results"
MAP_FILE       = SCRIPT_DIR / "scoring_map.json"
SCENARIOS_FILE = SCRIPT_DIR / "scenarios.json"
CAMPAIGNS_FILE = RESULTS_DIR / "campaigns.json"

# ── API endpoints to health-check ─────────────────────────────────────────────
API_BASE = os.environ.get("RELOPASS_API_BASE", "https://api.relopass.com")
HEALTH_ENDPOINTS = [
    f"{API_BASE}/health",
    f"{API_BASE}/api/auth/login",   # check it's not 404
]

# ── Required env vars (for the E2E runner) ────────────────────────────────────
REQUIRED_ENV_VARS = [
    "RELOPASS_ADMIN_EMAIL",
    "RELOPASS_ADMIN_PASSWORD",
]
OPTIONAL_ENV_VARS = [
    "RELOPASS_API_BASE",
    "RELOPASS_HR_EMAIL",
    "RELOPASS_HR_PASSWORD",
]

# ── Colours ────────────────────────────────────────────────────────────────────
BOLD  = "\033[1m"
RESET = "\033[0m"
GREEN = "\033[92m"
RED   = "\033[91m"
AMBER = "\033[93m"
GREY  = "\033[90m"
BLUE  = "\033[94m"

# ── Result collector ──────────────────────────────────────────────────────────
class CheckResults:
    def __init__(self):
        self.errors   = []
        self.warnings = []
        self.passes   = []

    def ok(self, msg):
        self.passes.append(msg)
        print(f"  {GREEN}✔{RESET}  {msg}")

    def warn(self, msg):
        self.warnings.append(msg)
        print(f"  {AMBER}⚠{RESET}  {msg}")

    def error(self, msg):
        self.errors.append(msg)
        print(f"  {RED}✘{RESET}  {msg}")

    def section(self, title):
        print(f"\n  {BOLD}{title}{RESET}")
        print(f"  {'─' * (len(title) + 2)}")

    def summary(self):
        print(f"\n  {'═' * 56}")
        total = len(self.passes) + len(self.warnings) + len(self.errors)
        if self.errors:
            print(f"  {RED}{BOLD}  PRE-FLIGHT FAILED — {len(self.errors)} error(s), {len(self.warnings)} warning(s){RESET}")
            for e in self.errors:
                print(f"    {RED}✘{RESET} {e}")
        elif self.warnings:
            print(f"  {AMBER}{BOLD}  PRE-FLIGHT PASSED WITH WARNINGS — {len(self.warnings)} warning(s){RESET}")
            for w in self.warnings:
                print(f"    {AMBER}⚠{RESET} {w}")
        else:
            print(f"  {GREEN}{BOLD}  ALL CHECKS PASSED ({total} checks) — safe to run campaign{RESET}")
        print(f"  {'═' * 56}\n")

# ── Individual checks ─────────────────────────────────────────────────────────

def check_files(r):
    """Verify all required reference files are present."""
    r.section("1. Reference files")

    if MAP_FILE.exists():
        r.ok(f"scoring_map.json found ({MAP_FILE.stat().st_size // 1024 + 1}KB)")
    else:
        r.error(f"scoring_map.json MISSING at {MAP_FILE}")

    if SCENARIOS_FILE.exists():
        r.ok(f"scenarios.json found ({SCENARIOS_FILE.stat().st_size // 1024 + 1}KB)")
    else:
        r.warn("scenarios.json not found — step-level breakdown will be skipped")

    if CAMPAIGNS_FILE.exists():
        r.ok(f"campaigns.json found")
    else:
        r.warn("campaigns.json not found — campaign registry will not be updated")

    results_files = sorted(glob.glob(str(RESULTS_DIR / "test_results_*.json")))
    if results_files:
        latest = Path(results_files[-1]).name
        r.ok(f"results/ has {len(results_files)} test_results file(s) — latest: {latest}")
    else:
        r.warn("No test_results_*.json in results/ — this will be the first campaign")


def check_env_vars(r):
    """Check required and optional environment variables."""
    r.section("2. Environment variables")

    for var in REQUIRED_ENV_VARS:
        val = os.environ.get(var)
        if val:
            r.ok(f"{var} is set")
        else:
            r.warn(f"{var} not set — E2E runner may use hardcoded fallbacks")

    for var in OPTIONAL_ENV_VARS:
        val = os.environ.get(var)
        if val:
            r.ok(f"{var} = {val}")
        else:
            r.warn(f"{var} not set (optional)")


def check_api(r, skip_api):
    """Hit health endpoints to verify the platform is up."""
    r.section("3. Platform reachability")

    if skip_api:
        r.warn("API checks skipped (--skip-api flag)")
        return

    for url in HEALTH_ENDPOINTS:
        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "ReloPass-PreCampaignCheck/1.0")
            with urllib.request.urlopen(req, timeout=8) as resp:
                status = resp.status
                if status < 500:
                    r.ok(f"GET {url} → {status}")
                else:
                    r.error(f"GET {url} → {status} (server error)")
        except urllib.error.HTTPError as e:
            # 401/403/405 are acceptable — endpoint exists
            if e.code in (401, 403, 405, 422):
                r.ok(f"GET {url} → {e.code} (endpoint reachable)")
            else:
                r.error(f"GET {url} → {e.code} {e.reason}")
        except urllib.error.URLError as e:
            r.error(f"GET {url} → UNREACHABLE ({e.reason})")
        except Exception as e:
            r.error(f"GET {url} → ERROR: {e}")


def check_scoring_map_consistency(r):
    """Validate scoring_map.json structure and cross-reference with scenarios.json."""
    r.section("4. Scoring map consistency")

    if not MAP_FILE.exists():
        r.error("scoring_map.json missing — skipping consistency checks")
        return

    try:
        score_map = json.loads(MAP_FILE.read_text())
    except json.JSONDecodeError as e:
        r.error(f"scoring_map.json is invalid JSON: {e}")
        return

    tests     = score_map.get("tests", {})
    meta      = score_map.get("_meta", {})
    rules     = meta.get("scoring_rules", {})
    weights   = rules.get("domain_weights", {})

    if not tests:
        r.error("scoring_map.json has no tests defined")
        return

    r.ok(f"scoring_map.json has {len(tests)} test definitions")

    # Check every test has a domain that exists in domain_weights
    missing_domains = set()
    for tid, t in tests.items():
        d = t.get("domain")
        if d and d not in weights:
            missing_domains.add(d)

    if missing_domains:
        r.warn(f"Tests reference domains not in domain_weights: {sorted(missing_domains)}")
    else:
        r.ok(f"All {len(weights)} domains have weights defined")

    # Cross-check with scenarios.json if present
    if SCENARIOS_FILE.exists():
        try:
            scenarios_data = json.loads(SCENARIOS_FILE.read_text())
            scenarios = scenarios_data.get("scenarios", {})
            run_order = scenarios_data.get("_meta", {}).get("run_order", [])

            # Collect all test_ids referenced in scenarios
            scenario_test_ids = set()
            for sc in scenarios.values():
                for step in sc.get("steps", []):
                    tid = step.get("test_id")
                    if tid:
                        scenario_test_ids.add(tid)

            # Tests in scoring_map but not referenced in any scenario step
            unscenarioed = set(tests.keys()) - scenario_test_ids
            # Filter to only FLOW-type tests or known standalone tests
            standalone_ok = {tid for tid in unscenarioed
                             if any(tid.startswith(p) for p in ("CORS", "RE1", "PERF", "RL1", "SEC1", "HP2", "RLS", "EP1", "VT1", "RT1"))}
            truly_orphaned = unscenarioed - standalone_ok

            if truly_orphaned:
                r.warn(f"{len(truly_orphaned)} scoring_map test(s) not referenced in scenarios.json: {sorted(truly_orphaned)[:5]}")
            else:
                r.ok(f"All non-standalone tests are referenced in at least one scenario step")

            # Scenarios in run_order but not in scenarios dict
            missing_from_dict = []
            for short_id in run_order:
                full_id = f"{short_id}_FLOW"
                if short_id not in scenarios and full_id not in scenarios:
                    missing_from_dict.append(short_id)
            if missing_from_dict:
                r.warn(f"run_order references scenarios not in scenarios dict: {missing_from_dict}")
            else:
                r.ok(f"All {len(run_order)} run_order entries have a matching scenario")

        except json.JSONDecodeError as e:
            r.error(f"scenarios.json is invalid JSON: {e}")


def check_campaigns_registry(r):
    """Verify campaigns.json integrity."""
    r.section("5. Campaign registry integrity")

    if not CAMPAIGNS_FILE.exists():
        r.warn("campaigns.json not found — will be created on first campaign close")
        return

    try:
        reg = json.loads(CAMPAIGNS_FILE.read_text())
    except json.JSONDecodeError as e:
        r.error(f"campaigns.json is invalid JSON: {e}")
        return

    campaigns = reg.get("campaigns", [])
    r.ok(f"campaigns.json has {len(campaigns)} campaign(s) recorded")

    if campaigns:
        latest = campaigns[-1]
        label  = latest.get("label", "?")
        date   = latest.get("date", "?")
        score  = latest.get("overall_score", "?")
        band   = latest.get("health_band", "?")
        r.ok(f"Latest campaign: {label} ({date}) — {score}% {band}")

        # Verify the referenced files still exist
        for field in ("results_file", "report_file"):
            path_str = latest.get(field)
            if path_str:
                path = REPO_ROOT / path_str
                if path.exists():
                    r.ok(f"{field} exists: {Path(path_str).name}")
                else:
                    r.warn(f"{field} not found: {path_str}")

    # Check IDs are monotonic
    ids = [c.get("id") for c in campaigns]
    expected = list(range(1, len(ids) + 1))
    if ids == expected:
        r.ok("Campaign IDs are sequential (1, 2, 3, ...)")
    else:
        r.warn(f"Campaign IDs are not sequential: {ids}")


# ── Phase 0.5: persona precondition checks ────────────────────────────────────
# The demo/seed accounts are what real demos + pilots log in as; their health is a
# P0 precondition. The automated runner mints fresh, perfectly-provisioned accounts,
# so it stays green while these drift. Overridable via env for non-default envs.
DEMO_HR_EMAIL     = os.environ.get("RELOPASS_DEMO_HR_EMAIL",     "hr@testingapril.com")
DEMO_HR_PASSWORD  = os.environ.get("RELOPASS_DEMO_HR_PASSWORD",  "HrPass!1")
DEMO_EMP_EMAIL    = os.environ.get("RELOPASS_DEMO_EMP_EMAIL",    "employee@testingapril.com")
DEMO_EMP_PASSWORD = os.environ.get("RELOPASS_DEMO_EMP_PASSWORD", "EmpPass!1")


def _http_json(method, path, token=None, body=None, timeout=10):
    """Minimal API call. Returns (status:int, text:str); status=0 on transport error."""
    url = path if path.startswith("http") else f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", "ReloPass-PreCampaignCheck/1.1")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", "replace") if e.fp else ""
        return e.code, body_txt
    except Exception as e:  # URLError, timeout, etc.
        return 0, str(e)


def _login(email, password):
    """POST /api/auth/login. Returns (token|None, detail)."""
    status, text = _http_json("POST", "/api/auth/login",
                              body={"identifier": email, "password": password})
    if status == 0:
        return None, f"transport error: {text}"
    if status != 200:
        return None, f"HTTP {status}"
    try:
        payload = json.loads(text)
        tok = payload.get("token") or payload.get("access_token")
    except json.JSONDecodeError:
        tok = None
    return (tok, "ok") if tok else (None, "no token in response")


def check_persona_preconditions(r, skip_api):
    """Phase 0.5 — verify demo/seed personas in dependency order.

    Dependency chain: company → HR linked to company → cases → employee. We assert
    the demo accounts (what sales/pilots log in as) are healthy at each link. The
    HR↔company check is the one that would have caught the missing hr_users link
    that 400'd every policy endpoint while the runner stayed green.
    """
    r.section("6. Persona preconditions (dependency order)")

    if skip_api:
        r.warn("Persona precondition checks skipped (--skip-api flag)")
        return

    # ── HR persona: login → company link → cases ──
    hr_token, detail = _login(DEMO_HR_EMAIL, DEMO_HR_PASSWORD)
    if not hr_token:
        r.error(f"HR demo login failed ({DEMO_HR_EMAIL}): {detail} "
                f"— set RELOPASS_DEMO_HR_EMAIL/PASSWORD if creds changed")
    else:
        r.ok(f"HR demo login OK ({DEMO_HR_EMAIL})")

        # THE check: HR ↔ company. A missing hr_users link → 400 on every policy
        # endpoint (the exact prod break this section exists to catch).
        status, body = _http_json("GET", "/api/hr/policy-config", token=hr_token)
        if status == 400 and "company association" in body.lower():
            r.error(f"HR demo has NO company association ({DEMO_HR_EMAIL}) — hr_users "
                    f"link missing; every HR policy endpoint 400s. Seed "
                    f"hr_users(profile_id, company_id) before running (SKILL.md Phase 0.5).")
        elif status == 200:
            r.ok("HR ↔ company link OK (policy-config → 200)")
        else:
            r.warn(f"HR policy-config → {status} (expected 200)")

        status, _ = _http_json("GET", "/api/hr/cases", token=hr_token)
        if status == 200:
            r.ok("HR cases endpoint OK (→ 200)")
        else:
            r.warn(f"HR /api/hr/cases → {status} (expected 200)")

    # ── Employee persona: login → assignments overview ──
    emp_token, detail = _login(DEMO_EMP_EMAIL, DEMO_EMP_PASSWORD)
    if not emp_token:
        r.error(f"Employee demo login failed ({DEMO_EMP_EMAIL}): {detail}")
    else:
        r.ok(f"Employee demo login OK ({DEMO_EMP_EMAIL})")
        status, _ = _http_json("GET", "/api/employee/assignments/overview", token=emp_token)
        if status == 200:
            r.ok("Employee assignments overview OK (→ 200)")
        else:
            r.warn(f"Employee /api/employee/assignments/overview → {status} (expected 200)")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="ReloPass Pre-Campaign Check")
    parser.add_argument("--skip-api", action="store_true", help="Skip live API reachability checks")
    parser.add_argument("--strict",   action="store_true", help="Exit 1 on warnings (not just errors)")
    args = parser.parse_args()

    print()
    print(f"  {BOLD}ReloPass Pre-Campaign Check  v1.1{RESET}")
    print(f"  {GREY}Run: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}{RESET}")

    r = CheckResults()

    check_files(r)
    check_env_vars(r)
    check_api(r, skip_api=args.skip_api)
    check_scoring_map_consistency(r)
    check_campaigns_registry(r)
    check_persona_preconditions(r, skip_api=args.skip_api)

    r.summary()

    if r.errors:
        sys.exit(1)
    if r.warnings and args.strict:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
