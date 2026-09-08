"""
PDF fixture builder for the Prompt A PDF-path unblock.

Converts the three HR Policy Dummy DOCX files to PDF via LibreOffice, and
derives a password-encrypted PDF from the first one via qpdf. All outputs
land under backend/tests/fixtures/generated/pdf/ which is gitignored —
fixtures are rebuilt at test time and never committed.

Invocation:
    python backend/tests/fixtures/build_pdf_fixtures.py           # idempotent
    python backend/tests/fixtures/build_pdf_fixtures.py --force   # rebuild all

A session-scoped pytest fixture in backend/tests/conftest.py calls this
once per test session, skipping cleanly when the required tools are
missing on the host.

Tools are resolved via shutil.which so the builder works on any host
that has soffice / qpdf on PATH (Homebrew prefix or user-local install,
either way). No hardcoded paths.

Audit reference: Prompt A §4 fixture generation; GAP-011 (host tools).
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

log = logging.getLogger(__name__)

# Source roots probed in order. `.audit_tmp/fixtures/source_docx/` is the
# audit-time location the user copied the OneDrive originals into during
# the first Prompt A pass; `backend/tests/fixtures/` is the canonical
# repo-shipped location if fixtures ever get committed.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SOURCE_ROOTS: tuple[Path, ...] = (
    _REPO_ROOT / ".audit_tmp" / "fixtures" / "source_docx",
    _REPO_ROOT / "backend" / "tests" / "fixtures" / "source_docx",
)
_OUTPUT_DIR: Path = _REPO_ROOT / "backend" / "tests" / "fixtures" / "generated" / "pdf"

# File name pattern is intentionally loose: glob-match any .docx whose
# stem contains "dummy" (case-insensitive) in any source root.
_DOCX_GLOB = "*[Dd]ummy*.docx"


class FixtureBuildError(RuntimeError):
    """Raised when a required tool is missing or a conversion fails."""


def _run(cmd: List[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """Thin subprocess wrapper that preserves stdout / stderr on failure."""
    return subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)


def _discover_sources() -> List[Path]:
    """
    Locate the three HR Policy Dummy DOCX files across the configured
    source roots. Returns a sorted list (stable for audit logs). Empty
    list when no source root holds any matching file — caller decides
    whether that's fatal.
    """
    found: List[Path] = []
    for root in _SOURCE_ROOTS:
        if not root.is_dir():
            continue
        for p in sorted(root.glob(_DOCX_GLOB)):
            if p.is_file():
                found.append(p)
        if found:
            break  # first root with matches wins
    return found


def _tool_version(tool: str) -> str:
    """Best-effort version string for logging. Never raises."""
    path = shutil.which(tool)
    if not path:
        return "(missing)"
    for flag in ("--version", "-v"):
        try:
            res = subprocess.run([tool, flag], capture_output=True, timeout=5)
        except Exception:
            continue
        text = (res.stdout or res.stderr).decode(errors="ignore").strip()
        if text:
            return text.splitlines()[0]
    return f"{path} (version unknown)"


def _needs_rebuild(src: Path, dst: Path, force: bool) -> bool:
    if force:
        return True
    if not dst.exists():
        return True
    try:
        return src.stat().st_mtime > dst.stat().st_mtime
    except FileNotFoundError:
        return True


def _docx_to_pdf(src: Path, out_dir: Path, force: bool) -> Path:
    """
    Convert one .docx to .pdf via LibreOffice. Returns the output path.
    Raises FixtureBuildError on non-zero exit, timeout, or missing output.
    """
    out = out_dir / (src.stem + ".pdf")
    if not _needs_rebuild(src, out, force):
        log.info("skipping (up-to-date): %s", out.name)
        return out

    soffice = shutil.which("soffice")
    if not soffice:
        raise FixtureBuildError("soffice not on PATH")

    out_dir.mkdir(parents=True, exist_ok=True)
    # Per `libreoffice --help`, the `--convert-to pdf` path writes the
    # output into `--outdir` using the source stem. Use `--headless`
    # so no UI tries to draw.
    cmd = [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(src)]
    log.info("converting: %s → %s", src.name, out.name)
    try:
        res = _run(cmd, timeout=30)
    except subprocess.TimeoutExpired as exc:
        raise FixtureBuildError(f"soffice timed out converting {src.name}") from exc
    if res.returncode != 0:
        raise FixtureBuildError(
            f"soffice returned {res.returncode} for {src.name}: "
            f"{res.stderr.decode(errors='ignore')[:400]}"
        )
    if not out.exists():
        raise FixtureBuildError(f"soffice reported success but {out} is missing")
    return out


def _make_encrypted(src_pdf: Path, out_dir: Path, force: bool) -> Path:
    """Encrypt a source PDF with qpdf. Returns the output path."""
    out = out_dir / "encrypted_dummy1.pdf"
    if not _needs_rebuild(src_pdf, out, force):
        log.info("skipping (up-to-date): %s", out.name)
        return out

    qpdf = shutil.which("qpdf")
    if not qpdf:
        raise FixtureBuildError("qpdf not on PATH")

    out_dir.mkdir(parents=True, exist_ok=True)
    # 256-bit AES; 'user_pw' is the open password, 'owner_pw' is the
    # permissions password. Both are fixture-only — never secrets.
    cmd = [qpdf, "--encrypt", "user_pw", "owner_pw", "256", "--", str(src_pdf), str(out)]
    log.info("encrypting: %s → %s", src_pdf.name, out.name)
    res = _run(cmd, timeout=30)
    if res.returncode != 0:
        raise FixtureBuildError(
            f"qpdf returned {res.returncode} for {src_pdf.name}: "
            f"{res.stderr.decode(errors='ignore')[:400]}"
        )
    if not out.exists():
        raise FixtureBuildError(f"qpdf reported success but {out} is missing")
    return out


def build_all(force: bool = False) -> List[Path]:
    """
    Build every PDF fixture. Returns the list of produced paths (including
    skipped-idempotent ones). Raises FixtureBuildError on failure.
    """
    print(f"soffice={_tool_version('soffice')}")
    print(f"qpdf={_tool_version('qpdf')}")
    print(f"python={sys.version.split()[0]}")

    sources = _discover_sources()
    if not sources:
        raise FixtureBuildError(
            f"no source .docx files matched {_DOCX_GLOB} under any of: "
            + ", ".join(str(r) for r in _SOURCE_ROOTS)
        )

    produced: List[Path] = []
    for src in sources:
        pdf = _docx_to_pdf(src, _OUTPUT_DIR, force=force)
        produced.append(pdf)

    # Encrypted variant built from the first generated PDF (the lowest-
    # numbered dummy). Also drives the §9 R1 encrypted-PDF test.
    if produced:
        encrypted = _make_encrypted(produced[0], _OUTPUT_DIR, force=force)
        produced.append(encrypted)

    return produced


def main() -> int:
    parser = argparse.ArgumentParser(description="Build PDF fixtures for Prompt A.")
    parser.add_argument("--force", action="store_true", help="Rebuild even when outputs are newer.")
    parser.add_argument("--verbose", action="store_true", help="DEBUG logging.")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        produced = build_all(force=args.force)
    except FixtureBuildError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired as exc:
        print(f"FAIL (timeout): {exc}", file=sys.stderr)
        return 1

    for p in produced:
        print(f"  -> {p.relative_to(_REPO_ROOT)}")
    print(f"OK — {len(produced)} fixtures at {_OUTPUT_DIR.relative_to(_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
