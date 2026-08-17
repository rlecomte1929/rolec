"""[AIQ-1859] Scanning a passport must not put it in the vault.

`POST /employee/cases/{id}/profile/ocr-passport` used to call `save_ocr_to_vault`
before the employee had seen a single extracted field. Its own docstring said so:

    Does NOT require the employee to confirm — fields are saved immediately
    with source='ocr'

So the UI's "Save extracted data" button was decorative, and "Discard & enter
manually" only advanced the wizard (ImmigrationPage sets stage='interview') while the
passport number, MRZ lines and date of birth stayed in the vault. With
IMMIGRATION_ENCRYPTION_KEY live that is passport data written before the person agreed
to save it, and declining did not remove it.

Extraction is now read-only. The write happens on confirm, through
`PUT /employee/cases/{id}/profile`, which already gates on consent and encrypts
passport_number — and now records provenance `ocr_confirmed` (a machine read it, a
human checked it) rather than flattening it to `self_entered`.

These are unit tests over the module, not HTTP: the point is the *absence* of a call,
which is easiest to assert directly and impossible to fake.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

ROUTER = Path(__file__).resolve().parents[1] / "app" / "routers" / "immigration_intake_profile.py"


def _ocr_handler_source() -> str:
    """Source of the ocr_passport handler only — not the whole module."""
    tree = ast.parse(ROUTER.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "ocr_passport":
            return ast.get_source_segment(ROUTER.read_text(), node) or ""
    raise AssertionError("ocr_passport handler not found — did it get renamed?")


def _calls_in(src: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                names.add(fn.id)
            elif isinstance(fn, ast.Attribute):
                names.add(fn.attr)
    return names


def test_ocr_endpoint_never_writes_the_vault():
    """THE test. A comment saying 'do not reinstate' is not enforcement; this is."""
    called = _calls_in(_ocr_handler_source())
    assert "save_ocr_to_vault" not in called, (
        "ocr-passport called save_ocr_to_vault — that stores passport fields before the "
        "employee has confirmed them, and Discard does not undo it. The write belongs in "
        "PUT /employee/cases/{case_id}/profile."
    )


def test_the_audit_entry_does_not_claim_a_write():
    """An extract that persisted nothing must not log like it saved fields."""
    src = _ocr_handler_source()
    assert 'action="ocr_extract_preview"' in src, (
        "the OCR audit action should say preview — an `ocr_extract` entry listing fields "
        "reads, in an audit review, as those fields having been written"
    )


def test_employee_writes_may_claim_ocr_confirmed_but_not_hr_provided():
    """Provenance vocabulary for an employee-initiated write."""
    from backend.app.routers import immigration_intake_profile as m

    assert m._EMPLOYEE_FIELD_SOURCES == {"self_entered", "ocr_confirmed"}, (
        "employee writes must be able to record a reviewed-OCR origin, and must never be "
        "able to attribute their own edit to HR"
    )


def test_field_source_is_stripped_before_sql_is_built():
    """`field_source` is provenance, not a column.

    Every branch of the handler builds SQL from the keys of `updates`, so if the pop
    ever moves below the first use the endpoint emits `field_source = :field_source`
    against a column that does not exist — a 500 on every profile save.
    """
    from backend.app.routers import immigration_intake_profile as m

    src = inspect.getsource(m.upsert_profile_employee)
    pop_at = src.find('updates.pop("field_source"')
    assert pop_at != -1, "field_source must be popped out of updates"
    for marker in ("set_clauses", "params.update(updates)", "for f in updates"):
        use_at = src.find(marker)
        if use_at != -1:
            assert pop_at < use_at, f"field_source must be popped before `{marker}` reads updates"


def test_profile_update_model_carries_every_field_the_extraction_produces():
    """The confirm path must be able to persist everything the scan found.

    If the extraction grows a field the model lacks, confirm would silently drop it and
    the employee's reviewed value would be lost.
    """
    from backend.app.routers.immigration_intake_profile import EmployeeProfileUpdate

    extracted = {
        "legal_first_name", "legal_last_name", "date_of_birth", "gender",
        "place_of_birth", "nationality", "passport_country", "passport_expiry",
        "passport_issue_date", "passport_number", "passport_mrz_line1", "passport_mrz_line2",
    }
    missing = extracted - set(EmployeeProfileUpdate.model_fields)
    assert not missing, f"confirm cannot persist these extracted fields: {sorted(missing)}"
