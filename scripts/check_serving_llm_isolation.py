#!/usr/bin/env python3
"""Serving/LLM isolation guard — the generation/serving split as a build-failing invariant.

ReloPass's trust story ("why not just use ChatGPT?") rests on one architectural fact: a
served requirement is produced only by the deterministic engine over verified, cited
catalog data. The serving path must NEVER call an LLM at request time. Transformers
belong in the authoring/drafting layer, where a human reviews their output BEFORE it
becomes served data.

Until this guard, that split was a convention held up by code review. This script makes
it a build failure.

HOW IT WORKS

Parses every ``backend/**/*.py`` with ``ast`` (pure stdlib — no third-party imports, so
the CI job needs nothing installed) and builds a module-level import graph. It collects
ALL import statements, including lazy function-local ones::

    def f():
        from .llm_client import complete_sync   # <- still recorded

That matters: function-local imports are this codebase's convention in ``backend/db/*``
and in ``llm_client.py`` itself, and a checker that only read top-level imports could be
defeated by moving one line inside a function. It then BFS-walks from each serving root
and reports the first path to an LLM boundary.

A module is an LLM boundary when EITHER:

  1. its name is in ``LLM_GATEWAY_MODULES`` — a known gateway, caught even if it
     switches from an SDK to raw HTTP; or
  2. it imports an LLM vendor SDK anywhere in the file (``LLM_SDK_MODULES``) — so a
     brand-new module calling OpenAI directly is caught without anyone remembering to
     register it.

EXIT CODES

  0  invariant holds
  1  violation — every offending path is printed with its exact import chain
  2  configuration error — a serving root no longer exists on disk, OR any module
     inside the serving closure failed to parse. An unparsed module contributes no
     edges, so anything it imports is invisible; a clean verdict past one would be
     meaningless. A parse error OUTSIDE the closure is a WARN and still exits 0.
     Deliberately a failure: the guard must never silently pass while protecting nothing.

THERE IS NO ALLOWLIST. The invariant is "never", not "usually". Fix a violation by
breaking the import — move the LLM use into the authoring layer and have the serving
engine read reviewed rows. Editing the lists below to make CI green is a
review-rejectable change.

See docs/specs/serving-llm-isolation.md.
"""
from __future__ import annotations

import argparse
import ast
import sys
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# The protected set. Changing these lists to make a build pass is the one edit
# this guard exists to prevent — see the module docstring.
# ─────────────────────────────────────────────────────────────────────────────

#: Deterministic requirement-serving engines. Anything whose output reaches a customer
#: as a requirement WITHOUT human review in between belongs here.
SERVING_ROOTS: Tuple[str, ...] = (
    # in-country relocation dossier (requirement_items, keyed destination × purpose)
    "backend.app.services.requirements_builder",
    # deterministic applicability rules (STA waivers, nationality gating,
    # anti-silence confirmations)
    "backend.app.services.rules_engine",
    # the "deterministic MVP evaluator (no AI)" over the mobility-case graph
    "backend.app.services.requirement_evaluation_service",
    # entry-visa checklist + risk flags, keyed corridor × visa_type
    "backend.app.services.immigration_requirement_service",
    # deterministic HR policy benefit resolution
    "backend.app.services.hr_policy_resolver",
    # Document Data Sheet read-model — composes requirement/template/value data into the
    # customer-facing sheet with no human review in between, so it must stay LLM-free.
    "backend.app.services.data_sheet_service",
)

#: Live PDF fill path. Not a requirement-serving engine, but it writes a GOVERNMENT PDF at request
#: time (generate_prefilled_pdf), so it must stay LLM-free too — the form-onboarding LLM mapper is
#: authoring-only and must never be import-reachable from here.
FILL_ROOTS: Tuple[str, ...] = (
    "backend.app.services.form_prefill_service",
)

#: Known LLM gateways, matched on the final module segment so a gateway is caught
#: wherever it lives. Listed explicitly so a gateway that drops its SDK for raw HTTP
#: still trips the guard.
LLM_GATEWAY_MODULES: Tuple[str, ...] = (
    "llm_client",
    "policy_assistant_llm_client",
    "llm_policy_extractor",
    "policy_extractor",
    "roadmap_generator",
    "rce_entity_resolution_ai",
    "embeddings",
    "policy_assistant_embedder",
    "mistral_ocr_client",
)

