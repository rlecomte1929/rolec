"""
immigration_gdpr.py — GDPR subject-rights stub routes extracted from
immigration.py (AUDIT-B9-imm-5, re-scoped from immigration_documents.py
per imm-1 split plan §6 finding).

Houses 2 endpoints:
  GET  /api/employee/cases/{case_id}/my-data/export             (IMM-17)
  POST /api/employee/cases/{case_id}/my-data/erasure-request    (IMM-18)

Both are stubs — return 501. When IMM-17 / IMM-18 land, the implementation
goes here.

DORMANT: this router is not yet wired into backend/app/main.py.
Canonical registration still happens via immigration.py until imm-6.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from ..auth_deps import get_current_user

router = APIRouter(prefix="/api", tags=["immigration-gdpr"])


@router.get("/employee/cases/{case_id}/my-data/export")
def data_export_stub(case_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    raise HTTPException(status_code=501, detail="Data export (IMM-17) not yet implemented.")


@router.post("/employee/cases/{case_id}/my-data/erasure-request")
def erasure_request_stub(case_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    raise HTTPException(status_code=501, detail="Erasure workflow (IMM-18) not yet implemented.")
