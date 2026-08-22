#!/usr/bin/env python3
"""Ask production a real question and check the answer.

WHY THIS EXISTS — an outage, 2026-08-22, 09:44–17:13 UTC (7h29m).

`GET /api/public/corridor-requirements` returned HTTP 500 for both flagship corridors
(ES→IE and FR→NO) for seven and a half hours. Measured afterwards, what was watching:

    keepalive.yml            32 green runs DURING the outage — it pings /health only,
                             and /health does not read the database
    e2e-campaign.yml         ran on the breaking SHA and went green; no spec requests
                             this endpoint
    test_public_corridor.py  12 tests on this route, every one monkeypatching
                             crud.list_requirements away, so not one emits a SELECT

No check anywhere in this repo issued a real, unmocked HTTP request to a business endpoint
on api.relopass.com and asserted a 200. The outage was found by accident.

WHAT THIS ASSERTS, AND WHY BOTH HALVES MATTER.

  status == 200      — the UndefinedColumn class of failure, i.e. what happened.
  len(requirements)  — a 200 carrying zero rows is this repo's other recurring silent
      > 0              failure: a filter that can never match, a nationality gate that
                       excludes everyone, a country missing from a lookup map. Green-on-
                       empty has shipped here more than once. Status alone is not enough.

Never an exact count. Corridor counts legitimately move as the catalog is curated (FRANCE
went 29 → 16 in a single dedupe), and a check that has to be edited after every content
change gets edited without being read.

COLD START IS NOT A BUG. The backend is on Render's free plan and spins down after ~15
minutes idle, costing ~7.7s on the first request. So /health is probed FIRST as a control:
if the service itself is down, this reports that rather than blaming the endpoint. Each
probe then retries, because one slow first response is the expected state, not a defect —
whereas an UndefinedColumn 500 is instant and fails all three attempts.

Exit codes:
  0 — every probe returned 200 with a non-empty payload
  1 — a probe failed every attempt (this is the alarm)
  2 — the control probe failed: the service is unreachable or unhealthy, which is a
      different problem and deliberately a different exit code

Usage:
  python scripts/smoke_public_endpoints.py
  python scripts/smoke_public_endpoints.py --base-url http://localhost:8000
  python scripts/smoke_public_endpoints.py --attempts 1 --json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_BASE_URL = "https://api.relopass.com"

#: (label, path, key that must be a non-empty list). Public + unauthenticated on purpose:
#: these are reachable with no credentials in CI, and they are the two that were down.
#: `[[reference_public_corridor_nationality_gate]]` — curl, not urllib: Cloudflare 403s
#: python-urllib's default user agent.
PROBES: List[Tuple[str, str, str]] = [
    (
        "ES->IE LTA",
        "/api/public/corridor-requirements?from=ES&to=IE&employee_type=LTA",
        "requirements",
    ),
    (
        "FR->NO LTA",
        "/api/public/corridor-requirements?from=FR&to=NO&employee_type=LTA",
        "requirements",
    ),
]

CONTROL_PATH = "/health"


def http_get(url: str, timeout: int = 90) -> Tuple[int, str]:
    """Return ``(status_code, body)``. curl, not urllib — Cloudflare rejects urllib's
    default user agent with a 403, which would read as an outage."""
    proc = subprocess.run(
        ["curl", "-sS", "-o", "-", "-w", "\n%{http_code}", "--max-time", str(timeout), url],
        capture_output=True,
        text=True,
        check=False,
    )
    out = proc.stdout or ""
    body, _, status = out.rpartition("\n")
    try:
        return int(status.strip()), body
    except ValueError:
        return 0, body


def check_payload(body: str, key: str) -> Optional[str]:
    """``None`` if the payload is a JSON object whose ``key`` is a non-empty list,
    otherwise the reason it is not. Pure, so the green-on-empty path is unit-testable
    without a network."""
    try:
        data: Any = json.loads(body)
    except (ValueError, TypeError):
        return f"response is not JSON (first 120 chars: {body[:120]!r})"
    if not isinstance(data, dict):
        return f"expected a JSON object, got {type(data).__name__}"
    if key not in data:
        return f"no '{key}' key in the response (keys: {sorted(data)})"
    value = data[key]
    if not isinstance(value, list):
        return f"'{key}' is {type(value).__name__}, expected a list"
    if not value:
        return f"'{key}' is EMPTY — 200 OK carrying nothing is still a broken endpoint"
    return None


def probe(
    base_url: str, path: str, key: str, attempts: int, delay: int
) -> Tuple[bool, str, int]:
    """Return ``(ok, detail, count)``. Retries absorb a Render cold start; a real 500
    fails every attempt."""
    last = "no attempt made"
    for attempt in range(1, attempts + 1):
        status, body = http_get(base_url.rstrip("/") + path)
        if status == 200:
            reason = check_payload(body, key)
            if reason is None:
                return True, f"HTTP 200, {len(json.loads(body)[key])} items", len(
                    json.loads(body)[key]
                )
            last = f"HTTP 200 but {reason}"
        elif status == 0:
            last = "no response (timeout or DNS failure)"
        else:
            last = f"HTTP {status}: {body[:200]}"
        if attempt < attempts:
            print(f"    attempt {attempt}/{attempts} — {last}; retrying in {delay}s")
            time.sleep(delay)
    return False, last, 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the public API for real.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--attempts",
        type=int,
        default=3,
        help="Attempts per probe before failing (default 3). Absorbs a cold start.",
    )
    parser.add_argument(
        "--delay", type=int, default=20, help="Seconds between attempts (default 20)."
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    print(f"[smoke] target {base}")

    # Control first: distinguish "the service is down" from "this endpoint is broken".
    status, _ = http_get(base + CONTROL_PATH)
    if status != 200:
        print(
            f"[smoke] CONTROL FAILED — {CONTROL_PATH} returned HTTP {status}. The service "
            "itself is unhealthy or unreachable; not attributing this to any endpoint.",
            file=sys.stderr,
        )
        return 2
    print(f"[smoke] control {CONTROL_PATH} → 200")

    results: Dict[str, Dict[str, Any]] = {}
    failures: List[str] = []
    for label, path, key in PROBES:
        print(f"[smoke] {label} {path}")
        ok, detail, count = probe(base, path, key, args.attempts, args.delay)
        results[label] = {"path": path, "ok": ok, "detail": detail, "count": count}
        print(f"    {'OK  ' if ok else 'FAIL'} {detail}")
        if not ok:
            failures.append(f"{label}: {detail}")

    if args.json:
        print(json.dumps(results, indent=2))

    if failures:
        print(
            f"\n[smoke] FAIL — {len(failures)} of {len(PROBES)} public endpoints are broken "
            f"after {args.attempts} attempts each:",
            file=sys.stderr,
        )
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        print(
            "\n  A 500 here is most often a column the ORM maps and production lacks — a "
            "merged-but-unapplied migration. `scripts/check_model_schema_drift.py` names it "
            "directly. Check the Render logs for the request id.",
            file=sys.stderr,
        )
        return 1

    print(f"\n[smoke] OK — {len(PROBES)} public endpoints served real content.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