#: LLM vendor SDKs. A module importing any of these IS a boundary, registered or not.
LLM_SDK_MODULES: Tuple[str, ...] = (
    "openai",
    "anthropic",
    "mistralai",
    "litellm",
    "cohere",
    "groq",
    "together",
    "google.generativeai",
    "google.genai",
    "vertexai",
    "transformers",
    "sentence_transformers",
    "llama_index",
    "langchain",
    "langchain_openai",
    "langchain_anthropic",
    "ollama",
    "replicate",
    "huggingface_hub",
)

_BACKEND_PACKAGE = "backend"


# ─────────────────────────────────────────────────────────────────────────────
# Import-graph construction
# ─────────────────────────────────────────────────────────────────────────────


class ConfigError(RuntimeError):
    """A serving root is missing or unparseable — exit 2, never a silent pass."""


def _dotted_prefixes(dotted: str) -> List[str]:
    """`a.b.c` -> ['a', 'a.b', 'a.b.c'] — the module and every ancestor package."""
    parts = dotted.split(".")
    return [".".join(parts[: i + 1]) for i in range(len(parts))]


def module_name_for(path: Path, root: Path) -> Optional[str]:
    """Dotted module name for a file under ``root``, or None if it isn't one.

    ``backend/app/services/rules_engine.py`` -> ``backend.app.services.rules_engine``
    ``backend/app/__init__.py``              -> ``backend.app``
    """
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    if rel.suffix != ".py":
        return None
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][: -len(".py")]
    if not parts:
        return None
    return ".".join(parts)


def _resolve_relative(module: Optional[str], level: int, importer: str) -> Optional[str]:
    """Resolve a relative import to an absolute dotted name.

    ``level`` is ast's dot count. Inside ``backend.app.services.rules_engine``,
    ``from .llm_client import x`` (level 1) -> ``backend.app.services.llm_client``.
    A package's own ``__init__`` counts as its package, which is why the importer's
    trailing segment is dropped exactly ``level`` times.
    """
    base_parts = importer.split(".")
    # level 1 == the importer's own package, so drop the module segment first.
    drop = level
    if drop > len(base_parts):
        return None
    prefix = base_parts[: len(base_parts) - drop]
    if module:
        prefix = prefix + module.split(".")
    if not prefix:
        return None
    return ".".join(prefix)


def imports_of(tree: ast.AST, importer: str) -> Set[str]:
    """Every module imported by ``tree``, at ANY nesting depth.

    ``ast.walk`` rather than a top-level scan: a function-local import is exactly the
    hiding place this guard has to see into.
    """
    found: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                resolved = _resolve_relative(node.module, node.level, importer)
                if resolved:
                    found.add(resolved)
                    # Each imported name may itself be a submodule, so expand every
                    # alias — exactly as the absolute branch below does.
                    #
                    # This expansion used to be gated on `node.module is None`, i.e. only
                    # `from . import sibling`. That left the guard blind to
                    # `from ...imports.candidate_beam import passes`, which recorded the
                    # PACKAGE and never the submodule — so a serving root could import an
                    # LLM-calling module and the walk would reach only the package
                    # `__init__`, find nothing, and report OK. Caught when the candidate
                    # beam's `passes.py` (which calls a model) was reached from
                    # `requirements_builder` and the guard still exited 0.
                    #
                    # The absolute form was always caught, which is what made this hard to
                    # see: `from backend.imports.x import y` failed correctly while the
                    # relative spelling of the same import passed. Relative imports are the
                    # dominant convention inside backend/app/services/, so the missed form
                    # was the likelier one.
                    for alias in node.names:
                        found.add(f"{resolved}.{alias.name}")
            elif node.module:
                found.add(node.module)
                # `from backend.app import services` — the target may be a module.
                for alias in node.names:
                    found.add(f"{node.module}.{alias.name}")
    return found


