"""Pytest hooks for backend tests."""
from __future__ import annotations

import os
import shutil

# Disable auth-endpoint rate limits during tests so repeated logins in a single
# run don't flake. Must be set before backend.main is imported.
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

# Make ~/homebrew/bin and the LibreOffice MacOS dir available to subprocess
# calls started from tests (fixture builder shells out to soffice / qpdf).
# No-ops when the paths don't exist; safe to always prepend.
_HB = os.path.expanduser("~/homebrew/bin")
_LO = os.path.expanduser("~/Applications/LibreOffice.app/Contents/MacOS")
for _p in (_HB, _LO, "/opt/homebrew/bin", "/usr/local/bin"):
    if os.path.isdir(_p) and _p not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = _p + os.pathsep + os.environ.get("PATH", "")

import pytest

# QG-2 (AIQ-1176): full-suite discovery exposed test modules that have always been
# broken at *import* time (they were never in the old hardcoded CI list, so this is
# not a regression). A collection ImportError aborts the whole run, and a marker
# can't skip a module that fails to import — so they're ignored here, by category,
# until fixed. Skip-list (shrinks over time), NOT an inclusion list — every other
# test now gates automatically.
collect_ignore = [
    # Pre-migration `from services...` imports — resolve only with backend/ on
    # sys.path; canonical path is backend.app.services (AUDIT-A9.3 service-tree
    # consolidation owns the fix; do not partially migrate per backend/CLAUDE.md).
    "test_collaboration.py",
    "test_dossier.py",
    "test_employee_policy_matrix_bridge.py",
    "test_guidance_pack.py",
    # Relative imports with no parent package (need a package __init__ or
    # importlib import-mode — out of scope for this CI-wiring change).
    "test_collaboration_api.py",
    "test_employee_policy_resolution.py",
    "test_official_ingest.py",
    "test_admin.py",
    "test_admin_verification.py",
    # scipy removed `trapz` (use scipy.integrate.trapezoid / numpy.trapezoid) —
    # real code/dep fix tracked separately.
    "test_case_duration_model.py",
]


def pytest_runtest_setup(item: pytest.Item) -> None:
    if "policy_assistant_audit" not in item.keywords:
        return
    if os.environ.get("RUN_POLICY_ASSISTANT_AUDIT") == "1":
        return
    markexpr = getattr(item.config.option, "markexpr", "") or ""
    if "policy_assistant_audit" in markexpr:
        return
    pytest.skip(
        "Policy assistant audit tests are opt-in: use "
        "`pytest -m policy_assistant_audit` or set RUN_POLICY_ASSISTANT_AUDIT=1"
    )


# ----------------------------------------------------------------------------
# PDF fixture bootstrap (GAP-011).
# Runs once per test session when a test needs the generated PDFs. No-op when
# the required tools aren't on PATH — individual tests guard themselves with
# @pytest.mark.skipif so the session stays green on fixture-less machines.
# ----------------------------------------------------------------------------

@pytest.fixture(scope="session")
def generated_pdf_dir() -> str:
    """
    Ensure the generated PDF fixture set exists. Returns its absolute path.

    Skips the requesting test with a clear reason when:
      - soffice or qpdf are missing on PATH (host lacks GAP-011 tooling), or
      - the source DOCX files haven't been copied into
        .audit_tmp/fixtures/source_docx/ yet.

    Idempotent: the builder itself short-circuits when outputs are newer
    than sources.
    """
    from pathlib import Path
    import sys

    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root))

    if not shutil.which("soffice") or not shutil.which("qpdf"):
        pytest.skip(
            "GAP-011: soffice or qpdf not on PATH — cannot build PDF fixtures. "
            "Install with `brew install --cask libreoffice && brew install qpdf`."
        )

    from backend.tests.fixtures.build_pdf_fixtures import build_all, FixtureBuildError

    try:
        build_all(force=False)
    except FixtureBuildError as exc:
        pytest.skip(f"PDF fixture builder failed: {exc}")

    out_dir = repo_root / "backend" / "tests" / "fixtures" / "generated" / "pdf"
    if not out_dir.is_dir():
        pytest.skip(f"PDF fixture dir not created: {out_dir}")
    return str(out_dir)
