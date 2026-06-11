"""
Unified database layer — works with both SQLite and Postgres.
Uses DATABASE_URL from db_config (single source of truth).
"""
import json
import os
import math
import re
import uuid
import logging
import time
from threading import Lock
from typing import Optional, Dict, Any, List, Tuple, Set, Callable
from datetime import datetime

from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from .db_config import (
    DATABASE_URL as _raw_url,
    REQUEST_DATABASE_URL as _request_url,
    REQUEST_DB_IS_DEDICATED as _request_db_is_dedicated,
    sqlalchemy_engine_kwargs,
)
from .identity_normalize import email_normalized_from_identifier, normalize_invite_key
from .identity_observability import identity_event

from .readiness_service import (
    DEFAULT_ROUTE_KEY,
    extract_destination_from_case_profile,
    extract_destination_from_profile,
    normalize_destination_key,
    resolve_readiness_route_key,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine setup (shared logic with backend/app/db.py)
# ---------------------------------------------------------------------------
_engine = create_engine(_raw_url, **sqlalchemy_engine_kwargs(_raw_url))

# F3/AIQ-834: a dedicated least-privilege engine for the request path (the
# non-superuser relopass_api role, where the RLS second barrier actually bites).
# Falls back to the same superuser engine when RELOPASS_API_DATABASE_URL is unset
# — so this is a no-op until the role is provisioned. Scoped use: only the
# policy_assistant_chunks retriever routes through it for now (task scope).
_request_engine = (
    create_engine(_request_url, **sqlalchemy_engine_kwargs(_request_url))
    if _request_db_is_dedicated
    else _engine
)

_is_sqlite = _raw_url.startswith("sqlite")
# Postgres-only jsonb cast suffix; empty string on SQLite (TEXT columns used there).
_jb = "" if _is_sqlite else "::jsonb"

if _is_sqlite:
    @event.listens_for(_engine, "connect")
    def _sqlite_enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        """Enforce REFERENCES clauses on SQLite (off by default)."""
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()
else:
    # B3-fix: Supabase PgBouncer in transaction-pooling mode resets session-level
    # GUC settings (statement_timeout / lock_timeout) between transactions, so the
    # connect_args options=-c ... approach is unreliable.  Re-applying them on every
    # pool checkout guarantees they are set before ANY DB round-trip regardless of
    # pooler mode.  The two SET calls add ~1 ms overhead per checkout.
    @event.listens_for(_engine, "checkout")
    def _set_db_timeouts(dbapi_conn, conn_record, conn_proxy):
        try:
            cur = dbapi_conn.cursor()
            cur.execute("SET statement_timeout = 8000")   # 8 s — abort hung queries fast
            cur.execute("SET lock_timeout = 5000")        # 5 s — abort lock waits fast
            cur.close()
        except Exception:
            pass  # never block a checkout for a non-critical SET


def _relocation_cases_join_on(table_alias: str = "a", style: str = "standard") -> str:
    """
    Predicate for: LEFT JOIN relocation_cases rc ON <this>
    Supabase/Postgres often types relocation_cases.id as uuid while case_assignments.case_id is text;
    comparing without a cast raises 'operator does not exist: uuid = text'. SQLite uses text ids — no ::text.
    """
    a = table_alias
    if style == "simple":
        rhs = f"{a}.case_id"
    elif style == "canonical_coalesce":
        rhs = f"COALESCE(NULLIF(TRIM(COALESCE({a}.canonical_case_id, '')), ''), {a}.case_id)"
    else:
        rhs = f"COALESCE(NULLIF(TRIM({a}.canonical_case_id), ''), {a}.case_id)"
    if _is_sqlite:
        return f"rc.id = {rhs}"
    # CAST both sides: avoids uuid=text operator errors across mixed schemas.
    return f"CAST(rc.id AS TEXT) = CAST(({rhs}) AS TEXT)"


def _eq_text(lhs_sql: str, rhs_sql: str) -> str:
    """Cross-type-safe equality for ids (Postgres uuid vs text on messages / assignments / prefs). SQLite: CAST is harmless."""
    return f"CAST({lhs_sql} AS TEXT) = CAST({rhs_sql} AS TEXT)"


def _coerce_json_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return {}
        try:
            out = json.loads(s)
            return dict(out) if isinstance(out, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _coerce_json_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        try:
            out = json.loads(s)
            return list(out) if isinstance(out, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _sqlite_ensure_policy_import_columns(conn: Any) -> None:
    """Add assistant-import columns to policy_documents when upgrading older SQLite DBs."""
    try:
        rows = conn.execute(text("PRAGMA table_info(policy_documents)")).fetchall()
    except Exception:
        return
    names = {r[1] for r in rows}
    if not names:
        return
    for col, typ in (
        ("file_size_bytes", "INTEGER"),
        ("archived_at", "TEXT"),
        ("assistant_import_status", "TEXT"),
        ("processed_at", "TEXT"),
    ):
        if col in names:
            continue
        try:
            conn.execute(text(f"ALTER TABLE policy_documents ADD COLUMN {col} {typ}"))
        except Exception:
            pass


def _sqlite_ensure_policy_hardening_columns(conn: Any) -> None:
    """Add hardening columns to policy_knowledge_snapshots / policy_document_chunks on older SQLite DBs."""
    try:
        r = conn.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='policy_knowledge_snapshots'"
            )
        ).fetchone()
        if not r:
            return
        names = {row[1] for row in conn.execute(text("PRAGMA table_info(policy_knowledge_snapshots)")).fetchall()}
        for col, typ, default in (
            ("revision_number", "INTEGER", "1"),
            ("parent_snapshot_id", "TEXT", None),
            ("superseded_by_snapshot_id", "TEXT", None),
            ("activation_state", "TEXT", "'failed'"),
            ("activated_at", "TEXT", None),
            ("activated_by_user_id", "TEXT", None),
        ):
            if col in names:
                continue
            try:
                if default is None:
                    conn.execute(text(f"ALTER TABLE policy_knowledge_snapshots ADD COLUMN {col} {typ}"))
                else:
                    conn.execute(
                        text(f"ALTER TABLE policy_knowledge_snapshots ADD COLUMN {col} {typ} DEFAULT {default}")
                    )
            except Exception:
                pass
        # Backfill activation_state from status when possible
        try:
            conn.execute(
                text(
                    "UPDATE policy_knowledge_snapshots SET activation_state = "
                    "CASE WHEN status = 'active_for_assistant' THEN 'active_for_assistant' "
                    "WHEN status = 'superseded' THEN 'superseded' WHEN status = 'failed' THEN 'failed' "
                    "ELSE 'failed' END WHERE activation_state IS NULL OR activation_state = ''"
                )
            )
        except Exception:
            pass
        cnames = {row[1] for row in conn.execute(text("PRAGMA table_info(policy_document_chunks)")).fetchall()}
        if "snapshot_id" not in cnames:
            try:
                conn.execute(text("ALTER TABLE policy_document_chunks ADD COLUMN snapshot_id TEXT"))
            except Exception:
                pass
    except Exception:
        pass


def _sqlite_ensure_canonical_policy_tenant_columns(conn: Any) -> None:
    try:
        tables = (
            ("canonical_policy_documents", ("company_id", "TEXT")),
            ("canonical_policy_document_chunks", ("company_id", "TEXT")),
            ("canonical_policy_facts", ("company_id", "TEXT")),
            ("canonical_policy_fact_validation_errors", ("company_id", "TEXT")),
        )
        for table, (col, typ) in tables:
            exists = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name = :name"),
                {"name": table},
            ).fetchone()
            if not exists:
                continue
            cols = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()}
            if col not in cols:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typ}"))
                except Exception:
                    pass
        try:
            conn.execute(
                text(
                    "UPDATE canonical_policy_documents "
                    "SET company_id = COALESCE(company_id, (SELECT company_id FROM policy_documents p WHERE p.id = source_policy_document_id), '') "
                    "WHERE company_id IS NULL OR company_id = ''"
                )
            )
        except Exception:
            pass
        for table in (
            "canonical_policy_document_chunks",
            "canonical_policy_facts",
            "canonical_policy_fact_validation_errors",
        ):
            try:
                conn.execute(
                    text(
                        f"UPDATE {table} "
                        "SET company_id = COALESCE(company_id, (SELECT company_id FROM canonical_policy_documents d "
                        f"WHERE d.id = {table}.canonical_policy_document_id), '') "
                        "WHERE company_id IS NULL OR company_id = ''"
                    )
                )
            except Exception:
                pass
    except Exception:
        pass


