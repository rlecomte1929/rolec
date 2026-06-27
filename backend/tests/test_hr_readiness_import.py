"""Regression: the HR readiness endpoints must not ImportError.

`backend/db/hr.py` did `from . import provenance_catalog` inside
`get_hr_readiness_summary` / `get_hr_readiness_detail`. `.` is `backend.db`, which
has no `provenance_catalog` module (it lives at `backend/provenance_catalog.py`), so
EVERY call to GET /api/hr/assignments/{id}/readiness/summary|detail raised
``ImportError`` → HTTP 500. It went unnoticed because there were no tests exercising
the readiness path. Found via the AIQ-1311 live spine harness (metric M4b) + the real
prod traceback. These guards keep the import correct.
"""
from __future__ import annotations

import inspect


def test_provenance_catalog_importable_as_hr_uses_it():
    # The module + the two functions the readiness path calls must resolve from
    # the backend package (the corrected `from .. import provenance_catalog`).
    from backend import provenance_catalog

    assert hasattr(provenance_catalog, "degraded_readiness_payload")
    assert hasattr(provenance_catalog, "readiness_summary_provenance_block")


def test_hr_module_uses_correct_relative_import():
    import backend.db.hr as hr

    src = inspect.getsource(hr)
    # the broken form (resolves to backend.db, which has no provenance_catalog)
    assert "from . import provenance_catalog" not in src
    # the corrected form (backend.provenance_catalog)
    assert "from .. import provenance_catalog" in src
