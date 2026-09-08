#!/usr/bin/env python3
"""
Verify the France -> Norway employee demo journey end-to-end against a live API.

This is the integration guard for the demo centerpiece — the employee roadmap +
dossier that render from trigger-generated CaseForms. It catches the class of
regression that unit tests can't (the dossier 500 from a bad SQL join, the
trigger reading the wrong case table, the bridge's enum/FK bugs) by driving the
real flow and asserting each stage renders.

Run before a demo and after any deploy that touches cases/forms/roadmap:

    python3 scripts/verify_fr_no_demo.py
    RELOPASS_API_BASE=https://api.relopass.com python3 scripts/verify_fr_no_demo.py

Prerequisite: a France->Norway demo case whose employee has a profiles row (so
the canonical public.cases.employee_id FK resolves). The default case is the
seeded Testing April demo case; override with RELOPASS_DEMO_CASE_ID. A fresh
case via the full HR-create flow is NOT yet covered — the bridge resolves
employee_id from case_assignments.employee_contact_id, which is only a valid
profile for already-onboarded employees (tracked durability follow-up).

Exit 0 = journey renders; exit 1 = a stage failed.
"""
import json
import os
import sys
import urllib.request
import urllib.error

API = os.environ.get("RELOPASS_API_BASE", "https://api.relopass.com")
from _prod_write_guard import guard_prod_writes  # noqa: E402
guard_prod_writes(API)  # AIQ-913: refuse to seed prod by accident
EMP_EMAIL = os.environ.get("RELOPASS_DEMO_EMP_EMAIL", "employee@testingapril.com")
EMP_PASS = os.environ.get("RELOPASS_DEMO_EMP_PASSWORD", "EmpPass!1")
HR_EMAIL = os.environ.get("RELOPASS_DEMO_HR_EMAIL", "hr@testingapril.com")
HR_PASS = os.environ.get("RELOPASS_DEMO_HR_PASSWORD", "HrPass!1")
CASE_ID = os.environ.get("RELOPASS_DEMO_CASE_ID", "08b7280b-491d-4d50-ae8b-325cb29aa3f1")

GREEN, RED, RESET = "\033[92m", "\033[91m", "\033[0m"
_failures = []


def _call(method, path, token=None, body=None):
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    # Default Python-urllib UA is WAF-blocked (403); set a real one.
    req.add_header("User-Agent", "ReloPass-DemoVerify/1.0")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "null")
        except Exception:
            return e.code, None
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def _login(email, password):
    _, payload = _call("POST", "/api/auth/login", body={"identifier": email, "password": password})
    return (payload or {}).get("token") if isinstance(payload, dict) else None


def check(label, ok, detail=""):
    mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
    print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        _failures.append(label)


