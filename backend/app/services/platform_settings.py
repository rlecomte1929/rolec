"""Platform settings store — env → DB → default resolver.

Foundation for Tasks 4 & 5 (admin-hardening).  Changes NO existing behaviour
on its own: until the ``platform_settings`` migration is applied to production,
every ``get_setting`` call with a missing table falls through to ``default``.

Precedence
----------
1. Environment variable named by ``env_var`` (if that env var is set and non-empty).
2. DB value for ``key`` (best-effort: returns ``default`` when the table is absent
   or any error occurs — so behaviour is safe before the migration is applied).
3. ``default``.

DB access
---------
Uses the caller-supplied SQLAlchemy Session (``db`` parameter), not an internal
SessionLocal, so the caller controls transaction boundaries.  Raw ``text()``
queries with named bind-params follow the repo's existing pattern
(``audit_log_service.py``, ``ranking_weights_store.py``).

The table is named ``platform_settings`` (no ``public.`` prefix) so the same
SQL works against both SQLite (tests, no schemas) and Postgres (default
``public`` search_path resolves the unqualified name).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from .admin_audit import record_admin_event

log = logging.getLogger(__name__)

# ── SQL statements ────────────────────────────────────────────────────────────

_SELECT_SQL = text(
    "SELECT value_json FROM platform_settings WHERE key = :key"
)

# INSERT … ON CONFLICT (key) DO UPDATE works on SQLite ≥ 3.24 (2018) and Postgres.
_UPSERT_SQL = text(
    """
    INSERT INTO platform_settings (key, value_json, updated_by, updated_at)
    VALUES (:key, :value_json, :actor_id, CURRENT_TIMESTAMP)
    ON CONFLICT (key) DO UPDATE
      SET value_json = EXCLUDED.value_json,
          updated_by = EXCLUDED.updated_by,
          updated_at = CURRENT_TIMESTAMP
    """
)

_LIST_SQL = text(
    "SELECT key, value_json, updated_by, updated_at"
    " FROM platform_settings ORDER BY key"
)


# ── Public API ────────────────────────────────────────────────────────────────


def get_setting(
    key: str,
    *,
    env_var: Optional[str] = None,
    default: Optional[str] = None,
    db: Any = None,
) -> Optional[str]:
    """Resolve a platform setting with env → DB → default precedence.

    Args:
        key:     Setting key (used for the DB lookup).
        env_var: Name of an environment variable; if set and non-empty its
                 value wins unconditionally.
        default: Fallback when neither env nor DB supplies the key.
        db:      SQLAlchemy Session; pass ``None`` to skip the DB look-up.

    Returns the resolved value or *default*.  Never raises.
    """
    # 1. Env var wins.
    if env_var:
        env_val = os.environ.get(env_var)
        if env_val is not None:
            return env_val

    # 2. DB look-up (best-effort).
    if db is not None:
        try:
            row = db.execute(_SELECT_SQL, {"key": key}).first()
            if row is not None:
                raw = row[0]
                # value_json is jsonb (Postgres) or TEXT (SQLite).
                # Unwrap one JSON layer to recover the original string.
                if isinstance(raw, str):
                    try:
                        val = json.loads(raw)
                    except (json.JSONDecodeError, ValueError):
                        val = raw
                else:
                    val = raw
                return str(val) if val is not None else default
        except Exception as exc:
            log.debug("get_setting(%r) db look-up failed (best-effort): %s", key, exc)

    # 3. Default.
    return default


def set_setting(
    db: Any,
    key: str,
    value: str,
    *,
    actor_id: str,
    event: str = "setting_changed",
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist a platform setting and write an audit log entry.

    The value is serialised as a JSON string so the ``jsonb`` column on Postgres
    can store any future type without a schema change.  Currently only string
    values are supported via the public API.

    Args:
        db:       SQLAlchemy Session (caller owns the transaction).
        key:      Setting key.
        value:    New value (stored JSON-encoded inside the jsonb column).
        actor_id: Admin user id for the audit log; may be a legacy text id.
        event:    Audit event name (defaults to ``"setting_changed"``).
        detail:   Extra fields merged into the audit detail alongside key/value.
    """
    db.execute(
        _UPSERT_SQL,
        {
            "key": key,
            "value_json": json.dumps(value),
            "actor_id": actor_id,
        },
    )
    merged_detail: Dict[str, Any] = {"key": key, "value": value, **(detail or {})}
    record_admin_event(
        db,
        actor_id=actor_id,
        event=event,
        entity="platform_settings",
        entity_id=key,
        detail=merged_detail,
    )


def list_settings(db: Any) -> List[Dict[str, Any]]:
    """Return all rows from ``platform_settings`` as dicts.

    Best-effort: returns ``[]`` when the table is absent or any error occurs.

    Each dict has keys: ``key``, ``value`` (unwrapped from JSON), ``updated_by``,
    ``updated_at``.
    """
    try:
        rows = db.execute(_LIST_SQL).all()
        out: List[Dict[str, Any]] = []
        for row in rows:
            key, raw, updated_by, updated_at = row
            if isinstance(raw, str):
                try:
                    val: Any = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    val = raw
            else:
                val = raw
            out.append(
                {
                    "key": key,
                    "value": val,
                    "updated_by": updated_by,
                    "updated_at": str(updated_at) if updated_at else None,
                }
            )
        return out
    except Exception as exc:
        log.debug("list_settings failed (best-effort): %s", exc)
        return []
