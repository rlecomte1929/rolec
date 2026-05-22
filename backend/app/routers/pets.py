"""
Pets CRUD router — AIQ-288 (AIQ-160-A).

GET    /api/cases/{case_id}/pets
POST   /api/cases/{case_id}/pets
PATCH  /api/cases/{case_id}/pets/{pet_id}
DELETE /api/cases/{case_id}/pets/{pet_id}

Access control: re-uses _assert_case_access from the cases router so the
same employee/HR/admin policy as case_forms applies. Raw SQL via the shared
engine to stay dialect-aware (Postgres in prod, SQLite in tests).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import text as _sql_text

from ..auth_deps import get_current_user
from ...database import db as main_db
from .cases import _assert_case_access, _pg_table, _sql_now, _sql_uuid_gen


router = APIRouter(prefix="/api/cases", tags=["pets"])
logger = logging.getLogger(__name__)


# ─── Schemas ──────────────────────────────────────────────────────────────────


class PetCreate(BaseModel):
    name: Optional[str] = None
    species: str
    breed: Optional[str] = None
    microchip_number: Optional[str] = None
    date_of_birth: Optional[str] = None       # ISO date
    passport_number: Optional[str] = None
    health_cert_expiry: Optional[str] = None  # ISO date
    vaccinations: Optional[List[Dict[str, Any]]] = None  # [{name, date, expiry}]
    vet_name: Optional[str] = None
    vet_phone: Optional[str] = None
    vet_country: Optional[str] = None         # ISO 3166-1 alpha-2


class PetPatch(BaseModel):
    name: Optional[str] = None
    species: Optional[str] = None
    breed: Optional[str] = None
    microchip_number: Optional[str] = None
    date_of_birth: Optional[str] = None
    passport_number: Optional[str] = None
    health_cert_expiry: Optional[str] = None
    vaccinations: Optional[List[Dict[str, Any]]] = None
    vet_name: Optional[str] = None
    vet_phone: Optional[str] = None
    vet_country: Optional[str] = None


class PetDTO(BaseModel):
    id: str
    case_id: str
    name: Optional[str] = None
    species: str
    breed: Optional[str] = None
    microchip_number: Optional[str] = None
    date_of_birth: Optional[str] = None
    passport_number: Optional[str] = None
    health_cert_expiry: Optional[str] = None
    vaccinations: List[Dict[str, Any]] = []
    vet_name: Optional[str] = None
    vet_phone: Optional[str] = None
    vet_country: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ─── Helpers ──────────────────────────────────────────────────────────────────


_PET_COLUMNS = (
    "id, case_id, name, species, breed, microchip_number, date_of_birth, "
    "passport_number, health_cert_expiry, vaccinations, vet_name, vet_phone, "
    "vet_country, created_at, updated_at"
)


def _row_to_dto(row: Dict[str, Any]) -> PetDTO:
    import json as _json

    vacc_raw = row.get("vaccinations")
    if isinstance(vacc_raw, str):
        try:
            vacc = _json.loads(vacc_raw) if vacc_raw else []
        except (ValueError, TypeError):
            vacc = []
    elif isinstance(vacc_raw, list):
        vacc = vacc_raw
    else:
        vacc = []

    def _iso(v: Any) -> Optional[str]:
        if v is None:
            return None
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return str(v)

    return PetDTO(
        id=str(row["id"]),
        case_id=str(row["case_id"]),
        name=row.get("name"),
        species=row["species"],
        breed=row.get("breed"),
        microchip_number=row.get("microchip_number"),
        date_of_birth=_iso(row.get("date_of_birth")),
        passport_number=row.get("passport_number"),
        health_cert_expiry=_iso(row.get("health_cert_expiry")),
        vaccinations=vacc,
        vet_name=row.get("vet_name"),
        vet_phone=row.get("vet_phone"),
        vet_country=row.get("vet_country"),
        created_at=_iso(row.get("created_at")),
        updated_at=_iso(row.get("updated_at")),
    )


def _vaccinations_param(value: Optional[List[Dict[str, Any]]]) -> str:
    import json as _json
    return _json.dumps(value or [])


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/{case_id}/pets", response_model=List[PetDTO])
def list_pets(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[PetDTO]:
    _assert_case_access(user, case_id)
    sql = f"SELECT {_PET_COLUMNS} FROM {_pg_table('pets')} WHERE case_id = :case_id ORDER BY created_at ASC"
    try:
        with main_db.engine.connect() as conn:
            rows = conn.execute(_sql_text(sql), {"case_id": case_id}).mappings().all()
    except Exception:
        logger.exception("pets: list failed case_id=%s", case_id)
        raise HTTPException(status_code=500, detail="Failed to list pets")
    return [_row_to_dto(dict(r)) for r in rows]


@router.post("/{case_id}/pets", response_model=PetDTO, status_code=201)
def create_pet(
    case_id: str,
    payload: PetCreate,
    user: Dict[str, Any] = Depends(get_current_user),
) -> PetDTO:
    _assert_case_access(user, case_id)
    if not payload.species or not payload.species.strip():
        raise HTTPException(status_code=400, detail="species is required")

    sql = (
        f"INSERT INTO {_pg_table('pets')} ("
        "id, case_id, name, species, breed, microchip_number, date_of_birth, "
        "passport_number, health_cert_expiry, vaccinations, vet_name, vet_phone, "
        "vet_country, created_at, updated_at"
        f") VALUES ("
        f"{_sql_uuid_gen()}, :case_id, :name, :species, :breed, :microchip_number, :date_of_birth, "
        ":passport_number, :health_cert_expiry, :vaccinations, :vet_name, :vet_phone, "
        f":vet_country, {_sql_now()}, {_sql_now()}"
        f") RETURNING {_PET_COLUMNS}"
    )
    params = {
        "case_id": case_id,
        "name": payload.name,
        "species": payload.species,
        "breed": payload.breed,
        "microchip_number": payload.microchip_number,
        "date_of_birth": payload.date_of_birth,
        "passport_number": payload.passport_number,
        "health_cert_expiry": payload.health_cert_expiry,
        "vaccinations": _vaccinations_param(payload.vaccinations),
        "vet_name": payload.vet_name,
        "vet_phone": payload.vet_phone,
        "vet_country": payload.vet_country,
    }
    try:
        with main_db.engine.begin() as conn:
            row = _insert_returning(conn, sql, params)
    except HTTPException:
        raise
    except Exception:
        logger.exception("pets: create failed case_id=%s", case_id)
        raise HTTPException(status_code=500, detail="Failed to create pet")
    return _row_to_dto(dict(row))


@router.patch("/{case_id}/pets/{pet_id}", response_model=PetDTO)
def update_pet(
    case_id: str,
    pet_id: str,
    payload: PetPatch,
    user: Dict[str, Any] = Depends(get_current_user),
) -> PetDTO:
    _assert_case_access(user, case_id)
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        # Nothing to update — return current row instead of running an empty UPDATE
        return _fetch_pet_or_404(case_id, pet_id)

    set_parts: List[str] = []
    params: Dict[str, Any] = {"case_id": case_id, "pet_id": pet_id}
    for key, value in fields.items():
        if key == "vaccinations":
            set_parts.append("vaccinations = :vaccinations")
            params["vaccinations"] = _vaccinations_param(value)
        else:
            set_parts.append(f"{key} = :{key}")
            params[key] = value
    set_parts.append(f"updated_at = {_sql_now()}")

    sql = (
        f"UPDATE {_pg_table('pets')} SET {', '.join(set_parts)} "
        f"WHERE id = :pet_id AND case_id = :case_id "
        f"RETURNING {_PET_COLUMNS}"
    )
    try:
        with main_db.engine.begin() as conn:
            row = _update_returning(conn, sql, params)
    except HTTPException:
        raise
    except Exception:
        logger.exception("pets: update failed case_id=%s pet_id=%s", case_id, pet_id)
        raise HTTPException(status_code=500, detail="Failed to update pet")
    if not row:
        raise HTTPException(status_code=404, detail="Pet not found")
    return _row_to_dto(dict(row))


@router.delete("/{case_id}/pets/{pet_id}", status_code=204)
def delete_pet(
    case_id: str,
    pet_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    _assert_case_access(user, case_id)
    sql = f"DELETE FROM {_pg_table('pets')} WHERE id = :pet_id AND case_id = :case_id"
    try:
        with main_db.engine.begin() as conn:
            result = conn.execute(_sql_text(sql), {"pet_id": pet_id, "case_id": case_id})
            rowcount = result.rowcount or 0
    except Exception:
        logger.exception("pets: delete failed case_id=%s pet_id=%s", case_id, pet_id)
        raise HTTPException(status_code=500, detail="Failed to delete pet")
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="Pet not found")
    return Response(status_code=204)


# ─── Private helpers ──────────────────────────────────────────────────────────


def _fetch_pet_or_404(case_id: str, pet_id: str) -> PetDTO:
    sql = (
        f"SELECT {_PET_COLUMNS} FROM {_pg_table('pets')} "
        f"WHERE id = :pet_id AND case_id = :case_id"
    )
    with main_db.engine.connect() as conn:
        row = conn.execute(
            _sql_text(sql), {"pet_id": pet_id, "case_id": case_id}
        ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Pet not found")
    return _row_to_dto(dict(row))


def _insert_returning(conn: Any, sql: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """RETURNING is Postgres-only — fall back to a SELECT on SQLite."""
    dialect = getattr(main_db.engine.dialect, "name", "postgresql")
    if dialect == "sqlite":
        # Pre-generate the UUID so we can re-SELECT after insert.
        import uuid as _uuid
        new_id = _uuid.uuid4().hex
        sqlite_sql = sql.replace("lower(hex(randomblob(16)))", ":__new_id").split(" RETURNING")[0]
        # If the placeholder wasn't substituted (shouldn't happen) bail.
        if ":__new_id" not in sqlite_sql:
            sqlite_sql = sql.split(" RETURNING")[0]
        params = {**params, "__new_id": new_id}
        conn.execute(_sql_text(sqlite_sql), params)
        select_sql = (
            f"SELECT {_PET_COLUMNS} FROM {_pg_table('pets')} WHERE id = :__new_id"
        )
        row = conn.execute(_sql_text(select_sql), {"__new_id": new_id}).mappings().first()
        if not row:
            raise HTTPException(status_code=500, detail="Pet insert did not persist")
        return dict(row)
    row = conn.execute(_sql_text(sql), params).mappings().first()
    if not row:
        raise HTTPException(status_code=500, detail="Pet insert did not persist")
    return dict(row)


def _update_returning(conn: Any, sql: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    dialect = getattr(main_db.engine.dialect, "name", "postgresql")
    if dialect == "sqlite":
        update_sql = sql.split(" RETURNING")[0]
        result = conn.execute(_sql_text(update_sql), params)
        if (result.rowcount or 0) == 0:
            return None
        select_sql = (
            f"SELECT {_PET_COLUMNS} FROM {_pg_table('pets')} "
            f"WHERE id = :pet_id AND case_id = :case_id"
        )
        row = conn.execute(
            _sql_text(select_sql), {"pet_id": params["pet_id"], "case_id": params["case_id"]}
        ).mappings().first()
        return dict(row) if row else None
    row = conn.execute(_sql_text(sql), params).mappings().first()
    return dict(row) if row else None
