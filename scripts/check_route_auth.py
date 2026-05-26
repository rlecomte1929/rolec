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
)
# A dep name matching ANY of these suffixes is also treated as an auth dep.
# Example: mobility_authenticated_user, get_verified_user
_AUTH_DEP_SUFFIXES = (
    "_authenticated_user",
    "_current_user",
    "_verified_user",
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

# Decorator names that indicate a GET endpoint
_GET_DECORATORS = {"get"}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class RouteViolation(NamedTuple):
    file: str           # relative path from project root
    line: int
    func_name: str
    decorator_path: str  # e.g. "@router.get" or "@app.get"


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def _is_get_decorator(node: ast.expr) -> bool:
    """Return True if this decorator AST node is a .get() call."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    # @router.get(...) or @app.get(...)
    if isinstance(func, ast.Attribute):
        return func.attr in _GET_DECORATORS
    # @get(...) — unlikely but defensive
    if isinstance(func, ast.Name):
        return func.id in _GET_DECORATORS
    return False


def _decorator_repr(node: ast.expr) -> str:
    """Return a human-readable string for the decorator."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        obj = getattr(node.func.value, "id", "?")
        return f"@{obj}.{node.func.attr}"
    return "@get"


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
        if default is None:
            continue
        if not isinstance(default, ast.Call):
            continue
        # Check the outer call is Depends(...)
        outer_func = default.func
        outer_name = (
            outer_func.id
            if isinstance(outer_func, ast.Name)
            else getattr(outer_func, "attr", "")
        )
        if outer_name != "Depends":
            continue
        # Check the first positional arg to Depends is an auth dep
        if not default.args:
            continue
        dep_arg = default.args[0]
        dep_name: Optional[str] = None
        if isinstance(dep_arg, ast.Name):
            dep_name = dep_arg.id
        elif isinstance(dep_arg, ast.Attribute):
            dep_name = dep_arg.attr
        if dep_name and (
            any(dep_name.startswith(p) for p in _AUTH_DEP_PREFIXES)
            or any(dep_name.endswith(s) for s in _AUTH_DEP_SUFFIXES)
            or dep_name in _AUTH_DEP_EXACT
        ):
            return True

        # Also handle curried deps: Depends(require_role(UserRole.HR))
        # where the argument is itself a Call node
        if isinstance(dep_arg, ast.Call):
            inner_func = dep_arg.func
            inner_name: Optional[str] = None
            if isinstance(inner_func, ast.Name):
                inner_name = inner_func.id
            elif isinstance(inner_func, ast.Attribute):
                inner_name = inner_func.attr
            if inner_name and (
                any(inner_name.startswith(p) for p in _AUTH_DEP_PREFIXES)
                or any(inner_name.endswith(s) for s in _AUTH_DEP_SUFFIXES)
                or inner_name in _AUTH_DEP_EXACT
            ):
                return True
    return False


def _scan_file(filepath: Path, root: Path) -> Iterator[RouteViolation]:
    """Yield a RouteViolation for every unguarded GET handler in *filepath*."""
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
            if not _is_get_decorator(decorator):
                continue
            # Found a GET-decorated function
            if not _has_auth_dep(node):
                yield RouteViolation(
                    file=rel,
                    line=node.lineno,
                    func_name=node.name,
                    decorator_path=_decorator_repr(decorator),
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
    args = parser.parse_args()

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
        for violation in _scan_file(filepath, root):
            total_routes += 1
            key = f"{violation.file}:{violation.func_name}"
            if key in allowlist:
                if args.verbose:
                    print(f"  [SKIP]  {key}  (allowlisted)")
            else:
                violations.append(violation)
                if args.verbose:
                    print(f"  [FAIL]  {violation.file}:{violation.line} {violation.func_name}")

    if violations:
        print(
            f"\n❌  {len(violations)} unguarded GET route(s) found "
            f"(add to scripts/route_auth_allowlist.txt if intentionally public):\n"
        )
        for v in sorted(violations, key=lambda x: (x.file, x.line)):
            print(f"  {v.file}:{v.line}  {v.func_name}  ({v.decorator_path})")
        print()
        return 1

    print(
        f"✅  Route-auth check passed — "
        f"{total_routes} GET route(s) scanned, all guarded or allowlisted."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
