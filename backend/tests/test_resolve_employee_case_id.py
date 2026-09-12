"""AIQ-2358 — GET /api/employee/tasks must not honor an unowned case_id."""

from backend.app.services.employee_case_scope import resolve_employee_case_id


def test_unowned_case_id_override_is_ignored():
    linked = [
        {
            "id": "assign-owned",
            "case_id": "case-owned",
            "canonical_case_id": "case-owned",
            "updated_at": "2026-09-01",
        }
    ]
    assert (
        resolve_employee_case_id(linked, "053c93bb-6ba4-4a7e-a26d-bc05dcfe3abe")
        is None
    )


def test_owned_case_id_override_is_accepted():
    linked = [
        {
            "id": "assign-owned",
            "case_id": "case-owned",
            "canonical_case_id": "case-owned",
            "updated_at": "2026-09-01",
        }
    ]
    assert resolve_employee_case_id(linked, "case-owned") == "case-owned"
    assert resolve_employee_case_id(linked, "assign-owned") == "case-owned"


def test_no_linked_assignment_returns_none_even_with_override():
    assert resolve_employee_case_id([], "case-owned") is None
    assert resolve_employee_case_id([], None) is None
