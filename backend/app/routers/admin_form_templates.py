"""
[P1-2 / Phase 2A] Admin Form Templates API.

CRUD over public.form_templates (created in P1-1). Powers the admin UI at
/admin/form-templates where ReloPass ops maintain the catalog of official
government forms.

Versioning model:
  - (code, version) is UNIQUE in the DB.
  - PATCH with the same version → updates the row in place.
  - PATCH with a different version → INSERTS a new row preserving the old one
    (so historical case_forms keep pointing at the old template_id).

Scope of Phase 2A (this file):
  - GET    /api/admin/form-templates             list (filter by country/category/code)
  - GET    /api/admin/form-templates/{id}        single
  - POST   /api/admin/form-templates             create
  - PATCH  /api/admin/form-templates/{id}        update (in-place or new-version)

Deferred to Phase 2B (separate queue task):
  - PDF upload to Supabase Storage
  - Fields editor (drag-and-drop FieldDefinition list)
  - Trigger rules visual editor
  - Soft-delete / deprecate

Portability note:
  SQL paths use the helpers `_table()`, `_id_select()`, and `_jsonb_expr()`
  to stay compatible with both Postgres (prod) and SQLite (test harness).
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..auth_deps import require_admin
from ...database import db

router = APIRouter(prefix="/form-templates", tags=["admin-form-templates"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class FormTemplateCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=200)
    country: str = Field(..., min_length=2, max_length=2)
    authority_code: Optional[str] = Field(None, max_length=64)
    authority_name: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = Field(None, max_length=64)
    original_pdf_url: Optional[str] = Field(None, max_length=1024)
    version: str = Field("1.0.0", min_length=1, max_length=32)
    # FieldDefinition shape will be locked down in P1-2B; accept any list for now.
    fields: List[Dict[str, Any]] = Field(default_factory=list)
    # TriggerRule shape will be locked down in P1-3; accept any object for now.
    trigger_rules: Dict[str, Any] = Field(default_factory=dict)


class FormTemplateUpdate(BaseModel):
    """
    PATCH body. All fields optional. If `version` is supplied and differs from
    the current row's version, a NEW row is inserted (the old row is preserved
    so historical case_forms keep working).
    """

    code: Optional[str] = Field(None, min_length=1, max_length=64)
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    country: Optional[str] = Field(None, min_length=2, max_length=2)
    authority_code: Optional[str] = Field(None, max_length=64)
    authority_name: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = Field(None, max_length=64)
    original_pdf_url: Optional[str] = Field(None, max_length=1024)
    version: Optional[str] = Field(None, min_length=1, max_length=32)
    fields: Optional[List[Dict[str, Any]]] = None
    trigger_rules: Optional[Dict[str, Any]] = None


class FormTemplateRead(BaseModel):
    id: str
    code: str
    name: str
    country: str
    authority_code: Optional[str]
    authority_name: Optional[str]
    category: Optional[str]
    original_pdf_url: Optional[str]
    version: str
    fields: List[Dict[str, Any]]
    trigger_rules: Dict[str, Any]
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Dialect helpers — keep SQL portable between Postgres prod and SQLite tests
# ---------------------------------------------------------------------------


def _dialect() -> str:
    try:
        return db.engine.dialect.name
    except Exception:
        return "postgresql"


def _table() -> str:
    """Qualified table name. Postgres uses `public.form_templates`; SQLite has no schemas."""
    return "public.form_templates" if _dialect() == "postgresql" else "form_templates"


def _qual(name: str) -> str:
    """Schema-qualify a table name for Postgres; bare name for SQLite."""
    return f"public.{name}" if _dialect() == "postgresql" else name


def _jsonb_expr(param: str) -> str:
    """`CAST(:param AS jsonb)` on Postgres; bare `:param` on SQLite (column is TEXT)."""
    return f"CAST(:{param} AS jsonb)" if _dialect() == "postgresql" else f":{param}"


def _id_select() -> str:
    """`id::text AS id` on Postgres so uuid serializes; bare `id` on SQLite."""
    return "id::text AS id" if _dialect() == "postgresql" else "id"


def _select_cols() -> str:
    return (
        f"{_id_select()}, code, name, country, authority_code, authority_name, "
        "category, original_pdf_url, version, fields, trigger_rules, "
        "created_at, updated_at"
    )


# ---------------------------------------------------------------------------
# Row helpers
# ---------------------------------------------------------------------------


def _row_to_dict(row: Any) -> Dict[str, Any]:
    """Normalize a SQLAlchemy mapping row into a JSON-safe dict."""
    d = dict(row)
    for k, v in list(d.items()):
        if v is None:
            continue
        if hasattr(v, "isoformat"):
            try:
                d[k] = v.isoformat()
                continue
            except Exception:
                d[k] = str(v)
                continue
        if isinstance(v, uuid.UUID):
            d[k] = str(v)
            continue
        # jsonb columns arrive as dict/list from Postgres; as str from SQLite.
        if k in ("fields", "trigger_rules") and isinstance(v, str):
            try:
                d[k] = json.loads(v)
            except (ValueError, TypeError):
                d[k] = [] if k == "fields" else {}
    # Defensive defaults
    if d.get("fields") is None:
        d["fields"] = []
    if d.get("trigger_rules") is None:
        d["trigger_rules"] = {}
    return d


def _json_dumps(value: Any) -> str:
    """JSON-encode a Python value for jsonb / text columns."""
    return json.dumps(value)


def _merge(current: Dict[str, Any], patch: FormTemplateUpdate) -> Dict[str, Any]:
    """Overlay a FormTemplateUpdate onto the current row's dict representation."""
    out = dict(current)
    for field_name, value in patch.model_dump(exclude_unset=True).items():
        out[field_name] = value
    return out


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=List[FormTemplateRead])
def list_form_templates(
    country: Optional[str] = Query(None, min_length=2, max_length=2),
    category: Optional[str] = Query(None, max_length=64),
    code: Optional[str] = Query(None, max_length=64),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: Dict[str, Any] = Depends(require_admin),
) -> List[Dict[str, Any]]:
    """List form templates, optionally filtered by country / category / code."""
    where: List[str] = []
    params: Dict[str, Any] = {"limit": limit, "offset": offset}
    if country:
        where.append("country = :country")
        params["country"] = country.upper()
    if category:
        where.append("category = :category")
        params["category"] = category
    if code:
        where.append("code = :code")
        params["code"] = code

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    sql = (
        f"SELECT {_select_cols()} FROM {_table()}"
        f"{where_sql}"
        " ORDER BY code, version, created_at DESC"
        " LIMIT :limit OFFSET :offset"
    )

    with db.engine.begin() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# [P4-6] Admin accuracy report — per-field AI override rates
