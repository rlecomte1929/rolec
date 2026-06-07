"""HR vendor-curation widget endpoints at their canonical bare paths (B16 / AIQ-422).

The vendor-curation widget and the E2E runner (T11_WIDGET) call:
  - GET /api/hr/vendor-assignments/pending
  - GET /api/hr/employees/waiting

The underlying handlers already exist in ``hr_catalog`` (computed from
``catalog_employee_demand`` vs ``company_vendor_selections``), but only under the
``/api/hr/catalog`` router prefix, so the bare paths still 404'd. This router
re-exposes the same handler functions at the bare paths — no logic duplication,
same ``require_admin_or_hr`` auth and company scoping.
"""
from fastapi import APIRouter

from .hr_catalog import employees_waiting_count, list_pending_vendor_assignments

router = APIRouter(tags=["hr_vendor_widgets"])

router.add_api_route(
    "/api/hr/vendor-assignments/pending",
    list_pending_vendor_assignments,
    methods=["GET"],
)
router.add_api_route(
    "/api/hr/employees/waiting",
    employees_waiting_count,
    methods=["GET"],
)
