#!/usr/bin/env python3
"""
check_router_registrations.py — dual-layer router registration guard.

Enforces the CLAUDE.md rule: every router included in the modular app
(``backend/app/main.py``) MUST also be included in the prod entrypoint
(``backend/main.py``). Render boots ``uvicorn backend.main:app`` and does NOT
serve the modular app, so a router registered only in ``app/main.py`` returns
405 in production. This bit us repeatedly — AI-002, AIQ-567/568, and most
recently hr_coordination (PR #213), hr_case_detail (#181), hr_case_audit (#188).
See ``audit/dual-layer-audit-followup.md``.

Design: this is a **syntactic (AST) check**. It parses the two files and
compares the set of routers passed to ``*.include_router(...)`` in each. It does
NOT import or mount the apps, so it avoids the prefix-doubling false positives a
runtime mount-check produces (see ``audit/dual-layer-mount-check-2026-06-01.md``,
where ``router.prefix + route.path`` double-counted and falsely flagged 17
routers). Commented-out / deleted ``include_router`` lines simply aren't in the
AST, so a removed prod registration is naturally detected.

Identity matching: router identities are normalised across the two files by
resolving import aliases to their source module and stripping the ``app``
path segment, so ``.app.routers.hr_coordination.router`` (prod, aliased to
``hr_coordination_router``) and ``.routers.hr_coordination.router`` (modular)
compare equal.

Two checks run in sequence:

  1. **Modular-only check** (original): every router in ``app/main.py`` must
     also appear in ``backend/main.py``. A modular-only router 405s in prod.

  2. **Neither-registered check** (new, AIQ-guard-fix): every file under
     ``backend/app/routers/`` that defines an ``APIRouter`` with at least one
     route must be registered in *at least one* entrypoint. A router in neither
     entrypoint is invisible to the modular-only check yet still ships a live
     404 — exactly the ``provider_portal`` case (audit/admin/33-defect-sweep.md).

Exit 0 if all checks pass; exit 1 (with the failing list) otherwise.

A companion allowlist (``scripts/router_registration_allowlist.txt``) grandfathers
the routers that are modular-only on main *today* (21 as of 2026-06-01 — most are
SERVED_VIA_ALTERNATE, a few need triage; see the mount-check doc). Without it the
guard fails with 21 entries on current main, since the strict ``modular ⊆ prod``
invariant does not hold yet. With it, the guard is green on main and fails only on
NEW, un-grandfathered modular-only routers — the actual hr_coordination-style bug.
The list should DRAIN as the modular cutover progresses.

The same allowlist covers the neither-registered check: a file whose router var
identity (``routers.<stem>.<var>``) is listed there is grandfathered for BOTH
checks. This avoids a separate allowlist file for a category that should drain
along the same timeline.

Local test results (2026-06-01, with the seeded allowlist):
  * current main @ a19291d7 (post-#213):                      PASS — 21 allowlisted        [VERIFIED]
  * pre-#213 main @ 9647cec5 (parent of #213 merge):          FAIL — flags ONLY hr_coordination [VERIFIED]
  * current main, hr_case_detail include removed (simulated): FAIL — flags ONLY hr_case_detail  [VERIFIED]
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PROD_DEFAULT = REPO / "backend" / "main.py"
MODULAR_DEFAULT = REPO / "backend" / "app" / "main.py"
ROUTERS_DIR_DEFAULT = REPO / "backend" / "app" / "routers"
ALLOWLIST_DEFAULT = Path(__file__).resolve().parent / "router_registration_allowlist.txt"

_HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options"})


def _load_allowlist(path: Path) -> set[str]:
    """Grandfathered modular-only router identities (one per line, '#' comments)."""
    if not path.exists():
        return set()
    out: set[str] = set()
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            out.add(line)
    return out


def _norm(dotted: str) -> str:
    """Strip leading dots and the ``app`` segment so prod/modular paths align."""
    return ".".join(p for p in dotted.split(".") if p and p != "app")


def _import_map(tree: ast.AST) -> dict[str, str]:
    """local name -> source dotted path (e.g. hr_coordination_router -> .app.routers.hr_coordination)."""
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = "." * node.level + (node.module or "")
            for alias in node.names:
                out[alias.asname or alias.name] = base + "." + alias.name
    return out


def _registered(path: Path) -> dict[str, str]:
    """Map normalised-identity -> readable label for each *.include_router(arg) call."""
    tree = ast.parse(path.read_text())
    imap = _import_map(tree)
    found: dict[str, str] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "include_router"
            and node.args
        ):
            arg = node.args[0]
            if isinstance(arg, ast.Name):
                base, attr = arg.id, ""
            elif isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name):
                base, attr = arg.value.id, "." + arg.attr
            else:
                continue  # too dynamic to resolve statically — skip
            resolved = imap.get(base, base) + attr
            found[_norm(resolved)] = base + attr
    return found


def _router_names_and_routes(path: Path) -> dict[str, list[str]]:
    """Return {var_name: ["METHOD /path", ...]} for each active APIRouter in *path*.

    "Active" means the var has at least one route decorator. Files with no
    APIRouter assignment, or whose router vars have no route decorators, return
    an empty dict — they are not a live-404 risk.

    The identity for each var is ``routers.<stem>.<var>`` (i.e. the output of
    ``_norm(f".routers.{path.stem}.{var}")``), which aligns with the keys
    produced by ``_registered()`` for the standard import pattern
    ``from .routers import <stem>; app.include_router(<stem>.<var>)``.
    """
    tree = ast.parse(path.read_text())

    # First pass: collect variable names assigned to APIRouter(...)
    router_vars: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "APIRouter"
        ):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    router_vars.add(target.id)

    if not router_vars:
        return {}

    # Second pass: collect route decorators per var
    routes_by_var: dict[str, list[str]] = {v: [] for v in router_vars}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                if (
                    isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Attribute)
                    and isinstance(dec.func.value, ast.Name)
                    and dec.func.value.id in router_vars
                    and dec.func.attr in _HTTP_METHODS
                ):
                    var = dec.func.value.id
                    path_str = ""
                    if dec.args and isinstance(dec.args[0], ast.Constant):
                        path_str = dec.args[0].value
                    routes_by_var[var].append(f"{dec.func.attr.upper()} {path_str}")

    # Discard vars with no routes (stub / helper vars)
    return {v: routes for v, routes in routes_by_var.items() if routes}


def _neither_registered_routers(
    routers_dir: Path,
    prod: dict[str, str],
    modular: dict[str, str],
    allowed: set[str],
) -> list[tuple[str, list[str]]]:
    """Find router files whose active router vars appear in NEITHER entrypoint.

    A file is flagged when:
      - It defines at least one APIRouter var with routes (i.e. it is "active").
      - None of its router var identities (``routers.<stem>.<var>``) appear in
        either *prod* or *modular* (i.e. it is registered nowhere).
      - None of its identities are in *allowed*.

    Returns a list of ``(module_name, routes)`` tuples for each flagged file,
    where *module_name* is ``"routers.<stem>"`` and *routes* is a sorted list of
    ``"METHOD /path"`` strings across all unregistered vars in that file.
    """
    problems: list[tuple[str, list[str]]] = []

    for path in sorted(routers_dir.glob("*.py")):
        if path.stem == "__init__":
            continue

        vars_and_routes = _router_names_and_routes(path)
        if not vars_and_routes:
            continue  # no active routers — not a live-404 risk

        stem = path.stem
        all_identities = {f"routers.{stem}.{var}" for var in vars_and_routes}

        # Skip if ANY var is registered in either entrypoint
        if any(ident in prod or ident in modular for ident in all_identities):
            continue

        # Skip if ANY var is grandfathered in the allowlist
        if any(ident in allowed for ident in all_identities):
            continue

        # Collect all routes across all vars for the error report
        all_routes: list[str] = []
        for routes in vars_and_routes.values():
            all_routes.extend(routes)

        problems.append((f"routers.{stem}", sorted(all_routes)))

    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prod", type=Path, default=PROD_DEFAULT)
    ap.add_argument("--modular", type=Path, default=MODULAR_DEFAULT)
    ap.add_argument("--routers-dir", type=Path, default=ROUTERS_DIR_DEFAULT,
                    dest="routers_dir",
                    help="Directory of router modules to scan for neither-registered routers.")
    ap.add_argument("--allowlist", type=Path, default=ALLOWLIST_DEFAULT)
    args = ap.parse_args()

    prod = _registered(args.prod)
    modular = _registered(args.modular)
    allowed = _load_allowlist(args.allowlist)

    failed = False

    # ── Check 1: modular-only (original) ──────────────────────────────────────
    missing = sorted(k for k in modular if k not in prod and k not in allowed)
    if missing:
        print("FAIL — NEW routers registered in backend/app/main.py but MISSING from backend/main.py:")
        for k in missing:
            print(f"  - {modular[k]}   (identity: {k})")
        print(
            "\nRender serves backend.main:app, not the modular app, so a modular-only "
            "router 405s in prod. Fix by adding `app.include_router(<name>_router.router)` "
            "to backend/main.py (see audit/dual-layer-audit-followup.md). If the router is "
            "intentionally modular-only, add its identity to "
            f"{args.allowlist.name} with a justifying comment."
        )
        failed = True

    # ── Check 2: neither-registered (new) ─────────────────────────────────────
    neither = _neither_registered_routers(args.routers_dir, prod, modular, allowed)
    if neither:
        print(
            "FAIL — router modules under backend/app/routers/ define active routes but "
            "are registered in NEITHER backend/main.py NOR backend/app/main.py:"
        )
        for module_name, routes in neither:
            print(f"  - {module_name}")
            for r in routes[:6]:  # cap output; full list is in the file
                print(f"      {r}")
            if len(routes) > 6:
                print(f"      ... ({len(routes) - 6} more)")
        print(
            "\nA router in neither entrypoint ships a silent 404 — the modular-only "
            "check can't see it because it never enters either include_router() list. "
            "Fix: register in BOTH backend/main.py AND backend/app/main.py "
            "(see CLAUDE.md 'Routers must be registered in BOTH'). "
            "If the router is intentionally inactive (dead code / held PR), add its "
            f"identity (routers.<stem>.<var>) to {args.allowlist.name} with a comment."
        )
        failed = True

    if not failed:
        n_allow = len(allowed & set(modular))
        print(
            f"PASS — every modular-app router is registered in backend/main.py "
            f"or grandfathered ({n_allow} allowlisted, pending triage); "
            f"no neither-registered routers detected."
        )

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
