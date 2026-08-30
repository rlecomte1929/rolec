"""CI coverage for the job-gating guard.

Runs in the backend pytest lane (ci.yml collects scripts/tests). Loads the guard by file
path rather than as a package — `scripts/` has no `__init__.py`, so `from scripts.x import`
resolves locally and raises ModuleNotFoundError under CI's full-suite discovery. Same idiom
as test_check_workflow_base_sha.py.

The planted-violation cases are the point. A guard that has only ever passed proves nothing:
the bug this one exists to catch (#2062 → #2076) was itself five days of a green pipeline in
which the five expensive jobs ran zero times. So these tests pin that it FAILS on the exact
shape that shipped, and that it refuses to pass when it cannot see anything.
"""
import importlib.util
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _guard():
    return _load("check_workflow_job_gating", "scripts/check_workflow_job_gating.py")


def _write(tmp_path, body):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "planted.yml").write_text(body)
    return tmp_path


def test_the_repo_is_clean_today():
    assert _guard().main(["--root", ROOT]) == 0, (
        "a job's explicit `if:` can be silently overridden by a skipped dependency — it will "
        "be SKIPPED and still report green, which is exactly the #2076 outage"
    )


def test_it_fails_on_the_shape_that_shipped(tmp_path):
    """#2062's exact shape: an `always()` aggregator, a dependent with a bare `if:`."""
    root = _write(
        tmp_path,
        "jobs:\n"
        "  changes:\n"
        "    runs-on: ubuntu-latest\n"
        "  gate:\n"
        "    if: always()\n"
        "    needs: [changes]\n"
        "    runs-on: ubuntu-latest\n"
        "  expensive:\n"
        "    needs: [changes, gate]\n"
        "    if: needs.changes.outputs.frontend == 'true'\n"
        "    runs-on: ubuntu-latest\n",
    )
    assert _guard().main(["--root", str(root)]) == 1


def test_a_status_function_clears_it(tmp_path):
    """The #2076 fix must read as clean, or the guard is unusable."""
    root = _write(
        tmp_path,
        "jobs:\n"
        "  changes:\n"
        "    runs-on: ubuntu-latest\n"
        "  gate:\n"
        "    if: always()\n"
        "    needs: [changes]\n"
        "    runs-on: ubuntu-latest\n"
        "  expensive:\n"
        "    needs: [changes, gate]\n"
        "    if: ${{ !cancelled() && needs.gate.result == 'success' "
        "&& needs.changes.outputs.frontend == 'true' }}\n"
        "    runs-on: ubuntu-latest\n",
    )
    assert _guard().main(["--root", str(root)]) == 0


def test_a_bare_if_on_an_unconditional_dependency_is_not_a_violation(tmp_path):
    """The ~17 guards gated on `changes` alone. `changes` has no `if:`, so nothing can skip.

    This is the boundary that keeps the guard honest: flagging these would force an allowlist
    on day one, and the docstring explains why there must not be one.
    """
    root = _write(
        tmp_path,
        "jobs:\n"
        "  changes:\n"
        "    runs-on: ubuntu-latest\n"
        "  migration-drift:\n"
        "    needs: changes\n"
        "    if: needs.changes.outputs.migrations == 'true'\n"
        "    runs-on: ubuntu-latest\n",
    )
    assert _guard().main(["--root", str(root)]) == 0


def test_no_if_at_all_is_not_a_violation(tmp_path):
    """Implicit success() — the author expressed no condition to be overridden."""
    root = _write(
        tmp_path,
        "jobs:\n"
        "  gate:\n"
        "    if: always()\n"
        "    runs-on: ubuntu-latest\n"
        "  after:\n"
        "    needs: [gate]\n"
        "    runs-on: ubuntu-latest\n",
    )
    assert _guard().main(["--root", str(root)]) == 0


def test_missing_workflows_dir_is_exit_2_not_a_pass(tmp_path):
    assert _guard().main(["--root", str(tmp_path)]) == 2


def test_unparseable_workflow_is_exit_2_not_a_silent_pass(tmp_path):
    """An unparsed workflow hides whatever it contains — never report clean over one."""
    root = _write(tmp_path, "jobs:\n  broken:\n   - this: [is not\n     valid yaml\n")
    with pytest.raises(SystemExit) as exc:
        _guard().main(["--root", str(root)])
    assert exc.value.code == 2


def test_zero_jobs_examined_fails(tmp_path):
    """'No unsafe gating' across an empty scan is a broken run, not a pass."""
    root = _write(tmp_path, "name: nothing\non: push\n")
    assert _guard().main(["--root", str(root)]) == 1
