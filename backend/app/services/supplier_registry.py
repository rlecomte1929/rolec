"""
Supplier Registry service — source of truth for recommendation matching and RFQ.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Supplier, SupplierServiceCapability, SupplierScoringMetadata
from .supplier_validation import (
    check_duplicate_capability,
    normalize_country_code,
    validate_active_supplier_requirements,
    validate_capability,
    validate_supplier_create,
    validate_supplier_update,
)


class DuplicateSupplierError(ValueError):
    """[AIQ-1511] A supplier with this name already exists.

    Subclasses ValueError so existing `except ValueError` callers keep working; routers
    that want the distinct 409 catch this first (see routers/suppliers.py).
    """

log = logging.getLogger(__name__)


def _parse_json_array(val: Any) -> List[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x) for x in val]
    if isinstance(val, str):
        try:
            out = json.loads(val)
            return [str(x) for x in out] if isinstance(out, list) else []
        except Exception:
            return [x.strip() for x in val.split(",") if x.strip()]
    return []


def _serialize_json_array(arr: List[str]) -> str:
    return json.dumps(arr) if arr else "[]"


def list_suppliers(
    session: Session,
    *,
    status: Optional[str] = None,
    service_category: Optional[str] = None,
    country_code: Optional[str] = None,
    city_name: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """List suppliers with optional filters.
    Country filter: show supplier if any capability covers the country (country_code match) or is global.
    """
    q = session.query(Supplier)
    if status:
        q = q.filter(Supplier.status == status)
    if service_category or country_code or city_name:
        q = q.join(SupplierServiceCapability, Supplier.id == SupplierServiceCapability.supplier_id)
        if service_category:
            q = q.filter(SupplierServiceCapability.service_category == service_category)
        if country_code:
            cc_upper = country_code.strip().upper()[:2]
            q = q.filter(
                (SupplierServiceCapability.country_code == cc_upper)
                | (SupplierServiceCapability.coverage_scope_type == "global")
            )
        if city_name:
            q = q.filter(
                (SupplierServiceCapability.city_name == city_name)
                | (SupplierServiceCapability.coverage_scope_type.in_(["global", "country"]))
            )
        q = q.distinct()
    q = q.order_by(Supplier.name)
    rows = q.offset(offset).limit(limit).all()
    return [_supplier_to_dict(r, session, include_list_summary=True) for r in rows]


def _has_accreditations_table(session: Session) -> bool:
    """Whether `supplier_accreditations` exists on this bind.

    Checked rather than caught: the table is real in production but absent from the SQLite
    unit lane, and swallowing the error would also hide a genuinely missing table in prod —
    which would silently drop the evidence a reviewer needs, with no signal at all.
    """
    try:
        from sqlalchemy import inspect as sa_inspect

        return sa_inspect(session.get_bind()).has_table("supplier_accreditations")
    except Exception:  # noqa: BLE001 — an uninspectable bind (a mock) simply has no table
        return False


def list_pending_capabilities(session: Session, *, limit: int = 200) -> List[Dict[str, Any]]:
    """Cross-supplier queue of capabilities awaiting a vetting decision.
    Returns the oldest-first flat rows the admin vetting queue renders."""
    rows = (
        session.query(SupplierServiceCapability, Supplier)
        .join(Supplier, Supplier.id == SupplierServiceCapability.supplier_id)
        .filter(SupplierServiceCapability.platform_vetting_status == "pending")
        .order_by(SupplierServiceCapability.created_at.asc())
        .limit(limit)
        .all()
    )
    # Accreditation, for the registry-harvested suppliers (AIQ-1788). Approving one of those
    # without being able to see WHICH register vouched for it is a rubber stamp — and the
    # evidence is the only thing separating a harvested candidate from a scrape. One extra
    # query rather than N, and an empty dict when the table has no rows for these suppliers.
    accreditations: Dict[str, Dict[str, Any]] = {}
    supplier_ids = [s.id for _, s in rows]
    if supplier_ids and _has_accreditations_table(session):
        from sqlalchemy import bindparam
        from sqlalchemy import text as _text

        # Portable on purpose: the unit lane runs on SQLite, which has neither `DISTINCT ON`
        # nor `= ANY(:ids)`. Ascending order plus dict overwrite gives newest-wins without
        # either. A first attempt used both and broke six unrelated tests.
        stmt = _text(
            "SELECT supplier_id, body, membership_number, valid_until, status, evidence_url "
            "FROM supplier_accreditations WHERE supplier_id IN :ids ORDER BY created_at"
        ).bindparams(bindparam("ids", expanding=True))
        for a in session.execute(stmt, {"ids": supplier_ids}).mappings():
            valid_until = a["valid_until"]
            accreditations[a["supplier_id"]] = {
                "body": a["body"],
                "number": a["membership_number"],
                # date on Postgres, str on SQLite
                "valid_until": (
                    valid_until.isoformat() if hasattr(valid_until, "isoformat")
                    else valid_until
                ),
                "status": a["status"],
                "evidence_url": a["evidence_url"],
            }

    return [
        {
            "supplier_id": s.id,
            "supplier_name": s.name,
            "capability_id": c.id,
            "service_category": c.service_category,
            "country_code": c.country_code,
            "city_name": c.city_name,
            "source": getattr(s, "source", None),
            "source_url": getattr(s, "source_url", None),
            "accreditation": accreditations.get(s.id),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c, s in rows
    ]


def list_supplier_countries(session: Session) -> List[str]:
    """Distinct country codes from supplier capabilities, for admin filter dropdown."""
    from sqlalchemy import distinct
    rows = (
        session.query(distinct(SupplierServiceCapability.country_code))
        .filter(SupplierServiceCapability.country_code.isnot(None))
        .filter(SupplierServiceCapability.country_code != "")
        .order_by(SupplierServiceCapability.country_code)
        .all()
    )
    codes = [r[0] for r in rows if r[0]]
    # Merge with common relocation destinations so dropdown is useful even with empty DB
    common = ["SG", "US", "GB", "DE", "FR", "NL", "AU", "JP", "HK", "NO", "CH"]
    seen = set(codes)
    for c in common:
        if c not in seen:
            codes.append(c)
    return sorted(set(codes))


def get_supplier(session: Session, supplier_id: str) -> Optional[Dict[str, Any]]:
    """Get supplier by id with capabilities and scoring."""
    s = session.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not s:
        return None
    return _supplier_to_dict(s, session, include_capabilities=True, include_scoring=True)


def _build_coverage_summary(caps: List[Any]) -> str:
    """Build coverage summary from capabilities: Global, country codes, city-specific."""
    if not caps:
        return "—"
    has_global = any(getattr(c, "coverage_scope_type", "") == "global" for c in caps)
    countries = sorted({c.country_code for c in caps if getattr(c, "country_code", None)})
    cities = [(c.country_code, c.city_name) for c in caps if getattr(c, "city_name", None)]
    parts = []
    if has_global:
        parts.append("Global")
    if countries:
        parts.append(", ".join(countries))
    if cities:
        city_strs = [f"{cn} ({cc})" for cc, cn in cities if cc and cn]
        if city_strs:
            parts.append("; ".join(city_strs))
    return " | ".join(parts) if parts else "—"


def _supplier_to_dict(
    s: Supplier,
    session: Session,
    *,
    include_capabilities: bool = False,
    include_scoring: bool = False,
    include_list_summary: bool = False,
) -> Dict[str, Any]:
    out = {
        "id": s.id,
        "name": s.name,
        "legal_name": s.legal_name,
        "status": s.status,
        "description": s.description,
        "website": s.website,
        "contact_email": s.contact_email,
        "contact_phone": s.contact_phone,
        "languages_supported": _parse_json_array(s.languages_supported),
        "verified": s.verified,
        "vendor_id": s.vendor_id,
        "source": getattr(s, "source", None),
        "source_url": getattr(s, "source_url", None),
        "source_reference": getattr(s, "source_reference", None),
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }
    if include_list_summary or include_capabilities:
        caps = session.query(SupplierServiceCapability).filter(
            SupplierServiceCapability.supplier_id == s.id
        ).all()
        if include_list_summary:
            out["service_categories"] = sorted({c.service_category for c in caps})
            out["coverage_summary"] = _build_coverage_summary(caps)
        if include_capabilities:
            out["capabilities"] = [
                {
                    "id": c.id,
                    "service_category": c.service_category,
                    "coverage_scope_type": c.coverage_scope_type,
                    "country_code": c.country_code,
                    "city_name": c.city_name,
                    "specialization_tags": _parse_json_array(c.specialization_tags),
                    "min_budget": float(c.min_budget) if c.min_budget is not None else None,
                    "max_budget": float(c.max_budget) if c.max_budget is not None else None,
                    "family_support": c.family_support,
                    "corporate_clients": c.corporate_clients,
                    "remote_support": c.remote_support,
                    "notes": c.notes,
                    "platform_vetting_status": getattr(c, "platform_vetting_status", None),
                    "vetted_by": getattr(c, "vetted_by", None),
                    "vetted_at": c.vetted_at.isoformat() if getattr(c, "vetted_at", None) else None,
                    "vetting_notes": getattr(c, "vetting_notes", None),
                }
                for c in caps
            ]
    if include_scoring:
        meta = session.query(SupplierScoringMetadata).filter(
            SupplierScoringMetadata.supplier_id == s.id
        ).first()
        if meta:
            out["scoring"] = {
                "average_rating": float(meta.average_rating) if meta.average_rating else None,
                "review_count": meta.review_count,
                "response_sla_hours": meta.response_sla_hours,
                "preferred_partner": meta.preferred_partner,
                "premium_partner": meta.premium_partner,
                "last_verified_at": meta.last_verified_at.isoformat() if meta.last_verified_at else None,
                "admin_score": float(meta.admin_score) if getattr(meta, "admin_score", None) is not None else None,
                "manual_priority": int(meta.manual_priority) if getattr(meta, "manual_priority", None) is not None else None,
            }
        else:
            out["scoring"] = None
    return out


def search_by_service_destination(
    session: Session,
    service_category: str,
    destination_city: Optional[str] = None,
    destination_country: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Find suppliers that can serve a given service + destination.
    Used by recommendation engine to load registry-backed items.
    """
    q = (
        session.query(Supplier)
        .join(SupplierServiceCapability, Supplier.id == SupplierServiceCapability.supplier_id)
        .filter(Supplier.status == "active")
        .filter(SupplierServiceCapability.service_category == service_category)
        # GAP 3: employees must never see an unvetted offering — only surface
        # capabilities an admin has approved.
        .filter(SupplierServiceCapability.platform_vetting_status == "approved")
    )
    # Coverage: supplier must serve the destination country (global or country match).
    # When destination_city is set, also allow city-level capability in that country.
    if destination_country:
        country_upper = destination_country.upper()[:2]
        q = q.filter(
            (SupplierServiceCapability.coverage_scope_type == "global")
            | (SupplierServiceCapability.country_code == country_upper)
        )
    if destination_city:
        if destination_country:
            country_upper = destination_country.upper()[:2]
            q = q.filter(
                (SupplierServiceCapability.coverage_scope_type == "global")
                | (SupplierServiceCapability.city_name == destination_city)
                | (SupplierServiceCapability.country_code == country_upper)
            )
        else:
            q = q.filter(
                (SupplierServiceCapability.coverage_scope_type == "global")
                | (SupplierServiceCapability.city_name == destination_city)
            )
    q = q.distinct().order_by(Supplier.name).limit(limit)
    rows = q.all()
    result = []
    for s in rows:
        meta = session.query(SupplierScoringMetadata).filter(
            SupplierScoringMetadata.supplier_id == s.id
        ).first()
        item = _supplier_to_recommendation_item(s, meta, destination_city or "")
        # Surface the matched capability's specialization tags so category plugins can
        # read sub-types (e.g. housing_agencies temporary/permanent). Harmless for other
        # categories, which ignore the field.
        cap = (
            session.query(SupplierServiceCapability)
            .filter(
                SupplierServiceCapability.supplier_id == s.id,
                SupplierServiceCapability.service_category == service_category,
            )
            .first()
        )
        item["specialization_tags"] = _parse_json_array(cap.specialization_tags) if cap else []
        result.append(item)

    # Attach real per-agency neighbourhood coverage (supplier_service_area_coverage) so
    # category plugins can boost by served areas from the curated table rather than the
    # `area:*` tag heuristic. Best-effort: one batched query; if the table is absent
    # (pre-migration / SQLite) the plugins fall back to the specialization_tags.
    if result:
        try:
            from sqlalchemy import bindparam as _bindparam, text as _text
            ids = [str(it.get("item_id")) for it in result if it.get("item_id")]
            cov_rows = session.execute(
                _text(
                    "SELECT supplier_id, area_id FROM supplier_service_area_coverage "
                    "WHERE service_category = :cat AND supplier_id IN :ids"
                ).bindparams(_bindparam("ids", expanding=True)),
                {"cat": service_category, "ids": ids},
            ).fetchall()
            by_supplier: Dict[str, List[str]] = {}
            for sup_id, area_id in cov_rows:
                by_supplier.setdefault(str(sup_id), []).append(str(area_id))
            for it in result:
                it["served_area_ids"] = by_supplier.get(str(it.get("item_id")), [])
        except Exception:
            pass
    return result


