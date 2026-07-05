#!/usr/bin/env python3
"""AIQ-1414 — Mobility Coordinator PRODUCTION pilot (operator-run).

The Phase-5 gate-#2 pilot: drives a handful of real coordinator turns against a LIVE server
for one relocation case, then reads the server-side per-relocation cost that the turns wrote
(`feature_key='ai_coordinator'`). This is how you measure REAL cost on real infrastructure
before enabling the flag for everyone.

PREREQUISITES (this does NOT run in CI — it needs a deployed, key-equipped server):
  • The target server has `RELOPASS_AI_COORDINATOR_ENABLED` truthy AND a live ANTHROPIC key,
    and the `ai_coordinator_sessions` migration applied.
  • Env:
      RELOPASS_API_BASE            base URL (default https://api.relopass.com)
      RELOPASS_COORDINATOR_CASE_ID an HR-surface case id you (the token owner) can access
      RELOPASS_COORDINATOR_TOKEN   a ReloPass session token for HR-of-that-company or the
                                   assigned employee
      RELOPASS_ADMIN_TOKEN         (optional) admin token to read the unit-economics cost
      RELOPASS_COORDINATOR_TURNS   (optional) number of turns, default 5

Verdicts: PASS | FAIL | BLOCKED. Exits non-zero on any FAIL.

Usage:  python3 scripts/verify_coordinator_pilot.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("RELOPASS_API_BASE", "https://api.relopass.com")
from _prod_write_guard import guard_prod_writes  # noqa: E402

guard_prod_writes(API)  # refuse to accidentally write prod unless explicitly allowed

UA = {"User-Agent": "relopass-coordinator-pilot/1.0", "Content-Type": "application/json"}
GREEN, RED, GRY, RESET = "\033[92m", "\033[91m", "\033[90m", "\033[0m"

CASE_ID = os.environ.get("RELOPASS_COORDINATOR_CASE_ID", "")
TOKEN = os.environ.get("RELOPASS_COORDINATOR_TOKEN", "")
ADMIN_TOKEN = os.environ.get("RELOPASS_ADMIN_TOKEN", "")
N_TURNS = int(os.environ.get("RELOPASS_COORDINATOR_TURNS", "5"))

_results: list[tuple[str, str]] = []

_MESSAGES = [
    "What's the single next step on my relocation?",
    "Where does my visa stand right now?",
    "Has my housing been approved yet?",
    "What documents are still outstanding?",
    "Give me a one-line status of the whole move.",
]


def call(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    h = dict(UA)
    if token:
        h["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{API}{path}", data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        b = e.read().decode()
        try:
            return e.code, json.loads(b)
        except Exception:
            return e.code, b[:200]
    except Exception as e:
        return 0, str(e)[:200]


def record(node, verdict, detail=""):
    _results.append((node, verdict))
    c = {"PASS": GREEN, "FAIL": RED, "BLOCKED": GRY}.get(verdict, "")
    print(f"  [{c}{verdict:7}{RESET}] {node:34} {detail}")


def main() -> None:
    print(f"\nCoordinator pilot → {API}  case={CASE_ID or '(unset)'}  turns={N_TURNS}\n")
    if not CASE_ID or not TOKEN:
        record("PREREQS", "BLOCKED", "set RELOPASS_COORDINATOR_CASE_ID + RELOPASS_COORDINATOR_TOKEN")
        _summary()
        return

    lengths = []
    for i in range(N_TURNS):
        msg = _MESSAGES[i % len(_MESSAGES)]
        st, body = call("POST", f"/api/cases/{CASE_ID}/coordinator/respond", token=TOKEN, body={"message": msg})
        if st == 404:
            record(f"turn {i + 1}", "BLOCKED", "404 — flag OFF, or no access to this case")
            _summary()
            return
        if st != 200 or not isinstance(body, dict) or not body.get("answer"):
            record(f"turn {i + 1}", "FAIL", f"status={st} body={str(body)[:80]}")
            continue
        ans = body["answer"]
        lengths.append(len(ans))
        record(f"turn {i + 1}", "PASS", f"{len(ans)} chars · model={body.get('model')}")

    # Read the REAL per-relocation cost the turns wrote (feature_key='ai_coordinator').
    if ADMIN_TOKEN:
        st, body = call("GET", "/api/admin/ai-unit-economics?feature_key=ai_coordinator", token=ADMIN_TOKEN)
        if st == 200 and isinstance(body, dict):
            record("cost read", "PASS", f"unit-economics: {json.dumps(body)[:160]}")
        else:
            record("cost read", "BLOCKED", f"status={st} — confirm the admin unit-economics route/params")
    else:
        record("cost read", "BLOCKED", "set RELOPASS_ADMIN_TOKEN to auto-read cost; else read the admin "
                                       "unit-economics dashboard filtered to feature_key=ai_coordinator")
    _summary()


def _summary() -> None:
    passed = sum(1 for _, v in _results if v == "PASS")
    failed = [n for n, v in _results if v == "FAIL"]
    print(f"\n  {passed} PASS · {len(failed)} FAIL · "
          f"{sum(1 for _, v in _results if v == 'BLOCKED')} BLOCKED")
    print("  Next: read real per-relocation cost from the ai_unit_economics rollup "
          "(feature_key=ai_coordinator), compare to the ~$1.20 model, then human gate #2.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
