"""Tests for the serving/LLM isolation guard.

Two jobs, matching docs/specs/serving-llm-isolation.md:

  1. UNIT — the checker itself behaves: it resolves relative imports, sees through
     function-local imports, recognises gateways and SDKs, reports the SHORTEST chain,
     survives cycles, and distinguishes exit 1 (violation) from exit 2 (misconfigured).
  2. INTEGRATION — the REAL repo graph is clean. This is the second wire: the dedicated
     `serving-llm-isolation` CI job and this pytest run both fail the build on a
     violation, so accidentally disabling one lane does not silently drop the gate.

The unit tests build throwaway repos under tmp_path rather than mutating the real one,
so they need nothing but pytest + stdlib — no DB, no API keys, no network.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import check_serving_llm_isolation as guard  # noqa: E402

REPO_ROOT = SCRIPTS_DIR.parent


# ─── helpers ────────────────────────────────────────────────────────────────


def make_module(root: Path, dotted: str, body: str = "") -> Path:
    """Write `backend/...` module `dotted` with `body`, creating packages as needed."""
    parts = dotted.split(".")
    directory = root.joinpath(*parts[:-1])
    directory.mkdir(parents=True, exist_ok=True)
    # Every package on the path needs an __init__ so the graph can resolve it.
    for depth in range(1, len(parts)):
        init = root.joinpath(*parts[:depth], "__init__.py")
        if not init.exists():
            init.write_text("", encoding="utf-8")
    path = directory / f"{parts[-1]}.py"
    path.write_text(body, encoding="utf-8")
    return path


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """A miniature repo with ONE serving root, so unit tests are hermetic."""
    monkeypatch.setattr(guard, "SERVING_ROOTS", ("backend.app.services.serving_engine",))
    make_module(tmp_path, "backend.app.services.serving_engine", "x = 1\n")
    return tmp_path


# ─── unit: module naming ────────────────────────────────────────────────────


def test_module_name_for_maps_file_to_dotted_name(tmp_path):
    path = make_module(tmp_path, "backend.app.services.rules_engine")
    assert guard.module_name_for(path, tmp_path) == "backend.app.services.rules_engine"


def test_module_name_for_treats_init_as_its_package(tmp_path):
    make_module(tmp_path, "backend.app.services.anything")
    init = tmp_path / "backend" / "app" / "__init__.py"
    assert guard.module_name_for(init, tmp_path) == "backend.app"


def test_module_name_for_ignores_non_python_and_outside_root(tmp_path):
    other = tmp_path / "backend" / "notes.txt"
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_text("hi", encoding="utf-8")
    assert guard.module_name_for(other, tmp_path) is None
    assert guard.module_name_for(Path("/etc/hosts"), tmp_path) is None


# ─── unit: import extraction ────────────────────────────────────────────────


def test_relative_import_resolves_against_the_importing_module():
    tree = ast.parse("from .llm_client import complete_sync")
    found = guard.imports_of(tree, "backend.app.services.rules_engine")
    assert "backend.app.services.llm_client" in found


def test_two_dot_relative_import_climbs_one_package():
    tree = ast.parse("from ..models import Case")
    found = guard.imports_of(tree, "backend.app.services.rules_engine")
    assert "backend.app.models" in found


def test_from_dot_import_sibling_records_the_sibling_module():
    tree = ast.parse("from . import llm_client")
    found = guard.imports_of(tree, "backend.app.services.rules_engine")
    assert "backend.app.services.llm_client" in found


def test_function_local_import_is_still_recorded():
    """The whole point. A lazy import must not be a hiding place — this codebase uses
    function-local imports as a convention in backend/db/* and llm_client.py itself."""
    tree = ast.parse(
        "def resolve():\n"
        "    from .llm_client import complete_sync\n"
        "    return complete_sync\n"
    )
    found = guard.imports_of(tree, "backend.app.services.rules_engine")
    assert "backend.app.services.llm_client" in found


def test_relative_from_package_import_submodule_records_the_SUBMODULE():
    """Regression. `from ...pkg import submodule` used to record only the PACKAGE.

    The alias expansion was gated on `node.module is None`, so it fired for
    `from . import sibling` and not for `from ...imports.candidate_beam import passes`.
    A serving root could then import an LLM-calling module and the walk would reach only
    the package `__init__`, find no boundary, and exit 0.

    Found live: the candidate beam's `passes.py` calls a model, and importing it from
    `requirements_builder` in this spelling left the guard green. The absolute spelling of
    the identical import failed correctly, which is what made it hard to see — and
    relative imports are the dominant convention inside backend/app/services/, so the
    missed form was the likelier one.
    """
    found = guard.imports_of(
        ast.parse("from ...imports.candidate_beam import passes"),
        "backend.app.services.requirements_builder",
    )
    assert "backend.imports.candidate_beam.passes" in found


@pytest.mark.parametrize(
    "source",
    [
        "from ...imports.candidate_beam import passes",
        "from ...imports.candidate_beam.passes import run_pass",
        "from backend.imports.candidate_beam import passes",
        "import backend.imports.candidate_beam.passes",
    ],
)
def test_every_spelling_of_the_same_import_is_recorded(source):
    """Four ways to import one module. A guard that catches three of them is a guard you
    can defeat by rephrasing an import."""
    found = guard.imports_of(ast.parse(source), "backend.app.services.requirements_builder")
    assert "backend.imports.candidate_beam.passes" in found


def test_deeply_nested_import_is_recorded():
    """Inside a method, inside a try, inside a class — ast.walk sees all of it."""
    tree = ast.parse(
        "class A:\n"
        "    def go(self):\n"
        "        try:\n"
        "            import openai\n"
        "        except ImportError:\n"
        "            openai = None\n"
    )
    assert "openai" in guard.imports_of(tree, "backend.app.services.rules_engine")


# ─── unit: boundary detection ───────────────────────────────────────────────


def test_gateway_module_is_matched_on_its_final_segment():
    assert guard.is_gateway_module("backend.app.services.llm_client")
    assert guard.is_gateway_module("llm_client")
    assert not guard.is_gateway_module("backend.app.services.rules_engine")


def test_sdk_import_is_detected_including_submodules():
    assert guard.imports_llm_sdk({"openai"}) == "openai"
    assert guard.imports_llm_sdk({"openai.types.chat"}) == "openai"
    assert guard.imports_llm_sdk({"anthropic"}) == "anthropic"


def test_sdk_detection_does_not_match_a_similar_prefix():
    """`openairline` is not `openai` — a substring match would produce false failures,
    and a guard that cries wolf gets disabled."""
    assert guard.imports_llm_sdk({"openairline", "openai_helpers_local"}) is None


def test_boundary_reason_distinguishes_gateway_from_sdk_from_clean():
    assert guard.boundary_reason("backend.app.services.llm_client", {}) == "LLM gateway module"
    reason = guard.boundary_reason("backend.app.services.new_thing", {"backend.app.services.new_thing": {"anthropic"}})
    assert reason is not None and "anthropic" in reason
    assert guard.boundary_reason("backend.app.services.rules_engine", {"backend.app.services.rules_engine": {"json"}}) is None


# ─── unit: the search ───────────────────────────────────────────────────────


def test_clean_repo_passes(repo):
    code, report = guard.check(repo)
    assert code == 0, report
    assert "OK" in report and "1 serving roots" in report


def test_direct_llm_import_from_a_serving_root_fails(repo):
    make_module(repo, "backend.app.services.llm_client", "def complete_sync():\n    ...\n")
    make_module(
        repo,
        "backend.app.services.serving_engine",
        "def resolve():\n    from .llm_client import complete_sync\n",
    )
    code, report = guard.check(repo)
    assert code == 1, report
    assert "serving_engine" in report and "llm_client" in report
    assert "LLM gateway module" in report


def test_transitive_chain_is_reported_in_full(repo):
    make_module(repo, "backend.app.services.serving_engine", "from . import mid\n")
    make_module(repo, "backend.app.services.mid", "from . import deeper\n")
    make_module(repo, "backend.app.services.deeper", "from . import llm_client\n")
    make_module(repo, "backend.app.services.llm_client", "")
    code, report = guard.check(repo)
    assert code == 1, report
    for hop in ("serving_engine", "mid", "deeper", "llm_client"):
        assert hop in report, f"{hop} missing from the reported chain:\n{report}"


def test_an_unregistered_module_importing_an_sdk_is_caught(repo):
    """Rule 2: nobody has to remember to register a brand-new module that calls OpenAI."""
    make_module(repo, "backend.app.services.serving_engine", "from . import brand_new\n")
    make_module(repo, "backend.app.services.brand_new", "import openai\n")
    code, report = guard.check(repo)
    assert code == 1, report
    assert "brand_new" in report and "openai" in report


def test_shortest_chain_is_reported(repo):
    """BFS: report the shortest cut, not whichever path DFS wandered down first."""
    make_module(repo, "backend.app.services.serving_engine", "from . import short, long_a\n")
    make_module(repo, "backend.app.services.short", "from . import llm_client\n")
    make_module(repo, "backend.app.services.long_a", "from . import long_b\n")
    make_module(repo, "backend.app.services.long_b", "from . import llm_client\n")
    make_module(repo, "backend.app.services.llm_client", "")
    code, report = guard.check(repo)
    assert code == 1, report
    assert "long_b" not in report, f"expected the short path, got:\n{report}"


def test_import_cycle_does_not_hang(repo):
    make_module(repo, "backend.app.services.serving_engine", "from . import a\n")
    make_module(repo, "backend.app.services.a", "from . import b\n")
    make_module(repo, "backend.app.services.b", "from . import a\n")
    code, report = guard.check(repo)
    assert code == 0, report


def test_a_serving_root_that_is_itself_a_boundary_is_caught(repo, monkeypatch):
    """The most severe form: the root imports an SDK directly. Not an exemption."""
    monkeypatch.setattr(guard, "SERVING_ROOTS", ("backend.app.services.serving_engine",))
    make_module(repo, "backend.app.services.serving_engine", "import anthropic\n")
    code, report = guard.check(repo)
    assert code == 1, report
    assert "anthropic" in report


# ─── unit: configuration errors are failures, never silent passes ───────────


def test_missing_serving_root_is_exit_2_not_a_pass(repo, monkeypatch):
    monkeypatch.setattr(guard, "SERVING_ROOTS", ("backend.app.services.renamed_away",))
    code, report = guard.check(repo)
    assert code == 2, report
    assert "CONFIG ERROR" in report and "renamed_away" in report


def test_unparseable_serving_root_is_exit_2(repo):
    make_module(repo, "backend.app.services.serving_engine", "def broken(:\n")
    code, report = guard.check(repo)
    assert code == 2, report
    assert "CONFIG ERROR" in report


def test_missing_backend_directory_is_exit_2(tmp_path):
    code, report = guard.check(tmp_path)
    assert code == 2, report
    assert "CONFIG ERROR" in report


def test_unparseable_module_OUTSIDE_the_closure_warns_but_passes(repo):
    """A broken script elsewhere in the tree must not fail the build — but it must be
    reported, because an unparsed module has no recorded edges."""
    make_module(repo, "backend.scripts.broken_tool", "def broken(:\n")
    code, report = guard.check(repo)
    assert code == 0, report
    assert "WARN" in report and "broken_tool" in report


# ─── unit: the guard defends itself ─────────────────────────────────────────


def test_there_is_no_allowlist():
    """The invariant is 'never', not 'usually'. If someone adds an escape hatch, this
    test is the thing that should stop them."""
    source = (SCRIPTS_DIR / "check_serving_llm_isolation.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    banned = {n for n in names if any(k in n.upper() for k in ("ALLOWLIST", "WHITELIST", "EXEMPT", "IGNORE", "SKIP"))}
    assert not banned, f"an allowlist-shaped constant appeared in the guard: {banned}"


def test_the_five_serving_roots_are_registered():
    assert set(guard.SERVING_ROOTS) == {
        "backend.app.services.requirements_builder",
        "backend.app.services.rules_engine",
        "backend.app.services.requirement_evaluation_service",
        "backend.app.services.immigration_requirement_service",
        "backend.app.services.hr_policy_resolver",
    }


# ─── integration: the real repository ───────────────────────────────────────


def test_real_repo_serving_paths_are_llm_free():
    """The second wire. If this fails, the fix is to break the offending import — move
    the LLM use into the authoring layer — never to edit the guard's lists."""
    code, report = guard.check(REPO_ROOT)
    assert code == 0, f"serving/LLM isolation is broken:\n\n{report}"


def test_real_repo_serving_roots_all_exist_on_disk():
    """Guards the guard: a renamed root must fail loudly (exit 2), not pass vacuously."""
    for dotted in guard.SERVING_ROOTS:
        path = REPO_ROOT / Path(*dotted.split(".")).with_suffix(".py")
        assert path.is_file(), f"{dotted} is registered but missing at {path}"


def test_real_repo_closure_is_not_suspiciously_small():
    """A graph builder that silently resolved nothing would report a clean, empty walk.
    The audited baseline is ~50 modules; anything tiny means the walk broke."""
    edges, _raw, _errs = guard.build_graph(REPO_ROOT)
    closure = guard.reachable_from(guard.SERVING_ROOTS, edges)
    assert len(closure) >= 20, (
        f"serving closure collapsed to {len(closure)} modules — the import graph is "
        f"probably not resolving; a clean result here would be meaningless"
    )


# ─── reconciliation vs the validated reference ──────────────────────────────
#
# Gaps found by semantically diffing this implementation against the reference
# implementation (Part A of the reconciliation round). Each test below pins a gap that
# was REAL — the branch version failed it before the fix.


def test_groq_and_together_are_recognised_sdks():
    """Both were missing from the branch's SDK set; the reference listed them."""
    assert guard.imports_llm_sdk({"groq"}) == "groq"
    assert guard.imports_llm_sdk({"together"}) == "together"


def test_reference_sdk_set_is_fully_covered():
    """The branch set must be a SUPERSET of the reference's. Extras are fine —
    over-strict is the safe direction for a 'never' invariant."""
    reference = {
        "openai", "anthropic", "mistralai", "google.generativeai", "google.genai",
        "litellm", "cohere", "groq", "together", "replicate", "ollama",
        "langchain", "langchain_openai", "langchain_anthropic", "vertexai",
    }
    assert reference <= set(guard.LLM_SDK_MODULES), (
        f"missing from LLM_SDK_MODULES: {sorted(reference - set(guard.LLM_SDK_MODULES))}"
    )


def test_importing_a_submodule_also_edges_its_ancestor_packages(repo):
    """`import a.b.c` executes a/__init__.py and a/b/__init__.py. A gateway sitting in
    a package __init__ was invisible before this: the branch reported OK."""
    make_module(repo, "backend.app.services.serving_engine", "import backend.pkg.sub\n")
    make_module(repo, "backend.pkg.sub", "x = 1\n")
    (repo / "backend" / "pkg" / "__init__.py").write_text("import openai\n", encoding="utf-8")
    code, report = guard.check(repo)
    assert code == 1, f"a package __init__ importing openai must be reachable:\n{report}"
    assert "backend.pkg" in report


def test_ancestor_edges_do_not_fire_on_an_empty_init(repo):
    """The ancestor rule must not manufacture violations — only reachability."""
    make_module(repo, "backend.app.services.serving_engine", "import backend.pkg.sub\n")
    make_module(repo, "backend.pkg.sub", "x = 1\n")
    code, report = guard.check(repo)
    assert code == 0, report


# ─── Part B: a reachable unparseable module is fatal ────────────────────────


def test_unparseable_module_INSIDE_the_closure_is_exit_2(repo):
    """The blind spot both implementations shared. A module that fails to parse has no
    recorded edges, so an LLM import hiding behind the syntax error would be invisible —
    the guard would print OK while protecting nothing past that point."""
    make_module(repo, "backend.app.services.serving_engine", "from . import mid\n")
    make_module(repo, "backend.app.services.mid", "def broken(:\n")
    code, report = guard.check(repo)
    assert code == 2, f"expected CONFIG ERROR, got {code}:\n{report}"
    assert "CONFIG ERROR" in report
    assert "mid" in report


def test_reachable_parse_error_names_the_serving_root_that_reaches_it(repo):
    """The report has to say which root is compromised, or the fix is a guessing game."""
    make_module(repo, "backend.app.services.serving_engine", "from . import mid\n")
    make_module(repo, "backend.app.services.mid", "def broken(:\n")
    _code, report = guard.check(repo)
    assert "reached from serving root backend.app.services.serving_engine" in report


def test_the_real_repo_parse_error_is_still_outside_the_closure():
    """Pins the pre-existing backend/scripts/admin_reconcile_to_test_company.py as a WARN,
    not a failure. If it ever becomes reachable, this test flips and the build fails —
    which is the point."""
    code, report = guard.check(REPO_ROOT)
    assert code == 0, f"a parse error entered the serving closure:\n{report}"