def _supplier_to_recommendation_item(
    s: Supplier,
    meta: Optional[SupplierScoringMetadata],
    city_hint: str,
) -> Dict[str, Any]:
    """Convert supplier + metadata to recommendation item shape (plugin-compatible)."""
    raw_rating = float(meta.average_rating) if meta and meta.average_rating is not None else 4.0
    rating = max(0.0, min(5.0, raw_rating))  # clamp 0-5 to avoid UI crash (Invalid count value)
    review_count = int(meta.review_count) if meta and meta.review_count is not None else 0
    review_count = max(0, review_count)
    preferred_partner = bool(meta.preferred_partner) if meta else False
    admin_score = float(meta.admin_score) if meta and getattr(meta, "admin_score", None) is not None else None
    manual_priority = int(meta.manual_priority) if meta and getattr(meta, "manual_priority", None) is not None else None
    out: Dict[str, Any] = {
        "item_id": s.id,
        "name": s.name,
        "city": city_hint,
        "rating": rating,
        "rating_count": review_count,
        "availability_level": "high",
        "confidence": 85,
        "_source": "supplier_registry",
        "_preferred_partner": preferred_partner,
    }
    if admin_score is not None:
        out["_admin_score"] = max(0.0, min(100.0, admin_score))
    if manual_priority is not None:
        out["_manual_priority"] = manual_priority
    return out


