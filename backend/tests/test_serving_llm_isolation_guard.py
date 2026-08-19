"""The serving/LLM isolation guard must fail on the thing it exists to catch.

A guard nobody has watched go red is decoration. This suite drives
`scripts/check_serving_llm_isolation.py` over synthetic repo layouts and asserts both
directions: green on a clean tree, and RED on a direct import, a transitive one, and each
way the scan can be structurally unable to check anything.

The transitive case is the one that matters. Anyone can spot
`from .llm_client import complete` sitting in `rules_engine.py` during review. What gets
through review is `rules_engine` importing a helper that imports a summariser that imports
the client — at which point a live request can reach a model and no single diff looks
wrong.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARD = REPO_ROOT / "scripts" / "check_serving_llm_isolation.py"


def _load_guard():
    spec = importlib.util.spec_from_file_location("check_serving_llm_isolation", GUARD)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


guard = _load_guard()


def _run(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GUARD), "--root", str(root)],
        capture_output=True,
        text=True,
    )


def _write(root: Path, dotted: str, body: str) -> None:
    path = root.joinpath(*dotted.split(".")).with_suffix(".py")
    path.parent.mkdir(parents=True, exist_ok=True)
    for depth in range(1, len(dotted.split("."))):
        pkg = root.joinpath(*dotted.split(".")[:depth]) / "__init__.py"
        pkg.parent.mkdir(parents=True, exist_ok=True)
        pkg.touch(exist_ok=True)
    path.write_text(body)


def _clean_tree(root: Path) -> None:
    """A minimal but honest stand-in: all five serving roots, one real LLM module that
    nothing serving reaches, and an authoring module that legitimately does."""
    for name in (
        "requirements_builder",
        "rules_engine",
        "requirement_evaluation_service",
        "immigration_requirement_service",
        "hr_policy_resolver",
    ):
        _write(root, f"backend.app.services.{name}", "from . import catalog_reader\n")
    _write(root, "backend.app.services.catalog_reader", "VALUE = 1\n")
    _write(root, "backend.app.services.llm_client", "import openai\n")
    _write(root, "backend.imports.candidate_beam.passes", "from backend.app.services import llm_client\n")


# ---------------------------------------------------------------------------
# Green.
# ---------------------------------------------------------------------------


def test_the_real_repository_is_clean():
    """The gate as the PR must show it."""
    result = _run(REPO_ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Serving/LLM isolation OK" in result.stdout


def test_authoring_may_call_an_llm(tmp_path):
    """The beam calls a model by design. Only the SERVING roots are constrained — a guard
    that forbade LLM use outright would forbid the feature it ships alongside."""
    _clean_tree(tmp_path)
    result = _run(tmp_path)
    assert result.returncode == 0, result.stdout


# ---------------------------------------------------------------------------
# Red — the cases it exists for.
# ---------------------------------------------------------------------------


def test_direct_import_from_a_serving_root_fails(tmp_path):
    _clean_tree(tmp_path)
    _write(tmp_path, "backend.app.services.rules_engine", "from . import llm_client\n")
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "Serving/LLM isolation FAILED" in result.stdout
    assert "rules_engine" in result.stdout
    assert "llm_client" in result.stdout


def test_transitive_import_fails_and_names_the_whole_path(tmp_path):
    """Three hops, no single suspicious diff. The report must print the chain, or a
    failure is a puzzle rather than a fix."""
    _clean_tree(tmp_path)
    _write(tmp_path, "backend.app.services.rules_engine", "from . import explainer\n")
    _write(tmp_path, "backend.app.services.explainer", "from . import summariser\n")
    _write(tmp_path, "backend.app.services.summariser", "from . import llm_client\n")
    result = _run(tmp_path)
    assert result.returncode == 1
    for hop in ("rules_engine", "explainer", "summariser", "llm_client"):
        assert hop in result.stdout, f"{hop} missing from the reported path:\n{result.stdout}"


def test_reaching_the_beam_fails_once_the_beam_calls_a_model(tmp_path):
    """The specific regression this feature could introduce: a serving engine importing
    the authoring package for a type or a constant, and inheriting its LLM edge."""
    _clean_tree(tmp_path)
    _write(
        tmp_path,
        "backend.app.services.requirements_builder",
        "from backend.imports.candidate_beam import passes\n",
    )
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "candidate_beam" in result.stdout


@pytest.mark.parametrize("sdk", ["openai", "anthropic", "mistralai", "litellm"])
def test_any_provider_sdk_counts_not_just_the_one_in_use(tmp_path, sdk):
    """LLM modules are DISCOVERED, not listed. Swapping providers must not silently
    disarm the guard."""
    _clean_tree(tmp_path)
    _write(tmp_path, "backend.app.services.other_client", f"import {sdk}\n")
    _write(tmp_path, "backend.app.services.hr_policy_resolver", "from . import other_client\n")
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "hr_policy_resolver" in result.stdout


# ---------------------------------------------------------------------------
# Red — the guard refusing to report a meaningless green.
# ---------------------------------------------------------------------------


def test_empty_root_fails_rather_than_passing(tmp_path):
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "scanned 0 Python files" in result.stdout


def test_a_renamed_serving_root_fails_loudly(tmp_path):
    """An unresolvable root is silently unguarded — the most expensive kind of green."""
    _clean_tree(tmp_path)
    (tmp_path / "backend" / "app" / "services" / "rules_engine.py").unlink()
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "serving roots not found" in result.stdout


def test_no_detected_llm_modules_fails(tmp_path):
    """If detection finds no model calls in a repo that certainly makes them, detection
    is broken and 'clean' means nothing."""
    _clean_tree(tmp_path)
    (tmp_path / "backend" / "app" / "services" / "llm_client.py").write_text("VALUE = 1\n")
    (tmp_path / "backend" / "imports" / "candidate_beam" / "passes.py").write_text("VALUE = 1\n")
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "0 LLM-calling modules" in result.stdout


# ---------------------------------------------------------------------------
# Unit.
# ---------------------------------------------------------------------------


def test_relative_imports_resolve_through_package_levels(tmp_path):
    _write(tmp_path, "backend.app.services.thing", "from ..db import SessionLocal\nfrom . import sibling\n")
    internal, _ = guard.parse_imports(
        tmp_path / "backend" / "app" / "services" / "thing.py",
        "backend.app.services.thing",
        is_package=False,
    )
    assert "backend.app.db" in internal
    assert "backend.app.services.sibling" in internal
