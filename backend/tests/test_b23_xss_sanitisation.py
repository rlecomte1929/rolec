"""
B23 XSS sanitisation regression test — SEC1.

Validates that user-supplied free-text fields with HTML/script injection payloads
are escaped before storage. Checks three injection points:

  1. RegisterRequest.name             → full name on signup
  2. AssignCaseRequest.employeeFirstName → HR case assignment first name
  3. AssignCaseRequest.employeeLastName  → HR case assignment last name

No API server needed — tests the Pydantic model validators directly so the
check is instant and environment-agnostic.
"""
from __future__ import annotations

import unittest

from backend.schemas import AssignCaseRequest, RegisterRequest, UserRole

_XSS = "<script>alert(1)</script>"
_SAFE = "&lt;script&gt;alert(1)&lt;/script&gt;"


class TestB23XssSanitisation(unittest.TestCase):
    """SEC1: free-text fields must not store or reflect raw HTML/script tags."""

    # ------------------------------------------------------------------
    # RegisterRequest.name
    # ------------------------------------------------------------------
    def test_register_name_xss_is_escaped(self) -> None:
        req = RegisterRequest(
            email="test@example.com",
            password="hunter2",
            role=UserRole.EMPLOYEE,
            name=_XSS,
        )
        self.assertNotIn("<script>", req.name or "")
        self.assertNotIn("</script>", req.name or "")
        self.assertEqual(req.name, _SAFE)

    def test_register_name_none_is_unchanged(self) -> None:
        req = RegisterRequest(
            email="test@example.com",
            password="hunter2",
            role=UserRole.EMPLOYEE,
            name=None,
        )
        self.assertIsNone(req.name)

    def test_register_name_plain_text_unchanged(self) -> None:
        req = RegisterRequest(
            email="test@example.com",
            password="hunter2",
            role=UserRole.EMPLOYEE,
            name="Alice Smith",
        )
        self.assertEqual(req.name, "Alice Smith")

    # ------------------------------------------------------------------
    # AssignCaseRequest.employeeFirstName
    # ------------------------------------------------------------------
    def test_assign_case_first_name_xss_is_escaped(self) -> None:
        req = AssignCaseRequest(
            employeeIdentifier="emp@company.test",
            employeeFirstName=_XSS,
            employeeLastName="Smith",
        )
        self.assertNotIn("<script>", req.employeeFirstName or "")
        self.assertEqual(req.employeeFirstName, _SAFE)

    def test_assign_case_last_name_xss_is_escaped(self) -> None:
        req = AssignCaseRequest(
            employeeIdentifier="emp@company.test",
            employeeFirstName="Alice",
            employeeLastName=_XSS,
        )
        self.assertNotIn("<script>", req.employeeLastName or "")
        self.assertEqual(req.employeeLastName, _SAFE)

    def test_assign_case_names_none_is_unchanged(self) -> None:
        req = AssignCaseRequest(
            employeeIdentifier="emp@company.test",
            employeeFirstName=None,
            employeeLastName=None,
        )
        self.assertIsNone(req.employeeFirstName)
        self.assertIsNone(req.employeeLastName)

    def test_assign_case_names_plain_text_unchanged(self) -> None:
        req = AssignCaseRequest(
            employeeIdentifier="emp@company.test",
            employeeFirstName="Alice",
            employeeLastName="O'Brien-Jones",
        )
        self.assertEqual(req.employeeFirstName, "Alice")
        # Ampersand and apostrophe are NOT escaped — only angle brackets/quotes
        self.assertEqual(req.employeeLastName, "O&#x27;Brien-Jones")

    # ------------------------------------------------------------------
    # Other common injection characters
    # ------------------------------------------------------------------
    def test_ampersand_and_quotes_are_escaped(self) -> None:
        req = RegisterRequest(
            email="test@example.com",
            password="hunter2",
            role=UserRole.EMPLOYEE,
            name='Bob & <em>"Hello"</em>',
        )
        self.assertNotIn("<em>", req.name or "")
        self.assertNotIn(">", req.name or "")
        self.assertIn("&amp;", req.name or "")


if __name__ == "__main__":
    unittest.main()
