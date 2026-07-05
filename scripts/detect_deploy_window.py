#!/usr/bin/env python3
"""
Detect whether an E2E Sentinel campaign run raced a backend deploy (Render rolling
restart mid-run), from the API runner's ``test_results.json``.

A test that failed only because the backend was mid-deploy is an environmental transient,
not a bug. The pre-run readiness gate can't see a deploy that rolls DURING the run, and by
the time the post-run ``/health`` re-probe runs the backend may have recovered — but the
recorded failure still carries the fingerprint. We look for a FAILED entry whose response is
an unambiguous INFRA signature:

  * a gateway status 502 / 503 / 504 (edge saw the backend as down/unreachable), or
  * status 0 / a network-level error string (fetch failed, ECONNRESET, timeout, …).

We deliberately do NOT treat 4xx or a plain 500 as infra — those can be real app bugs and
must still be filed. Read-only; the campaign's post-run health gate calls this and marks the
whole run degraded (scorer files nothing) on a hit.

Usage:  python3 scripts/detect_deploy_window.py [test_results.json]
Prints  ``DEPLOY_WINDOW:<test-id>`` and exits 0 on a hit; prints nothing otherwise.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

# Gateway (502/503/504) or a bare 0, flanked by non-digits so "404"/"500"/"3502ms" don't match.
_GATEWAY = re.compile(r"(?:^|[^0-9])(0|50[234])(?:[^0-9]|$)")
_NETWORK = re.compile(
    r"fetch failed|ECONNRE|socket hang up|EAI_AGAIN|ENOTFOUND|aborted|timed?\s?out|network error",
    re.IGNORECASE,
)


def detect(path: str = "test_results.json") -> Optional[str]:
    """Return the id of the first FAILED test with an infra signature, else None."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    rows = data if isinstance(data, list) else (data.get("results") if isinstance(data, dict) else [])
    for r in rows or []:
        if not isinstance(r, dict) or str(r.get("status", "")).upper() != "FAIL":
            continue
        actual = str(r.get("actual", ""))
        blob = f"{actual} {r.get('detail', '')}"
        if _GATEWAY.search(actual) or _NETWORK.search(blob):
            return str(r.get("id", "?"))
    return None


if __name__ == "__main__":
    hit = detect(sys.argv[1] if len(sys.argv) > 1 else "test_results.json")
    if hit:
        print(f"DEPLOY_WINDOW:{hit}")