def build_graph(root: Path) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]], List[str]]:
    """Parse every backend module.

    Returns (edges, raw_imports, parse_errors) where ``edges`` is restricted to
    in-repo backend modules (what BFS walks) and ``raw_imports`` keeps every import
    including third-party ones (what SDK detection reads).
    """
    backend_dir = root / _BACKEND_PACKAGE
    if not backend_dir.is_dir():
        raise ConfigError(f"no {_BACKEND_PACKAGE}/ directory under {root}")

    known: Dict[str, Path] = {}
    for path in sorted(backend_dir.rglob("*.py")):
        name = module_name_for(path, root)
        if name:
            known[name] = path

    edges: Dict[str, Set[str]] = {}
    raw_imports: Dict[str, Set[str]] = {}
    parse_errors: List[str] = []

    for name, path in known.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as exc:
            parse_errors.append(f"{name} ({path}): {exc}")
            edges[name] = set()
            raw_imports[name] = set()
            continue
        imported = imports_of(tree, name)
        raw_imports[name] = imported
        # Keep only edges to modules that exist in this repo — AND to every ancestor
        # package of each import, because importing `a.b.c` executes `a/__init__.py`
        # and `a/b/__init__.py` on the way. A package __init__ that reaches an LLM is
        # therefore reachable from anything importing any of its submodules; ignoring
        # ancestors would let a gateway hide one level up.
        resolved: Set[str] = set()
        for target in imported:
            for prefix in _dotted_prefixes(target):
                if prefix in known:
                    resolved.add(prefix)
        edges[name] = {m for m in resolved if m != name}

    return edges, raw_imports, parse_errors


# ─────────────────────────────────────────────────────────────────────────────
# Boundary detection
# ─────────────────────────────────────────────────────────────────────────────


def is_gateway_module(module: str) -> bool:
    """True when the module's own name is a registered LLM gateway."""
    return module.rsplit(".", 1)[-1] in LLM_GATEWAY_MODULES


def imports_llm_sdk(imported: Set[str]) -> Optional[str]:
    """The LLM SDK this module imports, if any.

    Matches the SDK name or any submodule of it, so ``openai.types`` counts and
    ``openairline`` does not.
    """
    for name in sorted(imported):
        for sdk in LLM_SDK_MODULES:
            if name == sdk or name.startswith(sdk + "."):
                return sdk
    return None


def boundary_reason(module: str, raw_imports: Dict[str, Set[str]]) -> Optional[str]:
    """Why ``module`` is an LLM boundary, or None."""
    if is_gateway_module(module):
        return "LLM gateway module"
    sdk = imports_llm_sdk(raw_imports.get(module, set()))
    if sdk:
        return f"imports LLM SDK {sdk!r}"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Search
# ─────────────────────────────────────────────────────────────────────────────


def find_violation(
    origin: str,
    edges: Dict[str, Set[str]],
    raw_imports: Dict[str, Set[str]],
) -> Optional[Tuple[List[str], str]]:
    """Shortest import chain from ``origin`` to an LLM boundary, or None.

    BFS, so the chain reported is the shortest one — the most actionable place to cut.
    The origin itself is checked too: a serving root that imports an SDK directly is
    the most severe form of the violation, not an exemption.
    """
    reason = boundary_reason(origin, raw_imports)
    if reason:
        return [origin], reason

    parent: Dict[str, Optional[str]] = {origin: None}
    queue = deque([origin])
    while queue:
        current = queue.popleft()
        for nxt in sorted(edges.get(current, ())):
            if nxt in parent:
                continue
            parent[nxt] = current
            reason = boundary_reason(nxt, raw_imports)
            if reason:
                chain = [nxt]
                cursor: Optional[str] = current
                while cursor is not None:
                    chain.append(cursor)
                    cursor = parent[cursor]
                chain.reverse()
                return chain, reason
            queue.append(nxt)
    return None


def reachable_from(origins: Sequence[str], edges: Dict[str, Set[str]]) -> Set[str]:
    """Transitive import closure of ``origins`` (inclusive)."""
    seen: Set[str] = set()
    queue = deque(origins)
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        queue.extend(edges.get(current, ()))
    return seen


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────


