"""autopilot_canary.py — post-deploy diagnostics-replay canary.

The validation half of the loop: after a fix is deployed, replay the failing requests that
were recorded in the reporting user's `client_context` and check the signal is resolved.
Read-only by construction — only **idempotent** (GET/HEAD) requests are replayed; a recorded
POST/PUT/DELETE is never re-fired against prod (no side effects). Authed endpoints hit
without a canary token are reported *inconclusive*, not falsely "resolved".

Additive in Phase 0 — exposed via `/api/crons/autopilot-canary` for manual/dry-run use and
unit tests; it is NOT yet wired into the auto-merge path (that is Phase 2, which will call
`notion_work_queue.set_validation_result` with the outcome).
"""
from __future__ import annotations

import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_IDEMPOTENT = {"GET", "HEAD"}
_DEFAULT_HEALTH = "/health"


@dataclass
class CanaryCheck:
    name: str
    ok: Optional[bool]   # True = resolved, False = still failing, None = inconclusive
    detail: str

    def as_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


@dataclass
class CanaryResult:
    passed: bool
    checks: List[CanaryCheck]

    @property
    def conclusive(self) -> bool:
        """True if at least one replayed request positively confirmed the fix."""
        return any(c.ok is True for c in self.checks[1:])

    def as_dict(self) -> Dict[str, Any]:
        return {"passed": self.passed, "conclusive": self.conclusive, "checks": [c.as_dict() for c in self.checks]}


def prod_base_url() -> str:
    return os.getenv("RELOPASS_PROD_API_URL", "https://api.relopass.com").rstrip("/")


def _http_status(method: str, url: str, *, auth_token: Optional[str] = None, timeout: int = 10) -> int:
    """HTTP status code for a request, or 0 on network error. Isolated so tests can
    monkeypatch it without real network I/O."""
    req = urllib.request.Request(url, method=method)
    if auth_token:
        req.add_header("Authorization", f"Bearer {auth_token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(getattr(resp, "status", 0) or 0)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except Exception:
        return 0


def failing_requests_from_context(client_context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pull the actionable (server-error) failing requests from a feedback client_context."""
    if not client_context:
        return []
    reqs = client_context.get("recentFailedRequests") or []
    # status 0 = network error (also actionable); >=500 = server error we can confirm fixed.
    return [r for r in reqs if isinstance(r, dict) and (int(r.get("status") or 0) == 0 or int(r.get("status") or 0) >= 500)]


def health_check(base_url: str, *, health_path: str = _DEFAULT_HEALTH, timeout: int = 10) -> CanaryCheck:
    status = _http_status("GET", f"{base_url}{health_path}", timeout=timeout)
    return CanaryCheck(f"health {health_path}", status == 200, f"HTTP {status}")


def replay_failing_request(
    base_url: str, fr: Dict[str, Any], *, auth_token: Optional[str] = None, timeout: int = 10
) -> CanaryCheck:
    method = (fr.get("method") or "GET").upper()
    path = fr.get("path") or "/"
    orig = int(fr.get("status") or 0)
    name = f"replay {method} {path} (was {orig or 'network-error'})"
    if method not in _IDEMPOTENT:
        return CanaryCheck(name, None, "skipped: non-idempotent method not replayed")
    status = _http_status(method, f"{base_url}{path}", auth_token=auth_token, timeout=timeout)
    if status == 0:
        return CanaryCheck(name, False, "network error / unreachable")
    if status >= 500:
        return CanaryCheck(name, False, f"still failing HTTP {status}")
    if status in (401, 403) and not auth_token:
        return CanaryCheck(name, None, f"inconclusive: auth wall HTTP {status} (no canary token)")
    return CanaryCheck(name, True, f"resolved HTTP {status}")


def run_canary(
    *,
    failing_requests: List[Dict[str, Any]],
    base_url: Optional[str] = None,
    health_path: str = _DEFAULT_HEALTH,
    auth_token: Optional[str] = None,
    timeout: int = 10,
) -> CanaryResult:
    """Health + diagnostics replay. `passed` iff health is 200 AND no replayed request is
    still failing (inconclusive checks are noted but do not fail the canary)."""
    base = (base_url or prod_base_url()).rstrip("/")
    checks: List[CanaryCheck] = [health_check(base, health_path=health_path, timeout=timeout)]
    for fr in failing_requests or []:
        checks.append(replay_failing_request(base, fr, auth_token=auth_token, timeout=timeout))
    health_ok = checks[0].ok is True
    any_failing = any(c.ok is False for c in checks[1:])
    return CanaryResult(passed=health_ok and not any_failing, checks=checks)
