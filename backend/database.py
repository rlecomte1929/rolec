"""
Unified database layer — works with both SQLite and Postgres.
Uses DATABASE_URL from db_config (single source of truth).
"""
import json
import os
import math
import uuid
import logging
import time
from typing import Optional, Dict, Any, List, Tuple, Set
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from .db_config import DATABASE_URL as _raw_url, sqlalchemy_engine_kwargs
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
# Debug-mode instrumentation for admin company/people/assignment flows
# ---------------------------------------------------------------------------
#region agent log
def _agent_debug_log(
    hypothesis_id: str,
    location: str,
    message: str,
    data: Dict[str, Any],
    run_id: str = "pre-fix",
) -> None:
    """
    Lightweight NDJSON logger for this debug session.
    Writes to .cursor/debug-2d9978.log; failures are swallowed.
    """
    try:
        payload = {
            "sessionId": "2d9978",
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
        }
        log_path = "/Users/Rom/Documents/GitHub/rolec/.cursor/debug-2d9978.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception:
        # Never let debug logging break the app.
        return
#endregion

# ---------------------------------------------------------------------------
# Engine setup (shared logic with backend/app/db.py)
# ---------------------------------------------------------------------------
_engine = create_engine(_raw_url, **sqlalchemy_engine_kwargs(_raw_url))

_is_sqlite = _raw_url.startswith("sqlite")

if _is_sqlite:
    from sqlalchemy import event

    @event.listens_for(_engine, "connect")
    def _sqlite_enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        """Enforce REFERENCES clauses on SQLite (off by default)."""
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


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
    return f"rc.id::text = {rhs}"


def _eq_text(lhs_sql: str, rhs_sql: str) -> str:
    """Cross-type-safe equality for ids (Postgres uuid vs text on messages / assignments / prefs). SQLite: CAST is harmless."""
    return f"CAST({lhs_sql} AS TEXT) = CAST({rhs_sql} AS TEXT)"


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


def _policy_bool_for_db(value: Any) -> int:
    """Return 1 or 0 for policy_* boolean columns. Use with _policy_ag_sql() in INSERTs for dialect-safe behavior."""
    b = bool(value) if value is not None else True
    return 1 if b else 0


def _policy_ag_sql() -> str:
    """SQL fragment for auto_generated column: plain :ag for SQLite (INTEGER), CASE for Postgres (boolean)."""
    if _is_sqlite:
        return ":ag"
    return "(CASE WHEN :ag = 1 THEN true ELSE false END)"


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
        out[k] = _policy_bool_for_db(v)
    return out


def _auto_id_col() -> str:
    """Return the DDL fragment for an auto-incrementing integer PK."""
    if _is_sqlite:
        return "INTEGER PRIMARY KEY AUTOINCREMENT"
    return "SERIAL PRIMARY KEY"


class Database:
    def __init__(self) -> None:
        self.engine = _engine
        # None = unknown; False = readiness_templates not available (migration not applied / wrong DB)
        self._readiness_store_cache: Optional[bool] = None
        self.init_db()

    def _exec(
        self,
        conn,
        sql: str,
        params: Dict[str, Any],
        op_name: str,
        request_id: Optional[str] = None,
    ):
        """
        Execute a SQL statement with basic timing and optional request correlation.
        """
        start = time.perf_counter()
        result = conn.execute(text(sql), params)
        dur_ms = (time.perf_counter() - start) * 1000
        if request_id:
            log.info("request_id=%s db_op=%s dur_ms=%.2f", request_id, op_name, dur_ms)
        else:
            log.info("db_op=%s dur_ms=%.2f", op_name, dur_ms)
        return result

    def _db_healthcheck(self, conn) -> None:
        info = Database.get_db_info()
        host = info.get("db_host") or "(local)"
        log.info("DB healthcheck: scheme=%s host=%s", info.get("db_url_scheme"), host)
        conn.execute(text("SELECT 1"))

    def _maybe_ensure_postgres_missing_schemas(self) -> None:
        """
        If core public tables are missing (migrations not applied), apply idempotent DDL.

        Covers: employee_contacts / claim invites (identity) and case_milestones / milestone_links (timeline).
        """
        if _is_sqlite:
            return
        need_identity = False
        need_timeline = False
        try:
            with self.engine.connect() as c:
                r1 = c.execute(
                    text(
                        "SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name = 'employee_contacts'"
                    )
                ).fetchone()
                r2 = c.execute(
                    text(
                        "SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name = 'case_milestones'"
                    )
                ).fetchone()
                r3 = c.execute(
                    text(
                        "SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name = 'milestone_links'"
                    )
                ).fetchone()
            need_identity = not r1
            need_timeline = not r2 or not r3
        except Exception as ex:
            log.warning("postgres schema presence check skipped: %s", ex)
            return
        if not need_identity and not need_timeline:
            return
        if need_identity:
            log.info(
                "public.employee_contacts missing — applying canonical identity DDL (idempotent). "
                "Prefer running Supabase migrations for production."
            )
        if need_timeline:
            log.info(
                "public.case_milestones and/or milestone_links missing — applying timeline DDL (idempotent). "
                "Prefer running Supabase migrations for production."
            )
        try:
            with self.engine.begin() as conn:
                if need_identity:
                    self._ensure_postgres_canonical_identity_schema(conn)
                if need_timeline:
                    self._ensure_postgres_case_milestones_schema(conn)
        except Exception:
            log.exception("Failed to ensure postgres missing schemas")

    def _ensure_postgres_canonical_identity_schema(self, conn) -> None:
        """Run inside a transaction; Postgres only. See _maybe_ensure_postgres_missing_schemas."""
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.employee_contacts (
                  id text PRIMARY KEY,
                  company_id text NOT NULL REFERENCES public.companies(id) ON DELETE RESTRICT,
                  invite_key text NOT NULL,
                  email_normalized text,
                  first_name text,
                  last_name text,
                  linked_auth_user_id text REFERENCES public.users(id) ON DELETE SET NULL,
                  created_at timestamptz NOT NULL DEFAULT now(),
                  updated_at timestamptz NOT NULL DEFAULT now(),
                  CONSTRAINT employee_contacts_company_invite_unique UNIQUE (company_id, invite_key)
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_employee_contacts_company "
                "ON public.employee_contacts(company_id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_employee_contacts_invite_key "
                "ON public.employee_contacts(invite_key)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_employee_contacts_linked_user "
                "ON public.employee_contacts(linked_auth_user_id)"
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.assignment_claim_invites (
                  id text PRIMARY KEY,
                  assignment_id text NOT NULL REFERENCES public.case_assignments(id) ON DELETE CASCADE,
                  employee_contact_id text NOT NULL REFERENCES public.employee_contacts(id) ON DELETE CASCADE,
                  email_normalized text,
                  token text NOT NULL,
                  status text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'claimed', 'revoked')),
                  claimed_by_user_id text REFERENCES public.users(id) ON DELETE SET NULL,
                  claimed_at timestamptz,
                  created_at timestamptz NOT NULL DEFAULT now(),
                  CONSTRAINT assignment_claim_invites_token_unique UNIQUE (token)
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_assignment_claim_invites_assignment "
                "ON public.assignment_claim_invites(assignment_id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_assignment_claim_invites_contact "
                "ON public.assignment_claim_invites(employee_contact_id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_assignment_claim_invites_status "
                "ON public.assignment_claim_invites(status)"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE public.case_assignments "
                "ADD COLUMN IF NOT EXISTS employee_contact_id text "
                "REFERENCES public.employee_contacts(id) ON DELETE SET NULL"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_case_assignments_employee_contact "
                "ON public.case_assignments(employee_contact_id)"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE public.case_assignments "
                "ADD COLUMN IF NOT EXISTS employee_link_mode text"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_case_assignments_employee_link_mode "
                "ON public.case_assignments(employee_link_mode) "
                "WHERE employee_user_id IS NULL AND employee_link_mode IS NOT NULL"
            )
        )
        try:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_employee_contacts_company_email_unique "
                    "ON public.employee_contacts (company_id, email_normalized) "
                    "WHERE email_normalized IS NOT NULL AND trim(email_normalized) <> ''"
                )
            )
        except (OperationalError, ProgrammingError) as ex:
            log.warning("idx_employee_contacts_company_email_unique skipped: %s", ex)
        try:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_assignment_claim_invites_one_pending_per_assignment "
                    "ON public.assignment_claim_invites (assignment_id) "
                    "WHERE status = 'pending'"
                )
            )
        except (OperationalError, ProgrammingError) as ex:
            log.warning("idx_assignment_claim_invites_one_pending_per_assignment skipped: %s", ex)
        try:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_assignment_claim_invites_assignment_status "
                    "ON public.assignment_claim_invites (assignment_id, status)"
                )
            )
        except (OperationalError, ProgrammingError) as ex:
            log.warning("idx_assignment_claim_invites_assignment_status skipped: %s", ex)
        try:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_employee_contacts_email_normalized "
                    "ON public.employee_contacts (email_normalized) "
                    "WHERE email_normalized IS NOT NULL AND trim(email_normalized) <> ''"
                )
            )
        except (OperationalError, ProgrammingError) as ex:
            log.warning("idx_employee_contacts_email_normalized skipped: %s", ex)
        try:
            conn.execute(text("ALTER TABLE public.employee_contacts ENABLE ROW LEVEL SECURITY"))
            conn.execute(text("DROP POLICY IF EXISTS employee_contacts_all ON public.employee_contacts"))
            conn.execute(
                text(
                    "CREATE POLICY employee_contacts_all ON public.employee_contacts "
                    "FOR ALL TO service_role USING (true) WITH CHECK (true)"
                )
            )
        except (OperationalError, ProgrammingError) as ex:
            log.warning("employee_contacts RLS/policy skipped: %s", ex)
        try:
            conn.execute(text("ALTER TABLE public.assignment_claim_invites ENABLE ROW LEVEL SECURITY"))
            conn.execute(text("DROP POLICY IF EXISTS assignment_claim_invites_all ON public.assignment_claim_invites"))
            conn.execute(
                text(
                    "CREATE POLICY assignment_claim_invites_all ON public.assignment_claim_invites "
                    "FOR ALL TO service_role USING (true) WITH CHECK (true)"
                )
            )
        except (OperationalError, ProgrammingError) as ex:
            log.warning("assignment_claim_invites RLS/policy skipped: %s", ex)

    def _ensure_postgres_case_milestones_schema(self, conn) -> None:
        """Postgres timeline tables (text ids, aligned with app inserts). See supabase/migrations/20260325000000_*."""
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.case_milestones (
                  id text PRIMARY KEY,
                  case_id text NOT NULL,
                  canonical_case_id text,
                  milestone_type text NOT NULL,
                  title text NOT NULL,
                  description text,
                  target_date date,
                  actual_date date,
                  status text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','in_progress','done','skipped','overdue','blocked')),
                  sort_order int NOT NULL DEFAULT 0,
                  created_at timestamptz NOT NULL DEFAULT now(),
                  updated_at timestamptz NOT NULL DEFAULT now(),
                  owner text NOT NULL DEFAULT 'joint',
                  criticality text NOT NULL DEFAULT 'normal',
                  notes text
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_case_milestones_case_id "
                "ON public.case_milestones(case_id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_case_milestones_canonical "
                "ON public.case_milestones(canonical_case_id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_case_milestones_sort "
                "ON public.case_milestones(case_id, sort_order)"
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.milestone_links (
                  id text PRIMARY KEY,
                  milestone_id text NOT NULL REFERENCES public.case_milestones(id) ON DELETE CASCADE,
                  linked_entity_type text NOT NULL,
                  linked_entity_id text NOT NULL,
                  created_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_milestone_links_milestone "
                "ON public.milestone_links(milestone_id)"
            )
        )
        try:
            conn.execute(text("ALTER TABLE public.case_milestones ENABLE ROW LEVEL SECURITY"))
            conn.execute(text("DROP POLICY IF EXISTS case_milestones_all ON public.case_milestones"))
            conn.execute(
                text(
                    "CREATE POLICY case_milestones_all ON public.case_milestones "
                    "FOR ALL TO service_role USING (true) WITH CHECK (true)"
                )
            )
        except (OperationalError, ProgrammingError) as ex:
            log.warning("case_milestones RLS/policy skipped: %s", ex)
        try:
            conn.execute(text("ALTER TABLE public.milestone_links ENABLE ROW LEVEL SECURITY"))
            conn.execute(text("DROP POLICY IF EXISTS milestone_links_all ON public.milestone_links"))
            conn.execute(
                text(
                    "CREATE POLICY milestone_links_all ON public.milestone_links "
                    "FOR ALL TO service_role USING (true) WITH CHECK (true)"
                )
            )
        except (OperationalError, ProgrammingError) as ex:
            log.warning("milestone_links RLS/policy skipped: %s", ex)

    # ------------------------------------------------------------------
    # Schema creation
    # ------------------------------------------------------------------
    def init_db(self) -> None:
        if not _is_sqlite:
            self._maybe_ensure_postgres_missing_schemas()

        # In production (Render), avoid runtime DDL. Use Supabase migrations instead.
        if not _is_sqlite and os.getenv("DISABLE_RUNTIME_DDL", "").lower() in ("1", "true", "yes"):
            with self.engine.connect() as conn:
                self._db_healthcheck(conn)
            log.info("Runtime DDL disabled via DISABLE_RUNTIME_DDL. Skipping init_db DDL.")
            try:
                self.seed_readiness_templates_if_empty()
            except Exception as e:
                log.warning("readiness template seed skipped: %s", e)
            try:
                self._backfill_employee_contacts()
            except Exception as e:
                log.warning("employee_contacts backfill skipped: %s", e)
            return

        with self.engine.begin() as conn:
            if _is_sqlite:
                self._ensure_users_table_sqlite(conn)
            else:
                self._create_users_table(conn)

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS profile_state (
                    user_id TEXT PRIMARY KEY,
                    profile_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))

            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS answers (
                    id {_auto_id_col()},
                    user_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    answer_json TEXT NOT NULL,
                    is_unknown INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS relocation_cases (
                    id TEXT PRIMARY KEY,
                    hr_user_id TEXT NOT NULL,
                    profile_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS case_assignments (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    hr_user_id TEXT NOT NULL,
                    employee_user_id TEXT,
                    employee_identifier TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    submitted_at TEXT,
                    hr_notes TEXT,
                    decision TEXT
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS assignment_invites (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    hr_user_id TEXT NOT NULL,
                    employee_identifier TEXT NOT NULL,
                    token TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS employee_answers (
                    id {_auto_id_col()},
                    assignment_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    answer_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS employee_profiles (
                    assignment_id TEXT PRIMARY KEY,
                    profile_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS compliance_reports (
                    id TEXT PRIMARY KEY,
                    assignment_id TEXT NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS case_services (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    assignment_id TEXT NOT NULL,
                    service_key TEXT NOT NULL,
                    category TEXT NOT NULL,
                    selected INTEGER NOT NULL DEFAULT 1,
                    estimated_cost REAL,
                    currency TEXT DEFAULT 'EUR',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS company_policies (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    version TEXT,
                    effective_date TEXT,
                    file_url TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    extraction_status TEXT NOT NULL,
                    extracted_at TEXT,
                    created_by TEXT,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_benefits (
                    id TEXT PRIMARY KEY,
                    policy_id TEXT NOT NULL,
                    service_category TEXT NOT NULL,
                    benefit_key TEXT NOT NULL,
                    benefit_label TEXT NOT NULL,
                    eligibility TEXT,
                    limits TEXT,
                    notes TEXT,
                    source_quote TEXT,
                    source_section TEXT,
                    confidence REAL,
                    updated_by TEXT,
                    updated_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS case_service_answers (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    service_key TEXT NOT NULL,
                    answers TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(case_id, service_key)
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS vendors (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    service_types TEXT NOT NULL,
                    countries TEXT NOT NULL,
                    logo_url TEXT,
                    contact_email TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS vendor_users (
                    user_id TEXT PRIMARY KEY,
                    vendor_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS case_vendor_shortlist (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    service_key TEXT NOT NULL,
                    vendor_id TEXT NOT NULL,
                    selected INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS rfqs (
                    id TEXT PRIMARY KEY,
                    rfq_ref TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    created_by_user_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS rfq_items (
                    id TEXT PRIMARY KEY,
                    rfq_id TEXT NOT NULL,
                    service_key TEXT NOT NULL,
                    requirements TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS rfq_recipients (
                    id TEXT PRIMARY KEY,
                    rfq_id TEXT NOT NULL,
                    vendor_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    last_activity_at TEXT
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS quote_conversations (
                    id TEXT PRIMARY KEY,
                    thread_type TEXT NOT NULL,
                    case_id TEXT,
                    rfq_id TEXT,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS quote_participants (
                    conversation_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (conversation_id, user_id)
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS quote_messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    sender_user_id TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS quotes (
                    id TEXT PRIMARY KEY,
                    rfq_id TEXT NOT NULL,
                    vendor_id TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    total_amount REAL NOT NULL,
                    valid_until TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS quote_lines (
                    id TEXT PRIMARY KEY,
                    quote_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    amount REAL NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS compliance_runs (
                    id TEXT PRIMARY KEY,
                    assignment_id TEXT NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_exceptions (
                    id TEXT PRIMARY KEY,
                    assignment_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT,
                    requested_amount REAL,
                    requested_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS compliance_actions (
                    id TEXT PRIMARY KEY,
                    assignment_id TEXT NOT NULL,
                    check_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    notes TEXT,
                    actor_user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS company_preferred_suppliers (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    supplier_id TEXT NOT NULL,
                    service_category TEXT,
                    priority_rank INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'active',
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_company_preferred_suppliers_company
                ON company_preferred_suppliers(company_id)
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_documents (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    uploaded_by_user_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    storage_path TEXT NOT NULL,
                    checksum TEXT,
                    uploaded_at TEXT NOT NULL,
                    processing_status TEXT NOT NULL DEFAULT 'uploaded',
                    detected_document_type TEXT,
                    detected_policy_scope TEXT,
                    version_label TEXT,
                    effective_date TEXT,
                    raw_text TEXT,
                    extraction_error TEXT,
                    extracted_metadata TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_policy_documents_company ON policy_documents(company_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_policy_documents_status ON policy_documents(processing_status)
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_document_clauses (
                    id TEXT PRIMARY KEY,
                    policy_document_id TEXT NOT NULL,
                    section_label TEXT,
                    section_path TEXT,
                    clause_type TEXT NOT NULL DEFAULT 'unknown',
                    title TEXT,
                    raw_text TEXT NOT NULL,
                    normalized_hint_json TEXT,
                    source_page_start INTEGER,
                    source_page_end INTEGER,
                    source_anchor TEXT,
                    confidence REAL DEFAULT 0.5,
                    hr_override_notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (policy_document_id) REFERENCES policy_documents(id)
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_policy_document_clauses_doc
                ON policy_document_clauses(policy_document_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_policy_document_clauses_type
                ON policy_document_clauses(clause_type)
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_versions (
                    id TEXT PRIMARY KEY,
                    policy_id TEXT NOT NULL,
                    source_policy_document_id TEXT,
                    version_number INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'draft',
                    auto_generated INTEGER NOT NULL DEFAULT 0,
                    review_status TEXT DEFAULT 'pending',
                    confidence REAL,
                    created_by TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_benefit_rules (
                    id TEXT PRIMARY KEY,
                    policy_version_id TEXT NOT NULL,
                    benefit_key TEXT NOT NULL,
                    benefit_category TEXT NOT NULL,
                    calc_type TEXT,
                    amount_value REAL,
                    amount_unit TEXT,
                    currency TEXT,
                    frequency TEXT,
                    description TEXT,
                    metadata_json TEXT,
                    auto_generated INTEGER NOT NULL DEFAULT 1,
                    review_status TEXT DEFAULT 'pending',
                    confidence REAL,
                    raw_text TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_rule_conditions (
                    id TEXT PRIMARY KEY,
                    policy_version_id TEXT NOT NULL,
                    object_type TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    condition_type TEXT NOT NULL,
                    condition_value_json TEXT NOT NULL DEFAULT '{}',
                    auto_generated INTEGER NOT NULL DEFAULT 1,
                    review_status TEXT DEFAULT 'pending',
                    confidence REAL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_exclusions (
                    id TEXT PRIMARY KEY,
                    policy_version_id TEXT NOT NULL,
                    benefit_key TEXT,
                    domain TEXT NOT NULL,
                    description TEXT,
                    auto_generated INTEGER NOT NULL DEFAULT 1,
                    review_status TEXT DEFAULT 'pending',
                    confidence REAL,
                    raw_text TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_evidence_requirements (
                    id TEXT PRIMARY KEY,
                    policy_version_id TEXT NOT NULL,
                    benefit_rule_id TEXT,
                    evidence_items_json TEXT NOT NULL DEFAULT '[]',
                    description TEXT,
                    auto_generated INTEGER NOT NULL DEFAULT 1,
                    review_status TEXT DEFAULT 'pending',
                    confidence REAL,
                    raw_text TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_assignment_type_applicability (
                    id TEXT PRIMARY KEY,
                    policy_version_id TEXT NOT NULL,
                    benefit_rule_id TEXT NOT NULL,
                    assignment_type TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_family_status_applicability (
                    id TEXT PRIMARY KEY,
                    policy_version_id TEXT NOT NULL,
                    benefit_rule_id TEXT NOT NULL,
                    family_status TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_tier_overrides (
                    id TEXT PRIMARY KEY,
                    policy_version_id TEXT NOT NULL,
                    benefit_rule_id TEXT NOT NULL,
                    tier_key TEXT NOT NULL,
                    override_limits_json TEXT NOT NULL DEFAULT '{}'
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_source_links (
                    id TEXT PRIMARY KEY,
                    policy_version_id TEXT NOT NULL,
                    object_type TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    clause_id TEXT NOT NULL,
                    source_page_start INTEGER,
                    source_page_end INTEGER,
                    source_anchor TEXT
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_policy_versions_policy ON policy_versions(policy_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_policy_benefit_rules_version ON policy_benefit_rules(policy_version_id)
            """))
            # Policy template source columns (company_policies) + default_policy_templates
            try:
                cols = conn.execute(text("PRAGMA table_info(company_policies)")).fetchall()
                col_names = {r[1] for r in cols}
                for col, ctype in [
                    ("template_source", "TEXT NOT NULL DEFAULT 'company_uploaded'"),
                    ("template_name", "TEXT"),
                    ("is_default_template", "INTEGER NOT NULL DEFAULT 0"),
                ]:
                    if col not in col_names:
                        conn.execute(text(f"ALTER TABLE company_policies ADD COLUMN {col} {ctype}"))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS default_policy_templates (
                        id TEXT PRIMARY KEY,
                        template_name TEXT NOT NULL,
                        version TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'active',
                        is_default_template INTEGER NOT NULL DEFAULT 0,
                        snapshot_json TEXT NOT NULL DEFAULT '{}',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """))
                # Seed one default template if none
                row = conn.execute(text(
                    "SELECT id FROM default_policy_templates WHERE is_default_template = 1 LIMIT 1"
                )).fetchone()
                if not row:
                    _seed_default_policy_template_sqlite(conn)
            except Exception:
                pass
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS resolved_assignment_policies (
                    id TEXT PRIMARY KEY,
                    assignment_id TEXT NOT NULL UNIQUE,
                    case_id TEXT,
                    company_id TEXT NOT NULL,
                    policy_id TEXT NOT NULL,
                    policy_version_id TEXT NOT NULL,
                    canonical_case_id TEXT,
                    resolution_status TEXT NOT NULL DEFAULT 'ok',
                    resolved_at TEXT NOT NULL,
                    resolution_context_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS resolved_assignment_policy_benefits (
                    id TEXT PRIMARY KEY,
                    resolved_policy_id TEXT NOT NULL,
                    benefit_key TEXT NOT NULL,
                    included INTEGER NOT NULL DEFAULT 1,
                    min_value REAL,
                    standard_value REAL,
                    max_value REAL,
                    currency TEXT,
                    amount_unit TEXT,
                    frequency TEXT,
                    approval_required INTEGER NOT NULL DEFAULT 0,
                    evidence_required_json TEXT NOT NULL DEFAULT '[]',
                    exclusions_json TEXT NOT NULL DEFAULT '[]',
                    condition_summary TEXT,
                    source_rule_ids_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS resolved_assignment_policy_exclusions (
                    id TEXT PRIMARY KEY,
                    resolved_policy_id TEXT NOT NULL,
                    benefit_key TEXT,
                    domain TEXT NOT NULL,
                    description TEXT,
                    source_rule_ids_json TEXT NOT NULL DEFAULT '[]'
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_resolved_policies_assignment ON resolved_assignment_policies(assignment_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_resolved_benefits_policy ON resolved_assignment_policy_benefits(resolved_policy_id)
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS rp_debug_kv (
                    id TEXT PRIMARY KEY,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS hr_policies (
                    id TEXT PRIMARY KEY,
                    policy_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    company_entity TEXT,
                    effective_date TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_by TEXT,
                    version INTEGER NOT NULL DEFAULT 1
                )
            """))

            # ------------------------------------------------------------------
            # Admin console tables
            # ------------------------------------------------------------------
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    email TEXT,
                    full_name TEXT,
                    company_id TEXT,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS admin_allowlist (
                    email TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    added_by_user_id TEXT,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id TEXT PRIMARY KEY,
                    actor_user_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT,
                    reason TEXT,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS companies (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    country TEXT,
                    size_band TEXT,
                    address TEXT,
                    phone TEXT,
                    hr_contact TEXT,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS employees (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    band TEXT,
                    assignment_type TEXT,
                    relocation_case_id TEXT,
                    status TEXT,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS hr_users (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    permissions_json TEXT,
                    created_at TEXT NOT NULL
                )
            """))

            # Dynamic dossier (Phase 1)
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS dossier_questions (
                    id TEXT PRIMARY KEY,
                    destination_country TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    question_key TEXT NOT NULL,
                    question_text TEXT NOT NULL,
                    answer_type TEXT NOT NULL,
                    options TEXT,
                    is_mandatory INTEGER NOT NULL DEFAULT 0,
                    applies_if TEXT,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    version INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_dossier_questions_key
                ON dossier_questions (destination_country, question_key, version)
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS dossier_answers (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    answer_json TEXT NOT NULL,
                    answered_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_dossier_answers_unique
                ON dossier_answers (case_id, user_id, question_id)
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS dossier_source_suggestions (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    destination_country TEXT NOT NULL,
                    query TEXT NOT NULL,
                    results TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS dossier_case_questions (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    question_text TEXT NOT NULL,
                    answer_type TEXT NOT NULL,
                    options TEXT,
                    is_mandatory INTEGER NOT NULL DEFAULT 0,
                    sources TEXT,
                    created_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS dossier_case_answers (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    case_question_id TEXT NOT NULL,
                    answer_json TEXT NOT NULL,
                    answered_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_dossier_case_answers_unique
                ON dossier_case_answers (case_id, user_id, case_question_id)
            """))

            # Guidance packs (Phase 2)
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS knowledge_packs (
                    id TEXT PRIMARY KEY,
                    destination_country TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'active',
                    effective_from TEXT,
                    effective_to TEXT,
                    last_verified_at TEXT,
                    created_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS knowledge_docs (
                    id TEXT PRIMARY KEY,
                    pack_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    publisher TEXT,
                    source_url TEXT NOT NULL,
                    text_content TEXT NOT NULL,
                    checksum TEXT,
                    fetched_at TEXT,
                    fetch_status TEXT NOT NULL DEFAULT 'not_fetched',
                    content_excerpt TEXT,
                    content_sha256 TEXT,
                    last_verified_at TEXT,
                    created_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS knowledge_rules (
                    id TEXT PRIMARY KEY,
                    pack_id TEXT NOT NULL,
                    rule_key TEXT NOT NULL,
                    applies_if TEXT,
                    title TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    category TEXT NOT NULL,
                    guidance_md TEXT NOT NULL,
                    citations TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    supersedes_rule_id TEXT,
                    is_baseline INTEGER NOT NULL DEFAULT 0,
                    baseline_priority INTEGER NOT NULL DEFAULT 100,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS relocation_guidance_packs (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    destination_country TEXT NOT NULL,
                    profile_snapshot TEXT NOT NULL,
                    plan TEXT NOT NULL,
                    checklist TEXT NOT NULL,
                    markdown TEXT NOT NULL,
                    sources TEXT NOT NULL,
                    not_covered TEXT NOT NULL,
                    coverage TEXT,
                    guidance_mode TEXT,
                    pack_hash TEXT,
                    rule_set TEXT,
                    created_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS relocation_trace_events (
                    id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    step_name TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    output_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS rule_evaluation_logs (
                    id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    destination_country TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    rule_key TEXT NOT NULL,
                    rule_version INTEGER NOT NULL,
                    pack_id TEXT NOT NULL,
                    pack_version INTEGER NOT NULL,
                    applies_if TEXT,
                    evaluation_result INTEGER NOT NULL,
                    was_baseline INTEGER NOT NULL,
                    injected_for_minimum INTEGER NOT NULL DEFAULT 0,
                    citations TEXT NOT NULL,
                    snapshot_subset TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS requirement_entities (
                    id TEXT PRIMARY KEY,
                    destination_country TEXT NOT NULL,
                    domain_area TEXT NOT NULL,
                    topic_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_requirement_entities_topic
                ON requirement_entities (destination_country, topic_key)
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS requirement_facts (
                    id TEXT PRIMARY KEY,
                    entity_id TEXT NOT NULL,
                    fact_type TEXT NOT NULL,
                    fact_key TEXT NOT NULL,
                    fact_text TEXT NOT NULL,
                    applies_to TEXT NOT NULL,
                    required_fields TEXT NOT NULL,
                    source_doc_id TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    evidence_quote TEXT,
                    confidence TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS requirement_reviews (
                    id TEXT PRIMARY KEY,
                    entity_id TEXT,
                    fact_id TEXT,
                    reviewer_user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL
                )
            """))

            # Ensure coverage column exists for local guidance packs
            try:
                cols = conn.execute(text("PRAGMA table_info(relocation_guidance_packs)")).fetchall()
                col_names = {r[1] for r in cols}
                if "coverage" not in col_names:
                    conn.execute(text("ALTER TABLE relocation_guidance_packs ADD COLUMN coverage TEXT"))
                if "guidance_mode" not in col_names:
                    conn.execute(text("ALTER TABLE relocation_guidance_packs ADD COLUMN guidance_mode TEXT"))
                if "pack_hash" not in col_names:
                    conn.execute(text("ALTER TABLE relocation_guidance_packs ADD COLUMN pack_hash TEXT"))
                if "rule_set" not in col_names:
                    conn.execute(text("ALTER TABLE relocation_guidance_packs ADD COLUMN rule_set TEXT"))
                if "canonical_case_id" not in col_names:
                    conn.execute(text("ALTER TABLE relocation_guidance_packs ADD COLUMN canonical_case_id TEXT"))
            except Exception:
                pass
            for tbl in ("dossier_answers", "dossier_case_questions", "dossier_case_answers", "dossier_source_suggestions", "relocation_trace_events"):
                try:
                    cols = conn.execute(text(f"PRAGMA table_info({tbl})")).fetchall()
                    if not any(c[1] == "canonical_case_id" for c in cols):
                        conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN canonical_case_id TEXT"))
                except Exception:
                    pass
            try:
                cols = conn.execute(text("PRAGMA table_info(knowledge_docs)")).fetchall()
                col_names = {r[1] for r in cols}
                if "fetched_at" not in col_names:
                    conn.execute(text("ALTER TABLE knowledge_docs ADD COLUMN fetched_at TEXT"))
                if "fetch_status" not in col_names:
                    conn.execute(text("ALTER TABLE knowledge_docs ADD COLUMN fetch_status TEXT"))
                if "content_excerpt" not in col_names:
                    conn.execute(text("ALTER TABLE knowledge_docs ADD COLUMN content_excerpt TEXT"))
                if "content_sha256" not in col_names:
                    conn.execute(text("ALTER TABLE knowledge_docs ADD COLUMN content_sha256 TEXT"))
                if "last_verified_at" not in col_names:
                    conn.execute(text("ALTER TABLE knowledge_docs ADD COLUMN last_verified_at TEXT"))
            except Exception:
                pass
            try:
                cols = conn.execute(text("PRAGMA table_info(knowledge_rules)")).fetchall()
                col_names = {r[1] for r in cols}
                if "version" not in col_names:
                    conn.execute(text("ALTER TABLE knowledge_rules ADD COLUMN version INTEGER NOT NULL DEFAULT 1"))
                if "supersedes_rule_id" not in col_names:
                    conn.execute(text("ALTER TABLE knowledge_rules ADD COLUMN supersedes_rule_id TEXT"))
                if "is_baseline" not in col_names:
                    conn.execute(text("ALTER TABLE knowledge_rules ADD COLUMN is_baseline INTEGER NOT NULL DEFAULT 0"))
                if "baseline_priority" not in col_names:
                    conn.execute(text("ALTER TABLE knowledge_rules ADD COLUMN baseline_priority INTEGER NOT NULL DEFAULT 100"))
                if "is_active" not in col_names:
                    conn.execute(text("ALTER TABLE knowledge_rules ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"))
            except Exception:
                pass

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS support_cases (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    created_by_profile_id TEXT NOT NULL,
                    employee_id TEXT,
                    hr_profile_id TEXT,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT,
                    last_error_code TEXT,
                    last_error_context_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS support_case_notes (
                    id TEXT PRIMARY KEY,
                    support_case_id TEXT NOT NULL,
                    author_user_id TEXT NOT NULL,
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    assignment_id TEXT,
                    hr_user_id TEXT,
                    employee_identifier TEXT,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS admin_sessions (
                    token TEXT PRIMARY KEY,
                    actor_user_id TEXT NOT NULL,
                    target_user_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS eligibility_overrides (
                    id TEXT PRIMARY KEY,
                    assignment_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    allowed INTEGER NOT NULL DEFAULT 1,
                    expires_at TEXT,
                    note TEXT,
                    created_by_user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS hr_feedback (
                    id TEXT PRIMARY KEY,
                    assignment_id TEXT NOT NULL,
                    hr_user_id TEXT NOT NULL,
                    employee_user_id TEXT,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    assignment_id TEXT,
                    case_id TEXT,
                    type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    read_at TEXT
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_notifications_user_created "
                "ON notifications(user_id, created_at DESC)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_notifications_user_read "
                "ON notifications(user_id, read_at)"
            ))

            # Message state: delivered_at, read_at, dismissed_at, recipient_user_id, sender_user_id
            if _is_sqlite:
                cols = conn.execute(text("PRAGMA table_info(messages)")).fetchall()
                col_names = {r[1] for r in cols}
                for col in ("delivered_at", "read_at", "dismissed_at", "recipient_user_id", "sender_user_id"):
                    if col not in col_names:
                        conn.execute(text(f"ALTER TABLE messages ADD COLUMN {col} TEXT"))
            else:
                conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS delivered_at TEXT"))
                conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS read_at TEXT"))
                conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS dismissed_at TEXT"))
                conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS recipient_user_id TEXT"))
                conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS sender_user_id TEXT"))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_messages_recipient_unread "
                "ON messages(recipient_user_id, read_at, dismissed_at, created_at DESC)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_messages_assignment_created "
                "ON messages(assignment_id, created_at)"
            ))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS message_conversation_prefs (
                    user_id TEXT NOT NULL,
                    assignment_id TEXT NOT NULL,
                    archived_at TEXT,
                    PRIMARY KEY (user_id, assignment_id)
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_message_conversation_prefs_user "
                "ON message_conversation_prefs(user_id, archived_at)"
            ))

            # Case Readiness Core v1: reusable templates + per-assignment state
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS readiness_templates (
                    id TEXT PRIMARY KEY,
                    destination_key TEXT NOT NULL,
                    route_key TEXT NOT NULL DEFAULT 'employment',
                    route_title TEXT NOT NULL,
                    employee_summary TEXT NOT NULL DEFAULT '',
                    hr_summary TEXT NOT NULL DEFAULT '',
                    internal_notes_hr TEXT,
                    watchouts_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL,
                    UNIQUE(destination_key, route_key)
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_readiness_templates_dest "
                "ON readiness_templates(destination_key)"
            ))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS readiness_template_checklist_items (
                    id TEXT PRIMARY KEY,
                    template_id TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    title TEXT NOT NULL,
                    owner_role TEXT NOT NULL DEFAULT 'employee',
                    required INTEGER NOT NULL DEFAULT 1,
                    depends_on_sort_order INTEGER,
                    notes_employee TEXT,
                    notes_hr TEXT,
                    stable_key TEXT
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_readiness_tmpl_chk_template "
                "ON readiness_template_checklist_items(template_id, sort_order)"
            ))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS readiness_template_milestones (
                    id TEXT PRIMARY KEY,
                    template_id TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    phase TEXT NOT NULL DEFAULT 'general',
                    title TEXT NOT NULL,
                    body_employee TEXT,
                    body_hr TEXT,
                    owner_role TEXT NOT NULL DEFAULT 'hr',
                    relative_timing TEXT
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_readiness_tmpl_ms_template "
                "ON readiness_template_milestones(template_id, sort_order)"
            ))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS case_readiness (
                    assignment_id TEXT PRIMARY KEY,
                    template_id TEXT NOT NULL,
                    destination_key TEXT NOT NULL,
                    route_key TEXT NOT NULL,
                    case_note_hr TEXT,
                    updated_at TEXT NOT NULL
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_case_readiness_template "
                "ON case_readiness(template_id)"
            ))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS case_readiness_checklist_state (
                    assignment_id TEXT NOT NULL,
                    template_checklist_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    notes TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (assignment_id, template_checklist_id)
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_crcs_assignment "
                "ON case_readiness_checklist_state(assignment_id)"
            ))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS case_readiness_milestone_state (
                    assignment_id TEXT NOT NULL,
                    template_milestone_id TEXT NOT NULL,
                    completed_at TEXT,
                    notes TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (assignment_id, template_milestone_id)
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_crms_assignment "
                "ON case_readiness_milestone_state(assignment_id)"
            ))

            # Best-effort schema extensions for relocation_cases
            if _is_sqlite:
                cols = conn.execute(text("PRAGMA table_info(companies)")).fetchall()
                col_names = {r[1] for r in cols}
                if "address" not in col_names:
                    conn.execute(text("ALTER TABLE companies ADD COLUMN address TEXT"))
                if "phone" not in col_names:
                    conn.execute(text("ALTER TABLE companies ADD COLUMN phone TEXT"))
                if "hr_contact" not in col_names:
                    conn.execute(text("ALTER TABLE companies ADD COLUMN hr_contact TEXT"))
                for col in ("legal_name", "website", "hq_city", "industry", "logo_url", "brand_color", "updated_at", "default_destination_country", "support_email", "default_working_location", "status", "plan_tier"):
                    cols = conn.execute(text("PRAGMA table_info(companies)")).fetchall()
                    col_names = {r[1] for r in cols}
                    if col not in col_names:
                        conn.execute(text(f"ALTER TABLE companies ADD COLUMN {col} TEXT"))
                cols = conn.execute(text("PRAGMA table_info(companies)")).fetchall()
                col_names = {r[1] for r in cols}
                for col in ("hr_seat_limit", "employee_seat_limit"):
                    if col not in col_names:
                        conn.execute(text(f"ALTER TABLE companies ADD COLUMN {col} INTEGER"))
                cols = conn.execute(text("PRAGMA table_info(relocation_cases)")).fetchall()
                col_names = {r[1] for r in cols}
                if "company_id" not in col_names:
                    conn.execute(text("ALTER TABLE relocation_cases ADD COLUMN company_id TEXT"))
                if "employee_id" not in col_names:
                    conn.execute(text("ALTER TABLE relocation_cases ADD COLUMN employee_id TEXT"))
                if "status" not in col_names:
                    conn.execute(text("ALTER TABLE relocation_cases ADD COLUMN status TEXT"))
                if "stage" not in col_names:
                    conn.execute(text("ALTER TABLE relocation_cases ADD COLUMN stage TEXT"))
                if "host_country" not in col_names:
                    conn.execute(text("ALTER TABLE relocation_cases ADD COLUMN host_country TEXT"))
                if "home_country" not in col_names:
                    conn.execute(text("ALTER TABLE relocation_cases ADD COLUMN home_country TEXT"))
            else:
                conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS address TEXT"))
                conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS phone TEXT"))
                conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS hr_contact TEXT"))
                for col in ("legal_name", "website", "hq_city", "industry", "logo_url", "brand_color", "updated_at", "default_destination_country", "support_email", "default_working_location", "status", "plan_tier"):
                    conn.execute(text(f"ALTER TABLE companies ADD COLUMN IF NOT EXISTS {col} TEXT"))
                conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS hr_seat_limit INTEGER"))
                conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS employee_seat_limit INTEGER"))
                conn.execute(text("ALTER TABLE relocation_cases ADD COLUMN IF NOT EXISTS company_id TEXT"))
                conn.execute(text("ALTER TABLE relocation_cases ADD COLUMN IF NOT EXISTS employee_id TEXT"))
                conn.execute(text("ALTER TABLE relocation_cases ADD COLUMN IF NOT EXISTS status TEXT"))
                conn.execute(text("ALTER TABLE relocation_cases ADD COLUMN IF NOT EXISTS stage TEXT"))
                conn.execute(text("ALTER TABLE relocation_cases ADD COLUMN IF NOT EXISTS host_country TEXT"))
                conn.execute(text("ALTER TABLE relocation_cases ADD COLUMN IF NOT EXISTS home_country TEXT"))

            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_profiles_email ON profiles(email)"))
            if _is_sqlite:
                cols = conn.execute(text("PRAGMA table_info(profiles)")).fetchall()
                col_names = {r[1] for r in cols}
                if "status" not in col_names:
                    conn.execute(text("ALTER TABLE profiles ADD COLUMN status TEXT DEFAULT 'active'"))
            else:
                conn.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active'"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_support_cases_status ON support_cases(status)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_support_cases_severity ON support_cases(severity)"))
            try:
                cols = conn.execute(text("PRAGMA table_info(support_cases)")).fetchall()
                col_names = {r[1] for r in cols}
                if "priority" not in col_names:
                    conn.execute(text("ALTER TABLE support_cases ADD COLUMN priority TEXT DEFAULT 'medium'"))
                if "assignee_id" not in col_names:
                    conn.execute(text("ALTER TABLE support_cases ADD COLUMN assignee_id TEXT"))
            except Exception:
                pass
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_relocation_cases_status ON relocation_cases(status)"))

            # HR Command Center: risk/budget columns, tasks, case_events
            if _is_sqlite:
                cc_cols = [
                    ("case_assignments", "risk_status", "TEXT"),
                    ("case_assignments", "budget_limit", "REAL"),
                    ("case_assignments", "budget_estimated", "REAL"),
                    ("case_assignments", "expected_start_date", "TEXT"),
                    ("case_assignments", "employee_first_name", "TEXT"),
                    ("case_assignments", "employee_last_name", "TEXT"),
                    ("case_assignments", "canonical_case_id", "TEXT"),
                    ("case_services", "canonical_case_id", "TEXT"),
                    ("case_service_answers", "canonical_case_id", "TEXT"),
                    ("rfqs", "canonical_case_id", "TEXT"),
                    ("quotes", "created_by_user_id", "TEXT"),
                ]
                for tbl, col, typ in cc_cols + [
                    ("case_assignments", "employee_contact_id", "TEXT"),
                    ("case_assignments", "employee_link_mode", "TEXT"),
                ]:
                    try:
                        cols = conn.execute(text(f"PRAGMA table_info({tbl})")).fetchall()
                        if not any(c[1] == col for c in cols):
                            conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN {col} {typ}"))
                    except Exception:
                        pass
            else:
                conn.execute(text("ALTER TABLE case_assignments ADD COLUMN IF NOT EXISTS risk_status TEXT DEFAULT 'green'"))
                conn.execute(text("ALTER TABLE case_assignments ADD COLUMN IF NOT EXISTS budget_limit NUMERIC"))
                conn.execute(text("ALTER TABLE case_assignments ADD COLUMN IF NOT EXISTS budget_estimated NUMERIC"))
                conn.execute(text("ALTER TABLE case_assignments ADD COLUMN IF NOT EXISTS expected_start_date DATE"))
                conn.execute(text("ALTER TABLE case_assignments ADD COLUMN IF NOT EXISTS employee_first_name TEXT"))
                conn.execute(text("ALTER TABLE case_assignments ADD COLUMN IF NOT EXISTS employee_last_name TEXT"))
                conn.execute(text("ALTER TABLE case_assignments ADD COLUMN IF NOT EXISTS canonical_case_id TEXT"))
                conn.execute(text("ALTER TABLE quotes ADD COLUMN IF NOT EXISTS created_by_user_id TEXT"))
                conn.execute(text("ALTER TABLE case_assignments ADD COLUMN IF NOT EXISTS employee_contact_id TEXT"))
                conn.execute(text("ALTER TABLE case_assignments ADD COLUMN IF NOT EXISTS employee_link_mode TEXT"))
            try:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS relocation_tasks (
                        id TEXT PRIMARY KEY, case_id TEXT, assignment_id TEXT, title TEXT,
                        phase TEXT, owner_role TEXT, status TEXT DEFAULT 'todo', due_date TEXT, created_at TEXT
                    )
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS case_events (
                        id TEXT PRIMARY KEY, case_id TEXT, assignment_id TEXT, actor_user_id TEXT,
                        event_type TEXT, description TEXT, created_at TEXT
                    )
                """))
                # Phase 1: payload, actor_principal_id, canonical_case_id for case_events
                if _is_sqlite:
                    for col_name, col_type in [("payload", "TEXT DEFAULT '{}'"), ("actor_principal_id", "TEXT"), ("canonical_case_id", "TEXT")]:
                        try:
                            cols = conn.execute(text("PRAGMA table_info(case_events)")).fetchall()
                            if not any(c[1] == col_name for c in cols):
                                conn.execute(text(f"ALTER TABLE case_events ADD COLUMN {col_name} {col_type}"))
                        except Exception:
                            pass
            except Exception:
                pass
            # Phase 1 Step 2: case_participants (SQLite only; Postgres uses migration)
            if _is_sqlite:
                try:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS case_participants (
                            id TEXT PRIMARY KEY,
                            case_id TEXT NOT NULL,
                            canonical_case_id TEXT,
                            person_id TEXT NOT NULL,
                            role TEXT NOT NULL CHECK (role IN ('relocatee','hr_owner','hr_reviewer','observer')),
                            invited_at TEXT,
                            joined_at TEXT,
                            created_at TEXT NOT NULL DEFAULT (datetime('now')),
                            UNIQUE(case_id, person_id, role)
                        )
                    """))
                    cols = conn.execute(text("PRAGMA table_info(case_participants)")).fetchall()
                    if not any(c[1] == "canonical_case_id" for c in cols):
                        conn.execute(text("ALTER TABLE case_participants ADD COLUMN canonical_case_id TEXT"))
                except Exception:
                    pass
            # Phase 1 Step 3: case_evidence (SQLite only; Postgres uses migration)
            if _is_sqlite:
                try:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS case_evidence (
                            id TEXT PRIMARY KEY,
                            case_id TEXT NOT NULL,
                            canonical_case_id TEXT,
                            assignment_id TEXT,
                            participant_id TEXT,
                            requirement_id TEXT,
                            evidence_type TEXT NOT NULL,
                            file_url TEXT,
                            metadata TEXT NOT NULL DEFAULT '{}',
                            status TEXT NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted','verified','rejected')),
                            submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
                            created_at TEXT NOT NULL DEFAULT (datetime('now'))
                        )
                    """))
                    cols = conn.execute(text("PRAGMA table_info(case_evidence)")).fetchall()
                    if not any(c[1] == "canonical_case_id" for c in cols):
                        conn.execute(text("ALTER TABLE case_evidence ADD COLUMN canonical_case_id TEXT"))
                except Exception:
                    pass
            # Timeline: case_milestones + milestone_links (operational task tracker)
            if _is_sqlite:
                try:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS case_milestones (
                            id TEXT PRIMARY KEY,
                            case_id TEXT NOT NULL,
                            canonical_case_id TEXT,
                            milestone_type TEXT NOT NULL,
                            title TEXT NOT NULL,
                            description TEXT,
                            target_date TEXT,
                            actual_date TEXT,
                            status TEXT NOT NULL DEFAULT 'pending'
                              CHECK (status IN ('pending','in_progress','done','skipped','overdue','blocked')),
                            sort_order INTEGER NOT NULL DEFAULT 0,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            owner TEXT NOT NULL DEFAULT 'joint',
                            criticality TEXT NOT NULL DEFAULT 'normal',
                            notes TEXT
                        )
                    """))
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS milestone_links (
                            id TEXT PRIMARY KEY,
                            milestone_id TEXT NOT NULL,
                            linked_entity_type TEXT NOT NULL,
                            linked_entity_id TEXT NOT NULL,
                            created_at TEXT NOT NULL
                        )
                    """))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_case_milestones_case ON case_milestones(case_id)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_case_milestones_canonical ON case_milestones(canonical_case_id)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_milestone_links_milestone ON milestone_links(milestone_id)"))
                    self._ensure_case_milestones_tracker_sqlite(conn)
                except Exception:
                    pass
            # Analytics: workflow events for observability
            try:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS analytics_events (
                        id TEXT PRIMARY KEY,
                        event_name TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_analytics_events_name ON analytics_events(event_name)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_analytics_events_created ON analytics_events(created_at)"))
            except Exception:
                pass
            # Canonical identity: employee contacts (pre-auth) + assignment claim invites
            try:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS employee_contacts (
                        id TEXT PRIMARY KEY,
                        company_id TEXT NOT NULL,
                        invite_key TEXT NOT NULL,
                        email_normalized TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        linked_auth_user_id TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(company_id, invite_key)
                    )
                """))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_employee_contacts_company ON employee_contacts(company_id)"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_employee_contacts_invite_key ON employee_contacts(invite_key)"
                ))
                try:
                    conn.execute(text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS idx_employee_contacts_company_email_unique "
                        "ON employee_contacts(company_id, email_normalized) "
                        "WHERE email_normalized IS NOT NULL AND TRIM(email_normalized) <> ''"
                    ))
                except Exception:
                    pass
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS assignment_claim_invites (
                        id TEXT PRIMARY KEY,
                        assignment_id TEXT NOT NULL,
                        employee_contact_id TEXT NOT NULL,
                        email_normalized TEXT,
                        token TEXT NOT NULL UNIQUE,
                        status TEXT NOT NULL DEFAULT 'pending',
                        claimed_by_user_id TEXT,
                        claimed_at TEXT,
                        created_at TEXT NOT NULL
                    )
                """))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_assignment_claim_invites_a ON assignment_claim_invites(assignment_id)"
                ))
                try:
                    conn.execute(text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS idx_assignment_claim_invites_one_pending_per_assignment "
                        "ON assignment_claim_invites(assignment_id) WHERE status = 'pending'"
                    ))
                except Exception:
                    pass
                try:
                    conn.execute(text(
                        "CREATE INDEX IF NOT EXISTS idx_assignment_claim_invites_assignment_status "
                        "ON assignment_claim_invites(assignment_id, status)"
                    ))
                except Exception:
                    pass
                try:
                    conn.execute(text(
                        "CREATE INDEX IF NOT EXISTS idx_employee_contacts_email_normalized "
                        "ON employee_contacts(email_normalized) "
                        "WHERE email_normalized IS NOT NULL AND TRIM(email_normalized) <> ''"
                    ))
                except Exception:
                    pass
            except Exception:
                pass

        log.info("DB schema ensured (legacy tables) — %s",
                 _raw_url.split("@")[-1] if "@" in _raw_url else _raw_url)

        try:
            self.seed_readiness_templates_if_empty()
        except Exception as e:
            log.warning("readiness template seed skipped: %s", e)

        try:
            self._backfill_employee_contacts()
        except Exception as e:
            log.warning("employee_contacts backfill skipped: %s", e)

    # ------------------------------------------------------------------
    # Users table migration helpers (SQLite only)
    # ------------------------------------------------------------------
    def _ensure_users_table_sqlite(self, conn: Any) -> None:
        row = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        ).fetchone()

        if row is None:
            self._create_users_table(conn)
            return

        cols = conn.execute(text("PRAGMA table_info(users)")).fetchall()
        col_names = {r[1] for r in cols}

        needs_migration = False
        if "username" not in col_names or "password_hash" not in col_names or "role" not in col_names:
            needs_migration = True

        if needs_migration:
            conn.execute(text("ALTER TABLE users RENAME TO users_old"))
            self._create_users_table(conn)
            conn.execute(text(
                "INSERT INTO users (id, email, created_at, role) "
                "SELECT id, email, created_at, 'EMPLOYEE' FROM users_old"
            ))
            conn.execute(text("DROP TABLE users_old"))
            return

        conn.execute(text("UPDATE users SET role = 'EMPLOYEE' WHERE role IS NULL"))

    def _create_users_table(self, conn: Any) -> None:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE,
                email TEXT UNIQUE,
                password_hash TEXT,
                role TEXT NOT NULL,
                name TEXT,
                created_at TEXT NOT NULL
            )
        """))

    # ------------------------------------------------------------------
    # Helper: convert row to dict
    # ------------------------------------------------------------------
    @staticmethod
    def _row_to_dict(row: Any) -> Optional[Dict[str, Any]]:
        if row is None:
            return None
        return dict(row._mapping)

    @staticmethod
    def _rows_to_list(rows: Any) -> List[Dict[str, Any]]:
        return [dict(r._mapping) for r in rows]

    # ==================================================================
    # User operations
    # ==================================================================
    def create_user(
        self,
        user_id: str,
        username: Optional[str],
        email: Optional[str],
        password_hash: str,
        role: str,
        name: Optional[str],
    ) -> bool:
        try:
            with self.engine.begin() as conn:
                conn.execute(text(
                    "INSERT INTO users (id, username, email, password_hash, role, name, created_at) "
                    "VALUES (:id, :username, :email, :password_hash, :role, :name, :created_at)"
                ), {
                    "id": user_id, "username": username, "email": email,
                    "password_hash": password_hash, "role": role, "name": name,
                    "created_at": datetime.utcnow().isoformat(),
                })
            return True
        except IntegrityError:
            return False

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        email_norm = (email or "").strip().lower()
        if not email_norm:
            return None
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM users WHERE LOWER(TRIM(email)) = :email"),
                {"email": email_norm},
            ).fetchone()
        return self._row_to_dict(row)

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        username_norm = (username or "").strip()
        if not username_norm:
            return None
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM users WHERE TRIM(username) = :username"),
                {"username": username_norm},
            ).fetchone()
        return self._row_to_dict(row)

    def get_user_by_identifier(self, identifier: str) -> Optional[Dict[str, Any]]:
        ident = (identifier or "").strip()
        if not ident:
            return None
        ident_lower = ident.lower()
        if "@" in ident_lower:
            return self.get_user_by_email(ident)
        user = self.get_user_by_username(ident)
        if user:
            return user
        return self.get_user_by_email(ident)

    def delete_session_by_token(self, token: str) -> bool:
        """Remove session on logout. Returns True if a row was deleted."""
        with self.engine.begin() as conn:
            result = conn.execute(text("DELETE FROM sessions WHERE token = :token"), {"token": token})
            return result.rowcount > 0

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id}).fetchone()
        return self._row_to_dict(row)

    # ==================================================================
    # Session operations
    # ==================================================================
    def create_session(self, token: str, user_id: str) -> bool:
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO sessions (token, user_id, created_at) VALUES (:token, :user_id, :created_at)"
            ), {"token": token, "user_id": user_id, "created_at": datetime.utcnow().isoformat()})
        return True

    def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT user_id FROM sessions WHERE token = :token"), {"token": token}).fetchone()
        if not row:
            return None
        return self.get_user_by_id(row._mapping["user_id"])

    # ==================================================================
    # Profile operations (legacy)
    # ==================================================================
    def save_profile(self, user_id: str, profile: Dict[str, Any]) -> bool:
        now = datetime.utcnow().isoformat()
        pj = json.dumps(profile)
        with self.engine.begin() as conn:
            existing = conn.execute(
                text("SELECT 1 FROM profile_state WHERE user_id = :uid"), {"uid": user_id}
            ).fetchone()
            if existing:
                conn.execute(text(
                    "UPDATE profile_state SET profile_json = :pj, updated_at = :now WHERE user_id = :uid"
                ), {"pj": pj, "now": now, "uid": user_id})
            else:
                conn.execute(text(
                    "INSERT INTO profile_state (user_id, profile_json, updated_at) VALUES (:uid, :pj, :now)"
                ), {"uid": user_id, "pj": pj, "now": now})
        return True

    def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT profile_json FROM profile_state WHERE user_id = :uid"
            ), {"uid": user_id}).fetchone()
        return json.loads(row._mapping["profile_json"]) if row else None

    # ==================================================================
    # Answer operations (legacy)
    # ==================================================================
    def save_answer(self, user_id: str, question_id: str, answer: Any, is_unknown: bool = False) -> bool:
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO answers (user_id, question_id, answer_json, is_unknown, created_at) "
                "VALUES (:uid, :qid, :aj, :iu, :ca)"
            ), {
                "uid": user_id, "qid": question_id,
                "aj": json.dumps(answer), "iu": 1 if is_unknown else 0,
                "ca": datetime.utcnow().isoformat(),
            })
        return True

    def get_answers(self, user_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT question_id, answer_json, is_unknown FROM answers "
                "WHERE user_id = :uid ORDER BY created_at"
            ), {"uid": user_id}).fetchall()
        return self._rows_to_list(rows)

    # ==================================================================
    # HR cases and assignments
    # ==================================================================
    def create_case(
        self, case_id: str, hr_user_id: str, profile: Dict[str, Any], company_id: Optional[str] = None
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            if company_id is not None:
                conn.execute(text(
                    "INSERT INTO relocation_cases (id, hr_user_id, profile_json, company_id, created_at, updated_at) "
                    "VALUES (:id, :hr, :pj, :cid, :ca, :ua)"
                ), {"id": case_id, "hr": hr_user_id, "pj": json.dumps(profile), "cid": company_id, "ca": now, "ua": now})
            else:
                conn.execute(text(
                    "INSERT INTO relocation_cases (id, hr_user_id, profile_json, created_at, updated_at) "
                    "VALUES (:id, :hr, :pj, :ca, :ua)"
                ), {"id": case_id, "hr": hr_user_id, "pj": json.dumps(profile), "ca": now, "ua": now})

    def get_case_by_id(self, case_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM relocation_cases WHERE id = :id"), {"id": case_id}).fetchone()
        return self._row_to_dict(row)

    def resolve_canonical_case_id(self, case_id: str) -> Optional[str]:
        """If case_id matches wizard_cases.id, return it (canonical). Else return None."""
        if not case_id or not case_id.strip():
            return None
        try:
            with self.engine.connect() as conn:
                row = conn.execute(
                    text("SELECT id FROM wizard_cases WHERE id = :cid LIMIT 1"),
                    {"cid": case_id.strip()},
                ).fetchone()
            return str(row["id"]) if row else None
        except Exception:
            return None

    def coalesce_case_lookup_id(self, case_id: str) -> str:
        """Prefer canonical when resolvable (exists in wizard_cases), else return original."""
        canonical = self.resolve_canonical_case_id(case_id)
        return canonical if canonical is not None else (case_id or "")

    def create_assignment(
        self,
        assignment_id: str,
        case_id: str,
        hr_user_id: str,
        employee_user_id: Optional[str],
        employee_identifier: str,
        status: str,
        request_id: Optional[str] = None,
        employee_first_name: Optional[str] = None,
        employee_last_name: Optional[str] = None,
        employee_contact_id: Optional[str] = None,
        employee_link_mode: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        efn = (employee_first_name or "").strip() or None
        eln = (employee_last_name or "").strip() or None
        ecid_check = (employee_contact_id or "").strip() if employee_contact_id else None
        if ecid_check:
            ec_row = self.get_employee_contact_by_id(ecid_check, request_id=request_id)
            if not ec_row:
                raise ValueError(f"employee_contact_id not found: {ecid_check}")
        elm = (employee_link_mode or "").strip() or None
        with self.engine.begin() as conn:
            self._exec(
                conn,
                "INSERT INTO case_assignments "
                "(id, case_id, canonical_case_id, hr_user_id, employee_user_id, employee_identifier, status, "
                "employee_first_name, employee_last_name, employee_contact_id, employee_link_mode, created_at, updated_at) "
                "VALUES (:id, :cid, :canonical, :hr, :emp, :ident, :status, :efn, :eln, :ecid, :elm, :ca, :ua)",
                {
                    "id": assignment_id,
                    "cid": case_id,
                    "canonical": case_id,
                    "hr": hr_user_id,
                    "emp": employee_user_id,
                    "ident": employee_identifier,
                    "status": status,
                    "efn": efn,
                    "eln": eln,
                    "ecid": employee_contact_id,
                    "elm": elm,
                    "ca": now,
                    "ua": now,
                },
                op_name="create_assignment",
                request_id=request_id,
            )

    def update_assignment_status(self, assignment_id: str, status: str, request_id: Optional[str] = None) -> None:
        with self.engine.begin() as conn:
            self._exec(
                conn,
                "UPDATE case_assignments SET status = :status, updated_at = :ua WHERE id = :id",
                {"status": status, "ua": datetime.utcnow().isoformat(), "id": assignment_id},
                op_name="update_assignment_status",
                request_id=request_id,
            )

    def update_assignment_identifier(self, assignment_id: str, employee_identifier: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE case_assignments SET employee_identifier = :ident, updated_at = :ua WHERE id = :id"
            ), {"ident": employee_identifier, "ua": datetime.utcnow().isoformat(), "id": assignment_id})

    def attach_employee_to_assignment(
        self,
        assignment_id: str,
        employee_user_id: str,
        request_id: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        post_ecid: Optional[str] = None
        post_hr_uid: Optional[str] = None
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT employee_contact_id, hr_user_id FROM case_assignments WHERE id = :id"
                ),
                {"id": assignment_id},
            ).fetchone()
            self._exec(
                conn,
                "UPDATE case_assignments SET employee_user_id = :emp, employee_link_mode = NULL, "
                "updated_at = :ua WHERE id = :id",
                {"emp": employee_user_id, "ua": now, "id": assignment_id},
                op_name="attach_employee_to_assignment",
                request_id=request_id,
            )
            ecid = None
            if row:
                m = row._mapping if hasattr(row, "_mapping") else dict(row)
                ecid = m.get("employee_contact_id")
                hu = m.get("hr_user_id")
                if hu and str(hu).strip():
                    post_hr_uid = str(hu).strip()
            if ecid and str(ecid).strip():
                post_ecid = str(ecid).strip()
                conn.execute(
                    text(
                        "UPDATE employee_contacts SET linked_auth_user_id = :uid, updated_at = :ua "
                        "WHERE id = :ecid AND (linked_auth_user_id IS NULL OR linked_auth_user_id = :uid)"
                    ),
                    {"uid": employee_user_id, "ua": now, "ecid": post_ecid},
                )

        company_for_dir: Optional[str] = None
        if post_ecid:
            ec_row = self.get_employee_contact_by_id(post_ecid, request_id=request_id)
            if ec_row and ec_row.get("company_id"):
                company_for_dir = str(ec_row["company_id"]).strip()
        if not company_for_dir and post_hr_uid:
            company_for_dir = self.get_hr_company_id(post_hr_uid)
        if company_for_dir:
            self.assign_employee_profile_to_company_directory(
                employee_user_id.strip(), company_for_dir, request_id=request_id
            )

    def get_employee_contact_by_id(
        self, employee_contact_id: str, request_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        if not (employee_contact_id or "").strip():
            return None
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT * FROM employee_contacts WHERE id = :id LIMIT 1",
                {"id": employee_contact_id.strip()},
                op_name="get_employee_contact_by_id",
                request_id=request_id,
            ).fetchone()
        return self._row_to_dict(row)

    def list_employee_contacts_matching_signup_email(
        self, email_normalized: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Contacts that may belong to this signup email (auth is separate).
        Matches email_normalized and legacy rows where invite_key is the normalized email.
        """
        en = normalize_invite_key(email_normalized)
        if not en or "@" not in en:
            return []
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT * FROM employee_contacts WHERE "
                "(email_normalized IS NOT NULL AND TRIM(email_normalized) <> '' "
                "AND LOWER(TRIM(email_normalized)) = :en) "
                "OR (invite_key = :en)",
                {"en": en},
                op_name="list_employee_contacts_matching_signup_email",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def list_unassigned_assignments_for_employee_contact(
        self, employee_contact_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if not (employee_contact_id or "").strip():
            return []
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT * FROM case_assignments "
                "WHERE employee_contact_id = :ecid AND employee_user_id IS NULL "
                "AND (employee_link_mode IS NULL OR TRIM(COALESCE(employee_link_mode, '')) = '' "
                "OR LOWER(TRIM(employee_link_mode)) NOT IN ('pending_claim', 'dismissed'))",
                {"ecid": employee_contact_id.strip()},
                op_name="list_unassigned_assignments_for_employee_contact",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def list_employee_contacts_by_invite_key(
        self, invite_key: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """All company-scoped contacts with this invite_key (e.g. username login)."""
        ik = normalize_invite_key(invite_key)
        if not ik:
            return []
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT * FROM employee_contacts WHERE invite_key = :ik",
                {"ik": ik},
                op_name="list_employee_contacts_by_invite_key",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def list_assignment_claim_invite_statuses(self, assignment_id: str) -> List[str]:
        if not (assignment_id or "").strip():
            return []
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT status FROM assignment_claim_invites WHERE assignment_id = :aid"
                    ),
                    {"aid": assignment_id.strip()},
                ).fetchall()
            out: List[str] = []
            for row in rows:
                m = row._mapping if hasattr(row, "_mapping") else dict(row)
                s = (m.get("status") or "").strip().lower()
                if s:
                    out.append(s)
            return out
        except (OperationalError, ProgrammingError):
            return []

    def map_claim_invite_statuses_by_assignments(
        self, assignment_ids: List[str], request_id: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """Bulk load invite statuses keyed by assignment_id (lowercase status strings)."""
        ids = sorted({(x or "").strip() for x in assignment_ids if x and str(x).strip()})
        if not ids:
            return {}
        placeholders = ", ".join(f":a{i}" for i in range(len(ids)))
        params: Dict[str, Any] = {f"a{i}": ids[i] for i in range(len(ids))}
        out: Dict[str, List[str]] = {aid: [] for aid in ids}
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(
                    text(
                        f"SELECT assignment_id, status FROM assignment_claim_invites "
                        f"WHERE assignment_id IN ({placeholders})"
                    ),
                    params,
                ).fetchall()
            for row in rows:
                m = row._mapping if hasattr(row, "_mapping") else dict(row)
                aid = (m.get("assignment_id") or "").strip()
                s = (m.get("status") or "").strip().lower()
                if aid and s:
                    out.setdefault(aid, []).append(s)
            return out
        except (OperationalError, ProgrammingError):
            return {aid: [] for aid in ids}

    def is_assignment_auto_claim_blocked_by_revoked_invites(self, assignment_id: str) -> bool:
        """
        True when claim-invite rows exist, none are pending/claimed, and all are revoked.
        HR revoked the invite → do not auto-attach by email/username.
        """
        st = self.list_assignment_claim_invite_statuses(assignment_id)
        if not st:
            return False
        if "pending" in st:
            return False
        if "claimed" in st:
            return False
        return all(x == "revoked" for x in st)

    def list_unassigned_assignments_legacy_for_identifiers(
        self, identifiers: List[str], request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Assignments with no employee_contact_id (legacy) and no employee_user_id,
        matching normalized employee_identifier.
        """
        idents = sorted(
            {normalize_invite_key(x) for x in identifiers if x and normalize_invite_key(x)}
        )
        if not idents:
            return []
        seen: Set[str] = set()
        out: List[Dict[str, Any]] = []
        with self.engine.connect() as conn:
            for ident in idents:
                rows = self._exec(
                    conn,
                    "SELECT * FROM case_assignments WHERE employee_user_id IS NULL "
                    "AND (employee_contact_id IS NULL OR TRIM(COALESCE(employee_contact_id, '')) = '') "
                    "AND LOWER(TRIM(COALESCE(employee_identifier, ''))) = :ident "
                    "AND (employee_link_mode IS NULL OR TRIM(COALESCE(employee_link_mode, '')) = '' "
                    "OR LOWER(TRIM(employee_link_mode)) NOT IN ('pending_claim', 'dismissed'))",
                    {"ident": ident},
                    op_name="list_unassigned_assignments_legacy_for_identifiers",
                    request_id=request_id,
                ).fetchall()
                for row in rows:
                    d = self._row_to_dict(row)
                    aid = d.get("id") if d else None
                    if aid and aid not in seen:
                        seen.add(aid)
                        out.append(d)
        return out

    def _find_employee_contact_id_for_resolve(
        self,
        conn: Any,
        company_id: str,
        en: Optional[str],
        canonical_ik: str,
        ik: str,
    ) -> Optional[str]:
        """SELECT-only: existing contact id for company + email or invite keys (same order as insert path)."""
        cid = company_id
        row = None
        if en:
            row = conn.execute(
                text(
                    "SELECT id FROM employee_contacts "
                    "WHERE company_id = :c AND email_normalized = :en LIMIT 1"
                ),
                {"c": cid, "en": en},
            ).fetchone()
        if not row:
            row = conn.execute(
                text(
                    "SELECT id FROM employee_contacts "
                    "WHERE company_id = :c AND invite_key = :ik LIMIT 1"
                ),
                {"c": cid, "ik": canonical_ik},
            ).fetchone()
        if not row and canonical_ik != ik:
            row = conn.execute(
                text(
                    "SELECT id FROM employee_contacts "
                    "WHERE company_id = :c AND invite_key = :ik2 LIMIT 1"
                ),
                {"c": cid, "ik2": ik},
            ).fetchone()
        if not row:
            return None
        m = row._mapping if hasattr(row, "_mapping") else dict(row)
        return str(m["id"])

    def resolve_or_create_employee_contact(
        self,
        company_id: str,
        employee_identifier_raw: str,
        *,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> str:
        """
        Company-scoped operational identity; does not create auth users.
        Dedup order: (company_id + normalized email) if email-like, else (company_id + invite_key).
        New rows use invite_key = normalized email when email is present, else normalized identifier.
        Idempotent under DB unique constraints: concurrent inserts resolve via IntegrityError retry.
        """
        cid = (company_id or "").strip()
        raw = (employee_identifier_raw or "").strip()
        ik = normalize_invite_key(raw)
        en = email_normalized_from_identifier(raw)
        if not cid or not ik:
            raise ValueError("company_id and employee identifier are required")
        canonical_ik = en if en else ik
        now = datetime.utcnow().isoformat()
        fn = (first_name or "").strip() or None
        ln = (last_name or "").strip() or None

        with self.engine.connect() as conn:
            found = self._find_employee_contact_id_for_resolve(conn, cid, en, canonical_ik, ik)
            if found:
                identity_event(
                    "identity.contact.resolve",
                    outcome="reused",
                    request_id=request_id,
                    company_id=cid,
                    employee_contact_id=found,
                    identifier_shape="email" if en else "invite_key",
                )
                return found

        for _attempt in range(2):
            eid = str(uuid.uuid4())
            try:
                with self.engine.begin() as conn:
                    self._exec(
                        conn,
                        "INSERT INTO employee_contacts "
                        "(id, company_id, invite_key, email_normalized, first_name, last_name, linked_auth_user_id, created_at, updated_at) "
                        "VALUES (:id, :c, :ik, :en, :fn, :ln, NULL, :ca, :ua)",
                        {
                            "id": eid,
                            "c": cid,
                            "ik": canonical_ik,
                            "en": en,
                            "fn": fn,
                            "ln": ln,
                            "ca": now,
                            "ua": now,
                        },
                        op_name="resolve_or_create_employee_contact_insert",
                        request_id=request_id,
                    )
                identity_event(
                    "identity.contact.resolve",
                    outcome="created",
                    request_id=request_id,
                    company_id=cid,
                    employee_contact_id=eid,
                    identifier_shape="email" if en else "invite_key",
                )
                return eid
            except IntegrityError:
                log.info(
                    "resolve_or_create_employee_contact insert race attempt=%s company_id=%s email=%s",
                    _attempt,
                    cid[:8],
                    (en or "")[:20],
                )
                with self.engine.connect() as conn:
                    found = self._find_employee_contact_id_for_resolve(conn, cid, en, canonical_ik, ik)
                    if found:
                        identity_event(
                            "identity.contact.resolve",
                            outcome="reused_after_race",
                            request_id=request_id,
                            company_id=cid,
                            employee_contact_id=found,
                            identifier_shape="email" if en else "invite_key",
                        )
                        return found

        raise RuntimeError(
            "Could not resolve employee_contacts after concurrent insert; retry the request."
        )

    def get_or_create_employee_contact(
        self,
        company_id: str,
        invite_key: str,
        *,
        email_normalized: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> str:
        """Backward-compatible alias: `invite_key` is treated as the raw HR identifier string."""
        _ = email_normalized  # derived from identifier; kept for call-site compatibility
        return self.resolve_or_create_employee_contact(
            company_id,
            invite_key,
            first_name=first_name,
            last_name=last_name,
            request_id=request_id,
        )

    def link_employee_contact_to_auth_user(
        self,
        employee_contact_id: str,
        user_id: str,
        request_id: Optional[str] = None,
    ) -> None:
        """Idempotent: set linked_auth_user_id when unset or already same user."""
        if not (employee_contact_id or "").strip() or not (user_id or "").strip():
            return
        ec = self.get_employee_contact_by_id(employee_contact_id.strip(), request_id=request_id)
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            self._exec(
                conn,
                "UPDATE employee_contacts SET linked_auth_user_id = :uid, updated_at = :ua "
                "WHERE id = :ecid AND (linked_auth_user_id IS NULL OR linked_auth_user_id = :uid)",
                {"uid": user_id.strip(), "ua": now, "ecid": employee_contact_id.strip()},
                op_name="link_employee_contact_to_auth_user",
                request_id=request_id,
            )
        if ec:
            cc = (str(ec.get("company_id") or "")).strip()
            if cc:
                self.assign_employee_profile_to_company_directory(
                    user_id.strip(), cc, request_id=request_id
                )

    def assignment_identity_matches_user_identifiers(
        self,
        assignment: Dict[str, Any],
        user_identifiers: List[str],
        request_id: Optional[str] = None,
    ) -> bool:
        """True if assignment target matches any normalized identifier (legacy row or employee_contact)."""
        if not user_identifiers:
            return False
        uid_set = {normalize_invite_key(u) for u in user_identifiers if u}
        uid_set.discard("")
        ai = normalize_invite_key(assignment.get("employee_identifier"))
        if ai and ai in uid_set:
            return True
        ecid = assignment.get("employee_contact_id")
        if not ecid:
            return False
        ec = self.get_employee_contact_by_id(str(ecid), request_id=request_id)
        if not ec:
            return False
        if normalize_invite_key(ec.get("invite_key")) in uid_set:
            return True
        en = normalize_invite_key(ec.get("email_normalized"))
        return bool(en and en in uid_set)

    def _backfill_employee_contacts(self) -> None:
        """Attach employee_contact_id to legacy assignments (idempotent). Skips rows without case company_id."""
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT a.id AS aid, a.case_id, a.employee_identifier "
                        "FROM case_assignments a "
                        "WHERE (a.employee_contact_id IS NULL OR TRIM(COALESCE(a.employee_contact_id, '')) = '') "
                        "AND a.employee_identifier IS NOT NULL "
                        "AND TRIM(a.employee_identifier) != ''"
                    )
                ).fetchall()
        except (OperationalError, ProgrammingError) as e:
            log.debug("_backfill_employee_contacts skipped (schema): %s", e)
            return
        join_on = _relocation_cases_join_on("a", style="standard")
        for row in rows:
            m = row._mapping if hasattr(row, "_mapping") else dict(row)
            aid = m.get("aid")
            case_id = m.get("case_id")
            ident = m.get("employee_identifier")
            if not aid or not case_id or not ident:
                continue
            ik = normalize_invite_key(str(ident))
            if not ik:
                continue
            try:
                with self.engine.connect() as conn:
                    rc_row = conn.execute(
                        text(f"SELECT rc.company_id AS company_id FROM case_assignments a "
                             f"LEFT JOIN relocation_cases rc ON {join_on} "
                             f"WHERE a.id = :aid LIMIT 1"),
                        {"aid": str(aid)},
                    ).fetchone()
                if not rc_row:
                    continue
                rcm = rc_row._mapping if hasattr(rc_row, "_mapping") else dict(rc_row)
                company_id = rcm.get("company_id")
                if not company_id or not str(company_id).strip():
                    continue
                company_id = str(company_id).strip()
                en = email_normalized_from_identifier(str(ident))
                ecid = self.get_or_create_employee_contact(
                    company_id,
                    ik,
                    email_normalized=en,
                    request_id=None,
                )
                with self.engine.begin() as conn:
                    conn.execute(
                        text(
                            "UPDATE case_assignments SET employee_contact_id = :ecid, updated_at = :ua "
                            "WHERE id = :aid AND (employee_contact_id IS NULL OR TRIM(COALESCE(employee_contact_id,'')) = '')"
                        ),
                        {"ecid": ecid, "ua": datetime.utcnow().isoformat(), "aid": str(aid)},
                    )
            except Exception as ex:
                log.warning("backfill employee_contact for assignment %s: %s", aid, ex)

    def set_assignment_submitted(self, assignment_id: str, request_id: Optional[str] = None) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            self._exec(
                conn,
                "UPDATE case_assignments "
                "SET status = :status, submitted_at = :now, updated_at = :now "
                "WHERE id = :id",
                {"status": "submitted", "now": now, "id": assignment_id},
                op_name="set_assignment_submitted",
                request_id=request_id,
            )

    def set_assignment_decision(
        self,
        assignment_id: str,
        decision: str,
        notes: Optional[str],
        request_id: Optional[str] = None,
    ) -> None:
        with self.engine.begin() as conn:
            self._exec(
                conn,
                "UPDATE case_assignments "
                "SET status = :decision, decision = :decision, hr_notes = :notes, updated_at = :ua "
                "WHERE id = :id",
                {"decision": decision, "notes": notes, "ua": datetime.utcnow().isoformat(), "id": assignment_id},
                op_name="set_assignment_decision",
                request_id=request_id,
            )

    def insert_case_event(
        self,
        case_id: str,
        assignment_id: Optional[str],
        actor_principal_id: str,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """Append an immutable event to the case_events spine."""
        event_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        pl = json.dumps(payload or {})
        with self.engine.begin() as conn:
            if _is_sqlite:
                self._exec(
                    conn,
                    "INSERT INTO case_events (id, case_id, canonical_case_id, assignment_id, actor_principal_id, event_type, payload, created_at) "
                    "VALUES (:id, :cid, :canonical, :aid, :actor, :et, :pl, :ca)",
                    {
                        "id": event_id,
                        "cid": case_id,
                        "canonical": case_id,
                        "aid": assignment_id,
                        "actor": actor_principal_id,
                        "et": event_type,
                        "pl": pl,
                        "ca": now,
                    },
                    op_name="insert_case_event",
                    request_id=request_id,
                )
            else:
                self._exec(
                    conn,
                    "INSERT INTO case_events (id, case_id, canonical_case_id, assignment_id, actor_principal_id, event_type, payload, created_at) "
                    "VALUES (:id, :cid, :canonical, :aid, :actor, :et, :pl, :ca)",
                    {
                        "id": event_id,
                        "cid": case_id,
                        "canonical": case_id,
                        "aid": assignment_id,
                        "actor": actor_principal_id,
                        "et": event_type,
                        "pl": pl,
                        "ca": now,
                    },
                    op_name="insert_case_event",
                    request_id=request_id,
                )

    def list_case_events(self, case_id: str, request_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List case_events for a case, newest first. Prefers canonical_case_id, falls back to case_id."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT id, case_id, assignment_id, actor_principal_id, actor_user_id, event_type, payload, description, created_at "
                "FROM case_events WHERE (canonical_case_id = :cid OR case_id = :cid) ORDER BY created_at DESC LIMIT 200",
                {"cid": cid},
                op_name="list_case_events",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def ensure_case_participant(
        self,
        case_id: str,
        person_id: str,
        role: str,
        invited_at: Optional[str] = None,
        joined_at: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """Insert or update case_participants. Idempotent on (case_id, person_id, role)."""
        part_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        inv = invited_at or now
        jnd = joined_at
        params = {
            "id": part_id,
            "cid": case_id,
            "canonical": case_id,
            "pid": person_id,
            "role": role,
            "inv": inv,
            "jnd": jnd,
            "ca": now,
        }
        with self.engine.begin() as conn:
            if _is_sqlite:
                self._exec(
                    conn,
                    "INSERT INTO case_participants (id, case_id, canonical_case_id, person_id, role, invited_at, joined_at, created_at) "
                    "VALUES (:id, :cid, :canonical, :pid, :role, :inv, :jnd, :ca) "
                    "ON CONFLICT (case_id, person_id, role) DO UPDATE SET "
                    "invited_at = COALESCE(excluded.invited_at, case_participants.invited_at), "
                    "joined_at = COALESCE(excluded.joined_at, case_participants.joined_at), "
                    "canonical_case_id = COALESCE(excluded.canonical_case_id, case_participants.canonical_case_id)",
                    params,
                    op_name="ensure_case_participant",
                    request_id=request_id,
                )
            else:
                self._exec(
                    conn,
                    "INSERT INTO case_participants (id, case_id, canonical_case_id, person_id, role, invited_at, joined_at, created_at) "
                    "VALUES (:id, :cid, :canonical, :pid, :role, :inv, :jnd, :ca) "
                    "ON CONFLICT (case_id, person_id, role) DO UPDATE SET "
                    "invited_at = COALESCE(EXCLUDED.invited_at, case_participants.invited_at), "
                    "joined_at = COALESCE(EXCLUDED.joined_at, case_participants.joined_at), "
                    "canonical_case_id = COALESCE(EXCLUDED.canonical_case_id, case_participants.canonical_case_id)",
                    params,
                    op_name="ensure_case_participant",
                    request_id=request_id,
                )

    def list_case_participants(
        self, case_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List case_participants for a case. Prefers canonical_case_id, falls back to case_id."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT id, case_id, person_id, role, invited_at, joined_at, created_at "
                "FROM case_participants WHERE (canonical_case_id = :cid OR case_id = :cid) ORDER BY created_at ASC",
                {"cid": cid},
                op_name="list_case_participants",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def insert_case_evidence(
        self,
        case_id: str,
        assignment_id: Optional[str],
        participant_id: Optional[str],
        requirement_id: Optional[str],
        evidence_type: str,
        file_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status: str = "submitted",
        request_id: Optional[str] = None,
    ) -> str:
        """Insert a case_evidence row. Returns the new evidence id."""
        evidence_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        pl = json.dumps(metadata or {})
        with self.engine.begin() as conn:
            self._exec(
                conn,
                "INSERT INTO case_evidence "
                "(id, case_id, canonical_case_id, assignment_id, participant_id, requirement_id, evidence_type, "
                "file_url, metadata, status, submitted_at, created_at) "
                "VALUES (:id, :cid, :canonical, :aid, :pid, :rid, :et, :url, :meta, :status, :sub, :ca)",
                {
                    "id": evidence_id,
                    "cid": case_id,
                    "canonical": case_id,
                    "aid": assignment_id,
                    "pid": participant_id,
                    "rid": requirement_id,
                    "et": evidence_type,
                    "url": file_url,
                    "meta": pl,
                    "status": status,
                    "sub": now,
                    "ca": now,
                },
                op_name="insert_case_evidence",
                request_id=request_id,
            )
        return evidence_id

    def list_case_evidence(
        self, case_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List case_evidence for a case, newest first. Prefers canonical_case_id, falls back to case_id."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT id, case_id, assignment_id, participant_id, requirement_id, evidence_type, "
                "file_url, metadata, status, submitted_at, created_at "
                "FROM case_evidence WHERE (canonical_case_id = :cid OR case_id = :cid) ORDER BY created_at DESC",
                {"cid": cid},
                op_name="list_case_evidence",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def list_assignment_evidence(
        self, assignment_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List case_evidence for an assignment, newest first."""
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT id, case_id, assignment_id, participant_id, requirement_id, evidence_type, "
                "file_url, metadata, status, submitted_at, created_at "
                "FROM case_evidence WHERE assignment_id = :aid ORDER BY created_at DESC",
                {"aid": assignment_id},
                op_name="list_assignment_evidence",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def _ensure_case_milestones_tracker_sqlite(self, conn: Any) -> None:
        """Migrate legacy SQLite case_milestones to blocked status + owner/criticality/notes."""
        row = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name='case_milestones'")
        ).fetchone()
        if not row or not row[0]:
            return
        ddl = row[0] or ""
        if "blocked" in ddl and "owner" in ddl:
            return
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        try:
            conn.execute(text("""
                CREATE TABLE case_milestones__new (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    canonical_case_id TEXT,
                    milestone_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    target_date TEXT,
                    actual_date TEXT,
                    status TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending','in_progress','done','skipped','overdue','blocked')),
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    owner TEXT NOT NULL DEFAULT 'joint',
                    criticality TEXT NOT NULL DEFAULT 'normal',
                    notes TEXT
                )
            """))
            conn.execute(text("""
                INSERT INTO case_milestones__new (
                  id, case_id, canonical_case_id, milestone_type, title, description,
                  target_date, actual_date, status, sort_order, created_at, updated_at,
                  owner, criticality, notes
                )
                SELECT
                  id, case_id, canonical_case_id, milestone_type, title, description,
                  target_date, actual_date, status, sort_order, created_at, updated_at,
                  'joint', 'normal', NULL
                FROM case_milestones
            """))
            conn.execute(text("DROP TABLE case_milestones"))
            conn.execute(text("ALTER TABLE case_milestones__new RENAME TO case_milestones"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_case_milestones_case ON case_milestones(case_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_case_milestones_canonical ON case_milestones(canonical_case_id)"))
        finally:
            conn.execute(text("PRAGMA foreign_keys=ON"))

    # ------------------------------------------------------------------
    # Case milestones (timeline workflow)
    # ------------------------------------------------------------------
    def list_case_milestones(
        self, case_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List case_milestones for a case, ordered by sort_order then created_at."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                """SELECT id, case_id, canonical_case_id, milestone_type, title, description,
                   target_date, actual_date, status, sort_order, created_at, updated_at,
                   owner, criticality, notes
                   FROM case_milestones
                   WHERE (canonical_case_id = :cid OR case_id = :cid)
                   ORDER BY sort_order ASC, created_at ASC""",
                {"cid": cid},
                op_name="list_case_milestones",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def upsert_case_milestone(
        self,
        case_id: str,
        milestone_type: str,
        title: str,
        *,
        description: Optional[str] = None,
        target_date: Optional[str] = None,
        actual_date: Optional[str] = None,
        status: str = "pending",
        sort_order: int = 0,
        owner: str = "joint",
        criticality: str = "normal",
        notes: Optional[str] = None,
        milestone_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create or update a milestone. If milestone_id given, update; else create."""
        cid = self.coalesce_case_lookup_id(case_id)
        now = datetime.utcnow().isoformat()
        if milestone_id:
            with self.engine.begin() as conn:
                self._exec(
                    conn,
                    """UPDATE case_milestones SET
                       title = :title, description = :desc, target_date = :td, actual_date = :ad,
                       status = :status, sort_order = :so, owner = :owner, criticality = :crit,
                       notes = :notes, updated_at = :now
                       WHERE id = :id AND (canonical_case_id = :cid OR case_id = :cid)""",
                    {
                        "id": milestone_id,
                        "cid": cid,
                        "title": title,
                        "desc": description,
                        "td": target_date,
                        "ad": actual_date,
                        "status": status,
                        "so": sort_order,
                        "owner": owner,
                        "crit": criticality,
                        "notes": notes,
                        "now": now,
                    },
                    op_name="update_case_milestone",
                    request_id=request_id,
                )
            with self.engine.connect() as conn:
                row = self._exec(
                    conn,
                    "SELECT * FROM case_milestones WHERE id = :id",
                    {"id": milestone_id},
                    op_name="get_milestone",
                    request_id=request_id,
                ).fetchone()
            return self._row_to_dict(row) or {}
        mid = str(uuid.uuid4())
        with self.engine.begin() as conn:
            self._exec(
                conn,
                """INSERT INTO case_milestones
                   (id, case_id, canonical_case_id, milestone_type, title, description, target_date, actual_date, status, sort_order, created_at, updated_at, owner, criticality, notes)
                   VALUES (:id, :cid, :canonical, :mt, :title, :desc, :td, :ad, :status, :so, :now, :now, :owner, :crit, :notes)""",
                {
                    "id": mid,
                    "cid": case_id,
                    "canonical": cid,
                    "mt": milestone_type,
                    "title": title,
                    "desc": description,
                    "td": target_date,
                    "ad": actual_date,
                    "status": status,
                    "so": sort_order,
                    "now": now,
                    "owner": owner,
                    "crit": criticality,
                    "notes": notes,
                },
                op_name="insert_case_milestone",
                request_id=request_id,
            )
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT * FROM case_milestones WHERE id = :id",
                {"id": mid},
                op_name="get_milestone",
                request_id=request_id,
            ).fetchone()
        return self._row_to_dict(row) or {}

    def link_milestone_entity(
        self,
        milestone_id: str,
        linked_entity_type: str,
        linked_entity_id: str,
        request_id: Optional[str] = None,
    ) -> None:
        """Add a link from milestone to an entity (evidence, event, rfq, service, etc.)."""
        link_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            self._exec(
                conn,
                "INSERT INTO milestone_links (id, milestone_id, linked_entity_type, linked_entity_id, created_at) "
                "VALUES (:id, :mid, :et, :eid, :now)",
                {
                    "id": link_id,
                    "mid": milestone_id,
                    "et": linked_entity_type,
                    "eid": linked_entity_id,
                    "now": now,
                },
                op_name="link_milestone_entity",
                request_id=request_id,
            )

    def list_milestone_links(
        self, milestone_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List links for a milestone."""
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT id, milestone_id, linked_entity_type, linked_entity_id, created_at FROM milestone_links WHERE milestone_id = :mid",
                {"mid": milestone_id},
                op_name="list_milestone_links",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    # ------------------------------------------------------------------
    # Analytics events (observability)
    # ------------------------------------------------------------------
    def insert_analytics_event(
        self, event_name: str, payload: Dict[str, Any], request_id: Optional[str] = None
    ) -> None:
        """Insert an analytics event. Table may not exist in Postgres (use migration)."""
        event_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        payload_json = json.dumps(payload)
        try:
            with self.engine.begin() as conn:
                self._exec(
                    conn,
                    """
                    INSERT INTO analytics_events (id, event_name, payload_json, created_at)
                    VALUES (:id, :event_name, :payload_json, :created_at)
                    """,
                    {
                        "id": event_id,
                        "event_name": event_name,
                        "payload_json": payload_json,
                        "created_at": now,
                    },
                    op_name="insert_analytics_event",
                    request_id=request_id,
                )
        except Exception as e:
            log.debug("insert_analytics_event failed (table may not exist): %s", e)

    def list_analytics_events(
        self,
        event_name: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 1000,
        request_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List analytics events for reporting. Requires analytics_events table."""
        try:
            sql = "SELECT id, event_name, payload_json, created_at FROM analytics_events WHERE 1=1"
            params: Dict[str, Any] = {}
            if event_name:
                sql += " AND event_name = :event_name"
                params["event_name"] = event_name
            if since:
                sql += " AND created_at >= :since"
                params["since"] = since
            sql += " ORDER BY created_at DESC LIMIT :limit"
            params["limit"] = limit
            with self.engine.connect() as conn:
                rows = self._exec(
                    conn, sql, params, op_name="list_analytics_events", request_id=request_id
                ).fetchall()
            out = []
            for r in rows:
                d = self._row_to_dict(r)
                if d and "payload_json" in d:
                    raw = d["payload_json"]
                    if isinstance(raw, dict):
                        d["payload"] = raw
                    else:
                        try:
                            d["payload"] = json.loads(raw or "{}")
                        except Exception:
                            d["payload"] = {}
                    del d["payload_json"]
                out.append(d)
            return out
        except Exception as e:
            log.debug("list_analytics_events failed: %s", e)
            return []

    def count_analytics_events_by_name(
        self, since: Optional[str] = None, request_id: Optional[str] = None
    ) -> Dict[str, int]:
        """Count events by event_name for admin analytics. Returns {event_name: count}."""
        try:
            sql = "SELECT event_name, COUNT(*) as cnt FROM analytics_events WHERE 1=1"
            params: Dict[str, Any] = {}
            if since:
                sql += " AND created_at >= :since"
                params["since"] = since
            sql += " GROUP BY event_name"
            with self.engine.connect() as conn:
                rows = self._exec(
                    conn, sql, params, op_name="count_analytics_events", request_id=request_id
                ).fetchall()
            return {r[0]: r[1] for r in rows}
        except Exception as e:
            log.debug("count_analytics_events_by_name failed: %s", e)
            return {}

    def get_assignment_by_id(self, assignment_id: str, request_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT * FROM case_assignments WHERE id = :id",
                {"id": assignment_id},
                op_name="get_assignment_by_id",
                request_id=request_id,
            ).fetchone()
        return self._row_to_dict(row)

    def get_assignment_by_case_id(self, case_id: str, request_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Prefer canonical_case_id when resolving, fall back to case_id for legacy."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT * FROM case_assignments WHERE (canonical_case_id = :cid OR case_id = :cid)",
                {"cid": cid},
                op_name="get_assignment_by_case_id",
                request_id=request_id,
            ).fetchone()
        return self._row_to_dict(row)

    def list_case_services(self, assignment_id: str, request_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT * FROM case_services WHERE assignment_id = :aid ORDER BY category, service_key",
                {"aid": assignment_id},
                op_name="list_case_services",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def upsert_case_services(
        self,
        assignment_id: str,
        case_id: str,
        services: List[Dict[str, Any]],
        request_id: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            for item in services:
                payload = {
                    "id": item.get("id") or str(uuid.uuid4()),
                    "case_id": case_id,
                    "canonical_case_id": case_id,
                    "assignment_id": assignment_id,
                    "service_key": item.get("service_key"),
                    "category": item.get("category"),
                    "selected": 1 if item.get("selected", True) else 0,
                    "estimated_cost": item.get("estimated_cost"),
                    "currency": item.get("currency") or "EUR",
                    "created_at": now,
                    "updated_at": now,
                }
                if _is_sqlite:
                    # SQLite local dev: no unique constraint on (case_id, service_key)
                    update = self._exec(
                        conn,
                        """
                        UPDATE case_services
                        SET assignment_id = :assignment_id,
                            category = :category,
                            selected = :selected,
                            estimated_cost = :estimated_cost,
                            currency = :currency,
                            updated_at = :updated_at
                        WHERE case_id = :case_id AND service_key = :service_key
                        """,
                        payload,
                        op_name="update_case_services",
                        request_id=request_id,
                    )
                    if update.rowcount == 0:
                        self._exec(
                            conn,
                            """
                            INSERT INTO case_services (
                                id, case_id, canonical_case_id, assignment_id, service_key, category,
                                selected, estimated_cost, currency, created_at, updated_at
                            )
                            VALUES (
                                :id, :case_id, :canonical_case_id, :assignment_id, :service_key, :category,
                                :selected, :estimated_cost, :currency, :created_at, :updated_at
                            )
                            """,
                            payload,
                            op_name="insert_case_services",
                            request_id=request_id,
                        )
                else:
                    self._exec(
                        conn,
                        """
                        INSERT INTO case_services (
                            id, case_id, canonical_case_id, assignment_id, service_key, category,
                            selected, estimated_cost, currency, created_at, updated_at
                        )
                        VALUES (
                            :id, :case_id, :canonical_case_id, :assignment_id, :service_key, :category,
                            :selected, :estimated_cost, :currency, :created_at, :updated_at
                        )
                        ON CONFLICT(case_id, service_key)
                        DO UPDATE SET
                            canonical_case_id = COALESCE(excluded.canonical_case_id, case_services.canonical_case_id),
                            assignment_id = excluded.assignment_id,
                            category = excluded.category,
                            selected = excluded.selected,
                            estimated_cost = excluded.estimated_cost,
                            currency = excluded.currency,
                            updated_at = excluded.updated_at
                        """,
                        payload,
                        op_name="upsert_case_services",
                        request_id=request_id,
                    )

    def list_case_service_answers(
        self,
        case_id: str,
        request_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Prefers canonical_case_id, falls back to case_id."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT * FROM case_service_answers WHERE (canonical_case_id = :cid OR case_id = :cid) ORDER BY service_key",
                {"cid": cid},
                op_name="list_case_service_answers",
                request_id=request_id,
            ).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            try:
                item["answers"] = json.loads(item.get("answers") or "{}")
            except Exception:
                item["answers"] = {}
        return items

    def upsert_case_service_answers(
        self,
        case_id: str,
        service_key: str,
        answers: Dict[str, Any],
        request_id: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        sql = """
            INSERT INTO case_service_answers (id, case_id, canonical_case_id, service_key, answers, updated_at)
            VALUES (:id, :case_id, :canonical_case_id, :service_key, :answers, :updated_at)
            ON CONFLICT(case_id, service_key) DO UPDATE SET
                canonical_case_id = COALESCE(excluded.canonical_case_id, case_service_answers.canonical_case_id),
                answers = excluded.answers,
                updated_at = excluded.updated_at
        """
        params = {
            "id": str(uuid.uuid4()),
            "case_id": case_id,
            "canonical_case_id": case_id,
            "service_key": service_key,
            "answers": json.dumps(answers),
            "updated_at": now,
        }
        with self.engine.begin() as conn:
            self._exec(conn, sql, params, op_name="upsert_case_service_answers", request_id=request_id)

    def create_rfq(
        self,
        case_id: str,
        creator_user_id: str,
        items: List[Dict[str, Any]],
        vendor_ids: List[str],
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        rfq_id = str(uuid.uuid4())
        rfq_ref = f"RFQ-{datetime.utcnow().strftime('%Y%m%d')}-{rfq_id.split('-')[0]}"
        with self.engine.begin() as conn:
            self._exec(
                conn,
                """
                INSERT INTO rfqs (id, rfq_ref, case_id, canonical_case_id, created_by_user_id, status, created_at)
                VALUES (:id, :rfq_ref, :case_id, :canonical_case_id, :created_by_user_id, :status, :created_at)
                """,
                {
                    "id": rfq_id,
                    "rfq_ref": rfq_ref,
                    "case_id": case_id,
                    "canonical_case_id": case_id,
                    "created_by_user_id": creator_user_id,
                    "status": "sent",
                    "created_at": now,
                },
                op_name="create_rfq",
                request_id=request_id,
            )
            for item in items:
                self._exec(
                    conn,
                    """
                    INSERT INTO rfq_items (id, rfq_id, service_key, requirements, created_at)
                    VALUES (:id, :rfq_id, :service_key, :requirements, :created_at)
                    """,
                    {
                        "id": str(uuid.uuid4()),
                        "rfq_id": rfq_id,
                        "service_key": item.get("service_key", "unknown"),
                        "requirements": json.dumps(item.get("requirements", {})),
                        "created_at": now,
                    },
                    op_name="create_rfq_item",
                    request_id=request_id,
                )
            for vendor_id in vendor_ids:
                self._exec(
                    conn,
                    """
                    INSERT INTO rfq_recipients (id, rfq_id, vendor_id, status, last_activity_at)
                    VALUES (:id, :rfq_id, :vendor_id, :status, :last_activity_at)
                    """,
                    {
                        "id": str(uuid.uuid4()),
                        "rfq_id": rfq_id,
                        "vendor_id": vendor_id,
                        "status": "sent",
                        "last_activity_at": now,
                    },
                    op_name="create_rfq_recipient",
                    request_id=request_id,
                )
            self._exec(
                conn,
                """
                INSERT INTO quote_conversations (id, thread_type, case_id, rfq_id, created_at)
                VALUES (:id, :thread_type, :case_id, :rfq_id, :created_at)
                """,
                {
                    "id": str(uuid.uuid4()),
                    "thread_type": "vendor_quote",
                    "case_id": case_id,
                    "rfq_id": rfq_id,
                    "created_at": now,
                },
                op_name="create_quote_conversation",
                request_id=request_id,
            )
        return {"id": rfq_id, "rfq_ref": rfq_ref}

    def list_rfqs_for_case(
        self, case_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List RFQs for a case with items and recipients."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                """SELECT * FROM rfqs
                   WHERE case_id = :cid OR canonical_case_id = :cid
                   ORDER BY created_at DESC""",
                {"cid": cid},
                op_name="list_rfqs_for_case",
                request_id=request_id,
            ).fetchall()
            rfqs = self._rows_to_list(rows)
            for rfq in rfqs:
                rfq["items"] = self._list_rfq_items(conn, rfq["id"])
                rfq["recipients"] = self._list_rfq_recipients(conn, rfq["id"])
        return rfqs

    def _list_rfq_items(self, conn, rfq_id: str) -> List[Dict[str, Any]]:
        rows = conn.execute(
            text("SELECT * FROM rfq_items WHERE rfq_id = :rfq_id ORDER BY created_at"),
            {"rfq_id": rfq_id},
        ).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["requirements"] = self._json_load(item.get("requirements")) or {}
        return items

    def _list_rfq_recipients(self, conn, rfq_id: str) -> List[Dict[str, Any]]:
        rows = conn.execute(
            text("SELECT * FROM rfq_recipients WHERE rfq_id = :rfq_id"),
            {"rfq_id": rfq_id},
        ).fetchall()
        return self._rows_to_list(rows)

    def list_rfqs_for_assignment(
        self, assignment_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List RFQs for an assignment via its case_id."""
        assignment = self.get_assignment_by_id(assignment_id, request_id=request_id)
        if not assignment:
            return []
        case_id = assignment.get("case_id")
        if not case_id:
            return []
        return self.list_rfqs_for_case(case_id, request_id=request_id)

    def get_rfq(
        self, rfq_id: str, request_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get single RFQ with items and recipients."""
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT * FROM rfqs WHERE id = :id",
                {"id": rfq_id},
                op_name="get_rfq",
                request_id=request_id,
            ).fetchone()
        if not row:
            return None
        rfq = self._row_to_dict(row)
        with self.engine.connect() as conn:
            rfq["items"] = self._list_rfq_items(conn, rfq_id)
            rfq["recipients"] = self._list_rfq_recipients(conn, rfq_id)
        return rfq

    def list_quotes_for_rfq(
        self, rfq_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List quotes for an RFQ with quote_lines."""
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT * FROM quotes WHERE rfq_id = :rfq_id ORDER BY created_at DESC",
                {"rfq_id": rfq_id},
                op_name="list_quotes_for_rfq",
                request_id=request_id,
            ).fetchall()
            quotes = self._rows_to_list(rows)
            for q in quotes:
                line_rows = conn.execute(
                    text("SELECT * FROM quote_lines WHERE quote_id = :quote_id ORDER BY id"),
                    {"quote_id": q["id"]},
                ).fetchall()
                q["quote_lines"] = self._rows_to_list(line_rows)
        return quotes

    def create_quote(
        self,
        rfq_id: str,
        vendor_id: str,
        currency: str,
        total_amount: float,
        valid_until: Optional[str],
        quote_lines: List[Dict[str, Any]],
        created_by_user_id: Optional[str],
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a quote with line items."""
        quote_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            self._exec(
                conn,
                """INSERT INTO quotes (id, rfq_id, vendor_id, currency, total_amount, valid_until, status, created_by_user_id, created_at)
                   VALUES (:id, :rfq_id, :vendor_id, :currency, :total_amount, :valid_until, :status, :created_by_user_id, :created_at)""",
                {
                    "id": quote_id,
                    "rfq_id": rfq_id,
                    "vendor_id": vendor_id,
                    "currency": currency,
                    "total_amount": total_amount,
                    "valid_until": valid_until,
                    "status": "proposed",
                    "created_by_user_id": created_by_user_id,
                    "created_at": now,
                },
                op_name="create_quote",
                request_id=request_id,
            )
            for line in quote_lines:
                self._exec(
                    conn,
                    """INSERT INTO quote_lines (id, quote_id, label, amount)
                       VALUES (:id, :quote_id, :label, :amount)""",
                    {
                        "id": str(uuid.uuid4()),
                        "quote_id": quote_id,
                        "label": line.get("label", ""),
                        "amount": float(line.get("amount", 0)),
                    },
                    op_name="create_quote_line",
                    request_id=request_id,
                )
        return {
            "id": quote_id,
            "rfq_id": rfq_id,
            "vendor_id": vendor_id,
            "currency": currency,
            "total_amount": total_amount,
            "valid_until": valid_until,
            "status": "proposed",
        }

    def update_quote_status(
        self,
        quote_id: str,
        status: str,
        request_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update quote status (e.g. accepted, rejected)."""
        with self.engine.connect() as conn:
            self._exec(
                conn,
                "UPDATE quotes SET status = :status WHERE id = :id",
                {"status": status, "id": quote_id},
                op_name="update_quote_status",
                request_id=request_id,
            )
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM quotes WHERE id = :id"), {"id": quote_id}
            ).fetchone()
        return self._row_to_dict(row)

    def list_rfqs_for_vendor(
        self, vendor_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List RFQs where rfq_recipients.vendor_id = vendor_id."""
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                """SELECT r.* FROM rfqs r
                   INNER JOIN rfq_recipients rr ON rr.rfq_id = r.id
                   WHERE rr.vendor_id = :vendor_id
                   ORDER BY r.created_at DESC""",
                {"vendor_id": vendor_id},
                op_name="list_rfqs_for_vendor",
                request_id=request_id,
            ).fetchall()
        rfqs = self._rows_to_list(rows)
        for rfq in rfqs:
            with self.engine.connect() as c:
                rfq["items"] = self._list_rfq_items(c, rfq["id"])
                rfq["recipients"] = self._list_rfq_recipients(c, rfq["id"])
        return rfqs

    def validate_vendor_ids(
        self, vendor_ids: List[str], request_id: Optional[str] = None
    ) -> Tuple[List[str], List[str]]:
        """Check each vendor_id exists in vendors table. Returns (valid_ids, errors)."""
        valid: List[str] = []
        errors: List[str] = []
        for vid in vendor_ids:
            if not vid or not str(vid).strip():
                continue
            vid = str(vid).strip()
            try:
                with self.engine.connect() as conn:
                    row = self._exec(
                        conn,
                        "SELECT 1 FROM vendors WHERE id = :vid",
                        {"vid": vid},
                        op_name="validate_vendor_id",
                        request_id=request_id,
                    ).fetchone()
                if row:
                    valid.append(vid)
                else:
                    errors.append(f"Vendor {vid} not found in vendors table. Ensure supplier.vendor_id references an existing vendor.")
            except Exception as e:
                log.warning("validate_vendor_ids check failed for %s: %s", vid, e)
                valid.append(vid)  # Best-effort: allow if check fails (e.g. no vendors table)
        return (valid, errors)

    def get_vendor_for_user(
        self, user_id: str, request_id: Optional[str] = None
    ) -> Optional[str]:
        """Get vendor_id from vendor_users for user_id, or None."""
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT vendor_id FROM vendor_users WHERE user_id = :user_id",
                {"user_id": user_id},
                op_name="get_vendor_for_user",
                request_id=request_id,
            ).fetchone()
        if not row:
            return None
        d = self._row_to_dict(row)
        return (d or {}).get("vendor_id")

    def list_linked_assignments_for_employee(
        self,
        employee_user_id: str,
        request_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not (employee_user_id or "").strip():
            return []
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT * FROM case_assignments WHERE employee_user_id = :emp "
                "ORDER BY created_at DESC",
                {"emp": employee_user_id.strip()},
                op_name="list_linked_assignments_for_employee",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def list_pending_claim_assignments_for_auth_user(
        self,
        auth_user_id: str,
        request_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Assignments tied to employee_contacts linked to this user, awaiting explicit claim."""
        uid = (auth_user_id or "").strip()
        if not uid:
            return []
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT a.* FROM case_assignments a "
                "INNER JOIN employee_contacts ec ON ec.id = a.employee_contact_id "
                "WHERE TRIM(COALESCE(ec.linked_auth_user_id, '')) = :uid "
                "AND a.employee_user_id IS NULL "
                "AND LOWER(TRIM(COALESCE(a.employee_link_mode, ''))) = 'pending_claim' "
                "ORDER BY a.created_at DESC",
                {"uid": uid},
                op_name="list_pending_claim_assignments_for_auth_user",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def dismiss_pending_claim_assignment_for_auth_user(
        self,
        assignment_id: str,
        auth_user_id: str,
        request_id: Optional[str] = None,
    ) -> bool:
        """Mark pending_claim assignment as dismissed for this user (no account link). Returns True if updated."""
        aid = (assignment_id or "").strip()
        uid = (auth_user_id or "").strip()
        if not aid or not uid:
            return False
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            res = self._exec(
                conn,
                "UPDATE case_assignments SET employee_link_mode = 'dismissed', updated_at = :ua "
                "WHERE id = :aid AND employee_user_id IS NULL "
                "AND LOWER(TRIM(COALESCE(employee_link_mode, ''))) = 'pending_claim' "
                "AND employee_contact_id IN ("
                "  SELECT id FROM employee_contacts WHERE TRIM(COALESCE(linked_auth_user_id, '')) = :uid"
                ")",
                {"aid": aid, "uid": uid, "ua": now},
                op_name="dismiss_pending_claim_assignment_for_auth_user",
                request_id=request_id,
            )
            try:
                rc = res.rowcount
            except Exception:
                rc = 0
        return bool(rc and rc > 0)

    def get_assignment_for_employee(
        self,
        employee_user_id: str,
        request_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        linked = self.list_linked_assignments_for_employee(employee_user_id, request_id=request_id)
        return linked[0] if linked else None

    def list_employee_linked_assignment_overview(
        self,
        employee_user_id: str,
        request_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Lightweight linked rows for the employee overview: assignment + case + company + destination hints.
        Scoped strictly by case_assignments.employee_user_id.
        """
        uid = (employee_user_id or "").strip()
        if not uid:
            return []
        join_on = _relocation_cases_join_on("a", style="standard")
        sql = f"""
            SELECT
                a.id AS assignment_id,
                COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id) AS case_id,
                a.status AS assignment_status,
                a.created_at AS assignment_created_at,
                a.updated_at AS assignment_updated_at,
                rc.host_country AS host_country,
                rc.home_country AS home_country,
                rc.stage AS relocation_stage,
                rc.status AS relocation_case_status,
                COALESCE(rc.company_id, hu.company_id) AS company_id,
                c.name AS company_name
            FROM case_assignments a
            LEFT JOIN relocation_cases rc ON {join_on}
            LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
            LEFT JOIN companies c ON c.id = COALESCE(rc.company_id, hu.company_id)
            WHERE a.employee_user_id = :uid
            ORDER BY a.created_at DESC
        """
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                sql,
                {"uid": uid},
                op_name="list_employee_linked_assignment_overview",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def list_employee_pending_assignment_overview(
        self,
        auth_user_id: str,
        request_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Pending_claim assignments for contacts already linked to this auth user.
        Drops rows where relocation case company disagrees with employee_contact company (anti-leak).
        """
        uid = (auth_user_id or "").strip()
        if not uid:
            return []
        join_on = _relocation_cases_join_on("a", style="standard")
        sql = f"""
            SELECT
                a.id AS assignment_id,
                COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id) AS case_id,
                a.created_at AS assignment_created_at,
                a.employee_link_mode AS employee_link_mode,
                ec.company_id AS contact_company_id,
                rc.host_country AS host_country,
                rc.home_country AS home_country,
                COALESCE(rc.company_id, ec.company_id) AS company_id,
                c.name AS company_name
            FROM case_assignments a
            INNER JOIN employee_contacts ec ON ec.id = a.employee_contact_id
            LEFT JOIN relocation_cases rc ON {join_on}
            LEFT JOIN companies c ON c.id = COALESCE(rc.company_id, ec.company_id)
            WHERE TRIM(COALESCE(ec.linked_auth_user_id, '')) = :uid
            AND a.employee_user_id IS NULL
            AND LOWER(TRIM(COALESCE(a.employee_link_mode, ''))) = 'pending_claim'
            AND (
                rc.id IS NULL
                OR TRIM(COALESCE(ec.company_id, '')) = ''
                OR TRIM(COALESCE(rc.company_id, '')) = ''
                OR CAST(rc.company_id AS TEXT) = CAST(ec.company_id AS TEXT)
            )
            ORDER BY a.created_at DESC
        """
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                sql,
                {"uid": uid},
                op_name="list_employee_pending_assignment_overview",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def get_unassigned_assignment_by_identifier(
        self,
        identifier: str,
        request_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        ident = normalize_invite_key(identifier)
        if not ident:
            return None
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT a.* FROM case_assignments a "
                "LEFT JOIN employee_contacts ec ON ec.id = a.employee_contact_id "
                "WHERE a.employee_user_id IS NULL AND ( "
                "LOWER(TRIM(COALESCE(a.employee_identifier, ''))) = :ident "
                "OR ec.invite_key = :ident "
                ") "
                "ORDER BY a.created_at DESC LIMIT 1",
                {"ident": ident},
                op_name="get_unassigned_assignment_by_identifier",
                request_id=request_id,
            ).fetchone()
        return self._row_to_dict(row)

    def list_assignments_for_hr(self, hr_user_id: str, request_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT * FROM case_assignments WHERE hr_user_id = :hr ORDER BY created_at DESC",
                {"hr": hr_user_id},
                op_name="list_assignments_for_hr",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def list_assignments_for_company(
        self, company_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List assignments belonging to a company (via case or HR ownership). Used for HR company-scoped view."""
        rows, _ = self._list_assignments_for_company_core(
            company_id, limit=None, offset=0, search=None, status=None, destination=None, request_id=request_id
        )
        return rows

    def list_assignments_for_company_paginated(
        self,
        company_id: str,
        *,
        limit: int = 25,
        offset: int = 0,
        search: Optional[str] = None,
        status: Optional[str] = None,
        destination: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List assignments for company with server-side filter and pagination. Returns (rows, total_count)."""
        return self._list_assignments_for_company_core(
            company_id, limit=limit, offset=offset, search=search, status=status, destination=destination, request_id=request_id
        )

    def _list_assignments_for_company_core(
        self,
        company_id: str,
        *,
        limit: Optional[int] = None,
        offset: int = 0,
        search: Optional[str] = None,
        status: Optional[str] = None,
        destination: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Core query for company assignments with optional filters and pagination."""
        if _is_sqlite:
            join_on_cases = "rc.id = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"
        else:
            join_on_cases = "rc.id::text = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"

        base_where = "(rc.company_id = :cid OR (rc.company_id IS NULL AND hu.company_id = :cid))"
        params: Dict[str, Any] = {"cid": company_id}
        extras: List[str] = []

        if search and (s := search.strip()):
            pattern = f"%{s}%"
            params["search"] = pattern
            extras.append(
                "(LOWER(COALESCE(a.employee_identifier,'')) LIKE LOWER(:search) OR "
                "LOWER(COALESCE(a.employee_first_name,'')) LIKE LOWER(:search) OR "
                "LOWER(COALESCE(a.employee_last_name,'')) LIKE LOWER(:search))"
            )
        if status and status.strip() and status.lower() != "all":
            params["status"] = status.strip()
            extras.append("a.status = :status")
        if destination and (d := destination.strip()):
            dest_pattern = f"%{d}%"
            params["dest"] = dest_pattern
            extras.append(
                "(LOWER(COALESCE(rc.host_country,'')) LIKE LOWER(:dest) OR LOWER(COALESCE(rc.home_country,'')) LIKE LOWER(:dest))"
            )

        where_clause = base_where + (" AND " + " AND ".join(extras) if extras else "")
        limit_clause = f" LIMIT {int(limit)}" if limit is not None else ""
        offset_clause = f" OFFSET {int(offset)}" if offset else ""

        count_sql = f"""
            SELECT COUNT(*) AS n FROM case_assignments a
            LEFT JOIN relocation_cases rc ON {join_on_cases}
            LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
            WHERE {where_clause}
        """
        data_sql = f"""
            SELECT a.* FROM case_assignments a
            LEFT JOIN relocation_cases rc ON {join_on_cases}
            LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
            WHERE {where_clause}
            ORDER BY a.created_at DESC
            {limit_clause}{offset_clause}
        """
        with self.engine.connect() as conn:
            total_row = self._exec(
                conn, count_sql, params, op_name="list_assignments_for_company_count", request_id=request_id
            ).fetchone()
            total = int(total_row._mapping["n"]) if total_row else 0
            rows = self._exec(
                conn, data_sql, params, op_name="list_assignments_for_company", request_id=request_id
            ).fetchall()
        return self._rows_to_list(rows), total

    def list_assignments_for_company_with_details(
        self, company_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Assignments for company with employee_name, destination, status for admin company detail."""
        if _is_sqlite:
            join_on_cases = "rc.id = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"
        else:
            join_on_cases = "rc.id::text = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"

        sql = f"""
            SELECT a.id, a.status,
                   COALESCE(TRIM(emp_p.full_name),
                            NULLIF(TRIM(COALESCE(a.employee_first_name, '') || ' ' || COALESCE(a.employee_last_name, '')), ''),
                            a.employee_identifier, a.employee_user_id, '—') AS employee_name,
                   COALESCE(rc.host_country, rc.home_country, '—') AS destination
            FROM case_assignments a
            LEFT JOIN relocation_cases rc ON {join_on_cases}
            LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
            LEFT JOIN profiles emp_p ON emp_p.id = a.employee_user_id
            WHERE (rc.company_id = :cid OR (rc.company_id IS NULL AND hu.company_id = :cid))
            ORDER BY a.created_at DESC
        """
        with self.engine.connect() as conn:
            rows = self._exec(
                conn, sql, {"cid": company_id}, op_name="list_assignments_for_company_with_details", request_id=request_id
            ).fetchall()
        return self._rows_to_list(rows)

    def get_company_detail_orphan_diagnostics(self, company_id: str) -> Dict[str, Any]:
        """Counts of legacy records missing company_id linkage. For admin company detail."""
        with self.engine.connect() as conn:
            # Assignments where case has null company_id but HR belongs to this company
            row = conn.execute(
                text(f"""
                    SELECT COUNT(*) AS n FROM case_assignments a
                    LEFT JOIN relocation_cases rc ON {_relocation_cases_join_on("a")}
                    LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
                    WHERE hu.company_id = :cid AND (rc.company_id IS NULL OR TRIM(COALESCE(rc.company_id, '')) = '')
                """),
                {"cid": company_id},
            ).fetchone()
            assignments_case_missing_company_id = row._mapping["n"] if row else 0
            # HR users with no profile (would show as missing name/email)
            row2 = conn.execute(
                text(
                    "SELECT COUNT(*) AS n FROM hr_users hu "
                    "LEFT JOIN profiles p ON p.id = hu.profile_id WHERE hu.company_id = :cid AND p.id IS NULL"
                ),
                {"cid": company_id},
            ).fetchone()
            hr_users_missing_profile = row2._mapping["n"] if row2 else 0
            row3 = conn.execute(
                text(
                    "SELECT COUNT(*) AS n FROM employees e "
                    "LEFT JOIN profiles p ON p.id = e.profile_id WHERE e.company_id = :cid AND p.id IS NULL"
                ),
                {"cid": company_id},
            ).fetchone()
            employees_missing_profile = row3._mapping["n"] if row3 else 0
        return {
            "assignments_case_missing_company_id": assignments_case_missing_company_id,
            "hr_users_missing_profile": hr_users_missing_profile,
            "employees_missing_profile": employees_missing_profile,
        }

    def assignment_belongs_to_company(self, assignment_id: str, company_id: str) -> bool:
        """Check if assignment belongs to the given company (via case or HR)."""
        sql = f"""
            SELECT 1 FROM case_assignments a
            LEFT JOIN relocation_cases rc ON {_relocation_cases_join_on("a")}
            LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
            WHERE a.id = :aid AND (rc.company_id = :cid OR (rc.company_id IS NULL AND hu.company_id = :cid))
            LIMIT 1
        """
        with self.engine.connect() as conn:
            row = conn.execute(text(sql), {"aid": assignment_id, "cid": company_id}).fetchone()
        return row is not None

    def insert_hr_feedback(
        self,
        feedback_id: str,
        assignment_id: str,
        hr_user_id: str,
        employee_user_id: Optional[str],
        message: str,
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO hr_feedback (id, assignment_id, hr_user_id, employee_user_id, message, created_at) "
                "VALUES (:id, :aid, :hr, :emp, :msg, :ca)"
            ), {"id": feedback_id, "aid": assignment_id, "hr": hr_user_id, "emp": employee_user_id, "msg": message, "ca": now})
        return {"id": feedback_id, "assignment_id": assignment_id, "message": message, "created_at": now}

    def list_hr_feedback(self, assignment_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT id, assignment_id, hr_user_id, employee_user_id, message, created_at "
                "FROM hr_feedback WHERE assignment_id = :aid ORDER BY created_at DESC"
            ), {"aid": assignment_id}).fetchall()
        return self._rows_to_list(rows)

    def _get_notification_preference(
        self, user_id: str, type_: str
    ) -> Optional[Dict[str, Any]]:
        """6C: Get preference for user/type. Returns None if no row or table missing (use defaults)."""
        try:
            with self.engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT in_app, email, muted_until FROM notification_preferences "
                        "WHERE user_id::text = :uid AND type = :type"
                    ),
                    {"uid": str(user_id), "type": type_},
                ).fetchone()
            if row:
                return {"in_app": row._mapping.get("in_app"), "email": row._mapping.get("email"), "muted_until": row._mapping.get("muted_until")}
        except Exception as e:
            log.debug("notification_preferences not available: %s", e)
        return None

    def _insert_notification_outbox(
        self,
        notification_id: str,
        user_id: str,
        to_email: str,
        type_: str,
        payload: Dict[str, Any],
    ) -> None:
        """6C: Insert outbox row for email delivery. No-op if table missing."""
        try:
            outbox_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()
            payload_json = json.dumps(payload)
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO notification_outbox "
                        "(id, notification_id, user_id, to_email, type, payload, status) "
                        "VALUES (:id, :nid, :uid, :email, :type, CAST(:payload AS jsonb), 'pending')"
                    ),
                    {
                        "id": outbox_id, "nid": notification_id, "uid": user_id,
                        "email": to_email, "type": type_, "payload": payload_json,
                    },
                )
        except Exception as e:
            log.warning("Failed to insert notification outbox: %s", e)

    def create_notification_with_preferences(
        self,
        user_id: str,
        type_: str,
        title: str,
        body: Optional[str] = None,
        assignment_id: Optional[str] = None,
        case_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """6C: Create notification respecting preferences and muted_until. Returns notification id or None."""
        pref = self._get_notification_preference(user_id, type_)
        in_app = True
        email = False
        muted_until = None
        if pref:
            in_app = pref.get("in_app") if pref.get("in_app") is not None else True
            email = pref.get("email") or False
            muted_until = pref.get("muted_until")
        if muted_until:
            try:
                if isinstance(muted_until, str):
                    muted_dt = datetime.fromisoformat(muted_until.replace("Z", "+00:00"))
                else:
                    muted_dt = muted_until
                if muted_dt and muted_dt > datetime.utcnow():
                    return None
            except Exception:
                pass
        if not in_app and not email:
            return None
        notification_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        meta_json = json.dumps(metadata or {})
        with self.engine.begin() as conn:
                conn.execute(
                text(
                    "INSERT INTO notifications (id, created_at, user_id, assignment_id, case_id, type, title, body, metadata) "
                    "VALUES (:id, :ca, :uid, :aid, :cid, :type, :title, :body, :meta)"
                ),
                {
                    "id": notification_id, "ca": now, "uid": user_id, "aid": assignment_id,
                    "cid": case_id, "type": type_, "title": title, "body": body, "meta": meta_json,
                },
            )
        if email:
            user = self.get_user_by_id(user_id)
            to_email = (user or {}).get("email") or ""
            if to_email:
                self._insert_notification_outbox(
                    notification_id=notification_id,
                    user_id=user_id,
                    to_email=to_email,
                    type_=type_,
                    payload={
                        "title": title,
                        "body": body or "",
                        "assignment_id": assignment_id,
                        "case_id": case_id,
                        **(metadata or {}),
                    },
                )
        return notification_id

    def insert_notification(
        self,
        notification_id: str,
        user_id: str,
        type_: str,
        title: str,
        body: Optional[str] = None,
        assignment_id: Optional[str] = None,
        case_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        meta_json = json.dumps(metadata or {})
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO notifications (id, created_at, user_id, assignment_id, case_id, type, title, body, metadata) "
                "VALUES (:id, :ca, :uid, :aid, :cid, :type, :title, :body, :meta)"
            ), {
                "id": notification_id, "ca": now, "uid": user_id, "aid": assignment_id,
                "cid": case_id, "type": type_, "title": title, "body": body, "meta": meta_json,
            })

    def list_notifications(
        self,
        user_id: str,
        limit: int = 25,
        only_unread: bool = False,
        request_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            q = (
                "SELECT id, created_at, assignment_id, case_id, type, title, body, metadata, read_at "
                "FROM notifications WHERE user_id = :uid"
            )
            if only_unread:
                q += " AND read_at IS NULL"
            q += " ORDER BY created_at DESC LIMIT :lim"
            rows = self._exec(
                conn,
                q,
                {"uid": user_id, "lim": min(limit, 100)},
                op_name="list_notifications",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def count_unread_notifications(self, user_id: str, request_id: Optional[str] = None) -> int:
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT COUNT(*) FROM notifications WHERE user_id = :uid AND read_at IS NULL",
                {"uid": user_id},
                op_name="count_unread_notifications",
                request_id=request_id,
            ).fetchone()
        return row[0] if row else 0

    def mark_notification_read(self, notification_id: str, user_id: str) -> bool:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            result = conn.execute(text(
                "UPDATE notifications SET read_at = :ra WHERE id = :id AND user_id = :uid"
            ), {"ra": now, "id": notification_id, "uid": user_id})
        return result.rowcount > 0

    def list_all_assignments(self) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text("SELECT * FROM case_assignments ORDER BY created_at DESC")).fetchall()
        return self._rows_to_list(rows)

    def list_admin_assignments(
        self,
        company_id: Optional[str] = None,
        employee_user_id: Optional[str] = None,
        employee_search: Optional[str] = None,
        status: Optional[str] = None,
        destination_country: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List assignments for admin with filters. Joins case_assignments, relocation_cases, profiles, companies."""
        clauses = []
        params: Dict[str, Any] = {}
        if company_id:
            clauses.append("(rc.company_id = :company_id OR (rc.company_id IS NULL AND EXISTS (SELECT 1 FROM hr_users hu2 WHERE hu2.profile_id = a.hr_user_id AND hu2.company_id = :company_id)))")
            params["company_id"] = company_id
        if employee_user_id:
            clauses.append("a.employee_user_id = :employee_user_id")
            params["employee_user_id"] = employee_user_id
        if status:
            clauses.append("a.status = :status")
            params["status"] = status
        else:
            clauses.append("(COALESCE(TRIM(LOWER(a.status)), '') NOT IN ('archived', 'closed'))")
        if destination_country:
            clauses.append("LOWER(TRIM(COALESCE(rc.host_country, ''))) = LOWER(TRIM(:dest_country))")
            params["dest_country"] = destination_country
        if employee_search:
            esc = (employee_search or "").strip()
            pattern = f"%{esc}%"
            if _is_sqlite:
                clauses.append(
                    "(LOWER(COALESCE(a.employee_identifier, '')) LIKE LOWER(:emp_search) OR "
                    "LOWER(COALESCE(emp_p.full_name, '')) LIKE LOWER(:emp_search) OR "
                    "LOWER(COALESCE(a.employee_first_name, '')) LIKE LOWER(:emp_search) OR "
                    "LOWER(COALESCE(a.employee_last_name, '')) LIKE LOWER(:emp_search))"
                )
            else:
                clauses.append(
                    "(a.employee_identifier ILIKE :emp_search OR emp_p.full_name ILIKE :emp_search OR "
                    "a.employee_first_name ILIKE :emp_search OR a.employee_last_name ILIKE :emp_search)"
                )
            params["emp_search"] = pattern

        where_sql = "AND " + " AND ".join(clauses) if clauses else ""

        if _is_sqlite:
            join_on_cases = "rc.id = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"
        else:
            # Postgres: relocation_cases.id is uuid, case_assignments.case_id / canonical_case_id are text UUIDs.
            # Cast uuid to text for a safe, index-friendly join.
            join_on_cases = "rc.id::text = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"

        _agent_debug_log(
            hypothesis_id="H1",
            location="database.list_admin_assignments",
            message="list_admin_assignments SQL prepared",
            data={
                "is_sqlite": _is_sqlite,
                "company_id": company_id,
                "employee_user_id": employee_user_id,
                "status": status,
                "destination_country": destination_country,
                "employee_search_present": bool(employee_search),
                "join_on_cases": join_on_cases,
                "where_sql": where_sql,
            },
        )

        sql = f"""
            SELECT
                a.id, a.case_id, a.canonical_case_id, a.hr_user_id, a.employee_user_id, a.employee_identifier,
                a.status, a.employee_first_name, a.employee_last_name, a.expected_start_date, a.submitted_at,
                a.created_at, a.updated_at,
                rc.id AS case_pk, rc.company_id AS case_company_id, rc.host_country, rc.home_country,
                rc.status AS case_status, rc.stage,
                c.name AS company_name,
                emp_p.full_name AS employee_full_name, emp_p.company_id AS employee_profile_company_id,
                hr_p.full_name AS hr_full_name, hr_p.company_id AS hr_profile_company_id,
                hu.company_id AS hr_company_id,
                COALESCE(emp.company_id, emp_p.company_id) AS employee_company_id,
                ep.profile_json,
                rap.id AS resolved_policy_id,
                (SELECT COUNT(*) FROM company_policies cp WHERE cp.company_id = COALESCE(rc.company_id, hu.company_id) AND cp.extraction_status = 'extracted') AS company_policy_count
            FROM case_assignments a
            LEFT JOIN relocation_cases rc ON {join_on_cases}
            LEFT JOIN companies c ON c.id = COALESCE(rc.company_id, (SELECT hu2.company_id FROM hr_users hu2 WHERE hu2.profile_id = a.hr_user_id LIMIT 1))
            LEFT JOIN profiles emp_p ON emp_p.id = a.employee_user_id
            LEFT JOIN profiles hr_p ON hr_p.id = a.hr_user_id
            LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
            LEFT JOIN employees emp ON emp.profile_id = a.employee_user_id
            LEFT JOIN employee_profiles ep ON ep.assignment_id = a.id
            LEFT JOIN resolved_assignment_policies rap ON rap.assignment_id = a.id
            WHERE 1=1 {where_sql}
            ORDER BY a.updated_at DESC, a.created_at DESC
        """

        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()

        result = []
        for row in rows:
            m = row._mapping
            r = dict(m)
            profile_json = r.get("profile_json")
            profile = self._json_load(profile_json) if profile_json else {}
            mp = profile.get("movePlan") or {}
            pa = profile.get("primaryApplicant") or {}
            assign = pa.get("assignment") or {}
            r["assignment_type"] = assign.get("type") or assign.get("assignmentType")
            r["move_date"] = mp.get("targetArrivalDate") or r.get("expected_start_date")
            dep = profile.get("dependents") or []
            has_spouse = bool(profile.get("spouse", {}).get("fullName"))
            r["family_status"] = "family" if (has_spouse or dep) else "single"
            r["destination_from_profile"] = mp.get("destination") if isinstance(mp.get("destination"), str) else None
            r["policy_resolved"] = bool(r.get("resolved_policy_id"))
            r["company_has_policy"] = (r.get("company_policy_count") or 0) > 0
            # Normalized fields for admin list
            r["assignment_id"] = r.get("id")
            r["company_id"] = r.get("case_company_id") or r.get("hr_company_id")
            r["destination_country"] = r.get("host_country") or r.get("destination_from_profile")
            r["orphan_employee"] = not (
                (r.get("employee_user_id") and str(r.get("employee_user_id")).strip())
                or (r.get("employee_identifier") and str(r.get("employee_identifier")).strip())
            )
            result.append(r)
        return result

    def get_admin_assignment_detail(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        """Full assignment context for admin detail: assignment, case, employee, HR, services, policy."""
        with self.engine.connect() as conn:
            join_on_cases = "rc.id = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)" if _is_sqlite else "rc.id::text = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"
            row = conn.execute(
                text(f"""
                    SELECT a.*, rc.id AS case_pk, rc.company_id AS case_company_id, rc.hr_user_id AS case_hr_user_id,
                        rc.host_country, rc.home_country, rc.status AS case_status, rc.stage, rc.profile_json AS case_profile_json,
                        c.name AS company_name,
                        emp_p.id AS emp_profile_id, emp_p.full_name AS employee_full_name, emp_p.email AS employee_email, emp_p.company_id AS employee_profile_company_id,
                        hr_p.id AS hr_profile_id, hr_p.full_name AS hr_full_name, hr_p.email AS hr_email, hr_p.company_id AS hr_profile_company_id,
                        hu.company_id AS hr_company_id, emp.company_id AS employee_company_id
                    FROM case_assignments a
                    LEFT JOIN relocation_cases rc ON {join_on_cases}
                    LEFT JOIN companies c ON c.id = COALESCE(rc.company_id, (SELECT hu2.company_id FROM hr_users hu2 WHERE hu2.profile_id = a.hr_user_id LIMIT 1))
                    LEFT JOIN profiles emp_p ON emp_p.id = a.employee_user_id
                    LEFT JOIN profiles hr_p ON hr_p.id = a.hr_user_id
                    LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
                    LEFT JOIN employees emp ON emp.profile_id = a.employee_user_id
                    WHERE a.id = :aid
                """),
                {"aid": assignment_id},
            ).fetchone()
        if not row:
            return None
        out = dict(row._mapping)
        ep = self.get_employee_profile(assignment_id)
        out["employee_profile"] = ep
        out["case_services"] = self.list_case_services(assignment_id)
        out["resolved_policy"] = self.get_resolved_assignment_policy(assignment_id)
        comp_id = out.get("case_company_id") or out.get("hr_company_id")
        policies = self.list_company_policies(comp_id) if comp_id else []
        out["company_policies"] = [p for p in policies if (p.get("extraction_status") or "") == "extracted"]
        out["company_has_published_policy"] = len(out["company_policies"]) > 0
        return out

    def admin_reassign_employee_company(self, employee_user_id: str, company_id: str) -> None:
        """Reassign employee profile to a company (profiles.company_id)."""
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE profiles SET company_id = :cid WHERE id = :id"), {"cid": company_id, "id": employee_user_id})
            conn.execute(text("UPDATE employees SET company_id = :cid WHERE profile_id = :pid"), {"cid": company_id, "pid": employee_user_id})

    def admin_reassign_hr_owner(self, assignment_id: str, new_hr_user_id: str) -> None:
        """Reassign assignment and case to new HR owner."""
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT case_id FROM case_assignments WHERE id = :aid"), {"aid": assignment_id}).fetchone()
        case_id = row[0] if row and row[0] else None
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE case_assignments SET hr_user_id = :hr, updated_at = :ua WHERE id = :aid"),
                {"hr": new_hr_user_id, "ua": datetime.utcnow().isoformat(), "aid": assignment_id},
            )
            if case_id:
                conn.execute(
                    text("UPDATE relocation_cases SET hr_user_id = :hr, updated_at = :ua WHERE id = :cid"),
                    {"hr": new_hr_user_id, "ua": datetime.utcnow().isoformat(), "cid": case_id},
                )

    def admin_fix_assignment_company_linkage(self, assignment_id: str, company_id: str) -> None:
        """Set relocation_case.company_id to match; ensures assignment-company consistency."""
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT case_id FROM case_assignments WHERE id = :aid"), {"aid": assignment_id}).fetchone()
        if not row or not row[0]:
            return
        case_id = row[0]
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE relocation_cases SET company_id = :cid, updated_at = :ua WHERE id = :case_id"),
                {"cid": company_id, "ua": datetime.utcnow().isoformat(), "case_id": case_id},
            )

    def update_relocation_case_host_country(self, case_id: str, host_country: str) -> None:
        """Set destination (host_country) on a relocation case (e.g. after admin create)."""
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE relocation_cases SET host_country = :host, updated_at = :ua WHERE id = :cid"),
                {"host": host_country, "ua": datetime.utcnow().isoformat(), "cid": case_id},
            )

    def admin_link_policy_company(self, policy_id: str, company_id: str) -> None:
        """Reassign a company_policy to a company (for reconciliation)."""
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE company_policies SET company_id = :cid WHERE id = :id"),
                {"cid": company_id, "id": policy_id},
            )

    def backfill_link_latest_policy_to_test_company(self, company_name: str = "Test company") -> Dict[str, Any]:
        """
        Link the most recently created company_policy (by created_at) to the company named company_name.
        Use to surface the policy worked on in the HR workflow under Test company in Admin Policies.
        """
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT id FROM companies WHERE LOWER(TRIM(name)) = LOWER(TRIM(:name)) LIMIT 1"),
                {"name": company_name},
            ).fetchone()
        if not row:
            return {"ok": False, "error": f"Company '{company_name}' not found", "policy_id": None}
        test_company_id = row._mapping["id"]
        with self.engine.connect() as conn:
            policy_row = conn.execute(
                text(
                    "SELECT id FROM company_policies ORDER BY created_at DESC LIMIT 1"
                ),
                {},
            ).fetchone()
        if not policy_row:
            return {"ok": True, "company_id": test_company_id, "company_name": company_name, "policy_id": None, "linked": False}
        policy_id = policy_row._mapping["id"]
        self.admin_link_policy_company(policy_id, test_company_id)
        log.info(
            "backfill_link_latest_policy_to_test_company: company=%s company_id=%s policy_id=%s",
            company_name,
            test_company_id,
            policy_id,
        )
        return {"ok": True, "company_id": test_company_id, "company_name": company_name, "policy_id": policy_id, "linked": True}

    def get_reconciliation_report(self) -> Dict[str, Any]:
        """Report for admin data reconciliation: entities and missing links. No destructive changes."""
        with self.engine.connect() as conn:
            companies = self._rows_to_list(
                conn.execute(text("SELECT id, name, country, created_at FROM companies ORDER BY name")).fetchall()
            )
            people = self._rows_to_list(
                conn.execute(text(
                    "SELECT id, role, email, full_name, company_id, created_at FROM profiles ORDER BY full_name, email"
                )).fetchall()
            )
            people_without_company = [
                p for p in people
                if not (p.get("company_id") or "").strip()
            ]
            sql_assignments = f"""
                SELECT a.id, a.case_id, a.hr_user_id, a.employee_user_id, a.employee_identifier, a.status,
                       rc.company_id AS case_company_id,
                       (SELECT hu.company_id FROM hr_users hu WHERE hu.profile_id = a.hr_user_id LIMIT 1) AS hr_company_id
                FROM case_assignments a
                LEFT JOIN relocation_cases rc ON {_relocation_cases_join_on("a")}
                ORDER BY a.created_at DESC
            """
            assignments = self._rows_to_list(conn.execute(text(sql_assignments)).fetchall())
            resolved_company_id = lambda a: (a.get("case_company_id") or "").strip() or (a.get("hr_company_id") or "").strip()
            assignments_without_company = [a for a in assignments if not resolved_company_id(a)]
            assignments_without_person = [a for a in assignments if not (a.get("employee_user_id") or "").strip()]
            policies = self._rows_to_list(
                conn.execute(text(
                    "SELECT id, company_id, title, extraction_status, created_at FROM company_policies ORDER BY created_at DESC"
                )).fetchall()
            )
            company_ids = {c["id"] for c in companies}
            policies_without_company = [p for p in policies if (p.get("company_id") or "").strip() not in company_ids]
        return {
            "companies": companies,
            "people": people,
            "people_without_company": people_without_company,
            "assignments": assignments,
            "assignments_without_company": assignments_without_company,
            "assignments_without_person": assignments_without_person,
            "policies": policies,
            "policies_without_company": policies_without_company,
            "summary": {
                "companies_count": len(companies),
                "people_count": len(people),
                "people_without_company_count": len(people_without_company),
                "assignments_count": len(assignments),
                "assignments_without_company_count": len(assignments_without_company),
                "assignments_without_person_count": len(assignments_without_person),
                "policies_count": len(policies),
                "policies_without_company_count": len(policies_without_company),
            },
        }

    # ------------------------------------------------------------------
    # Dynamic dossier (Phase 1)
    # ------------------------------------------------------------------
    @staticmethod
    def _json_load(value: Optional[str]) -> Optional[Any]:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except Exception:
            return None

    def list_dossier_questions(self, destination_country: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM dossier_questions WHERE destination_country = :dest "
                "ORDER BY sort_order ASC, created_at ASC"
            ), {"dest": destination_country}).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["options"] = self._json_load(item.get("options"))
            item["applies_if"] = self._json_load(item.get("applies_if"))
        return items

    def list_dossier_answers(self, case_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Prefers canonical_case_id, falls back to case_id."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM dossier_answers WHERE (canonical_case_id = :cid OR case_id = :cid) AND user_id = :uid"
            ), {"cid": cid, "uid": user_id}).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["answer"] = self._json_load(item.get("answer_json"))
        return items

    def upsert_dossier_answers(self, case_id: str, user_id: str, answers: List[Dict[str, Any]]) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            for ans in answers:
                payload = {
                    "id": ans.get("id") or str(uuid.uuid4()),
                    "cid": case_id,
                    "uid": user_id,
                    "qid": ans["question_id"],
                    "answer": json.dumps(ans["answer"]),
                    "answered_at": now,
                }
                conn.execute(text(
                    "INSERT INTO dossier_answers (id, case_id, user_id, question_id, answer_json, answered_at) "
                    "VALUES (:id, :cid, :uid, :qid, :answer, :answered_at) "
                    "ON CONFLICT(case_id, user_id, question_id) DO UPDATE SET "
                    "answer_json = excluded.answer_json, answered_at = excluded.answered_at"
                ), payload)

    def list_dossier_case_questions(self, case_id: str) -> List[Dict[str, Any]]:
        """Prefers canonical_case_id, falls back to case_id."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM dossier_case_questions WHERE (canonical_case_id = :cid OR case_id = :cid) ORDER BY created_at ASC"
            ), {"cid": cid}).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["options"] = self._json_load(item.get("options"))
            item["sources"] = self._json_load(item.get("sources"))
        return items

    def add_dossier_case_question(
        self,
        case_id: str,
        question_text: str,
        answer_type: str,
        options: Optional[Any],
        is_mandatory: bool,
        sources: Optional[Any],
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        row = {
            "id": str(uuid.uuid4()),
            "case_id": case_id,
            "question_text": question_text,
            "answer_type": answer_type,
            "options": json.dumps(options) if options is not None else None,
            "is_mandatory": 1 if is_mandatory else 0,
            "sources": json.dumps(sources) if sources is not None else None,
            "created_at": now,
        }
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO dossier_case_questions "
                "(id, case_id, question_text, answer_type, options, is_mandatory, sources, created_at) "
                "VALUES (:id, :case_id, :question_text, :answer_type, :options, :is_mandatory, :sources, :created_at)"
            ), row)
        return row

    def list_dossier_case_answers(self, case_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Prefers canonical_case_id, falls back to case_id."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM dossier_case_answers WHERE (canonical_case_id = :cid OR case_id = :cid) AND user_id = :uid"
            ), {"cid": cid, "uid": user_id}).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["answer"] = self._json_load(item.get("answer_json"))
        return items

    def upsert_dossier_case_answers(self, case_id: str, user_id: str, answers: List[Dict[str, Any]]) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            for ans in answers:
                payload = {
                    "id": ans.get("id") or str(uuid.uuid4()),
                    "cid": case_id,
                    "uid": user_id,
                    "qid": ans["case_question_id"],
                    "answer": json.dumps(ans["answer"]),
                    "answered_at": now,
                }
                conn.execute(text(
                    "INSERT INTO dossier_case_answers (id, case_id, user_id, case_question_id, answer_json, answered_at) "
                    "VALUES (:id, :cid, :uid, :qid, :answer, :answered_at) "
                    "ON CONFLICT(case_id, user_id, case_question_id) DO UPDATE SET "
                    "answer_json = excluded.answer_json, answered_at = excluded.answered_at"
                ), payload)

    def list_dossier_source_suggestions(self, case_id: str) -> List[Dict[str, Any]]:
        """Prefers canonical_case_id, falls back to case_id."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM dossier_source_suggestions WHERE (canonical_case_id = :cid OR case_id = :cid) ORDER BY created_at DESC"
            ), {"cid": cid}).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["results"] = self._json_load(item.get("results"))
        return items

    def add_dossier_source_suggestion(
        self,
        case_id: str,
        destination_country: str,
        query: str,
        results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        row = {
            "id": str(uuid.uuid4()),
            "case_id": case_id,
            "destination_country": destination_country,
            "query": query,
            "results": json.dumps(results),
            "created_at": now,
        }
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO dossier_source_suggestions "
                "(id, case_id, destination_country, query, results, created_at) "
                "VALUES (:id, :case_id, :destination_country, :query, :results, :created_at)"
            ), row)
        return row

    # ------------------------------------------------------------------
    # Guidance packs (Phase 2)
    # ------------------------------------------------------------------
    def list_knowledge_packs(self, destination_country: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM knowledge_packs "
                "WHERE destination_country = :dest AND status = 'active'"
            ), {"dest": destination_country}).fetchall()
        return self._rows_to_list(rows)

    def count_knowledge_packs_by_destination(self, destination_country: str) -> int:
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT COUNT(*) as count FROM knowledge_packs WHERE destination_country = :dest"
            ), {"dest": destination_country}).fetchone()
        return int(row[0] if row else 0)

    def ensure_knowledge_pack(self, destination_country: str, domain: str) -> Dict[str, Any]:
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT * FROM knowledge_packs WHERE destination_country = :dest AND domain = :domain AND status = 'active' "
                "ORDER BY created_at DESC LIMIT 1"
            ), {"dest": destination_country, "domain": domain}).fetchone()
        item = self._row_to_dict(row)
        if item:
            return item
        now = datetime.utcnow().isoformat()
        pack = {
            "id": str(uuid.uuid4()),
            "destination_country": destination_country,
            "domain": domain,
            "version": 1,
            "status": "active",
            "effective_from": None,
            "effective_to": None,
            "last_verified_at": now,
            "created_at": now,
        }
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO knowledge_packs "
                "(id, destination_country, domain, version, status, effective_from, effective_to, last_verified_at, created_at) "
                "VALUES (:id, :destination_country, :domain, :version, :status, :effective_from, :effective_to, :last_verified_at, :created_at)"
            ), pack)
        return pack

    def upsert_knowledge_doc_by_url(
        self,
        pack_id: str,
        source_url: str,
        title: str,
        publisher: Optional[str],
        text_content: str,
        fetched_at: Optional[str],
        fetch_status: str,
        content_excerpt: Optional[str],
        content_sha256: Optional[str],
        last_verified_at: Optional[str],
    ) -> Dict[str, Any]:
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT * FROM knowledge_docs WHERE source_url = :url ORDER BY created_at DESC LIMIT 1"
            ), {"url": source_url}).fetchone()
        existing = self._row_to_dict(row)
        now = datetime.utcnow().isoformat()
        if existing:
            with self.engine.begin() as conn:
                conn.execute(text(
                    "UPDATE knowledge_docs SET "
                    "pack_id = :pack_id, title = :title, publisher = :publisher, text_content = :text_content, "
                    "fetched_at = :fetched_at, fetch_status = :fetch_status, content_excerpt = :content_excerpt, "
                    "content_sha256 = :content_sha256, last_verified_at = :last_verified_at "
                    "WHERE id = :id"
                ), {
                    "id": existing["id"],
                    "pack_id": pack_id,
                    "title": title,
                    "publisher": publisher,
                    "text_content": text_content,
                    "fetched_at": fetched_at,
                    "fetch_status": fetch_status,
                    "content_excerpt": content_excerpt,
                    "content_sha256": content_sha256,
                    "last_verified_at": last_verified_at,
                })
            existing.update({
                "pack_id": pack_id,
                "title": title,
                "publisher": publisher,
                "text_content": text_content,
                "fetched_at": fetched_at,
                "fetch_status": fetch_status,
                "content_excerpt": content_excerpt,
                "content_sha256": content_sha256,
                "last_verified_at": last_verified_at,
            })
            return existing
        doc = {
            "id": str(uuid.uuid4()),
            "pack_id": pack_id,
            "title": title,
            "publisher": publisher,
            "source_url": source_url,
            "text_content": text_content,
            "checksum": None,
            "fetched_at": fetched_at,
            "fetch_status": fetch_status,
            "content_excerpt": content_excerpt,
            "content_sha256": content_sha256,
            "last_verified_at": last_verified_at,
            "created_at": now,
        }
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO knowledge_docs "
                "(id, pack_id, title, publisher, source_url, text_content, checksum, fetched_at, fetch_status, content_excerpt, "
                "content_sha256, last_verified_at, created_at) "
                "VALUES (:id, :pack_id, :title, :publisher, :source_url, :text_content, :checksum, :fetched_at, :fetch_status, "
                ":content_excerpt, :content_sha256, :last_verified_at, :created_at)"
            ), doc)
        return doc

    def create_baseline_rule_for_doc(
        self,
        pack_id: str,
        doc_id: str,
        doc_title: str,
        domain_area: str,
    ) -> str:
        now = datetime.utcnow().isoformat()
        rule_id = str(uuid.uuid4())
        phase_map = {
            "immigration": "pre_move",
            "registration": "arrival",
            "tax": "first_tax_year",
            "other": "first_90_days",
        }
        category_map = {
            "immigration": "immigration",
            "registration": "registration",
            "tax": "tax",
            "other": "other",
        }
        baseline_priority_map = {
            "pre_move": 10,
            "arrival": 20,
            "first_90_days": 30,
            "first_tax_year": 40,
        }
        phase = phase_map.get(domain_area, "pre_move")
        category = category_map.get(domain_area, "other")
        baseline_priority = baseline_priority_map.get(phase, 100)
        rule_key = f"AUTO_{domain_area.upper()}_{uuid.uuid4().hex[:8]}"
        guidance_md = (
            "Review the official guidance linked below and confirm which requirements apply to your situation. "
            "Capture any required documents, deadlines, and online accounts you may need. "
            "If unclear, keep this as a checkpoint and ask HR or immigration counsel."
        )
        row = {
            "id": rule_id,
            "pack_id": pack_id,
            "rule_key": rule_key,
            "applies_if": None,
            "title": f"Review official guidance: {doc_title}",
            "phase": phase,
            "category": category,
            "guidance_md": guidance_md,
            "citations": json.dumps([doc_id]),
            "version": 1,
            "supersedes_rule_id": None,
            "is_baseline": 1,
            "baseline_priority": baseline_priority,
            "is_active": 1,
            "created_at": now,
        }
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO knowledge_rules "
                "(id, pack_id, rule_key, applies_if, title, phase, category, guidance_md, citations, version, supersedes_rule_id, "
                "is_baseline, baseline_priority, is_active, created_at) "
                "VALUES (:id, :pack_id, :rule_key, :applies_if, :title, :phase, :category, :guidance_md, :citations, :version, "
                ":supersedes_rule_id, :is_baseline, :baseline_priority, :is_active, :created_at)"
            ), row)
        return rule_id

    def list_knowledge_docs_by_destination(self, destination_country: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT d.* FROM knowledge_docs d "
                "JOIN knowledge_packs p ON p.id = d.pack_id "
                "WHERE p.destination_country = :dest "
                "ORDER BY d.created_at DESC"
            ), {"dest": destination_country}).fetchall()
        return self._rows_to_list(rows)

    def list_knowledge_docs(self, pack_ids: List[str]) -> List[Dict[str, Any]]:
        if not pack_ids:
            return []
        placeholders = ",".join([f":p{i}" for i in range(len(pack_ids))])
        params = {f"p{i}": pid for i, pid in enumerate(pack_ids)}
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                f"SELECT * FROM knowledge_docs WHERE pack_id IN ({placeholders})"
            ), params).fetchall()
        return self._rows_to_list(rows)

    def list_knowledge_docs_by_destination(self, destination_country: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT d.* FROM knowledge_docs d "
                "JOIN knowledge_packs p ON p.id = d.pack_id "
                "WHERE p.destination_country = :dest "
                "ORDER BY COALESCE(d.last_verified_at, d.created_at) DESC"
            ), {"dest": destination_country}).fetchall()
        return self._rows_to_list(rows)

    def list_all_knowledge_docs(self) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM knowledge_docs ORDER BY created_at DESC"
            )).fetchall()
        return self._rows_to_list(rows)

    def count_knowledge_docs_by_destination(self, destination_country: str) -> int:
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT COUNT(*) as count FROM knowledge_docs d "
                "JOIN knowledge_packs p ON p.id = d.pack_id "
                "WHERE p.destination_country = :dest"
            ), {"dest": destination_country}).fetchone()
        return int(row[0] if row else 0)

    def count_knowledge_rules_by_destination(self, destination_country: str) -> int:
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT COUNT(*) as count FROM knowledge_rules r "
                "JOIN knowledge_packs p ON p.id = r.pack_id "
                "WHERE p.destination_country = :dest"
            ), {"dest": destination_country}).fetchone()
        return int(row[0] if row else 0)

    def list_knowledge_rules(self, pack_ids: List[str]) -> List[Dict[str, Any]]:
        if not pack_ids:
            return []
        placeholders = ",".join([f":p{i}" for i in range(len(pack_ids))])
        params = {f"p{i}": pid for i, pid in enumerate(pack_ids)}
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                f"SELECT * FROM knowledge_rules WHERE pack_id IN ({placeholders})"
            ), params).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["applies_if"] = self._json_load(item.get("applies_if"))
            item["citations"] = self._json_load(item.get("citations")) or []
            item["is_baseline"] = bool(item.get("is_baseline"))
            item["baseline_priority"] = int(item.get("baseline_priority") or 100)
            item["is_active"] = bool(item.get("is_active", 1))
        return items

    def upsert_requirement_entity(
        self,
        destination_country: str,
        domain_area: str,
        topic_key: str,
        title: str,
        status: str = "pending",
    ) -> Dict[str, Any]:
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT * FROM requirement_entities WHERE destination_country = :dest AND topic_key = :topic LIMIT 1"
            ), {"dest": destination_country, "topic": topic_key}).fetchone()
        existing = self._row_to_dict(row)
        now = datetime.utcnow().isoformat()
        if existing:
            with self.engine.begin() as conn:
                conn.execute(text(
                    "UPDATE requirement_entities SET domain_area = :domain, title = :title, status = :status, updated_at = :updated_at "
                    "WHERE id = :id"
                ), {
                    "id": existing["id"],
                    "domain": domain_area,
                    "title": title,
                    "status": status,
                    "updated_at": now,
                })
            existing.update({
                "domain_area": domain_area,
                "title": title,
                "status": status,
                "updated_at": now,
            })
            return existing
        entity = {
            "id": str(uuid.uuid4()),
            "destination_country": destination_country,
            "domain_area": domain_area,
            "topic_key": topic_key,
            "title": title,
            "status": status,
            "created_at": now,
            "updated_at": now,
        }
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO requirement_entities "
                "(id, destination_country, domain_area, topic_key, title, status, created_at, updated_at) "
                "VALUES (:id, :destination_country, :domain_area, :topic_key, :title, :status, :created_at, :updated_at)"
            ), entity)
        return entity

    def insert_requirement_facts(self, facts: List[Dict[str, Any]]) -> None:
        if not facts:
            return
        with self.engine.begin() as conn:
            for fact in facts:
                conn.execute(text(
                    "INSERT INTO requirement_facts "
                    "(id, entity_id, fact_type, fact_key, fact_text, applies_to, required_fields, source_doc_id, source_url, "
                    "evidence_quote, confidence, status, created_at) "
                    "VALUES (:id, :entity_id, :fact_type, :fact_key, :fact_text, :applies_to, :required_fields, :source_doc_id, "
                    ":source_url, :evidence_quote, :confidence, :status, :created_at)"
                ), fact)

    def list_requirement_entities(self, destination_country: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            if status:
                rows = conn.execute(text(
                    "SELECT * FROM requirement_entities WHERE destination_country = :dest AND status = :status "
                    "ORDER BY updated_at DESC"
                ), {"dest": destination_country, "status": status}).fetchall()
            else:
                rows = conn.execute(text(
                    "SELECT * FROM requirement_entities WHERE destination_country = :dest ORDER BY updated_at DESC"
                ), {"dest": destination_country}).fetchall()
        return self._rows_to_list(rows)

    def list_requirement_facts(self, entity_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            if status:
                rows = conn.execute(text(
                    "SELECT * FROM requirement_facts WHERE entity_id = :eid AND status = :status ORDER BY created_at DESC"
                ), {"eid": entity_id, "status": status}).fetchall()
            else:
                rows = conn.execute(text(
                    "SELECT * FROM requirement_facts WHERE entity_id = :eid ORDER BY created_at DESC"
                ), {"eid": entity_id}).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["applies_to"] = self._json_load(item.get("applies_to")) or {}
            item["required_fields"] = self._json_load(item.get("required_fields")) or []
        return items

    def list_requirement_facts_by_destination(self, destination_country: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            if status:
                rows = conn.execute(text(
                    "SELECT f.* FROM requirement_facts f "
                    "JOIN requirement_entities e ON e.id = f.entity_id "
                    "WHERE e.destination_country = :dest AND f.status = :status "
                    "ORDER BY f.created_at DESC"
                ), {"dest": destination_country, "status": status}).fetchall()
            else:
                rows = conn.execute(text(
                    "SELECT f.* FROM requirement_facts f "
                    "JOIN requirement_entities e ON e.id = f.entity_id "
                    "WHERE e.destination_country = :dest "
                    "ORDER BY f.created_at DESC"
                ), {"dest": destination_country}).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["applies_to"] = self._json_load(item.get("applies_to")) or {}
            item["required_fields"] = self._json_load(item.get("required_fields")) or []
        return items

    def list_approved_requirement_facts(self, destination_country: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT f.* FROM requirement_facts f "
                "JOIN requirement_entities e ON e.id = f.entity_id "
                "WHERE e.destination_country = :dest AND f.status = 'approved'"
            ), {"dest": destination_country}).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["applies_to"] = self._json_load(item.get("applies_to")) or {}
            item["required_fields"] = self._json_load(item.get("required_fields")) or []
        return items

    def update_requirement_fact_status(
        self,
        fact_ids: List[str],
        status: str,
        reviewer_user_id: str,
        notes: Optional[str] = None,
    ) -> None:
        if not fact_ids:
            return
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            for fid in fact_ids:
                conn.execute(text(
                    "UPDATE requirement_facts SET status = :status WHERE id = :id"
                ), {"status": status, "id": fid})
                conn.execute(text(
                    "INSERT INTO requirement_reviews "
                    "(id, entity_id, fact_id, reviewer_user_id, action, notes, created_at) "
                    "VALUES (:id, :entity_id, :fact_id, :reviewer_user_id, :action, :notes, :created_at)"
                ), {
                    "id": str(uuid.uuid4()),
                    "entity_id": None,
                    "fact_id": fid,
                    "reviewer_user_id": reviewer_user_id,
                    "action": "approve" if status == "approved" else "reject",
                    "notes": notes,
                    "created_at": now,
                })

    def insert_guidance_pack(
        self,
        case_id: str,
        user_id: str,
        destination_country: str,
        profile_snapshot: Dict[str, Any],
        plan: Dict[str, Any],
        checklist: Dict[str, Any],
        markdown: str,
        sources: List[Dict[str, Any]],
        not_covered: List[str],
        coverage: Dict[str, Any],
        guidance_mode: str,
        pack_hash: str,
        rule_set: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        row = {
            "id": str(uuid.uuid4()),
            "case_id": case_id,
            "user_id": user_id,
            "destination_country": destination_country,
            "profile_snapshot": json.dumps(profile_snapshot),
            "plan": json.dumps(plan),
            "checklist": json.dumps(checklist),
            "markdown": markdown,
            "sources": json.dumps(sources),
            "not_covered": json.dumps(not_covered),
            "coverage": json.dumps(coverage),
            "guidance_mode": guidance_mode,
            "pack_hash": pack_hash,
            "rule_set": json.dumps(rule_set),
            "created_at": now,
        }
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO relocation_guidance_packs "
                "(id, case_id, user_id, destination_country, profile_snapshot, plan, checklist, markdown, sources, not_covered, coverage, guidance_mode, pack_hash, rule_set, created_at) "
                "VALUES (:id, :case_id, :user_id, :destination_country, :profile_snapshot, :plan, :checklist, :markdown, :sources, :not_covered, :coverage, :guidance_mode, :pack_hash, :rule_set, :created_at)"
            ), row)
        return row

    def get_latest_guidance_pack(self, case_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Prefers canonical_case_id, falls back to case_id."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT * FROM relocation_guidance_packs "
                "WHERE (canonical_case_id = :cid OR case_id = :cid) AND user_id = :uid ORDER BY created_at DESC LIMIT 1"
            ), {"cid": cid, "uid": user_id}).fetchone()
        item = self._row_to_dict(row)
        if not item:
            return None
        item["profile_snapshot"] = self._json_load(item.get("profile_snapshot")) or {}
        item["plan"] = self._json_load(item.get("plan")) or {}
        item["checklist"] = self._json_load(item.get("checklist")) or {}
        item["sources"] = self._json_load(item.get("sources")) or []
        item["not_covered"] = self._json_load(item.get("not_covered")) or []
        item["coverage"] = self._json_load(item.get("coverage")) or {}
        item["rule_set"] = self._json_load(item.get("rule_set")) or []
        return item

    def insert_rule_evaluation_logs(self, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        with self.engine.begin() as conn:
            for row in rows:
                conn.execute(text(
                    "INSERT INTO rule_evaluation_logs "
                    "(id, trace_id, case_id, user_id, destination_country, rule_id, rule_key, rule_version, "
                    "pack_id, pack_version, applies_if, evaluation_result, was_baseline, injected_for_minimum, "
                    "citations, snapshot_subset, created_at) "
                    "VALUES (:id, :trace_id, :case_id, :user_id, :destination_country, :rule_id, :rule_key, :rule_version, "
                    ":pack_id, :pack_version, :applies_if, :evaluation_result, :was_baseline, :injected_for_minimum, "
                    ":citations, :snapshot_subset, :created_at)"
                ), row)

    def list_rule_evaluation_logs(self, case_id: str, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            if trace_id:
                rows = conn.execute(text(
                    "SELECT * FROM rule_evaluation_logs WHERE case_id = :cid AND trace_id = :tid "
                    "ORDER BY created_at DESC"
                ), {"cid": case_id, "tid": trace_id}).fetchall()
            else:
                rows = conn.execute(text(
                    "SELECT * FROM rule_evaluation_logs WHERE case_id = :cid ORDER BY created_at DESC"
                ), {"cid": case_id}).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["applies_if"] = self._json_load(item.get("applies_if"))
            item["citations"] = self._json_load(item.get("citations")) or []
            item["snapshot_subset"] = self._json_load(item.get("snapshot_subset")) or {}
        return items

    def list_trace_events(self, case_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Prefers canonical_case_id, falls back to case_id."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM relocation_trace_events WHERE (canonical_case_id = :cid OR case_id = :cid) "
                "ORDER BY created_at DESC LIMIT :lim"
            ), {"cid": cid, "lim": limit}).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["input"] = self._json_load(item.get("input_json")) or {}
            item["output"] = self._json_load(item.get("output_json")) or {}
        return items

    def insert_trace_event(
        self,
        trace_id: str,
        case_id: str,
        step_name: str,
        input_payload: Dict[str, Any],
        output_payload: Dict[str, Any],
        status: str,
        error: Optional[str],
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO relocation_trace_events "
                "(id, trace_id, case_id, step_name, input_json, output_json, status, error, created_at) "
                "VALUES (:id, :trace_id, :case_id, :step_name, :input_json, :output_json, :status, :error, :created_at)"
            ), {
                "id": str(uuid.uuid4()),
                "trace_id": trace_id,
                "case_id": case_id,
                "step_name": step_name,
                "input_json": json.dumps(input_payload),
                "output_json": json.dumps(output_payload),
                "status": status,
                "error": error,
                "created_at": now,
            })

    # ------------------------------------------------------------------
    # HR Command Center
    # ------------------------------------------------------------------
    def _command_center_base_join(self) -> str:
        """Join clause for case_assignments -> relocation_cases."""
        if _is_sqlite:
            return "rc.id = COALESCE(NULLIF(TRIM(ca.canonical_case_id), ''), ca.case_id)"
        return "rc.id::text = COALESCE(NULLIF(TRIM(ca.canonical_case_id), ''), ca.case_id)"

    def _command_center_company_where(self) -> str:
        """WHERE clause for company-scoped assignments (needs rc, hu joins)."""
        return "(rc.company_id = :cid OR (rc.company_id IS NULL AND hu.company_id = :cid))"

    def get_command_center_kpis(
        self,
        company_id: Optional[str] = None,
        hr_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Aggregate KPIs. Prefer company_id for company scope; fallback hr_user_id; None = admin (all)."""
        empty = {
            "activeCases": 0, "atRiskCount": 0, "attentionNeededCount": 0,
            "overdueTasksCount": 0, "avgVisaDurationDays": None, "budgetOverrunsCount": 0,
            "actionRequiredCount": 0, "departingSoonCount": 0, "completedCount": 0,
        }
        try:
            join_on = self._command_center_base_join()
            with self.engine.connect() as conn:
                if company_id:
                    sql = f"""
                        SELECT ca.* FROM case_assignments ca
                        LEFT JOIN relocation_cases rc ON {join_on}
                        LEFT JOIN hr_users hu ON hu.profile_id = ca.hr_user_id
                        WHERE {self._command_center_company_where()}
                    """
                    rows = conn.execute(text(sql), {"cid": company_id}).fetchall()
                elif hr_user_id:
                    rows = conn.execute(
                        text("SELECT * FROM case_assignments WHERE hr_user_id = :hr ORDER BY created_at DESC"),
                        {"hr": hr_user_id},
                    ).fetchall()
                else:
                    rows = conn.execute(text("SELECT * FROM case_assignments ORDER BY created_at DESC")).fetchall()
                assignments = self._rows_to_list(rows)
        except Exception:
            return empty

        at_risk = sum(1 for a in assignments if (a.get("risk_status") or "green") == "red")
        attention = sum(1 for a in assignments if (a.get("risk_status") or "green") == "yellow")
        budget_overruns = sum(
            1 for a in assignments
            if a.get("budget_limit") is not None and a.get("budget_estimated") is not None
            and float(a.get("budget_estimated") or 0) > float(a.get("budget_limit") or 0)
        )
        action_required = sum(1 for a in assignments if a.get("status") == "submitted")
        completed = 0
        now = datetime.utcnow()

        def _parse_date(value: Optional[str]) -> Optional[datetime]:
            if not value:
                return None
            try:
                return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except Exception:
                return None

        def _days_until(target: datetime) -> int:
            diff = target - now
            return int(math.ceil(diff.total_seconds() / (60 * 60 * 24)))

        for a in assignments:
            status = a.get("status")
            created_at = _parse_date(a.get("created_at"))
            if status == "approved" and (created_at is None or created_at.year == now.year):
                completed += 1

        departing_soon = 0
        for a in assignments:
            expected = _parse_date(str(a.get("expected_start_date") or ""))
            if expected:
                d = _days_until(expected)
                if 0 <= d <= 30:
                    departing_soon += 1

        a_ids = [a["id"] for a in assignments]
        overdue = 0
        if a_ids:
            try:
                with self.engine.connect() as conn:
                    placeholders = ", ".join(f":a{i}" for i in range(len(a_ids)))
                    r = conn.execute(
                        text(
                            f"SELECT COUNT(*) FROM relocation_tasks "
                            f"WHERE assignment_id IN ({placeholders}) AND status = 'overdue'"
                        ),
                        {f"a{i}": aid for i, aid in enumerate(a_ids)},
                    ).fetchone()
                    overdue = r[0] or 0
            except Exception:
                pass

        return {
            "activeCases": len([a for a in assignments if a.get("status") not in ("closed", "rejected")]),
            "atRiskCount": at_risk,
            "attentionNeededCount": attention,
            "overdueTasksCount": overdue,
            "avgVisaDurationDays": None,
            "budgetOverrunsCount": budget_overruns,
            "actionRequiredCount": action_required,
            "departingSoonCount": departing_soon,
            "completedCount": completed,
        }

    def list_command_center_cases(
        self,
        company_id: Optional[str] = None,
        hr_user_id: Optional[str] = None,
        page: int = 1,
        limit: int = 25,
        risk_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Paginated cases with task %% and risk. Prefer company_id; fallback hr_user_id; None = admin."""
        try:
            join_on = self._command_center_base_join()
            with self.engine.connect() as conn:
                params: Dict[str, Any] = {"limit": limit, "offset": (page - 1) * limit}
                if company_id:
                    where = "WHERE " + self._command_center_company_where()
                    params["cid"] = company_id
                    sql = f"""
                        SELECT ca.id, ca.employee_identifier, ca.status,
                               COALESCE(ca.risk_status, 'green') as risk_status,
                               ca.budget_limit, ca.budget_estimated, ca.expected_start_date,
                               rc.host_country as dest_country
                        FROM case_assignments ca
                        LEFT JOIN relocation_cases rc ON {join_on}
                        LEFT JOIN hr_users hu ON hu.profile_id = ca.hr_user_id
                        {where}
                    """
                elif hr_user_id:
                    where = "WHERE ca.hr_user_id = :hr"
                    params["hr"] = hr_user_id
                    sql = f"""
                        SELECT ca.id, ca.employee_identifier, ca.status,
                               COALESCE(ca.risk_status, 'green') as risk_status,
                               ca.budget_limit, ca.budget_estimated, ca.expected_start_date,
                               rc.host_country as dest_country
                        FROM case_assignments ca
                        LEFT JOIN relocation_cases rc ON {join_on}
                        {where}
                    """
                else:
                    sql = f"""
                        SELECT ca.id, ca.employee_identifier, ca.status,
                               COALESCE(ca.risk_status, 'green') as risk_status,
                               ca.budget_limit, ca.budget_estimated, ca.expected_start_date,
                               rc.host_country as dest_country
                        FROM case_assignments ca
                        LEFT JOIN relocation_cases rc ON {join_on}
                        WHERE 1=1
                    """
                if risk_filter:
                    sql = sql.rstrip() + " AND COALESCE(ca.risk_status, 'green') = :risk"
                    params["risk"] = risk_filter
                sql += " ORDER BY ca.updated_at DESC LIMIT :limit OFFSET :offset"
                rows = conn.execute(text(sql), params).fetchall()

            a_ids = [r._mapping["id"] for r in rows]
            task_stats: Dict[str, Dict[str, Any]] = {}
            if a_ids:
                try:
                    with self.engine.connect() as conn:
                        placeholders = ", ".join(f":a{i}" for i in range(len(a_ids)))
                        tr = conn.execute(
                            text(
                                f"SELECT assignment_id, status, due_date FROM relocation_tasks "
                                f"WHERE assignment_id IN ({placeholders})"
                            ),
                            {f"a{i}": aid for i, aid in enumerate(a_ids)},
                        ).fetchall()
                        for r in tr:
                            m = r._mapping
                            aid = m["assignment_id"]
                            if aid not in task_stats:
                                task_stats[aid] = {"total": 0, "done": 0, "next_overdue": None}
                            task_stats[aid]["total"] += 1
                            if m.get("status") == "done":
                                task_stats[aid]["done"] += 1
                            elif m.get("status") == "overdue" and m.get("due_date"):
                                cur = task_stats[aid]["next_overdue"]
                                task_stats[aid]["next_overdue"] = min(cur, m["due_date"]) if cur else m["due_date"]
                except Exception:
                    pass

            result = []
            for row in rows:
                m = row._mapping
                a_id = m["id"]
                stats = task_stats.get(a_id, {"total": 0, "done": 0, "next_overdue": None})
                pct = round(100 * stats["done"] / stats["total"]) if stats["total"] else 0
                result.append({
                    "id": a_id,
                    "employeeIdentifier": m.get("employee_identifier") or "",
                    "destCountry": m.get("dest_country"),
                    "status": m.get("status") or "",
                    "riskStatus": m.get("risk_status") or "green",
                    "tasksDonePercent": pct,
                    "budgetLimit": m.get("budget_limit"),
                    "budgetEstimated": m.get("budget_estimated"),
                    "nextDeadline": str(stats["next_overdue"]) if stats["next_overdue"] else None,
                })
            return result
        except Exception as e:
            log.warning("list_command_center_cases: %s", e)
            return []

    def get_command_center_case_detail(
        self,
        assignment_id: str,
        company_id: Optional[str] = None,
        hr_user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Full case detail: tasks, budget, events."""
        try:
            join_on = self._command_center_base_join()
            with self.engine.connect() as conn:
                params: Dict[str, Any] = {"aid": assignment_id}
                if company_id:
                    where = "ca.id = :aid AND " + self._command_center_company_where()
                    params["cid"] = company_id
                    sql = f"""
                        SELECT ca.*, rc.host_country as dest_country
                        FROM case_assignments ca
                        LEFT JOIN relocation_cases rc ON {join_on}
                        LEFT JOIN hr_users hu ON hu.profile_id = ca.hr_user_id
                        WHERE {where}
                    """
                elif hr_user_id:
                    where = "ca.id = :aid AND ca.hr_user_id = :hr"
                    params["hr"] = hr_user_id
                    sql = f"""
                        SELECT ca.*, rc.host_country as dest_country
                        FROM case_assignments ca
                        LEFT JOIN relocation_cases rc ON {join_on}
                        WHERE {where}
                    """
                else:
                    sql = f"""
                        SELECT ca.*, rc.host_country as dest_country
                        FROM case_assignments ca
                        LEFT JOIN relocation_cases rc ON {join_on}
                        WHERE ca.id = :aid
                    """
                row = conn.execute(text(sql), params).fetchone()
                if not row:
                    return None
                m = row._mapping
                tasks = []
                try:
                    tr = conn.execute(text(
                        "SELECT * FROM relocation_tasks WHERE assignment_id = :aid ORDER BY due_date"
                    ), {"aid": assignment_id}).fetchall()
                    tasks = self._rows_to_list(tr)
                except Exception:
                    pass
                events = []
                try:
                    er = conn.execute(text(
                        "SELECT * FROM case_events WHERE assignment_id = :aid ORDER BY created_at DESC LIMIT 50"
                    ), {"aid": assignment_id}).fetchall()
                    events = self._rows_to_list(er)
                except Exception:
                    pass
                tasks_done = sum(1 for t in tasks if t.get("status") == "done")
                tasks_overdue = sum(1 for t in tasks if t.get("status") == "overdue")
                phases: Dict[str, List[Dict]] = {}
                for t in tasks:
                    ph = t.get("phase") or "General"
                    if ph not in phases:
                        phases[ph] = []
                    phases[ph].append({"title": t.get("title"), "status": t.get("status"), "due_date": t.get("due_date")})
                return {
                    "id": assignment_id,
                    "employeeIdentifier": m.get("employee_identifier") or "",
                    "destCountry": m.get("dest_country"),
                    "status": m.get("status") or "",
                    "riskStatus": m.get("risk_status") or "green",
                    "budgetLimit": m.get("budget_limit"),
                    "budgetEstimated": m.get("budget_estimated"),
                    "expectedStartDate": str(m.get("expected_start_date")) if m.get("expected_start_date") else None,
                    "tasksTotal": len(tasks),
                    "tasksDone": tasks_done,
                    "tasksOverdue": tasks_overdue,
                    "phases": [{"phase": k, "tasks": v} for k, v in phases.items()],
                    "events": [{"event_type": e.get("event_type"), "description": e.get("description"), "created_at": e.get("created_at")} for e in events],
                }
        except Exception as e:
            log.warning("get_command_center_case_detail: %s", e)
            return None

    def delete_assignment(self, assignment_id: str) -> bool:
        with self.engine.begin() as conn:
            row = conn.execute(text(
                "SELECT case_id FROM case_assignments WHERE id = :id"
            ), {"id": assignment_id}).fetchone()
            if not row:
                return False
            case_id = row._mapping["case_id"]
            try:
                conn.execute(
                    text("DELETE FROM assignment_claim_invites WHERE assignment_id = :aid"),
                    {"aid": assignment_id},
                )
            except (OperationalError, ProgrammingError):
                pass
            conn.execute(text("DELETE FROM assignment_invites WHERE case_id = :cid"), {"cid": case_id})
            conn.execute(text("DELETE FROM case_assignments WHERE id = :id"), {"id": assignment_id})
            conn.execute(text("DELETE FROM relocation_cases WHERE id = :cid"), {"cid": case_id})
        return True

    # ==================================================================
    # Assignment invites (legacy `assignment_invites` + canonical `assignment_claim_invites`)
    # ==================================================================
    # New HR/Admin flows must use `ensure_pending_assignment_invites` only (writes both tables in sync).
    # Do not add standalone `create_assignment_invite` call sites for product features.
    def create_assignment_invite(
        self, invite_id: str, case_id: str, hr_user_id: str,
        employee_identifier: str, token: str,
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO assignment_invites "
                "(id, case_id, hr_user_id, employee_identifier, token, status, created_at) "
                "VALUES (:id, :cid, :hr, :ident, :tok, 'ACTIVE', :ca)"
            ), {
                "id": invite_id, "cid": case_id, "hr": hr_user_id,
                "ident": employee_identifier, "tok": token,
                "ca": datetime.utcnow().isoformat(),
            })

    def create_assignment_claim_invite(
        self,
        invite_id: str,
        assignment_id: str,
        employee_contact_id: str,
        token: str,
        email_normalized: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        en = (email_normalized or "").strip() or None
        with self.engine.begin() as conn:
            self._exec(
                conn,
                "INSERT INTO assignment_claim_invites "
                "(id, assignment_id, employee_contact_id, email_normalized, token, status, "
                "claimed_by_user_id, claimed_at, created_at) "
                "VALUES (:id, :aid, :ecid, :en, :tok, 'pending', NULL, NULL, :ca)",
                {
                    "id": invite_id,
                    "aid": assignment_id,
                    "ecid": employee_contact_id,
                    "en": en,
                    "tok": token,
                    "ca": now,
                },
                op_name="create_assignment_claim_invite",
                request_id=request_id,
            )

    def get_pending_claim_invite_token_for_assignment(self, assignment_id: str) -> Optional[str]:
        if not (assignment_id or "").strip():
            return None
        try:
            with self.engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT token FROM assignment_claim_invites "
                        "WHERE assignment_id = :aid AND status = 'pending' LIMIT 1"
                    ),
                    {"aid": assignment_id.strip()},
                ).fetchone()
            if not row:
                return None
            m = row._mapping if hasattr(row, "_mapping") else dict(row)
            return str(m["token"]) if m.get("token") else None
        except (OperationalError, ProgrammingError):
            return None

    def ensure_pending_assignment_invites(
        self,
        assignment_id: str,
        case_id: str,
        hr_user_id: str,
        employee_contact_id: str,
        stored_identifier: str,
        email_normalized: Optional[str],
        request_id: Optional[str] = None,
    ) -> str:
        """
        Idempotent pending claim for this assignment: reuse existing pending row or create legacy + claim rows.
        Returns invite token (new or existing).
        """
        existing = self.get_pending_claim_invite_token_for_assignment(assignment_id)
        if existing:
            identity_event(
                "identity.invite.pending_ensure",
                outcome="idempotent_reuse",
                request_id=request_id,
                assignment_id=assignment_id,
                employee_contact_id=employee_contact_id,
            )
            return existing
        token = str(uuid.uuid4())
        self.create_assignment_invite(
            str(uuid.uuid4()),
            case_id,
            hr_user_id,
            stored_identifier,
            token,
        )
        try:
            self.create_assignment_claim_invite(
                str(uuid.uuid4()),
                assignment_id,
                employee_contact_id,
                token,
                email_normalized=email_normalized,
                request_id=request_id,
            )
        except IntegrityError:
            # Unique partial index: at most one pending row per assignment; concurrent HR path.
            dup = self.get_pending_claim_invite_token_for_assignment(assignment_id)
            if dup:
                identity_event(
                    "identity.invite.pending_ensure",
                    outcome="idempotent_reuse_concurrent",
                    request_id=request_id,
                    assignment_id=assignment_id,
                    employee_contact_id=employee_contact_id,
                )
                return dup
            raise
        identity_event(
            "identity.invite.pending_ensure",
            outcome="created",
            request_id=request_id,
            assignment_id=assignment_id,
            employee_contact_id=employee_contact_id,
        )
        return token

    def mark_invites_claimed(
        self,
        employee_identifier: str,
        *,
        claimed_by_user_id: Optional[str] = None,
        assignment_id: Optional[str] = None,
    ) -> None:
        ident_raw = (employee_identifier or "").strip()
        ident_norm = normalize_invite_key(ident_raw)
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            if ident_norm:
                conn.execute(
                    text(
                        "UPDATE assignment_invites SET status = 'CLAIMED' "
                        "WHERE LOWER(TRIM(COALESCE(employee_identifier, ''))) = :in2"
                    ),
                    {"in2": ident_norm},
                )
            if assignment_id and claimed_by_user_id:
                try:
                    conn.execute(
                        text(
                            "UPDATE assignment_claim_invites "
                            "SET status = 'claimed', claimed_by_user_id = :uid, claimed_at = :ca "
                            "WHERE assignment_id = :aid AND status = 'pending'"
                        ),
                        {"uid": claimed_by_user_id, "ca": now, "aid": assignment_id},
                    )
                except (OperationalError, ProgrammingError):
                    pass

    # ==================================================================
    # Employee journey data
    # ==================================================================
    def save_employee_answer(self, assignment_id: str, question_id: str, answer: Any) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO employee_answers (assignment_id, question_id, answer_json, created_at) "
                "VALUES (:aid, :qid, :aj, :ca)"
            ), {
                "aid": assignment_id, "qid": question_id,
                "aj": json.dumps(answer), "ca": datetime.utcnow().isoformat(),
            })

    def get_employee_answers(self, assignment_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT question_id, answer_json FROM employee_answers "
                "WHERE assignment_id = :aid ORDER BY created_at"
            ), {"aid": assignment_id}).fetchall()
        return self._rows_to_list(rows)

    def save_employee_profile(self, assignment_id: str, profile: Dict[str, Any]) -> None:
        now = datetime.utcnow().isoformat()
        pj = json.dumps(profile)
        with self.engine.begin() as conn:
            existing = conn.execute(
                text("SELECT 1 FROM employee_profiles WHERE assignment_id = :aid"), {"aid": assignment_id}
            ).fetchone()
            if existing:
                conn.execute(text(
                    "UPDATE employee_profiles SET profile_json = :pj, updated_at = :now WHERE assignment_id = :aid"
                ), {"pj": pj, "now": now, "aid": assignment_id})
            else:
                conn.execute(text(
                    "INSERT INTO employee_profiles (assignment_id, profile_json, updated_at) VALUES (:aid, :pj, :now)"
                ), {"aid": assignment_id, "pj": pj, "now": now})

    def get_employee_profile(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT profile_json FROM employee_profiles WHERE assignment_id = :aid"
            ), {"aid": assignment_id}).fetchone()
        return json.loads(row._mapping["profile_json"]) if row else None

    # ==================================================================
    # Compliance reports
    # ==================================================================
    def save_compliance_report(self, report_id: str, assignment_id: str, report: Dict[str, Any]) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO compliance_reports (id, assignment_id, report_json, created_at) "
                "VALUES (:id, :aid, :rj, :ca)"
            ), {"id": report_id, "aid": assignment_id, "rj": json.dumps(report), "ca": datetime.utcnow().isoformat()})

    def get_latest_compliance_report(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT report_json FROM compliance_reports "
                "WHERE assignment_id = :aid ORDER BY created_at DESC LIMIT 1"
            ), {"aid": assignment_id}).fetchone()
        return json.loads(row._mapping["report_json"]) if row else None

    def save_compliance_run(self, run_id: str, assignment_id: str, report: Dict[str, Any]) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO compliance_runs (id, assignment_id, report_json, created_at) "
                "VALUES (:id, :aid, :rj, :ca)"
            ), {"id": run_id, "aid": assignment_id, "rj": json.dumps(report), "ca": datetime.utcnow().isoformat()})

    def get_latest_compliance_run(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT report_json, created_at FROM compliance_runs "
                "WHERE assignment_id = :aid ORDER BY created_at DESC LIMIT 1"
            ), {"aid": assignment_id}).fetchone()
        if not row:
            return None
        report = json.loads(row._mapping["report_json"])
        report["lastVerified"] = row._mapping["created_at"]
        return report

    # ==================================================================
    # Policy exceptions
    # ==================================================================
    def list_policy_exceptions(self, assignment_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM policy_exceptions WHERE assignment_id = :aid ORDER BY created_at DESC"
            ), {"aid": assignment_id}).fetchall()
        return self._rows_to_list(rows)

    def create_policy_exception(
        self,
        exception_id: str,
        assignment_id: str,
        category: str,
        status: str,
        reason: Optional[str],
        requested_amount: Optional[float],
        requested_by: str,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO policy_exceptions "
                "(id, assignment_id, category, status, reason, requested_amount, requested_by, created_at, updated_at) "
                "VALUES (:id, :aid, :cat, :status, :reason, :amount, :by, :ca, :ua)"
            ), {
                "id": exception_id, "aid": assignment_id, "cat": category,
                "status": status, "reason": reason, "amount": requested_amount,
                "by": requested_by, "ca": now, "ua": now,
            })

    # ==================================================================
    # Compliance actions
    # ==================================================================
    def create_compliance_action(
        self,
        action_id: str,
        assignment_id: str,
        check_id: str,
        action_type: str,
        notes: Optional[str],
        actor_user_id: str,
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO compliance_actions "
                "(id, assignment_id, check_id, action_type, notes, actor_user_id, created_at) "
                "VALUES (:id, :aid, :chk, :atype, :notes, :actor, :ca)"
            ), {
                "id": action_id, "aid": assignment_id, "chk": check_id,
                "atype": action_type, "notes": notes, "actor": actor_user_id,
                "ca": datetime.utcnow().isoformat(),
            })

    def list_compliance_actions(self, assignment_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM compliance_actions WHERE assignment_id = :aid ORDER BY created_at DESC"
            ), {"aid": assignment_id}).fetchall()
        return self._rows_to_list(rows)

    # ==================================================================
    # Admin console operations
    # ==================================================================
    def ensure_profile_record(
        self,
        user_id: str,
        email: Optional[str],
        role: str,
        full_name: Optional[str],
        company_id: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            existing = conn.execute(
                text("SELECT 1 FROM profiles WHERE id = :id"), {"id": user_id}
            ).fetchone()
            if existing:
                if company_id is None:
                    conn.execute(text(
                        "UPDATE profiles SET role = :role, email = :email, full_name = :full_name "
                        "WHERE id = :id"
                    ), {
                        "id": user_id,
                        "role": role,
                        "email": (email or "").strip().lower() if email else None,
                        "full_name": full_name,
                    })
                else:
                    conn.execute(text(
                        "UPDATE profiles SET role = :role, email = :email, full_name = :full_name, company_id = :company_id "
                        "WHERE id = :id"
                    ), {
                        "id": user_id,
                        "role": role,
                        "email": (email or "").strip().lower() if email else None,
                        "full_name": full_name,
                        "company_id": company_id,
                    })
            else:
                conn.execute(text(
                    "INSERT INTO profiles (id, role, email, full_name, company_id, created_at) "
                    "VALUES (:id, :role, :email, :full_name, :company_id, :created_at)"
                ), {
                    "id": user_id,
                    "role": role,
                    "email": (email or "").strip().lower() if email else None,
                    "full_name": full_name,
                    "company_id": company_id,
                    "created_at": now,
                })

    def get_profile_record(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM profiles WHERE id = :id"), {"id": user_id}).fetchone()
        return self._row_to_dict(row)

    def set_profile_company(self, user_id: str, company_id: str) -> None:
        """Set profile company and keep hr_users/employees in sync."""
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE profiles SET company_id = :cid WHERE id = :id"
            ), {"cid": company_id, "id": user_id})
            conn.execute(text(
                "UPDATE hr_users SET company_id = :cid WHERE profile_id = :id"
            ), {"cid": company_id, "id": user_id})
            conn.execute(text(
                "UPDATE employees SET company_id = :cid WHERE profile_id = :id"
            ), {"cid": company_id, "id": user_id})

    def update_profile(
        self,
        person_id: str,
        full_name: Optional[str] = None,
        role: Optional[str] = None,
        company_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> bool:
        """Partial update of profile. Only non-None fields are updated. Returns True if row existed and was updated."""
        updates = []
        params: Dict[str, Any] = {"id": person_id}
        if full_name is not None:
            updates.append("full_name = :full_name")
            params["full_name"] = full_name
        if role is not None:
            r = (role or "").strip().upper()
            if r in ("ADMIN", "HR", "EMPLOYEE", "EMPLOYEE_USER"):
                updates.append("role = :role")
                params["role"] = r
        if company_id is not None:
            updates.append("company_id = :company_id")
            params["company_id"] = company_id.strip() if company_id else None
        if status is not None and _profiles_has_status_column:
            s = (status or "active").lower()
            if s in ("active", "inactive"):
                updates.append("status = :status")
                params["status"] = s
        if not updates:
            return False
        with self.engine.begin() as conn:
            result = conn.execute(
                text(f"UPDATE profiles SET {', '.join(updates)} WHERE id = :id"),
                params,
            )
        return result.rowcount > 0

    def set_profile_role(self, person_id: str, role: str) -> bool:
        r = (role or "").strip().upper()
        if r not in ("ADMIN", "HR", "EMPLOYEE", "EMPLOYEE_USER"):
            r = "EMPLOYEE"
        with self.engine.begin() as conn:
            result = conn.execute(
                text("UPDATE profiles SET role = :role WHERE id = :id"),
                {"role": r, "id": person_id},
            )
        return result.rowcount > 0

    def deactivate_profile(self, person_id: str) -> bool:
        """
        Deactivate a profile. Uses status='inactive' when profiles.status exists; otherwise hard delete.
        """
        try:
            updated = self.update_profile(person_id, status="inactive")
            if updated:
                return True
        except Exception as e:
            _agent_debug_log(
                hypothesis_id="H4",
                location="database.deactivate_profile",
                message="deactivate_profile fallback delete",
                data={"person_id": person_id, "error": str(e)},
            )
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM profiles WHERE id = :id"), {"id": person_id})
        return True

    def create_profile(
        self,
        person_id: str,
        email: str,
        full_name: Optional[str] = None,
        role: str = "EMPLOYEE",
        company_id: Optional[str] = None,
    ) -> None:
        """Insert a new profile (admin provisioning). Idempotent: uses upsert if exists."""
        now = datetime.utcnow().isoformat()
        email_clean = (email or "").strip().lower()
        role_clean = (role or "EMPLOYEE").strip().upper()
        if _is_sqlite:
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO profiles (id, email, full_name, role, company_id)
                        VALUES (:id, :email, :full_name, :role, :company_id)
                        ON CONFLICT(id) DO UPDATE SET
                            email = excluded.email,
                            full_name = excluded.full_name,
                            role = excluded.role,
                            company_id = excluded.company_id
                        """
                    ),
                    {
                        "id": person_id,
                        "email": email_clean,
                        "full_name": full_name,
                        "role": role_clean,
                        "company_id": company_id,
                    },
                )
        else:
            # Postgres: profiles schema may differ between environments; generate columns dynamically.
            with self.engine.begin() as conn:
                cols = conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'profiles'"
                    )
                ).fetchall()
                existing = {r._mapping["column_name"] for r in cols}
                base_cols = ["id", "email", "full_name", "role", "company_id", "created_at", "updated_at"]
                insert_cols = [c for c in base_cols if c in existing]
                params: Dict[str, Any] = {
                    "id": person_id,
                    "email": email_clean,
                    "full_name": full_name,
                    "role": role_clean,
                    "company_id": company_id,
                    "created_at": now,
                    "updated_at": now,
                }
                values_clause = ", ".join(f":{c}" for c in insert_cols)
                update_sets = []
                for c in insert_cols:
                    if c in ("id", "created_at"):
                        continue
                    update_sets.append(f"{c} = EXCLUDED.{c}")
                sql = (
                    f"INSERT INTO profiles ({', '.join(insert_cols)}) "
                    f"VALUES ({values_clause}) "
                    f"ON CONFLICT(id) DO UPDATE SET {', '.join(update_sets)}"
                )
                conn.execute(text(sql), params)

    def get_company_for_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        profile = self.get_profile_record(user_id)
        if not profile or not profile.get("company_id"):
            return None
        return self.get_company(profile["company_id"])

    def get_hr_company_id(self, profile_id: str) -> Optional[str]:
        """
        Resolve company_id for HR user.
        Uses hr_users.company_id when set; if the row exists but company_id is NULL/empty,
        falls back to profiles.company_id (Admin assign-company updates profile; hr_users can lag).
        """
        profile = self.get_profile_record(profile_id)
        pcid = (str(profile["company_id"]).strip() if profile and profile.get("company_id") else "") or None
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT company_id FROM hr_users WHERE profile_id = :pid LIMIT 1"),
                {"pid": profile_id},
            ).fetchone()
        if row:
            v = row._mapping.get("company_id")
            hcid = str(v).strip() if v is not None and str(v).strip() else None
            if hcid:
                return hcid
            return pcid
        return pcid

    def sync_hr_user_company_from_profile(self, profile_id: str) -> None:
        """
        For HR profiles with profiles.company_id set, ensure hr_users row exists and company_id matches.
        Fixes blank HR Company Profile when Admin assigned company but hr_users was missing or NULL.
        """
        if not profile_id:
            return
        profile = self.get_profile_record(profile_id)
        if not profile:
            return
        if (profile.get("role") or "").strip().upper() != "HR":
            return
        cid = profile.get("company_id")
        if not cid or not str(cid).strip():
            return
        self.ensure_hr_user_for_profile(profile_id, str(cid).strip())

    def list_profiles(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        q = (query or "").strip().lower()
        with self.engine.connect() as conn:
            if q:
                rows = conn.execute(text(
                    "SELECT * FROM profiles WHERE LOWER(email) LIKE :q OR LOWER(full_name) LIKE :q ORDER BY created_at DESC"
                ), {"q": f"%{q}%"}).fetchall()
            else:
                rows = conn.execute(text("SELECT * FROM profiles ORDER BY created_at DESC")).fetchall()
        return self._rows_to_list(rows)

    def backfill_profiles_to_test_company(self, company_name: str = "Test company") -> Dict[str, Any]:
        """
        Assign all profiles that have no company to the company named company_name.
        Default role to EMPLOYEE; use ADMIN if in admin_allowlist, HR if in hr_users.
        Syncs hr_users and employees company_id. Returns counts and log info.
        """
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT id FROM companies WHERE LOWER(TRIM(name)) = LOWER(TRIM(:name)) LIMIT 1"),
                {"name": company_name},
            ).fetchone()
        if not row:
            return {"ok": False, "error": f"Company '{company_name}' not found", "profiles_updated": 0}
        test_company_id = row._mapping["id"]
        with self.engine.connect() as conn:
            profiles = conn.execute(
                text(
                    "SELECT id, email, full_name, role, company_id FROM profiles "
                    "WHERE (company_id IS NULL OR TRIM(COALESCE(company_id, '')) = '')"
                ),
                {},
            ).fetchall()
        updated = 0
        role_defaulted = 0
        for p in profiles:
            pid = p._mapping["id"]
            email = (p._mapping.get("email") or "").strip().lower()
            current_role = (p._mapping.get("role") or "").strip()
            new_company = test_company_id
            new_role = current_role
            if not new_role or new_role not in ("ADMIN", "HR", "EMPLOYEE", "EMPLOYEE_USER"):
                if self.is_admin_allowlisted(email):
                    new_role = "ADMIN"
                else:
                    with self.engine.connect() as conn:
                        hr_row = conn.execute(
                            text("SELECT 1 FROM hr_users WHERE profile_id = :pid LIMIT 1"), {"pid": pid}
                        ).fetchone()
                    if hr_row:
                        new_role = "HR"
                    else:
                        new_role = "EMPLOYEE"
                role_defaulted += 1
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE profiles SET company_id = :cid, role = :role WHERE id = :id"
                    ),
                    {"cid": new_company, "role": new_role, "id": pid},
                )
                conn.execute(
                    text(
                        "UPDATE hr_users SET company_id = :cid WHERE profile_id = :id AND (company_id IS NULL OR TRIM(COALESCE(company_id, '')) = '')"
                    ),
                    {"cid": new_company, "id": pid},
                )
                conn.execute(
                    text(
                        "UPDATE employees SET company_id = :cid WHERE profile_id = :id AND (company_id IS NULL OR TRIM(COALESCE(company_id, '')) = '')"
                    ),
                    {"cid": new_company, "id": pid},
                )
            updated += 1
        log.info(
            "backfill_profiles_to_test_company: company=%s company_id=%s profiles_updated=%s role_defaulted=%s",
            company_name,
            test_company_id,
            updated,
            role_defaulted,
        )
        return {
            "ok": True,
            "company_id": test_company_id,
            "company_name": company_name,
            "profiles_updated": updated,
            "role_defaulted": role_defaulted,
        }

    def backfill_assignments_to_test_company(self, company_name: str = "Test company") -> Dict[str, Any]:
        """
        Set relocation_cases.company_id to the given company for all cases that have no company.
        This makes assignments show under that company in the admin list (company filter).
        Does not duplicate records; only updates existing relocation_cases rows.
        """
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT id FROM companies WHERE LOWER(TRIM(name)) = LOWER(TRIM(:name)) LIMIT 1"),
                {"name": company_name},
            ).fetchone()
        if not row:
            return {"ok": False, "error": f"Company '{company_name}' not found", "cases_updated": 0}
        test_company_id = row._mapping["id"]
        with self.engine.begin() as conn:
            if _is_sqlite:
                result = conn.execute(
                    text(
                        "UPDATE relocation_cases SET company_id = :cid "
                        "WHERE company_id IS NULL OR TRIM(COALESCE(company_id, '')) = ''"
                    ),
                    {"cid": test_company_id},
                )
            else:
                result = conn.execute(
                    text(
                        "UPDATE relocation_cases SET company_id = :cid "
                        "WHERE company_id IS NULL OR TRIM(COALESCE(company_id, '')) = ''"
                    ),
                    {"cid": test_company_id},
                )
        updated = result.rowcount if hasattr(result, "rowcount") else 0
        log.info(
            "backfill_assignments_to_test_company: company=%s company_id=%s cases_updated=%s",
            company_name,
            test_company_id,
            updated,
        )
        return {
            "ok": True,
            "company_id": test_company_id,
            "company_name": company_name,
            "cases_updated": updated,
        }

    def ensure_test_company_has_hr_user(self, company_name: str = "Test company") -> Dict[str, Any]:
        """
        Ensure the Test company has at least one HR user so the admin console is usable.
        Only adds an hr_users row when inferable: pick one profile linked to Test company with role ADMIN.
        Non-destructive: does not overwrite or remove existing hr_users.
        Returns: ok, hr_added, profile_id, ambiguous_reason.
        """
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT id FROM companies WHERE LOWER(TRIM(name)) = LOWER(TRIM(:name)) LIMIT 1"),
                {"name": company_name},
            ).fetchone()
        if not row:
            return {"ok": False, "hr_added": False, "ambiguous_reason": f"Company '{company_name}' not found"}
        test_company_id = row._mapping["id"]
        with self.engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) AS n FROM hr_users WHERE company_id = :cid"),
                {"cid": test_company_id},
            ).fetchone()
        hr_count = count._mapping["n"] if count else 0
        if hr_count >= 1:
            return {"ok": True, "hr_added": False, "profile_id": None, "ambiguous_reason": None}
        with self.engine.connect() as conn:
            candidates = conn.execute(
                text(
                    "SELECT id, email, full_name FROM profiles "
                    "WHERE company_id = :cid AND TRIM(COALESCE(role, '')) = 'ADMIN' "
                    "ORDER BY email ASC LIMIT 2"
                ),
                {"cid": test_company_id},
            ).fetchall()
        if not candidates:
            return {
                "ok": False,
                "hr_added": False,
                "profile_id": None,
                "ambiguous_reason": "No ADMIN profile linked to Test company; cannot infer HR user",
            }
        profile_id = candidates[0]._mapping["id"]
        hr_id = str(uuid.uuid4())
        self.create_hr_user(hr_id, test_company_id, profile_id, None)
        log.info(
            "ensure_test_company_has_hr_user: company=%s profile_id=%s (inferred from ADMIN)",
            company_name,
            profile_id,
        )
        return {
            "ok": True,
            "hr_added": True,
            "profile_id": profile_id,
            "ambiguous_reason": None,
        }

    def add_admin_allowlist(self, email: str, added_by_user_id: Optional[str]) -> None:
        now = datetime.utcnow().isoformat()
        email_norm = (email or "").strip().lower()
        if not email_norm:
            return
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO admin_allowlist (email, enabled, added_by_user_id, created_at) "
                "VALUES (:email, 1, :added_by, :created_at) "
                "ON CONFLICT(email) DO UPDATE SET enabled = 1, added_by_user_id = excluded.added_by_user_id"
            ), {"email": email_norm, "added_by": added_by_user_id, "created_at": now})

    def is_admin_allowlisted(self, email: str) -> bool:
        email_norm = (email or "").strip().lower()
        if not email_norm:
            return False
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT enabled FROM admin_allowlist WHERE email = :email"
            ), {"email": email_norm}).fetchone()
        return bool(row and row._mapping.get("enabled") == 1)

    def log_audit(
        self,
        actor_user_id: str,
        action_type: str,
        target_type: str,
        target_id: Optional[str],
        reason: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append-only audit log. Never raises: failures are logged and ignored so callers are not broken."""
        now = datetime.utcnow().isoformat()
        try:
            with self.engine.begin() as conn:
                conn.execute(text(
                    "INSERT INTO audit_log (id, actor_user_id, action_type, target_type, target_id, reason, metadata_json, created_at) "
                    "VALUES (:id, :actor, :action, :target_type, :target_id, :reason, :meta, :created_at)"
                ), {
                    "id": str(uuid.uuid4()),
                    "actor": actor_user_id,
                    "action": action_type,
                    "target_type": target_type,
                    "target_id": target_id,
                    "reason": reason,
                    "meta": json.dumps(metadata or {}),
                    "created_at": now,
                })
        except Exception as e:
            log.warning("log_audit failed (non-fatal): %s", e)

    def list_companies(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        q = (query or "").strip().lower()
        with self.engine.connect() as conn:
            if q:
                rows = conn.execute(text(
                    "SELECT * FROM companies WHERE LOWER(name) LIKE :q ORDER BY created_at DESC"
                ), {"q": f"%{q}%"}).fetchall()
            else:
                rows = conn.execute(text("SELECT * FROM companies ORDER BY created_at DESC")).fetchall()
        return self._rows_to_list(rows)

    def get_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM companies WHERE id = :id"), {"id": company_id}).fetchone()
        return self._row_to_dict(row)

    def get_company_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find company by exact name match (case-sensitive)."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM companies WHERE TRIM(name) = :name LIMIT 1"),
                {"name": (name or "").strip()},
            ).fetchone()
        return self._row_to_dict(row)

    TEST_COMPANY_FIXED_ID = "110854ad-3c85-4291-a484-0b43effb680e"

    def run_admin_reconciliation_backfill_test_company(
        self, test_company_name: str = "Test company"
    ) -> Dict[str, Any]:
        """
        One-time non-destructive backfill: link orphan profiles, hr_users, and relocation_cases
        to Test company. Uses fixed company_id 110854ad-3c85-4291-a484-0b43effb680e when that
        company exists; otherwise falls back to lookup by exact name and creates if missing.
        Does not overwrite existing non-null linkage.
        Returns summary counts.
        """
        name = (test_company_name or "").strip()
        if not name:
            return {"ok": False, "error": "test_company_name is required", "summary": {}}
        test_id = self.TEST_COMPANY_FIXED_ID
        with self.engine.connect() as conn:
            by_id = conn.execute(
                text("SELECT id, name FROM companies WHERE id = :id LIMIT 1"),
                {"id": test_id},
            ).fetchone()
            if by_id:
                log.info("admin_reconciliation: using existing Test company id=%s name=%s", test_id, by_id._mapping.get("name"))
            else:
                # Create Test company with fixed ID so all backfill targets this UUID
                self.create_company(
                    company_id=test_id,
                    name=name,
                    country=None,
                    status="active",
                    plan_tier="low",
                )
                log.info("admin_reconciliation: created Test company id=%s name=%s", test_id, name)
        summary: Dict[str, Any] = {
            "test_company_id": test_id,
            "profiles_linked": 0,
            "hr_users_linked": 0,
            "relocation_cases_linked": 0,
        }
        with self.engine.begin() as conn:
            # Profiles: set company_id where null or empty (profiles table may not have updated_at in SQLite)
            r = conn.execute(
                text(
                    "UPDATE profiles SET company_id = :tid "
                    "WHERE (company_id IS NULL OR TRIM(COALESCE(company_id, '')) = '')"
                ),
                {"tid": test_id},
            )
            summary["profiles_linked"] = r.rowcount
            # hr_users
            r = conn.execute(
                text(
                    "UPDATE hr_users SET company_id = :tid "
                    "WHERE (company_id IS NULL OR TRIM(COALESCE(company_id, '')) = '')"
                ),
                {"tid": test_id},
            )
            summary["hr_users_linked"] = r.rowcount
            # relocation_cases
            r = conn.execute(
                text(
                    "UPDATE relocation_cases SET company_id = :tid, updated_at = COALESCE(updated_at, :now) "
                    "WHERE (company_id IS NULL OR TRIM(COALESCE(company_id, '')) = '')"
                ),
                {"tid": test_id, "now": datetime.utcnow().isoformat()},
            )
            summary["relocation_cases_linked"] = r.rowcount
        log.info(
            "admin_reconciliation backfill test_company: profiles_linked=%s hr_users_linked=%s cases_linked=%s",
            summary["profiles_linked"],
            summary["hr_users_linked"],
            summary["relocation_cases_linked"],
        )
        return {"ok": True, "summary": summary}

    def rebuild_test_company_graph(self) -> Dict[str, Any]:
        """
        Rebuild canonical Test company graph in the current DB.
        - Uses TEST_COMPANY_FIXED_ID as the canonical company id.
        - Reassigns non-admin profiles, hr_users, employees, and relocation_cases to this company
          when they are demo/test data.
        - Ensures HR and employee seats exist for HR/EMPLOYEE profiles.
        - Repairs relocation_cases.employee_id and hr_user_id when possible.
        Idempotent: running multiple times converges to the same graph.
        """
        test_id = self.TEST_COMPANY_FIXED_ID
        now = datetime.utcnow().isoformat()
        created: Dict[str, Any] = {
            "profiles_linked": 0,
            "hr_users_linked": 0,
            "employees_linked": 0,
            "relocation_cases_linked": 0,
            "case_assignments_repaired": 0,
            "policies_linked": 0,
        }

        # Ensure Test company exists
        self.create_company(
            company_id=test_id,
            name="Test company",
            country=None,
            status="active",
            plan_tier="low",
        )

        # Link non-admin profiles that look like demo/test into Test company
        with self.engine.begin() as conn:
            r = conn.execute(
                text(
                    """
                    UPDATE profiles
                    SET company_id = :cid
                    WHERE COALESCE(role,'') <> 'ADMIN'
                      AND (company_id IS NULL OR TRIM(company_id) = '' OR company_id = 'demo-company-001')
                    """
                ),
                {"cid": test_id},
            )
            created["profiles_linked"] = r.rowcount

        # Repoint hr_users and employees rows with demo company to Test company
        with self.engine.begin() as conn:
            r = conn.execute(
                text("UPDATE hr_users SET company_id = :cid WHERE company_id = 'demo-company-001'"),
                {"cid": test_id},
            )
            created["hr_users_linked"] += r.rowcount
            r = conn.execute(
                text("UPDATE employees SET company_id = :cid WHERE company_id = 'demo-company-001'"),
                {"cid": test_id},
            )
            created["employees_linked"] += r.rowcount

        # Ensure HR seats exist for HR profiles
        with self.engine.begin() as conn:
            hr_profiles = conn.execute(
                text("SELECT id FROM profiles WHERE role = 'HR' AND company_id = :cid"),
                {"cid": test_id},
            ).fetchall()
            existing_hr = conn.execute(
                text("SELECT DISTINCT profile_id FROM hr_users"),
                {},
            ).fetchall()
            existing_hr_ids = {r._mapping["profile_id"] for r in existing_hr}
            for r in hr_profiles:
                pid = r._mapping["id"]
                if pid in existing_hr_ids:
                    continue
                hr_id = f"hr-{pid}"
                conn.execute(
                    text(
                        "INSERT INTO hr_users (id, company_id, profile_id, permissions_json, created_at) "
                        "VALUES (:id, :cid, :pid, :perms, :ca)"
                    ),
                    {
                        "id": hr_id,
                        "cid": test_id,
                        "pid": pid,
                        "perms": '{"can_manage_policy": true}',
                        "ca": now,
                    },
                )
                created["hr_users_linked"] += 1

        # Ensure employee seats exist for employee/employee_user profiles
        with self.engine.begin() as conn:
            emp_profiles = conn.execute(
                text(
                    "SELECT id FROM profiles "
                    "WHERE role IN ('EMPLOYEE','EMPLOYEE_USER') AND company_id = :cid"
                ),
                {"cid": test_id},
            ).fetchall()
            existing_emp = conn.execute(
                text("SELECT DISTINCT profile_id FROM employees"),
                {},
            ).fetchall()
            existing_emp_ids = {r._mapping["profile_id"] for r in existing_emp}
            for r in emp_profiles:
                pid = r._mapping["id"]
                if pid in existing_emp_ids:
                    continue
                emp_id = f"emp-{pid}"
                conn.execute(
                    text(
                        "INSERT INTO employees (id, company_id, profile_id, band, assignment_type, relocation_case_id, status, created_at) "
                        "VALUES (:id, :cid, :pid, NULL, NULL, NULL, 'active', :ca)"
                    ),
                    {"id": emp_id, "cid": test_id, "pid": pid, "ca": now},
                )
                created["employees_linked"] += 1

        # Repoint relocation_cases for demo company or null company_id
        with self.engine.begin() as conn:
            r = conn.execute(
                text(
                    """
                    UPDATE relocation_cases
                    SET company_id = :cid, updated_at = :now
                    WHERE company_id = 'demo-company-001'
                       OR company_id IS NULL OR TRIM(COALESCE(company_id,'')) = ''
                    """
                ),
                {"cid": test_id, "now": now},
            )
            created["relocation_cases_linked"] = r.rowcount

        # Attempt to fix relocation_cases.employee_id from employees table when missing
        with self.engine.begin() as conn:
            # Cases with null employee_id but matching employees.relocation_case_id
            rows = conn.execute(
                text(
                    """
                    SELECT rc.id AS case_id, e.id AS employee_id
                    FROM relocation_cases rc
                    JOIN employees e ON e.relocation_case_id = rc.id
                    WHERE (rc.employee_id IS NULL OR TRIM(COALESCE(rc.employee_id,'')) = '')
                    """
                ),
                {},
            ).fetchall()
            for row in rows:
                conn.execute(
                    text("UPDATE relocation_cases SET employee_id = :eid, updated_at = :now WHERE id = :cid"),
                    {"eid": row._mapping["employee_id"], "cid": row._mapping["case_id"], "now": now},
                )

        # Assignments: nothing to change for canonical counts here; linkage via company_id already fixed via cases/hr_users
        # Leave created['case_assignments_repaired'] for future detailed repair logic if needed.

        return created

    def create_company(
        self,
        company_id: str,
        name: str,
        country: Optional[str] = None,
        size_band: Optional[str] = None,
        address: Optional[str] = None,
        phone: Optional[str] = None,
        hr_contact: Optional[str] = None,
        legal_name: Optional[str] = None,
        website: Optional[str] = None,
        hq_city: Optional[str] = None,
        industry: Optional[str] = None,
        logo_url: Optional[str] = None,
        brand_color: Optional[str] = None,
        default_destination_country: Optional[str] = None,
        support_email: Optional[str] = None,
        default_working_location: Optional[str] = None,
        status: Optional[str] = None,
        plan_tier: Optional[str] = None,
        hr_seat_limit: Optional[int] = None,
        employee_seat_limit: Optional[int] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        status_val = (status or "active").lower() if status else "active"
        plan_val = (plan_tier or "low").lower() if plan_tier else "low"
        if plan_val not in ("low", "medium", "premium"):
            plan_val = "low"
        params = {
            "id": company_id,
            "name": name,
            "country": country,
            "size_band": size_band,
            "address": address,
            "phone": phone,
            "hr_contact": hr_contact,
            "created_at": now,
            "legal_name": legal_name,
            "website": website,
            "hq_city": hq_city,
            "industry": industry,
            "logo_url": logo_url,
            "brand_color": brand_color,
            "updated_at": now,
            "default_destination_country": default_destination_country,
            "support_email": support_email,
            "default_working_location": default_working_location,
            "status": status_val,
            "plan_tier": plan_val,
            "hr_seat_limit": hr_seat_limit,
            "employee_seat_limit": employee_seat_limit,
        }

        with self.engine.begin() as conn:
            # Production Postgres may not yet have the newer columns (status, plan_tier, hr_seat_limit, employee_seat_limit).
            # Build the INSERT/UPSERT dynamically based on actual columns to avoid UndefinedColumn errors.
            company_cols = {
                row._mapping["column_name"]
                for row in conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'companies'"
                    )
                ).fetchall()
            }

            base_cols = [
                "id",
                "name",
                "country",
                "size_band",
                "address",
                "phone",
                "hr_contact",
                "created_at",
                "legal_name",
                "website",
                "hq_city",
                "industry",
                "logo_url",
                "brand_color",
                "updated_at",
                "default_destination_country",
                "support_email",
                "default_working_location",
            ]
            optional_cols = [
                "status",
                "plan_tier",
                "hr_seat_limit",
                "employee_seat_limit",
            ]

            insert_cols = [c for c in base_cols if c in company_cols] + [
                c for c in optional_cols if c in company_cols
            ]
            values_clause = ", ".join(f":{c}" for c in insert_cols)
            columns_clause = ", ".join(insert_cols)

            # Build ON CONFLICT update set only for columns that actually exist
            update_sets = [
                "name = excluded.name",
                "country = excluded.country",
                "size_band = excluded.size_band",
                "address = excluded.address",
                "phone = excluded.phone",
                "hr_contact = excluded.hr_contact",
                "legal_name = COALESCE(excluded.legal_name, companies.legal_name)",
                "website = COALESCE(excluded.website, companies.website)",
                "hq_city = COALESCE(excluded.hq_city, companies.hq_city)",
                "industry = COALESCE(excluded.industry, companies.industry)",
                "logo_url = COALESCE(excluded.logo_url, companies.logo_url)",
                "brand_color = COALESCE(excluded.brand_color, companies.brand_color)",
                "updated_at = excluded.updated_at",
                "default_destination_country = COALESCE(excluded.default_destination_country, companies.default_destination_country)",
                "support_email = COALESCE(excluded.support_email, companies.support_email)",
                "default_working_location = COALESCE(excluded.default_working_location, companies.default_working_location)",
            ]
            if "status" in company_cols:
                update_sets.append("status = COALESCE(excluded.status, companies.status)")
            if "plan_tier" in company_cols:
                update_sets.append("plan_tier = COALESCE(excluded.plan_tier, companies.plan_tier)")
            if "hr_seat_limit" in company_cols:
                update_sets.append(
                    "hr_seat_limit = COALESCE(excluded.hr_seat_limit, companies.hr_seat_limit)"
                )
            if "employee_seat_limit" in company_cols:
                update_sets.append(
                    "employee_seat_limit = COALESCE(excluded.employee_seat_limit, companies.employee_seat_limit)"
                )

            sql = f"""
                INSERT INTO companies ({columns_clause})
                VALUES ({values_clause})
                ON CONFLICT(id) DO UPDATE SET
                {", ".join(update_sets)}
            """
            conn.execute(text(sql), params)

    def update_company(
        self,
        company_id: str,
        name: Optional[str] = None,
        country: Optional[str] = None,
        size_band: Optional[str] = None,
        address: Optional[str] = None,
        phone: Optional[str] = None,
        hr_contact: Optional[str] = None,
        legal_name: Optional[str] = None,
        website: Optional[str] = None,
        hq_city: Optional[str] = None,
        industry: Optional[str] = None,
        logo_url: Optional[str] = None,
        brand_color: Optional[str] = None,
        default_destination_country: Optional[str] = None,
        support_email: Optional[str] = None,
        default_working_location: Optional[str] = None,
        status: Optional[str] = None,
        plan_tier: Optional[str] = None,
        hr_seat_limit: Optional[int] = None,
        employee_seat_limit: Optional[int] = None,
    ) -> bool:
        """Update company by id. Only provided (non-None) fields are updated. Returns True if row was updated."""
        updates = []
        params: Dict[str, Any] = {"id": company_id}
        if name is not None:
            updates.append("name = :name")
            params["name"] = name
        if country is not None:
            updates.append("country = :country")
            params["country"] = country
        if size_band is not None:
            updates.append("size_band = :size_band")
            params["size_band"] = size_band
        if address is not None:
            updates.append("address = :address")
            params["address"] = address
        if phone is not None:
            updates.append("phone = :phone")
            params["phone"] = phone
        if hr_contact is not None:
            updates.append("hr_contact = :hr_contact")
            params["hr_contact"] = hr_contact
        if legal_name is not None:
            updates.append("legal_name = :legal_name")
            params["legal_name"] = legal_name
        if website is not None:
            updates.append("website = :website")
            params["website"] = website
        if hq_city is not None:
            updates.append("hq_city = :hq_city")
            params["hq_city"] = hq_city
        if industry is not None:
            updates.append("industry = :industry")
            params["industry"] = industry
        if logo_url is not None:
            updates.append("logo_url = :logo_url")
            params["logo_url"] = logo_url
        if brand_color is not None:
            updates.append("brand_color = :brand_color")
            params["brand_color"] = brand_color
        if default_destination_country is not None:
            updates.append("default_destination_country = :default_destination_country")
            params["default_destination_country"] = default_destination_country
        if support_email is not None:
            updates.append("support_email = :support_email")
            params["support_email"] = support_email
        if default_working_location is not None:
            updates.append("default_working_location = :default_working_location")
            params["default_working_location"] = default_working_location
        if status is not None:
            # Some runtimes (like current production) have no companies.status column.
            # We only include this update when the column exists.
            try:
                with self.engine.connect() as conn:
                    row = conn.execute(
                        text(
                            "SELECT 1 FROM information_schema.columns "
                            "WHERE table_name = 'companies' AND column_name = 'status'"
                        )
                    ).fetchone()
                if row:
                    updates.append("status = :status")
                    params["status"] = (status or "active").lower()
            except Exception:
                # If schema lookup fails, skip status update to avoid breaking writes.
                pass
        if plan_tier is not None:
            pt = (plan_tier or "low").lower()
            if pt in ("low", "medium", "premium"):
                updates.append("plan_tier = :plan_tier")
                params["plan_tier"] = pt
        if hr_seat_limit is not None:
            updates.append("hr_seat_limit = :hr_seat_limit")
            params["hr_seat_limit"] = hr_seat_limit
        if employee_seat_limit is not None:
            updates.append("employee_seat_limit = :employee_seat_limit")
            params["employee_seat_limit"] = employee_seat_limit
        if not updates:
            return False
        updates.append("updated_at = :updated_at")
        params["updated_at"] = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            result = conn.execute(
                text(f"UPDATE companies SET {', '.join(updates)} WHERE id = :id"),
                params,
            )
        return result.rowcount > 0

    def deactivate_company(self, company_id: str) -> bool:
        """
        Delete/deactivate a company.
        - If companies.status column exists, mark it inactive.
        - Otherwise, hard delete the row.
        """
        try:
            with self.engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.columns "
                        "WHERE table_name = 'companies' AND column_name = 'status'"
                    )
                ).fetchone()
            if row:
                return self.update_company(company_id, status="inactive")
        except Exception:
            pass
        # Fallback: hard delete.
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM companies WHERE id = :id"), {"id": company_id})
        return True

    def update_company_logo(self, company_id: str, logo_url: Optional[str]) -> None:
        with self.engine.begin() as conn:
            if _is_sqlite:
                conn.execute(text("UPDATE companies SET logo_url = :url WHERE id = :id"), {"url": logo_url, "id": company_id})
            else:
                conn.execute(text("UPDATE companies SET logo_url = :url, updated_at = now() WHERE id = :id"), {"url": logo_url, "id": company_id})

    def create_employee(
        self,
        employee_id: str,
        company_id: str,
        profile_id: str,
        band: Optional[str],
        assignment_type: Optional[str],
        relocation_case_id: Optional[str],
        status: Optional[str],
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO employees (id, company_id, profile_id, band, assignment_type, relocation_case_id, status, created_at) "
                "VALUES (:id, :cid, :pid, :band, :atype, :rcid, :status, :created_at) "
                "ON CONFLICT(id) DO UPDATE SET company_id = excluded.company_id, profile_id = excluded.profile_id, band = excluded.band, "
                "assignment_type = excluded.assignment_type, relocation_case_id = excluded.relocation_case_id, status = excluded.status"
            ), {
                "id": employee_id,
                "cid": company_id,
                "pid": profile_id,
                "band": band,
                "atype": assignment_type,
                "rcid": relocation_case_id,
                "status": status,
                "created_at": now,
            })

    def create_hr_user(
        self,
        hr_id: str,
        company_id: str,
        profile_id: str,
        permissions: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO hr_users (id, company_id, profile_id, permissions_json, created_at) "
                "VALUES (:id, :cid, :pid, :perm, :created_at) "
                "ON CONFLICT(id) DO UPDATE SET company_id = excluded.company_id, profile_id = excluded.profile_id, permissions_json = excluded.permissions_json"
            ), {
                "id": hr_id,
                "cid": company_id,
                "pid": profile_id,
                "perm": json.dumps(permissions or {}),
                "created_at": now,
            })

    def ensure_hr_user_for_profile(self, profile_id: str, company_id: str) -> None:
        """
        Ensure an hr_users row exists for this profile and company (so they appear in
        assignment creation HR dropdown). If a row exists, update company_id; else insert.
        """
        if not profile_id or not company_id:
            return
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT id FROM hr_users WHERE profile_id = :pid LIMIT 1"),
                {"pid": profile_id},
            ).fetchone()
        if row:
            with self.engine.begin() as conn:
                conn.execute(
                    text("UPDATE hr_users SET company_id = :cid WHERE profile_id = :pid"),
                    {"cid": company_id, "pid": profile_id},
                )
        else:
            self.create_hr_user(
                hr_id=str(uuid.uuid4()),
                company_id=company_id,
                profile_id=profile_id,
                permissions={"can_manage_policy": True},
            )

    def ensure_hr_users_for_company(self, company_id: str) -> None:
        """
        Ensure hr_users rows exist for all profiles with role=HR and company_id=company_id
        (backfill so existing HR people appear in assignment creation dropdown).
        """
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id FROM profiles WHERE role = 'HR' AND company_id = :cid"
                ),
                {"cid": company_id},
            ).fetchall()
        for row in rows:
            pid = row._mapping["id"] if hasattr(row, "_mapping") else row[0]
            self.ensure_hr_user_for_profile(pid, company_id)

    def ensure_employee_for_profile(self, profile_id: str, company_id: str) -> None:
        """
        Ensure an employees row exists for this profile and company (so they appear in
        assignment creation employee dropdown). If a row exists, update company_id; else insert.
        """
        if not profile_id or not company_id:
            return
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT id FROM employees WHERE profile_id = :pid LIMIT 1"),
                {"pid": profile_id},
            ).fetchone()
        if row:
            with self.engine.begin() as conn:
                conn.execute(
                    text("UPDATE employees SET company_id = :cid WHERE profile_id = :pid"),
                    {"cid": company_id, "pid": profile_id},
                )
        else:
            self.create_employee(
                employee_id=str(uuid.uuid4()),
                company_id=company_id,
                profile_id=profile_id,
                band=None,
                assignment_type=None,
                relocation_case_id=None,
                status="active",
            )

    def assign_employee_profile_to_company_directory(
        self,
        auth_user_id: str,
        company_id: str,
        *,
        request_id: Optional[str] = None,
    ) -> None:
        """
        Set profiles.company_id and ensure an employees row so the person appears on HR → Employees.
        Used when an employee contact is linked or an assignment is claimed — those flows previously
        only set case_assignments / employee_contacts and left profiles.company_id null.
        """
        _ = request_id
        cid = (company_id or "").strip()
        uid = (auth_user_id or "").strip()
        if not cid or not uid:
            return
        profile = self.get_profile_record(uid)
        if not profile:
            return
        role = (profile.get("role") or "").strip().upper()
        if role not in ("EMPLOYEE", "EMPLOYEE_USER"):
            return
        existing = (str(profile.get("company_id") or "")).strip()
        if existing and existing != cid:
            log.warning(
                "assign_employee_profile_to_company_directory: skip conflicting company_id profile=%s",
                uid[:12],
            )
            return
        if existing == cid:
            self.ensure_employee_for_profile(uid, cid)
            return
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE profiles SET company_id = :cid WHERE id = :pid"),
                {"cid": cid, "pid": uid},
            )
        self.ensure_employee_for_profile(uid, cid)

    def ensure_directory_from_assignments_for_company(self, company_id: str) -> None:
        """
        Backfill HR → Employees for users already attached to assignments (employee_user_id set)
        but missing profiles.company_id — e.g. claimed before directory sync existed.
        """
        cid = (company_id or "").strip()
        if not cid:
            return
        if _is_sqlite:
            join_on_cases = "rc.id = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"
        else:
            join_on_cases = "rc.id::text = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"
        sql = f"""
            SELECT DISTINCT a.employee_user_id AS euid
            FROM case_assignments a
            LEFT JOIN relocation_cases rc ON {join_on_cases}
            LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
            WHERE (rc.company_id = :cid OR (rc.company_id IS NULL AND hu.company_id = :cid))
              AND NULLIF(TRIM(CAST(a.employee_user_id AS TEXT)), '') IS NOT NULL
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"cid": cid}).fetchall()
        seen: Set[str] = set()
        for row in rows:
            m = row._mapping if hasattr(row, "_mapping") else dict(row)
            euid = m.get("euid")
            if not euid:
                continue
            pid = str(euid).strip()
            if not pid or pid in seen:
                continue
            seen.add(pid)
            self.assign_employee_profile_to_company_directory(pid, cid)

    def ensure_employees_for_company(self, company_id: str) -> None:
        """
        Ensure employees rows exist for all profiles with role EMPLOYEE/EMPLOYEE_USER and
        company_id=company_id (backfill so they appear in assignment creation dropdown).
        """
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id FROM profiles WHERE role IN ('EMPLOYEE', 'EMPLOYEE_USER') AND company_id = :cid"
                ),
                {"cid": company_id},
            ).fetchall()
        for row in rows:
            pid = row._mapping["id"] if hasattr(row, "_mapping") else row[0]
            self.ensure_employee_for_profile(pid, company_id)

    def upsert_relocation_case(
        self,
        case_id: str,
        company_id: Optional[str],
        employee_id: Optional[str],
        status: Optional[str],
        stage: Optional[str],
        host_country: Optional[str],
        home_country: Optional[str],
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE relocation_cases SET company_id = :cid, employee_id = :eid, status = :status, "
                "stage = :stage, host_country = :host, home_country = :home, updated_at = :now "
                "WHERE id = :id"
            ), {
                "id": case_id,
                "cid": company_id,
                "eid": employee_id,
                "status": status,
                "stage": stage,
                "host": host_country,
                "home": home_country,
                "now": now,
            })

    def create_support_case(
        self,
        support_case_id: str,
        company_id: str,
        created_by_profile_id: str,
        category: str,
        severity: str,
        status: str,
        summary: Optional[str],
        employee_id: Optional[str] = None,
        hr_profile_id: Optional[str] = None,
        last_error_code: Optional[str] = None,
        last_error_context: Optional[Dict[str, Any]] = None,
        priority: Optional[str] = None,
        assignee_id: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        prio = (priority or "medium").lower() if priority else "medium"
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO support_cases "
                "(id, company_id, created_by_profile_id, employee_id, hr_profile_id, category, severity, status, summary, last_error_code, last_error_context_json, created_at, updated_at, priority, assignee_id) "
                "VALUES (:id, :cid, :cbp, :eid, :hid, :cat, :sev, :status, :summary, :err, :ctx, :created_at, :updated_at, :priority, :assignee_id) "
                "ON CONFLICT(id) DO UPDATE SET company_id = excluded.company_id, status = excluded.status, summary = excluded.summary, "
                "last_error_code = excluded.last_error_code, last_error_context_json = excluded.last_error_context_json, updated_at = excluded.updated_at, priority = excluded.priority, assignee_id = excluded.assignee_id"
            ), {
                "id": support_case_id,
                "cid": company_id,
                "cbp": created_by_profile_id,
                "eid": employee_id,
                "hid": hr_profile_id,
                "cat": category,
                "sev": severity,
                "status": status,
                "summary": summary,
                "err": last_error_code,
                "ctx": json.dumps(last_error_context or {}),
                "created_at": now,
                "updated_at": now,
                "priority": prio,
                "assignee_id": assignee_id,
            })

    def list_employees(self, company_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            if company_id:
                rows = conn.execute(text(
                    "SELECT * FROM employees WHERE company_id = :cid ORDER BY created_at DESC"
                ), {"cid": company_id}).fetchall()
            else:
                rows = conn.execute(text("SELECT * FROM employees ORDER BY created_at DESC")).fetchall()
        return self._rows_to_list(rows)

    def list_employees_with_profiles(
        self, company_id: str
    ) -> List[Dict[str, Any]]:
        """List employees with profile (full_name, email) for HR company-scoped view."""
        sql = """
            SELECT e.id, e.company_id, e.profile_id, e.band, e.assignment_type, e.relocation_case_id, e.status, e.created_at,
                   p.full_name, p.email
            FROM employees e
            LEFT JOIN profiles p ON p.id = e.profile_id
            WHERE e.company_id = :cid
            ORDER BY p.full_name ASC NULLS LAST, e.created_at DESC
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"cid": company_id}).fetchall()
        return self._rows_to_list(rows)

    def get_employee_for_company(
        self, employee_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get employee with profile if they belong to the given company. Returns None if not found or wrong company."""
        sql = """
            SELECT e.id, e.company_id, e.profile_id, e.band, e.assignment_type, e.relocation_case_id, e.status, e.created_at,
                   p.full_name, p.email, p.role
            FROM employees e
            LEFT JOIN profiles p ON p.id = e.profile_id
            WHERE e.id = :eid AND e.company_id = :cid
        """
        with self.engine.connect() as conn:
            row = conn.execute(text(sql), {"eid": employee_id, "cid": company_id}).fetchone()
        return self._row_to_dict(row) if row else None

    def get_employee_by_profile_for_company(
        self, profile_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get employee by profile_id if they belong to the given company."""
        sql = """
            SELECT e.id, e.company_id, e.profile_id, e.band, e.assignment_type, e.relocation_case_id, e.status, e.created_at,
                   p.full_name, p.email, p.role
            FROM employees e
            LEFT JOIN profiles p ON p.id = e.profile_id
            WHERE e.profile_id = :pid AND e.company_id = :cid
        """
        with self.engine.connect() as conn:
            row = conn.execute(text(sql), {"pid": profile_id, "cid": company_id}).fetchone()
        return self._row_to_dict(row) if row else None

    def update_employee_limited(
        self,
        employee_id: str,
        company_id: str,
        *,
        band: Optional[str] = None,
        assignment_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> bool:
        """Update employee fields (band, assignment_type, status). Returns False if not in company."""
        updates = []
        params: Dict[str, Any] = {"eid": employee_id, "cid": company_id}
        if band is not None:
            updates.append("band = :band")
            params["band"] = band
        if assignment_type is not None:
            updates.append("assignment_type = :assignment_type")
            params["assignment_type"] = assignment_type
        if status is not None:
            updates.append("status = :status")
            params["status"] = status
        if not updates:
            return True
        with self.engine.begin() as conn:
            result = conn.execute(
                text(f"UPDATE employees SET {', '.join(updates)} WHERE id = :eid AND company_id = :cid"),
                params,
            )
        return result.rowcount > 0 if hasattr(result, "rowcount") else True

    def list_hr_users(self, company_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            if company_id:
                rows = conn.execute(text(
                    "SELECT * FROM hr_users WHERE company_id = :cid ORDER BY created_at DESC"
                ), {"cid": company_id}).fetchall()
            else:
                rows = conn.execute(text("SELECT * FROM hr_users ORDER BY created_at DESC")).fetchall()
        return self._rows_to_list(rows)

    def list_hr_users_with_profiles(self, company_id: str) -> List[Dict[str, Any]]:
        """HR users for company with name, email, status from profiles. For admin company detail."""
        sql = f"""
            SELECT hu.id, hu.company_id, hu.profile_id, hu.created_at,
                   COALESCE(p.full_name, p.email, hu.profile_id) AS name,
                   p.email AS email,
                   'active' AS status
            FROM hr_users hu
            LEFT JOIN profiles p ON p.id = hu.profile_id
            WHERE hu.company_id = :cid
            ORDER BY hu.created_at DESC
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"cid": company_id}).fetchall()
        return self._rows_to_list(rows)

    def list_relocation_cases(self, company_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        clauses = []
        if company_id:
            clauses.append("company_id = :cid")
            params["cid"] = company_id
        if status:
            clauses.append("status = :status")
            params["status"] = status
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                f"SELECT * FROM relocation_cases {where} ORDER BY updated_at DESC"
            ), params).fetchall()
        return self._rows_to_list(rows)

    def get_relocation_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM relocation_cases WHERE id = :id"),
                {"id": case_id},
            ).fetchone()
        return self._row_to_dict(row)

    def list_support_cases(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        company_id: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        clauses = []
        if status:
            clauses.append("status = :status")
            params["status"] = status
        if severity:
            clauses.append("severity = :severity")
            params["severity"] = severity
        if company_id:
            clauses.append("company_id = :cid")
            params["cid"] = company_id
        if priority:
            clauses.append("priority = :priority")
            params["priority"] = priority
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                f"SELECT * FROM support_cases {where} ORDER BY updated_at DESC"
            ), params).fetchall()
        return self._rows_to_list(rows)

    def update_support_case(
        self,
        support_case_id: str,
        *,
        priority: Optional[str] = None,
        status: Optional[str] = None,
        assignee_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update ticket fields: priority (low|medium|high|urgent), status (open|investigating|blocked|resolved), assignee_id, category."""
        updates = []
        params: Dict[str, Any] = {"id": support_case_id, "now": datetime.utcnow().isoformat()}
        if priority is not None:
            updates.append("priority = :priority")
            params["priority"] = priority
        if status is not None:
            updates.append("status = :status")
            params["status"] = status
        if assignee_id is not None:
            updates.append("assignee_id = :assignee_id")
            params["assignee_id"] = assignee_id
        if category is not None:
            updates.append("category = :category")
            params["category"] = category
        if not updates:
            return self.get_support_case(support_case_id)
        updates.append("updated_at = :now")
        with self.engine.begin() as conn:
            conn.execute(
                text(f"UPDATE support_cases SET {', '.join(updates)} WHERE id = :id"),
                params,
            )
        return self.get_support_case(support_case_id)

    def get_support_case(self, support_case_id: str) -> Optional[Dict[str, Any]]:
        """Get a single support case by id."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM support_cases WHERE id = :id"),
                {"id": support_case_id},
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def add_support_note(self, support_case_id: str, author_user_id: str, note: str) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO support_case_notes (id, support_case_id, author_user_id, note, created_at) "
                "VALUES (:id, :sid, :uid, :note, :created_at)"
            ), {"id": str(uuid.uuid4()), "sid": support_case_id, "uid": author_user_id, "note": note, "created_at": now})

    def list_support_notes(self, support_case_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM support_case_notes WHERE support_case_id = :sid ORDER BY created_at DESC"
            ), {"sid": support_case_id}).fetchall()
        return self._rows_to_list(rows)

    def create_message(
        self,
        message_id: str,
        assignment_id: Optional[str],
        hr_user_id: Optional[str],
        employee_identifier: Optional[str],
        subject: str,
        body: str,
        status: str = "draft",
        sender_user_id: Optional[str] = None,
        recipient_user_id: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        sender = sender_user_id or hr_user_id
        recipient = recipient_user_id
        if not recipient and assignment_id and hr_user_id:
            # HR sent: recipient is employee
            assignment = self.get_assignment_by_id(assignment_id)
            if assignment and assignment.get("employee_user_id"):
                recipient = assignment["employee_user_id"]
            elif assignment and employee_identifier:
                user = self.get_user_by_identifier(employee_identifier)
                if user:
                    recipient = user["id"]
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO messages (id, assignment_id, hr_user_id, employee_identifier, subject, body, status, created_at, delivered_at, sender_user_id, recipient_user_id) "
                "VALUES (:id, :aid, :hr, :emp, :sub, :body, :status, :created_at, :delivered_at, :sender, :recipient)"
            ), {
                "id": message_id,
                "aid": assignment_id,
                "hr": hr_user_id,
                "emp": employee_identifier,
                "sub": subject,
                "body": body,
                "status": status,
                "created_at": now,
                "delivered_at": now,
                "sender": sender,
                "recipient": recipient,
            })

    def list_messages_for_hr(self, hr_user_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT * FROM messages WHERE {_eq_text('hr_user_id', ':hr')} "
                    "ORDER BY created_at DESC"
                ),
                {"hr": hr_user_id},
            ).fetchall()
        return self._rows_to_list(rows)

    def upsert_message_conversation_pref(
        self, user_id: str, assignment_id: str, archived: bool
    ) -> None:
        """Soft-archive or restore a conversation in the HR user's list (per user_id + assignment_id)."""
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            if archived:
                if _is_sqlite:
                    conn.execute(
                        text(
                            "INSERT INTO message_conversation_prefs (user_id, assignment_id, archived_at) "
                            "VALUES (:u, :a, :now) ON CONFLICT (user_id, assignment_id) "
                            "DO UPDATE SET archived_at = excluded.archived_at"
                        ),
                        {"u": user_id, "a": assignment_id, "now": now},
                    )
                else:
                    conn.execute(
                        text(
                            "INSERT INTO message_conversation_prefs (user_id, assignment_id, archived_at) "
                            "VALUES (:u, :a, :now) ON CONFLICT (user_id, assignment_id) "
                            "DO UPDATE SET archived_at = EXCLUDED.archived_at"
                        ),
                        {"u": user_id, "a": assignment_id, "now": now},
                    )
            else:
                conn.execute(
                    text(
                        f"DELETE FROM message_conversation_prefs "
                        f"WHERE {_eq_text('user_id', ':u')} AND {_eq_text('assignment_id', ':a')}"
                    ),
                    {"u": user_id, "a": assignment_id},
                )

    def get_message_by_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Single message row by id (cross-type-safe id match on Postgres)."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT * FROM messages WHERE {_eq_text('id', ':mid')}"),
                {"mid": message_id},
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def delete_message_by_id(self, message_id: str) -> bool:
        """Hard-delete one message row. Caller must enforce authorization."""
        with self.engine.begin() as conn:
            result = conn.execute(
                text(f"DELETE FROM messages WHERE {_eq_text('id', ':mid')}"),
                {"mid": message_id},
            )
        rc = getattr(result, "rowcount", None)
        return bool(rc and rc > 0)

    def list_hr_conversation_summaries(
        self,
        hr_user_id: str,
        hr_company_id: Optional[str],
        is_admin: bool,
        search_q: Optional[str] = None,
        archive_filter: str = "active",
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        One row per assignment_id: preview, counts, archive pref, company-safe HR visibility.
        archive_filter: 'active' | 'archived' | 'all'
        """
        lim = max(1, min(int(limit or 50), 200))
        off = max(0, int(offset or 0))

        if is_admin:
            access_sql = "1 = 1"
            access_params: Dict[str, Any] = {}
        elif hr_company_id:
            access_sql = f"""(
                {_eq_text("a.hr_user_id", ":hr_uid")} OR
                {_eq_text("rc.company_id", ":hr_cid")} OR
                (rc.company_id IS NULL AND {_eq_text("hu.company_id", ":hr_cid")})
            )"""
            access_params = {"hr_uid": hr_user_id, "hr_cid": hr_company_id}
        else:
            access_sql = _eq_text("a.hr_user_id", ":hr_uid")
            access_params = {"hr_uid": hr_user_id}

        if archive_filter == "archived":
            archive_sql = "p.archived_at IS NOT NULL"
        elif archive_filter == "all":
            archive_sql = "1 = 1"
        else:
            archive_sql = "(p.archived_at IS NULL)"

        search_sql = "1 = 1"
        search_params: Dict[str, Any] = {}
        if search_q and search_q.strip():
            term = f"%{search_q.strip().lower()}%"
            search_sql = """(
                LOWER(COALESCE(emp_p.full_name, '')) LIKE :sq OR
                LOWER(COALESCE(emp_p.email, '')) LIKE :sq OR
                LOWER(COALESCE(a.employee_identifier, '')) LIKE :sq OR
                LOWER(COALESCE(a.employee_first_name, '')) LIKE :sq OR
                LOWER(COALESCE(a.employee_last_name, '')) LIKE :sq OR
                LOWER(COALESCE(a.case_id, '')) LIKE :sq OR
                LOWER(COALESCE(a.canonical_case_id, '')) LIKE :sq
            )"""
            search_params["sq"] = term

        unread_sql = "1 = 1"
        if unread_only:
            unread_sql = (
                "(SELECT COUNT(*) FROM messages uq WHERE "
                + _eq_text("uq.assignment_id", "m.assignment_id")
                + " AND "
                + _eq_text("uq.recipient_user_id", ":hr_uid_unread")
                + " "
                "AND uq.read_at IS NULL AND uq.dismissed_at IS NULL) > 0"
            )

        order_clause = (
            "ORDER BY last_message_at DESC NULLS LAST"
            if not _is_sqlite
            else "ORDER BY last_message_at DESC"
        )

        params: Dict[str, Any] = {
            **access_params,
            **search_params,
            "hr_uid": hr_user_id,
            "hr_uid_unread": hr_user_id,
            "lim": lim,
            "off": off,
        }

        sql_full = f"""
            SELECT
                m.assignment_id,
                MAX(m.created_at) AS last_message_at,
                COUNT(*) AS message_count,
                (SELECT body FROM messages m2 WHERE {_eq_text("m2.assignment_id", "m.assignment_id")}
                 ORDER BY m2.created_at DESC LIMIT 1) AS last_body,
                (SELECT subject FROM messages m2s WHERE {_eq_text("m2s.assignment_id", "m.assignment_id")}
                 ORDER BY m2s.created_at DESC LIMIT 1) AS last_subject,
                (SELECT COUNT(*) FROM messages m3 WHERE {_eq_text("m3.assignment_id", "m.assignment_id")}
                 AND {_eq_text("m3.recipient_user_id", ":hr_uid_unread")}
                 AND m3.read_at IS NULL AND m3.dismissed_at IS NULL) AS unread_count,
                MAX(p.archived_at) AS archived_at,
                MAX(a.employee_user_id) AS employee_user_id,
                MAX(a.hr_user_id) AS assignment_hr_user_id,
                MAX(a.employee_identifier) AS employee_identifier,
                MAX(a.employee_first_name) AS employee_first_name,
                MAX(a.employee_last_name) AS employee_last_name,
                MAX(a.status) AS assignment_status,
                MAX(emp_p.full_name) AS employee_full_name,
                MAX(emp_p.email) AS employee_email,
                MAX(COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)) AS case_id
            FROM messages m
            INNER JOIN case_assignments a ON {_eq_text("a.id", "m.assignment_id")}
            LEFT JOIN relocation_cases rc ON {_relocation_cases_join_on("a")}
            LEFT JOIN hr_users hu ON {_eq_text("hu.profile_id", "a.hr_user_id")}
            LEFT JOIN profiles emp_p ON {_eq_text("emp_p.id", "a.employee_user_id")}
            LEFT JOIN message_conversation_prefs p ON {_eq_text("p.user_id", ":hr_uid")} AND {_eq_text("p.assignment_id", "m.assignment_id")}
            WHERE m.assignment_id IS NOT NULL
              AND ({access_sql})
              AND ({archive_sql})
              AND ({search_sql})
              AND ({unread_sql})
            GROUP BY m.assignment_id
            {order_clause}
            LIMIT :lim OFFSET :off
        """

        # Postgres without runtime DDL often lacks: message_conversation_prefs, messages.read_at/*,
        # case_assignments.canonical_case_id / employee_* name columns. Degraded query keeps messages working.
        search_compat_sql = "1 = 1"
        search_compat_params: Dict[str, Any] = {}
        if search_q and search_q.strip():
            term = f"%{search_q.strip().lower()}%"
            search_compat_sql = """(
                LOWER(COALESCE(a.employee_identifier, '')) LIKE :sqc OR
                LOWER(COALESCE(a.case_id, '')) LIKE :sqc
            )"""
            search_compat_params["sqc"] = term
        compat_params = {**access_params, **search_compat_params, "hr_uid": hr_user_id, "lim": lim, "off": off}
        null_arch = "NULL" if _is_sqlite else "CAST(NULL AS TEXT)"
        sql_compat = f"""
            SELECT
                m.assignment_id,
                MAX(m.created_at) AS last_message_at,
                COUNT(*) AS message_count,
                (SELECT body FROM messages m2 WHERE {_eq_text("m2.assignment_id", "m.assignment_id")}
                 ORDER BY m2.created_at DESC LIMIT 1) AS last_body,
                (SELECT subject FROM messages m2s WHERE {_eq_text("m2s.assignment_id", "m.assignment_id")}
                 ORDER BY m2s.created_at DESC LIMIT 1) AS last_subject,
                0 AS unread_count,
                {null_arch} AS archived_at,
                MAX(a.employee_user_id) AS employee_user_id,
                MAX(a.hr_user_id) AS assignment_hr_user_id,
                MAX(a.employee_identifier) AS employee_identifier,
                {null_arch} AS employee_first_name,
                {null_arch} AS employee_last_name,
                MAX(a.status) AS assignment_status,
                MAX(emp_p.full_name) AS employee_full_name,
                MAX(emp_p.email) AS employee_email,
                MAX(a.case_id) AS case_id
            FROM messages m
            INNER JOIN case_assignments a ON {_eq_text("a.id", "m.assignment_id")}
            LEFT JOIN relocation_cases rc ON {_relocation_cases_join_on("a", "simple")}
            LEFT JOIN hr_users hu ON {_eq_text("hu.profile_id", "a.hr_user_id")}
            LEFT JOIN profiles emp_p ON {_eq_text("emp_p.id", "a.employee_user_id")}
            WHERE m.assignment_id IS NOT NULL
              AND ({access_sql})
              AND ({search_compat_sql})
            GROUP BY m.assignment_id
            {order_clause}
            LIMIT :lim OFFSET :off
        """

        rows: List[Any] = []
        try:
            with self.engine.connect() as conn:
                rows = list(conn.execute(text(sql_full), params).fetchall())
            # #region agent log
            _agent_debug_log(
                hypothesis_id="H-conv",
                location="database.list_hr_conversation_summaries",
                message="full query ok",
                data={
                    "row_count": len(rows),
                    "archive_filter": archive_filter,
                    "unread_only": unread_only,
                    "is_admin": is_admin,
                },
            )
            # #endregion
        except (ProgrammingError, OperationalError) as e:
            log.warning(
                "list_hr_conversation_summaries: full query failed (%s), using compat query",
                e,
            )
            # #region agent log
            _agent_debug_log(
                hypothesis_id="H-conv-fallback",
                location="database.list_hr_conversation_summaries",
                message="full query failed; trying compat",
                data={
                    "error_type": type(e).__name__,
                    "error": str(e)[:400],
                },
            )
            # #endregion
            try:
                with self.engine.connect() as conn:
                    rows = list(conn.execute(text(sql_compat), compat_params).fetchall())
                # #region agent log
                _agent_debug_log(
                    hypothesis_id="H-conv-compat",
                    location="database.list_hr_conversation_summaries",
                    message="compat query ok",
                    data={"row_count": len(rows)},
                )
                # #endregion
            except (ProgrammingError, OperationalError) as e2:
                # #region agent log
                _agent_debug_log(
                    hypothesis_id="H-conv-fail",
                    location="database.list_hr_conversation_summaries",
                    message="compat query failed",
                    data={
                        "error_type": type(e2).__name__,
                        "error": str(e2)[:400],
                    },
                )
                # #endregion
                raise

        out: List[Dict[str, Any]] = []
        for row in rows:
            r = dict(row._mapping)
            aid = r.get("assignment_id")
            if not aid:
                continue
            raw_body = r.get("last_body") or ""
            raw_sub = r.get("last_subject") or ""
            preview_src = raw_body.strip() or raw_sub.strip() or ""
            last_body = preview_src[:100]
            if len(preview_src) > 100:
                last_body = last_body.rstrip() + "…"

            fn = (r.get("employee_first_name") or "").strip()
            ln = (r.get("employee_last_name") or "").strip()
            composed = (fn + " " + ln).strip()
            emp_name = (
                r.get("employee_full_name")
                or composed
                or r.get("employee_identifier")
                or "Employee"
            )
            unread = int(r.get("unread_count") or 0)
            out.append({
                "assignment_id": aid,
                "case_id": r.get("case_id"),
                "employee_user_id": r.get("employee_user_id"),
                "employee_name": emp_name,
                "employee_email": r.get("employee_email"),
                "employee_identifier": r.get("employee_identifier"),
                "last_message_preview": last_body,
                "last_message_at": r.get("last_message_at"),
                "message_count": int(r.get("message_count") or 0),
                "unread_count": unread,
                "has_unread": unread > 0,
                "archived_at": r.get("archived_at"),
                "assignment_status": r.get("assignment_status"),
            })
        return out

    def list_messages_for_employee(self, employee_user_id: str) -> List[Dict[str, Any]]:
        assignment = self.get_assignment_for_employee(employee_user_id)
        if not assignment:
            return []
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT * FROM messages WHERE {_eq_text('assignment_id', ':aid')} "
                    "ORDER BY created_at DESC"
                ),
                {"aid": assignment["id"]},
            ).fetchall()
        return self._rows_to_list(rows)

    def mark_conversation_read(self, assignment_id: str, recipient_user_id: str) -> int:
        """Set read_at and dismissed_at for all messages in this assignment to the recipient. Returns count updated."""
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            result = conn.execute(
                text(
                    "UPDATE messages SET read_at = :now, dismissed_at = :now "
                    f"WHERE {_eq_text('assignment_id', ':aid')} "
                    f"AND {_eq_text('recipient_user_id', ':uid')} AND read_at IS NULL"
                ),
                {"now": now, "aid": assignment_id, "uid": recipient_user_id},
            )
        return result.rowcount if hasattr(result, "rowcount") else 0

    def dismiss_message_notification(self, message_id: str, recipient_user_id: str) -> bool:
        """Set dismissed_at for one message. Returns True if updated."""
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            result = conn.execute(
                text(
                    "UPDATE messages SET dismissed_at = :now "
                    f"WHERE {_eq_text('id', ':mid')} "
                    f"AND {_eq_text('recipient_user_id', ':uid')} AND dismissed_at IS NULL"
                ),
                {"now": now, "mid": message_id, "uid": recipient_user_id},
            )
        return (result.rowcount if hasattr(result, "rowcount") else 0) > 0

    def get_unread_message_count(self, recipient_user_id: str) -> int:
        """Count messages where recipient hasn't read and hasn't dismissed."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT COUNT(*) as n FROM messages "
                    f"WHERE {_eq_text('recipient_user_id', ':uid')} "
                    "AND read_at IS NULL AND dismissed_at IS NULL"
                ),
                {"uid": recipient_user_id},
            ).fetchone()
        return row[0] if row else 0

    def list_admin_message_threads(
        self,
        company_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Admin: list message threads (assignment-based) with company/participant context."""
        clauses = ["m.assignment_id IS NOT NULL"]
        params: Dict[str, Any] = {"lim": limit, "off": offset}
        if company_id:
            clauses.append("(rc.company_id = :company_id OR hu.company_id = :company_id)")
            params["company_id"] = company_id
        if user_id:
            clauses.append("(a.hr_user_id = :user_id OR a.employee_user_id = :user_id)")
            params["user_id"] = user_id
        where_sql = " AND ".join(clauses)
        order_clause = "ORDER BY last_message_at DESC NULLS LAST" if not _is_sqlite else "ORDER BY last_message_at DESC"
        sql = f"""
            SELECT
                m.assignment_id,
                MAX(m.created_at) AS last_message_at,
                COUNT(*) AS message_count,
                (SELECT body FROM messages m2 WHERE m2.assignment_id = m.assignment_id ORDER BY m2.created_at DESC LIMIT 1) AS last_body,
                (SELECT COUNT(*) FROM messages m3 WHERE m3.assignment_id = m.assignment_id AND m3.read_at IS NULL) AS unread_count,
                MAX(c.name) AS company_name,
                MAX(rc.company_id) AS case_company_id,
                MAX(hu.company_id) AS hr_company_id,
                MAX(a.employee_user_id) AS employee_user_id,
                MAX(a.hr_user_id) AS hr_user_id,
                MAX(emp_p.full_name) AS employee_full_name,
                MAX(a.employee_identifier) AS employee_identifier,
                MAX(hr_p.full_name) AS hr_full_name,
                MAX(a.status) AS assignment_status
            FROM messages m
            LEFT JOIN case_assignments a ON {_eq_text("a.id", "m.assignment_id")}
            LEFT JOIN relocation_cases rc ON {_relocation_cases_join_on("a")}
            LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
            LEFT JOIN companies c ON c.id = COALESCE(rc.company_id, hu.company_id)
            LEFT JOIN profiles emp_p ON emp_p.id = a.employee_user_id
            LEFT JOIN profiles hr_p ON hr_p.id = a.hr_user_id
            WHERE {where_sql}
            GROUP BY m.assignment_id
            {order_clause}
            LIMIT :lim OFFSET :off
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
        out = []
        for row in rows:
            r = dict(row._mapping)
            aid = r.get("assignment_id")
            if not aid:
                continue
            last_body = (r.get("last_body") or "")[:100]
            if len((r.get("last_body") or "")) > 100:
                last_body = last_body.rstrip() + "…"
            emp_name = r.get("employee_full_name") or r.get("employee_identifier") or "—"
            hr_name = r.get("hr_full_name") or "—"
            parts = [p for p in [hr_name, emp_name] if p and p != "—"]
            unread = int(r.get("unread_count") or 0)
            out.append({
                "thread_id": aid,
                "thread_type": "hr_employee",
                "assignment_id": aid,
                "company_id": r.get("case_company_id") or r.get("hr_company_id"),
                "company_name": r.get("company_name") or "—",
                "employee_name": emp_name,
                "hr_name": hr_name,
                "employee_user_id": r.get("employee_user_id"),
                "hr_user_id": r.get("hr_user_id"),
                "participant_id": r.get("employee_user_id"),
                "participant_name": emp_name,
                "participant_role": "employee",
                "participants": parts or ["—"],
                "last_message_preview": last_body,
                "last_message_at": r.get("last_message_at"),
                "message_count": r.get("message_count", 0),
                "unread_count": unread,
                "has_unread": unread > 0,
                "status": r.get("assignment_status"),
            })
        return out

    def list_messages_by_assignment(self, assignment_id: str) -> List[Dict[str, Any]]:
        """List all messages for an assignment (admin or HR/employee context)."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(f"""
                SELECT m.*, COALESCE(u.name, u.email, u.username) as sender_display_name
                FROM messages m
                LEFT JOIN users u ON {_eq_text("u.id", "COALESCE(m.sender_user_id, m.hr_user_id)")}
                WHERE {_eq_text("m.assignment_id", ":aid")}
                ORDER BY m.created_at ASC
            """),
                {"aid": assignment_id},
            ).fetchall()
        return self._rows_to_list(rows)

    def list_unread_message_notifications(
        self, recipient_user_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """List unread, non-dismissed messages for the recipient with sender name and snippet."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(f"""
                SELECT m.id as message_id, m.assignment_id as conversation_id,
                       m.body, m.created_at,
                       COALESCE(u.name, u.email, u.username, 'HR') as sender_name
                FROM messages m
                LEFT JOIN users u ON {_eq_text("u.id", "COALESCE(m.sender_user_id, m.hr_user_id)")}
                WHERE {_eq_text("m.recipient_user_id", ":uid")}
                  AND m.read_at IS NULL AND m.dismissed_at IS NULL
                ORDER BY m.created_at DESC
                LIMIT :lim
            """),
                {"uid": recipient_user_id, "lim": limit},
            ).fetchall()
        out = []
        for r in rows:
            row = dict(r._mapping)
            body = (row.get("body") or "")[:80]
            if len((row.get("body") or "")) > 80:
                body = body.rstrip() + "…"
            out.append({
                "message_id": row.get("message_id"),
                "conversation_id": row.get("conversation_id") or row.get("assignment_id"),
                "sender_name": row.get("sender_name") or "HR",
                "snippet": body,
                "created_at": row.get("created_at"),
            })
        return out

    def set_admin_session(self, token: str, actor_user_id: str, target_user_id: str, mode: str) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT OR REPLACE INTO admin_sessions (token, actor_user_id, target_user_id, mode, created_at) "
                "VALUES (:token, :actor, :target, :mode, :created_at)"
            ), {"token": token, "actor": actor_user_id, "target": target_user_id, "mode": mode, "created_at": now})

    def clear_admin_session(self, token: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM admin_sessions WHERE token = :token"), {"token": token})

    def get_admin_session(self, token: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM admin_sessions WHERE token = :token"), {"token": token}).fetchone()
        return self._row_to_dict(row)

    def create_eligibility_override(
        self,
        assignment_id: str,
        category: str,
        allowed: bool,
        expires_at: Optional[str],
        note: Optional[str],
        created_by_user_id: str,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO eligibility_overrides (id, assignment_id, category, allowed, expires_at, note, created_by_user_id, created_at) "
                "VALUES (:id, :aid, :cat, :allowed, :expires, :note, :uid, :created_at)"
            ), {
                "id": str(uuid.uuid4()),
                "aid": assignment_id,
                "cat": category,
                "allowed": 1 if allowed else 0,
                "expires": expires_at,
                "note": note,
                "uid": created_by_user_id,
                "created_at": now,
            })

    def purge_inactive_cases(self, active_statuses: List[str]) -> Dict[str, int]:
        """Remove inactive case/assignment data and related records."""
        status_list = [s for s in active_statuses if s]
        if not status_list:
            return {"assignments_deleted": 0, "relocation_cases_deleted": 0}

        placeholders = ", ".join([f":s{i}" for i in range(len(status_list))])
        params = {f"s{i}": status_list[i] for i in range(len(status_list))}

        with self.engine.begin() as conn:
            # Collect assignments to delete
            rows = conn.execute(text(
                f"SELECT id FROM case_assignments WHERE status NOT IN ({placeholders})"
            ), params).fetchall()
            assignment_ids = [r._mapping["id"] for r in rows]

            if assignment_ids:
                id_placeholders = ", ".join([f":a{i}" for i in range(len(assignment_ids))])
                id_params = {f"a{i}": assignment_ids[i] for i in range(len(assignment_ids))}

                conn.execute(text(
                    f"DELETE FROM employee_profiles WHERE assignment_id IN ({id_placeholders})"
                ), id_params)
                conn.execute(text(
                    f"DELETE FROM employee_answers WHERE assignment_id IN ({id_placeholders})"
                ), id_params)
                conn.execute(text(
                    f"DELETE FROM compliance_reports WHERE assignment_id IN ({id_placeholders})"
                ), id_params)
                conn.execute(text(
                    f"DELETE FROM compliance_runs WHERE assignment_id IN ({id_placeholders})"
                ), id_params)
                conn.execute(text(
                    f"DELETE FROM policy_exceptions WHERE assignment_id IN ({id_placeholders})"
                ), id_params)
                conn.execute(text(
                    f"DELETE FROM compliance_actions WHERE assignment_id IN ({id_placeholders})"
                ), id_params)

                conn.execute(text(
                    f"DELETE FROM assignment_invites WHERE case_id IN (SELECT case_id FROM case_assignments WHERE id IN ({id_placeholders}))"
                ), id_params)

                conn.execute(text(
                    f"DELETE FROM case_assignments WHERE id IN ({id_placeholders})"
                ), id_params)

            # Purge relocation_cases not active
            rows_cases = conn.execute(text(
                f"SELECT id FROM relocation_cases WHERE status NOT IN ({placeholders})"
            ), params).fetchall()
            case_ids = [r._mapping["id"] for r in rows_cases]
            if case_ids:
                case_placeholders = ", ".join([f":c{i}" for i in range(len(case_ids))])
                case_params = {f"c{i}": case_ids[i] for i in range(len(case_ids))}
                conn.execute(text(
                    f"DELETE FROM relocation_cases WHERE id IN ({case_placeholders})"
                ), case_params)

        return {
            "assignments_deleted": len(assignment_ids),
            "relocation_cases_deleted": len(case_ids),
        }

    # ==================================================================
    # HR Policies (full policy spec)
    # ==================================================================
    def create_hr_policy(
        self,
        policy_id: str,
        policy_json: Dict[str, Any],
        created_by: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        pj = json.dumps(policy_json)
        status = policy_json.get("status", "draft")
        company_entity = policy_json.get("companyEntity", "")
        effective_date = policy_json.get("effectiveDate", "")
        version = policy_json.get("version", 1)
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO hr_policies "
                "(id, policy_json, status, company_entity, effective_date, created_at, updated_at, created_by, version) "
                "VALUES (:id, :pj, :status, :ce, :ed, :ca, :ua, :cb, :ver)"
            ), {
                "id": policy_id, "pj": pj, "status": status, "ce": company_entity,
                "ed": effective_date, "ca": now, "ua": now, "cb": created_by, "ver": version,
            })

    def update_hr_policy(
        self,
        policy_id: str,
        policy_json: Dict[str, Any],
    ) -> bool:
        now = datetime.utcnow().isoformat()
        pj = json.dumps(policy_json)
        status = policy_json.get("status", "draft")
        company_entity = policy_json.get("companyEntity", "")
        effective_date = policy_json.get("effectiveDate", "")
        version = policy_json.get("version", 1)
        with self.engine.begin() as conn:
            r = conn.execute(text(
                "UPDATE hr_policies SET policy_json = :pj, status = :status, company_entity = :ce, "
                "effective_date = :ed, updated_at = :ua, version = :ver WHERE id = :id"
            ), {"pj": pj, "status": status, "ce": company_entity, "ed": effective_date, "ua": now, "ver": version, "id": policy_id})
            return r.rowcount > 0

    def get_hr_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT policy_json, status, created_at, updated_at, version FROM hr_policies WHERE id = :id"
            ), {"id": policy_id}).fetchone()
        if not row:
            return None
        policy = json.loads(row._mapping["policy_json"])
        policy["_meta"] = {
            "status": row._mapping["status"],
            "created_at": row._mapping["created_at"],
            "updated_at": row._mapping["updated_at"],
            "version": row._mapping["version"],
        }
        return policy

    def list_hr_policies(
        self,
        status_filter: Optional[str] = None,
        company_entity: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            q = "SELECT id, policy_json, status, company_entity, effective_date, created_at, updated_at, version FROM hr_policies WHERE 1=1"
            params: Dict[str, Any] = {}
            if status_filter:
                q += " AND status = :status"
                params["status"] = status_filter
            if company_entity:
                q += " AND company_entity = :ce"
                params["ce"] = company_entity
            q += " ORDER BY effective_date DESC, created_at DESC"
            rows = conn.execute(text(q), params).fetchall()
        result = []
        for row in rows:
            policy = json.loads(row._mapping["policy_json"])
            policy["id"] = row._mapping["id"]
            policy["_meta"] = {
                "status": row._mapping["status"],
                "created_at": row._mapping["created_at"],
                "updated_at": row._mapping["updated_at"],
                "version": row._mapping["version"],
            }
            result.append(policy)
        return result

    def list_hr_policies_by_company(self, company_id: str) -> List[Dict[str, Any]]:
        return self.list_hr_policies(company_entity=company_id)

    def get_published_hr_policy_for_employee(
        self,
        employee_band: str,
        assignment_type: str,
        country_code: Optional[str] = None,
        company_entity: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return the first published policy that matches band, assignment type, optionally country/entity."""
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT id, policy_json FROM hr_policies WHERE status = 'published' "
                "ORDER BY effective_date DESC, created_at DESC"
            )).fetchall()
        for row in rows:
            policy = json.loads(row._mapping["policy_json"])
            bands = policy.get("employeeBands", [])
            types = policy.get("assignmentTypes", [])
            if employee_band in bands and assignment_type in types:
                if company_entity and policy.get("companyEntity") != company_entity:
                    continue
                policy["id"] = row._mapping["id"]
                return policy
        return None

    def delete_hr_policy(self, policy_id: str) -> bool:
        with self.engine.begin() as conn:
            r = conn.execute(text("DELETE FROM hr_policies WHERE id = :id"), {"id": policy_id})
            return r.rowcount > 0

    # ==================================================================
    # Company policy documents + extracted benefits
    # ==================================================================
    def create_company_policy(
        self,
        policy_id: str,
        company_id: str,
        title: str,
        version: Optional[str],
        effective_date: Optional[str],
        file_url: str,
        file_type: str,
        created_by: Optional[str],
        template_source: str = "company_uploaded",
        template_name: Optional[str] = None,
        is_default_template: bool = False,
        request_id: Optional[str] = None,
    ) -> None:
        """
        Insert a row into company_policies. Columns are built from actual schema so production
        Postgres without template_source/template_name/is_default_template still works.
        """
        now = datetime.utcnow().isoformat()
        _col_to_param = {
            "id": "id",
            "company_id": "cid",
            "title": "title",
            "version": "ver",
            "effective_date": "ed",
            "file_url": "url",
            "file_type": "ft",
            "extraction_status": "status",
            "created_by": "cb",
            "created_at": "ca",
            "template_source": "tsrc",
            "template_name": "tname",
            "is_default_template": "isdef",
        }
        _param_values = {
            "id": policy_id,
            "cid": company_id,
            "title": title,
            "ver": version,
            "ed": effective_date,
            "url": file_url,
            "ft": file_type,
            "status": "pending",
            "cb": created_by,
            "ca": now,
            "tsrc": template_source,
            "tname": template_name,
            "isdef": 1 if is_default_template else 0,
        }
        existing: set = set()
        try:
            with self.engine.begin() as conn:
                existing = _get_company_policies_columns(conn)
                core = [
                    "id", "company_id", "title", "version", "effective_date",
                    "file_url", "file_type", "extraction_status", "created_by", "created_at",
                ]
                optional = ["template_source", "template_name", "is_default_template"]
                insert_cols = [c for c in core + optional if c in existing]
                if not insert_cols:
                    raise RuntimeError("company_policies has no columns we can insert")
                placeholders = [f":{_col_to_param[c]}" for c in insert_cols]
                params = {_col_to_param[c]: _param_values[_col_to_param[c]] for c in insert_cols}
                sql = (
                    "INSERT INTO company_policies ("
                    + ", ".join(insert_cols)
                    + ") VALUES ("
                    + ", ".join(placeholders)
                    + ")"
                )
                conn.execute(text(sql), params)
        except Exception as exc:
            log.error(
                "request_id=%s create_company_policy failed company_id=%s policy_id=%s title=%s "
                "company_policies_columns=%s exc_type=%s exc_msg=%s",
                request_id or "?",
                company_id,
                policy_id,
                (title or "")[:80],
                sorted(existing),
                type(exc).__name__,
                str(exc)[:500],
                exc_info=True,
            )
            raise

    def list_company_policies(self, company_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT * FROM company_policies WHERE company_id = :cid "
                    "ORDER BY created_at DESC"
                ),
                {"cid": company_id},
            ).fetchall()
        return self._rows_to_list(rows)

    def list_admin_policy_overview(
        self, company_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Per-company policy status for admin overview."""
        params: Dict[str, Any] = {}
        where = "WHERE c.id = :cid" if company_id else ""
        if company_id:
            params["cid"] = company_id
        sql = f"""
            SELECT
                c.id AS company_id,
                c.name AS company_name,
                (SELECT cp.id FROM company_policies cp WHERE cp.company_id = c.id ORDER BY cp.created_at DESC LIMIT 1) AS policy_id,
                (SELECT cp.title FROM company_policies cp WHERE cp.company_id = c.id ORDER BY cp.created_at DESC LIMIT 1) AS policy_title,
                (SELECT cp.extraction_status FROM company_policies cp WHERE cp.company_id = c.id ORDER BY cp.created_at DESC LIMIT 1) AS extraction_status,
                (SELECT cp.created_at FROM company_policies cp WHERE cp.company_id = c.id ORDER BY cp.created_at DESC LIMIT 1) AS policy_updated_at,
                (SELECT COUNT(*) FROM policy_documents pd WHERE pd.company_id = c.id) AS doc_count,
                (SELECT COUNT(*) FROM policy_versions pv
                 JOIN company_policies cp2 ON cp2.id = pv.policy_id WHERE cp2.company_id = c.id) AS version_count,
                (SELECT pv2.status FROM policy_versions pv2
                 JOIN company_policies cp3 ON cp3.id = pv2.policy_id
                 WHERE cp3.company_id = c.id
                 ORDER BY pv2.version_number DESC, pv2.created_at DESC LIMIT 1) AS latest_version_status,
                (SELECT pv2.version_number FROM policy_versions pv2
                 JOIN company_policies cp3 ON cp3.id = pv2.policy_id
                 WHERE cp3.company_id = c.id
                 ORDER BY pv2.version_number DESC, pv2.created_at DESC LIMIT 1) AS latest_version_number,
                (SELECT pv2.updated_at FROM policy_versions pv2
                 JOIN company_policies cp3 ON cp3.id = pv2.policy_id
                 WHERE cp3.company_id = c.id
                 ORDER BY pv2.version_number DESC, pv2.created_at DESC LIMIT 1) AS latest_version_updated_at,
                (SELECT COUNT(*) FROM resolved_assignment_policies rap
                 JOIN case_assignments ca ON ca.id = rap.assignment_id
                 LEFT JOIN relocation_cases rc ON {_relocation_cases_join_on("ca")}
                 WHERE rc.company_id = c.id) AS resolved_count
            FROM companies c
            {where}
            ORDER BY c.name ASC
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
        result = []
        for row in rows:
            m = row._mapping
            status = "no_policy"
            if m.get("policy_id"):
                vs = m.get("latest_version_status")
                if vs == "published":
                    status = "published"
                elif vs == "reviewed":
                    status = "reviewed"
                elif vs == "review_required":
                    status = "review_required"
                elif vs:
                    status = "draft"
            r = dict(m)
            r["policy_status"] = status
            result.append(r)
        return result

    def get_admin_policies_by_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        """
        Admin: full policy list for one company with version counts, published version, source doc count.
        Returns None if company not found.
        """
        company = self.get_company(company_id)
        if not company:
            return None
        policies_raw = self.list_company_policies(company_id)
        docs = self.list_policy_documents(company_id)
        source_document_count = len(docs)
        policies: List[Dict[str, Any]] = []
        for cp in policies_raw:
            pid = cp.get("id")
            if not pid:
                continue
            versions = self.list_policy_versions(pid)
            published = self.get_published_policy_version(pid)
            latest = versions[0] if versions else None
            policies.append({
                "policy_id": pid,
                "title": cp.get("title"),
                "extraction_status": cp.get("extraction_status"),
                "version_count": len(versions),
                "published_version_id": published.get("id") if published else None,
                "published_at": published.get("updated_at") if published else None,
                "latest_version_status": latest.get("status") if latest else None,
                "latest_version_number": latest.get("version_number") if latest else None,
                "template_source": cp.get("template_source") or "company_uploaded",
                "template_name": cp.get("template_name"),
                "is_default_template": bool(cp.get("is_default_template")),
            })
        return {
            "company_id": company_id,
            "company_name": company.get("name"),
            "source_document_count": source_document_count,
            "policies": policies,
        }

    def get_admin_policy_detail(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """Admin: single policy with company, versions, published version."""
        policy = self.get_company_policy(policy_id)
        if not policy:
            return None
        cid = policy.get("company_id")
        company = self.get_company(cid) if cid else None
        versions = self.list_policy_versions(policy_id)
        published = self.get_published_policy_version(policy_id)
        doc_count = len(self.list_policy_documents(cid)) if cid else 0
        out = dict(policy)
        out["company_name"] = company.get("name") if company else None
        out["source_document_count"] = doc_count
        out["versions"] = versions
        out["published_version"] = published
        out["published_version_id"] = published.get("id") if published else None
        out["published_at"] = published.get("updated_at") if published else None
        return out

    def list_default_policy_templates(self) -> List[Dict[str, Any]]:
        """List platform default policy templates (for admin UI)."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id, template_name, version, status, is_default_template, snapshot_json, created_at, updated_at "
                    "FROM default_policy_templates ORDER BY is_default_template DESC, created_at ASC"
                ),
                {},
            ).fetchall()
        items = self._rows_to_list(rows)
        for d in items:
            self._parse_json_col(d, "snapshot_json")
            if d.get("is_default_template") is not None and not isinstance(d["is_default_template"], bool):
                d["is_default_template"] = bool(d["is_default_template"])
        return items

    def get_default_policy_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get one default policy template by id."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM default_policy_templates WHERE id = :id"),
                {"id": template_id},
            ).fetchone()
        if not row:
            return None
        d = self._row_to_dict(row)
        self._parse_json_col(d, "snapshot_json")
        if d.get("is_default_template") is not None and not isinstance(d["is_default_template"], bool):
            d["is_default_template"] = bool(d["is_default_template"])
        return d

    def apply_default_template_to_company(
        self,
        company_id: str,
        template_id: str,
        overwrite_existing: bool = False,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a company policy from a default template and one policy_version + benefit_rules.
        Does not overwrite existing company policies unless overwrite_existing=True (then we still only add, never delete).
        Returns the new policy_id and version_id.
        """
        template = self.get_default_policy_template(template_id)
        if not template:
            return {"ok": False, "error": "Template not found", "policy_id": None}
        snapshot = template.get("snapshot_json") or {}
        if isinstance(snapshot, str):
            try:
                snapshot = json.loads(snapshot)
            except Exception:
                snapshot = {}
        template_name = template.get("template_name") or "Platform default"
        version_label = template.get("version") or "1.0"
        effective_date = (snapshot.get("effectiveDate") or "")[:10] if isinstance(snapshot.get("effectiveDate"), str) else None
        if not overwrite_existing:
            existing = self.list_company_policies(company_id)
            if existing:
                has_custom = any((p.get("template_source") or "company_uploaded") == "company_uploaded" for p in existing)
                if has_custom:
                    return {"ok": False, "error": "Company already has a custom uploaded policy; use overwrite_existing to add template anyway", "policy_id": None}
        policy_id = str(uuid.uuid4())
        file_url = ""
        file_type = "application/json"
        self.create_company_policy(
            policy_id=policy_id,
            company_id=company_id,
            title=template_name,
            version=version_label,
            effective_date=effective_date,
            file_url=file_url,
            file_type=file_type,
            created_by=created_by,
            template_source="default_platform_template",
            template_name=template_name,
            is_default_template=False,
        )
        self.update_company_policy_status(policy_id, "extracted", datetime.utcnow().isoformat())
        version_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        ag_sql = _policy_ag_sql()
        with self.engine.begin() as conn:
            conn.execute(
                text(f"""
                    INSERT INTO policy_versions
                    (id, policy_id, source_policy_document_id, version_number, status,
                     auto_generated, review_status, confidence, created_by, created_at, updated_at)
                    VALUES (:id, :pid, NULL, 1, 'draft', {ag_sql}, 'accepted', NULL, :cb, :now, :now)
                """),
                {"id": version_id, "pid": policy_id, "ag": 1, "cb": created_by, "now": now},
            )
        benefit_rules = snapshot.get("benefit_rules") or []
        for br in benefit_rules:
            if not isinstance(br, dict):
                continue
            rule_id = str(uuid.uuid4())
            ag_sql = _policy_ag_sql()
            with self.engine.begin() as conn:
                conn.execute(
                    text(f"""
                        INSERT INTO policy_benefit_rules
                        (id, policy_version_id, benefit_key, benefit_category, calc_type, amount_value, amount_unit, currency,
                         description, metadata_json, auto_generated, review_status, created_at, updated_at)
                        VALUES (:id, :vid, :bk, :cat, :ct, :av, :au, :cur, :desc, '{{}}', {ag_sql}, 'accepted', :now, :now)
                    """),
                    {
                        "id": rule_id,
                        "vid": version_id,
                        "ag": 1,
                        "bk": br.get("benefit_key") or "",
                        "cat": br.get("benefit_category") or "",
                        "ct": br.get("calc_type"),
                        "av": br.get("amount_value"),
                        "au": br.get("amount_unit"),
                        "cur": br.get("currency"),
                        "desc": br.get("description"),
                        "now": now,
                    },
                )
        return {"ok": True, "policy_id": policy_id, "version_id": version_id}

    # -------------------------------------------------------------------------
    # Admin read model: normalized indexes and data-integrity
    # -------------------------------------------------------------------------

    def get_admin_company_index(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all companies for admin from the canonical companies table only.
        Orphan company_ids (referenced elsewhere but not in companies) are logged, not shown.
        """
        q = (query or "").strip().lower()
        with self.engine.connect() as conn:
            base_sql = "SELECT * FROM companies WHERE 1=1"
            params: Dict[str, Any] = {}
            if q:
                if _is_sqlite:
                    base_sql += " AND (LOWER(name) LIKE :q OR LOWER(COALESCE(legal_name,'')) LIKE :q)"
                else:
                    base_sql += " AND (LOWER(name) LIKE :q OR LOWER(COALESCE(legal_name,'')) LIKE :q)"
                params["q"] = f"%{q}%"
            base_sql += " ORDER BY name ASC"
            rows = conn.execute(text(base_sql), params).fetchall()
            result = []
            for r in rows:
                d = dict(r._mapping)
                d["missing_from_companies_table"] = 0
                result.append(d)
            seen = {r["id"] for r in result}
            # Collect orphan company_ids for logging only; do not add them to the visible list.
            orphan_ids: set = set()
            for table, col in [("hr_users", "company_id"), ("profiles", "company_id"),
                              ("company_policies", "company_id"), ("relocation_cases", "company_id")]:
                try:
                    orphan_sql = text(
                        f"SELECT DISTINCT {col} AS id FROM {table} WHERE {col} IS NOT NULL AND TRIM({col}) <> ''"
                    )
                    if seen:
                        placeholders = ",".join([f":s{i}" for i in range(len(seen))])
                        orphan_sql = text(
                            f"SELECT DISTINCT {col} AS id FROM {table} WHERE {col} IS NOT NULL AND TRIM({col}) <> '' "
                            f"AND {col} NOT IN ({placeholders})"
                        )
                        orphan_params = {f"s{i}": s for i, s in enumerate(seen)}
                    else:
                        orphan_params = {}
                    orows = conn.execute(orphan_sql, orphan_params).fetchall()
                    for o in orows:
                        cid = (o._mapping.get("id") or "").strip()
                        if cid and cid not in seen:
                            orphan_ids.add(cid)
                except Exception as e:
                    log.warning("admin_company_index: orphan lookup %s.%s failed: %s", table, col, e)
            if orphan_ids:
                log.warning("admin_company_index: orphan company_ids (not in registry): %s", sorted(orphan_ids))

            # Enrich each row with hr_users_count, employee_count, assignments_count, primary_contact_name
            if result:
                ids = [r["id"] for r in result]
                unions = " UNION ALL ".join([f"SELECT :id{i} AS id" for i in range(len(ids))])
                params_agg = {f"id{i}": ids[i] for i in range(len(ids))}
                if _is_sqlite:
                    join_on_cases = "rc.id = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"
                else:
                    # Postgres: relocation_cases.id is uuid, case_assignments.case_id / canonical_case_id are text UUIDs.
                    join_on_cases = "rc.id::text = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"
                agg_sql = f"""
                SELECT v.id,
                    (SELECT COUNT(*) FROM hr_users hu WHERE hu.company_id = v.id) AS hr_users_count,
                    (SELECT COUNT(*) FROM employees e WHERE e.company_id = v.id) AS employee_count,
                    (SELECT COUNT(*) FROM case_assignments a
                     LEFT JOIN relocation_cases rc ON {join_on_cases}
                     LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
                     WHERE (rc.company_id = v.id OR (rc.company_id IS NULL AND hu.company_id = v.id))) AS assignments_count,
                    COALESCE(
                        (SELECT TRIM(c.hr_contact) FROM companies c WHERE c.id = v.id AND c.hr_contact IS NOT NULL AND TRIM(c.hr_contact) <> ''),
                        (SELECT COALESCE(p.full_name, p.email) FROM hr_users hu2
                         JOIN profiles p ON p.id = hu2.profile_id
                         WHERE hu2.company_id = v.id
                         ORDER BY hu2.created_at
                         LIMIT 1)
                    ) AS primary_contact_name
                FROM ({unions}) v
                """
                _agent_debug_log(
                    hypothesis_id="H1",
                    location="database.get_admin_company_index",
                    message="admin_company_index aggregation SQL prepared",
                    data={
                        "is_sqlite": _is_sqlite,
                        "company_ids_count": len(ids),
                        "join_on_cases": join_on_cases,
                    },
                )
                try:
                    agg_rows = conn.execute(text(agg_sql), params_agg).fetchall()
                    by_id = {row._mapping["id"]: dict(row._mapping) for row in agg_rows}
                    for r in result:
                        agg = by_id.get(r["id"]) or {}
                        r["hr_users_count"] = agg.get("hr_users_count") or 0
                        r["employee_count"] = agg.get("employee_count") or 0
                        r["assignments_count"] = agg.get("assignments_count") or 0
                        r["primary_contact_name"] = agg.get("primary_contact_name")
                except Exception as e:
                    log.warning("admin_company_index: enrich counts failed: %s", e)
                    for r in result:
                        r["hr_users_count"] = 0
                        r["employee_count"] = 0
                        r["assignments_count"] = 0
                        r["primary_contact_name"] = None
        return result

    def get_admin_people_index(
        self,
        company_id: Optional[str] = None,
        query: Optional[str] = None,
        role: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        List people (profiles) for admin with optional company, role, and text filters.
        Returns (list with company_name, status), summary with count and orphans_without_company.
        """
        params: Dict[str, Any] = {}
        clauses = []
        if company_id:
            clauses.append("p.company_id = :cid")
            params["cid"] = company_id
        if role and (role or "").strip().lower() not in ("", "all"):
            r = (role or "").strip().upper()
            if r == "HR":
                clauses.append("(p.role = 'HR' OR EXISTS (SELECT 1 FROM hr_users hu WHERE hu.profile_id = p.id))")
            elif r == "EMPLOYEE":
                clauses.append("(p.role IN ('EMPLOYEE', 'EMPLOYEE_USER') OR EXISTS (SELECT 1 FROM employees e WHERE e.profile_id = p.id))")
            elif r == "ADMIN":
                clauses.append("p.role = 'ADMIN'")
            else:
                clauses.append("p.role = :role_filter")
                params["role_filter"] = r
        if query:
            q = (query or "").strip()
            pattern = f"%{q}%"
            if _is_sqlite:
                clauses.append("(LOWER(COALESCE(p.email,'')) LIKE LOWER(:q) OR LOWER(COALESCE(p.full_name,'')) LIKE LOWER(:q))")
            else:
                clauses.append("(p.email ILIKE :q OR p.full_name ILIKE :q)")
            params["q"] = pattern
        # Exclude deactivated (inactive) profiles when status column exists
        with self.engine.connect() as conn:
            has_status = False
            try:
                if _is_sqlite:
                    cur = conn.execute(text("PRAGMA table_info(profiles)"))
                    cols = [r[1] for r in cur.fetchall()]
                    has_status = "status" in cols
                else:
                    r = conn.execute(text(
                        "SELECT 1 FROM information_schema.columns WHERE table_name = 'profiles' AND column_name = 'status' LIMIT 1"
                    )).fetchone()
                    has_status = r is not None
            except Exception:
                pass
            if has_status:
                clauses.append("(COALESCE(TRIM(LOWER(p.status)), 'active') <> 'inactive')")
        where = " AND " + " AND ".join(clauses) if clauses else ""
        sql = f"""
            SELECT p.id, p.role, p.email, p.full_name, p.company_id,
                   'active' AS status,
                   p.created_at,
                   c.name AS company_name,
                   (SELECT COUNT(*) FROM hr_users hu WHERE hu.profile_id = p.id) AS hr_link_count,
                   (SELECT COUNT(*) FROM employees e WHERE e.profile_id = p.id) AS employee_link_count
            FROM profiles p
            LEFT JOIN companies c ON c.id = p.company_id
            WHERE 1=1 {where}
            ORDER BY p.full_name ASC NULLS LAST, p.created_at DESC
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
        people = [dict(r._mapping) for r in rows]
        for row in people:
            row["name"] = row.get("full_name") or row.get("email") or row.get("id")
        # Orphans: profiles with role in ('HR','EMPLOYEE','EMPLOYEE_USER') and no company_id
        try:
            orphan_sql = text("""
                SELECT COUNT(*) AS n FROM profiles
                WHERE (role IN ('HR','EMPLOYEE','EMPLOYEE_USER') OR role IS NULL)
                AND (company_id IS NULL OR TRIM(company_id) = '')
            """)
            with self.engine.connect() as conn:
                orphan_row = conn.execute(orphan_sql, {}).fetchone()
            orphans = int(orphan_row._mapping["n"]) if orphan_row else 0
        except Exception as e:
            log.warning("admin_people_index: orphan count failed: %s", e)
            orphans = 0
        summary = {"count": len(people), "orphans_without_company": orphans}
        return people, summary

    def get_admin_assignments_index(
        self,
        company_id: Optional[str] = None,
        employee_user_id: Optional[str] = None,
        employee_search: Optional[str] = None,
        status: Optional[str] = None,
        destination_country: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        List assignments for admin (same as list_admin_assignments) plus summary with
        count, orphans_without_company, orphans_without_person.
        """
        items = self.list_admin_assignments(
            company_id=company_id,
            employee_user_id=employee_user_id,
            employee_search=employee_search,
            status=status,
            destination_country=destination_country,
        )
        with self.engine.connect() as conn:
            total = conn.execute(text("SELECT COUNT(*) AS n FROM case_assignments"), {}).fetchone()
            total_count = int(total._mapping["n"]) if total else 0
            no_company_sql = text(f"""
                SELECT COUNT(*) AS n FROM case_assignments a
                LEFT JOIN relocation_cases rc ON {_relocation_cases_join_on("a", "canonical_coalesce")}
                LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
                WHERE COALESCE(rc.company_id, hu.company_id) IS NULL
            """)
            no_emp_sql = text("""
                SELECT COUNT(*) AS n FROM case_assignments
                WHERE employee_user_id IS NULL OR TRIM(COALESCE(employee_user_id,'')) = ''
            """)
            try:
                no_co = conn.execute(no_company_sql, {}).fetchone()
                no_emp = conn.execute(no_emp_sql, {}).fetchone()
                orphans_no_company = int(no_co._mapping["n"]) if no_co else 0
                orphans_no_person = int(no_emp._mapping["n"]) if no_emp else 0
            except Exception as e:
                log.warning("admin_assignments_index: orphan counts failed: %s", e)
                orphans_no_company = orphans_no_person = 0
        summary = {
            "count": total_count,
            "orphans_without_company": orphans_no_company,
            "orphans_without_person": orphans_no_person,
        }
        return items, summary

    def get_admin_policies_index(
        self, company_id: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        List company_policies for admin with company name; optional company_id filter.
        Returns (list of policies), summary with count and orphans_without_company.
        """
        params: Dict[str, Any] = {}
        where = "WHERE 1=1"
        if company_id:
            where += " AND cp.company_id = :cid"
            params["cid"] = company_id
        sql = f"""
            SELECT cp.id, cp.company_id, cp.title, cp.version, cp.effective_date, cp.file_url, cp.file_type,
                   cp.extraction_status, cp.extracted_at, cp.created_by, cp.created_at,
                   c.name AS company_name
            FROM company_policies cp
            LEFT JOIN companies c ON c.id = cp.company_id
            {where}
            ORDER BY cp.company_id, cp.created_at DESC
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
        policies = [dict(r._mapping) for r in rows]
        try:
            orphan_sql = text("""
                SELECT COUNT(*) AS n FROM company_policies cp
                WHERE NOT EXISTS (SELECT 1 FROM companies c WHERE c.id = cp.company_id)
            """)
            with self.engine.connect() as conn:
                o = conn.execute(orphan_sql, {}).fetchone()
            orphans = int(o._mapping["n"]) if o else 0
        except Exception as e:
            log.warning("admin_policies_index: orphan count failed: %s", e)
            orphans = 0
        summary = {"count": len(policies), "orphans_without_company": orphans}
        return policies, summary

    def get_data_integrity_overview(self) -> Dict[str, Any]:
        """
        Admin-safe summary of entity counts and orphan flags for data-integrity dashboard.
        """
        out: Dict[str, Any] = {
            "companies": {"count": 0},
            "people": {"count": 0, "orphans_without_company": 0},
            "assignments": {"count": 0, "orphans_without_company": 0, "orphans_without_person": 0},
            "policies": {"count": 0, "orphans_without_company": 0},
        }
        try:
            with self.engine.connect() as conn:
                c = conn.execute(text("SELECT COUNT(*) AS n FROM companies"), {}).fetchone()
                out["companies"]["count"] = int(c._mapping["n"]) if c else 0
                p = conn.execute(text("SELECT COUNT(*) AS n FROM profiles"), {}).fetchone()
                out["people"]["count"] = int(p._mapping["n"]) if p else 0
                _, people_sum = self.get_admin_people_index()
                out["people"]["orphans_without_company"] = people_sum.get("orphans_without_company", 0)
                a = conn.execute(text("SELECT COUNT(*) AS n FROM case_assignments"), {}).fetchone()
                out["assignments"]["count"] = int(a._mapping["n"]) if a else 0
                no_co = conn.execute(text(f"""
                    SELECT COUNT(*) AS n FROM case_assignments a
                    LEFT JOIN relocation_cases rc ON {_relocation_cases_join_on("a", "canonical_coalesce")}
                    LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
                    WHERE COALESCE(rc.company_id, hu.company_id) IS NULL
                """), {}).fetchone()
                out["assignments"]["orphans_without_company"] = int(no_co._mapping["n"]) if no_co else 0
                no_emp = conn.execute(text("""
                    SELECT COUNT(*) AS n FROM case_assignments
                    WHERE employee_user_id IS NULL OR TRIM(COALESCE(employee_user_id,'')) = ''
                """), {}).fetchone()
                out["assignments"]["orphans_without_person"] = int(no_emp._mapping["n"]) if no_emp else 0
                pol = conn.execute(text("SELECT COUNT(*) AS n FROM company_policies"), {}).fetchone()
                out["policies"]["count"] = int(pol._mapping["n"]) if pol else 0
                pol_orphan = conn.execute(text("""
                    SELECT COUNT(*) AS n FROM company_policies cp
                    WHERE NOT EXISTS (SELECT 1 FROM companies c WHERE c.id = cp.company_id)
                """), {}).fetchone()
                out["policies"]["orphans_without_company"] = int(pol_orphan._mapping["n"]) if pol_orphan else 0
        except Exception as e:
            log.warning("get_data_integrity_overview failed: %s", e)
        return out

    def get_company_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM company_policies WHERE id = :id"),
                {"id": policy_id},
            ).fetchone()
        return self._row_to_dict(row)

    def get_latest_company_policy(self, company_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT * FROM company_policies WHERE company_id = :cid "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"cid": company_id},
            ).fetchone()
        return self._row_to_dict(row)

    def get_company_policy_with_published_version(
        self, company_id: str
    ) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """Return (policy, version) for the first company policy that has a published version."""
        policies = self.list_company_policies(company_id)
        for policy in policies:
            version = self.get_published_policy_version(policy["id"])
            if version:
                return (policy, version)
        return None

    def list_company_ids_with_published_policy(self) -> List[Dict[str, Any]]:
        """Return list of {company_id, company_name} for companies that have at least one published policy (for debug logging)."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT DISTINCT c.id AS company_id, c.name AS company_name
                    FROM companies c
                    JOIN company_policies cp ON cp.company_id = c.id
                    JOIN policy_versions pv ON pv.policy_id = cp.id AND pv.status = 'published'
                """),
                {},
            ).fetchall()
        return [{"company_id": r._mapping["company_id"], "company_name": r._mapping.get("company_name")} for r in rows]

    def update_company_policy_status(
        self,
        policy_id: str,
        status: str,
        extracted_at: Optional[str] = None,
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE company_policies SET extraction_status = :status, extracted_at = :ea "
                    "WHERE id = :id"
                ),
                {"status": status, "ea": extracted_at, "id": policy_id},
            )

    def update_company_policy_meta(
        self,
        policy_id: str,
        title: Optional[str] = None,
        version: Optional[str] = None,
        effective_date: Optional[str] = None,
    ) -> None:
        fields = []
        params: Dict[str, Any] = {"id": policy_id}
        if title is not None:
            fields.append("title = :title")
            params["title"] = title
        if version is not None:
            fields.append("version = :version")
            params["version"] = version
        if effective_date is not None:
            fields.append("effective_date = :effective_date")
            params["effective_date"] = effective_date
        if not fields:
            return
        with self.engine.begin() as conn:
            conn.execute(text(f"UPDATE company_policies SET {', '.join(fields)} WHERE id = :id"), params)

    def list_company_preferred_suppliers(
        self, company_id: str, service_category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            sql = "SELECT * FROM company_preferred_suppliers WHERE company_id = :cid AND status = 'active'"
            params: Dict[str, Any] = {"cid": company_id}
            if service_category:
                sql += " AND (service_category = :svc OR service_category IS NULL)"
                params["svc"] = service_category
            sql += " ORDER BY priority_rank ASC, created_at ASC"
            rows = conn.execute(text(sql), params).fetchall()
        return self._rows_to_list(rows)

    def add_company_preferred_supplier(
        self,
        company_id: str,
        supplier_id: str,
        service_category: Optional[str] = None,
        priority_rank: int = 0,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        rid = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO company_preferred_suppliers
                    (id, company_id, supplier_id, service_category, priority_rank, status, notes, created_at, updated_at)
                    VALUES (:id, :cid, :sid, :svc, :rank, 'active', :notes, :now, :now)
                """),
                {
                    "id": rid,
                    "cid": company_id,
                    "sid": supplier_id,
                    "svc": service_category,
                    "rank": priority_rank,
                    "notes": notes or "",
                    "now": now,
                },
            )
        return {"id": rid, "company_id": company_id, "supplier_id": supplier_id}

    def remove_company_preferred_supplier(
        self, company_id: str, supplier_id: str, service_category: Optional[str] = None
    ) -> int:
        with self.engine.begin() as conn:
            if service_category:
                r = conn.execute(
                    text("DELETE FROM company_preferred_suppliers WHERE company_id = :cid AND supplier_id = :sid AND service_category = :svc"),
                    {"cid": company_id, "sid": supplier_id, "svc": service_category},
                )
            else:
                r = conn.execute(
                    text("DELETE FROM company_preferred_suppliers WHERE company_id = :cid AND supplier_id = :sid AND service_category IS NULL"),
                    {"cid": company_id, "sid": supplier_id},
                )
                return r.rowcount

    def create_policy_document(
        self,
        doc_id: str,
        company_id: str,
        uploaded_by_user_id: str,
        filename: str,
        mime_type: str,
        storage_path: str,
        checksum: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO policy_documents
                    (id, company_id, uploaded_by_user_id, filename, mime_type, storage_path,
                     checksum, uploaded_at, processing_status, created_at, updated_at)
                    VALUES (:id, :cid, :uid, :fn, :mt, :sp, :cs, :now, 'uploaded', :now, :now)
                """),
                {
                    "id": doc_id,
                    "cid": company_id,
                    "uid": uploaded_by_user_id,
                    "fn": filename,
                    "mt": mime_type,
                    "sp": storage_path,
                    "cs": checksum,
                    "now": now,
                },
            )
        return self.get_policy_document(doc_id, request_id=request_id) or {}

    def get_policy_document(
        self, doc_id: str, request_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT * FROM policy_documents WHERE id = :id",
                {"id": doc_id},
                op_name="get_policy_document",
                request_id=request_id,
            ).fetchone()
        d = self._row_to_dict(row)
        if d:
            try:
                val = d.get("extracted_metadata")
                raw = json.loads(val) if isinstance(val, str) else (val if isinstance(val, dict) else None)
                from .services.policy_document_intake import normalize_extracted_metadata
                d["extracted_metadata"] = normalize_extracted_metadata(raw)
            except Exception:
                d["extracted_metadata"] = {}
        return d

    def list_policy_documents(
        self, company_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT * FROM policy_documents WHERE company_id = :cid ORDER BY uploaded_at DESC",
                {"cid": company_id},
                op_name="list_policy_documents",
                request_id=request_id,
            ).fetchall()
        items = self._rows_to_list(rows)
        from .services.policy_document_intake import normalize_extracted_metadata
        for d in items:
            try:
                val = d.get("extracted_metadata")
                raw = json.loads(val) if isinstance(val, str) else (val if isinstance(val, dict) else None)
                d["extracted_metadata"] = normalize_extracted_metadata(raw)
            except Exception:
                d["extracted_metadata"] = {}
        return items

    def update_policy_document(
        self,
        doc_id: str,
        processing_status: Optional[str] = None,
        detected_document_type: Optional[str] = None,
        detected_policy_scope: Optional[str] = None,
        version_label: Optional[str] = None,
        effective_date: Optional[str] = None,
        raw_text: Optional[str] = None,
        extraction_error: Optional[str] = None,
        extracted_metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        fields = ["updated_at = :now"]
        params: Dict[str, Any] = {"id": doc_id, "now": now}
        if processing_status is not None:
            fields.append("processing_status = :ps")
            params["ps"] = processing_status
        if detected_document_type is not None:
            fields.append("detected_document_type = :ddt")
            params["ddt"] = detected_document_type
        if detected_policy_scope is not None:
            fields.append("detected_policy_scope = :dps")
            params["dps"] = detected_policy_scope
        if version_label is not None:
            fields.append("version_label = :vl")
            params["vl"] = version_label
        if effective_date is not None:
            fields.append("effective_date = :ed")
            params["ed"] = effective_date
        if raw_text is not None:
            fields.append("raw_text = :rt")
            params["rt"] = raw_text
        if extraction_error is not None:
            fields.append("extraction_error = :ee")
            params["ee"] = extraction_error
        if extracted_metadata is not None:
            fields.append("extracted_metadata = :em")
            params["em"] = json.dumps(extracted_metadata)
        with self.engine.begin() as conn:
            conn.execute(
                text(f"UPDATE policy_documents SET {', '.join(fields)} WHERE id = :id"),
                params,
            )

    def policy_version_references_document(self, doc_id: str) -> bool:
        """True if any policy_version has source_policy_document_id = doc_id."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT 1 FROM policy_versions WHERE source_policy_document_id = :id LIMIT 1"),
                {"id": doc_id},
            ).fetchone()
        return row is not None

    def delete_policy_document(self, doc_id: str, request_id: Optional[str] = None) -> bool:
        """Delete policy_document and its clauses. Returns True if a row was deleted."""
        self.delete_policy_document_clauses(doc_id, request_id=request_id)
        with self.engine.begin() as conn:
            r = conn.execute(text("DELETE FROM policy_documents WHERE id = :id"), {"id": doc_id})
            return r.rowcount > 0

    def delete_policy_document_clauses(self, doc_id: str, request_id: Optional[str] = None) -> int:
        """Remove all clauses for a document (before re-segment)."""
        with self.engine.begin() as conn:
            r = conn.execute(
                text("DELETE FROM policy_document_clauses WHERE policy_document_id = :id"),
                {"id": doc_id},
            )
            return r.rowcount

    def upsert_policy_document_clauses(
        self,
        doc_id: str,
        clauses: List[Dict[str, Any]],
        request_id: Optional[str] = None,
    ) -> int:
        """Replace clauses for a document. Deletes existing and inserts new."""
        self.delete_policy_document_clauses(doc_id, request_id=request_id)
        if not clauses:
            return 0
        now = datetime.utcnow().isoformat()
        valid_types = {
            "scope", "eligibility", "benefit", "exclusion", "approval_rule",
            "evidence_rule", "tax_rule", "definition", "lifecycle_rule", "unknown",
        }
        with self.engine.begin() as conn:
            for c in clauses:
                cid = str(uuid.uuid4())
                ctype = str(c.get("clause_type") or "unknown")
                if ctype not in valid_types:
                    ctype = "unknown"
                conn.execute(
                    text("""
                        INSERT INTO policy_document_clauses
                        (id, policy_document_id, section_label, section_path, clause_type,
                         title, raw_text, normalized_hint_json, source_page_start, source_page_end,
                         source_anchor, confidence, created_at, updated_at)
                        VALUES (:id, :doc_id, :sl, :sp, :ct, :title, :raw, :hint,
                                :ps, :pe, :anchor, :conf, :now, :now)
                    """),
                    {
                        "id": cid,
                        "doc_id": doc_id,
                        "sl": c.get("section_label"),
                        "sp": c.get("section_path"),
                        "ct": ctype,
                        "title": c.get("title"),
                        "raw": c.get("raw_text") or "",
                        "hint": json.dumps(c.get("normalized_hint_json")) if c.get("normalized_hint_json") else None,
                        "ps": c.get("source_page_start"),
                        "pe": c.get("source_page_end"),
                        "anchor": c.get("source_anchor"),
                        "conf": float(c.get("confidence", 0.5)),
                        "now": now,
                    },
                )
        return len(clauses)

    def list_policy_document_clauses(
        self,
        doc_id: str,
        clause_type: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM policy_document_clauses WHERE policy_document_id = :id"
        params: Dict[str, Any] = {"id": doc_id}
        if clause_type:
            sql += " AND clause_type = :ct"
            params["ct"] = clause_type
        sql += " ORDER BY source_page_start ASC NULLS LAST, created_at ASC"
        with self.engine.connect() as conn:
            try:
                rows = conn.execute(text(sql), params).fetchall()
            except Exception:
                sql = sql.replace(" NULLS LAST", "")
                rows = conn.execute(text(sql), params).fetchall()
        items = self._rows_to_list(rows)
        for d in items:
            if d.get("normalized_hint_json") and isinstance(d["normalized_hint_json"], str):
                try:
                    d["normalized_hint_json"] = json.loads(d["normalized_hint_json"])
                except Exception:
                    d["normalized_hint_json"] = None
        return items

    def get_policy_document_clause(
        self, clause_id: str, request_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM policy_document_clauses WHERE id = :id"),
                {"id": clause_id},
            ).fetchone()
        d = self._row_to_dict(row)
        if d and d.get("normalized_hint_json") and isinstance(d["normalized_hint_json"], str):
            try:
                d["normalized_hint_json"] = json.loads(d["normalized_hint_json"])
            except Exception:
                d["normalized_hint_json"] = None
        return d

    def update_policy_document_clause(
        self,
        clause_id: str,
        clause_type: Optional[str] = None,
        title: Optional[str] = None,
        hr_override_notes: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        valid_types = {
            "scope", "eligibility", "benefit", "exclusion", "approval_rule",
            "evidence_rule", "tax_rule", "definition", "lifecycle_rule", "unknown",
        }
        fields = ["updated_at = :now"]
        params: Dict[str, Any] = {"id": clause_id, "now": datetime.utcnow().isoformat()}
        if clause_type is not None:
            ctype = clause_type if clause_type in valid_types else "unknown"
            fields.append("clause_type = :ct")
            params["ct"] = ctype
        if title is not None:
            fields.append("title = :title")
            params["title"] = title
        if hr_override_notes is not None:
            fields.append("hr_override_notes = :notes")
            params["notes"] = hr_override_notes
        if len(fields) <= 1:
            return
        with self.engine.begin() as conn:
            conn.execute(
                text(f"UPDATE policy_document_clauses SET {', '.join(fields)} WHERE id = :id"),
                params,
            )

    # ==================================================================
    # Policy normalization (canonical policy objects)
    # ==================================================================

    @staticmethod
    def _coerce_policy_boolean_fields(payload: Dict[str, Any], boolean_keys: List[str]) -> Dict[str, Any]:
        """Ensure boolean DB columns receive Python bool, not int. Safe for Postgres."""
        out = dict(payload)
        for k in boolean_keys:
            if k in out and out[k] is not None:
                v = out[k]
                if isinstance(v, int):
                    out[k] = bool(v)
                elif not isinstance(v, bool):
                    out[k] = bool(v)
        return out

    def create_policy_version(
        self,
        version_id: str,
        policy_id: str,
        source_policy_document_id: Optional[str] = None,
        version_number: int = 1,
        status: str = "auto_generated",
        auto_generated: bool = True,
        review_status: str = "pending",
        confidence: Optional[float] = None,
        created_by: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        # Coerce to str for Postgres uuid columns (driver may return UUID from list_company_policies)
        params = {
            "id": str(version_id),
            "pid": str(policy_id),
            "doc_id": str(source_policy_document_id) if source_policy_document_id is not None else None,
            "vn": version_number,
            "status": status,
            "ag": _policy_bool_for_db(auto_generated),
            "rs": review_status,
            "conf": confidence,
            "cb": created_by,
            "now": now,
        }
        params = normalize_policy_boolean_fields(params)
        if request_id:
            log.info(
                "request_id=%s policy_versions insert payload keys=%s status=%s auto_generated=%s review_status=%s ag_type=%s doc_id=%s",
                request_id, list(params.keys()), params.get("status"), params.get("ag"),
                params.get("rs"), type(params.get("ag")).__name__, params.get("doc_id"),
            )
        ag_sql = _policy_ag_sql()
        with self.engine.begin() as conn:
            conn.execute(
                text(f"""
                    INSERT INTO policy_versions
                    (id, policy_id, source_policy_document_id, version_number, status,
                     auto_generated, review_status, confidence, created_by, created_at, updated_at)
                    VALUES (:id, :pid, :doc_id, :vn, :status, {ag_sql}, :rs, :conf, :cb, :now, :now)
                """),
                params,
            )

    def get_latest_policy_version(self, policy_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM policy_versions WHERE policy_id = :pid ORDER BY version_number DESC, created_at DESC LIMIT 1"),
                {"pid": policy_id},
            ).fetchone()
        return self._row_to_dict(row)

    def get_published_policy_version(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest published version. Employees see only published policies."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM policy_versions WHERE policy_id = :pid AND status = 'published' ORDER BY version_number DESC, created_at DESC LIMIT 1"),
                {"pid": policy_id},
            ).fetchone()
        return self._row_to_dict(row)

    def update_policy_version_status(self, version_id: str, status: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE policy_versions SET status = :s, updated_at = :now WHERE id = :id"),
                {"id": version_id, "s": status, "now": datetime.utcnow().isoformat()},
            )

    def archive_other_published_versions(self, policy_id: str, keep_version_id: str) -> int:
        """Set status=archived for all published versions except keep_version_id. Returns count updated."""
        with self.engine.begin() as conn:
            r = conn.execute(
                text("""
                    UPDATE policy_versions SET status = 'archived', updated_at = :now
                    WHERE policy_id = :pid AND status = 'published' AND id != :keep
                """),
                {"pid": policy_id, "keep": keep_version_id, "now": datetime.utcnow().isoformat()},
            )
            return r.rowcount

    def archive_all_published_versions(self, policy_id: str) -> int:
        """Set status=archived for all published versions of this policy (unpublish). Returns count updated."""
        with self.engine.begin() as conn:
            r = conn.execute(
                text("""
                    UPDATE policy_versions SET status = 'archived', updated_at = :now
                    WHERE policy_id = :pid AND status = 'published'
                """),
                {"pid": policy_id, "now": datetime.utcnow().isoformat()},
            )
            return r.rowcount

    def get_policy_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM policy_versions WHERE id = :id"),
                {"id": version_id},
            ).fetchone()
        return self._row_to_dict(row)

    def list_policy_versions(self, policy_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM policy_versions WHERE policy_id = :pid ORDER BY version_number DESC"),
                {"pid": policy_id},
            ).fetchall()
        return self._rows_to_list(rows)

    def _parse_json_col(self, d: Dict[str, Any], key: str) -> None:
        if d.get(key) and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except Exception:
                d[key] = None

    def list_policy_benefit_rules(self, policy_version_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM policy_benefit_rules WHERE policy_version_id = :vid ORDER BY benefit_key"),
                {"vid": policy_version_id},
            ).fetchall()
        items = self._rows_to_list(rows)
        for d in items:
            self._parse_json_col(d, "metadata_json")
        return items

    def list_policy_exclusions(self, policy_version_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM policy_exclusions WHERE policy_version_id = :vid"),
                {"vid": policy_version_id},
            ).fetchall()
        return self._rows_to_list(rows)

    def list_policy_evidence_requirements(self, policy_version_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM policy_evidence_requirements WHERE policy_version_id = :vid"),
                {"vid": policy_version_id},
            ).fetchall()
        items = self._rows_to_list(rows)
        for d in items:
            self._parse_json_col(d, "evidence_items_json")
        return items

    def list_policy_rule_conditions(self, policy_version_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM policy_rule_conditions WHERE policy_version_id = :vid"),
                {"vid": policy_version_id},
            ).fetchall()
        items = self._rows_to_list(rows)
        for d in items:
            self._parse_json_col(d, "condition_value_json")
        return items

    def list_policy_assignment_applicability(self, policy_version_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM policy_assignment_type_applicability WHERE policy_version_id = :vid"),
                {"vid": policy_version_id},
            ).fetchall()
        return self._rows_to_list(rows)

    def list_policy_family_applicability(self, policy_version_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM policy_family_status_applicability WHERE policy_version_id = :vid"),
                {"vid": policy_version_id},
            ).fetchall()
        return self._rows_to_list(rows)

    def list_policy_tier_overrides(self, policy_version_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM policy_tier_overrides WHERE policy_version_id = :vid"),
                {"vid": policy_version_id},
            ).fetchall()
        items = self._rows_to_list(rows)
        for d in items:
            self._parse_json_col(d, "override_limits_json")
        return items

    def list_policy_source_links(self, policy_version_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM policy_source_links WHERE policy_version_id = :vid"),
                {"vid": policy_version_id},
            ).fetchall()
        return self._rows_to_list(rows)

    def insert_policy_benefit_rule(self, rule: Dict[str, Any]) -> str:
        rid = rule.get("id") or str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        ag_sql = _policy_ag_sql()
        with self.engine.begin() as conn:
            conn.execute(
                text(f"""
                    INSERT INTO policy_benefit_rules
                    (id, policy_version_id, benefit_key, benefit_category, calc_type, amount_value,
                     amount_unit, currency, frequency, description, metadata_json, auto_generated,
                     review_status, confidence, raw_text, created_at, updated_at)
                    VALUES (:id, :vid, :bk, :bc, :ct, :av, :au, :cur, :freq, :desc, :meta, {ag_sql}, :rs, :conf, :raw, :now, :now)
                """),
                {
                    "id": rid,
                    "vid": rule["policy_version_id"],
                    "bk": rule["benefit_key"],
                    "bc": rule["benefit_category"],
                    "ct": rule.get("calc_type"),
                    "av": rule.get("amount_value"),
                    "au": rule.get("amount_unit"),
                    "cur": rule.get("currency"),
                    "freq": rule.get("frequency"),
                    "desc": rule.get("description"),
                    "meta": json.dumps(rule.get("metadata_json")) if rule.get("metadata_json") else None,
                    "ag": _policy_bool_for_db(rule.get("auto_generated", True)),
                    "rs": rule.get("review_status", "pending"),
                    "conf": rule.get("confidence"),
                    "raw": rule.get("raw_text"),
                    "now": now,
                },
            )
        return rid

    def insert_policy_exclusion(self, excl: Dict[str, Any]) -> str:
        eid = excl.get("id") or str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        ag_sql = _policy_ag_sql()
        with self.engine.begin() as conn:
            conn.execute(
                text(f"""
                    INSERT INTO policy_exclusions
                    (id, policy_version_id, benefit_key, domain, description, auto_generated,
                     review_status, confidence, raw_text, created_at, updated_at)
                    VALUES (:id, :vid, :bk, :dom, :desc, {ag_sql}, :rs, :conf, :raw, :now, :now)
                """),
                {
                    "id": eid,
                    "vid": excl["policy_version_id"],
                    "bk": excl.get("benefit_key"),
                    "dom": excl["domain"],
                    "desc": excl.get("description"),
                    "ag": _policy_bool_for_db(excl.get("auto_generated", True)),
                    "rs": excl.get("review_status", "pending"),
                    "conf": excl.get("confidence"),
                    "raw": excl.get("raw_text"),
                    "now": now,
                },
            )
        return eid

    def insert_policy_evidence_requirement(self, ev: Dict[str, Any]) -> str:
        eid = ev.get("id") or str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        ag_sql = _policy_ag_sql()
        with self.engine.begin() as conn:
            conn.execute(
                text(f"""
                    INSERT INTO policy_evidence_requirements
                    (id, policy_version_id, benefit_rule_id, evidence_items_json, description,
                     auto_generated, review_status, confidence, raw_text, created_at, updated_at)
                    VALUES (:id, :vid, :brid, :items, :desc, {ag_sql}, :rs, :conf, :raw, :now, :now)
                """),
                {
                    "id": eid,
                    "vid": ev["policy_version_id"],
                    "brid": ev.get("benefit_rule_id"),
                    "items": json.dumps(ev.get("evidence_items_json") or []),
                    "desc": ev.get("description"),
                    "ag": _policy_bool_for_db(ev.get("auto_generated", True)),
                    "rs": ev.get("review_status", "pending"),
                    "conf": ev.get("confidence"),
                    "raw": ev.get("raw_text"),
                    "now": now,
                },
            )
        return eid

    def insert_policy_rule_condition(self, cond: Dict[str, Any]) -> str:
        cid = cond.get("id") or str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        ag_sql = _policy_ag_sql()
        with self.engine.begin() as conn:
            conn.execute(
                text(f"""
                    INSERT INTO policy_rule_conditions
                    (id, policy_version_id, object_type, object_id, condition_type, condition_value_json,
                     auto_generated, review_status, confidence, created_at, updated_at)
                    VALUES (:id, :vid, :ot, :oid, :ct, :val, {ag_sql}, :rs, :conf, :now, :now)
                """),
                {
                    "id": cid,
                    "vid": cond["policy_version_id"],
                    "ot": cond["object_type"],
                    "oid": cond["object_id"],
                    "ct": cond["condition_type"],
                    "val": json.dumps(cond.get("condition_value_json") or {}),
                    "ag": _policy_bool_for_db(cond.get("auto_generated", True)),
                    "rs": cond.get("review_status", "pending"),
                    "conf": cond.get("confidence"),
                    "now": now,
                },
            )
        return cid

    def insert_policy_assignment_applicability(self, app: Dict[str, Any]) -> str:
        aid = app.get("id") or str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO policy_assignment_type_applicability
                    (id, policy_version_id, benefit_rule_id, assignment_type)
                    VALUES (:id, :vid, :brid, :at)
                """),
                {
                    "id": aid,
                    "vid": app["policy_version_id"],
                    "brid": app["benefit_rule_id"],
                    "at": app["assignment_type"],
                },
            )
        return aid

    def insert_policy_family_applicability(self, app: Dict[str, Any]) -> str:
        fid = app.get("id") or str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO policy_family_status_applicability
                    (id, policy_version_id, benefit_rule_id, family_status)
                    VALUES (:id, :vid, :brid, :fs)
                """),
                {
                    "id": fid,
                    "vid": app["policy_version_id"],
                    "brid": app["benefit_rule_id"],
                    "fs": app["family_status"],
                },
            )
        return fid

    def insert_policy_source_link(self, link: Dict[str, Any]) -> str:
        lid = link.get("id") or str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO policy_source_links
                    (id, policy_version_id, object_type, object_id, clause_id, source_page_start, source_page_end, source_anchor)
                    VALUES (:id, :vid, :ot, :oid, :cid, :ps, :pe, :anchor)
                """),
                {
                    "id": lid,
                    "vid": link["policy_version_id"],
                    "ot": link["object_type"],
                    "oid": link["object_id"],
                    "cid": link["clause_id"],
                    "ps": link.get("source_page_start"),
                    "pe": link.get("source_page_end"),
                    "anchor": link.get("source_anchor"),
                },
            )
        return lid

    def update_policy_benefit_rule(
        self,
        rule_id: str,
        amount_value: Optional[float] = None,
        amount_unit: Optional[str] = None,
        currency: Optional[str] = None,
        frequency: Optional[str] = None,
        description: Optional[str] = None,
        review_status: Optional[str] = None,
        benefit_key: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> None:
        fields = ["updated_at = :now"]
        params: Dict[str, Any] = {"id": rule_id, "now": datetime.utcnow().isoformat()}
        if amount_value is not None:
            fields.append("amount_value = :av")
            params["av"] = amount_value
        if amount_unit is not None:
            fields.append("amount_unit = :au")
            params["au"] = amount_unit
        if currency is not None:
            fields.append("currency = :cur")
            params["cur"] = currency
        if frequency is not None:
            fields.append("frequency = :freq")
            params["freq"] = frequency
        if description is not None:
            fields.append("description = :desc")
            params["desc"] = description
        if review_status is not None:
            fields.append("review_status = :rs")
            params["rs"] = review_status
        if benefit_key is not None:
            fields.append("benefit_key = :bk")
            params["bk"] = benefit_key
        if metadata_json is not None:
            fields.append("metadata_json = :meta")
            params["meta"] = json.dumps(metadata_json)
        if len(fields) <= 1:
            return
        with self.engine.begin() as conn:
            conn.execute(
                text(f"UPDATE policy_benefit_rules SET {', '.join(fields)} WHERE id = :id"),
                params,
            )

    def update_policy_exclusion(
        self,
        excl_id: str,
        description: Optional[str] = None,
        review_status: Optional[str] = None,
    ) -> None:
        fields = ["updated_at = :now"]
        params: Dict[str, Any] = {"id": excl_id, "now": datetime.utcnow().isoformat()}
        if description is not None:
            fields.append("description = :desc")
            params["desc"] = description
        if review_status is not None:
            fields.append("review_status = :rs")
            params["rs"] = review_status
        if len(fields) <= 1:
            return
        with self.engine.begin() as conn:
            conn.execute(
                text(f"UPDATE policy_exclusions SET {', '.join(fields)} WHERE id = :id"),
                params,
            )

    def update_policy_rule_condition(
        self,
        cond_id: str,
        condition_value_json: Optional[Dict[str, Any]] = None,
        review_status: Optional[str] = None,
    ) -> None:
        fields = ["updated_at = :now"]
        params: Dict[str, Any] = {"id": cond_id, "now": datetime.utcnow().isoformat()}
        if condition_value_json is not None:
            fields.append("condition_value_json = :val")
            params["val"] = json.dumps(condition_value_json)
        if review_status is not None:
            fields.append("review_status = :rs")
            params["rs"] = review_status
        if len(fields) <= 1:
            return
        with self.engine.begin() as conn:
            conn.execute(
                text(f"UPDATE policy_rule_conditions SET {', '.join(fields)} WHERE id = :id"),
                params,
            )

    def get_policy_benefit_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM policy_benefit_rules WHERE id = :id"),
                {"id": rule_id},
            ).fetchone()
        d = self._row_to_dict(row)
        if d:
            self._parse_json_col(d, "metadata_json")
        return d

    def list_policy_benefits(self, policy_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM policy_benefits WHERE policy_id = :pid ORDER BY service_category, benefit_label"),
                {"pid": policy_id},
            ).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            try:
                item["eligibility"] = json.loads(item.get("eligibility") or "null")
            except Exception:
                item["eligibility"] = None
            try:
                item["limits"] = json.loads(item.get("limits") or "null")
            except Exception:
                item["limits"] = None
        return items

    def replace_policy_benefits(
        self,
        policy_id: str,
        benefits: List[Dict[str, Any]],
        updated_by: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM policy_benefits WHERE policy_id = :pid"), {"pid": policy_id})
            for item in benefits:
                conn.execute(
                    text(
                        "INSERT INTO policy_benefits "
                        "(id, policy_id, service_category, benefit_key, benefit_label, eligibility, limits, notes, "
                        "source_quote, source_section, confidence, updated_by, updated_at) "
                        "VALUES (:id, :pid, :cat, :key, :label, :elig, :limits, :notes, :quote, :section, :conf, :ub, :ua)"
                    ),
                    {
                        "id": item.get("id") or str(uuid.uuid4()),
                        "pid": policy_id,
                        "cat": item.get("service_category"),
                        "key": item.get("benefit_key"),
                        "label": item.get("benefit_label"),
                        "elig": json.dumps(item.get("eligibility")) if item.get("eligibility") is not None else None,
                        "limits": json.dumps(item.get("limits")) if item.get("limits") is not None else None,
                        "notes": item.get("notes"),
                        "quote": item.get("source_quote"),
                        "section": item.get("source_section"),
                        "conf": item.get("confidence"),
                        "ub": updated_by,
                        "ua": now,
                    },
                )

    # ==================================================================
    # Resolved assignment policies
    # ==================================================================
    def get_resolved_assignment_policy(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM resolved_assignment_policies WHERE assignment_id = :aid"),
                {"aid": assignment_id},
            ).fetchone()
        d = self._row_to_dict(row)
        if d:
            self._parse_json_col(d, "resolution_context_json")
        return d

    def list_resolved_policy_benefits(self, resolved_policy_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM resolved_assignment_policy_benefits WHERE resolved_policy_id = :rid ORDER BY benefit_key"),
                {"rid": resolved_policy_id},
            ).fetchall()
        items = self._rows_to_list(rows)
        for d in items:
            self._parse_json_col(d, "evidence_required_json")
            self._parse_json_col(d, "exclusions_json")
            self._parse_json_col(d, "source_rule_ids_json")
        return items

    def list_resolved_policy_exclusions(self, resolved_policy_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM resolved_assignment_policy_exclusions WHERE resolved_policy_id = :rid"),
                {"rid": resolved_policy_id},
            ).fetchall()
        items = self._rows_to_list(rows)
        for d in items:
            self._parse_json_col(d, "source_rule_ids_json")
        return items

    def upsert_resolved_assignment_policy(
        self,
        assignment_id: str,
        case_id: Optional[str],
        company_id: str,
        policy_id: str,
        policy_version_id: str,
        canonical_case_id: Optional[str],
        resolution_status: str,
        resolution_context: Dict[str, Any],
        benefits: List[Dict[str, Any]],
        exclusions: List[Dict[str, Any]],
    ) -> str:
        now = datetime.utcnow().isoformat()
        with self.engine.connect() as conn:
            existing = conn.execute(
                text("SELECT id FROM resolved_assignment_policies WHERE assignment_id = :aid"),
                {"aid": assignment_id},
            ).fetchone()
        rid = str(uuid.uuid4()) if not existing else existing._mapping["id"]
        with self.engine.begin() as conn:
            if existing:
                conn.execute(text("""
                    UPDATE resolved_assignment_policies SET
                    case_id = :cid, company_id = :coid, policy_id = :pid, policy_version_id = :vid,
                    canonical_case_id = :ccid, resolution_status = :status, resolved_at = :now,
                    resolution_context_json = :ctx, updated_at = :now
                    WHERE assignment_id = :aid
                """), {
                    "aid": assignment_id, "cid": case_id, "coid": company_id, "pid": policy_id,
                    "vid": policy_version_id, "ccid": canonical_case_id, "status": resolution_status,
                    "now": now, "ctx": json.dumps(resolution_context),
                })
                conn.execute(text("DELETE FROM resolved_assignment_policy_benefits WHERE resolved_policy_id = :rid"), {"rid": rid})
                conn.execute(text("DELETE FROM resolved_assignment_policy_exclusions WHERE resolved_policy_id = :rid"), {"rid": rid})
            else:
                conn.execute(text("""
                    INSERT INTO resolved_assignment_policies
                    (id, assignment_id, case_id, company_id, policy_id, policy_version_id, canonical_case_id,
                     resolution_status, resolved_at, resolution_context_json, created_at, updated_at)
                    VALUES (:id, :aid, :cid, :coid, :pid, :vid, :ccid, :status, :now, :ctx, :now, :now)
                """), {
                    "id": rid, "aid": assignment_id, "cid": case_id, "coid": company_id, "pid": policy_id,
                    "vid": policy_version_id, "ccid": canonical_case_id, "status": resolution_status,
                    "now": now, "ctx": json.dumps(resolution_context),
                })
            for b in benefits:
                bid = str(uuid.uuid4())
                inc = b.get("included", True)
                apr = b.get("approval_required", False)
                if not isinstance(inc, bool):
                    inc = bool(inc)
                if not isinstance(apr, bool):
                    apr = bool(apr)
                conn.execute(text("""
                    INSERT INTO resolved_assignment_policy_benefits
                    (id, resolved_policy_id, benefit_key, included, min_value, standard_value, max_value,
                     currency, amount_unit, frequency, approval_required, evidence_required_json,
                     exclusions_json, condition_summary, source_rule_ids_json, created_at, updated_at)
                    VALUES (:id, :rid, :bk, :inc, :minv, :stdv, :maxv, :cur, :au, :freq, :apr, :evj, :exj, :cs, :srj, :now, :now)
                """), {
                    "id": bid, "rid": rid, "bk": b["benefit_key"], "inc": inc,
                    "minv": b.get("min_value"), "stdv": b.get("standard_value"), "maxv": b.get("max_value"),
                    "cur": b.get("currency"), "au": b.get("amount_unit"), "freq": b.get("frequency"),
                    "apr": apr,
                    "evj": json.dumps(b.get("evidence_required_json") or []),
                    "exj": json.dumps(b.get("exclusions_json") or []),
                    "cs": b.get("condition_summary"), "srj": json.dumps(b.get("source_rule_ids_json") or []),
                    "now": now,
                })
            for e in exclusions:
                eid = str(uuid.uuid4())
                conn.execute(text("""
                    INSERT INTO resolved_assignment_policy_exclusions
                    (id, resolved_policy_id, benefit_key, domain, description, source_rule_ids_json)
                    VALUES (:id, :rid, :bk, :dom, :desc, :srj)
                """), {
                    "id": eid, "rid": rid, "bk": e.get("benefit_key"), "dom": e["domain"],
                    "desc": e.get("description"), "srj": json.dumps(e.get("source_rule_ids_json") or []),
                })
        return rid

    # ==================================================================
    # Case Readiness Core v1
    # ==================================================================
    def _readiness_store_available(self) -> bool:
        """
        False when `readiness_templates` is missing (e.g. Supabase migration not applied).
        Cached per process; deploy migration + restart to recover.
        """
        if self._readiness_store_cache is not None:
            return self._readiness_store_cache
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1 FROM readiness_templates LIMIT 1"))
            self._readiness_store_cache = True
        except Exception as e:
            log.warning(
                "readiness_templates unavailable — apply migration 20260321000000_case_readiness_core.sql: %s",
                e,
            )
            self._readiness_store_cache = False
        return self._readiness_store_cache

    def seed_readiness_templates_if_empty(self) -> None:
        """Load JSON seed when no templates exist (idempotent)."""
        if not self._readiness_store_available():
            log.warning("readiness template seed skipped: readiness_templates table not available")
            return
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT COUNT(*) AS n FROM readiness_templates")).fetchone()
            if row and int(row[0] or 0) > 0:
                return
        seed_path = os.path.join(os.path.dirname(__file__), "seed_data", "readiness_templates.json")
        if not os.path.isfile(seed_path):
            log.warning("readiness seed file missing: %s", seed_path)
            return
        with open(seed_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        templates = payload.get("templates") or []
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            for t in templates:
                tid = str(uuid.uuid4())
                dest = (t.get("destination_key") or "").strip().upper()
                route = (t.get("route_key") or DEFAULT_ROUTE_KEY).strip() or DEFAULT_ROUTE_KEY
                if not dest:
                    continue
                watchouts = json.dumps(t.get("watchouts") or [])
                conn.execute(
                    text(
                        "INSERT INTO readiness_templates "
                        "(id, destination_key, route_key, route_title, employee_summary, hr_summary, "
                        "internal_notes_hr, watchouts_json, updated_at) "
                        "VALUES (:id, :dk, :rk, :rt, :es, :hs, :inh, :wj, :ua)"
                    ),
                    {
                        "id": tid,
                        "dk": dest,
                        "rk": route,
                        "rt": t.get("route_title") or f"{dest} — {route}",
                        "es": t.get("employee_summary") or "",
                        "hs": t.get("hr_summary") or "",
                        "inh": t.get("internal_notes_hr"),
                        "wj": watchouts,
                        "ua": now,
                    },
                )
                for c in t.get("checklist") or []:
                    cid = str(uuid.uuid4())
                    conn.execute(
                        text(
                            "INSERT INTO readiness_template_checklist_items "
                            "(id, template_id, sort_order, title, owner_role, required, depends_on_sort_order, "
                            "notes_employee, notes_hr, stable_key) "
                            "VALUES (:id, :tid, :so, :title, :own, :req, :dep, :ne, :nh, :sk)"
                        ),
                        {
                            "id": cid,
                            "tid": tid,
                            "so": int(c.get("sort_order") or 0),
                            "title": c.get("title") or "Item",
                            "own": (c.get("owner_role") or "employee").strip(),
                            "req": 1 if c.get("required", True) else 0,
                            "dep": c.get("depends_on_sort_order"),
                            "ne": c.get("notes_employee"),
                            "nh": c.get("notes_hr"),
                            "sk": c.get("stable_key"),
                        },
                    )
                for m in t.get("milestones") or []:
                    mid = str(uuid.uuid4())
                    conn.execute(
                        text(
                            "INSERT INTO readiness_template_milestones "
                            "(id, template_id, sort_order, phase, title, body_employee, body_hr, owner_role, relative_timing) "
                            "VALUES (:id, :tid, :so, :ph, :title, :be, :bh, :own, :rt)"
                        ),
                        {
                            "id": mid,
                            "tid": tid,
                            "so": int(m.get("sort_order") or 0),
                            "ph": (m.get("phase") or "general").strip(),
                            "title": m.get("title") or "Milestone",
                            "be": m.get("body_employee"),
                            "bh": m.get("body_hr"),
                            "own": (m.get("owner_role") or "hr").strip(),
                            "rt": m.get("relative_timing"),
                        },
                    )

    def get_readiness_template(self, destination_key: str, route_key: str) -> Optional[Dict[str, Any]]:
        if not self._readiness_store_available():
            return None
        dk = (destination_key or "").strip().upper()
        rk = (route_key or DEFAULT_ROUTE_KEY).strip() or DEFAULT_ROUTE_KEY
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM readiness_templates WHERE destination_key = :dk AND route_key = :rk"),
                {"dk": dk, "rk": rk},
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def resolve_readiness_destination_for_assignment(self, assignment_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Returns (destination_raw, destination_key) from employee profile, then relocation case.
        """
        prof = self.get_employee_profile(assignment_id)
        raw = extract_destination_from_profile(prof)
        if not raw:
            asn = self.get_assignment_by_id(assignment_id)
            if asn:
                cid = (asn.get("case_id") or "").strip()
                case = self.get_case_by_id(cid) if cid else None
                if case:
                    pj = case.get("profile_json")
                    raw = extract_destination_from_case_profile(pj)
                    if not raw and case.get("host_country"):
                        raw = str(case.get("host_country")).strip()
        key = normalize_destination_key(raw)
        return raw, key

    def ensure_case_readiness_binding(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        """Create case_readiness row pointing at resolved template; no template duplication."""
        asn = self.get_assignment_by_id(assignment_id)
        if not asn:
            return None
        prof = self.get_employee_profile(assignment_id)
        _, dest_key = self.resolve_readiness_destination_for_assignment(assignment_id)
        route_key = resolve_readiness_route_key(asn, prof)
        if not dest_key:
            return None
        tmpl = self.get_readiness_template(dest_key, route_key)
        if not tmpl:
            return None
        tid = tmpl["id"]
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            row = conn.execute(
                text("SELECT * FROM case_readiness WHERE assignment_id = :aid"),
                {"aid": assignment_id},
            ).fetchone()
            if row:
                d = dict(row._mapping)
                if d.get("template_id") != tid:
                    conn.execute(
                        text(
                            "UPDATE case_readiness SET template_id = :tid, destination_key = :dk, "
                            "route_key = :rk, updated_at = :ua WHERE assignment_id = :aid"
                        ),
                        {"tid": tid, "dk": dest_key, "rk": route_key, "ua": now, "aid": assignment_id},
                    )
                row2 = conn.execute(
                    text("SELECT * FROM case_readiness WHERE assignment_id = :aid"), {"aid": assignment_id}
                ).fetchone()
                return self._row_to_dict(row2) if row2 else None
            conn.execute(
                text(
                    "INSERT INTO case_readiness (assignment_id, template_id, destination_key, route_key, updated_at) "
                    "VALUES (:aid, :tid, :dk, :rk, :ua)"
                ),
                {"aid": assignment_id, "tid": tid, "dk": dest_key, "rk": route_key, "ua": now},
            )
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM case_readiness WHERE assignment_id = :aid"), {"aid": assignment_id}).fetchone()
        return self._row_to_dict(row) if row else None

    def get_hr_readiness_summary(self, assignment_id: str) -> Dict[str, Any]:
        """Compact payload for first paint; no full checklist rows."""
        from . import provenance_catalog

        raw_dest, dest_key = self.resolve_readiness_destination_for_assignment(assignment_id)
        prof = self.get_employee_profile(assignment_id)
        asn = self.get_assignment_by_id(assignment_id)
        route_key = resolve_readiness_route_key(asn or {}, prof) if asn else DEFAULT_ROUTE_KEY
        if not dest_key:
            return {
                "resolved": False,
                "reason": "no_destination",
                "destination_raw": raw_dest,
                "destination_key": None,
                "route_key": route_key,
                **provenance_catalog.degraded_readiness_payload(
                    "no_destination", raw_dest, None, route_key
                ),
            }
        if not self._readiness_store_available():
            return {
                "resolved": False,
                "reason": "readiness_store_unavailable",
                "destination_raw": raw_dest,
                "destination_key": dest_key,
                "route_key": route_key,
                **provenance_catalog.degraded_readiness_payload(
                    "readiness_store_unavailable", raw_dest, dest_key, route_key
                ),
            }
        tmpl = self.get_readiness_template(dest_key, route_key)
        if not tmpl:
            return {
                "resolved": False,
                "reason": "no_template",
                "destination_raw": raw_dest,
                "destination_key": dest_key,
                "route_key": route_key,
                **provenance_catalog.degraded_readiness_payload(
                    "no_template", raw_dest, dest_key, route_key
                ),
            }
        bind = self.ensure_case_readiness_binding(assignment_id)
        tid = tmpl["id"]
        watchouts = []
        try:
            watchouts = json.loads(tmpl.get("watchouts_json") or "[]")
        except Exception:
            watchouts = []
        if not isinstance(watchouts, list):
            watchouts = []
        top_watchouts = [str(w) for w in watchouts[:3]]

        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT
                        COUNT(c.id) AS total,
                        SUM(CASE WHEN COALESCE(s.status, 'pending') IN ('done', 'waived') THEN 1 ELSE 0 END) AS doneish
                    FROM readiness_template_checklist_items c
                    LEFT JOIN case_readiness_checklist_state s
                        ON s.template_checklist_id = c.id AND s.assignment_id = :aid
                    WHERE c.template_id = :tid
                    """
                ),
                {"aid": assignment_id, "tid": tid},
            ).fetchone()
        total_chk = int(row[0] or 0) if row else 0
        done_chk = int(row[1] or 0) if row else 0
        pending_chk = max(0, total_chk - done_chk)

        next_ms = None
        with self.engine.connect() as conn:
            mrows = conn.execute(
                text(
                    """
                    SELECT m.id, m.title, m.sort_order, m.phase, m.relative_timing, ms.completed_at
                    FROM readiness_template_milestones m
                    LEFT JOIN case_readiness_milestone_state ms
                        ON ms.template_milestone_id = m.id AND ms.assignment_id = :aid
                    WHERE m.template_id = :tid
                    ORDER BY m.sort_order ASC, m.id ASC
                    """
                ),
                {"aid": assignment_id, "tid": tid},
            ).fetchall()
        for mr in mrows:
            r = dict(mr._mapping)
            if not r.get("completed_at"):
                next_ms = {
                    "id": r.get("id"),
                    "title": r.get("title"),
                    "phase": r.get("phase"),
                    "relative_timing": r.get("relative_timing"),
                }
                break

        base_summary = {
            "resolved": True,
            "assignment_id": assignment_id,
            "destination_raw": raw_dest,
            "destination_key": dest_key,
            "route_key": route_key,
            "template_id": tid,
            "route_title": tmpl.get("route_title"),
            "employee_summary": tmpl.get("employee_summary"),
            "hr_summary": tmpl.get("hr_summary"),
            "top_watchouts": top_watchouts,
            "checklist": {
                "total": total_chk,
                "completed_or_waived": done_chk,
                "pending": pending_chk,
            },
            "next_milestone": next_ms,
            "updated_at": tmpl.get("updated_at"),
            "case_readiness_updated_at": (bind or {}).get("updated_at"),
        }
        prov = provenance_catalog.readiness_summary_provenance_block(dest_key, route_key, True)
        return {**base_summary, **prov}

    def get_hr_readiness_detail(self, assignment_id: str) -> Dict[str, Any]:
        """Full checklist + milestones merged with case state (two queries)."""
        from . import provenance_catalog

        summary = self.get_hr_readiness_summary(assignment_id)
        if not summary.get("resolved"):
            return {"summary": summary, "checklist_items": [], "milestones": []}
        tid = summary["template_id"]
        with self.engine.connect() as conn:
            crows = conn.execute(
                text(
                    """
                    SELECT c.id, c.sort_order, c.title, c.owner_role, c.required, c.depends_on_sort_order,
                           c.notes_employee, c.notes_hr, c.stable_key,
                           COALESCE(s.status, 'pending') AS status, s.notes AS state_notes, s.updated_at AS state_updated_at
                    FROM readiness_template_checklist_items c
                    LEFT JOIN case_readiness_checklist_state s
                        ON s.template_checklist_id = c.id AND s.assignment_id = :aid
                    WHERE c.template_id = :tid
                    ORDER BY c.sort_order ASC, c.id ASC
                    """
                ),
                {"aid": assignment_id, "tid": tid},
            ).fetchall()
            mrows = conn.execute(
                text(
                    """
                    SELECT m.id, m.sort_order, m.phase, m.title, m.body_employee, m.body_hr, m.owner_role, m.relative_timing,
                           ms.completed_at, ms.notes AS state_notes, ms.updated_at AS state_updated_at
                    FROM readiness_template_milestones m
                    LEFT JOIN case_readiness_milestone_state ms
                        ON ms.template_milestone_id = m.id AND ms.assignment_id = :aid
                    WHERE m.template_id = :tid
                    ORDER BY m.sort_order ASC, m.id ASC
                    """
                ),
                {"aid": assignment_id, "tid": tid},
            ).fetchall()
        checklist_items = [dict(r._mapping) for r in crows]
        milestones = [dict(r._mapping) for r in mrows]
        dk = str(summary.get("destination_key") or "")
        rk = str(summary.get("route_key") or DEFAULT_ROUTE_KEY)
        enriched_checklist = [
            provenance_catalog.enrich_checklist_row(row, dk, rk) for row in checklist_items
        ]
        detail_provenance = provenance_catalog.readiness_summary_provenance_block(dk, rk, True)
        return {
            "summary": summary,
            "checklist_items": enriched_checklist,
            "milestones": milestones,
            "provenance": detail_provenance,
        }

    def upsert_readiness_checklist_state(
        self, assignment_id: str, template_checklist_id: str, status: str, notes: Optional[str] = None
    ) -> None:
        allowed = {"pending", "in_progress", "done", "waived", "blocked"}
        if status not in allowed:
            raise ValueError("invalid checklist status")
        now = datetime.utcnow().isoformat()
        params = {"aid": assignment_id, "cid": template_checklist_id, "st": status, "notes": notes, "ua": now}
        sql_sqlite = text(
            """
            INSERT INTO case_readiness_checklist_state
            (assignment_id, template_checklist_id, status, notes, updated_at)
            VALUES (:aid, :cid, :st, :notes, :ua)
            ON CONFLICT(assignment_id, template_checklist_id) DO UPDATE SET
                status = excluded.status,
                notes = COALESCE(excluded.notes, case_readiness_checklist_state.notes),
                updated_at = excluded.updated_at
            """
        )
        sql_pg = text(
            """
            INSERT INTO case_readiness_checklist_state
            (assignment_id, template_checklist_id, status, notes, updated_at)
            VALUES (:aid, :cid, :st, :notes, :ua)
            ON CONFLICT(assignment_id, template_checklist_id) DO UPDATE SET
                status = EXCLUDED.status,
                notes = COALESCE(EXCLUDED.notes, case_readiness_checklist_state.notes),
                updated_at = EXCLUDED.updated_at
            """
        )
        with self.engine.begin() as conn:
            conn.execute(sql_sqlite if _is_sqlite else sql_pg, params)

    def upsert_readiness_milestone_state(
        self, assignment_id: str, template_milestone_id: str, completed: bool, notes: Optional[str] = None
    ) -> None:
        now = datetime.utcnow().isoformat()
        completed_at = now if completed else None
        with self.engine.begin() as conn:
            if _is_sqlite:
                conn.execute(
                    text(
                        """
                        INSERT INTO case_readiness_milestone_state
                        (assignment_id, template_milestone_id, completed_at, notes, updated_at)
                        VALUES (:aid, :mid, :cat, :notes, :ua)
                        ON CONFLICT(assignment_id, template_milestone_id) DO UPDATE SET
                            completed_at = excluded.completed_at,
                            notes = COALESCE(excluded.notes, case_readiness_milestone_state.notes),
                            updated_at = excluded.updated_at
                        """
                    ),
                    {"aid": assignment_id, "mid": template_milestone_id, "cat": completed_at, "notes": notes, "ua": now},
                )
            else:
                conn.execute(
                    text(
                        """
                        INSERT INTO case_readiness_milestone_state
                        (assignment_id, template_milestone_id, completed_at, notes, updated_at)
                        VALUES (:aid, :mid, :cat, :notes, :ua)
                        ON CONFLICT(assignment_id, template_milestone_id) DO UPDATE SET
                            completed_at = EXCLUDED.completed_at,
                            notes = COALESCE(EXCLUDED.notes, case_readiness_milestone_state.notes),
                            updated_at = EXCLUDED.updated_at
                        """
                    ),
                    {"aid": assignment_id, "mid": template_milestone_id, "cat": completed_at, "notes": notes, "ua": now},
                )

    # ==================================================================
    # Debug KV operations
    # ==================================================================
    def debug_kv_set(self, key: str, value: str) -> None:
        now = datetime.utcnow().isoformat()
        kv_id = key
        with self.engine.begin() as conn:
            existing = conn.execute(
                text("SELECT 1 FROM rp_debug_kv WHERE key = :key"), {"key": key}
            ).fetchone()
            if existing:
                conn.execute(text(
                    "UPDATE rp_debug_kv SET value = :value, updated_at = :now WHERE key = :key"
                ), {"value": value, "now": now, "key": key})
            else:
                conn.execute(text(
                    "INSERT INTO rp_debug_kv (id, key, value, updated_at) VALUES (:id, :key, :value, :now)"
                ), {"id": kv_id, "key": key, "value": value, "now": now})

    def debug_kv_get(self, key: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT key, value, updated_at FROM rp_debug_kv WHERE key = :key"),
                {"key": key},
            ).fetchone()
        return self._row_to_dict(row)

    # ==================================================================
    # Debug: DB info
    # ==================================================================
    @staticmethod
    def get_db_info() -> Dict[str, Any]:
        """Return non-secret info about the database connection."""
        scheme = "postgresql" if not _is_sqlite else "sqlite"
        host = None
        if not _is_sqlite and "@" in _raw_url:
            after_at = _raw_url.split("@", 1)[-1]
            host = after_at.split("/")[0] if "/" in after_at else after_at
        connectivity = False
        server_time = None
        try:
            with _engine.connect() as conn:
                if _is_sqlite:
                    row = conn.execute(text("SELECT datetime('now') AS t")).fetchone()
                else:
                    row = conn.execute(text("SELECT now() AS t")).fetchone()
                if row:
                    server_time = str(row._mapping["t"])
                    connectivity = True
        except Exception as exc:
            server_time = f"error: {exc}"
        return {
            "db_url_scheme": scheme,
            "db_host": host,
            "connectivity": connectivity,
            "server_time": server_time,
        }

    @staticmethod
    def log_expected_tables_status() -> None:
        """
        Log which expected production tables exist. Use at startup to verify
        migrations have been applied. Expected tables from Supabase migrations.
        """
        expected = [
            "rfqs", "rfq_items", "rfq_recipients", "quotes", "quote_lines",
            "case_milestones", "analytics_events", "suppliers",
            "supplier_service_capabilities", "supplier_scoring_metadata",
            "company_preferred_suppliers",
            "policy_documents",
            "policy_document_clauses",
        ]
        if _is_sqlite:
            try:
                with _engine.connect() as conn:
                    present = []
                    missing = []
                    for t in expected:
                        r = conn.execute(text(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name=:n"
                        ), {"n": t}).fetchone()
                        (present if r else missing).append(t)
                    log.info(
                        "db_tables: present=%s missing=%s (sqlite)",
                        present, missing,
                    )
            except Exception as e:
                log.warning("db_tables check failed: %s", e)
            return
        try:
            with _engine.connect() as conn:
                placeholders = ",".join([f":t{i}" for i in range(len(expected))])
                params = {f"t{i}": t for i, t in enumerate(expected)}
                rows = conn.execute(text(f"""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name IN ({placeholders})
                """), params).fetchall()
                found = {r[0] for r in rows}
                present = [t for t in expected if t in found]
                missing = [t for t in expected if t not in found]
                log.info(
                    "db_tables: present=%s missing=%s (postgres). Apply migrations if missing.",
                    present, missing,
                )
                if missing:
                    log.warning(
                        "db_tables: Run supabase migrations for: %s. See docs/SUPABASE_MIGRATIONS.md",
                        missing,
                    )
        except Exception as e:
            log.warning("db_tables check failed: %s", e)


# Global database instance
db = Database()