# NOTE: Production Postgres currently has no profiles.status column.
# To avoid schema drift issues we do not reference profiles.status at all.
_profiles_has_status_column = False


def _get_company_policies_columns(conn: Any) -> set:
    """Return set of column names for company_policies (SQLite PRAGMA or Postgres information_schema)."""
    if _is_sqlite:
        rows = conn.execute(text("PRAGMA table_info(company_policies)")).fetchall()
        return {r[1] for r in rows}
    rows = conn.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'company_policies'"
        )
    ).fetchall()
    return {r._mapping["column_name"] for r in rows}


def _table_columns(conn: Any, table_name: str) -> set:
    """Dialect-aware column-name introspection.

    Returns the set of column names for `table_name`. Uses SQLite's
    PRAGMA table_info on SQLite engines and Postgres's information_schema
    on everything else. Existing call sites that hard-code the Postgres
    query break on SQLite dev — this helper is the safe replacement.
    """
    if _is_sqlite:
        rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        return {r[1] for r in rows}
    rows = conn.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :t"
        ),
        {"t": table_name},
    ).fetchall()
    return {r._mapping["column_name"] for r in rows}


def _table_has_column(conn: Any, table_name: str, column_name: str) -> bool:
    """Convenience wrapper over `_table_columns` for the common existence check."""
    return column_name in _table_columns(conn, table_name)


