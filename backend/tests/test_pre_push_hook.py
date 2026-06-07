"""Regression tests for .githooks/pre-push frontend-change detection (AIQ-550).

The hook is the only local safety net before push-to-main → Render auto-deploys,
so a *silent skip* of the build when frontend files changed can ship a broken
frontend to production. The original bug: on a new-branch push where
`git merge-base <tip> origin/main` failed, the range collapsed to a bare single
sha, and `git diff <sha>` compares the commit against the working tree (clean at
push time) → empty diff → "no frontend changes detected" → build skipped.

These tests build a throwaway git repo and drive the hook with simulated push
stdin lines ("<local_ref> <local_sha> <remote_ref> <remote_sha>"). A fake `npm`
shim on PATH makes the build phase deterministic without Node.
"""

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_SRC = REPO_ROOT / ".githooks" / "pre-push"

ZERO = "0" * 40


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit_file(repo, relpath, content, message):
    target = repo / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def repo(tmp_path):
    """A git repo with the hook installed and a fake `npm` shim on PATH."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")

    # Hook under test.
    hook_dir = repo / ".githooks"
    hook_dir.mkdir()
    hook = hook_dir / "pre-push"
    hook.write_text(HOOK_SRC.read_text())
    hook.chmod(0o755)

    # A frontend/ dir so need_build=1 reaches the (faked) build, not the
    # "frontend/ not found" early-out.
    base_sha = _commit_file(repo, "frontend/package.json", '{"name":"x"}\n', "init")

    # Fake npm: build always succeeds, instantly, with no Node required.
    shim = tmp_path / "bin"
    shim.mkdir()
    npm = shim / "npm"
    npm.write_text("#!/bin/sh\nexit 0\n")
    npm.chmod(0o755)

    return {"path": repo, "base_sha": base_sha, "shim": shim}


def _run_hook(repo, stdin):
    env = dict(os.environ)
    env["PATH"] = f"{repo['shim']}{os.pathsep}{env['PATH']}"
    proc = subprocess.run(
        ["bash", ".githooks/pre-push"],
        cwd=repo["path"],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _builds(out):
    return "running frontend production build" in out


def _skipped(out):
    return "no frontend changes detected" in out


# 1 + 4. A frontend change (existing-branch update) must trigger the build.
def test_frontend_change_triggers_build(repo):
    path = repo["path"]
    tip = _commit_file(path, "frontend/src/App.tsx", "export const x = 1\n", "fe")
    stdin = f"refs/heads/main {tip} refs/heads/main {repo['base_sha']}\n"
    code, out = _run_hook(repo, stdin)
    assert code == 0, out
    assert _builds(out), out
    assert not _skipped(out), out


# 2 + 5. Backend-only change must skip the build (fast path, no false build).
def test_backend_only_skips_build(repo):
    path = repo["path"]
    tip = _commit_file(path, "backend/app/thing.py", "x = 1\n", "be")
    stdin = f"refs/heads/main {tip} refs/heads/main {repo['base_sha']}\n"
    code, out = _run_hook(repo, stdin)
    assert code == 0, out
    assert _skipped(out), out
    assert not _builds(out), out


# 3. Mixed frontend + backend change must build.
def test_mixed_change_triggers_build(repo):
    path = repo["path"]
    (path / "backend").mkdir(exist_ok=True)
    (path / "backend" / "x.py").write_text("x = 1\n")
    (path / "frontend" / "src").mkdir(parents=True, exist_ok=True)
    (path / "frontend" / "src" / "y.tsx").write_text("export const y = 2\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-m", "mixed")
    tip = _git(path, "rev-parse", "HEAD")
    stdin = f"refs/heads/main {tip} refs/heads/main {repo['base_sha']}\n"
    code, out = _run_hook(repo, stdin)
    assert code == 0, out
    assert _builds(out), out


# AIQ-550 core regression: new branch, no origin/main → must NOT silently skip.
# The old single-sha fallback (`git diff <tip>`) reported zero changes here.
def test_new_branch_without_upstream_builds_to_be_safe(repo):
    path = repo["path"]
    tip = _commit_file(path, "frontend/src/New.tsx", "export const n = 3\n", "new")
    # remote_sha = zero (new branch); there is no origin/main in this repo.
    stdin = f"refs/heads/feat {tip} refs/heads/feat {ZERO}\n"
    code, out = _run_hook(repo, stdin)
    assert code == 0, out
    assert _builds(out), out
    # The bug's signature was this message appearing despite a frontend change.
    assert not _skipped(out), out


# Deletion pushes are a no-op (nothing to build).
def test_branch_deletion_is_noop(repo):
    stdin = f"(delete) {ZERO} refs/heads/old {repo['base_sha']}\n"
    code, out = _run_hook(repo, stdin)
    assert code == 0, out
    assert not _builds(out), out
