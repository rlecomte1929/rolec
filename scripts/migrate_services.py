#!/usr/bin/env python3
"""
migrate_services.py — AUDIT-A9.3
==================================
Atomically consolidates backend/services/ into backend/app/services/.

The correct import transformation differs by file location.
This script applies path-aware rules so no rule fires on the output of another.

Transformation table:
  backend/app/routers/*.py, backend/app/recommendations/*.py
    from ...services.X  →  from ..services.X   (3-dot → 2-dot, module import)
    from ...services import X  →  from ..services import X  (3-dot → 2-dot, package import)

  backend/app/main.py
    from ..services.X   →  from .services.X    (2-dot → 1-dot)

  backend/app/services/*.py  (already-canonical files with cross-tree refs)
    from ...services.X  →  from .X             (3-dot → sibling)
    from ..services.X   →  from .X             (2-dot → sibling)

  backend/main.py
    from .services.X    →  from .app.services.X  (1-dot → 1-dot+app)

  backend/routes/*.py   (legacy compat routes, stay in backend/routes/)
    from ..services.X   →  from ..app.services.X  (module import)
    from ..services import X  →  from ..app.services import X  (package import)

  Everywhere (tests, scripts, crawler, imports, service docstrings):
    from backend.services.X  →  from backend.app.services.X  (module import)
    from backend.services import X  →  from backend.app.services import X  (package import)

  backend/services/*.py  (files being MOVED; fix parent-dir refs before copy)
    When backend/services/X.py moves to backend/app/services/X.py the package
    depth increases by one (backend.services → backend.app.services), so any
    import that resolved to backend/ via 2-dot now needs 3-dot to reach the same target.

    from ..database     →  from ...database
    from ..schemas_*    →  from ...schemas_*
    from .._time        →  from ..._time
    from ..core.*       →  from ...core.*
    from ..identity_*   →  from ...identity_*
    from ..relocation_* →  from ...relocation_*
    from ..app.X        →  from ..X  (drop spurious "app." — went backend.services→backend.app.X,
                                      but from backend.app.services ".." already lands at backend.app)

Usage:
  python scripts/migrate_services.py --dry-run   # show what would change
  python scripts/migrate_services.py --apply     # copy + rewrite
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parent.parent
SRC  = ROOT / "backend" / "services"
DST  = ROOT / "backend" / "app" / "services"


# ---------------------------------------------------------------------------
# Path classifiers
# ---------------------------------------------------------------------------

def _classify(path: Path) -> str:
    """Return a category key for the file."""
    rel = path.relative_to(ROOT)
    parts = rel.parts

    if parts == ("backend", "main.py"):
        return "backend_main"
    if parts == ("backend", "app", "main.py"):
        return "app_main"
    if len(parts) >= 3 and parts[:2] == ("backend", "app") and parts[2] in ("routers", "recommendations"):
        return "app_routers"
    if len(parts) >= 3 and parts[:3] == ("backend", "app", "services"):
        return "app_services"
    if len(parts) >= 3 and parts[:2] == ("backend", "routes"):
        return "backend_routes"
    if len(parts) >= 2 and parts[:2] == ("backend", "services"):
        return "backend_services"
    if len(parts) >= 2 and parts[0] == "backend":
        return "backend_other"   # tests, scripts, crawler, imports, etc.
    return "other"


# ---------------------------------------------------------------------------
# Per-category substitution rules
# ---------------------------------------------------------------------------
# Each entry: (compiled_pattern, replacement, description)

_ABSOLUTE = (
    re.compile(r'\bfrom backend\.services\.'),
    "from backend.app.services.",
    "absolute: backend.services.X → backend.app.services.X (module import)",
)

_ABSOLUTE_PKG = (
    re.compile(r'\bfrom backend\.services import\b'),
    "from backend.app.services import",
    "absolute: backend.services import X → backend.app.services import X (package import)",
)

RULES_BY_CATEGORY: dict[str, list[tuple[re.Pattern[str], str, str]]] = {
    # backend/app/routers/** and backend/app/recommendations/**
    # 3-dot relative: from ...services.X → from ..services.X
    # Also covers package-level: from ...services import X  (no trailing dot)
    "app_routers": [
        (re.compile(r'\bfrom \.\.\.services\.'), "from ..services.", "3-dot → 2-dot (module import)"),
        (re.compile(r'\bfrom \.\.\.services import\b'), "from ..services import", "3-dot → 2-dot (package import)"),
        _ABSOLUTE, _ABSOLUTE_PKG,
    ],

    # backend/app/main.py
    # 2-dot relative: from ..services.X → from .services.X
    "app_main": [
        (re.compile(r'\bfrom \.\.services\.'), "from .services.", "2-dot → 1-dot"),
        _ABSOLUTE, _ABSOLUTE_PKG,
    ],

    # backend/app/services/*.py (already in canonical location)
    # These files have 3-dot or 2-dot refs into the OLD services tree.
    # After the move the modules are siblings, so strip the ...(.)services. prefix.
    "app_services": [
        (re.compile(r'\bfrom \.\.\.services\.(\w)'), r"from .\1", "3-dot → sibling (app/services)"),
        (re.compile(r'\bfrom \.\.services\.(\w)'), r"from .\1", "2-dot → sibling (app/services)"),
        _ABSOLUTE, _ABSOLUTE_PKG,
    ],

    # backend/main.py
    # 1-dot: from .services.X → from .app.services.X
    "backend_main": [
        (re.compile(r'\bfrom \.services\.'), "from .app.services.", "1-dot → 1-dot+app (backend/main.py)"),
        _ABSOLUTE, _ABSOLUTE_PKG,
    ],

    # backend/routes/*.py (legacy; stay at backend.routes — parent is backend/)
    # 2-dot: from ..services.X → from ..app.services.X
    # Also covers package-level: from ..services import X
    "backend_routes": [
        (re.compile(r'\bfrom \.\.services\.'), "from ..app.services.", "2-dot → 2-dot+app module (backend/routes/)"),
        (re.compile(r'\bfrom \.\.services import\b'), "from ..app.services import", "2-dot → 2-dot+app package (backend/routes/)"),
        (re.compile(r'\bfrom \.\.database\b'), "from ..database", "2-dot database — NO CHANGE (routes stay in place)"),
        _ABSOLUTE, _ABSOLUTE_PKG,
    ],

    # backend/services/*.py — files being moved
    # Fix parent-dir refs BEFORE they're copied so the destination has corrected imports.
    #
    # When backend/services/X.py moves to backend/app/services/X.py the package depth
    # increases by one (backend.services → backend.app.services), so any import that
    # resolved to backend/ via 2-dot now needs 3-dot to reach the same target.
    #
    # Patterns that need an extra dot after the move:
    #   from ..database      → from ...database        (backend/database.py)
    #   from ..schemas_*     → from ...schemas_*       (backend/schemas_*.py)
    #   from .._time         → from ..._time           (backend/_time.py)
    #   from ..core.*        → from ...core.*          (backend/core/)
    #   from ..identity_*    → from ...identity_*      (backend/identity_*.py)
    #   from ..relocation_*  → from ...relocation_*    (backend/relocation_*.py)
    #
    # Patterns that were "from ..app.X" (resolving to backend.app.X via backend.services)
    # must drop the spurious "app." level after the move, because from backend.app.services
    # "..app." would resolve to backend.app.app — one level too deep:
    #   from ..app.X         → from ..X                (e.g. ..app.db → ..db, ..app.schemas → ..schemas)
    "backend_services": [
        (re.compile(r'\bfrom \.\.database\b'), "from ...database", "2-dot → 3-dot database"),
        (re.compile(r'\bfrom \.\.schemas_'), "from ...schemas_", "2-dot → 3-dot schemas_"),
        (re.compile(r'\bfrom \.\._time\b'), "from ..._time", "2-dot → 3-dot _time"),
        (re.compile(r'\bfrom \.\.core\.'), "from ...core.", "2-dot → 3-dot core.*"),
        (re.compile(r'\bfrom \.\.identity_'), "from ...identity_", "2-dot → 3-dot identity_*"),
        (re.compile(r'\bfrom \.\.relocation_'), "from ...relocation_", "2-dot → 3-dot relocation_*"),
        (re.compile(r'\bfrom \.\.app\.'), "from ..", "2-dot..app. → 2-dot (drop spurious app level)"),
        _ABSOLUTE, _ABSOLUTE_PKG,
    ],

    # tests, scripts, crawler, imports, anything else in backend/
    "backend_other": [
        _ABSOLUTE,
        _ABSOLUTE_PKG,
        (re.compile(r'\bimport backend\.services\.'), "import backend.app.services.", "bare import: backend.services.X → backend.app.services.X"),
    ],
}


# ---------------------------------------------------------------------------
# File scanning
# ---------------------------------------------------------------------------

def _py_files(root: Path) -> Iterator[Path]:
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        if "node_modules" in p.parts:
            continue
        yield p


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _rewrite_file(path: Path, dry_run: bool) -> list[str]:
    category = _classify(path)
    rules = RULES_BY_CATEGORY.get(category, [])
    if not rules:
        return []

    original = path.read_text(encoding="utf-8")
    text = original
    changes: list[str] = []

    for pattern, replacement, description in rules:
        # Skip the no-op database rule for routes (it's a guard, not a real sub)
        if "NO CHANGE" in description:
            continue
        new_text, count = pattern.subn(replacement, text)
        if count:
            changes.append(f"  [{count}x] {description}")
            text = new_text

    if text != original and not dry_run:
        path.write_text(text, encoding="utf-8")

    return changes


# ---------------------------------------------------------------------------
# Tree copy
# ---------------------------------------------------------------------------

def _copy_tree(dry_run: bool) -> None:
    if not SRC.exists():
        print(f"[ERROR] Source directory does not exist: {SRC}")
        sys.exit(1)
    count = sum(1 for _ in SRC.rglob("*.py"))
    if dry_run:
        print(f"\n[DRY-RUN] Would copy {count} .py files:")
        print(f"  {SRC.relative_to(ROOT)}")
        print(f"  → {DST.relative_to(ROOT)}")
    else:
        shutil.copytree(str(SRC), str(DST), dirs_exist_ok=True)
        print(f"[COPY] Copied {count} files → backend/app/services/")


# ---------------------------------------------------------------------------
# Rewrite pass
# ---------------------------------------------------------------------------

def _rewrite_all(dry_run: bool) -> None:
    total_files = 0
    total_subs = 0
    changed_files: list[tuple[Path, list[str]]] = []

    for pyfile in sorted(_py_files(ROOT / "backend")):
        changes = _rewrite_file(pyfile, dry_run=dry_run)
        total_files += 1
        if changes:
            n = sum(int(c.split("[")[1].split("x]")[0]) for c in changes)
            total_subs += n
            changed_files.append((pyfile, changes))

    verb = "Would change" if dry_run else "Changed"
    print(f"\n{verb} {len(changed_files)} file(s), {total_subs} substitution(s) "
          f"across {total_files} .py file(s) scanned.\n")

    for path, changes in changed_files:
        rel = path.relative_to(ROOT)
        print(f"  {rel}")
        for c in changes:
            print(c)


# ---------------------------------------------------------------------------
# Post-copy fix: dossier_notifications.py has a lazy 4-dot database import
# ---------------------------------------------------------------------------

def _fix_post_copy(dry_run: bool) -> None:
    """Fix any edge-case imports that need correction after the copy."""
    target = DST / "dossier_notifications.py"
    if not target.exists():
        return
    text = target.read_text(encoding="utf-8")
    new, n = re.subn(r'\bfrom \.\.\.\.database\b', "from ...database", text)
    if n:
        print(f"  [post-copy] dossier_notifications.py: {n}x 4-dot → 3-dot database")
        if not dry_run:
            target.write_text(new, encoding="utf-8")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Consolidate backend/services/ → backend/app/services/"
    )
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply",   action="store_true")
    args = parser.parse_args()
    dry_run = args.dry_run

    print(f"{'=== DRY RUN ===' if dry_run else '=== APPLYING ==='}")
    print(f"Source : {SRC.relative_to(ROOT)}")
    print(f"Dest   : {DST.relative_to(ROOT)}")

    # Step 1: rewrite files BEFORE copy (so the copy gets corrected source files)
    print("\n-- Step 1: Rewriting imports in place --")
    _rewrite_all(dry_run=dry_run)

    # Step 2: copy the (now-corrected) tree
    print("-- Step 2: Copying tree --")
    _copy_tree(dry_run=dry_run)

    # Step 3: post-copy edge-case fixes
    if not dry_run:
        print("-- Step 3: Post-copy edge-case fixes --")
        _fix_post_copy(dry_run=dry_run)

    if dry_run:
        print("\nDry run complete. Review above, then:")
        print("  python scripts/migrate_services.py --apply")
        print("  find backend -type d -name services")
        print("  grep -r 'from \\.\\.\\.services\\.' backend/app/  # expect 0")
        print("  python -m pytest -q backend/tests/")
        print("  python -c 'import backend.app.main'")
        print("  # If all pass: git rm -r backend/services/")
    else:
        print("\nDone. Validate now:")
        print("  find backend -type d -name services")
        print("  grep -r 'from \\.\\.\\.services\\.' backend/app/  # expect 0")
        print("  python -m pytest -q backend/tests/")
        print("  python -c 'import backend.app.main'")
        print("  # If all pass: git rm -r backend/services/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