def _seed_default_policy_template_sqlite(conn: Any) -> None:
    """Insert one platform default policy template for SQLite when none exists."""
    from sqlalchemy import text
    now = datetime.utcnow().isoformat()
    template_id = str(uuid.uuid4())
    snapshot = {
        "policyVersion": "v2.1",
        "effectiveDate": "2024-10-01",
        "jurisdictionNotes": "Base policy for global assignments. Local counsel required for exceptions.",
        "caps": {
            "housing": {"amount": 5000, "currency": "USD", "durationMonths": 12},
            "movers": {"amount": 10000, "currency": "USD"},
            "schools": {"amount": 20000, "currency": "USD"},
            "immigration": {"amount": 4000, "currency": "USD"},
        },
        "approvalRules": {"nearLimit": "Manager", "overLimit": "HR"},
        "exceptionWorkflow": {"states": ["PENDING", "APPROVED", "REJECTED"], "requiredFields": ["category", "reason", "amount"]},
        "requiredEvidence": {
            "housing": ["Lease estimate", "Budget approval"],
            "movers": ["Vendor quote", "Inventory list"],
            "schools": ["School invoice", "Enrollment confirmation"],
            "immigration": ["Legal engagement letter", "Filing receipt"],
        },
        "leadTimeRules": {"minDays": 30},
        "riskThresholds": {"low": 80, "moderate": 60},
        "documentRequirements": {
            "base": ["Passport scans", "Employment letter"],
            "married": ["Marriage certificate"],
            "children": ["Birth certificates"],
            "spouseWork": ["Spouse resume"],
        },
        "approvalThresholds": {
            "housing": {"jobLevelCapOverrides": {"L1": 5000, "L2": 7000, "L3": 10000}},
            "movers": {"storageWeeksIncluded": 4},
        },
        "benefit_rules": [
            {"benefit_key": "housing", "benefit_category": "housing", "calc_type": "unit_cap", "amount_value": 5000, "amount_unit": "month", "currency": "USD"},
            {"benefit_key": "movers", "benefit_category": "movers", "calc_type": "flat_amount", "amount_value": 10000, "currency": "USD"},
            {"benefit_key": "schools", "benefit_category": "schools", "calc_type": "flat_amount", "amount_value": 20000, "currency": "USD"},
            {"benefit_key": "immigration", "benefit_category": "immigration", "calc_type": "flat_amount", "amount_value": 4000, "currency": "USD"},
        ],
    }
    conn.execute(
        text("""
            INSERT INTO default_policy_templates (id, template_name, version, status, is_default_template, snapshot_json, created_at, updated_at)
            VALUES (:id, :name, :ver, :status, 1, :snapshot, :ca, :ua)
        """),
        {
            "id": template_id,
            "name": "Platform default relocation policy",
            "ver": "v2.1",
            "status": "active",
            "snapshot": json.dumps(snapshot),
            "ca": now,
            "ua": now,
        },
    )


def _policy_bool_bind(value: Any) -> Any:
    """
    Bind value for policy_* auto_generated columns.
    SQLite uses INTEGER 0/1; Postgres expects a boolean bind (avoids driver/type mismatches with CASE+int).
    """
    b = bool(value) if value is not None else True
    if _is_sqlite:
        return 1 if b else 0
    return b


def _policy_ag_sql() -> str:
    """SQL placeholder for auto_generated; use :ag with _policy_bool_bind() for each dialect."""
    return ":ag"


