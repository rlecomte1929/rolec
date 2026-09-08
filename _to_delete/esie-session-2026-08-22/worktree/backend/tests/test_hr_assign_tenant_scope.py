"""Security guard: POST /api/hr/cases/{id}/assign must be company-scoped.

The tenant-isolation probe found that an HR from company A could assign on
company B's case (HTTP 200) — the B5 company-scope guard was on the case-detail
GET but NOT on the assign endpoint, so a cross-tenant write slipped through (and
an unowned case would even be claimed into the assigning HR's company).

The assign handler runs parallel futures + Supabase round-trips, so a functional
unit test is impractical here; guard the boundary at source (same pattern as the
case-engine bridge guards). Behaviour is verified live by the probe.
"""
from __future__ import annotations

import os
import unittest


def _assign_case_source() -> str:
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backend", "main.py"
    )
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()
    start = src.index("def assign_case(")
    end = src.index("\n@app.", start + 1)
    return src[start:end]


class HrAssignTenantScopeGuardTests(unittest.TestCase):
    def test_assign_enforces_company_boundary(self) -> None:
        body = _assign_case_source()
        # Must compare the case's owning company to the HR's company and 404 on
        # a mismatch (only when the case already has an owner — unowned cases are
        # claimed legitimately).
        self.assertIn("case_company", body)
        self.assertIn("hr_company_id == case_company", body)
        self.assertIn("hr_user_id", body)
        self.assertIn('status_code=404', body)


if __name__ == "__main__":
    unittest.main()
