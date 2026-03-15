"""Supplier Registry API — list, search, filter, detail, admin CRUD."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from ..auth_deps import require_admin, require_admin_or_hr
from ..db import SessionLocal
from ..services.supplier_registry import (
    add_capability,
    create_supplier,
    get_supplier,
    list_supplier_countries,
    list_suppliers,
    remove_capability,
    search_by_service_destination,
    set_supplier_status,
    update_capability,
    update_scoring,
    update_supplier,
)
from ..services.supplier_validation import get_valid_service_categories

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


def get_session():
    with SessionLocal() as session:
        yield session


@router.get("/categories")
def list_service_categories(user: Dict[str, Any] = Depends(require_admin)):
    """List valid service categories for capability assignment."""
    return {"categories": get_valid_service_categories()}


@router.get("/countries")
def list_countries_api(user: Dict[str, Any] = Depends(require_admin_or_hr)):
    """List country codes from supplier capabilities (for filter dropdown)."""
    with SessionLocal() as session:
        codes = list_supplier_countries(session)
        return {"countries": codes}


@router.get("", response_model=Dict[str, Any])
def list_suppliers_api(
    user: Dict[str, Any] = Depends(require_admin_or_hr),
    status: Optional[str] = Query(None, description="Filter by status"),
    service_category: Optional[str] = Query(None, description="Filter by service category"),
    country_code: Optional[str] = Query(None, description="Filter by country"),
    city_name: Optional[str] = Query(None, description="Filter by city"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List suppliers with optional filters."""
    with SessionLocal() as session:
        items = list_suppliers(
            session,
            status=status,
            service_category=service_category,
            country_code=country_code,
            city_name=city_name,
            limit=limit,
            offset=offset,
        )
        return {"suppliers": items, "total": len(items)}


@router.get("/search", response_model=Dict[str, Any])
def search_suppliers_api(
    user: Dict[str, Any] = Depends(require_admin),
    service_category: str = Query(..., description="Service category (e.g. movers, schools)"),
    destination_country: Optional[str] = Query(None),
    destination_city: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
):
    """Search suppliers by service + destination. Used by recommendation engine."""
    with SessionLocal() as session:
        items = search_by_service_destination(
            session,
            service_category=service_category,
            destination_city=destination_city,
            destination_country=destination_country,
            limit=limit,
        )
        return {"suppliers": items}


@router.post("", response_model=Dict[str, Any])
def create_supplier_api(
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_admin),
):
    """Create supplier (admin only)."""
    try:
        with SessionLocal() as session:
            s = create_supplier(session, body)
            return s
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{supplier_id}", response_model=Dict[str, Any])
def get_supplier_api(
    supplier_id: str,
    request: Request,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
):
    """Get supplier detail with capabilities and scoring."""
    with SessionLocal() as session:
        s = get_supplier(session, supplier_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")
        try:
            from ...services.analytics_service import emit_event, EVENT_SUPPLIER_VIEWED
            emit_event(
                EVENT_SUPPLIER_VIEWED,
                request_id=getattr(request.state, "request_id", None),
                user_id=user.get("id"),
                user_role=user.get("role", "admin"),
                extra={"supplier_id": supplier_id, "supplier_name": s.get("name")},
            )
        except Exception:
            pass
        return s


@router.get("/{supplier_id}/ranking-debug", response_model=Dict[str, Any])
def get_supplier_ranking_debug(
    supplier_id: str,
    service_category: Optional[str] = Query(None, description="Service category to check match (e.g. movers)"),
    destination_country: Optional[str] = Query(None, description="Destination country code (e.g. GB)"),
    destination_city: Optional[str] = Query(None, description="Destination city name"),
    user: Dict[str, Any] = Depends(require_admin),
):
    """Admin: debug why a supplier ranks (or does not) for given service + destination."""
    with SessionLocal() as session:
        s = get_supplier(session, supplier_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")
        # Would this supplier be included by search_by_service_destination?
        would_match = False
        match_reason = "Not checked (no service_category and destination provided)"
        if service_category and (destination_country or destination_city):
            items = search_by_service_destination(
                session,
                service_category=service_category,
                destination_city=destination_city or None,
                destination_country=destination_country or None,
                limit=100,
            )
            ids = [str(x.get("item_id") or "") for x in items]
            would_match = supplier_id in ids
            match_reason = (
                "Included: supplier appears in search results for this service + destination."
                if would_match
                else "Excluded: supplier not in search results (check status=active, capability service_category and country/city coverage)."
            )
        return {
            "supplier_id": supplier_id,
            "name": s.get("name"),
            "status": s.get("status"),
            "capabilities": s.get("capabilities", []),
            "coverage_summary": s.get("coverage_summary"),
            "scoring": s.get("scoring"),
            "requested_service_category": service_category,
            "requested_destination_country": destination_country,
            "requested_destination_city": destination_city,
            "would_match_search": would_match,
            "match_reason": match_reason,
        }


@router.patch("/{supplier_id}", response_model=Dict[str, Any])
def update_supplier_api(
    supplier_id: str,
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_admin),
):
    """Update supplier (admin only)."""
    try:
        with SessionLocal() as session:
            s = update_supplier(session, supplier_id, body)
            if not s:
                raise HTTPException(status_code=404, detail="Supplier not found")
            return s
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{supplier_id}/status", response_model=Dict[str, Any])
def set_supplier_status_api(
    supplier_id: str,
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_admin),
):
    """Activate/deactivate supplier. Body: { "status": "active"|"inactive"|"draft" }"""
    status = (body.get("status") or "").strip().lower()
    if not status or status not in ("active", "inactive", "draft"):
        raise HTTPException(status_code=400, detail="status must be active, inactive, or draft")
    with SessionLocal() as session:
        s = set_supplier_status(session, supplier_id, status)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")
        return s


@router.post("/{supplier_id}/capabilities", response_model=Dict[str, Any])
def add_capability_api(
    supplier_id: str,
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_admin),
):
    """Add service capability (admin only)."""
    try:
        with SessionLocal() as session:
            s = add_capability(session, supplier_id, body)
            if not s:
                raise HTTPException(status_code=404, detail="Supplier not found")
            return s
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{supplier_id}/capabilities/{capability_id}", response_model=Dict[str, Any])
def update_capability_api(
    supplier_id: str,
    capability_id: str,
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_admin),
):
    """Update capability (admin only)."""
    try:
        with SessionLocal() as session:
            s = update_capability(session, supplier_id, capability_id, body)
            if not s:
                raise HTTPException(status_code=404, detail="Capability or supplier not found")
            return s
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{supplier_id}/capabilities/{capability_id}", response_model=Dict[str, Any])
def remove_capability_api(
    supplier_id: str,
    capability_id: str,
    user: Dict[str, Any] = Depends(require_admin),
):
    """Remove capability (admin only)."""
    with SessionLocal() as session:
        s = remove_capability(session, supplier_id, capability_id)
        if not s:
            raise HTTPException(status_code=404, detail="Capability or supplier not found")
        return s


@router.patch("/{supplier_id}/scoring", response_model=Dict[str, Any])
def update_scoring_api(
    supplier_id: str,
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_admin),
):
    """Update scoring/verification metadata (admin only)."""
    with SessionLocal() as session:
        s = update_scoring(session, supplier_id, body)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")
        return s
