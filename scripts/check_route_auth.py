#!/usr/bin/env python3
"""
Route-auth CI check — AUDIT-B6
================================
Static AST analysis: walks FastAPI handler files, finds every GET endpoint,
and asserts each one either:
  a) has an auth dependency (Depends(get_current_user) or a sibling), OR
  b) is explicitly allowlisted in scripts/route_auth_allowlist.txt.

Exit 0  → all GET routes are guarded or allowlisted.
Exit 1  → at least one unguarded GET route found (CI fails).

Usage:
  python scripts/check_route_auth.py
  python scripts/check_route_auth.py --root .          # project root (default: cwd)
  python scripts/check_route_auth.py --verbose         # show every route checked

Why AST, not runtime import?
  Importing backend.main triggers DB init + migrations. AST analysis is safe in CI
  without a database, is instant, and catches the same structural patterns.
"""
from __future__ import annotations

import argparse
import ast
import os
import sys
from pathlib import Path
from typing import Iterator, List, NamedTuple, Optional, Set

# ---------------------------------------------------------------------------
# Auth dependency recognition — naming conventions
# ---------------------------------------------------------------------------
# Rather than maintaining an exact list (which breaks every time a new local
# auth dep is added to a router), we match by naming convention:
#   • anything starting with "require_" or "_require_"
#   • anything starting with "get_current_"
#   • anything starting with "get_supabase_" (Supabase-based auth guards)
# These prefixes are the project-wide convention for auth/authz Depends.
#
# If a dep name matches these prefixes it is treated as "route is protected".
# Add exact names below for deps that break the naming pattern.
_AUTH_DEP_PREFIXES = (
    "require_",
    "_require_",
    "get_current_",
    "get_supabase_",
    "verify_",          # secret/signature verifiers (verify_postmark_secret, ...)
)
# A dep name matching ANY of these suffixes is also treated as an auth dep.
# Example: mobility_authenticated_user, get_verified_user, verify_*_secret
_AUTH_DEP_SUFFIXES = (
    "_authenticated_user",
    "_current_user",
    "_verified_user",
    "_secret",          # webhook/automation shared-secret checks
    "_signature",       # HMAC/signature checks
)
_AUTH_DEP_EXACT: Set[str] = {
    "get_org_id_for_hr_user",  # org-scoping dep that implies auth
}

# ---------------------------------------------------------------------------
# Files scanned
# ---------------------------------------------------------------------------
_SCAN_PATHS = [
    "backend/app/routers",
    "backend/main.py",
    "backend/routes",         # legacy router directory if present
]

# HTTP methods whose endpoints are audited for an auth dependency.
# GET is the original AUDIT-B6 scope; the mutation methods were added by
# SEC-CASES-2-FU after a sweep found unauthenticated POST/PATCH endpoints
# (cases_write.patch_case/create_case) that the GET-only guard couldn't see.
_DEFAULT_METHODS = {"get", "post", "patch", "put", "delete"}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class RouteViolation(NamedTuple):
    file: str           # relative path from project root
    line: int
    func_name: str
    decorator_path: str  # e.g. "@router.get" or "@router.post"
    method: str          # http method, e.g. "get" / "post"


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def _route_method(node: ast.expr, methods: Set[str]) -> Optional[str]:
    """Return the HTTP method (lowercase) if this decorator is a route decorator
    for one of *methods* (e.g. @router.post(...)), else None."""
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    name = None
    if isinstance(func, ast.Attribute):   # @router.post(...) / @app.get(...)
        name = func.attr
    elif isinstance(func, ast.Name):      # @post(...) — defensive
        name = func.id
    return name if name in methods else None


