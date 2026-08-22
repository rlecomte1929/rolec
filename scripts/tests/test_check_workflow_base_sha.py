"""CI coverage for the stale-base guard.

Runs in the backend pytest lane (ci.yml collects scripts/tests). Loads the guard by file
path rather than as a package — `scripts/` has no `__init__.py`, so `from scripts.x import`
resolves locally and raises ModuleNotFoundError under CI's full-suite discovery. Same idiom
as test_gate_loader_sync.py.

The point of the planted-violation cases: a guard that has only ever passed proves nothing.
`check_migration_drift` shipped in an audit mode that printed warnings and exited 0 — it was
structurally incapable of failing, including for the collision it named as its reason to
exist. So these tests pin that it FAILS, not merely that it runs.
"""
import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _guard():
    return _load("check_workflow_base_sha", "scripts/check_workflow_base_sha.py")


def test_the_repo_is_clean_today():
    assert _guard().main() == 0, (
        "a workflow derives a diff range from github.event.pull_request.base.sha — that SHA "
        "is frozen at PR-open time, so the job will fail a PR for another PR's files"
    )


def test_it_fails_on_a_planted_env_binding(tmp_path, monkeypatch):
    """The exact shape #1971 shipped."""
    guard = _guard()
    wf = tmp_path / "workflows"
    wf.mkdir()
    (wf / "planted.yml").write_text(
        "jobs:\n"
        "  gate:\n"
        "    steps:\n"
        "      - env:\n"
        "          BASE_SHA: ${{ github.event.pull_request.base.sha }}\n"
        "        run: git diff --name-only \"$BASE_SHA...HEAD\"\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(guard, "WORKFLOWS", wf)
    assert guard.main() == 1


def test_it_fails_on_the_expression_used_inline_in_run(tmp_path, monkeypatch):
    guard = _guard()
    wf = tmp_path / "workflows"
    wf.mkdir()
    (wf / "planted.yml").write_text(
        "jobs:\n"
        "  gate:\n"
        "    steps:\n"
        "      - run: git diff ${{ github.event.pull_request.base.sha }}...HEAD\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(guard, "WORKFLOWS", wf)
    assert guard.main() == 1


def test_a_comment_mentioning_the_field_is_not_a_violation(tmp_path, monkeypatch):
    """ci.yml documents the rule by naming the field three times. A guard that flags its own
    explanation is unusable, and the comments are how the lesson survives."""
    guard = _guard()
    wf = tmp_path / "workflows"
    wf.mkdir()
    (wf / "documented.yml").write_text(
        "jobs:\n"
        "  gate:\n"
        "    steps:\n"
        "      # Derive the base from LIVE origin/main, not\n"
        "      # github.event.pull_request.base.sha — it is frozen at PR-open time.\n"
        "      - run: |\n"
        "          git fetch --quiet origin main\n"
        "          BASE_SHA=$(git merge-base origin/main HEAD || true)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(guard, "WORKFLOWS", wf)
    assert guard.main() == 0


def test_a_missing_workflows_dir_is_exit_2_not_a_silent_pass(tmp_path, monkeypatch):
    """Exit 0 here would mean "no violations found" when the guard never looked."""
    guard = _guard()
    monkeypatch.setattr(guard, "WORKFLOWS", tmp_path / "does-not-exist")
    assert guard.main() == 2