def create_supplier(session: Session, data: Dict[str, Any]) -> Dict[str, Any]:
    """Create supplier with optional capabilities and scoring. Use data['id'] for explicit id (e.g. when seeding from recommendation datasets).

    Raises DuplicateSupplierError if the name already exists (case/whitespace-insensitive).
    """
    ok, err = validate_supplier_create(data)
    if not ok:
        raise ValueError(err or "Validation failed")

    # [AIQ-1511] The registry is keyed by id, but a supplier is identified by NAME. An
    # explicit id (used when seeding from the recommendation datasets) is exactly how the
    # duplicate rows got in: the same ten movers were inserted once with uuid4 ids and once
    # with the dataset's 'm-N' ids. Reject the name up-front so the caller gets a 409 rather
    # than a raw unique_violation from uq_suppliers_name_ci (migration 20260913000000).
    name = (data.get("name") or "").strip()
    existing = (
        session.query(Supplier.id)
        .filter(func.lower(func.trim(Supplier.name)) == name.lower())
        .first()
    )
    if existing:
        raise DuplicateSupplierError(
            f"A supplier named '{name}' already exists (id={existing[0]})."
        )

    sid = (data.get("id") or "").strip() or str(uuid.uuid4())
    s = Supplier(
        id=sid,
        name=data["name"],
        legal_name=data.get("legal_name"),
        status=data.get("status", "active"),
        description=data.get("description"),
        website=data.get("website"),
        contact_email=data.get("contact_email"),
        contact_phone=data.get("contact_phone"),
        languages_supported=_serialize_json_array(data.get("languages_supported") or []),
        verified=data.get("verified", False),
        vendor_id=data.get("vendor_id"),
        source=data.get("source", "admin_manual"),
        source_url=data.get("source_url"),
        source_reference=data.get("source_reference"),
    )
    session.add(s)
    caps = data.get("capabilities", [])
    for c in caps:
        cap_id = str(uuid.uuid4())
        cap = SupplierServiceCapability(
            id=cap_id,
            supplier_id=sid,
            service_category=c.get("service_category", "general"),
            coverage_scope_type=c.get("coverage_scope_type", "country"),
            # Normalised like add_capability / update_capability already do — this
            # path wrote it verbatim, which is how ' no ' / 'Norway' could be stored.
            country_code=normalize_country_code(c.get("country_code")),
            city_name=c.get("city_name"),
            specialization_tags=_serialize_json_array(c.get("specialization_tags") or []),
            min_budget=c.get("min_budget"),
            max_budget=c.get("max_budget"),
            family_support=c.get("family_support", False),
            corporate_clients=c.get("corporate_clients", False),
            remote_support=c.get("remote_support", False),
            notes=c.get("notes"),
            platform_vetting_status=c.get("platform_vetting_status", "pending"),
        )
        session.add(cap)
    scoring = data.get("scoring")
    if scoring or True:
        meta = SupplierScoringMetadata(
            supplier_id=sid,
            average_rating=scoring.get("average_rating") if scoring else None,
            review_count=scoring.get("review_count", 0) if scoring else 0,
            response_sla_hours=scoring.get("response_sla_hours") if scoring else None,
            preferred_partner=scoring.get("preferred_partner", False) if scoring else False,
            premium_partner=scoring.get("premium_partner", False) if scoring else False,
            admin_score=scoring.get("admin_score") if scoring else None,
            manual_priority=scoring.get("manual_priority") if scoring else None,
        )
        session.add(meta)
    session.commit()
    session.refresh(s)
    return get_supplier(session, sid) or _supplier_to_dict(s, session, include_capabilities=True, include_scoring=True)


