"""BL-OCR.3 / AIQ-948 — document extraction queue (classify + extract + store).

run_extraction is the background OCR job: download → classify → (passport)
extract → UPDATE ocr_status/ocr_result. ocr_passport_extractor (which pulls the
OpenAI SDK) is stubbed; the Supabase client and the status writer are mocked, so
the test exercises the queue's control flow without network, OpenAI, or a DB.
"""
import asyncio
import os
import sys
import types
import unittest
from unittest import mock
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("DATABASE_URL", "sqlite://")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Stub the passport extractor (pulls the OpenAI SDK) BEFORE importing the queue;
# run_extraction lazy-imports it. Restored in tearDownModule.
_EXTRACTOR_KEY = "backend.app.services.ocr_passport_extractor"
_ORIG_EXTRACTOR = sys.modules.get(_EXTRACTOR_KEY)
sys.modules[_EXTRACTOR_KEY] = MagicMock()

import backend.app.services.document_extraction_queue as q  # noqa: E402


def tearDownModule() -> None:  # noqa: N802
    if _ORIG_EXTRACTOR is not None:
        sys.modules[_EXTRACTOR_KEY] = _ORIG_EXTRACTOR
    else:
        sys.modules.pop(_EXTRACTOR_KEY, None)


class ClassifyTests(unittest.TestCase):
    """[AIQ-1764] Behaviour is unchanged by the move; only the owner changed.

    Asserted against `document_classifier`, the module that now OWNS the function,
    rather than `document_extraction_queue`, which merely imports it. Testing the
    consumer would keep passing if the import were later dropped.
    """

    def test_filename_heuristic(self) -> None:
        from backend.app.services.document_classifier import classify_document

        self.assertEqual(classify_document("priya_passport.jpg", "image/jpeg"), "PASSPORT")
        self.assertEqual(classify_document("employment_contract.pdf", "application/pdf"), "CONTRACT")
        self.assertEqual(classify_document("march_payslip.pdf", "application/pdf"), "PAYSLIP")
        self.assertEqual(classify_document("random.pdf", "application/pdf"), "OTHER")
        self.assertEqual(classify_document(None, None), "OTHER")

    def test_queue_still_resolves_it_for_its_own_use(self) -> None:
        # The queue calls it at run_extraction time; the import must stay live.
        self.assertEqual(q.classify_document("priya_passport.jpg", "image/jpeg"), "PASSPORT")


class RunExtractionTests(unittest.TestCase):
    def _patch_storage(self):
        gc = mock.patch.object(q, "get_supabase_admin_client")
        m = gc.start()
        self.addCleanup(gc.stop)
        m.return_value.storage.from_.return_value.download.return_value = b"imgbytes"
        return m

    def test_passport_produces_structured_output(self) -> None:
        # The validation criterion: passport → PASSPORT → structured fields.
        fake = types.SimpleNamespace(
            surname="Dupont", given_names="Jean", date_of_birth="1990-05-14",
            gender="M", place_of_birth=None, nationality="FRA", issuing_country="FRA",
            passport_number="YY123456", issue_date="2020-05-14", expiry_date="2030-05-13",
            mrz_line1="P<FRADUPONT<<JEAN", mrz_line2="YY1234567FRA9005142",
            confidence={"surname": 0.97, "passport_number": 0.95},
            low_quality=False, low_quality_reason=None,
        )
        sys.modules[_EXTRACTOR_KEY].extract_passport = AsyncMock(return_value=fake)
        self._patch_storage()
        with mock.patch.object(q, "_update_status") as upd:
            asyncio.run(q.run_extraction(
                document_id="d1", storage_path="case-1/d1.jpg",
                mime_type="image/jpeg", file_name="priya_passport.jpg",
            ))
        statuses = [c.args[1] for c in upd.call_args_list]
        self.assertEqual(statuses, ["processing", "done"])
        ocr_result = upd.call_args_list[-1].args[2]
        self.assertEqual(ocr_result["document_type"], "PASSPORT")
        self.assertEqual(ocr_result["fields"]["passport_number"], "YY123456")
        self.assertEqual(ocr_result["fields"]["surname"], "Dupont")
        self.assertEqual(ocr_result["confidence"], 0.95)  # weakest field

    def test_non_passport_records_classification_only(self) -> None:
        self._patch_storage()
        with mock.patch.object(q, "_update_status") as upd:
            asyncio.run(q.run_extraction(
                document_id="d2", storage_path="case-1/d2.pdf",
                mime_type="application/pdf", file_name="random.pdf",
            ))
        self.assertEqual(upd.call_args_list[-1].args[1], "done")
        self.assertEqual(upd.call_args_list[-1].args[2], {"document_type": "OTHER", "fields": {}, "confidence": None})

    def test_failure_is_fail_soft(self) -> None:
        with mock.patch.object(q, "get_supabase_admin_client", side_effect=RuntimeError("storage down")), \
             mock.patch.object(q, "_update_status") as upd:
            asyncio.run(q.run_extraction(
                document_id="d3", storage_path="p", mime_type="image/jpeg", file_name="passport.jpg",
            ))  # must not raise
        statuses = [c.args[1] for c in upd.call_args_list]
        self.assertIn("failed", statuses)


if __name__ == "__main__":
    unittest.main()