# IMPORTANT: This route must be declared before /{template_id} or FastAPI
# will route GET /accuracy-report as get_form_template with template_id="accuracy-report"
# ---------------------------------------------------------------------------

class FieldAccuracyItem(BaseModel):
    """One row in the accuracy report: a (form_code, field_id) pair with stats."""
    form_template_id: str
    form_code: str
    field_id: str
    total_ai_fills: int
    overrides: int
    override_rate_pct: int          # 0–100
    accuracy_flag: Optional[str]    # 'low_accuracy' if override_rate_pct > 20, else None
    # Deep-link for admin to navigate to the FieldDefinition editor
    field_edit_url: str


@router.get("/accuracy-report", response_model=List[FieldAccuracyItem])
def get_accuracy_report(
    user: Dict[str, Any] = Depends(require_admin),
) -> List[FieldAccuracyItem]:
    """
    [P4-6] Returns per-(form_template, field) override statistics.

    Rows are ordered by override_rate_pct DESC so the worst-performing
    fields appear first. Fields with override_rate_pct > 20 are flagged
    as 'low_accuracy'; the field_edit_url links the admin directly to the
    FieldDefinition editor.
    """
    # Dialect-aware ROUND expression
    if _dialect() == "postgresql":
        rate_expr = (
            "ROUND(COUNT(fvo.id) * 100.0 / NULLIF(COUNT(fv.id), 0))::int"
        )
    else:
        rate_expr = (
            "CAST(ROUND(COUNT(fvo.id) * 100.0 / NULLIF(COUNT(fv.id), 0)) AS INTEGER)"
        )

    sql = f"""
        SELECT
          ft.id        AS form_template_id,
          ft.code      AS form_code,
          fv.field_id,
          COUNT(fv.id) AS total_ai_fills,
          COUNT(fvo.id) AS overrides,
          COALESCE({rate_expr}, 0) AS override_rate_pct
        FROM {_qual('case_form_field_values')} fv
        JOIN {_qual('case_forms')} cf  ON cf.id = fv.case_form_id
        JOIN {_table()} ft             ON ft.id = cf.form_template_id
        LEFT JOIN {_qual('field_value_overrides')} fvo
          ON fvo.case_form_id = fv.case_form_id
         AND fvo.field_id     = fv.field_id
        WHERE fv.filled_by = 'ai'
        GROUP BY ft.id, ft.code, fv.field_id
        ORDER BY override_rate_pct DESC
    """

    try:
        with db.engine.connect() as conn:
            rows = conn.execute(text(sql)).mappings().all()
    except Exception:
        logger.exception("accuracy_report: query failed")
        raise HTTPException(status_code=500, detail="Failed to generate accuracy report")

    items: List[FieldAccuracyItem] = []
    for row in rows:
        tmpl_id  = str(row["form_template_id"])
        field_id = str(row["field_id"])
        rate     = int(row["override_rate_pct"] or 0)
        items.append(FieldAccuracyItem(
            form_template_id=tmpl_id,
            form_code=str(row["form_code"]),
            field_id=field_id,
            total_ai_fills=int(row["total_ai_fills"] or 0),
            overrides=int(row["overrides"] or 0),
            override_rate_pct=rate,
            accuracy_flag="low_accuracy" if rate > 20 else None,
            field_edit_url=f"/admin/form-templates/{tmpl_id}?field={field_id}",
        ))
    return items


