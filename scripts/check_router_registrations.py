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

Exit 0 if every modular-app router is also registered in prod; exit 1 (with the
missing list) otherwise.

A companion allowlist (``scripts/router_registration_allowlist.txt``) grandfathers
the routers that are modular-only on main *today* (21 as of 2026-06-01 — most are
SERVED_VIA_ALTERNATE, a few need triage; see the mount-check doc). Without it the
guard fails with 21 entries on current main, since the strict ``modular ⊆ prod``
invariant does not hold yet. With it, the guard is green on main and fails only on
NEW, un-grandfathered modular-only routers — the actual hr_coordination-style bug.
The list should DRAIN as the modular cutover progresses.

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
ALLOWLIST_DEFAULT = Path(__file__).resolve().parent / "router_registration_allowlist.txt"


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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prod", type=Path, default=PROD_DEFAULT)
    ap.add_argument("--modular", type=Path, default=MODULAR_DEFAULT)
    ap.add_argument("--allowlist", type=Path, default=ALLOWLIST_DEFAULT)
    args = ap.parse_args()

    prod = _registered(args.prod)
    modular = _registered(args.modular)
    allowed = _load_allowlist(args.allowlist)
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
        return 1

    n_allow = len(allowed & set(modular))
    print(
        f"PASS — every modular-app router is registered in backend/main.py "
        f"or grandfathered ({n_allow} allowlisted, pending triage)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
