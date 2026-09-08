"""BL-OCR.2 / AIQ-748 — immigration document upload endpoint.

Calls the handler directly (no FastAPI DI / TestClient — mirrors
test_correction_analytics.py). The router imports ``upload_validator`` lazily;
we swap it for a stub in ``sys.modules`` so the test needs neither libmagic nor
werkzeug (Render base-image deps). upload_validator is unit-tested separately —
here we verify the handler enforces case access, propagates the size/MIME
413/415, stamps uploaded_by, returns {document_id, storage_path, ocr_status},
and maps storage failures to 502.
"""
import asyncio
import os
import sys
import unittest
from unittest import mock
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("DATABASE_URL", "sqlite://")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Swap upload_validator (hard-imports libmagic + werkzeug) for a stub BEFORE the
# router is imported; the router's lazy `from ..services.upload_validator import
# read_and_validate` then resolves to this stub. Restored in tearDownModule so
# the rest of the curated suite sees the real module.
_UV_KEY = "backend.app.services.upload_validator"
_ORIG_UV = sys.modules.get(_UV_KEY)
_UV = MagicMock()
sys.modules[_UV_KEY] = _UV


def tearDownModule() -> None:  # noqa: N802 (unittest hook name)
    if _ORIG_UV is not None:
        sys.modules[_UV_KEY] = _ORIG_UV
    else:
        sys.modules.pop(_UV_KEY, None)


from fastapi import HTTPException  # noqa: E402

import backend.app.routers.immigration_documents as router_mod  # noqa: E402
from backend.app.routers.immigration_documents import upload_immigration_document  # noqa: E402

_USER = {"id": "user-1", "is_admin": True}


class ImmigrationUploadTests(unittest.TestCase):
    def setUp(self) -> None:
        # Assume case access for happy/validation paths (no DB).
        self.guard = mock.patch.object(router_mod, "_resolve_accessible_case", return_value="case-1")
        self.guard.start()
        self.addCleanup(self.guard.stop)
        # Default: a valid PDF passes the size/MIME gate.
        _UV.read_and_validate = AsyncMock(return_value=(b"data", "x.pdf", "application/pdf"))

    def _call(self):
        self.bg = MagicMock()
        return asyncio.run(
            upload_immigration_document(
                case_id="case-1", background_tasks=self.bg, file=MagicMock(), user=_USER
            )
        )

    def test_valid_upload_returns_document_contract(self) -> None:
        with mock.patch.object(
            router_mod, "store_immigration_document",
            return_value={"document_id": "d1", "storage_path": "case-1/d1.pdf", "ocr_status": "pending"},
        ) as store:
            res = self._call()
        self.assertEqual(res, {"document_id": "d1", "storage_path": "case-1/d1.pdf", "ocr_status": "pending"})
        self.assertEqual(store.call_args.kwargs["uploaded_by"], "user-1")
        self.assertEqual(store.call_args.kwargs["case_id"], "case-1")
        self.assertEqual(store.call_args.kwargs["mime_type"], "application/pdf")
        # BL-OCR.3: extraction scheduled in the background for the stored doc.
        self.bg.add_task.assert_called_once()
        self.assertIs(self.bg.add_task.call_args.args[0], router_mod.run_extraction)
        self.assertEqual(self.bg.add_task.call_args.kwargs["document_id"], "d1")

    def test_oversized_file_rejected_413(self) -> None:
        _UV.read_and_validate = AsyncMock(side_effect=HTTPException(status_code=413, detail="file_too_large"))
        with self.assertRaises(HTTPException) as ctx:
            self._call()
        self.assertEqual(ctx.exception.status_code, 413)

    def test_unsupported_type_rejected_415(self) -> None:
        _UV.read_and_validate = AsyncMock(side_effect=HTTPException(status_code=415, detail="unsupported_type"))
        with self.assertRaises(HTTPException) as ctx:
            self._call()
        self.assertEqual(ctx.exception.status_code, 415)

    def test_inaccessible_case_404(self) -> None:
        with mock.patch.object(
            router_mod, "_resolve_accessible_case",
            side_effect=HTTPException(status_code=404, detail="Case not found or not accessible"),
        ):
            with self.assertRaises(HTTPException) as ctx:
                self._call()
        self.assertEqual(ctx.exception.status_code, 404)

    def test_storage_failure_maps_to_502(self) -> None:
        with mock.patch.object(router_mod, "store_immigration_document", side_effect=RuntimeError("supabase down")):
            with self.assertRaises(HTTPException) as ctx:
                self._call()
        self.assertEqual(ctx.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