@router.get("/{template_id}", response_model=FormTemplateRead)
def get_form_template(
    template_id: str,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Get a single form template by id."""
    with db.engine.begin() as conn:
        row = conn.execute(
            text(f"SELECT {_select_cols()} FROM {_table()} WHERE id = :id"),
            {"id": template_id},
        ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Form template not found")
    return _row_to_dict(row)


@router.post("", response_model=FormTemplateRead, status_code=201)
def create_form_template(
    body: FormTemplateCreate,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """
    Create a new form template. (code, version) must be unique — duplicates 409.

    `created_at` / `updated_at` are intentionally omitted from the INSERT:
    Postgres column defaults (`DEFAULT now()`) handle them. Passing a Python
    isoformat() string fails with type mismatch on Postgres timestamptz columns.
    """
    new_id = str(uuid.uuid4())

    with db.engine.begin() as conn:
        existing = conn.execute(
            text(
                f"SELECT 1 FROM {_table()} "
                "WHERE code = :code AND version = :version LIMIT 1"
            ),
            {"code": body.code, "version": body.version},
        ).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Form template with code={body.code} version={body.version} already exists"
                ),
            )

        fields_expr = _jsonb_expr("fields")
        rules_expr = _jsonb_expr("trigger_rules")
        conn.execute(
            text(
                f"""
                INSERT INTO {_table()} (
                    id, code, name, country, authority_code, authority_name,
                    category, original_pdf_url, version, fields, trigger_rules
                ) VALUES (
                    :id, :code, :name, :country, :authority_code, :authority_name,
                    :category, :original_pdf_url, :version,
                    {fields_expr}, {rules_expr}
                )
                """
            ),
            {
                "id": new_id,
                "code": body.code,
                "name": body.name,
                "country": body.country.upper(),
                "authority_code": body.authority_code,
                "authority_name": body.authority_name,
                "category": body.category,
                "original_pdf_url": body.original_pdf_url,
                "version": body.version,
                "fields": _json_dumps(body.fields),
                "trigger_rules": _json_dumps(body.trigger_rules),
            },
        )
        row = conn.execute(
            text(f"SELECT {_select_cols()} FROM {_table()} WHERE id = :id"),
            {"id": new_id},
        ).mappings().first()

    logger.info(
        "form_template created id=%s code=%s v=%s by=%s",
        new_id, body.code, body.version, user.get("id"),
    )
    return _row_to_dict(row)


@router.patch("/{template_id}", response_model=FormTemplateRead)
def update_form_template(
    template_id: str,
    body: FormTemplateUpdate,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """
    Update a form template.

    Two modes:
      1. **In-place update** — body.version is omitted OR equals the current
         row's version. Mutates the row.
      2. **Version bump** — body.version differs from the current row's version.
         INSERTS a new row carrying the merged values; the old row is preserved
         so historical case_forms keep pointing at it.

    Returns the (possibly newly-created) row.
    """
    with db.engine.begin() as conn:
        current = conn.execute(
            text(f"SELECT {_select_cols()} FROM {_table()} WHERE id = :id"),
            {"id": template_id},
        ).mappings().first()
        if not current:
            raise HTTPException(status_code=404, detail="Form template not found")

        current_dict = _row_to_dict(current)
        merged = _merge(current_dict, body)
        is_version_bump = (
            body.version is not None and body.version != current_dict["version"]
        )

        fields_expr = _jsonb_expr("fields")
        rules_expr = _jsonb_expr("trigger_rules")

        if is_version_bump:
            dup = conn.execute(
                text(
                    f"SELECT 1 FROM {_table()} "
                    "WHERE code = :code AND version = :version LIMIT 1"
                ),
                {"code": merged["code"], "version": merged["version"]},
            ).first()
            if dup:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Form template with code={merged['code']} "
                        f"version={merged['version']} already exists"
                    ),
                )

            new_id = str(uuid.uuid4())
            conn.execute(
                text(
                    f"""
                    INSERT INTO {_table()} (
                        id, code, name, country, authority_code, authority_name,
                        category, original_pdf_url, version, fields, trigger_rules
                    ) VALUES (
                        :id, :code, :name, :country, :authority_code, :authority_name,
                        :category, :original_pdf_url, :version,
                        {fields_expr}, {rules_expr}
                    )
                    """
                ),
                {
                    "id": new_id,
                    "code": merged["code"],
                    "name": merged["name"],
                    "country": (merged["country"] or "").upper(),
                    "authority_code": merged.get("authority_code"),
                    "authority_name": merged.get("authority_name"),
                    "category": merged.get("category"),
                    "original_pdf_url": merged.get("original_pdf_url"),
                    "version": merged["version"],
                    "fields": _json_dumps(merged.get("fields") or []),
                    "trigger_rules": _json_dumps(merged.get("trigger_rules") or {}),
                },
            )
            row = conn.execute(
                text(f"SELECT {_select_cols()} FROM {_table()} WHERE id = :id"),
                {"id": new_id},
            ).mappings().first()
            logger.info(
                "form_template version-bumped from id=%s v=%s to id=%s v=%s by=%s",
                template_id, current_dict["version"], new_id, merged["version"], user.get("id"),
            )
            return _row_to_dict(row)

        # In-place update path. On SQLite we also bump updated_at explicitly
        # (Postgres has the moddatetime trigger).
        if _dialect() == "postgresql":
            updated_at_clause = ""
            extra_params: Dict[str, Any] = {}
        else:
            updated_at_clause = ", updated_at = :updated_at"
            extra_params = {"updated_at": datetime.utcnow().isoformat()}

        conn.execute(
            text(
                f"""
                UPDATE {_table()} SET
                  code             = :code,
                  name             = :name,
                  country          = :country,
                  authority_code   = :authority_code,
                  authority_name   = :authority_name,
                  category         = :category,
                  original_pdf_url = :original_pdf_url,
                  version          = :version,
                  fields           = {fields_expr},
                  trigger_rules    = {rules_expr}
                  {updated_at_clause}
                WHERE id = :id
                """
            ),
            {
                "id": template_id,
                "code": merged["code"],
                "name": merged["name"],
                "country": (merged["country"] or "").upper(),
                "authority_code": merged.get("authority_code"),
                "authority_name": merged.get("authority_name"),
                "category": merged.get("category"),
                "original_pdf_url": merged.get("original_pdf_url"),
                "version": merged["version"],
                "fields": _json_dumps(merged.get("fields") or []),
                "trigger_rules": _json_dumps(merged.get("trigger_rules") or {}),
                **extra_params,
            },
        )
        row = conn.execute(
            text(f"SELECT {_select_cols()} FROM {_table()} WHERE id = :id"),
            {"id": template_id},
        ).mappings().first()

    logger.info("form_template updated in-place id=%s by=%s", template_id, user.get("id"))
    return _row_to_dict(row)


# (accuracy-report endpoint moved above /{template_id} — see earlier in this file)
