#!/usr/bin/env python3
"""Fresh-onboarding vertical-slice probe.

Provisions a BRAND-NEW throwaway tenant through the real Admin -> HR -> Company ->
Policy -> Employee chain and reports a per-node verdict, so we can see — with
evidence, not code-reads — which onboarding functionalities actually work for a
real new customer (the state the pre-seeded demo accounts hide).

Corridor is held constant at the already-proven FR -> NO, work, single, no
family — so any failure isolates to an *onboarding* link, not the case engine.

Design:
  * Loginable HR/employee accounts are created via POST /api/auth/register with
    known passwords (no DB credential-bridge needed). The employee is linked to
    the HR's case via claim-on-login (reconcile_pending_assignment_claims).
  * The admin->HR provisioning + the invite->login handoff (B2) are tested
    SEPARATELY and reported honestly — an admin-created account is invite-email
    only, so its automated login is expected to fail; that's a real finding.

Verdicts per node: PASS (real data) | EMPTY (200 but nothing) | FAIL (4xx/5xx /
missing) | BLOCKED (a prerequisite failed). The probe continues through every
node it can, to map the whole chain in one run.

Usage:
    python3 scripts/verify_fresh_onboarding.py
    RELOPASS_API_BASE=https://api.relopass.com python3 scripts/verify_fresh_onboarding.py
    python3 scripts/verify_fresh_onboarding.py --keep   # skip teardown for inspection

Admin creds default to the static platform admin; override with env if needed.
A timestamped tenant ("Probe Co <ts>") + namespaced emails keep it isolated;
teardown is `scripts/fresh_onboarding_teardown.sql` (run via the Supabase MCP).

RATE LIMIT: POST /api/auth/register is capped at 5/hour;20/day (SEC-004). Each
run does 2 registrations (HR + employee), so don't run more than ~2x/hour or
N10 returns 429 (a probe constraint, not a platform bug).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = os.environ.get("RELOPASS_API_BASE", "https://api.relopass.com")
from _prod_write_guard import guard_prod_writes  # noqa: E402
guard_prod_writes(API)  # AIQ-913: refuse to seed prod by accident
ADMIN_EMAIL = os.environ.get("RELOPASS_ADMIN_EMAIL", "admin@relopass.com")
ADMIN_PASS = os.environ.get("RELOPASS_ADMIN_PASSWORD", "Passw0rd!")
UA = {"User-Agent": "relopass-fresh-onboarding/1.0", "Content-Type": "application/json"}

GREEN, RED, YEL, GRY, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[90m", "\033[0m"

# Stamp a unique, recognizable tenant so runs never collide or pollute the demo.
STAMP = os.environ.get("RELOPASS_PROBE_STAMP") or str(int(time.time()))
HR_EMAIL = f"probe-hr-{STAMP}@probe.test"
EMP_EMAIL = f"probe-emp-{STAMP}@probe.test"
ADMIN_HR_EMAIL = f"probe-adminhr-{STAMP}@probe.test"  # the admin-CREATED HR (B2 node)
PW = "ProbePass!1"
COMPANY_NAME = f"Probe Co {STAMP}"
ADMIN_COMPANY_NAME = f"Probe AdminCo {STAMP}"

_results = []  # (node, verdict, detail)
_ctx = {}      # shared state across nodes (tokens, ids)


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
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body[:200]
    except Exception as e:  # network etc.
        return 0, str(e)[:200]


def record(node, verdict, detail=""):
    _results.append((node, verdict, detail))
    color = {"PASS": GREEN, "EMPTY": YEL, "FAIL": RED, "BLOCKED": GRY}.get(verdict, "")
    print(f"  [{color}{verdict:7}{RESET}] {node:42} {detail}")


def token_of(payload):
    if not isinstance(payload, dict):
        return None
    return payload.get("token") or payload.get("access_token") or payload.get("relopass_token")


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()

    print(f"\n  Fresh-onboarding probe  ({API})  tenant=Probe Co {STAMP}\n")

    # ── N1: Admin login ──────────────────────────────────────────────────────
    s, p = call("POST", "/api/auth/login", body={"identifier": ADMIN_EMAIL, "password": ADMIN_PASS})
    admin = token_of(p)
    record("N1 admin login", "PASS" if admin else "FAIL", f"HTTP {s}")

    # ── N2: Admin creates a company ──────────────────────────────────────────
    if admin:
        s, p = call("POST", "/api/admin/companies", admin, {
            "name": ADMIN_COMPANY_NAME, "country": "FR",
            "address": "10 Rue de Test, 75001 Paris", "phone": "+33100000000",
        })
        comp = (p or {}).get("company") if isinstance(p, dict) else None
        cid = comp.get("id") if isinstance(comp, dict) else None
        _ctx["admin_company_id"] = cid
        record("N2 admin creates company", "PASS" if (s in (200, 201) and cid) else "FAIL", f"HTTP {s} id={str(cid)[:8] if cid else None}")
    else:
        record("N2 admin creates company", "BLOCKED", "no admin token")

    # ── N3: Admin creates an HR linked to that company ───────────────────────
    if admin and _ctx.get("admin_company_id"):
        s, p = call("POST", "/api/admin/people", admin, {
            "email": ADMIN_HR_EMAIL, "full_name": "Probe Admin-HR",
            "role": "HR", "company_id": _ctx["admin_company_id"],
            "password": PW,  # B2: initial password -> loginable users row
        })
        ok = s in (200, 201)
        person = (p or {}).get("person") if isinstance(p, dict) else None
        _ctx["admin_hr_id"] = person.get("id") if isinstance(person, dict) else None
        _ctx["admin_hr_login_ready"] = (p or {}).get("login_ready") if isinstance(p, dict) else None
        record("N3 admin creates HR (+initial password)", "PASS" if ok else "FAIL",
               f"HTTP {s} login_ready={_ctx.get('admin_hr_login_ready')}")
    else:
        record("N3 admin creates HR (+initial password)", "BLOCKED", "no admin/company")

    # ── N4: B2 — the admin-created HR logs in with the initial password ───────
    # With an initial password, admin-create now writes a loginable `users` row,
    # so the admin->HR handoff completes without the email link.
    if _ctx.get("admin_hr_id") is not None or admin:
        s, p = call("POST", "/api/auth/login", body={"identifier": ADMIN_HR_EMAIL, "password": PW})
        if token_of(p):
            record("N4 admin-created HR can log in (B2)", "PASS", f"HTTP {s} (B2 closed)")
        else:
            record("N4 admin-created HR can log in (B2)", "FAIL",
                   f"HTTP {s} — admin-created HR still not loginable")
    else:
        record("N4 admin-created HR can log in (B2)", "BLOCKED", "N3 failed")

    # ── N5: Provision a loginable HR for the functional chain (register) ─────
    s, p = call("POST", "/api/auth/register", body={
        "email": HR_EMAIL, "password": PW, "role": "HR",
        "full_name": "Probe HR", "company_name": COMPANY_NAME,
    })
    hr = token_of(p)
    _ctx["hr"] = hr
    record("N5 loginable HR (register + company)", "PASS" if hr else "FAIL", f"HTTP {s}")

    # ── N6: HR fills the company profile (ADDRESS) ───────────────────────────
    if hr:
        s, p = call("POST", "/api/hr/company-profile", hr, {
            "name": COMPANY_NAME, "country": "FR",
            "address": "25 Avenue des Tests, 69002 Lyon", "phone": "+33400000000",
            "hq_city": "Lyon", "industry": "Software", "size_band": "50-200",
            "support_email": f"hr+{STAMP}@probe.test",
        })
        ok = s in (200, 201)
        # verify it round-trips
        gs, gp = call("GET", "/api/hr/company-profile", hr)
        addr = (gp or {}).get("address") if isinstance(gp, dict) else None
        _ctx["company_id"] = (gp or {}).get("id") or (gp or {}).get("company_id") if isinstance(gp, dict) else None
        if ok and addr:
            record("N6 HR fills company address", "PASS", f"address persisted: {addr[:32]!r}")
        elif ok:
            record("N6 HR fills company address", "EMPTY", f"saved {s} but address not read back (GET {gs})")
        else:
            record("N6 HR fills company address", "FAIL", f"HTTP {s}")
    else:
        record("N6 HR fills company address", "BLOCKED", "no HR token")

    # ── N7: HR configures + publishes a relocation policy ────────────────────
    if hr:
        ds, dp = call("POST", "/api/hr/policy-config/draft", hr, {})
        today = time.strftime("%Y-%m-%d")
        ps, pp = call("POST", "/api/hr/policy-config/publish", hr, {"effective_date": today})
        ok = ps in (200, 201)
        ver = (pp or {}).get("version_number") or (pp or {}).get("policy_version") if isinstance(pp, dict) else None
        if ok:
            record("N7 HR publishes policy", "PASS", f"draft {ds} -> publish {ps} v={ver}")
        else:
            record("N7 HR publishes policy", "FAIL", f"draft {ds} publish {ps}: {str(pp)[:80]}")
    else:
        record("N7 HR publishes policy", "BLOCKED", "no HR token")

    # ── N8: HR creates a case ────────────────────────────────────────────────
    if hr:
        s, p = call("POST", "/api/hr/cases", hr, {})
        case_id = (p or {}).get("caseId") or (p or {}).get("case_id") if isinstance(p, dict) else None
        _ctx["case_id"] = case_id
        record("N8 HR creates case", "PASS" if case_id else "FAIL", f"HTTP {s} case={str(case_id)[:8] if case_id else None}")
    else:
        record("N8 HR creates case", "BLOCKED", "no HR token")

    # ── N9: HR assigns the employee (by email) ───────────────────────────────
    if hr and _ctx.get("case_id"):
        s, p = call("POST", f"/api/hr/cases/{_ctx['case_id']}/assign", hr, {"employeeIdentifier": EMP_EMAIL})
        ok = s in (200, 201)
        if isinstance(p, dict):
            _ctx["assignment_id"] = p.get("assignmentId") or p.get("assignment_id")
            _ctx["invite_token"] = p.get("inviteToken") or p.get("invite_token")
        record("N9 HR assigns employee (invite)", "PASS" if ok else "FAIL",
               f"HTTP {s} asg={str(_ctx.get('assignment_id'))[:8]} token={'yes' if _ctx.get('invite_token') else 'no'}")
    else:
        record("N9 HR assigns employee (invite)", "BLOCKED", "no HR/case")

    # ── N10: Employee registers -> claim-on-login links the case ─────────────
    s, p = call("POST", "/api/auth/register", body={
        "email": EMP_EMAIL, "password": PW, "role": "EMPLOYEE", "full_name": "Probe Employee",
    })
    emp = token_of(p)
    _ctx["emp"] = emp
    record("N10 employee registers", "PASS" if emp else "FAIL", f"HTTP {s}")

    # ── N10b: Employee claims the assignment via the invite token ────────────
    # pending_claim assignments are NOT auto-reconciled on register — the
    # employee must explicitly claim with the invite token.
    if emp and _ctx.get("invite_token"):
        cs, cp = call("POST", "/api/employee/assignments/claim-by-token", emp, {"token": _ctx["invite_token"]})
        ok = cs in (200, 201) and isinstance(cp, dict) and cp.get("success")
        record("N10b employee claims case (by token)", "PASS" if ok else "FAIL",
               f"HTTP {cs}" + ("" if ok else f": {str(cp)[:80]}"))
    elif emp:
        record("N10b employee claims case (by token)", "BLOCKED", "no invite token from N9")
    else:
        record("N10b employee claims case (by token)", "BLOCKED", "no employee token")

    # ── N11: Employee drives intake FR->NO (work) -> bridge -> forms ─────────
    if emp and _ctx.get("case_id"):
        s, _ = call("PATCH", f"/api/cases/{_ctx['case_id']}", emp, {
            "relocationBasics": {"originCountry": "France", "originCity": "Lyon",
                                 "destCountry": "NO", "destCity": "Oslo",
                                 "purpose": "work", "targetMoveDate": "2026-09-01"}})
        fs, fp = call("GET", f"/api/cases/{_ctx['case_id']}/forms", emp)
        forms = fp if isinstance(fp, list) else (fp or {}).get("forms", []) if isinstance(fp, dict) else []
        if s == 200 and len(forms) >= 1:
            record("N11 employee intake -> roadmap/dossier", "PASS", f"PATCH {s}, {len(forms)} forms")
        elif s == 200:
            record("N11 employee intake -> roadmap/dossier", "EMPTY", f"PATCH {s} but 0 forms (bridge/templates?)")
        else:
            record("N11 employee intake -> roadmap/dossier", "FAIL", f"PATCH {s} forms {fs}")
    else:
        record("N11 employee intake -> roadmap/dossier", "BLOCKED", "no employee/case")

    # ── N12: Employee benefits == the HR-published policy (the connection) ───
    if emp and _ctx.get("case_id"):
        s, p = call("GET", f"/api/employee/policy-config?caseId={_ctx['case_id']}", emp)
        cats = (p or {}).get("categories") if isinstance(p, dict) else None
        has_policy = (p or {}).get("has_policy_config") if isinstance(p, dict) else None
        if s == 200 and cats:
            record("N12 employee benefits from HR policy", "PASS", f"{len(cats)} categories, has_policy={has_policy}")
        elif s == 200:
            record("N12 employee benefits from HR policy", "EMPTY", f"200 but no benefit categories (has_policy={has_policy})")
        else:
            record("N12 employee benefits from HR policy", "FAIL", f"HTTP {s}: {str(p)[:80]}")
    else:
        record("N12 employee benefits from HR policy", "BLOCKED", "no employee/case")

    # ── Summary ──────────────────────────────────────────────────────────────
    print()
    counts = {}
    for _, v, _d in _results:
        counts[v] = counts.get(v, 0) + 1
    summary = "  ".join(f"{k}={counts[k]}" for k in ("PASS", "EMPTY", "FAIL", "BLOCKED") if k in counts)
    print(f"  Summary: {summary}")
    print(f"  Tenant stamp: {STAMP}  (HR={HR_EMAIL}, EMP={EMP_EMAIL})")
    print("  Teardown: run scripts/fresh_onboarding_teardown.sql via the Supabase MCP")
    print("  (scoped by 'Probe %' / @probe.test — cleans every probe run's tenant).")
    # Exit non-zero if any node FAILs (B2/N4 is now fixed, so it counts too).
    hard = [n for (n, v, _d) in _results if v == "FAIL"]
    sys.exit(1 if hard else 0)


if __name__ == "__main__":
    main()
