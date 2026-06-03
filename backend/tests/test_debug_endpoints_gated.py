"""
SEC-001: /debug/* endpoints must only register when ENABLE_DEBUG_ENDPOINTS=1.

Debug/diagnostic routes are live unauthenticated attack surface in production.
They are gated behind the `debug_route(...)` helper in backend/main.py, which
registers a route ONLY when ENABLE_DEBUG_ENDPOINTS=1. When the flag is unset
(the production default) the routes simply do not exist and return 404.

The two assertions:
  1. Default (no env var)        -> none of the 8 debug routes are registered.
  2. ENABLE_DEBUG_ENDPOINTS=1    -> all 8 debug routes are registered.

We inspect the FastAPI route table directly (no SQL, no DB queries). Because the
gating decision is made at module-import time, each mode is probed in its own
subprocess so the env var is read fresh and the shared in-process app object is
never mutated.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Repo root: backend/tests/this_file -> parents[2].
REPO_ROOT = Path(__file__).resolve().parents[2]

# Every debug route that SEC-001 gates. Paths are the FastAPI template paths
# (path params keep their `{...}` form). `/debug/kv` is POST-only and shares no
# path with the GET routes, so it appears once.
EXPECTED_DEBUG_PATHS = {
    "/debug/db",
    "/debug/kv",
    "/debug/kv/{key}",
    "/api/admin/debug/runtime-database",
    "/api/admin/debug/test-company-graph",
    "/api/debug/supabase",
    "/api/debug/cases/{case_id}/events",
    "/api/debug/assignment-check",
}

# Snippet run in a child process: import the real app and dump the set of
# registered route paths that contain "/debug".
_PROBE = (
    "import json;"
    "from backend.main import app;"
    "print('DEBUG_PATHS=' + json.dumps(sorted("
    "    p for r in app.router.routes"
    "    for p in [getattr(r, 'path', '')]"
    "    if '/debug' in p"
    ")))"
)


def _registered_debug_paths(enable: bool) -> set[str]:
    """Import backend.main in a fresh process and return its /debug route paths."""
    env = dict(os.environ)
    env["RELOPASS_DISABLE_RATE_LIMITS"] = "1"
    if enable:
        env["ENABLE_DEBUG_ENDPOINTS"] = "1"
    else:
        env.pop("ENABLE_DEBUG_ENDPOINTS", None)

    proc = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        pytest.fail(
            "Probing backend.main failed "
            f"(enable={enable}, rc={proc.returncode}).\n"
            f"STDERR:\n{proc.stderr[-2000:]}"
        )

    marker = "DEBUG_PATHS="
    line = next(
        (ln for ln in proc.stdout.splitlines() if ln.startswith(marker)),
        None,
    )
    assert line is not None, f"probe produced no marker line; stdout:\n{proc.stdout}"
    return set(json.loads(line[len(marker):]))


def test_debug_routes_absent_by_default() -> None:
    """With no ENABLE_DEBUG_ENDPOINTS env var, no debug route is registered."""
    paths = _registered_debug_paths(enable=False)
    assert paths == set(), f"expected zero debug routes, got: {sorted(paths)}"


def test_debug_routes_present_when_enabled() -> None:
    """With ENABLE_DEBUG_ENDPOINTS=1, all 8 debug routes are registered."""
    paths = _registered_debug_paths(enable=True)
    assert paths == EXPECTED_DEBUG_PATHS, (
        "debug route set mismatch.\n"
        f"  missing: {sorted(EXPECTED_DEBUG_PATHS - paths)}\n"
        f"  unexpected: {sorted(paths - EXPECTED_DEBUG_PATHS)}"
    )