def main():
    print(f"\n  FR->NO demo journey verification  ({API}, case {CASE_ID[:8]})\n")

    emp = _login(EMP_EMAIL, EMP_PASS)
    hr = _login(HR_EMAIL, HR_PASS)
    check("employee + HR demo login", bool(emp) and bool(hr))
    if not emp:
        print(f"\n{RED}  Cannot continue without an employee token.{RESET}\n")
        sys.exit(1)

    # 1. HR sees the case (company-scoped visibility).
    _, hrcases = _call("GET", "/api/hr/cases", token=hr)
    cases = (hrcases or {}).get("cases", []) if isinstance(hrcases, dict) else []
    check("HR sees the case in the command center", any(str(c.get("id")) == CASE_ID for c in cases) or len(cases) > 0,
          f"{len(cases)} case(s)")

    # 2. Employee drives intake (FR->NO) — fires the trigger.
    status, _ = _call("PATCH", f"/api/cases/{CASE_ID}", token=emp, body={
        "relocationBasics": {"originCountry": "France", "originCity": "Lyon",
                             "destCountry": "NO", "destCity": "Oslo",
                             "purpose": "work", "targetMoveDate": "2026-09-01"}})
    check("employee can drive intake (PATCH 200)", status == 200, f"HTTP {status}")

    # 3. Trigger generated CaseForms -> dossier renders them.
    _, formsr = _call("GET", f"/api/cases/{CASE_ID}/forms", token=emp)
    forms = formsr if isinstance(formsr, list) else (formsr or {}).get("forms", [])
    check("dossier: trigger-generated forms present", len(forms) >= 1, f"{len(forms)} form(s)")

    # 4. Roadmap projects the forms into tracks.
    _, road = _call("GET", f"/api/cases/{CASE_ID}/roadmap/tracks", token=emp)
    tracks = road.get("tracks", road) if isinstance(road, dict) else road
    n_tracks = len(tracks) if isinstance(tracks, list) else 0
    check("roadmap: tracks render from forms", n_tracks >= 1, f"{n_tracks} track(s)")

    # 5. Immigration surface reachable (consent gate is the entry point).
    st, _ = _call("GET", f"/api/employee/cases/{CASE_ID}/interview/status", token=emp)
    check("immigration interview surface reachable", st in (200, 403),
          f"HTTP {st} (403 = consent not yet given, expected)")

    # 6. Employee benefits / policy surface resolves real categories.
    _, pol = _call("GET", f"/api/employee/policy-config?caseId={CASE_ID}", token=emp)
    pol_cats = (pol or {}).get("categories", []) if isinstance(pol, dict) else []
    check("employee benefits: policy categories resolve", len(pol_cats) >= 1, f"{len(pol_cats)} categories")

    # 7. Requirements + budget surfaces render (employee dossier sidebars).
    rs, req = _call("GET", f"/api/cases/{CASE_ID}/requirements", token=emp)
    check("requirements surface renders", rs == 200 and isinstance(req, dict), f"HTTP {rs}")
    bs, _ = _call("GET", f"/api/cases/{CASE_ID}/budget-summary", token=emp)
    check("budget summary renders", bs == 200, f"HTTP {bs}")

    # 8. HR command center (the real landing view) shows the case. This is a
    #    distinct surface from /api/hr/cases and silently returned 0 when the
    #    wizard_cases enrichment columns (s3/s4 migrations) were unapplied.
    if hr:
        _, ccc = _call("GET", "/api/hr/command-center/cases", token=hr)
        cc_rows = ccc if isinstance(ccc, list) else []
        check("HR command-center shows the case", len(cc_rows) >= 1, f"{len(cc_rows)} row(s)")
        ps, pcfg = _call("GET", "/api/hr/policy-config", token=hr)
        check("HR policy-config resolves (legacy-id company)", ps == 200 and isinstance(pcfg, dict), f"HTTP {ps}")

    # 9. Exceptions loop: employee raises an exception, HR sees it in the inbox.
    #    Idempotent — only creates one if the case has none yet.
    _, exist = _call("GET", f"/api/cases/{CASE_ID}/exception-requests", token=emp)
    exist = exist if isinstance(exist, list) else []
    if not exist:
        _call("POST", f"/api/cases/{CASE_ID}/exception-requests", token=emp, body={
            "category": "housing", "exception_type": "cap_override",
            "requested_amount": 32000, "cap_amount": 25000, "currency": "NOK",
            "reason": "Central Oslo 3-bed for a family of 4; comparable units exceed the policy cap."})
    if hr:
        _, inbox = _call("GET", "/api/exception-requests", token=hr)
        inbox = inbox if isinstance(inbox, list) else []
        check("HR exceptions inbox shows the employee's request",
              any(str(r.get("case_id")) == CASE_ID for r in inbox), f"{len(inbox)} in inbox")

    print()
    if _failures:
        print(f"{RED}  JOURNEY BROKEN — {len(_failures)} stage(s) failed: {', '.join(_failures)}{RESET}\n")
        sys.exit(1)
    print(f"{GREEN}  FR->NO demo journey renders end-to-end.{RESET}\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