def check(root: Path) -> Tuple[int, str]:
    """Run the guard. Returns (exit_code, report)."""
    try:
        edges, raw_imports, parse_errors = build_graph(root)
    except ConfigError as exc:
        return 2, f"[serving-llm-isolation] CONFIG ERROR — {exc}"

    _all_roots = SERVING_ROOTS + FILL_ROOTS

    missing = [m for m in _all_roots if m not in edges]
    if missing:
        lines = [
            "[serving-llm-isolation] CONFIG ERROR — serving root(s) not found on disk:",
            "",
        ]
        lines += [f"    {m}" for m in missing]
        lines += [
            "",
            "  A serving engine was renamed or deleted without updating SERVING_ROOTS.",
            "  Re-register it — a guard that protects nothing must not pass silently.",
        ]
        return 2, "\n".join(lines)

    root_parse_errors = [e for e in parse_errors if e.split(" ", 1)[0] in _all_roots]
    if root_parse_errors:
        lines = ["[serving-llm-isolation] CONFIG ERROR — serving root(s) failed to parse:", ""]
        lines += [f"    {e}" for e in root_parse_errors]
        return 2, "\n".join(lines)

    violations: List[Tuple[str, List[str], str]] = []
    for origin in _all_roots:
        found = find_violation(origin, edges, raw_imports)
        if found:
            chain, reason = found
            violations.append((origin, chain, reason))

    if violations:
        lines = [
            f"[serving-llm-isolation] FAIL — {len(violations)} serving path(s) "
            f"can reach an LLM call:",
            "",
        ]
        for origin, chain, reason in violations:
            lines.append(f"  serving root {origin}")
            lines.append(f"       {chain[0]}")
            for step in chain[1:-1]:
                lines.append(f"    -> {step}")
            if len(chain) > 1:
                lines.append(f"    -> {chain[-1]}   [{reason}]")
            else:
                lines.append(f"       ^ this root itself is a boundary   [{reason}]")
            lines.append("")
        lines += [
            "  Fix by BREAKING THE IMPORT: move the LLM use into the authoring layer and",
            "  have the serving engine read human-reviewed rows. Do not edit SERVING_ROOTS,",
            "  LLM_GATEWAY_MODULES or LLM_SDK_MODULES to make this pass — there is no",
            "  allowlist, because the invariant is 'never', not 'usually'.",
            "  See docs/specs/serving-llm-isolation.md.",
        ]
        return 1, "\n".join(lines)

    closure = reachable_from(_all_roots, edges)

    # A module that failed to parse has NO recorded edges, so the graph beyond it is
    # invisible. Outside the serving closure that is merely untidy; INSIDE it, the
    # guard could print OK while an LLM import hides behind the syntax error. Fatal.
    # This applies to the fill root exactly as it does to serving roots — a parse
    # error reachable only from the fill path would otherwise hide an LLM import too.
    broken_by_module = {e.split(" ", 1)[0]: e for e in parse_errors}
    reachable_broken = sorted(set(broken_by_module) & closure)
    if reachable_broken:
        lines = [
            "[serving-llm-isolation] CONFIG ERROR — "
            f"{len(reachable_broken)} module(s) inside the serving closure failed to parse.",
            "",
            "  Their imports could not be read, so any LLM call beyond them would be",
            "  invisible to this guard. A clean result here would be meaningless.",
            "",
        ]
        for module in reachable_broken:
            reaching = sorted(
                root for root in _all_roots
                if module in reachable_from([root], edges)
            )
            lines.append(f"    {broken_by_module[module]}")
            for root in reaching:
                lines.append(f"      reached from serving root {root}")
            lines.append("")
        lines.append("  Fix the syntax error — do not remove the module from the graph.")
        return 2, "\n".join(lines)

    report = (
        f"[serving-llm-isolation] OK — {len(SERVING_ROOTS)} serving roots, "
        f"{len(closure)} reachable modules, no path to an LLM gateway or SDK."
    )
    for err in sorted(parse_errors):
        report = (
            f"[serving-llm-isolation] WARN — could not parse {err} "
            f"(outside the serving closure)\n" + report
        )
    return 0, report


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assert the deterministic serving path cannot reach an LLM call.",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="repository root containing backend/ (default: the current directory)",
    )
    args = parser.parse_args(argv)

    exit_code, report = check(Path(args.root))
    print(report)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
