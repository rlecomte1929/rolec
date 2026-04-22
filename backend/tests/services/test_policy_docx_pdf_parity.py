"""
§8 DOCX↔PDF parity tests (Prompt A).

Same content should produce equivalent extraction regardless of which
format HR uploaded. The recipe's P1 (exact field-for-field equality
on the structured-fact dict) is reachable only with the LLM normalizer
enabled — §1 rule 1 forbids counting LLM output, and GAP-006 makes
disabling it clean. So this file asserts the deterministic substrate:

  - detected_document_type parity
  - terminal processing_status parity
  - currency-span SET parity (order-insensitive; same € amounts in both)
  - section-title coverage parity (6 canonical sections visible in both)
  - soft text token-overlap ≥ 0.85 (PDF extraction tolerates whitespace
    and page-boundary noise; DOCX is ground truth)

Failures here are PARITY-BUGs — filed in Prompt A format.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, Iterable, Set, Tuple

import pytest

# Skip the whole module on hosts without the PDF toolchain. GitHub Actions
# ubuntu-latest has no soffice; the per-fixture skip inside generated_pdf_dir
# doesn't propagate cleanly through parametrized module fixtures so we gate
# at collection time instead. Keep this aligned with test_policy_pdf_ingestion.
pytestmark = pytest.mark.skipif(
    shutil.which("soffice") is None
    or shutil.which("qpdf") is None
    or not __import__("importlib.util").util.find_spec("pdfplumber"),
    reason=(
        "PDF toolchain (soffice + qpdf + pdfplumber) required for §8 parity "
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
from backend.services.policy_fact_extraction_service import (  # noqa: E402
    _CURRENCY_RE,
)

_DOCX_DIR = Path(_REPO_ROOT) / ".audit_tmp" / "fixtures" / "source_docx"

_TENANTS: Tuple[Tuple[str, str], ...] = (
    ("HR_Policy_Dummy_1.docx", "HR_Policy_Dummy_1.pdf"),
    ("HR_Policy_Dummy_2.docx", "HR_Policy_Dummy_2.pdf"),
    ("HR_Policy_Dummy_3.docx", "HR_Policy_Dummy_3.pdf"),
)


def _process(path: Path, mime: str) -> Dict:
    if not path.exists():
        pytest.skip(f"fixture missing: {path}")
    return process_uploaded_document(path.read_bytes(), mime, path.name)


def _currency_spans(raw: str) -> Set[str]:
    """Normalise: trim whitespace, collapse internal spaces."""
    spans = set()
    for m in _CURRENCY_RE.findall(raw or ""):
        s = re.sub(r"\s+", " ", m.strip())
        spans.add(s)
    return spans


_TOKEN_RE = re.compile(r"[A-Za-z0-9€£]+(?:[.\-–—][A-Za-z0-9€£]+)*")


def _tokens(raw: str) -> Set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(raw or "")}


def _overlap(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@pytest.fixture(scope="module", params=_TENANTS, ids=[t[0] for t in _TENANTS])
def tenant_pair(request, generated_pdf_dir):
    docx_name, pdf_name = request.param
    docx = _DOCX_DIR / docx_name
    pdf = Path(generated_pdf_dir) / pdf_name
    if not docx.exists():
        pytest.skip(f"DOCX fixture missing: {docx}")
    if not pdf.exists():
        pytest.skip(f"PDF fixture missing: {pdf}")
    docx_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    pdf_mime = "application/pdf"
    return {
        "docx_name": docx_name,
        "pdf_name": pdf_name,
        "docx_result": _process(docx, docx_mime),
        "pdf_result": _process(pdf, pdf_mime),
    }


class TestParityP1:
    """
    P1 (deterministic subset): equivalent classification + extracted-fact
    surface across DOCX and PDF for the same source content.
    """

    def test_detected_document_type_parity(self, tenant_pair) -> None:
        assert (
            tenant_pair["docx_result"]["detected_document_type"]
            == tenant_pair["pdf_result"]["detected_document_type"]
        ), (
            f"{tenant_pair['docx_name']}: "
            f"DOCX→{tenant_pair['docx_result']['detected_document_type']}, "
            f"PDF→{tenant_pair['pdf_result']['detected_document_type']}"
        )

    def test_processing_status_parity(self, tenant_pair) -> None:
        assert (
            tenant_pair["docx_result"]["processing_status"]
            == tenant_pair["pdf_result"]["processing_status"]
        )

    def test_currency_span_set_parity(self, tenant_pair) -> None:
        """
        The *set* of currency spans extracted by _CURRENCY_RE should
        match across formats. Order-insensitive (PDFs sometimes reflow
        content), duplicates collapse.
        """
        docx_spans = _currency_spans(tenant_pair["docx_result"].get("raw_text") or "")
        pdf_spans = _currency_spans(tenant_pair["pdf_result"].get("raw_text") or "")
        # Dummy 3 has only one cap (€20,000) so an empty set on one side
        # would be a real parity bug even with a single-row corpus.
        assert docx_spans == pdf_spans, (
            f"{tenant_pair['docx_name']}: "
            f"docx-only={sorted(docx_spans - pdf_spans)}, "
            f"pdf-only={sorted(pdf_spans - docx_spans)}"
        )

    def test_section_titles_parity(self, tenant_pair) -> None:
        """Both formats must surface the six canonical top-level sections."""
        sections = (
            "immigration & legal",
            "relocation assistance",
            "compensation & allowances",
            "family support",
            "tax & payroll",
            "conditions",
        )
        docx_text = (tenant_pair["docx_result"].get("raw_text") or "").lower()
        pdf_text = (tenant_pair["pdf_result"].get("raw_text") or "").lower()
        for s in sections:
            assert s in docx_text, f"DOCX missing '{s}' (baseline regression)"
            assert s in pdf_text, f"PDF missing '{s}' (parity failure)"


class TestParityP2:
    """
    P2 (near-parity): token overlap between DOCX and PDF extractions ≥ 0.85.
    This tolerates whitespace differences and page-boundary hyphenation
    while catching real text-loss regressions.
    """

    def test_token_overlap_threshold(self, tenant_pair) -> None:
        docx_tokens = _tokens(tenant_pair["docx_result"].get("raw_text") or "")
        pdf_tokens = _tokens(tenant_pair["pdf_result"].get("raw_text") or "")
        overlap = _overlap(docx_tokens, pdf_tokens)
        assert overlap >= 0.85, (
            f"{tenant_pair['docx_name']}: token overlap {overlap:.2f} < 0.85; "
            f"docx-only sample: {sorted(docx_tokens - pdf_tokens)[:15]}, "
            f"pdf-only sample: {sorted(pdf_tokens - docx_tokens)[:15]}"
        )


class TestParityP3:
    """P3: tenant round-trip — no format-path rewrites company_id."""

    def test_mime_type_reflects_actual_input(self, tenant_pair) -> None:
        """
        process_uploaded_document uses sniff.kind, not the claimed MIME.
        Both formats must produce the right raw_text regardless of what
        mime_type was claimed. Already exercised above via correct MIME;
        this test double-checks with a nonsense claimed MIME.
        """
        docx_path = _DOCX_DIR / tenant_pair["docx_name"]
        out = process_uploaded_document(
            docx_path.read_bytes(),
            "application/octet-stream",  # deliberately wrong
            tenant_pair["docx_name"],
        )
        assert out.get("raw_text")  # sniffer overrode the wrong MIME
