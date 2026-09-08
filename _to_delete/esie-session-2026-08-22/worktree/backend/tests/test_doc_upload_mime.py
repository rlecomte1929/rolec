"""[DOC-UPLOAD-502] Unit tests for the document upload MIME resolver.

The case-documents bucket only accepts PDF + common image types and rejects
application/octet-stream. _resolve_doc_mime must yield an allowed type (inferring
from the filename when the client omits/ defaults the content type) or None so
the handler can return a clear 415 instead of a misleading 502.
"""
from __future__ import annotations

import unittest

from backend.app.routers.cases_write import _resolve_doc_mime


class TestDocUploadMime(unittest.TestCase):
    def test_declared_pdf_ok(self):
        self.assertEqual(_resolve_doc_mime("application/pdf", "x.pdf"), "application/pdf")

    def test_declared_image_ok(self):
        self.assertEqual(_resolve_doc_mime("image/png", "x.png"), "image/png")
        self.assertEqual(_resolve_doc_mime("IMAGE/JPEG", "x.jpg"), "image/jpeg")

    def test_octet_stream_infers_from_pdf_filename(self):
        # the core bug: client sends octet-stream for a real PDF -> infer pdf
        self.assertEqual(_resolve_doc_mime("application/octet-stream", "passport.pdf"), "application/pdf")

    def test_empty_infers_from_png_filename(self):
        self.assertEqual(_resolve_doc_mime("", "photo.png"), "image/png")
        self.assertEqual(_resolve_doc_mime(None, "scan.jpeg"), "image/jpeg")

    def test_disallowed_text_rejected(self):
        self.assertIsNone(_resolve_doc_mime("text/plain", "notes.txt"))

    def test_octet_stream_unknown_extension_rejected(self):
        self.assertIsNone(_resolve_doc_mime("application/octet-stream", "data.bin"))

    def test_no_type_no_extension_rejected(self):
        self.assertIsNone(_resolve_doc_mime(None, "upload"))

    def test_disallowed_office_doc_rejected(self):
        self.assertIsNone(_resolve_doc_mime("application/msword", "contract.doc"))


if __name__ == "__main__":
    unittest.main()