def _decorator_repr(node: ast.expr, method: str) -> str:
    """Return a human-readable string for the decorator."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        obj = getattr(node.func.value, "id", "?")
        return f"@{obj}.{node.func.attr}"
    return f"@{method}"


def _dep_name_is_auth(dep_name: Optional[str]) -> bool:
    """True if *dep_name* matches one of the recognised auth callable patterns."""
    if not dep_name:
        return False
    return (
        any(dep_name.startswith(p) for p in _AUTH_DEP_PREFIXES)
        or any(dep_name.endswith(s) for s in _AUTH_DEP_SUFFIXES)
        or dep_name in _AUTH_DEP_EXACT
    )


def _depends_call_is_auth(call: ast.Call) -> bool:
    """
    Return True if *call* is ``Depends(<auth-dep>)``.

    Handles a bare callable (``Depends(get_current_user)``), an attribute
    (``Depends(mod.require_admin)``) and a curried factory
    (``Depends(require_role(UserRole.HR))``).
    """
    outer_func = call.func
    outer_name = (
        outer_func.id
        if isinstance(outer_func, ast.Name)
        else getattr(outer_func, "attr", "")
    )
    if outer_name != "Depends" or not call.args:
        return False
    dep_arg = call.args[0]
    if isinstance(dep_arg, ast.Name):
        return _dep_name_is_auth(dep_arg.id)
    if isinstance(dep_arg, ast.Attribute):
        return _dep_name_is_auth(dep_arg.attr)
    if isinstance(dep_arg, ast.Call):   # curried: Depends(require_role(...))
        inner = dep_arg.func
        inner_name = (
            inner.id if isinstance(inner, ast.Name) else getattr(inner, "attr", "")
        )
        return _dep_name_is_auth(inner_name)
    return False


def _has_auth_dep(func_def: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """
    Return True if any parameter of *func_def* has a default that calls
    Depends() with one of the recognised auth callables.

    Handles both forms:
      param: Type = Depends(get_current_user)
      param = Depends(require_admin)
    """
    all_defaults: List[ast.expr] = list(func_def.args.defaults) + list(
        func_def.args.kw_defaults
    )
    for default in all_defaults:
        if isinstance(default, ast.Call) and _depends_call_is_auth(default):
            return True
    return False


def _decorator_has_auth_dep(decorator: ast.expr) -> bool:
    """
    Return True if a route decorator declares an auth dependency at the
    decorator level, e.g.:

      @router.post("/x", dependencies=[Depends(verify_postmark_secret)])

    This is the webhook/secret-gated pattern: the endpoint has no auth in its
    own signature but is protected by a decorator-level dependency.
    """
    if not isinstance(decorator, ast.Call):
        return False
    for kw in decorator.keywords:
        if kw.arg != "dependencies":
            continue
        if isinstance(kw.value, (ast.List, ast.Tuple)):
            for elt in kw.value.elts:
                if isinstance(elt, ast.Call) and _depends_call_is_auth(elt):
                    return True
    return False


def _scan_file(filepath: Path, root: Path, methods: Set[str]) -> Iterator[RouteViolation]:
    """Yield a RouteViolation for every unguarded route handler in *filepath*
    whose HTTP method is in *methods*."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError) as exc:
        print(f"  [WARN] Could not parse {filepath.relative_to(root)}: {exc}")
        return

    rel = str(filepath.relative_to(root))

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            method = _route_method(decorator, methods)
            if method is None:
                continue
            if not _has_auth_dep(node) and not _decorator_has_auth_dep(decorator):
                yield RouteViolation(
                    file=rel,
                    line=node.lineno,
                    func_name=node.name,
                    decorator_path=_decorator_repr(decorator, method),
                    method=method,
                )
            break  # only process each function once


def _load_allowlist(allowlist_path: Path) -> Set[str]:
    """
    Load the allowlist file.  Each non-comment line has the format:

        relative/path/to/file.py:function_name   # optional comment

    Returns a set of "file:funcname" keys.
    """
    entries: Set[str] = set()
    if not allowlist_path.exists():
        return entries
    for raw_line in allowlist_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        entries.add(line)
    return entries


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Audit GET routes for missing auth deps.")
    parser.add_argument(
        "--root",
        default=".",
        help="Project root directory (default: current working directory)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print every route checked, not only failures",
    )
    parser.add_argument(
        "--methods",
        default=",".join(sorted(_DEFAULT_METHODS)),
        help="Comma-separated HTTP methods to audit (default: get,post,patch,put,delete).",
    )
    args = parser.parse_args()

    methods = {m.strip().lower() for m in args.methods.split(",") if m.strip()}
    root = Path(args.root).resolve()
    allowlist_path = root / "scripts" / "route_auth_allowlist.txt"
    allowlist = _load_allowlist(allowlist_path)

    # Collect all .py files to scan
    files_to_scan: List[Path] = []
    for scan_rel in _SCAN_PATHS:
        scan_path = root / scan_rel
        if not scan_path.exists():
            continue
        if scan_path.is_file():
            files_to_scan.append(scan_path)
        elif scan_path.is_dir():
            files_to_scan.extend(sorted(scan_path.rglob("*.py")))

    violations: List[RouteViolation] = []
    total_routes = 0

    for filepath in files_to_scan:
        for violation in _scan_file(filepath, root, methods):
            total_routes += 1
            key = f"{violation.file}:{violation.func_name}"
            if key in allowlist:
                if args.verbose:
                    print(f"  [SKIP]  {key}  (allowlisted)")
            else:
                violations.append(violation)
                if args.verbose:
                    print(f"  [FAIL]  {violation.method.upper():6} {violation.file}:{violation.line} {violation.func_name}")

    if violations:
        print(
            f"\n❌  {len(violations)} unguarded route(s) found "
            f"(add to scripts/route_auth_allowlist.txt if intentionally public):\n"
        )
        for v in sorted(violations, key=lambda x: (x.file, x.line)):
            print(f"  {v.method.upper():6} {v.file}:{v.line}  {v.func_name}  ({v.decorator_path})")
        print()
        return 1

    print(
        f"✅  Route-auth check passed — "
        f"{total_routes} route(s) scanned ({','.join(sorted(methods))}), all guarded or allowlisted."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
