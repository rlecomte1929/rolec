"""
PDF-path ingestion tests (Prompt A §7).

For each of the three dummy DOCX fixtures, convert to PDF via the
session-scoped generated_pdf_dir fixture, feed the PDF bytes through
process_uploaded_document, and verify the pipeline produces the same
shape of output it does for DOCX: non-empty raw_text, typed
classification, section titles recoverable from the content.

Run with:
    pytest backend/tests/services/test_policy_pdf_ingestion.py -v -k pdf
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Dict

import pytest

# Skip the whole module on hosts that don't have the PDF toolchain — CI
# runners (ubuntu-latest in GitHub Actions) don't ship soffice. We also
# skip when pdfplumber isn't importable so a drifted venv surfaces cleanly
# rather than as an error in every parametrized test.
pytestmark = pytest.mark.skipif(
    shutil.which("soffice") is None
    or shutil.which("qpdf") is None
    or not __import__("importlib.util").util.find_spec("pdfplumber"),
    reason=(
        "PDF toolchain (soffice + qpdf + pdfplumber) required for §7 ingestion "
        "tests — not present on this host. See VERIFY_PDF_TOOLS.sh."
    ),
)

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_document_intake import (  # noqa: E402
    DOC_TYPE_ASSIGNMENT_POLICY,
    DOC_TYPE_UNKNOWN,
    STATUS_CLASSIFIED,
    STATUS_REVIEW_REQUIRED,
    process_uploaded_document,
)


# Expected outcomes per tenant — derived from the DOCX behavior (now
# already green). PDF ingestion of the same content should match.
_EXPECTED: Dict[str, Dict[str, str]] = {
    "HR_Policy_Dummy_1.pdf": {
        "detected_document_type": DOC_TYPE_ASSIGNMENT_POLICY,
        "terminal_status": STATUS_CLASSIFIED,
    },
    "HR_Policy_Dummy_2.pdf": {
        "detected_document_type": DOC_TYPE_ASSIGNMENT_POLICY,
        "terminal_status": STATUS_CLASSIFIED,
    },
    "HR_Policy_Dummy_3.pdf": {
        "detected_document_type": DOC_TYPE_UNKNOWN,
        "terminal_status": STATUS_REVIEW_REQUIRED,
    },
}


@pytest.fixture(scope="module", params=list(_EXPECTED.keys()))
def pdf_tenant(request, generated_pdf_dir):
    """Parametrize each PDF-path test over the three tenants."""
    pdf = Path(generated_pdf_dir) / request.param
    if not pdf.exists():
        pytest.skip(f"PDF fixture missing: {pdf}")
    return {
        "name": request.param,
        "path": pdf,
        "bytes": pdf.read_bytes(),
        "expected": _EXPECTED[request.param],
    }


class TestPdfIngest:
    """§7 DOCX.*.* assertions, translated to the PDF path."""

    def test_pdf_processes_without_crash(self, pdf_tenant) -> None:
        result = process_uploaded_document(
            pdf_tenant["bytes"], "application/pdf", pdf_tenant["name"]
        )
        assert result.get("processing_status") in (
            STATUS_CLASSIFIED,
            STATUS_REVIEW_REQUIRED,
        ), f"unexpected status: {result.get('processing_status')}"

    def test_pdf_raw_text_non_empty(self, pdf_tenant) -> None:
        result = process_uploaded_document(
            pdf_tenant["bytes"], "application/pdf", pdf_tenant["name"]
        )
        raw = (result.get("raw_text") or "").strip()
        assert raw, "raw_text must be non-empty for a valid policy PDF"
        # Cheap sanity: the preamble line "Assignment Type:" should appear.
        assert "assignment type" in raw.lower()

    def test_pdf_detected_document_type_matches_docx_baseline(self, pdf_tenant) -> None:
        result = process_uploaded_document(
            pdf_tenant["bytes"], "application/pdf", pdf_tenant["name"]
        )
        assert result.get("detected_document_type") == pdf_tenant["expected"]["detected_document_type"]

    def test_pdf_terminal_status_matches_docx_baseline(self, pdf_tenant) -> None:
        result = process_uploaded_document(
            pdf_tenant["bytes"], "application/pdf", pdf_tenant["name"]
        )
        assert result.get("processing_status") == pdf_tenant["expected"]["terminal_status"]

    def test_pdf_text_mentions_six_canonical_sections(self, pdf_tenant) -> None:
        """Each dummy has 6 numbered sections; extracted text must preserve them."""
        result = process_uploaded_document(
            pdf_tenant["bytes"], "application/pdf", pdf_tenant["name"]
        )
        raw_lower = (result.get("raw_text") or "").lower()
        for section in (
            "immigration & legal",
            "relocation assistance",
            "compensation & allowances",
            "family support",
            "tax & payroll",
            "conditions",
        ):
            assert section in raw_lower, f"PDF extraction dropped section '{section}'"
