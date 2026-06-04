"""
Tests for the SEC-CASES-2 extension of scripts/check_route_auth.py — the route
auth guard now audits POST/PATCH/PUT/DELETE, not just GET.

Exercises the real _scan_file code path against synthetic router files: an
unguarded mutation is flagged; a Depends()-guarded one (standard or custom-named
dep) is not; the --methods filter restricts which verbs are audited.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "check_route_auth", _REPO_ROOT / "scripts" / "check_route_auth.py"
)
cra = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cra)

_ROUTER_SRC = '''
from fastapi import APIRouter, Depends
router = APIRouter()

@router.post("/open")
def unguarded_post(body: dict):
    return {}

@router.patch("/open/{x}")
def unguarded_patch(x: str):
    return {}

@router.post("/safe")
def guarded_post(body: dict, user=Depends(get_current_user)):
    return {}

@router.post("/admin")
def admin_post(body: dict, user=Depends(_require_admin)):
    return {}

@router.get("/read")
def unguarded_get():
    return {}
'''


class ScanMutationsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.f = self.root / "router.py"
        self.f.write_text(_ROUTER_SRC, encoding="utf-8")
        self.addCleanup(self._tmp.cleanup)

    def _scan(self, methods):
        return {v.func_name for v in cra._scan_file(self.f, self.root, methods)}

    def test_flags_unguarded_mutations_only(self):
        flagged = self._scan({"post", "patch", "put", "delete"})
        self.assertEqual(flagged, {"unguarded_post", "unguarded_patch"})

    def test_standard_and_custom_named_auth_deps_pass(self):
        flagged = self._scan({"post"})
        self.assertNotIn("guarded_post", flagged)   # Depends(get_current_user)
        self.assertNotIn("admin_post", flagged)     # Depends(_require_admin)

    def test_methods_filter_includes_get_when_requested(self):
        self.assertIn("unguarded_get", self._scan({"get"}))
        self.assertNotIn("unguarded_get", self._scan({"post"}))

    def test_route_method_helper(self):
        import ast
        post = ast.parse('@router.post("/x")\ndef f(): ...').body[0].decorator_list[0]
        get = ast.parse('@router.get("/x")\ndef f(): ...').body[0].decorator_list[0]
        methods = {"post", "patch"}
        self.assertEqual(cra._route_method(post, methods), "post")
        self.assertIsNone(cra._route_method(get, methods))


class GuardIsGreenOnRepoTests(unittest.TestCase):
    """The extended guard must pass on the current repo (every mutation is
    guarded or allowlisted) — a regression guard for the allowlist."""

    def test_repo_passes(self):
        rc = cra.main.__wrapped__ if hasattr(cra.main, "__wrapped__") else None
        # main() reads argv; invoke via the module with explicit args instead.
        argv = sys.argv
        try:
            sys.argv = ["check_route_auth.py", "--root", str(_REPO_ROOT)]
            self.assertEqual(cra.main(), 0)
        finally:
            sys.argv = argv


if __name__ == "__main__":
    unittest.main()
