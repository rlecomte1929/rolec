#!/usr/bin/env python3
"""
Demo-account health check (AIQ-875 / UIAUDIT-G1 deliverable #3).

Logs in as each demo persona against the live API and FAILS LOUDLY if any
account's password has drifted — so a broken demo account is caught in the e2e
preflight, not mid-way through a live sales demo (which is what happened to
admin@relopass.com).

Credentials come from the environment so no password is hardcoded in git:

    RELOPASS_API_BASE         (default https://api.relopass.com)
    DEMO_ADMIN_EMAIL / DEMO_ADMIN_PW
    DEMO_HR_EMAIL    / DEMO_HR_PW
    DEMO_EMPLOYEE_EMAIL / DEMO_EMPLOYEE_PW

The e2e-test skill sets these from its credentials table before calling this in
its preflight. A persona with no *_PW env var is reported SKIPPED (not failed),
but at least one persona must be configured or the check fails (so an empty env
can't masquerade as a healthy pass).

Exit codes:
  0 — every configured persona logged in (200 + token)
  1 — a configured persona failed to log in (drift), or nothing was configured
"""
import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = os.environ.get("RELOPASS_API_BASE", "https://api.relopass.com").rstrip("/")

PERSONAS = [
    ("admin", os.environ.get("DEMO_ADMIN_EMAIL", "admin@relopass.com"), os.environ.get("DEMO_ADMIN_PW")),
    ("hr", os.environ.get("DEMO_HR_EMAIL", "hr@relopass.com"), os.environ.get("DEMO_HR_PW")),
    ("employee", os.environ.get("DEMO_EMPLOYEE_EMAIL", "employee@relopass.com"), os.environ.get("DEMO_EMPLOYEE_PW")),
]


def _login(email: str, password: str) -> tuple[int, bool]:
    """POST /api/auth/login. Returns (http_status, has_token)."""
    body = json.dumps({"identifier": email, "password": password}).encode()
    req = urllib.request.Request(
        f"{API_BASE}/api/auth/login",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode() or "{}")
            return resp.status, bool(payload.get("token"))
    except urllib.error.HTTPError as exc:
        return exc.code, False
    except Exception:
        return 0, False


def main() -> int:
    print(f"[demo-health] checking demo logins against {API_BASE}")
    configured = 0
    failures = []
    for label, email, pw in PERSONAS:
        if not pw:
            print(f"[demo-health] SKIP   {label:<8} ({email}) — no {label.upper()} password env set")
            continue
        configured += 1
        status, has_token = _login(email, pw)
        if status == 200 and has_token:
            print(f"[demo-health] OK     {label:<8} ({email}) — 200 + token")
        else:
            print(f"[demo-health] FAIL   {label:<8} ({email}) — status={status} token={has_token}")
            failures.append(label)

    if configured == 0:
        print(
            "[demo-health] ERROR: no demo passwords configured — set at least one "
            "DEMO_*_PW env var (an all-skip run is not a healthy pass).",
            file=sys.stderr,
        )
        return 1
    if failures:
        print(
            f"[demo-health] DRIFT DETECTED — {len(failures)} persona(s) cannot log in: "
            f"{', '.join(failures)}. Reset via scripts/reset_demo_admin_password.py.",
            file=sys.stderr,
        )
        return 1
    print(f"[demo-health] all {configured} configured persona(s) healthy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
