#!/usr/bin/env python3
"""Tenant-isolation (RLS) probe — the launch-critical "company A cannot see
company B's data" check, on freshly provisioned tenants.

Provisions two throwaway tenants (A and B) via the real APIs, each with an HR,
a case, and a published policy, then asserts — from each HR's perspective — that
they see ONLY their own company's data. A cross-tenant read is a LEAK (a
launch-blocking security failure), reported distinctly from a PASS.

Verdicts: PASS (isolated) | LEAK (cross-tenant access — security FAIL) |
FAIL (setup error) | BLOCKED (a prerequisite failed).

Usage:
    python3 scripts/verify_tenant_isolation.py

Throwaway tenants are namespaced ("Probe RLS-A/B <ts>", @probe.test) and cleaned
by scripts/fresh_onboarding_teardown.sql. NB: register is rate-limited 5/hour
(SEC-004) and this does 2 registrations, so run sparingly.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

API = os.environ.get("RELOPASS_API_BASE", "https://api.relopass.com")
UA = {"User-Agent": "relopass-tenant-isolation/1.0", "Content-Type": "application/json"}
GREEN, RED, GRY, RESET = "\033[92m", "\033[91m", "\033[90m", "\033[0m"

STAMP = os.environ.get("RELOPASS_PROBE_STAMP") or str(int(time.time()))
PW = "ProbePass!1"
A = {"email": f"probe-rls-a-{STAMP}@probe.test", "company": f"Probe RLS-A {STAMP}"}
B = {"email": f"probe-rls-b-{STAMP}@probe.test", "company": f"Probe RLS-B {STAMP}"}

_results = []


def call(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    h = dict(UA)
    if token:
        h["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{API}{path}", data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        b = e.read().decode()
        try:
            return e.code, json.loads(b)
        except Exception:
            return e.code, b[:160]
    except Exception as e:
        return 0, str(e)[:160]


def record(node, verdict, detail=""):
    _results.append((node, verdict))
    c = {"PASS": GREEN, "LEAK": RED, "FAIL": RED, "BLOCKED": GRY}.get(verdict, "")
    print(f"  [{c}{verdict:7}{RESET}] {node:46} {detail}")


def token_of(p):
    return p.get("token") if isinstance(p, dict) else None


def provision(t):
    """Register an HR + company, create a case, publish a policy. Returns
    (token, case_id, company_name)."""
    s, p = call("POST", "/api/auth/register", body={
        "email": t["email"], "password": PW, "role": "HR",
        "full_name": "Probe RLS HR", "company_name": t["company"]})
    tok = token_of(p)
    if not tok:
        return None, None, None
    call("POST", "/api/hr/company-profile", tok, {"name": t["company"], "country": "FR", "address": f"1 Rue {t['company']}"})
    call("POST", "/api/hr/policy-config/draft", tok, {})
    call("POST", "/api/hr/policy-config/publish", tok, {"effective_date": time.strftime("%Y-%m-%d")})
    cs, cp = call("POST", "/api/hr/cases", tok, {})
    case_id = (cp or {}).get("caseId") if isinstance(cp, dict) else None
    return tok, case_id, t["company"]


def main():
    print(f"\n  Tenant-isolation (RLS) probe  ({API})  A={A['company']} / B={B['company']}\n")

    tokA, caseA, _ = provision(A)
    record("setup: tenant A (HR + case + policy)", "PASS" if tokA and caseA else "FAIL",
           f"case={str(caseA)[:8] if caseA else None}")
    tokB, caseB, nameB = provision(B)
    record("setup: tenant B (HR + case + policy)", "PASS" if tokB and caseB else "FAIL",
           f"case={str(caseB)[:8] if caseB else None}")

    if not (tokA and tokB and caseA and caseB):
        record("isolation checks", "BLOCKED", "provisioning failed (rate limit? see 429)")
        _summary()
        return

    # ISO-1: A's case list must contain caseA and EXCLUDE caseB.
    s, p = call("GET", "/api/hr/cases", tokA)
    cases = [str(c.get("id")) for c in (p or {}).get("cases", [])] if isinstance(p, dict) else []
    if caseB in cases:
        record("ISO-1 A's case list excludes B's case", "LEAK", f"caseB visible to HR A! ({len(cases)} cases)")
    elif caseA in cases:
        record("ISO-1 A's case list excludes B's case", "PASS", f"{len(cases)} case(s), B absent")
    else:
        record("ISO-1 A's case list excludes B's case", "FAIL", f"A's own case missing ({len(cases)})")

    # ISO-2: A must NOT be able to read B's case detail.
    s, _ = call("GET", f"/api/hr/cases/{caseB}", tokA)
    record("ISO-2 A cannot read B's case detail", "PASS" if s in (403, 404) else "LEAK",
           f"HTTP {s}" + ("" if s in (403, 404) else " — expected 403/404"))

    # ISO-3: A cannot assign B's case.
    s, _ = call("POST", f"/api/hr/cases/{caseB}/assign", tokA, {"employeeIdentifier": A["email"]})
    record("ISO-3 A cannot assign B's case", "PASS" if s in (403, 404) else "LEAK", f"HTTP {s}")

    # ISO-4: A's company is A, not B.
    s, p = call("GET", "/api/company", tokA)
    cname = (p or {}).get("company", {}).get("name") if isinstance(p, dict) else None
    if cname == nameB:
        record("ISO-4 A's company is not B", "LEAK", f"HR A sees company {cname!r}")
    else:
        record("ISO-4 A's company is not B", "PASS", f"company={cname!r}")

    # ISO-5: symmetric — B's case list excludes A's case.
    s, p = call("GET", "/api/hr/cases", tokB)
    casesB = [str(c.get("id")) for c in (p or {}).get("cases", [])] if isinstance(p, dict) else []
    record("ISO-5 B's case list excludes A's case", "LEAK" if caseA in casesB else "PASS",
           f"{len(casesB)} case(s)")

    _summary()


def _summary():
    print()
    counts = {}
    for _, v in _results:
        counts[v] = counts.get(v, 0) + 1
    print("  Summary: " + "  ".join(f"{k}={counts[k]}" for k in ("PASS", "LEAK", "FAIL", "BLOCKED") if k in counts))
    print(f"  Tenant stamp: {STAMP}  — teardown: scripts/fresh_onboarding_teardown.sql via MCP")
    leaks = [n for (n, v) in _results if v == "LEAK"]
    if leaks:
        print(f"  {RED}LAUNCH-BLOCKER: {len(leaks)} cross-tenant leak(s){RESET}")
    sys.exit(1 if any(v in ("LEAK", "FAIL") for _, v in _results) else 0)


if __name__ == "__main__":
    main()