def update_supplier(session: Session, supplier_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update supplier fields. Returns updated supplier or None if not found."""
    ok, err = validate_supplier_update(data)
    if not ok:
        raise ValueError(err or "Validation failed")
    s = session.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not s:
        return None
    if "name" in data:
        s.name = str(data["name"]).strip()
    if "legal_name" in data:
        s.legal_name = str(data["legal_name"]).strip() or None
    if "status" in data:
        s.status = str(data["status"]).lower()
    if "description" in data:
        s.description = str(data["description"]).strip() or None if data["description"] is not None else s.description
    if "website" in data:
        s.website = str(data["website"]).strip() or None if data["website"] is not None else s.website
    if "contact_email" in data:
        s.contact_email = str(data["contact_email"]).strip() or None if data["contact_email"] is not None else s.contact_email
    if "contact_phone" in data:
        s.contact_phone = str(data["contact_phone"]).strip() or None if data["contact_phone"] is not None else s.contact_phone
    if "languages_supported" in data:
        s.languages_supported = _serialize_json_array(data.get("languages_supported") or [])
    if "verified" in data:
        s.verified = bool(data["verified"])
    if "vendor_id" in data:
        s.vendor_id = str(data["vendor_id"]).strip() or None if data["vendor_id"] else s.vendor_id
    session.commit()
    session.refresh(s)
    updated = get_supplier(session, supplier_id)
    if updated:
        ok, err = validate_active_supplier_requirements(updated)
        if not ok:
            log.warning("Supplier %s updated but active requirements not met: %s", supplier_id, err)
    return updated


def set_supplier_status(session: Session, supplier_id: str, status: str) -> Optional[Dict[str, Any]]:
    """Activate or deactivate supplier. status: active, inactive, draft."""
    s = session.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not s:
        return None
    status = status.lower()
    if status not in ("active", "inactive", "draft"):
        raise ValueError(f"status must be active, inactive, or draft; got {status}")
    s.status = status
    session.commit()
    session.refresh(s)
    return get_supplier(session, supplier_id)


def add_capability(
    session: Session,
    supplier_id: str,
    data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Add service capability. Validates and checks for duplicates."""
    s = session.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not s:
        return None
    ok, err = validate_capability(data, exclude_id=True)
    if not ok:
        raise ValueError(err or "Invalid capability")
    existing = [
        {
            "id": c.id,
            "service_category": c.service_category,
            "coverage_scope_type": c.coverage_scope_type,
            "country_code": c.country_code,
            "city_name": c.city_name,
        }
        for c in session.query(SupplierServiceCapability).filter(
            SupplierServiceCapability.supplier_id == supplier_id
        ).all()
    ]
    if check_duplicate_capability(existing, data):
        raise ValueError("Duplicate capability: same service, coverage, country, city already exists")
    cap_id = str(uuid.uuid4())
    country_code = (data.get("country_code") or "").strip().upper()[:2] or None
    city_name = (data.get("city_name") or "").strip() or None
    cap = SupplierServiceCapability(
        id=cap_id,
        supplier_id=supplier_id,
        service_category=(data.get("service_category") or "general").lower(),
        coverage_scope_type=(data.get("coverage_scope_type") or "country").lower(),
        country_code=country_code,
        city_name=city_name,
        specialization_tags=_serialize_json_array(data.get("specialization_tags") or []),
        min_budget=data.get("min_budget"),
        max_budget=data.get("max_budget"),
        family_support=data.get("family_support", False),
        corporate_clients=data.get("corporate_clients", False),
        remote_support=data.get("remote_support", False),
        notes=(data.get("notes") or "").strip() or None,
        platform_vetting_status=(data.get("platform_vetting_status") or "pending"),
    )
    session.add(cap)
    session.commit()
    return get_supplier(session, supplier_id)


def _ensure_catalog_master_for_capability(cap: Any, supplier_name: Optional[str]) -> None:
    """AIQ-2095: forge the ``service_catalog_items`` master that makes an approved
    supplier reachable by an employee.

    A supplier reaches an employee ONLY through a catalog master — the HR curation
    view, the vendor-proposal seed and the employee recommendations filter all read
    ``service_catalog_items`` (by ``supplier_id`` / ``external_id``), never the
    registry directly. Approving a capability is the moment the supplier becomes
    offerable, so the master is created here rather than at raw promotion (a pending
    supplier must not appear in HR curation, and ``list_items`` does not gate on
    vetting status).

    Country comes from the CAPABILITY's ``country_code``, never
    ``suppliers.based_in_country``: an AGS-France-style supplier based in FR but
    serving DE and NO must get a DE master and a NO master — one per capability —
    not an FR one. Idempotent via a deterministic ``external_id``. Best-effort: a
    catalog failure must never roll back a completed approval (the coverage guard /
    backfill catches any straggler)."""
    from . import service_catalog

    category = (getattr(cap, "service_category", None) or "").strip().lower()
    if not category:
        return
    country = (getattr(cap, "country_code", None) or "").strip().upper()[:2] or None
    city = getattr(cap, "city_name", None) or None
    supplier_id = str(getattr(cap, "supplier_id", "") or "")
    if not supplier_id:
        return
    # Dedupe is on (category, external_id); key by supplier+capability country so
    # re-approving the same capability updates one row instead of duplicating.
    external_id = f"registry:{supplier_id}:{category}:{country or ''}"
    try:
        service_catalog.upsert_item(
            category=category,
            name=(supplier_name or supplier_id),
            attributes={},
            source="registry_promoted",
            city=city,
            country=country,
            external_id=external_id,
            supplier_id=supplier_id,
        )
    except Exception:
        log.exception(
            "AIQ-2095: failed to create catalog master for approved capability "
            "supplier_id=%s category=%s country=%s",
            supplier_id, category, country,
        )


def approve_capability(
    session: Session,
    capability_id: str,
    vetted_by_user_id: Optional[str],
    notes: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Approve a service capability: mark it visible to recommendations and stamp
    the reviewer. Returns the parent supplier dict, or None if the capability is
    not found."""
    cap = (
        session.query(SupplierServiceCapability)
        .filter(SupplierServiceCapability.id == capability_id)
        .first()
    )
    if not cap:
        return None
    cap.platform_vetting_status = "approved"
    cap.vetted_by = vetted_by_user_id
    cap.vetted_at = datetime.now(timezone.utc)
    cap.vetting_notes = (notes or "").strip() or None
    session.commit()
    supplier = get_supplier(session, cap.supplier_id)
    # AIQ-2095: an approved capability is only reachable by an employee once a
    # linked catalog master exists — create it now (best-effort, never fails the
    # approval). Country is taken from the capability, not suppliers.based_in_country.
    _ensure_catalog_master_for_capability(cap, (supplier or {}).get("name"))
    return supplier


def reject_capability(
    session: Session,
    capability_id: str,
    vetted_by_user_id: Optional[str],
    notes: str,
) -> Optional[Dict[str, Any]]:
    """Reject a service capability. Notes are mandatory (raises ValueError if
    blank). Returns the parent supplier dict, or None if not found."""
    if not (notes or "").strip():
        raise ValueError("Rejection notes are required")
    cap = (
        session.query(SupplierServiceCapability)
        .filter(SupplierServiceCapability.id == capability_id)
        .first()
    )
    if not cap:
        return None
    cap.platform_vetting_status = "rejected"
    cap.vetted_by = vetted_by_user_id
    cap.vetted_at = datetime.now(timezone.utc)
    cap.vetting_notes = notes.strip()
    session.commit()
    return get_supplier(session, cap.supplier_id)


def update_capability(
    session: Session,
    supplier_id: str,
    capability_id: str,
    data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Update capability. Validates and checks for duplicates."""
    cap = (
        session.query(SupplierServiceCapability)
        .filter(
            SupplierServiceCapability.supplier_id == supplier_id,
            SupplierServiceCapability.id == capability_id,
        )
        .first()
    )
    if not cap:
        return None
    ok, err = validate_capability(data, exclude_id=True)
    if not ok:
        raise ValueError(err or "Invalid capability")
    existing = [
        {
            "id": c.id,
            "service_category": c.service_category,
            "coverage_scope_type": c.coverage_scope_type,
            "country_code": c.country_code,
            "city_name": c.city_name,
        }
        for c in session.query(SupplierServiceCapability).filter(
            SupplierServiceCapability.supplier_id == supplier_id
        ).all()
    ]
    merged = {
        "service_category": data.get("service_category", cap.service_category),
        "coverage_scope_type": data.get("coverage_scope_type", cap.coverage_scope_type),
        "country_code": data.get("country_code", cap.country_code),
        "city_name": data.get("city_name", cap.city_name),
    }
    if check_duplicate_capability(existing, merged, exclude_cap_id=capability_id):
        raise ValueError("Duplicate capability: same service, coverage, country, city already exists")
    if "service_category" in data:
        cap.service_category = (data["service_category"] or "general").lower()
    if "coverage_scope_type" in data:
        cap.coverage_scope_type = (data["coverage_scope_type"] or "country").lower()
    if "country_code" in data:
        cap.country_code = (data["country_code"] or "").strip().upper()[:2] or None
    if "city_name" in data:
        cap.city_name = (data["city_name"] or "").strip() or None
    if "specialization_tags" in data:
        cap.specialization_tags = _serialize_json_array(data.get("specialization_tags") or [])
    if "min_budget" in data:
        cap.min_budget = data["min_budget"]
    if "max_budget" in data:
        cap.max_budget = data["max_budget"]
    if "family_support" in data:
        cap.family_support = bool(data["family_support"])
    if "corporate_clients" in data:
        cap.corporate_clients = bool(data["corporate_clients"])
    if "remote_support" in data:
        cap.remote_support = bool(data["remote_support"])
    if "notes" in data:
        cap.notes = (data["notes"] or "").strip() or None
    session.commit()
    return get_supplier(session, supplier_id)


def remove_capability(
    session: Session,
    supplier_id: str,
    capability_id: str,
) -> Optional[Dict[str, Any]]:
    """Remove capability."""
    cap = (
        session.query(SupplierServiceCapability)
        .filter(
            SupplierServiceCapability.supplier_id == supplier_id,
            SupplierServiceCapability.id == capability_id,
        )
        .first()
    )
    if not cap:
        return None
    session.delete(cap)
    session.commit()
    return get_supplier(session, supplier_id)


def update_scoring(
    session: Session,
    supplier_id: str,
    data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Update scoring/verification metadata."""
    s = session.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not s:
        return None
    meta = session.query(SupplierScoringMetadata).filter(
        SupplierScoringMetadata.supplier_id == supplier_id
    ).first()
    if not meta:
        meta = SupplierScoringMetadata(supplier_id=supplier_id)
        session.add(meta)
    if "average_rating" in data:
        v = data["average_rating"]
        meta.average_rating = float(v) if v is not None else None
    if "review_count" in data:
        meta.review_count = int(data["review_count"] or 0)
    if "response_sla_hours" in data:
        v = data["response_sla_hours"]
        meta.response_sla_hours = int(v) if v is not None else None
    if "preferred_partner" in data:
        meta.preferred_partner = bool(data["preferred_partner"])
    if "premium_partner" in data:
        meta.premium_partner = bool(data["premium_partner"])
    if "admin_score" in data:
        v = data["admin_score"]
        meta.admin_score = float(v) if v is not None else None
    if "manual_priority" in data:
        v = data["manual_priority"]
        meta.manual_priority = int(v) if v is not None else None
    if "last_verified_at" in data:
        from datetime import datetime, timezone
        v = data["last_verified_at"]
        meta.last_verified_at = v if isinstance(v, datetime) else (datetime.now(timezone.utc) if v else None)
    session.commit()
    return get_supplier(session, supplier_id)
