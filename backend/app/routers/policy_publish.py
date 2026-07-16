"""
[P1-4] HR validation gate — policy publish + version control.

This is the gate that turns a draft policy into the company's live source of
truth. The Notion task brief (AIQ-224) calls out four invariants:

  1. **HR-only** — the action requires `role IN ('hr', 'admin')`.
  2. **14-category completeness** — a version cannot be published until each
     of the 14 canonical `policy_categories` (CAT-01 … CAT-14) has at least
     one `policy_values` row for this version.
  3. **Atomic archive + publish** — the previously published version (if any)
     and the new version must transition in a single transaction. At most
     one row per policy may have status='published' at any time.
  4. **Auditable** — every publish is logged to the canonical
     `public.audit_logs` table (action_type='update', with the semantic
     event name 'policy.published' in new_value_json.event).

Endpoints
─────────
POST /api/policy/publish                 → publish a specific draft version
GET  /api/policy/versions/{company_id}   → full version history for a company
GET  /api/policy/active/{company_id}     → the currently active (published)
                                            version, or null

Version numbering
─────────────────
`policy_versions.version_number` is per-policy and auto-incremented on
publish: max(version_number)+1 over rows for the same `policy_id`. Numbers
are dense and never reused, even when a version is rolled back to archived.

Lives in its own router (mirrors the P2-4 / P1-6 standalone pattern) so it
ships without touching the in-flight `cases.py` refactor.

Tests live in `backend/tests/test_policy_publish.py`.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..auth_deps import get_current_user
from ..services.audit_log_service import insert_audit_log
from ...database import db


router = APIRouter(prefix="/api/policy", tags=["policy-publish"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dialect helper
# ---------------------------------------------------------------------------

def _t(name: str) -> str:
    try:
        dialect_name = db.engine.dialect.name
    except Exception:
        dialect_name = "postgresql"
    return f"public.{name}" if dialect_name == "postgresql" else name


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Auth guard — HR or admin only.
# ---------------------------------------------------------------------------

def _require_hr_or_admin(user: Dict[str, Any]) -> Dict[str, Any]:
    role = (user.get("role") or "").lower()
    if role not in ("hr", "admin"):
        raise HTTPException(status_code=403, detail="HR or admin role required")
    return {
        "id": user.get("id") or user.get("sub"),
        "company_id": user.get("company_id"),
        "role": role,
    }


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class PublishPayload(BaseModel):
    """Body of POST /api/policy/publish."""
    version_id: str = Field(..., description="policy_versions.id to publish")
    effective_date: date = Field(..., description="ISO-8601 YYYY-MM-DD")
    expiry_date: Optional[date] = Field(None, description="Optional sunset date")
    notes: Optional[str] = Field(None, description="HR-visible publish note")


class PolicyVersionDTO(BaseModel):
    id: str
    policy_id: str
    version_number: int
    status: str
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    published_by: Optional[str] = None
    published_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PublishResponse(BaseModel):
    version: PolicyVersionDTO
    archived_version_id: Optional[str] = None
    audit_log_id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXPECTED_CATEGORY_CODES = [f"CAT-{i:02d}" for i in range(1, 15)]


def _load_version(conn: Any, version_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            f"SELECT v.id, v.policy_id, v.version_number, v.status, "
            f"       v.effective_date, v.expiry_date, "
            f"       v.published_by, v.published_at, "
            f"       v.created_at, v.updated_at, "
            f"       p.company_id "
            f"FROM {_t('policy_versions')} v "
            f"JOIN {_t('company_policies')} p ON p.id = v.policy_id "
            f"WHERE v.id = :id"
        ),
        {"id": version_id},
    ).mappings().first()
    return dict(row) if row else None


def _category_codes_covered_by_version(conn: Any, version_id: str) -> List[str]:
    """Return the sorted list of CAT-NN codes that have at least one
    policy_values row for this version. Used to compute "missing categories"."""
    rows = conn.execute(
        text(
            f"SELECT DISTINCT c.code "
            f"FROM {_t('policy_values')} v "
            f"JOIN {_t('policy_categories')} c ON c.id = v.category_id "
            f"WHERE v.version_id = :vid"
        ),
        {"vid": version_id},
    ).fetchall()
    return sorted(r[0] for r in rows)


def _missing_categories(conn: Any, version_id: str) -> List[str]:
    covered = set(_category_codes_covered_by_version(conn, version_id))
    return [code for code in EXPECTED_CATEGORY_CODES if code not in covered]


def _next_version_number(conn: Any, policy_id: str) -> int:
    """Compute the next published version number.

    Drafts do NOT count toward numbering — only versions that have ever
    reached `published` (currently published or later archived). So:
      first publish  → 1
      second publish → 2
      …
    """
    row = conn.execute(
        text(
            f"SELECT COALESCE(MAX(version_number), 0) AS max_v "
            f"FROM {_t('policy_versions')} "
            f"WHERE policy_id = :pid "
            f"  AND status IN ('published', 'archived')"
        ),
        {"pid": policy_id},
    ).mappings().first()
    return int((row or {}).get("max_v") or 0) + 1


def _archive_current_published(conn: Any, policy_id: str,
                               exclude_version_id: str) -> Optional[str]:
    """Set the currently-published version (if any, and not the one we're
    about to publish) to status='archived'. Return its id or None."""
    row = conn.execute(
        text(
            f"SELECT id FROM {_t('policy_versions')} "
            f"WHERE policy_id = :pid AND status = 'published' "
            f"AND id != :exc "
            f"LIMIT 1"
        ),
        {"pid": policy_id, "exc": exclude_version_id},
    ).mappings().first()
    if not row:
        return None
    prev_id = str(row["id"])
    conn.execute(
        text(
            f"UPDATE {_t('policy_versions')} "
            f"SET status = 'archived', updated_at = :now "
            f"WHERE id = :id"
        ),
        {"id": prev_id, "now": _now_iso()},
    )
    return prev_id


def _publish_version_row(
    conn: Any,
    *,
    version_id: str,
    new_version_number: int,
    effective_date: date,
    expiry_date: Optional[date],
    published_by: str,
) -> None:
    conn.execute(
        text(
            f"UPDATE {_t('policy_versions')} "
            f"SET status = 'published', "
            f"    version_number = :vnum, "
            f"    effective_date = :eff, "
            f"    expiry_date = :exp, "
            f"    published_by = :pby, "
            f"    published_at = :pat, "
            f"    updated_at = :pat "
            f"WHERE id = :id"
        ),
        {
            "id": version_id,
            "vnum": new_version_number,
            "eff": str(effective_date),
            "exp": str(expiry_date) if expiry_date else None,
            "pby": published_by,
            "pat": _now_iso(),
        },
    )


def _write_audit_log(
    conn: Any,
    *,
    actor_id: str,
    company_id: str,
    policy_id: str,
    version_id: str,
    version_number: int,
    archived_version_id: Optional[str],
    notes: Optional[str],
) -> str:
    """Append the publish event to the canonical public.audit_logs table.
    Returns the new row id.

    Consolidated onto audit_logs (AIQ-942) so policy-publish events land in the
    same table downstream queries and admin tooling already read — previously
    they went to the orphaned legacy `audit_log` and were invisible there.
    The audit_logs.action_type CHECK only permits insert/update/delete, so the
    semantic event name ('policy.published') is carried in new_value_json.event.
    Audit-write failures are logged but never raised: a missing audit row must
    not roll back a successful publish (re-publishing is destructive).
    """
    new_id = str(uuid.uuid4())
    try:
        new_id = insert_audit_log(
            conn,
            entity_type="policy_version",
            entity_id=version_id,
            action_type="update",
            new_value={
                "event": "policy.published",
                "company_id": company_id,
                "policy_id": policy_id,
                "version_id": version_id,
                "version_number": version_number,
                "archived_version_id": archived_version_id,
                "notes": notes,
            },
            actor_type="human",
            actor_id=actor_id,
        )
    except Exception:
        logger.warning(
            "policy_publish: audit_logs write failed version_id=%s", version_id,
            exc_info=True,
        )
    return new_id


def _row_to_dto(row: Dict[str, Any]) -> PolicyVersionDTO:
    return PolicyVersionDTO(
        id=str(row["id"]),
        policy_id=str(row["policy_id"]),
        version_number=int(row.get("version_number") or 1),
        status=str(row.get("status") or "draft"),
        effective_date=str(row["effective_date"]) if row.get("effective_date") else None,
        expiry_date=str(row["expiry_date"]) if row.get("expiry_date") else None,
        published_by=str(row["published_by"]) if row.get("published_by") else None,
        published_at=str(row["published_at"]) if row.get("published_at") else None,
        created_at=str(row["created_at"]) if row.get("created_at") else None,
        updated_at=str(row["updated_at"]) if row.get("updated_at") else None,
    )


# ---------------------------------------------------------------------------
# Endpoint: POST /api/policy/publish
# ---------------------------------------------------------------------------

@router.post("/publish", response_model=PublishResponse)
def publish_policy_version(
    payload: PublishPayload,
    user: Dict[str, Any] = Depends(get_current_user),
) -> PublishResponse:
    """Promote a draft `policy_versions` row to status='published'."""
    actor = _require_hr_or_admin(user)

    try:
        with db.engine.begin() as conn:
            version = _load_version(conn, payload.version_id)
            if not version:
                raise HTTPException(status_code=404, detail="Version not found")

            policy_id = str(version["policy_id"])
            company_id = str(version["company_id"])

            # Cross-company guard: HR can only publish within their company.
            if actor["role"] != "admin":
                if not actor["company_id"] or str(actor["company_id"]) != company_id:
                    raise HTTPException(
                        status_code=403,
                        detail="Cross-company publish denied",
                    )

            # Idempotency guard: already published.
            if version.get("status") == "published":
                raise HTTPException(
                    status_code=409,
                    detail="Version is already published",
                )

            # 14-category completeness check.
            missing = _missing_categories(conn, payload.version_id)
            if missing:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "message": "Cannot publish: missing required categories",
                        "missing_categories": missing,
                    },
                )

            new_number = _next_version_number(conn, policy_id)
            archived_id = _archive_current_published(
                conn, policy_id, payload.version_id
            )
            _publish_version_row(
                conn,
                version_id=payload.version_id,
                new_version_number=new_number,
                effective_date=payload.effective_date,
                expiry_date=payload.expiry_date,
                published_by=actor["id"],
            )
            audit_id = _write_audit_log(
                conn,
                actor_id=actor["id"],
                company_id=company_id,
                policy_id=policy_id,
                version_id=payload.version_id,
                version_number=new_number,
                archived_version_id=archived_id,
                notes=payload.notes,
            )

            refreshed = _load_version(conn, payload.version_id)
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "publish_policy_version: failed version_id=%s", payload.version_id
        )
        raise HTTPException(status_code=500, detail="Failed to publish version")

    try:
        from ..posthog_client import get_posthog_client
        ph = get_posthog_client()
        if ph:
            ph.capture(
                distinct_id=actor["id"],
                event="policy_published",
                properties={
                    "version_number": new_number,
                    "has_expiry": payload.expiry_date is not None,
                    "archived_previous": archived_id is not None,
                },
            )
    except Exception:
        pass
    return PublishResponse(
        version=_row_to_dto(refreshed or {"id": payload.version_id, "policy_id": ""}),
        archived_version_id=archived_id,
        audit_log_id=audit_id,
    )


# ---------------------------------------------------------------------------
# Endpoint: GET /api/policy/versions/{company_id}
# ---------------------------------------------------------------------------

@router.get("/versions/{company_id}", response_model=List[PolicyVersionDTO])
def list_company_versions(
    company_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[PolicyVersionDTO]:
    """Full version history (newest first) for every policy in this company."""
    actor = _require_hr_or_admin(user)
    if actor["role"] != "admin":
        if not actor["company_id"] or str(actor["company_id"]) != str(company_id):
            raise HTTPException(status_code=403, detail="Cross-company access denied")

    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT v.id, v.policy_id, v.version_number, v.status, "
                    f"       v.effective_date, v.expiry_date, "
                    f"       v.published_by, v.published_at, "
                    f"       v.created_at, v.updated_at "
                    f"FROM {_t('policy_versions')} v "
                    f"JOIN {_t('company_policies')} p ON p.id = v.policy_id "
                    f"WHERE p.company_id = :cid "
                    f"ORDER BY v.created_at DESC"
                ),
                {"cid": company_id},
            ).mappings().fetchall()
    except Exception:
        logger.exception("list_company_versions failed company_id=%s", company_id)
        raise HTTPException(status_code=500, detail="Failed to load version history")

    return [_row_to_dto(dict(r)) for r in rows]


# ---------------------------------------------------------------------------
# Endpoint: GET /api/policy/active/{company_id}
# ---------------------------------------------------------------------------

@router.get("/active/{company_id}", response_model=Optional[PolicyVersionDTO])
def get_active_version(
    company_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Optional[PolicyVersionDTO]:
    """Return the currently-published version for the company, or None."""
    actor = _require_hr_or_admin(user)
    if actor["role"] != "admin":
        if not actor["company_id"] or str(actor["company_id"]) != str(company_id):
            raise HTTPException(status_code=403, detail="Cross-company access denied")

    try:
        with db.engine.connect() as conn:
            row = conn.execute(
                text(
                    f"SELECT v.id, v.policy_id, v.version_number, v.status, "
                    f"       v.effective_date, v.expiry_date, "
                    f"       v.published_by, v.published_at, "
                    f"       v.created_at, v.updated_at "
                    f"FROM {_t('policy_versions')} v "
                    f"JOIN {_t('company_policies')} p ON p.id = v.policy_id "
                    f"WHERE p.company_id = :cid AND v.status = 'published' "
                    f"ORDER BY v.published_at DESC NULLS LAST "
                    f"LIMIT 1"
                ),
                {"cid": company_id},
            ).mappings().first()
    except Exception:
        logger.exception("get_active_version failed company_id=%s", company_id)
        raise HTTPException(status_code=500, detail="Failed to load active version")

    if not row:
        return None
    return _row_to_dto(dict(row))
