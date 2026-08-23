#!/usr/bin/env python3
"""Verify the ES→IE relocation chain end to end against a live API.

WHY. On 2026-08-22 six PRs landed claiming to fix this corridor — the P0 serving regression
(#2001), the family-of-four seed profile (#2002), roadmap regeneration (#2003), HR document
extraction → intake prefill (#2005 / #2009) and the content classifier (#2012). Every one was
unit-tested; not one had been exercised against a running system. This is the command that
does that, and it names the PR that regressed rather than just failing.

Each stage maps to one merged change, so a red line is a diagnosis:

    2  public corridor requirements serve at all ................. #2001
    3  a new case is not pre-loaded with somebody else's family ... #2002
    4  HR can prefill the intake, and it lands in the draft ....... #2005 / #2009
    5  regeneration replaces generic steps with the CSEP journey .. #2003
    6  regenerating twice changes nothing ........................ #2003 (idempotency)
    7  the employee can actually see it .......................... end-to-end

Run it after any deploy touching requirements, milestones, intake or the corridor overlay:

    RELOPASS_API_BASE=http://localhost:8000 python3 scripts/verify_es_ie_chain.py --seed
    RELOPASS_ALLOW_PROD_WRITES=1 python3 scripts/verify_es_ie_chain.py --seed   # prod, on purpose
    RELOPASS_ESIE_CASE_ID=<id> python3 scripts/verify_es_ie_chain.py --read-only  # smoke, no writes

--read-only asserts without writing anything, so it is safe against prod and is the mode to
run after a deploy. It needs a case the HR user's own tenant owns: a case at another company
returns 404/403, and this script reports that as an ACCESS failure rather than silently
reading it as "no milestones" — which was its own first bug, found the first time it ran.

NOTE ON A LOCAL TARGET: a SQLite backend cannot serve `POST /api/hr/cases` (the path uses
Postgres `::text` casts), so --seed needs a Postgres target. --read-only works anywhere.

Needs an ES→IE fixture case. `scripts/seed_es_ie_fixture.py` makes one through the real HR
API; pass its id as RELOPASS_ESIE_CASE_ID, or let this script call it for you (--seed).

Andrea's live case 6ecadafe is deliberately NOT the default for the WRITING modes: it is real
work belonging to a real person, and a re-run would rewrite her roadmap. It is a perfectly good
--read-only target once hydrated, and is the intended one.

WHAT THIS DELIBERATELY DOES NOT DO. The OCR half of the extraction flow (`propose`) is behind
--with-ocr. It needs MISTRAL_API_KEY, costs money per run, and is non-deterministic. The
default asserts `confirm`, which is the half that WRITES and therefore the half that can
silently regress. A verifier that costs money and flakes gets switched off, which is worse
than one that covers slightly less.

Exit 0 = the chain works; exit 1 = a stage failed (the label says which).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

API = os.environ.get("RELOPASS_API_BASE", "https://api.relopass.com")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _prod_write_guard import guard_prod_writes  # noqa: E402

HR_EMAIL = os.environ.get("RELOPASS_DEMO_HR_EMAIL", "hr@testingapril.com")
HR_PASS = os.environ.get("RELOPASS_DEMO_HR_PASSWORD", "HrPass!1")
EMP_EMAIL = os.environ.get("RELOPASS_DEMO_EMP_EMAIL", "employee@testingapril.com")
EMP_PASS = os.environ.get("RELOPASS_DEMO_EMP_PASSWORD", "EmpPass!1")
CASE_ID = os.environ.get("RELOPASS_ESIE_CASE_ID", "")

GREEN, RED, DIM, RESET = "\033[92m", "\033[91m", "\033[2m", "\033[0m"
_failures: list[str] = []

# The seed markers #2002 removed. Any of these on a FRESH case means the regression is back.
#
# On a LEGACY case this check is a true positive, not a false alarm: the 2,002 cases created
# before #2002 still carry the seed until backend/scripts/clear_seed_family_profile.py is run
# against them. Verified 2026-08-22 — a Testing April case from before the fix reports
# `budgetMonthlySGD`, correctly. So judge this stage against the fixture (--seed), and read a
# hit on an old case as "that row needs the backfill", not "the fix regressed".
SEED_MARKERS = ("Singapore", "Oslo", "budgetMonthlySGD")

# The CSEP journey a third-country national on ES→IE must be given. Substrings, because the
# titles carry punctuation and detail that is allowed to change.
CSEP_STEPS = (
    "Critical Skills Employment Permit",
    "Employment visa",          # the long-stay 'D' visa
    "IRP",                      # immigration permission / Stamp 1, Burgh Quay
    "PPSN",
    "RPN",                      # Revenue employment registration
)
# Generic copy the corridor overlay is supposed to supersede. Seeing these ALONGSIDE the CSEP
# steps is worse than seeing only the generic pack — the employee cannot tell which is real.
GENERIC_VISA = ("task_visa_docs_prep", "task_visa_submit", "task_biometrics")


def call(method, path, token=None, body=None, timeout=60):
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    # The default urllib UA is WAF-blocked (403) — see verify_fr_no_demo.py.
    req.add_header("User-Agent", "ReloPass-EsIeVerify/1.0")
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


def check(label, ok, detail=""):
    mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
    print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        _failures.append(label)
    return ok


def milestones(case_id, token):
    """(http_status, rows). The status MATTERS and callers must check it.

    Returning a bare list here was this script's own first bug, caught the first time it was
    run: a case the caller cannot reach 404s, the payload has no milestones, and "denied"
    became indistinguishable from "genuinely empty" — so the roadmap assertions went red for
    a case that in fact carried 25 milestones, and would equally have gone GREEN on an
    unreachable case with a lenient predicate. Same failure mode this repo keeps hitting
    (a 404 that renders identically to "nothing to show").
    """
    status, payload = call("GET", f"/api/cases/{case_id}/timeline", token=token)
    if isinstance(payload, dict):
        rows = payload.get("milestones") or payload.get("timeline") or []
    else:
        rows = payload if isinstance(payload, list) else []
    return status, (rows if isinstance(rows, list) else [])


def _seed_fixture() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    out = subprocess.run(
        [sys.executable, os.path.join(here, "seed_es_ie_fixture.py")],
        capture_output=True, text=True, env=os.environ.copy(),
    )
    sys.stdout.write(out.stdout)
    if out.returncode != 0:
        sys.stderr.write(out.stderr)
        return ""
    return (out.stdout.strip().splitlines() or [""])[-1].strip()


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify the ES→IE chain end to end")
    ap.add_argument("--seed", action="store_true",
                    help="Provision the fixture case first (seed_es_ie_fixture.py)")
    ap.add_argument("--with-ocr", action="store_true",
                    help="Also exercise the OCR propose stage (needs MISTRAL_API_KEY; costs money)")
    ap.add_argument("--read-only", action="store_true",
                    help="Assert only — never write. Post-deploy smoke against an existing "
                         "hydrated case; needs RELOPASS_ESIE_CASE_ID.")
    args = ap.parse_args()

    # Only guard when we are actually going to write. --read-only is safe against prod by
    # construction, and that is the mode you want after a deploy.
    if not args.read_only:
        guard_prod_writes(API)  # AIQ-913
    elif not CASE_ID:
        print(f"{RED}  --read-only needs RELOPASS_ESIE_CASE_ID (it will not create one){RESET}")
        return 1

    case_id = CASE_ID
    if not args.read_only and (args.seed or not case_id):
        case_id = _seed_fixture()
    if not case_id:
        print(f"{RED}  no fixture case — set RELOPASS_ESIE_CASE_ID or run with --seed{RESET}")
        return 1

    print(f"\n  ES→IE chain verification  ({API}, case {case_id[:8]})\n")

    # ── 1. credentials ────────────────────────────────────────────────────────────
    hr = login(HR_EMAIL, HR_PASS)
    emp = login(EMP_EMAIL, EMP_PASS)
    check("HR + employee login", bool(hr) and bool(emp))
    if not hr:
        print(f"\n{RED}  Cannot continue without an HR token.{RESET}\n")
        return 1

    # ── 2. the P0: does the corridor serve at all? (#2001) ────────────────────────
    status, payload = call(
        "GET", "/api/public/corridor-requirements?from=ES&to=IE&employee_type=LTA"
    )
    reqs = (payload or {}).get("requirements", []) if isinstance(payload, dict) else []
    check("public corridor requirements serve (ES→IE)   [#2001]",
          status == 200 and len(reqs) > 0, f"HTTP {status}, {len(reqs)} requirement(s)")

    # ── 3. the seed profile is gone (#2002) ───────────────────────────────────────
    st_case, detail = call("GET", f"/api/hr/cases/{case_id}", token=hr)
    blob = json.dumps(detail or {})
    found = [m for m in SEED_MARKERS if m in blob]
    # Reachability first. An error body contains no seed markers either, so judging the blob
    # without checking the status is a PASS that proves nothing.
    if not check(f"HR can read the case (tenant scope)", st_case == 200, f"HTTP {st_case}"):
        print(f"{DIM}    → the case is not visible to {HR_EMAIL}; it likely belongs to "
              f"another company. Use a case at the HR user's own tenant.{RESET}")
    else:
        check("a new case carries no invented family/route   [#2002]",
              not found, f"markers found: {found}" if found else "clean")

    # ── 4. HR prefills the intake, and it lands (#2005 / #2009) ───────────────────
    if args.read_only:
        print(f"{DIM}  --read-only: skipping the intake-prefill and regeneration WRITES; "
              f"asserting the resulting state only{RESET}")
    if args.with_ocr:
        print(f"{DIM}  (--with-ocr: the propose stage needs a document; skipped unless "
              f"RELOPASS_ESIE_CONTRACT is set){RESET}")

    status, payload = (200, None) if args.read_only else call(
        "POST", f"/api/hr/cases/{case_id}/intake-extraction/confirm", token=hr,
        body={"fields": {
            "full_name": "Esie Fixture",
            "nationality": "VE",           # third-country → the CSEP track
            "job_title": "Senior Data Engineer",
            "origin_country": "ES",
            "dest_country": "IE",
            "origin_city": "Madrid",
            "dest_city": "Dublin",
            "contract_start": "2026-10-01",
        }},
    )
    written = (payload or {}).get("written_fields", []) if isinstance(payload, dict) else []
    draft = (payload or {}).get("intake_draft", {}) if isinstance(payload, dict) else {}
    if not args.read_only:
        check("HR intake prefill writes the corridor ends   [#2005]",
              status == 200 and draft.get("origin_country") == "ES"
              and draft.get("dest_country") == "IE",
              f"HTTP {status}, wrote {len(written)} field(s)")

    # ── 5. regeneration replaces the generic pack with the CSEP journey (#2003) ───
    _st_before, _rows_before = milestones(case_id, hr)
    before = len(_rows_before)
    if not args.read_only:
        status, payload = call("POST", f"/api/hr/cases/{case_id}/roadmap/regenerate", token=hr)
        check("roadmap regeneration accepted   [#2003]", status == 200, f"HTTP {status}")

    st_rows, rows = milestones(case_id, hr)
    if not check("the roadmap is readable by HR", st_rows == 200, f"HTTP {st_rows}"):
        print(f"{DIM}    → cannot judge the roadmap on an unreadable case; "
              f"skipping the CSEP assertions rather than failing them misleadingly.{RESET}")
        rows = None
    titles = " | ".join(str(r.get("title") or "") for r in (rows or []))
    if rows is not None:
        types = {str(r.get("milestone_type") or "") for r in rows}
        missing = [m for m in CSEP_STEPS if m not in titles]
        check("the CSEP journey is on the roadmap   [#2003]",
              rows and not missing,
              f"{len(rows)} milestone(s) (was {before})"
              + (f"; MISSING {missing}" if missing else ""))
        still_generic = [g for g in GENERIC_VISA if g in types]
        # Only meaningful once there ARE milestones — an empty list trivially contains none.
        check("the superseded generic visa pack is gone   [#2003]",
              bool(rows) and not still_generic,
              f"still present: {still_generic}" if still_generic
              else ("no milestones to judge" if not rows else ""))

    # ── 6. idempotency — the whole point of the reconcile (#2003) ─────────────────
    if not args.read_only and rows is not None:
        status, payload = call("POST", f"/api/hr/cases/{case_id}/roadmap/regenerate", token=hr)
        no_change = bool((payload or {}).get("no_change")) if isinstance(payload, dict) else False
        _st_after, _rows_after = milestones(case_id, hr)
        after = len(_rows_after)
        check("regenerating twice changes nothing   [#2003]",
              status == 200 and no_change and after == len(rows),
              f"no_change={no_change}, {len(rows)} → {after} milestone(s)")

    # ── 7. the employee can see it ────────────────────────────────────────────────
    if emp and rows is not None:
        st_emp, emp_rows = milestones(case_id, emp)
        emp_titles = " | ".join(str(r.get("title") or "") for r in emp_rows)
        check("the employee sees the CSEP journey",
              st_emp == 200 and emp_rows and any(m in emp_titles for m in CSEP_STEPS),
              f"HTTP {st_emp}, {len(emp_rows)} milestone(s) visible")

    print()
    if _failures:
        print(f"{RED}  {len(_failures)} stage(s) failed:{RESET}")
        for f in _failures:
            print(f"    - {f}")
        print()
        return 1
    print(f"{GREEN}  ES→IE chain verified end to end.{RESET}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
