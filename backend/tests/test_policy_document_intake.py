"""
N10 / AIQ-850 — OCR fallback for scanned (image-only) PDF HR policy documents.

OCR libraries (pytesseract/pdf2image) are NOT exercised here — they need the
Tesseract + poppler system binaries. The OCR call is mocked; these tests cover
the fallback DECISION logic and the extraction_method surfacing. Real OCR output
(Criteria 1 & 5) is a runtime/container spot-check (Yellow-tier sample).
"""
from __future__ import annotations

import os
import sys
import types
import unittest
from unittest import mock

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import policy_document_intake as pdi
from backend.app.services.policy_intake_errors import EncryptedDocumentError

_MOD = "backend.app.services.policy_document_intake"


class ExtractPdfOcrDecisionTests(unittest.TestCase):
    def test_text_layer_pdf_uses_pdfplumber_no_ocr(self):
        # Criterion 3: a PDF with a real text layer never invokes Tesseract.
        with mock.patch(f"{_MOD}._pdfplumber_lines",
                        return_value=(["A residence permit is required for stays over 90 days."], None)), \
             mock.patch(f"{_MOD}._ocr_pdf") as ocr:
            lines, err, method = pdi._extract_text_from_pdf(b"%PDF-text")
        self.assertIsNone(err)
        self.assertEqual(method, "pdfplumber")
        self.assertTrue(lines)
        ocr.assert_not_called()

    def test_image_only_pdf_triggers_ocr(self):
        # Criterion 1/2: empty pdfplumber text → OCR runs and returns non-empty text.
        with mock.patch(f"{_MOD}._pdfplumber_lines", return_value=([], None)), \
             mock.patch(f"{_MOD}._ocr_pdf",
                        return_value=(["Oppholdstillatelse kreves for opphold over 90 dager."], None, "ok")):
            lines, err, method = pdi._extract_text_from_pdf(b"%PDF-image")
        self.assertIsNone(err)
        self.assertEqual(method, "ocr")
        self.assertTrue(any("Oppholdstillatelse" in l for l in lines))

    def test_near_empty_text_triggers_ocr(self):
        # Below the min-length threshold (a few stray chars) is treated as "no text layer".
        with mock.patch(f"{_MOD}._pdfplumber_lines", return_value=(["p. 1"], None)), \
             mock.patch(f"{_MOD}._ocr_pdf", return_value=(["Full scanned policy body text."], None, "ok")):
            _, _, method = pdi._extract_text_from_pdf(b"%PDF")
        self.assertEqual(method, "ocr")

    def test_low_confidence_ocr_flags_quality(self):
        # Criterion 3(c): Tesseract confidence < 60% → ocr_low_quality.
        with mock.patch(f"{_MOD}._pdfplumber_lines", return_value=([], None)), \
             mock.patch(f"{_MOD}._ocr_pdf", return_value=(["g4rbl3d sc4n"], None, "low")):
            _, _, method = pdi._extract_text_from_pdf(b"%PDF")
        self.assertEqual(method, "ocr_low_quality")

    def test_ocr_unavailable_degrades_gracefully(self):
        # No Tesseract in the runtime → OCR returns an error; keep pdfplumber's
        # (empty) result so the intake raises the existing "no readable text" error.
        with mock.patch(f"{_MOD}._pdfplumber_lines", return_value=([], None)), \
             mock.patch(f"{_MOD}._ocr_pdf",
                        return_value=([], "ocr unavailable: No module named 'pytesseract'", "none")):
            lines, err, method = pdi._extract_text_from_pdf(b"%PDF")
        self.assertEqual(lines, [])
        self.assertIsNone(err)
        self.assertEqual(method, "pdfplumber")

    def test_pdfplumber_error_skips_ocr(self):
        # When pdfplumber itself raises (corrupt/unreadable), do NOT OCR — surface
        # the error so the intake raises MalformedDocumentError as before.
        with mock.patch(f"{_MOD}._pdfplumber_lines", return_value=([], "PDF read error")), \
             mock.patch(f"{_MOD}._ocr_pdf") as ocr:
            lines, err, method = pdi._extract_text_from_pdf(b"bad")
        self.assertEqual(err, "PDF read error")
        self.assertEqual(method, "none")
        ocr.assert_not_called()


class ProcessDocumentExtractionMethodTests(unittest.TestCase):
    @staticmethod
    def _sniff(kind="pdf"):
        return types.SimpleNamespace(kind=kind)

    def _run(self, *, method, lines):
        with mock.patch("backend.app.services.policy_filetype.validate_upload_bytes", return_value=self._sniff("pdf")), \
             mock.patch(f"{_MOD}._extract_text_from_pdf", return_value=(lines, None, method)), \
             mock.patch(f"{_MOD}.classify_document", return_value=("unknown", "unknown", False)), \
             mock.patch(f"{_MOD}.extract_metadata", return_value={}):
            return pdi.process_uploaded_document(b"%PDF", "application/pdf", "doc.pdf")

    def test_intake_response_carries_ocr_method(self):
        res = self._run(method="ocr", lines=["Scanned policy body, long enough to pass."])
        self.assertEqual(res["extraction_method"], "ocr")
        self.assertTrue(res["raw_text"])

    def test_intake_response_carries_pdfplumber_method(self):
        res = self._run(method="pdfplumber", lines=["Native text-layer policy body."])
        self.assertEqual(res["extraction_method"], "pdfplumber")

    def test_encrypted_pdf_unchanged_and_no_ocr(self):
        # Criterion 4: encrypted PDFs are rejected by the encryption gate BEFORE
        # extraction — OCR is never reached; existing behaviour is unchanged.
        with mock.patch("backend.app.services.policy_filetype.validate_upload_bytes",
                        side_effect=EncryptedDocumentError("encrypted")), \
             mock.patch(f"{_MOD}._extract_text_from_pdf") as ext:
            with self.assertRaises(EncryptedDocumentError):
                pdi.process_uploaded_document(b"%PDF", "application/pdf", "enc.pdf")
        ext.assert_not_called()


if __name__ == "__main__":
    unittest.main()
