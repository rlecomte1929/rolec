#!/usr/bin/env python3
"""
[PERF-1 / AIQ-1014] Production-safe authenticated latency harness.

The existing ``scripts/perf_audit.py`` is local/static. This harness is the
instrument the rest of AIQ-1014 depends on: it logs in as real personas against a
deployed environment, hits the *actual* core authenticated endpoint set, and
measures warm latency separately from the first (cold) request — so we can tell
infra latency (Render cold-start) apart from app/DB latency.

Design notes
------------
- **Measure, don't change.** Read-only GETs against existing endpoints; auth and
  tenant checks run exactly as in production.
- **Cold vs warm.** The very first request after login is reported separately as
  the "cold" sample; the budget assertions apply to the warm p95/max only, so a
  one-off cold-start spike doesn't mask (or fail) the steady-state number. Use
  ``--cold-only`` against a freshly-idle service to characterise cold-start
  itself (PERF-2).
- **Honest about auth.** Non-2xx responses are surfaced per endpoint, never
  averaged in silently — a 401/403/405 means the persona/endpoint is
  mis-provisioned, which is a finding, not a latency number.
- **Budgets.** ``--assert`` exits non-zero if any 2xx endpoint breaches
  ``--p95-budget-ms`` (default 2000) or ``--max-budget-ms`` (default 3000).

The endpoint set is curated from ``frontend/src/api/client.ts`` (the real product
flows), grouped by persona. Override creds via env so secrets never live in the
repo:  PERF_ADMIN_ID/PERF_ADMIN_PW, PERF_HR_ID/PERF_HR_PW, PERF_EMP_ID/PERF_EMP_PW.

Usage
-----
    python scripts/perf_authed_harness.py                 # human table, all personas
    python scripts/perf_authed_harness.py --json          # machine-readable
    python scripts/perf_authed_harness.py --persona employee --samples 20
    python scripts/perf_authed_harness.py --assert        # CI/budget gate (non-zero on breach)
    python scripts/perf_authed_harness.py --cold-only      # characterise cold-start (PERF-2)
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_BASE_URL = os.environ.get("PERF_BASE_URL", "https://api.relopass.com")

# Demo creds — overridable via env so nothing secret is committed. These are the
# shared demo/seed accounts used for sales demos (their health is itself a P0).
PERSONAS: Dict[str, Dict[str, str]] = {
    "admin": {
        "id": os.environ.get("PERF_ADMIN_ID", "admin@relopass.com"),
        "pw": os.environ.get("PERF_ADMIN_PW", "Passw0rd!"),
    },
    "hr": {
        "id": os.environ.get("PERF_HR_ID", "hr@testingapril.com"),
        "pw": os.environ.get("PERF_HR_PW", "HrPass!1"),
    },
    "employee": {
        "id": os.environ.get("PERF_EMP_ID", "employee@testingapril.com"),
        "pw": os.environ.get("PERF_EMP_PW", "EmpPass!1"),
    },
}

# Core authenticated GET endpoints per persona — the product flows the latency
# audit cares about (curated from frontend/src/api/client.ts). Keep these as the
# *list* surfaces (no path params needed) so the harness runs without seeding a
# specific case id; per-case detail endpoints are out of scope for the budget gate.
CORE_ENDPOINTS: Dict[str, List[str]] = {
    "admin": [
        "/api/admin/people",
        "/api/admin/companies",
        "/api/admin/assignments",
        "/api/admin/policy-config/templates",
    ],
    "hr": [
        "/api/hr/command-center/cases",
        "/api/hr/cases",
        "/api/hr/assignments",
        "/api/hr/policy-config/templates",
    ],
    "employee": [
        "/api/employee/assignments/overview",
        "/api/employee/assignments/current",
        "/api/employee/policy/caps",
        "/api/employee/tasks",
    ],
}

LOGIN_PATH = "/api/auth/login"

# The API sits behind Cloudflare, which 403s the default ``Python-urllib`` agent.
# Send a normal browser UA so the harness measures the real app, not a WAF block.
USER_AGENT = os.environ.get(
    "PERF_USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124 Safari/537.36",
)


def _request(
    url: str, *, method: str = "GET", token: Optional[str] = None,
    body: Optional[bytes] = None, timeout: float = 45.0,
) -> Tuple[Optional[float], int, bytes]:
    """Return (elapsed_ms, status_code, body). elapsed_ms is None on transport error."""
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, headers=headers, data=body, method=method)
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
            return (time.time() - started) * 1000.0, resp.status, payload
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        return (time.time() - started) * 1000.0, exc.code, payload
    except Exception as exc:  # noqa: BLE001 — transport failure is a result, not a crash
        return None, 0, str(exc).encode("utf-8")


def login(base_url: str, identifier: str, password: str) -> Optional[str]:
    body = json.dumps({"identifier": identifier, "password": password}).encode("utf-8")
    ms, code, payload = _request(base_url + LOGIN_PATH, method="POST", body=body)
    if code != 200:
        return None
    try:
        return json.loads(payload).get("token") or None
    except Exception:
        return None


def _percentile(sorted_xs: List[float], pct: float) -> float:
    if not sorted_xs:
        return 0.0
    if len(sorted_xs) == 1:
        return sorted_xs[0]
    idx = max(0, min(len(sorted_xs) - 1, int(round(pct / 100.0 * len(sorted_xs))) - 1))
    return sorted_xs[idx]


def bench_endpoint(
    base_url: str, path: str, token: str, *, samples: int, cold_only: bool, delay_ms: float,
) -> Dict[str, Any]:
    url = base_url + path
    # The first request is the "cold" sample (kept separate from the warm set).
    cold_ms, cold_code, _ = _request(url, token=token)
    result: Dict[str, Any] = {
        "endpoint": path,
        "cold_ms": round(cold_ms, 1) if cold_ms is not None else None,
        "cold_status": cold_code,
        "warm": None,
        "rate_limited": 0,
        "statuses": sorted({cold_code}),
    }
    if cold_only:
        return result

    warm: List[float] = []
    statuses = {cold_code}
    rate_limited = 0
    for _ in range(samples):
        if delay_ms:
            time.sleep(delay_ms / 1000.0)  # pace to avoid self-inflicted slowapi 429s
        ms, code, _ = _request(url, token=token)
        statuses.add(code)
        if code == 429:
            rate_limited += 1
        if ms is not None and 200 <= code < 300:
            warm.append(ms)
    result["statuses"] = sorted(statuses)
    result["rate_limited"] = rate_limited
    if warm:
        warm.sort()
        result["warm"] = {
            "n": len(warm),
            "p50_ms": round(statistics.median(warm), 1),
            "p95_ms": round(_percentile(warm, 95), 1),
            "max_ms": round(max(warm), 1),
        }
    return result


def run(
    base_url: str, personas: List[str], *, samples: int, cold_only: bool, delay_ms: float,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"base_url": base_url, "samples": samples, "personas": {}}
    for name in personas:
        creds = PERSONAS[name]
        token = login(base_url, creds["id"], creds["pw"])
        persona_block: Dict[str, Any] = {"identifier": creds["id"], "logged_in": bool(token), "endpoints": []}
        if not token:
            persona_block["error"] = "login_failed"
            out["personas"][name] = persona_block
            continue
        for path in CORE_ENDPOINTS.get(name, []):
            persona_block["endpoints"].append(
                bench_endpoint(base_url, path, token, samples=samples, cold_only=cold_only, delay_ms=delay_ms)
            )
        out["personas"][name] = persona_block
    return out


def evaluate_budgets(result: Dict[str, Any], p95_budget: float, max_budget: float) -> List[str]:
    """Return a list of budget-breach strings for 2xx endpoints with warm samples."""
    breaches: List[str] = []
    for name, block in result["personas"].items():
        for ep in block.get("endpoints", []):
            warm = ep.get("warm")
            if not warm:
                continue
            if warm["p95_ms"] > p95_budget:
                breaches.append(f"{name} {ep['endpoint']}: p95 {warm['p95_ms']}ms > {p95_budget}ms")
            if warm["max_ms"] > max_budget:
                breaches.append(f"{name} {ep['endpoint']}: max {warm['max_ms']}ms > {max_budget}ms")
    return breaches


def print_table(result: Dict[str, Any]) -> None:
    print(f"\nAuthed latency harness — {result['base_url']}  (warm samples={result['samples']})")
    print("-" * 92)
    for name, block in result["personas"].items():
        if not block.get("logged_in"):
            print(f"[{name}] LOGIN FAILED ({block['identifier']}) — {block.get('error','')}")
            continue
        print(f"[{name}] {block['identifier']}")
        for ep in block["endpoints"]:
            warm = ep.get("warm")
            rl = f" rl={ep['rate_limited']}" if ep.get("rate_limited") else ""
            if warm:
                print(
                    f"  {ep['endpoint']:46s} cold={str(ep['cold_ms'])+'ms':>9s} "
                    f"p50={warm['p50_ms']:>7.0f} p95={warm['p95_ms']:>7.0f} "
                    f"max={warm['max_ms']:>7.0f}  status={ep['statuses']}{rl}"
                )
            else:
                print(
                    f"  {ep['endpoint']:46s} cold={str(ep['cold_ms'])+'ms':>9s} "
                    f"NO WARM 2xx SAMPLES        status={ep['statuses']}"
                )
    print("-" * 92)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Authenticated production latency harness (PERF-1/AIQ-1014).")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--persona", choices=list(PERSONAS), action="append",
                    help="Limit to one or more personas (default: all).")
    ap.add_argument("--samples", type=int, default=10, help="Warm samples per endpoint (default 10).")
    ap.add_argument("--cold-only", action="store_true",
                    help="Only measure the first (cold) request — characterise cold-start (PERF-2).")
    ap.add_argument("--delay-ms", type=float, default=250.0,
                    help="Pause between warm samples to avoid self-inflicted slowapi 429s (default 250).")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of the table.")
    ap.add_argument("--assert", dest="do_assert", action="store_true",
                    help="Exit non-zero if any warm 2xx endpoint breaches the budgets.")
    ap.add_argument("--p95-budget-ms", type=float, default=2000.0)
    ap.add_argument("--max-budget-ms", type=float, default=3000.0)
    args = ap.parse_args(argv)

    personas = args.persona or list(PERSONAS)
    result = run(args.base_url, personas, samples=args.samples, cold_only=args.cold_only, delay_ms=args.delay_ms)

    breaches = evaluate_budgets(result, args.p95_budget_ms, args.max_budget_ms)
    result["budget"] = {
        "p95_budget_ms": args.p95_budget_ms,
        "max_budget_ms": args.max_budget_ms,
        "breaches": breaches,
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_table(result)
        if breaches:
            print(f"\nBUDGET BREACHES ({len(breaches)}):")
            for b in breaches:
                print(f"  ✗ {b}")
        else:
            print("\nNo warm budget breaches.")

    if args.do_assert and breaches:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
