#!/usr/bin/env python3
"""Provision ONE ES→IE fixture case, through the real HR API flow.

WHY THIS EXISTS. Six PRs landed on 2026-08-22 claiming to fix the ES→IE journey, and there
was no ES→IE case reachable by a login that works. Measured that day: the demo tenant
"Testing April" (the only one whose HR *and* employee credentials both authenticate) carried
FR→DE / FR→JP / FR→NL / FR→SG / FR→ES / FR→US cases and **not one ES→IE**. So verifying the
corridor meant hand-building state every time, which is why it had not been verified at all.

Andrea's own case is NOT usable for this: it is real work belonging to a real person, and a
verification fixture must never be someone's live case — a re-run would rewrite her roadmap.

(An earlier draft of this file said her company had no HR user who could open the case. That
was wrong: access resolves through `users` + `hr_users`, not `profiles`, and company 46fc3db0
does have an HR user. What is missing there is only the `profiles` row, which affects display
lookups and not access. Corrected so nobody repeats the inference.)

THROUGH THE API, NOT THROUGH SQL. This drives POST /api/hr/cases → POST
/api/hr/cases/{id}/assign, the same two calls the HR UI makes. A fixture built by INSERT
proves the schema accepts rows; it does not prove the product can create a case, and it is
exactly how a seeded "working" fixture ends up asserting nothing.

IDEMPOTENT BY SEARCH, not by deterministic id: the case id is issued by the server
(uuid4 inside create_case), so this cannot pin one. Instead it looks for an existing fixture
by its marker job title before creating another, and prints the id it found or made. Re-run
it as often as you like.

    RELOPASS_API_BASE=http://localhost:8000 python3 scripts/seed_es_ie_fixture.py
    RELOPASS_ALLOW_PROD_WRITES=1 python3 scripts/seed_es_ie_fixture.py     # prod, on purpose

Prints the case id on the last line so the verifier can consume it:

    CASE_ID=$(python3 scripts/seed_es_ie_fixture.py | tail -1)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("RELOPASS_API_BASE", "https://api.relopass.com")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _prod_write_guard import guard_prod_writes  # noqa: E402

guard_prod_writes(API)  # AIQ-913: refuse to seed prod by accident

HR_EMAIL = os.environ.get("RELOPASS_DEMO_HR_EMAIL", "hr@testingapril.com")
HR_PASS = os.environ.get("RELOPASS_DEMO_HR_PASSWORD", "HrPass!1")
EMP_EMAIL = os.environ.get("RELOPASS_DEMO_EMP_EMAIL", "employee@testingapril.com")

# The marker that makes this fixture findable on a re-run. Deliberately specific enough that
# it cannot collide with a real case at the demo tenant.
FIXTURE_JOB_TITLE = "ES-IE Chain Fixture (automated)"
FIXTURE_FIRST = "Esie"
FIXTURE_LAST = "Fixture"

GREEN, RED, DIM, RESET = "\033[92m", "\033[91m", "\033[2m", "\033[0m"


def call(method, path, token=None, body=None, timeout=30):
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", "ReloPass-EsIeFixture/1.0")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "null")
        except Exception:
            return e.code, None
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def login(email, password):
    _, payload = call("POST", "/api/auth/login", body={"identifier": email, "password": password})
    return (payload or {}).get("token") if isinstance(payload, dict) else None


def find_existing(hr_token):
    """The fixture, if a previous run already made it. Matched on the employee name we set."""
    _, payload = call("GET", "/api/hr/cases", token=hr_token)
    cases = (payload or {}).get("cases", []) if isinstance(payload, dict) else []
    for case in cases:
        blob = json.dumps(case).lower()
        if FIXTURE_FIRST.lower() in blob and FIXTURE_LAST.lower() in blob:
            return str(case.get("id") or case.get("caseId") or "")
    return None


def main() -> int:
    print(f"{DIM}  target: {API}{RESET}")
    hr = login(HR_EMAIL, HR_PASS)
    if not hr:
        print(f"{RED}  cannot log in as {HR_EMAIL} — check RELOPASS_DEMO_HR_PASSWORD{RESET}")
        return 1

    existing = find_existing(hr)
    if existing:
        print(f"{GREEN}  fixture already present{RESET} — reusing case {existing}")
        print(existing)
        return 0

    status, payload = call("POST", "/api/hr/cases", token=hr)
    case_id = (payload or {}).get("caseId") if isinstance(payload, dict) else None
    if status != 200 or not case_id:
        print(f"{RED}  POST /api/hr/cases failed: HTTP {status} {payload}{RESET}")
        return 1
    print(f"  created case {case_id}")

    # Link the demo employee so the employee-facing stage of the verifier has a reader.
    status, payload = call(
        "POST", f"/api/hr/cases/{case_id}/assign", token=hr,
        body={
            "employeeIdentifier": EMP_EMAIL,
            "employeeFirstName": FIXTURE_FIRST,
            "employeeLastName": FIXTURE_LAST,
        },
    )
    assignment_id = (payload or {}).get("assignmentId") if isinstance(payload, dict) else None
    if status != 200 or not assignment_id:
        print(f"{RED}  assign failed: HTTP {status} {payload}{RESET}")
        print(f"{DIM}  (the case exists at {case_id} but has no assignment; "
              f"the intake-extraction endpoints need one){RESET}")
        return 1
    print(f"  assigned to {EMP_EMAIL} — assignment {assignment_id}")

    print(f"{GREEN}  fixture ready{RESET}")
    print(case_id)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