def normalize_policy_boolean_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Coerce known boolean keys for DB write.
    SQLite policy_* tables use INTEGER (0/1); Postgres uses boolean (True/False).
    """
    BOOLEAN_KEYS = ("auto_generated", "ag")
    out = dict(payload)
    for k in BOOLEAN_KEYS:
        if k not in out:
            continue
        v = out[k]
        if v is None:
            continue
        out[k] = _policy_bool_bind(v)
    return out


def _auto_id_col() -> str:
    """Return the DDL fragment for an auto-incrementing integer PK."""
    if _is_sqlite:
        return "INTEGER PRIMARY KEY AUTOINCREMENT"
    return "SERIAL PRIMARY KEY"


# [AUDIT-C1.2] Cases-domain methods are extracted into backend/db/cases.py and
# mixed in here. backend.db.cases imports nothing from this module, so there is
# no import cycle. Callers (db.create_case(...) etc.) are unchanged via MRO.
from .db.cases import CasesMixin
from .db.policies import PoliciesMixin
from .db.users import UsersMixin
from .db.auth import AuthMixin
from .db.intake import IntakeMixin
from .db.hr import HrMixin
from .db.companies import CompaniesMixin
from .db.support import SupportMixin
from .db.vendors import VendorsMixin
from .db.audit import AuditMixin
from .db.misc import MiscMixin


class Database(CasesMixin, PoliciesMixin, UsersMixin, AuthMixin, IntakeMixin, HrMixin, CompaniesMixin, SupportMixin, VendorsMixin, AuditMixin, MiscMixin):
    def __init__(self) -> None:
        self.engine = _engine
        # F3/AIQ-834: least-privilege request-path engine (relopass_api when
        # provisioned, else the same engine). Use for request queries that must
        # honour the RLS second barrier; currently the policy_assistant_chunks
        # retriever only.
        self.request_engine = _request_engine
        # None = unknown; False = readiness_templates not available (migration not applied / wrong DB)
        self._readiness_store_cache: Optional[bool] = None
        self._init_lock = Lock()
        self._initialized = False

    # [AUDIT-C1.6b] ensure_initialized extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] _exec extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] _db_healthcheck extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] _maybe_ensure_postgres_missing_schemas extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6a] _maybe_ensure_policy_versions_normalization_draft_json extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] _maybe_ensure_policy_versions_normalization_state extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] _maybe_ensure_policy_benefit_rule_hr_overrides extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] _maybe_ensure_compensation_allowance_policy_config extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6b] _maybe_ensure_hot_path_indexes extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] _maybe_ensure_archived_at_columns extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.2] cases batch 13e — case assignments link-mode schema extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6b] _ensure_postgres_canonical_identity_schema extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.2] cases batch 13d — case milestones schema extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6b] init_db extracted to backend/db/misc.py (MiscMixin).

    # ------------------------------------------------------------------
    # Users table migration helpers (SQLite only)
    # ------------------------------------------------------------------
    # [AUDIT-C1.4] _ensure_users_table_sqlite extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] _create_users_table extracted to backend/db/users.py (UsersMixin).

    # ------------------------------------------------------------------
    # Helper: convert row to dict
    # ------------------------------------------------------------------
    # [AUDIT-C1.6b] _row_to_dict extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] _rows_to_list extracted to backend/db/misc.py (MiscMixin).

    # ==================================================================
    # User operations
    # ==================================================================
    # [AUDIT-C1.4] create_user extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] get_user_by_email extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] get_user_by_username extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] get_user_by_identifier extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] delete_session_by_token extracted to backend/db/auth.py (AuthMixin).

    # [AUDIT-C1.4] get_user_by_id extracted to backend/db/users.py (UsersMixin).

    # ==================================================================
    # Session operations
    # ==================================================================
    # [AUDIT-C1.4] create_session extracted to backend/db/auth.py (AuthMixin).

    # [AUDIT-C1.4] get_user_by_token extracted to backend/db/auth.py (AuthMixin).

    # ==================================================================
    # Profile operations (legacy)
    # ==================================================================
    # [AUDIT-C1.4] get_user_context_by_token extracted to backend/db/auth.py (AuthMixin).

    # [AUDIT-C1.4] save_profile extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] get_profile extracted to backend/db/users.py (UsersMixin).

    # ==================================================================
    # Answer operations (legacy)
    # ==================================================================
    # [AUDIT-C1.5] save_answer extracted to backend/db/intake.py (IntakeMixin).

    # [AUDIT-C1.5] get_answers extracted to backend/db/intake.py (IntakeMixin).

    # ==================================================================
    # HR cases and assignments
    # ==================================================================
    # [AUDIT-C1.2] create_case, get_case_by_id, redact_case_identity_data,
    # resolve_canonical_case_id, coalesce_case_lookup_id were extracted to
    # backend/db/cases.py (CasesMixin) — Database inherits them, callers unchanged.

    # [AUDIT-C1.2] cases batch 12a — assignment create/update/attach extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6b] get_employee_contact_by_id extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] list_employee_contacts_matching_signup_email extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.2] cases batch 12b extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.4] list_employee_contacts_by_invite_key extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] list_assignment_claim_invite_statuses extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] map_claim_invite_statuses_by_assignments extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] is_assignment_auto_claim_blocked_by_revoked_invites extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] get_claim_invite_by_token extracted to backend/db/auth.py (AuthMixin).

    # [AUDIT-C1.2] cases batch 12c extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6b] _find_employee_contact_id_for_resolve extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] resolve_or_create_employee_contact extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] get_or_create_employee_contact extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.4] link_employee_contact_to_auth_user extracted to backend/db/auth.py (AuthMixin).

    # [AUDIT-C1.4] assignment_identity_matches_user_identifiers extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.6b] _backfill_employee_contacts extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.2 batch 2] The assignment-intake / case-event / participant /
    # evidence / milestone cases methods were extracted to backend/db/cases.py
    # (CasesMixin) — Database inherits them, callers unchanged.

    # [AUDIT-C1.6a] list_exception_requests extracted to backend/db/support.py (SupportMixin).

    # [AUDIT-C1.6a] upsert_exception_request extracted to backend/db/support.py (SupportMixin).

    # [AUDIT-C1.6a] update_exception_request extracted to backend/db/support.py (SupportMixin).

    # ------------------------------------------------------------------
    # Analytics events (observability)
    # ------------------------------------------------------------------
    # [AUDIT-C1.6a] insert_analytics_event extracted to backend/db/audit.py (AuditMixin).

    # [AUDIT-C1.6a] list_analytics_events extracted to backend/db/audit.py (AuditMixin).

    # [AUDIT-C1.6a] count_analytics_events_by_name extracted to backend/db/audit.py (AuditMixin).

    # [AUDIT-C1.2] cases batch 3 — assignment/mobility getters + case services extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6a] create_rfq extracted to backend/db/vendors.py (VendorsMixin).

    # [AUDIT-C1.2] cases batch 13a extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6a] _list_rfq_items extracted to backend/db/vendors.py (VendorsMixin).

    # [AUDIT-C1.6a] _list_rfq_recipients extracted to backend/db/vendors.py (VendorsMixin).

    # [AUDIT-C1.2] cases batch 13b extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6a] get_rfq extracted to backend/db/vendors.py (VendorsMixin).

    # [AUDIT-C1.6a] list_quotes_for_rfq extracted to backend/db/vendors.py (VendorsMixin).

    # [AUDIT-C1.6a] create_quote extracted to backend/db/vendors.py (VendorsMixin).

    # [AUDIT-C1.6a] update_quote_status extracted to backend/db/vendors.py (VendorsMixin).

    # [AUDIT-C1.6a] list_rfqs_for_vendor extracted to backend/db/vendors.py (VendorsMixin).

    # [AUDIT-C1.6a] validate_vendor_ids extracted to backend/db/vendors.py (VendorsMixin).

    # [AUDIT-C1.4] get_vendor_for_user extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.2] cases batch 4a — list_linked_assignments_for_employee extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.4] list_pending_claim_assignments_for_auth_user extracted to backend/db/auth.py (AuthMixin).

    # [AUDIT-C1.4] dismiss_pending_claim_assignment_for_auth_user extracted to backend/db/auth.py (AuthMixin).

    # [AUDIT-C1.2] cases batch 4b — employee/HR assignment overviews extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6a] list_assignments_for_company extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] list_assignments_for_company_paginated extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] _list_assignments_for_company_core extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] list_assignments_for_company_with_details extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] get_company_detail_orphan_diagnostics extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] assignment_belongs_to_company extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.5] insert_hr_feedback extracted to backend/db/hr.py (HrMixin).

    # [AUDIT-C1.5] list_hr_feedback extracted to backend/db/hr.py (HrMixin).

    # [AUDIT-C1.6a] _get_notification_preference extracted to backend/db/support.py (SupportMixin).

    # [AUDIT-C1.6a] _insert_notification_outbox extracted to backend/db/support.py (SupportMixin).

    # [AUDIT-C1.6a] create_notification_with_preferences extracted to backend/db/support.py (SupportMixin).

    # [AUDIT-C1.6a] insert_notification extracted to backend/db/support.py (SupportMixin).

    # [AUDIT-C1.6a] list_notifications extracted to backend/db/support.py (SupportMixin).

    # [AUDIT-C1.6a] count_unread_notifications extracted to backend/db/support.py (SupportMixin).

    # [AUDIT-C1.6a] mark_notification_read extracted to backend/db/support.py (SupportMixin).

    # [AUDIT-C1.2] cases batch 5 — admin assignment listings extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6a] admin_reassign_employee_company extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6b] admin_reassign_hr_owner extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6a] admin_fix_assignment_company_linkage extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.2] cases batch 11a — host country + route touch extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6b] set_case_employee_seniority extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.2] cases batch 11b — route sync extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.5] apply_wizard_patch_side_effects extracted to backend/db/intake.py (IntakeMixin).

    # [AUDIT-C1.2] cases batch 11c — sync case dependents extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.4] _resolve_employee_profile_id extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.6a] _resolve_canonical_case_company extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.2] cases batch 11d — canonical case + milestone deadlines extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6a] admin_link_policy_company extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] backfill_link_latest_policy_to_test_company extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6b] get_reconciliation_report extracted to backend/db/misc.py (MiscMixin).

    # ------------------------------------------------------------------
    # Dynamic dossier (Phase 1)
    # ------------------------------------------------------------------
    # [AUDIT-C1.6b] _json_load extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.5] seed_dossier_questions_if_missing extracted to backend/db/intake.py (IntakeMixin).

    # [AUDIT-C1.5] list_dossier_questions extracted to backend/db/intake.py (IntakeMixin).

    # [AUDIT-C1.5] list_dossier_answers extracted to backend/db/intake.py (IntakeMixin).

    # [AUDIT-C1.5] upsert_dossier_answers extracted to backend/db/intake.py (IntakeMixin).

    # [AUDIT-C1.2] cases batch 6 — dossier case questions/answers extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6b] list_dossier_source_suggestions extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] add_dossier_source_suggestion extracted to backend/db/misc.py (MiscMixin).

    # ------------------------------------------------------------------
    # Guidance packs (Phase 2)
    # ------------------------------------------------------------------
    # [AUDIT-C1.6b] list_knowledge_packs extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] count_knowledge_packs_by_destination extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] ensure_knowledge_pack extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] upsert_knowledge_doc_by_url extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] create_baseline_rule_for_doc extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] list_knowledge_docs extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] list_knowledge_docs_by_destination extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] list_all_knowledge_docs extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] count_knowledge_docs_by_destination extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] count_knowledge_rules_by_destination extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] list_knowledge_rules extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] upsert_requirement_entity extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] insert_requirement_facts extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.3] policies batch 11 — requirement_* adapters
    # (list_requirement_entities, list_requirement_facts,
    # list_requirement_facts_by_destination, list_approved_requirement_facts,
    # update_requirement_fact_status) extracted to backend/db/policies.py
    # (PoliciesMixin). Database inherits them, callers unchanged.

    # [AUDIT-C1.6b] insert_guidance_pack extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] get_latest_guidance_pack extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] insert_rule_evaluation_logs extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] list_rule_evaluation_logs extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6a] list_trace_events extracted to backend/db/audit.py (AuditMixin).

    # [AUDIT-C1.6a] insert_trace_event extracted to backend/db/audit.py (AuditMixin).

    # ------------------------------------------------------------------
    # HR Command Center
    # ------------------------------------------------------------------
    # [AUDIT-C1.2] cases batch 13c — command-center join helpers extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.5] _command_center_dest_country_sql extracted to backend/db/hr.py (HrMixin).

    # [AUDIT-C1.5] _command_center_base_join extracted to backend/db/hr.py (HrMixin).

    # [AUDIT-C1.5] _command_center_display_status extracted to backend/db/hr.py (HrMixin).

    # [AUDIT-C1.5] _command_center_company_where extracted to backend/db/hr.py (HrMixin).

    # [AUDIT-C1.5] get_command_center_kpis extracted to backend/db/hr.py (HrMixin).

    # [AUDIT-C1.2] cases batch 8 — command-center cases + delete_assignment extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.4] create_assignment_invite extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] create_assignment_claim_invite extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] get_pending_claim_invite_token_for_assignment extracted to backend/db/auth.py (AuthMixin).

    # [AUDIT-C1.4] ensure_pending_assignment_invites extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] mark_invites_claimed extracted to backend/db/users.py (UsersMixin).

    # ==================================================================
    # Employee journey data
    # ==================================================================
    # [AUDIT-C1.5] save_employee_answer extracted to backend/db/intake.py (IntakeMixin).

    # [AUDIT-C1.5] get_employee_answers extracted to backend/db/intake.py (IntakeMixin).

    # [AUDIT-C1.4] save_employee_profile extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] get_employee_profile extracted to backend/db/users.py (UsersMixin).

    # ==================================================================
    # Compliance reports
    # ==================================================================
    # [AUDIT-C1.6a] save_compliance_report extracted to backend/db/audit.py (AuditMixin).

    # [AUDIT-C1.6a] get_latest_compliance_report extracted to backend/db/audit.py (AuditMixin).

    # [AUDIT-C1.6a] save_compliance_run extracted to backend/db/audit.py (AuditMixin).

    # [AUDIT-C1.6a] get_latest_compliance_run extracted to backend/db/audit.py (AuditMixin).

    # ==================================================================
    # Policy exceptions
    # ==================================================================
    # [AUDIT-C1.6a] list_policy_exceptions extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] create_policy_exception extracted to backend/db/policies.py (PoliciesMixin).

    # ==================================================================
    # Compliance actions
    # ==================================================================
    # [AUDIT-C1.6a] create_compliance_action extracted to backend/db/audit.py (AuditMixin).

    # [AUDIT-C1.6a] list_compliance_actions extracted to backend/db/audit.py (AuditMixin).

    # ==================================================================
    # Admin console operations
    # ==================================================================
    # [AUDIT-C1.4] ensure_profile_record extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] get_profile_record extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] get_profile_by_email extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] set_profile_company extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] update_profile extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] set_profile_role extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] deactivate_profile extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] create_profile extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] get_company_for_user extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.5] get_hr_company_id extracted to backend/db/hr.py (HrMixin).

    # [AUDIT-C1.4] sync_hr_user_company_from_profile extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] list_profiles extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] backfill_profiles_to_test_company extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.6a] backfill_assignments_to_test_company extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.4] ensure_test_company_has_hr_user extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] add_admin_allowlist extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] is_admin_allowlisted extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.6a] log_audit extracted to backend/db/audit.py (AuditMixin).

    # [AUDIT-C1.6a] list_companies extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] get_company extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] get_company_by_name extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] find_or_create_company_by_name extracted to backend/db/companies.py (CompaniesMixin).

    TEST_COMPANY_FIXED_ID = "110854ad-3c85-4291-a484-0b43effb680e"

    # [AUDIT-C1.6a] run_admin_reconciliation_backfill_test_company extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] rebuild_test_company_graph extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] create_company extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] update_company extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] deactivate_company extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] archive_company extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] delete_company_hard extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] update_company_logo extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6b] create_employee extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.4] create_hr_user extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] ensure_hr_user_for_profile extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] ensure_hr_users_for_company extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] ensure_employee_for_profile extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] assign_employee_profile_to_company_directory extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.6a] ensure_directory_from_assignments_for_company extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] ensure_employees_for_company extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.2] cases batch 7a — relocation/support case upserts extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6b] list_employees extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.4] list_employees_with_profiles extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.6a] get_employee_for_company extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.4] get_employee_by_profile_for_company extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.6b] update_employee_limited extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6a] delete_employee_for_company extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.4] list_hr_users extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.4] list_hr_users_with_profiles extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.2] cases batch 7b — relocation/support case reads extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6a] add_support_note extracted to backend/db/support.py (SupportMixin).

    # [AUDIT-C1.6a] list_support_notes extracted to backend/db/support.py (SupportMixin).

    # [AUDIT-C1.6a] create_message extracted to backend/db/support.py (SupportMixin).

    # [AUDIT-C1.5] list_messages_for_hr extracted to backend/db/hr.py (HrMixin).

    # [AUDIT-C1.6a] upsert_message_conversation_pref extracted to backend/db/support.py (SupportMixin).

    # [AUDIT-C1.6a] get_message_by_id extracted to backend/db/support.py (SupportMixin).

    # [AUDIT-C1.6a] delete_message_by_id extracted to backend/db/support.py (SupportMixin).

    # [AUDIT-C1.5] list_hr_conversation_summaries extracted to backend/db/hr.py (HrMixin).

    # [AUDIT-C1.6a] list_messages_for_employee extracted to backend/db/support.py (SupportMixin).

    # [AUDIT-C1.6a] _vendor_names_for_rfq extracted to backend/db/vendors.py (VendorsMixin).

    # [AUDIT-C1.6a] list_quote_threads_for_employee extracted to backend/db/vendors.py (VendorsMixin).

    # [AUDIT-C1.6b] mark_conversation_read extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6a] dismiss_message_notification extracted to backend/db/support.py (SupportMixin).

    # [AUDIT-C1.6a] get_unread_message_count extracted to backend/db/support.py (SupportMixin).

    # [AUDIT-C1.6b] list_admin_message_threads extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.2] cases batch 13f extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6a] list_unread_message_notifications extracted to backend/db/support.py (SupportMixin).

    # [AUDIT-C1.4] set_admin_session extracted to backend/db/auth.py (AuthMixin).

    # [AUDIT-C1.4] clear_admin_session extracted to backend/db/auth.py (AuthMixin).

    # [AUDIT-C1.4] get_admin_session extracted to backend/db/auth.py (AuthMixin).

    # [AUDIT-C1.6b] create_eligibility_override extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.2] cases batch 10a extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6a] create_hr_policy extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] update_hr_policy extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] get_hr_policy extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] list_hr_policies extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] list_hr_policies_by_company extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] get_published_hr_policy_for_employee extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] delete_hr_policy extracted to backend/db/policies.py (PoliciesMixin).

    # ==================================================================
    # Company policy documents + extracted benefits
    # ==================================================================
    # [AUDIT-C1.6a] run_policy_normalization_transaction extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] create_company_policy extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] list_company_policies extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] list_admin_policy_overview extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] get_admin_policies_by_company extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] get_admin_policy_detail extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] list_default_policy_templates extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] get_default_policy_template extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] apply_default_template_to_company extracted to backend/db/companies.py (CompaniesMixin).

    # -------------------------------------------------------------------------
    # Admin read model: normalized indexes and data-integrity
    # -------------------------------------------------------------------------

    # [AUDIT-C1.6a] get_admin_company_index extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.4] get_admin_people_index extracted to backend/db/users.py (UsersMixin).

    # [AUDIT-C1.2] cases batch 13g extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6a] get_admin_policies_index extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6b] get_data_integrity_overview extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.3] policies batch 9 — company_policies reads/writes
    # (get_company_policy, get_latest_company_policy,
    # get_company_policy_with_published_version, list_company_ids_with_published_policy,
    # update_company_policy_status, update_company_policy_meta) extracted to
    # backend/db/policies.py (PoliciesMixin). Database inherits them, callers unchanged.

    # [AUDIT-C1.6a] list_company_preferred_suppliers extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] add_company_preferred_supplier extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] remove_company_preferred_supplier extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.3] policies batch 10 — policy_documents (upload/intake) CRUD
    # (create_policy_document, get_active_policy_document_by_checksum,
    # get_policy_document, list_policy_documents, update_policy_document) extracted
    # to backend/db/policies.py (PoliciesMixin; create_policy_document lazy-imports
    # _is_sqlite; get/list use the deeper ..app.services import path). Database
    # inherits them, callers unchanged.

    # [AUDIT-C1.6a] policy_assistant_tables_available extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] clear_policy_assistant_pipeline_for_document extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] insert_policy_processing_run extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] finish_policy_processing_run extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] insert_policy_document_chunk extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.3] policies batch 12 — policy knowledge snapshots / document chunks
    # (list_policy_document_chunks, list_policy_document_chunks_for_snapshot,
    # insert_policy_knowledge_snapshot, update_policy_knowledge_snapshot,
    # supersede_active_snapshots_for_company) extracted to backend/db/policies.py
    # (PoliciesMixin; chunk listers lazy-import module-level _coerce_json_dict; the
    # sibling policy_assistant_tables_available stays here, resolved via MRO).
    # Database inherits them, callers unchanged.

    # [AUDIT-C1.3] policies batch 13 — policy_facts + assistant-binding reads
    # (insert_policy_fact, count_policy_document_chunks, count_policy_facts_for_snapshot,
    # policy_fact_counts_by_type, list_policy_facts_for_snapshot,
    # get_policy_document_chunks_by_ids, get_company_policy_assistant_binding) extracted
    # to backend/db/policies.py (PoliciesMixin; insert_policy_fact lazy-imports _is_sqlite,
    # the json-coercing readers lazy-import _coerce_json_dict; sibling
    # policy_assistant_tables_available stays here). Database inherits them, callers unchanged.

    # [AUDIT-C1.3] policies batch 14 — assistant-binding upsert + knowledge-snapshot getters
    # (upsert_company_policy_assistant_binding, get_active_policy_knowledge_snapshot_for_company,
    # get_latest_policy_knowledge_snapshot_for_document, count_policy_facts_for_document_via_snapshots,
    # policy_hardening_tables_available, get_policy_knowledge_snapshot_by_id,
    # next_snapshot_revision_number) extracted to backend/db/policies.py (PoliciesMixin;
    # upsert + hardening-check lazy-import _is_sqlite). Database inherits them, callers unchanged.

    # [AUDIT-C1.3] policies batch 15 — snapshot activation + extraction locks
    # (activate_policy_knowledge_snapshot, mark_policy_snapshot_failed,
    # try_acquire_policy_extraction_lock, release_policy_extraction_lock) extracted
    # to backend/db/policies.py (PoliciesMixin). Sibling guards/upsert resolve via
    # MRO. Database inherits them, callers unchanged.

    # [AUDIT-C1.6a] canonical_policy_tables_available extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] insert_canonical_policy_document extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] update_canonical_policy_document extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] get_canonical_policy_document extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] list_canonical_policy_documents extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] delete_canonical_policy_artifacts extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] insert_canonical_policy_document_chunk extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] list_canonical_policy_document_chunks extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] insert_canonical_policy_fact extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] list_canonical_policy_facts extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] insert_canonical_policy_validation_error extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] list_canonical_policy_validation_errors extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] get_canonical_policy_audit_summary extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] get_active_canonical_policy_document_for_company extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] insert_canonical_policy_query_audit_log extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] list_canonical_policy_query_audit_logs extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.5] insert_policy_assistant_answer_audit extracted to backend/db/intake.py (IntakeMixin).

    # [P5-8] AI Trace Logger — write one trace row per RAG engine call.
    # [AUDIT-C1.6a] insert_policy_assistant_trace extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6b] get_answer_provenance_rollup extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.5] list_policy_assistant_answer_audits extracted to backend/db/intake.py (IntakeMixin).

    # [AUDIT-C1.6a] list_policy_knowledge_snapshots_for_document extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] list_policy_knowledge_snapshots_for_company extracted to backend/db/companies.py (CompaniesMixin).

    # [AUDIT-C1.6a] list_policy_processing_runs_for_document extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] latest_policy_processing_run extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.3] policies batch 3 — policy_documents/clauses CRUD
    # (policy_version_references_document, delete_policy_document,
    # delete_policy_document_clauses, upsert_policy_document_clauses,
    # list_policy_document_clauses, get_policy_document_clause,
    # update_policy_document_clause) extracted to backend/db/policies.py
    # (PoliciesMixin). Database inherits them, callers unchanged.

    # ==================================================================
    # Policy normalization (canonical policy objects)
    # ==================================================================

    # [AUDIT-C1.6a] _coerce_policy_boolean_fields extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.3] policies batch 4 — create_policy_version extracted to
    # backend/db/policies.py (PoliciesMixin); it lazy-imports the module-level
    # _policy_ag_sql / _policy_bool_bind / normalize_policy_boolean_fields helpers
    # (which remain here). Database inherits it, callers unchanged.
    # NOTE: the _coerce_policy_boolean_fields staticmethod above is pre-existing
    # dead code (no callers) — left in place per surgical-change discipline.

    # [AUDIT-C1.3] policies batch 2 — policy_versions lifecycle (get_latest/get_published/
    # update_status/archive_other/archive_all/get/list/list_by_source/
    # _decode_policy_version_row/update_normalization_draft) extracted to
    # backend/db/policies.py (PoliciesMixin). Database inherits them, callers unchanged.

    # [AUDIT-C1.6b] _parse_json_col extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.3] policies batch 1 — list_policy_benefit_rules, list_policy_exclusions,
    # list_policy_evidence_requirements, list_policy_rule_conditions,
    # list_policy_family_applicability, list_policy_tier_overrides extracted to
    # backend/db/policies.py (PoliciesMixin). Database inherits them, callers unchanged.

    # [AUDIT-C1.2] cases batch 10b extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6a] list_hr_benefit_rule_overrides extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] get_hr_benefit_rule_override extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] upsert_hr_benefit_rule_override extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] _append_hr_benefit_rule_override_audit extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] delete_hr_benefit_rule_override extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] list_policy_source_links extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] insert_policy_benefit_rule extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] insert_policy_exclusion extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] insert_policy_evidence_requirement extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] insert_policy_rule_condition extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.2] cases batch 10c extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6a] insert_policy_family_applicability extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] insert_policy_source_link extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.3] policies batch 5 — benefit-rule/exclusion/condition writers +
    # get_policy_benefit_rule, list_policy_benefits, replace_policy_benefits
    # extracted to backend/db/policies.py (PoliciesMixin). Database inherits them,
    # callers unchanged.

    # ==================================================================
    # Resolved assignment policies
    # ==================================================================
    # [AUDIT-C1.2] cases batch 9a extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6a] list_resolved_policy_benefits extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] list_resolved_policy_exclusions extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.2] cases batch 9b extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6b] _readiness_store_available extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] seed_readiness_templates_if_empty extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] ensure_missing_readiness_templates extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] get_readiness_template extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.2] cases batch 9c extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.5] get_hr_readiness_summary extracted to backend/db/hr.py (HrMixin).

    # [AUDIT-C1.5] get_hr_readiness_detail extracted to backend/db/hr.py (HrMixin).

    # [AUDIT-C1.6b] upsert_readiness_checklist_state extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.2] cases batch 9d extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.3] policies batch 6 — policy_config + config-version reads/writes
    # (_normalize_policy_config_benefit_row, get_policy_config, ensure_policy_config,
    # get_policy_config_version_row, get_policy_config_version_with_config,
    # archive_policy_config_drafts, max_policy_config_version_number,
    # insert_policy_config_version) extracted to backend/db/policies.py
    # (PoliciesMixin; ensure_policy_config lazy-imports module-level _is_sqlite).
    # Database inherits them, callers unchanged.

    # [AUDIT-C1.3] policies batch 7 — policy_config benefit rows
    # (list_policy_config_benefits, delete_policy_config_benefits_for_version,
    # delete_policy_config_benefit_by_key, insert_policy_config_benefit_row)
    # extracted to backend/db/policies.py (PoliciesMixin;
    # insert_policy_config_benefit_row lazy-imports module-level _is_sqlite).
    # Database inherits them, callers unchanged.

    # [AUDIT-C1.6a] insert_policy_config_benefit_audit_row extracted to backend/db/policies.py (PoliciesMixin).

    # ------------------------------------------------------------------
    # Section C: jurisdiction overrides on policy_config_benefits rows.
    # See supabase/migrations/20260502100000_policy_benefit_jurisdiction_overrides.sql
    # and services/policy_section_c_resolver.py.
    # ------------------------------------------------------------------

    # [AUDIT-C1.6a] list_jurisdiction_overrides_for_benefit_rows extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.6a] replace_jurisdiction_overrides_for_benefit extracted to backend/db/policies.py (PoliciesMixin).

    # [AUDIT-C1.3] policies batch 8 — policy_config_version publish/draft/history
    # (publish_policy_config_version_atomic, get_latest_published_policy_config_version,
    # get_policy_config_draft_for_config, list_policy_config_versions_history,
    # update_policy_config_version_effective_date) extracted to backend/db/policies.py
    # (PoliciesMixin). Database inherits them, callers unchanged.

    # [AUDIT-C1.6a] get_company_id_for_assignment_id extracted to backend/db/companies.py (CompaniesMixin).

    # ==================================================================
    # Debug KV operations
    # ==================================================================
    # [AUDIT-C1.6b] debug_kv_set extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6b] debug_kv_get extracted to backend/db/misc.py (MiscMixin).

    # ==================================================================
    # Debug: DB info
    # ==================================================================
    # [AUDIT-C1.6b] get_db_info extracted to backend/db/misc.py (MiscMixin).

    # [AUDIT-C1.6a] log_expected_tables_status extracted to backend/db/audit.py (AuditMixin).

    # ------------------------------------------------------------------
    # Provider Status Grid  (AIQ-14)
    # ------------------------------------------------------------------

    # [AUDIT-C1.6a] get_provider_status_grid extracted to backend/db/vendors.py (VendorsMixin).

    # ------------------------------------------------------------------
    # Employee Task Portal (AIQ-34-B)
    # ------------------------------------------------------------------

    # [AUDIT-C1.6a] list_employee_tasks extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6a] get_employee_task extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6a] submit_employee_task extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6a] review_employee_task extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6a] create_employee_task_for_case extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.6a] list_employee_tasks_for_case_hr extracted to backend/db/cases.py (CasesMixin).

    # [AUDIT-C1.5] list_hr_backlog extracted to backend/db/hr.py (HrMixin).


# Global database instance
db = Database()
