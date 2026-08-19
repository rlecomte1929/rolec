#!/usr/bin/env python3
"""Serving/LLM isolation guard — no serving engine may reach an LLM.

    python scripts/check_serving_llm_isolation.py --root .

The serving engines answer "what does this person have to do to move?". They read a
human-approved catalog and apply deterministic rules. If one of them can reach a module
that calls a language model, then a compliance requirement can be INVENTED at request
time — not drafted, reviewed and approved, but produced mid-request and shown to a real
person as though it were the catalog. That is the failure this repo is built to prevent,
and no amount of "we only call it in the authoring path" survives a refactor.

The rule is therefore structural, not behavioural: the serving roots must not be able to
import an LLM-calling module, transitively, at all. Generation happens in the authoring
layer (`backend/imports/…`), lands in staging, and reaches customers only through the
existing human approval gate.

WHAT COUNTS AS AN LLM MODULE is discovered, not listed: any module under the scanned root
that imports a model-provider SDK. A hand-maintained denylist would go stale the day
someone adds a new provider, and would then report green for exactly the change it exists
to catch.

Exit 0 clean, 1 on a violation or when the scan is structurally unable to check anything.
"""
from __future__ import annotations

import argparse
import ast
import sys
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# The engines that answer a live request. Dotted module names, matched as prefixes so a
# package root covers its submodules.
SERVING_ROOTS = (
    "backend.app.services.requirements_builder",
    "backend.app.services.rules_engine",
    "backend.app.services.requirement_evaluation_service",
    "backend.app.services.immigration_requirement_service",
    "backend.app.services.hr_policy_resolver",
)

# Third-party model SDKs. A module importing one of these IS an LLM module.
LLM_SDKS = {"openai", "anthropic", "mistralai", "cohere", "google.generativeai", "litellm", "ollama"}

SCAN_DIRS = ("backend",)


def module_name(path: Path, root: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_relative(current: str, level: int, module: Optional[str], is_package: bool) -> Optional[str]:
    """Resolve `from ..x import y` against the importing module's package."""
    parts = current.split(".")
    base = parts if is_package else parts[:-1]
    if level > 1:
        base = base[: len(base) - (level - 1)]
    if not base:
        return None
    return ".".join(base + ([module] if module else []))


def parse_imports(path: Path, current: str, is_package: bool) -> Tuple[Set[str], Set[str]]:
    """(internal dotted targets, third-party top-level names) imported by this module."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return set(), set()

    internal: Set[str] = set()
    external: Set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                (internal if alias.name.split(".")[0] in SCAN_DIRS else external).add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                resolved = _resolve_relative(current, node.level, node.module, is_package)
                if resolved:
                    internal.add(resolved)
                    for alias in node.names:
                        internal.add(f"{resolved}.{alias.name}")
            elif node.module:
                if node.module.split(".")[0] in SCAN_DIRS:
                    internal.add(node.module)
                    for alias in node.names:
                        internal.add(f"{node.module}.{alias.name}")
                else:
                    external.add(node.module)
    return internal, external


def build_graph(root: Path) -> Tuple[Dict[str, Set[str]], Set[str], int]:
    """(edges, llm_modules, files_scanned)."""
    edges: Dict[str, Set[str]] = {}
    externals: Dict[str, Set[str]] = {}
    files = 0

    for scan_dir in SCAN_DIRS:
        base = root / scan_dir
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            parts = path.parts
            if "__pycache__" in parts or ".venv" in parts or "node_modules" in parts:
                continue
            name = module_name(path, root)
            if not name:
                continue
            files += 1
            internal, external = parse_imports(path, name, path.name == "__init__.py")
            edges.setdefault(name, set()).update(internal)
            externals.setdefault(name, set()).update(external)

    known = set(edges)
    for name, targets in edges.items():
        edges[name] = {t for t in targets if t in known}

    llm_modules = {
        name
        for name, ext in externals.items()
        if any(e == sdk or e.startswith(f"{sdk}.") for e in ext for sdk in LLM_SDKS)
    }
    return edges, llm_modules, files


def find_path(edges: Dict[str, Set[str]], start: str, targets: Set[str]) -> Optional[List[str]]:
    """Shortest import path from `start` to any target, for a diagnosable failure."""
    if start in targets:
        return [start]
    seen = {start}
    queue = deque([[start]])
    while queue:
        path = queue.popleft()
        for nxt in sorted(edges.get(path[-1], ())):
            if nxt in seen:
                continue
            seen.add(nxt)
            extended = path + [nxt]
            if nxt in targets:
                return extended
            queue.append(extended)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Assert no serving engine can reach an LLM-calling module.")
    parser.add_argument("--root", default=".", help="repository root (default: .)")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    edges, llm_modules, files = build_graph(root)

    # A guard that examined nothing must fail, not pass. check_route_auth.py learned this
    # the same way: "all clean" over an empty scan is indistinguishable from success and
    # is the most expensive kind of green.
    if files == 0:
        print("❌  Serving/LLM isolation FAILED — scanned 0 Python files.")
        print(f"    Looked under {root} for {', '.join(SCAN_DIRS)}/. Wrong --root, or the layout moved.")
        return 1

    present = [r for r in SERVING_ROOTS if r in edges]
    missing = [r for r in SERVING_ROOTS if r not in edges]
    if missing:
        print("❌  Serving/LLM isolation FAILED — serving roots not found in the import graph:\n")
        for name in missing:
            print(f"      {name}")
        print("\n    These were renamed or moved. Fix this list — an unresolvable root is")
        print("    silently unguarded, which is worse than a noisy failure.")
        return 1

    if not llm_modules:
        print("❌  Serving/LLM isolation FAILED — found 0 LLM-calling modules.")
        print(f"    Detection looks for imports of: {', '.join(sorted(LLM_SDKS))}.")
        print("    This repo does call models, so finding none means detection is broken")
        print("    and a green result here would mean nothing.")
        return 1

    violations: List[Tuple[str, List[str]]] = []
    for serving_root in present:
        path = find_path(edges, serving_root, llm_modules)
        if path:
            violations.append((serving_root, path))

    if violations:
        print("❌  Serving/LLM isolation FAILED — a serving engine can reach an LLM:\n")
        for serving_root, path in violations:
            print(f"      {serving_root}")
            for depth, step in enumerate(path[1:], start=1):
                marker = "  ⟵ LLM" if step in llm_modules else ""
                print(f"        {'  ' * depth}└─ {step}{marker}")
            print()
        print("    Generation belongs in the authoring layer (backend/imports/…), whose")
        print("    output lands in staging and reaches customers only through the human")
        print("    approval gate. Do not add an allowlist — move the import.")
        return 1

    print(
        f"✅  Serving/LLM isolation OK — {len(present)} serving roots, "
        f"{len(llm_modules)} LLM-calling modules, {files} files scanned; no path between them."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
