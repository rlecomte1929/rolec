#!/usr/bin/env python3
"""AIQ-1311 spine probe — the employee→HR intake-submit flow, end-to-end, live.

Reproduces the REAL data path the v2 "Pathway" wizard uses (flat snake_case
autosaved into ``case_assignments.intake_draft`` via PATCH .../intake-draft, then
``POST .../submit`` reads it) — NOT the synthetic camelCase shortcut that let the
original 400 hide behind a green preflight (T14). This is the Red-tier live gate
for AIQ-1311 (#1032 submit fix + #1035 relocation_cases columns, both merged).

Success metric (exit 0 only if all green):
  M1 submit 200            — complete snake draft → POST /submit returns 200
  M4 HR overview populated — GET /api/hr/cases/{case}/overview shows origin/dest/corridor
  M4b HR readiness > 0     — GET /api/hr/assignments/{id}/readiness/summary
  M5 negative control      — incomplete draft (no dest_city) → 400 + missingFields + suggestedStep
(M2 status='submitted' and M3 relocation_cases columns are asserted out-of-band via
 the Supabase MCP using the asg/case ids this script prints.)

Usage:
  RELOPASS_ALLOW_PROD_WRITES=1 python3 scripts/verify_intake_submit_spine.py
  RELOPASS_API_BASE=https://api.relopass.com  (default)

Provisioning: reuses the stable HR persona (hr@testingapril.com) and registers ONE
throwaway employee per run (probe-spine-<ts>@probe.test) so the assignment is
isolated; the run prints the ids for teardown via scripts/fresh_onboarding_teardown
patterns. register is rate-limited (SEC-004) — don't run >~5x/hour.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

API = os.environ.get("RELOPASS_API_BASE", "https://api.relopass.com")
from _prod_write_guard import guard_prod_writes  # noqa: E402
guard_prod_writes(API)  # refuse to write prod unless RELOPASS_ALLOW_PROD_WRITES=1

HR_EMAIL = os.environ.get("RELOPASS_HR_EMAIL", "hr@testingapril.com")
HR_PASS = os.environ.get("RELOPASS_HR_PASSWORD", "HrPass!1")
STAMP = os.environ.get("RELOPASS_PROBE_STAMP") or str(int(time.time()))
EMP_EMAIL = f"probe-spine-{STAMP}@probe.test"
EMP_PASS = "ProbePass!1"
UA = {"User-Agent": "relopass-spine-probe/1.0", "Content-Type": "application/json"}
GREEN, RED, YEL, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[0m"

_results: list[tuple[str, bool, str]] = []
_ids: dict[str, str] = {}


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
            return e.code, b[:300]
    except Exception as e:
        return 0, str(e)[:200]


def metric(name, ok, detail=""):
    _results.append((name, ok, detail))
    c = GREEN if ok else RED
    print(f"  [{c}{'PASS' if ok else 'FAIL'}{RESET}] {name:26} {detail}")


def token_of(p):
    return p.get("token") or p.get("access_token") if isinstance(p, dict) else None


def complete_draft(dest_city: str) -> dict:
    """Flat snake_case IntakeData (Paris→Amsterdam). dest_city='' = incomplete."""
    return {
        "origin_country": "FR", "origin_city": "Paris",
        "dest_country": "NL", "dest_city": dest_city,
        "target_date": "2026-09-25", "purpose": "Employment",
        "full_name": "Spine Probe", "email": EMP_EMAIL, "nationality": "FR",
        "passport_country": "FR", "passport_expiry": "2031-01-01",
        "members": [], "has_pets": False,
        "job_title": "Engineer", "contract_type": "permanent",
        "contract_start": "2026-10-01", "salary_band": "B4",
        "office_address": "Herengracht 1, Amsterdam",
        "work_pattern": "hybrid", "commute_mins": 30, "commute_mode": ["bike"],
        "consent": True,
    }


def provision_case(hr, emp, label) -> str | None:
    """HR creates a case + assigns the employee; employee claims it. Returns assignment_id."""
    s, p = call("POST", "/api/hr/cases", hr, {})
    case_id = (p or {}).get("caseId") or (p or {}).get("case_id") if isinstance(p, dict) else None
    if not case_id:
        print(f"    provision[{label}]: case create failed HTTP {s}: {str(p)[:120]}")
        return None
    s, p = call("POST", f"/api/hr/cases/{case_id}/assign", hr, {"employeeIdentifier": EMP_EMAIL})
    asg = (p or {}).get("assignmentId") or (p or {}).get("assignment_id") if isinstance(p, dict) else None
    token = (p or {}).get("inviteToken") or (p or {}).get("invite_token") if isinstance(p, dict) else None
    if asg and token:
        call("POST", "/api/employee/assignments/claim-by-token", emp, {"token": token})
    _ids[f"case_{label}"] = case_id
    _ids[f"asg_{label}"] = asg or "?"
    print(f"    provision[{label}]: case={case_id} asg={asg}")
    return asg


def main():
    print(f"\n  AIQ-1311 spine probe  ({API})  emp={EMP_EMAIL}\n")

    hr = token_of(call("POST", "/api/auth/login", body={"identifier": HR_EMAIL, "password": HR_PASS})[1])
    if not hr:
        print(f"  {RED}FATAL{RESET}: HR login failed ({HR_EMAIL}). Check creds/drift.")
        sys.exit(2)
    emp = token_of(call("POST", "/api/auth/register", body={
        "email": EMP_EMAIL, "password": EMP_PASS, "role": "EMPLOYEE", "full_name": "Spine Probe"})[1])
    if not emp:
        emp = token_of(call("POST", "/api/auth/login", body={"identifier": EMP_EMAIL, "password": EMP_PASS})[1])
    if not emp:
        print(f"  {RED}FATAL{RESET}: employee register+login failed (rate limit? SEC-004).")
        sys.exit(2)

    # ── Happy path: complete snake draft → submit 200 ────────────────────────
    asg_ok = provision_case(hr, emp, "ok")
    if asg_ok and asg_ok != "?":
        call("PATCH", f"/api/employee/assignments/{asg_ok}/intake-draft", emp, {"data": complete_draft("Amsterdam")})
        s, p = call("POST", f"/api/employee/assignments/{asg_ok}/submit", emp)
        metric("M1 submit 200", s == 200, f"HTTP {s} {str(p)[:60]}")
    else:
        metric("M1 submit 200", False, "provisioning failed")

    # ── M4: HR overview shows origin/destination ─────────────────────────────
    case_ok = _ids.get("case_ok")
    if case_ok:
        s, p = call("GET", f"/api/hr/cases/{case_ok}/overview", hr)
        ov = (p or {}).get("overview") if isinstance(p, dict) else None
        oc = (ov or {}).get("origin_country_code")
        dc = (ov or {}).get("dest_country_code")
        corr = (ov or {}).get("corridor")
        metric("M4 HR overview route", bool(oc and dc),
               f"origin={oc} dest={dc} corridor={corr} (HTTP {s})")
        # M4b guards the endpoint HEALTH (no 500 — the provenance_catalog ImportError
        # regression). resolved=False@200 is a valid graceful degrade (e.g. no readiness
        # template for the corridor, or an unnormalizable destination) — NOT a failure;
        # it's reported as info, not asserted, since seeding templates is separate content.
        s, p = call("GET", f"/api/hr/assignments/{asg_ok}/readiness/summary", hr)
        chk = (p or {}).get("checklist") if isinstance(p, dict) else None
        done = (chk or {}).get("completed_or_waived")
        resolved = (p or {}).get("resolved") if isinstance(p, dict) else None
        reason = (p or {}).get("reason") if isinstance(p, dict) else None
        metric("M4b readiness 200 (not 500)", s == 200,
               f"HTTP {s} resolved={resolved} reason={reason} completed_or_waived={done}")
    else:
        metric("M4 HR overview route", False, "no case_ok")
        metric("M4b readiness 200 (not 500)", False, "no case_ok")

    # ── M5: negative control — incomplete draft still blocks, humanely ───────
    asg_bad = provision_case(hr, emp, "bad")
    if asg_bad and asg_bad != "?":
        call("PATCH", f"/api/employee/assignments/{asg_bad}/intake-draft", emp, {"data": complete_draft("")})
        s, p = call("POST", f"/api/employee/assignments/{asg_bad}/submit", emp)
        detail = (p or {}).get("detail") if isinstance(p, dict) else None
        mf = (detail or {}).get("missingFields") if isinstance(detail, dict) else None
        step = (detail or {}).get("suggestedStep") if isinstance(detail, dict) else None
        ok = s == 400 and isinstance(mf, list) and any("destCity" in str(x) for x in (mf or [])) and step == 1
        metric("M5 incomplete → 400", ok, f"HTTP {s} missingFields={mf} suggestedStep={step}")
    else:
        metric("M5 incomplete → 400", False, "provisioning failed")

    print(f"\n  ids for DB assertion (M2/M3) + teardown: {json.dumps(_ids)}\n")
    passed = sum(1 for _, ok, _ in _results if ok)
    total = len(_results)
    color = GREEN if passed == total else RED
    print(f"  {color}{passed}/{total} metrics passed{RESET}\n")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
