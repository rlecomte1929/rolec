"""[AUDIT-C1.6b] Misc/infrastructure DB methods, extracted from backend/database.py.

The remainder of the monolith: schema bootstrap (``init_db``), connection/
timeout setup, low-level row helpers, and the small admin_ops/immigration/
catalog/documents methods. These live here as a mixin (:class:`MiscMixin`)
that ``Database`` inherits, so every caller resolves unchanged via MRO.
Only ``Database.__init__`` stays in backend/database.py. ``..database``
module helpers are imported lazily in-method to avoid an import cycle.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import json
import logging
import os
import time
import uuid

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import ProgrammingError

from ..db_config import DATABASE_URL as _raw_url
from ..identity_normalize import email_normalized_from_identifier
from ..identity_normalize import normalize_invite_key
from ..identity_observability import identity_event
from ..readiness_service import DEFAULT_ROUTE_KEY

from ..db_config import DATABASE_URL as _raw_url

log = logging.getLogger(__name__)

_is_sqlite = _raw_url.startswith("sqlite")


class MiscMixin:
    """Misc/infrastructure methods mixed into :class:`backend.database.Database`."""

    def ensure_initialized(self) -> None:
        if self._initialized:
            return
        with self._init_lock:
            if self._initialized:
                return
            self.init_db()
            self._initialized = True

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

        B3-fix-v4: initialization check uses non-blocking lock acquisition.
        Calling ensure_initialized() with blocking=True while holding an open
        engine.begin() connection causes a deadlock when the startup daemon thread
        already holds _init_lock: the connection stays in "idle in transaction"
        until idle_in_transaction_session_timeout kills it (15s).  Using
        acquire(blocking=False) means we skip init if another thread is initializing
        and proceed with the SQL directly — tables always exist in prod
        (DISABLE_RUNTIME_DDL=true / Supabase migrations).
        """
        if not self._initialized:
            acquired = self._init_lock.acquire(blocking=False)
            if acquired:
                try:
                    if not self._initialized:  # double-checked locking
                        self.init_db()
                        self._initialized = True
                except Exception as _init_exc:
                    log.warning("_exec: init_db skipped due to error: %s", _init_exc)
                finally:
                    self._init_lock.release()
            else:
                log.warning(
                    "_exec: _init_lock held by another thread (startup race?) — "
                    "proceeding without init for op=%s request_id=%s",
                    op_name,
                    request_id,
                )
        start = time.perf_counter()
        result = conn.execute(text(sql), params)
        dur_ms = (time.perf_counter() - start) * 1000
        if request_id:
            log.info("request_id=%s db_op=%s dur_ms=%.2f", request_id, op_name, dur_ms)
        else:
            log.info("db_op=%s dur_ms=%.2f", op_name, dur_ms)
        return result

    def _db_healthcheck(self, conn) -> None:
        # [AUDIT-C1.6b fix] get_db_info is a @staticmethod on this mixin; resolve
        # it via self. The pre-fix `Database.get_db_info()` NameError'd because
        # `Database` is not imported into this extracted module -> 500 on every
        # endpoint that calls ensure_initialized() (e.g. GET /api/hr/assignments).
        info = self.get_db_info()
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

    def _maybe_ensure_hot_path_indexes(self) -> None:
        """
        Idempotent indexes for the hot listing paths on case_assignments +
        relocation_cases. Mirrors supabase/migrations/20260428100000_hot_path_indexes.sql.
        Runs on both SQLite and Postgres; uses IF NOT EXISTS so repeat boots
        are safe.
        """
        statements_pg = [
            "CREATE INDEX IF NOT EXISTS idx_case_assignments_hr_user_created_at "
            "ON case_assignments (hr_user_id, created_at DESC) "
            "WHERE archived_at IS NULL",
            "CREATE INDEX IF NOT EXISTS idx_relocation_cases_company_created_at "
            "ON relocation_cases (company_id, created_at DESC) "
            "WHERE archived_at IS NULL",
            "CREATE INDEX IF NOT EXISTS idx_case_assignments_employee_user "
            "ON case_assignments (employee_user_id) "
            "WHERE employee_user_id IS NOT NULL AND archived_at IS NULL",
            "CREATE INDEX IF NOT EXISTS idx_case_assignments_case_id "
            "ON case_assignments (case_id) "
            "WHERE archived_at IS NULL",
        ]
        # SQLite supports partial indexes via WHERE. Same DDL works on both
        # engines for our predicates — no dialect split needed.
        try:
            with self.engine.begin() as conn:
                for sql in statements_pg:
                    conn.execute(text(sql))
        except Exception as ex:
            log.warning("hot-path indexes ensure failed (run Supabase migration): %s", ex)

    def _maybe_ensure_archived_at_columns(self) -> None:
        """
        Idempotently adds archived_at to case_assignments and relocation_cases
        for soft-delete support (see delete_assignment). Works on both SQLite
        dev and Postgres prod.
        Supabase migration: 20260427100000_case_assignments_archived_at.sql
        """
        if _is_sqlite:
            # SQLite: ADD COLUMN IF NOT EXISTS is not supported in older SQLite;
            # swallow "duplicate column" errors instead.
            for table in ("case_assignments", "relocation_cases"):
                try:
                    with self.engine.begin() as conn:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN archived_at TEXT NULL"))
                except (OperationalError, ProgrammingError) as ex:
                    # Already exists — expected on second boot.
                    if "duplicate column" not in str(ex).lower():
                        log.warning("%s.archived_at ensure: %s", table, ex)
            return
        try:
            with self.engine.begin() as conn:
                conn.execute(text("ALTER TABLE case_assignments ADD COLUMN IF NOT EXISTS archived_at timestamptz NULL"))
                conn.execute(text("ALTER TABLE relocation_cases ADD COLUMN IF NOT EXISTS archived_at timestamptz NULL"))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_case_assignments_archived_at "
                    "ON case_assignments (archived_at) WHERE archived_at IS NOT NULL"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_relocation_cases_archived_at "
                    "ON relocation_cases (archived_at) WHERE archived_at IS NOT NULL"
                ))
        except Exception as ex:
            log.warning("archived_at columns ensure failed (run Supabase migration): %s", ex)

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

    def init_db(self) -> None:
        # In production (Render), avoid runtime DDL. Supabase migrations are the
        # source of truth. The early return must happen BEFORE the per-feature
        # `_maybe_ensure_*` helpers — those run ALTER/CREATE statements that
        # acquire table-level locks during the IF NOT EXISTS catalog check, and
        # on a cold start that compounds with pool warm-up to time out the
        # frontend's 15s axios window.
        from ..database import _auto_id_col, _seed_default_policy_template_sqlite, _sqlite_ensure_canonical_policy_tenant_columns, _sqlite_ensure_policy_hardening_columns, _sqlite_ensure_policy_import_columns  # lazy: avoid import cycle
        if not _is_sqlite and os.getenv("DISABLE_RUNTIME_DDL", "").lower() in ("1", "true", "yes"):
            with self.engine.connect() as conn:
                self._db_healthcheck(conn)
            log.info("Runtime DDL disabled via DISABLE_RUNTIME_DDL. Skipping init_db DDL.")
            try:
                self.seed_readiness_templates_if_empty()
            except Exception as e:
                log.warning("readiness template seed skipped: %s", e)
            try:
                self.ensure_missing_readiness_templates()
            except Exception as e:
                log.warning("readiness template top-up skipped: %s", e)
            try:
                self.seed_dossier_questions_if_missing()
            except Exception as e:
                log.warning("dossier questions seed skipped: %s", e)
            try:
                self._backfill_employee_contacts()
            except Exception as e:
                log.warning("employee_contacts backfill skipped: %s", e)
            return

        if not _is_sqlite:
            self._maybe_ensure_postgres_missing_schemas()
            self._maybe_ensure_postgres_case_assignments_employee_link_mode()
            self._maybe_ensure_policy_versions_normalization_draft_json()
            self._maybe_ensure_policy_versions_normalization_state()
            self._maybe_ensure_policy_benefit_rule_hr_overrides()
            self._maybe_ensure_compensation_allowance_policy_config()

        # archived_at is needed on both SQLite dev and Postgres prod. The helper
        # handles both and only runs ALTER TABLE if the column is missing.
        self._maybe_ensure_archived_at_columns()

        with self.engine.begin() as conn:
            if _is_sqlite:
                self._ensure_users_table_sqlite(conn)
            else:
                self._create_users_table(conn)

        # AUDIT-A1-followup (AIQ-383): On Postgres every table is managed by
        # Supabase migrations. The CREATE TABLE / CREATE INDEX block below is
        # SQLite-only dev scaffolding. Running it on Postgres causes
        # InFailedSqlTransaction because an earlier try/except ALTER in init_db
        # can leave the connection in a failed state. Exit early; nothing below
        # is needed on Postgres.
        if not _is_sqlite:
            return

        with self.engine.begin() as conn:
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
                    updated_at TEXT NOT NULL,
                    archived_at TEXT
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
                    decision TEXT,
                    archived_at TEXT,
                    -- Intake wizard progress. Mirrors Postgres migration
                    -- 20260529130000_case_assignments_intake_progress.sql.
                    intake_step INTEGER NOT NULL DEFAULT 0,
                    -- 5 = the canonical v2 intake step count (was a stale 7).
                    intake_total_steps INTEGER NOT NULL DEFAULT 5,
                    intake_updated_at TEXT
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS mobility_cases (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    employee_user_id TEXT,
                    origin_country TEXT,
                    destination_country TEXT,
                    case_type TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS assignment_mobility_links (
                    id TEXT PRIMARY KEY,
                    assignment_id TEXT NOT NULL UNIQUE,
                    mobility_case_id TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (mobility_case_id) REFERENCES mobility_cases(id) ON DELETE RESTRICT
                )
            """))

            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_assignment_mobility_links_assignment_id "
                "ON assignment_mobility_links(assignment_id)"
            ))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS case_people (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (case_id) REFERENCES mobility_cases(id) ON DELETE CASCADE
                )
            """))

            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS case_people_one_employee_per_case "
                "ON case_people(case_id) WHERE role = 'employee'"
            ))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS case_documents (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    person_id TEXT,
                    document_key TEXT,
                    document_status TEXT NOT NULL DEFAULT 'missing',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (case_id) REFERENCES mobility_cases(id) ON DELETE CASCADE,
                    FOREIGN KEY (person_id) REFERENCES case_people(id) ON DELETE SET NULL
                )
            """))

            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS case_documents_one_passport_copy_per_case "
                "ON case_documents(case_id) WHERE document_key = 'passport_copy'"
            ))

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
                CREATE TABLE IF NOT EXISTS wizard_employee_profiles (
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
                CREATE TABLE IF NOT EXISTS policy_extracted_benefits (
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
                CREATE TABLE IF NOT EXISTS policy_configs (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    name TEXT NOT NULL DEFAULT 'Compensation & Allowance',
                    config_key TEXT NOT NULL DEFAULT 'compensation_allowance',
                    description TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_by TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(company_id, config_key)
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_config_versions (
                    id TEXT PRIMARY KEY,
                    policy_config_id TEXT NOT NULL REFERENCES policy_configs(id) ON DELETE CASCADE,
                    version_number INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    effective_date TEXT NOT NULL,
                    published_at TEXT,
                    created_by TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(policy_config_id, version_number)
                )
            """))

            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_sqlite_pc_one_published
                ON policy_config_versions(policy_config_id)
                WHERE status = 'published'
            """))

            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_sqlite_pc_one_draft
                ON policy_config_versions(policy_config_id)
                WHERE status = 'draft'
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_config_benefits (
                    id TEXT PRIMARY KEY,
                    policy_config_version_id TEXT NOT NULL
                        REFERENCES policy_config_versions(id) ON DELETE CASCADE,
                    benefit_key TEXT NOT NULL,
                    benefit_label TEXT NOT NULL,
                    category TEXT NOT NULL,
                    covered INTEGER NOT NULL DEFAULT 0,
                    value_type TEXT NOT NULL DEFAULT 'none',
                    amount_value REAL,
                    currency_code TEXT,
                    percentage_value REAL,
                    unit_frequency TEXT NOT NULL DEFAULT 'one_time',
                    cap_rule_json TEXT NOT NULL DEFAULT '{}',
                    notes TEXT,
                    conditions_json TEXT NOT NULL DEFAULT '{}',
                    assignment_types TEXT NOT NULL DEFAULT '[]',
                    family_statuses TEXT NOT NULL DEFAULT '[]',
                    employee_levels TEXT NOT NULL DEFAULT '[]',
                    targeting_signature TEXT NOT NULL DEFAULT 'global',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    display_order INTEGER NOT NULL DEFAULT 0,
                    source TEXT DEFAULT 'seeded',
                    auto_generated INTEGER NOT NULL DEFAULT 1,
                    field_confidence REAL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(policy_config_version_id, benefit_key, targeting_signature)
                )
            """))
            # Back-compat: when this table pre-existed (tests reusing an
            # older ci_test.db or a dev sqlite), add the new column with the
            # same "applies to all levels" default so existing rows keep
            # their effective meaning.
            # AUDIT-A1: SQLite-only back-compat. On Postgres the equivalent
            # column was already ensured as jsonb by
            # _maybe_ensure_compensation_allowance_policy_config() (line ~711
            # above) which uses `ADD COLUMN IF NOT EXISTS`. Running this ALTER
            # on Postgres caused the column-already-exists error to be caught
            # in Python but the transaction was already aborted by Postgres,
            # cascading into `InFailedSqlTransaction` on the next CREATE INDEX
            # below. See audit/02-expert-security.md SEC-1 / audit/02-expert-qa.md QA-1.
            if _is_sqlite:
                try:
                    conn.execute(text(
                        "ALTER TABLE policy_config_benefits ADD COLUMN employee_levels TEXT NOT NULL DEFAULT '[]'"
                    ))
                except Exception:
                    # Column already exists — safe to ignore in SQLite (caught error
                    # does not abort SQLite transactions).
                    pass
                # AIQ-838: provenance marker (extracted_llm | template_default | manual_hr | seeded).
                try:
                    conn.execute(text(
                        "ALTER TABLE policy_config_benefits ADD COLUMN source TEXT DEFAULT 'seeded'"
                    ))
                except Exception:
                    pass
                # AIQ-839: auto_generated flag (0 = manual HR entry, 1 = AI/template/seeded).
                try:
                    conn.execute(text(
                        "ALTER TABLE policy_config_benefits ADD COLUMN auto_generated INTEGER NOT NULL DEFAULT 1"
                    ))
                except Exception:
                    pass
                # AIQ-873: per-field extraction confidence (NULL except extracted_llm rows).
                try:
                    conn.execute(text(
                        "ALTER TABLE policy_config_benefits ADD COLUMN field_confidence REAL"
                    ))
                except Exception:
                    pass

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_sqlite_pc_benefits_version
                ON policy_config_benefits(policy_config_version_id)
            """))

            # AIQ-839: field-level audit trail for policy_config_benefits manual-override
            # path. SQLite mirror of supabase/migrations/20260607070000_policy_config_benefits_audit.sql.
            # No FK on benefit_id (the PUT draft path deletes+reinserts rows each save).
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_config_benefits_audit (
                    id TEXT PRIMARY KEY,
                    benefit_id TEXT,
                    policy_config_version_id TEXT,
                    benefit_key TEXT,
                    action TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    source TEXT,
                    changed_by TEXT,
                    changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_sqlite_pcb_audit_benefit
                ON policy_config_benefits_audit(benefit_id, changed_at DESC)
            """))

            # Section C of HR Policy: per-jurisdiction × employee_level ×
            # assignment_type override rows that stack on top of a base
            # policy_config_benefits row. SQLite mirror of supabase/migrations/
            # 20260502100000_policy_benefit_jurisdiction_overrides.sql.
            # SQLite has no text[] — jurisdiction_countries is JSON-encoded
            # TEXT, parsed by services/policy_section_c_resolver.py which
            # handles both shapes (Postgres array, SQLite JSON string).
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_benefit_jurisdiction_overrides (
                    id TEXT PRIMARY KEY,
                    benefit_row_id TEXT NOT NULL
                        REFERENCES policy_config_benefits(id) ON DELETE CASCADE,
                    jurisdiction_countries TEXT NOT NULL DEFAULT '[]',
                    employee_level TEXT,
                    assignment_type TEXT,
                    amount_value REAL,
                    currency_code TEXT,
                    cap_rule_json TEXT NOT NULL DEFAULT '{}',
                    reimbursement_md TEXT,
                    repayment_md TEXT,
                    display_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (benefit_row_id, employee_level, assignment_type)
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_sqlite_pbjo_benefit
                ON policy_benefit_jurisdiction_overrides(benefit_row_id)
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
                    updated_at TEXT NOT NULL,
                    file_size_bytes INTEGER,
                    archived_at TEXT,
                    assistant_import_status TEXT,
                    processed_at TEXT
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
                CREATE TABLE IF NOT EXISTS policy_knowledge_snapshots (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    policy_document_id TEXT NOT NULL,
                    version_label TEXT,
                    status TEXT NOT NULL DEFAULT 'failed',
                    extraction_method TEXT NOT NULL DEFAULT 'deterministic_v1',
                    created_at TEXT NOT NULL,
                    superseded_at TEXT,
                    revision_number INTEGER NOT NULL DEFAULT 1,
                    parent_snapshot_id TEXT,
                    superseded_by_snapshot_id TEXT,
                    activation_state TEXT NOT NULL DEFAULT 'failed',
                    activated_at TEXT,
                    activated_by_user_id TEXT,
                    FOREIGN KEY (policy_document_id) REFERENCES policy_documents(id) ON DELETE CASCADE,
                    FOREIGN KEY (parent_snapshot_id) REFERENCES policy_knowledge_snapshots(id) ON DELETE SET NULL,
                    FOREIGN KEY (superseded_by_snapshot_id) REFERENCES policy_knowledge_snapshots(id) ON DELETE SET NULL
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_policy_knowledge_snapshots_company
                ON policy_knowledge_snapshots(company_id)
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_document_chunks (
                    id TEXT PRIMARY KEY,
                    policy_document_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    page_number INTEGER,
                    section_title TEXT,
                    text_content TEXT NOT NULL,
                    token_count INTEGER,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    snapshot_id TEXT,
                    FOREIGN KEY (policy_document_id) REFERENCES policy_documents(id) ON DELETE CASCADE
                )
            """))
            # Must run before indexes on policy_document_chunks.snapshot_id (upgrade path for older SQLite files).
            # AUDIT-A1: the helper uses `sqlite_master` / `PRAGMA table_info`, which fail on Postgres and
            # abort the surrounding transaction (caught Python error doesn't roll back Postgres). Guard.
            if _is_sqlite:
                _sqlite_ensure_policy_hardening_columns(conn)
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_policy_document_chunks_doc
                ON policy_document_chunks(policy_document_id)
            """))
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS policy_document_chunks_snapshot_chunk_idx
                ON policy_document_chunks(snapshot_id, chunk_index)
                WHERE snapshot_id IS NOT NULL
            """))
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS policy_document_chunks_doc_chunk_legacy_idx
                ON policy_document_chunks(policy_document_id, chunk_index)
                WHERE snapshot_id IS NULL
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_processing_runs (
                    id TEXT PRIMARY KEY,
                    policy_document_id TEXT NOT NULL,
                    run_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    error_message TEXT,
                    metrics_json TEXT,
                    FOREIGN KEY (policy_document_id) REFERENCES policy_documents(id) ON DELETE CASCADE
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_policy_processing_runs_doc
                ON policy_processing_runs(policy_document_id)
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_facts (
                    id TEXT PRIMARY KEY,
                    snapshot_id TEXT NOT NULL,
                    fact_type TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    subcategory TEXT,
                    normalized_value_json TEXT NOT NULL DEFAULT '{}',
                    applicability_json TEXT NOT NULL DEFAULT '{}',
                    ambiguity_flag INTEGER NOT NULL DEFAULT 0,
                    confidence_score REAL,
                    source_chunk_id TEXT NOT NULL,
                    source_page INTEGER,
                    source_section TEXT,
                    source_quote TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (snapshot_id) REFERENCES policy_knowledge_snapshots(id) ON DELETE CASCADE,
                    FOREIGN KEY (source_chunk_id) REFERENCES policy_document_chunks(id) ON DELETE RESTRICT
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_policy_facts_snapshot ON policy_facts(snapshot_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_policy_facts_chunk ON policy_facts(source_chunk_id)
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS canonical_policy_documents (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    source_policy_document_id TEXT,
                    source_type TEXT NOT NULL DEFAULT 'local_file',
                    source_uri TEXT,
                    filename TEXT,
                    mime_type TEXT,
                    title TEXT,
                    policy_scope TEXT,
                    document_type TEXT,
                    version_label TEXT,
                    effective_date TEXT,
                    default_currency TEXT,
                    assignment_types_json TEXT NOT NULL DEFAULT '[]',
                    raw_text TEXT,
                    normalized_text TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    ingestion_status TEXT NOT NULL DEFAULT 'ingested',
                    extraction_status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (source_policy_document_id) REFERENCES policy_documents(id) ON DELETE SET NULL
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_canonical_policy_documents_source_policy
                ON canonical_policy_documents(source_policy_document_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_canonical_policy_documents_company
                ON canonical_policy_documents(company_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_canonical_policy_documents_status
                ON canonical_policy_documents(extraction_status)
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS canonical_policy_document_chunks (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    canonical_policy_document_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    section_path TEXT,
                    structure_type TEXT,
                    page_number INTEGER,
                    char_start INTEGER,
                    char_end INTEGER,
                    text_content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (canonical_policy_document_id) REFERENCES canonical_policy_documents(id) ON DELETE CASCADE
                )
            """))
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_canonical_policy_document_chunks_doc_chunk
                ON canonical_policy_document_chunks(canonical_policy_document_id, chunk_index)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_canonical_policy_document_chunks_doc
                ON canonical_policy_document_chunks(canonical_policy_document_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_canonical_policy_document_chunks_company
                ON canonical_policy_document_chunks(company_id)
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS canonical_policy_facts (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    canonical_policy_document_id TEXT NOT NULL,
                    canonical_policy_document_chunk_id TEXT NOT NULL,
                    source_policy_document_id TEXT,
                    phase TEXT,
                    benefit_category TEXT,
                    value_type TEXT NOT NULL,
                    frequency TEXT,
                    provider_entity TEXT,
                    title TEXT,
                    description TEXT,
                    eligibility_json TEXT NOT NULL DEFAULT '{}',
                    assignment_types_json TEXT NOT NULL DEFAULT '[]',
                    amount NUMERIC,
                    currency TEXT,
                    percentage REAL,
                    quantity REAL,
                    duration_value INTEGER,
                    duration_unit TEXT,
                    value_text TEXT,
                    is_taxable INTEGER,
                    reimbursement_required INTEGER,
                    source_quote TEXT,
                    confidence_score REAL,
                    raw_payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (canonical_policy_document_id) REFERENCES canonical_policy_documents(id) ON DELETE CASCADE,
                    FOREIGN KEY (canonical_policy_document_chunk_id) REFERENCES canonical_policy_document_chunks(id) ON DELETE CASCADE,
                    FOREIGN KEY (source_policy_document_id) REFERENCES policy_documents(id) ON DELETE SET NULL
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_canonical_policy_facts_doc
                ON canonical_policy_facts(canonical_policy_document_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_canonical_policy_facts_company
                ON canonical_policy_facts(company_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_canonical_policy_facts_chunk
                ON canonical_policy_facts(canonical_policy_document_chunk_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_canonical_policy_facts_category_phase
                ON canonical_policy_facts(benefit_category, phase)
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS canonical_policy_fact_validation_errors (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    canonical_policy_document_id TEXT NOT NULL,
                    canonical_policy_document_chunk_id TEXT NOT NULL,
                    raw_payload_json TEXT NOT NULL DEFAULT '{}',
                    errors_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (canonical_policy_document_id) REFERENCES canonical_policy_documents(id) ON DELETE CASCADE,
                    FOREIGN KEY (canonical_policy_document_chunk_id) REFERENCES canonical_policy_document_chunks(id) ON DELETE CASCADE
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_canonical_policy_fact_validation_errors_doc
                ON canonical_policy_fact_validation_errors(canonical_policy_document_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_canonical_policy_fact_validation_errors_company
                ON canonical_policy_fact_validation_errors(company_id)
            """))
            # AUDIT-A1: SQLite-only helper. See note on _sqlite_ensure_policy_hardening_columns above.
            if _is_sqlite:
                _sqlite_ensure_canonical_policy_tenant_columns(conn)
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS canonical_policy_query_audit_logs (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    user_role TEXT NOT NULL,
                    canonical_policy_document_id TEXT NOT NULL,
                    query_text TEXT NOT NULL,
                    redacted_query_text TEXT NOT NULL,
                    retrieved_chunk_ids_json TEXT NOT NULL DEFAULT '[]',
                    answer_preview TEXT,
                    created_at TEXT NOT NULL
                )
            """))

            # Generic audit_logs table — used by backend/services/audit_log_service.py
            # for row-level mutations (e.g. delete_assignment). Postgres prod has
            # this via Supabase migrations; create on SQLite dev too so audit is
            # never silently dropped in local testing.
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    old_value_json TEXT,
                    new_value_json TEXT,
                    actor_type TEXT NOT NULL DEFAULT 'system',
                    actor_id TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_audit_logs_entity
                ON audit_logs (entity_type, entity_id, created_at DESC)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_canonical_policy_query_audit_logs_company
                ON canonical_policy_query_audit_logs(company_id)
            """))

            # Per-case Services-flow state (selected services + answers + recommendations
            # + shortlist + display currency). Postgres has this via supabase migration
            # 20260427110000_services_state.sql; mirror on SQLite for local dev.
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS services_state (
                    case_id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_by_user_id TEXT
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_services_state_org
                ON services_state (organization_id)
            """))

            # Master catalog of service vendors per (category, city/country).
            # Phase 2a of the recommendations catalog routine. Postgres has
            # this via supabase migration 20260427120000_service_catalog_items.sql;
            # mirror on SQLite for local dev so the admin endpoints + the
            # JSON->DB backfill script work without Supabase.
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS service_catalog_items (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    city TEXT,
                    country TEXT,
                    name TEXT NOT NULL,
                    attributes_json TEXT NOT NULL DEFAULT '{}',
                    source TEXT NOT NULL DEFAULT 'manual',
                    active INTEGER NOT NULL DEFAULT 1,
                    external_id TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    created_by_user_id TEXT,
                    UNIQUE (category, external_id)
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_service_catalog_items_cat_city
                ON service_catalog_items (category, city)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_service_catalog_items_cat_country
                ON service_catalog_items (category, country)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_service_catalog_items_source
                ON service_catalog_items (source)
            """))

            # HR per-company curation (Phase 2d). Postgres has this via
            # supabase migration 20260427130000_company_vendor_selections.sql.
            # SQLite mirror; FK to service_catalog_items is informational
            # only here (SQLite doesn't enforce by default).
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS company_vendor_selections (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    destination_city TEXT,
                    country TEXT,
                    master_item_id TEXT,
                    custom_item_json TEXT,
                    selected INTEGER NOT NULL DEFAULT 1,
                    display_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    created_by_user_id TEXT,
                    UNIQUE (company_id, category, destination_city, master_item_id),
                    CHECK (
                        (master_item_id IS NOT NULL AND custom_item_json IS NULL)
                        OR (master_item_id IS NULL AND custom_item_json IS NOT NULL)
                    )
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_cvs_company_cat_city
                ON company_vendor_selections (company_id, category, destination_city)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_cvs_master_item
                ON company_vendor_selections (master_item_id)
            """))

            # Catalog scraper safety net (Phase 2b-secured). Postgres mirrors:
            # supabase migration 20260427140000_catalog_scrape_safety.sql.
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS catalog_destination_allowlist (
                    city TEXT NOT NULL,
                    country TEXT NOT NULL,
                    approved_by TEXT,
                    approved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT,
                    PRIMARY KEY (city, country)
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS catalog_scrape_quota (
                    company_id TEXT NOT NULL,
                    day TEXT NOT NULL,
                    calls_made INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (company_id, day)
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS catalog_destination_requests (
                    id TEXT PRIMARY KEY,
                    city TEXT NOT NULL,
                    country TEXT NOT NULL,
                    category TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    company_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    resolved_by TEXT,
                    resolved_at TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_cdr_status
                ON catalog_destination_requests (status, created_at DESC)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_cdr_company
                ON catalog_destination_requests (company_id, created_at DESC)
            """))

            # Case messages — employee/HR messaging thread per case (WZ5 / B19).
            # Postgres has this via supabase migration 20260524110000_case_messages.sql.
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS case_messages (
                    id          TEXT NOT NULL PRIMARY KEY,
                    case_id     TEXT NOT NULL,
                    sender_id   TEXT NOT NULL,
                    sender_role TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_case_messages_case_id
                ON case_messages (case_id, created_at DESC)
            """))

            # Employee demand signal (Phase 2 notifications). Postgres has this
            # via supabase migration 20260427150000_catalog_employee_demand.sql.
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS catalog_employee_demand (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    destination_city TEXT,
                    destination_country TEXT,
                    last_seen_by_user_id TEXT,
                    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    demand_count INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (company_id, category, destination_city)
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_ced_company
                ON catalog_employee_demand (company_id, last_seen_at DESC)
            """))

            # Policy Assistant RAG chunks (Sprint A). Postgres has this via
            # supabase migration 20260503100000_policy_assistant_chunks.sql
            # with pgvector. SQLite has no pgvector so we store the
            # embedding as a JSON-encoded TEXT array — services/
            # policy_chunk_retriever.py falls back to in-Python cosine
            # similarity when running on SQLite.
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_assistant_chunks (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    policy_version_id TEXT,
                    source_type TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    chunk_text TEXT NOT NULL,
                    chunk_metadata TEXT NOT NULL DEFAULT '{}',
                    embedding TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (company_id, source_type, source_ref)
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_pac_company_sqlite
                ON policy_assistant_chunks (company_id)
            """))

            # Exception requests — P2/P3 immigration-flag schema (supersedes old
            # budget-exception schema; Postgres uses migration 20260427100000_*.sql).
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS exception_requests (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    assignment_id TEXT,
                    exception_type TEXT NOT NULL,
                    reason TEXT,
                    severity TEXT NOT NULL DEFAULT 'warning'
                      CHECK (severity IN ('warning','blocker')),
                    status TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending','approved','denied','escalated','withdrawn')),
                    recommended_action TEXT,
                    resolved_at TEXT,
                    resolved_by TEXT,
                    resolution_notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))
            # Migrate any old budget-exception tables that are missing the new columns
            # AUDIT-A1: savepoint per column — on Postgres the column already exists
            # (added by `_maybe_ensure_postgres_*` helpers), the bare ADD COLUMN fails,
            # and without a savepoint the caught error aborts the outer transaction.
            for _col, _dflt in [
                ("severity", "'warning'"),
                ("exception_type", "''"),
                ("assignment_id", "NULL"),
                ("recommended_action", "NULL"),
                ("resolved_by", "NULL"),
                ("resolution_notes", "NULL"),
            ]:
                try:
                    with conn.begin_nested():
                        conn.execute(text(
                            f"ALTER TABLE exception_requests ADD COLUMN {_col} TEXT NOT NULL DEFAULT {_dflt}"
                            if _dflt not in ("NULL",) else
                            f"ALTER TABLE exception_requests ADD COLUMN {_col} TEXT"
                        ))
                except Exception:
                    pass
            # AUDIT-A1: savepoint isolates the failing DDL so a caught error
            # doesn't abort the outer Postgres transaction (SQLite was tolerant
            # of caught errors mid-transaction; Postgres isn't).
            try:
                with conn.begin_nested():
                    conn.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_exception_requests_case
                        ON exception_requests (case_id, created_at DESC)
                    """))
            except Exception:
                pass
            try:
                # organization_id only exists in the older budget-exceptions schema;
                # the P2/P3 immigration-flags schema does not have it — skip safely.
                with conn.begin_nested():
                    conn.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_exception_requests_org_status
                        ON exception_requests (organization_id, status, created_at DESC)
                    """))
            except Exception:
                pass
            # policy_cap_requests: employee-initiated cost override requests (B18 fix).
            # Separate from exception_requests (immigration/compliance flags).
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_cap_requests (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    organization_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    requested_amount REAL NOT NULL,
                    cap_amount REAL NOT NULL,
                    currency TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','approved','rejected','countered')),
                    hr_note TEXT,
                    counter_amount REAL,
                    requested_by_user_id TEXT NOT NULL,
                    resolved_by_user_id TEXT,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    updated_at TEXT NOT NULL
                )
            """))
            # employee_cap_overrides: per-employee policy cap overrides written on
            # exception approval or counter (P3-3). Base policy caps are never modified;
            # overrides are scoped per-employee per-category.
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS employee_cap_overrides (
                    id TEXT PRIMARY KEY,
                    employee_id TEXT NOT NULL,
                    company_id TEXT NOT NULL,
                    category_code TEXT NOT NULL,
                    approved_cap REAL NOT NULL,
                    currency TEXT NOT NULL,
                    approved_by TEXT NOT NULL,
                    approved_at TEXT NOT NULL,
                    expiry_date TEXT,
                    exception_id TEXT
                )
            """))
            # AUDIT-A1: savepoint per index so a column-mismatch failure on Postgres
            # doesn't abort the outer transaction.
            try:
                with conn.begin_nested():
                    conn.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_policy_cap_requests_case
                        ON policy_cap_requests (case_id, created_at DESC)
                    """))
            except Exception:
                pass
            try:
                with conn.begin_nested():
                    conn.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_policy_cap_requests_org_status
                        ON policy_cap_requests (organization_id, status, created_at DESC)
                    """))
            except Exception:
                pass

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS company_policy_assistant_bindings (
                    company_id TEXT PRIMARY KEY,
                    active_snapshot_id TEXT,
                    policy_document_id TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (active_snapshot_id) REFERENCES policy_knowledge_snapshots(id) ON DELETE SET NULL,
                    FOREIGN KEY (policy_document_id) REFERENCES policy_documents(id) ON DELETE SET NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_extraction_locks (
                    id TEXT PRIMARY KEY,
                    policy_document_id TEXT NOT NULL UNIQUE,
                    company_id TEXT NOT NULL,
                    locked_by_user_id TEXT NOT NULL,
                    lock_token TEXT NOT NULL,
                    acquired_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    metadata_json TEXT,
                    FOREIGN KEY (policy_document_id) REFERENCES policy_documents(id) ON DELETE CASCADE
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_assistant_answer_audits (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    case_id TEXT,
                    asked_by_user_id TEXT NOT NULL,
                    question_session_id TEXT,
                    policy_document_id TEXT,
                    snapshot_id TEXT,
                    extraction_run_id TEXT,
                    question_text TEXT NOT NULL,
                    normalized_question_topic TEXT,
                    answer_text TEXT NOT NULL,
                    evidence_status TEXT NOT NULL,
                    fact_ids_json TEXT NOT NULL DEFAULT '[]',
                    chunk_ids_json TEXT NOT NULL DEFAULT '[]',
                    applicability_decision_json TEXT NOT NULL DEFAULT '{}',
                    ambiguity_flags_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (policy_document_id) REFERENCES policy_documents(id) ON DELETE SET NULL,
                    FOREIGN KEY (snapshot_id) REFERENCES policy_knowledge_snapshots(id) ON DELETE SET NULL,
                    FOREIGN KEY (extraction_run_id) REFERENCES policy_processing_runs(id) ON DELETE SET NULL
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_policy_answer_audits_company
                ON policy_assistant_answer_audits(company_id, created_at)
            """))
            # [P5-8] AI trace table — one row per answer_policy_question() call.
            # Raw query text is never stored here; only the anonymised query_hash.
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_assistant_traces (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    query_hash TEXT NOT NULL,
                    company_id TEXT NOT NULL,
                    steps_json TEXT NOT NULL DEFAULT '[]',
                    total_latency_ms INTEGER NOT NULL DEFAULT 0,
                    fallback_triggered INTEGER NOT NULL DEFAULT 0,
                    co2e_grams_estimated REAL,
                    cost_usd_estimated REAL,
                    tokens_in INTEGER,
                    tokens_out INTEGER,
                    customer_id TEXT,
                    feature_key TEXT,
                    prompt_version_id TEXT,
                    canary_arm TEXT,
                    cited_chunk_ids TEXT NOT NULL DEFAULT '[]',
                    answer_kind TEXT,
                    grounding_verdict TEXT,
                    verification_skipped INTEGER,
                    grounding_score REAL,
                    created_at TEXT NOT NULL
                )
            """))
            # Parker Step G: carbon + customer/feature attribution columns. Idempotent
            # additive backfill for traces tables created before unit economics landed.
            _pat_g_cols = (
                ("co2e_grams_estimated", "REAL", "NUMERIC"),
                ("cost_usd_estimated", "REAL", "NUMERIC"),
                ("tokens_in", "INTEGER", "INTEGER"),
                ("tokens_out", "INTEGER", "INTEGER"),
                ("customer_id", "TEXT", "TEXT"),
                ("feature_key", "TEXT", "TEXT"),
                # W3/AIQ-837: cited chunk ids (jsonb in pg, JSON-text in sqlite).
                ("cited_chunk_ids", "TEXT", "JSONB"),
            )
            if _is_sqlite:
                try:
                    _patg = conn.execute(text("PRAGMA table_info(policy_assistant_traces)")).fetchall()
                    _patg_names = {r[1] for r in _patg}
                    for _col, _sqlite_t, _pg_t in _pat_g_cols:
                        if _col not in _patg_names:
                            conn.execute(text(
                                f"ALTER TABLE policy_assistant_traces ADD COLUMN {_col} {_sqlite_t}"
                            ))
                except Exception:
                    pass
            else:
                for _col, _sqlite_t, _pg_t in _pat_g_cols:
                    conn.execute(text(
                        f"ALTER TABLE policy_assistant_traces ADD COLUMN IF NOT EXISTS {_col} {_pg_t}"
                    ))
            # Parker Step D: prompt attribution columns. Idempotent additive
            # backfill for traces tables created before the registry landed.
            if _is_sqlite:
                try:
                    _pat_cols = conn.execute(text("PRAGMA table_info(policy_assistant_traces)")).fetchall()
                    _pat_names = {r[1] for r in _pat_cols}
                    if "prompt_version_id" not in _pat_names:
                        conn.execute(text("ALTER TABLE policy_assistant_traces ADD COLUMN prompt_version_id TEXT"))
                    if "canary_arm" not in _pat_names:
                        conn.execute(text("ALTER TABLE policy_assistant_traces ADD COLUMN canary_arm TEXT"))
                except Exception:
                    pass
            else:
                conn.execute(text("ALTER TABLE policy_assistant_traces ADD COLUMN IF NOT EXISTS prompt_version_id TEXT"))
                conn.execute(text("ALTER TABLE policy_assistant_traces ADD COLUMN IF NOT EXISTS canary_arm TEXT"))
            # W2-5 provenance columns. Idempotent additive backfill for traces
            # tables created before answer-provenance instrumentation landed.
            _pat_w25_cols = (
                ("answer_kind", "TEXT", "TEXT"),
                ("grounding_verdict", "TEXT", "TEXT"),
                ("verification_skipped", "INTEGER", "BOOLEAN"),
                ("grounding_score", "REAL", "NUMERIC"),
            )
            if _is_sqlite:
                try:
                    _patw = conn.execute(text("PRAGMA table_info(policy_assistant_traces)")).fetchall()
                    _patw_names = {r[1] for r in _patw}
                    for _col, _sqlite_t, _pg_t in _pat_w25_cols:
                        if _col not in _patw_names:
                            conn.execute(text(
                                f"ALTER TABLE policy_assistant_traces ADD COLUMN {_col} {_sqlite_t}"
                            ))
                except Exception:
                    pass
            else:
                for _col, _sqlite_t, _pg_t in _pat_w25_cols:
                    conn.execute(text(
                        f"ALTER TABLE policy_assistant_traces ADD COLUMN IF NOT EXISTS {_col} {_pg_t}"
                    ))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_pa_traces_company_created
                ON policy_assistant_traces(company_id, created_at)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_pa_traces_session
                ON policy_assistant_traces(session_id)
                WHERE session_id IS NOT NULL
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_pa_traces_customer_feature_created
                ON policy_assistant_traces(customer_id, feature_key, created_at)
            """))
            # AUDIT-A1: SQLite-only helper. See note on _sqlite_ensure_policy_hardening_columns above.
            if _is_sqlite:
                _sqlite_ensure_policy_import_columns(conn)
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
                    updated_at TEXT NOT NULL,
                    normalization_draft_json TEXT
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
                CREATE TABLE IF NOT EXISTS policy_benefit_rule_hr_overrides (
                    id TEXT PRIMARY KEY,
                    policy_version_id TEXT NOT NULL,
                    benefit_rule_id TEXT NOT NULL,
                    service_visibility TEXT,
                    amount_value_override REAL,
                    amount_unit_override TEXT,
                    currency_override TEXT,
                    duration_quantity_json TEXT,
                    approval_required_override INTEGER,
                    hr_notes TEXT,
                    created_by TEXT,
                    updated_by TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(policy_version_id, benefit_rule_id)
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policy_benefit_rule_hr_override_audit (
                    id TEXT PRIMARY KEY,
                    override_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    previous_json TEXT,
                    new_json TEXT,
                    actor_id TEXT,
                    created_at TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_pbr_hr_overrides_version
                ON policy_benefit_rule_hr_overrides(policy_version_id)
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
            # AUDIT-A1: PRAGMA is SQLite-only and was aborting the Postgres transaction.
            if _is_sqlite:
                try:
                    pv_cols = conn.execute(text("PRAGMA table_info(policy_versions)")).fetchall()
                    pv_names = {r[1] for r in pv_cols}
                    if "normalization_draft_json" not in pv_names:
                        conn.execute(text("ALTER TABLE policy_versions ADD COLUMN normalization_draft_json TEXT"))
                    if "normalization_state" not in pv_names:
                        conn.execute(text("ALTER TABLE policy_versions ADD COLUMN normalization_state TEXT"))
                except Exception:
                    pass
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_policy_benefit_rules_version ON policy_benefit_rules(policy_version_id)
            """))
            # Policy template source columns (company_policies) + default_policy_templates
            # AUDIT-A1: PRAGMA + default_policy_templates seeding are SQLite-only;
            # they were aborting the Postgres transaction. Postgres has the equivalent
            # in supabase/migrations.
            if _is_sqlite:
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
            # AUDIT-A1: PRAGMA is SQLite-only and was aborting the Postgres transaction.
            if _is_sqlite:
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
            # AUDIT-A1: PRAGMA is SQLite-only and was aborting the Postgres transaction.
            if _is_sqlite:
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
            # AUDIT-A1: PRAGMA is SQLite-only and was aborting the Postgres transaction.
            if _is_sqlite:
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
            # AUDIT-A1: PRAGMA is SQLite-only and was aborting the Postgres transaction.
            if _is_sqlite:
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
            # P2/P3: exception_requests (HR sign-off flags)
            if _is_sqlite:
                try:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS exception_requests (
                            id TEXT PRIMARY KEY,
                            case_id TEXT NOT NULL,
                            assignment_id TEXT,
                            exception_type TEXT NOT NULL,
                            reason TEXT,
                            severity TEXT NOT NULL DEFAULT 'warning'
                              CHECK (severity IN ('warning','blocker')),
                            status TEXT NOT NULL DEFAULT 'pending'
                              CHECK (status IN ('pending','approved','denied','escalated','withdrawn')),
                            recommended_action TEXT,
                            resolved_at TEXT,
                            resolved_by TEXT,
                            resolution_notes TEXT,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        )
                    """))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_exception_requests_case ON exception_requests(case_id)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_exception_requests_status ON exception_requests(status) WHERE status IN ('pending','escalated')"))
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

        # Hot-path indexes depend on tables + archived_at column existing.
        # Safe to run here unconditionally — idempotent via IF NOT EXISTS.
        self._maybe_ensure_hot_path_indexes()

        try:
            self.seed_readiness_templates_if_empty()
        except Exception as e:
            log.warning("readiness template seed skipped: %s", e)

        try:
            self.ensure_missing_readiness_templates()
        except Exception as e:
            log.warning("readiness template top-up skipped: %s", e)

        try:
            self.seed_dossier_questions_if_missing()
        except Exception as e:
            log.warning("dossier questions seed skipped: %s", e)

        try:
            self._backfill_employee_contacts()
        except Exception as e:
            log.warning("employee_contacts backfill skipped: %s", e)

    @staticmethod
    def _row_to_dict(row: Any) -> Optional[Dict[str, Any]]:
        if row is None:
            return None
        # PostgreSQL/psycopg2 returns UUID columns as Python uuid.UUID objects.
        # Pydantic v2 models typed as str reject uuid.UUID inputs, causing 500s
        # on production (Supabase Postgres) that never appear on SQLite dev.
        # Coerce all uuid.UUID values to str so callers always get plain strings.
        import uuid as _uuid
        return {
            k: str(v) if isinstance(v, _uuid.UUID) else v
            for k, v in row._mapping.items()
        }

    @staticmethod
    def _rows_to_list(rows: Any) -> List[Dict[str, Any]]:
        import uuid as _uuid
        return [
            {k: str(v) if isinstance(v, _uuid.UUID) else v for k, v in r._mapping.items()}
            for r in rows
        ]

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

    def _backfill_employee_contacts(self) -> None:
        """Attach employee_contact_id to legacy assignments (idempotent). Skips rows without case company_id."""
        from ..database import _relocation_cases_join_on  # lazy: avoid import cycle
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

    def set_case_employee_seniority(self, case_id: str, seniority_band: str) -> bool:
        """Merge an HR-set seniority band into the case profile_json at
        primaryApplicant.employer.seniorityBand, preserving all other fields.

        This is the level signal benefit comparison targets — extract_resolution_context
        reads it (policy_resolution.py). Read-modify-write; returns True on update.
        """
        band = (seniority_band or "").strip()
        rid = (case_id or "").strip()
        if not band or not rid:
            return False
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            row = conn.execute(
                text("SELECT profile_json FROM relocation_cases WHERE id::text = :cid"),
                {"cid": rid},
            ).fetchone()
            if not row:
                return False
            raw = row[0]
            try:
                profile = json.loads(raw) if isinstance(raw, str) else (raw or {})
            except Exception:
                profile = {}
            if not isinstance(profile, dict):
                profile = {}
            applicant = profile.setdefault("primaryApplicant", {})
            employer = applicant.setdefault("employer", {})
            employer["seniorityBand"] = band
            conn.execute(
                text("UPDATE relocation_cases SET profile_json = :pj, updated_at = :ua WHERE id::text = :cid"),
                {"pj": json.dumps(profile), "ua": now, "cid": rid},
            )
        return True

    def get_reconciliation_report(self) -> Dict[str, Any]:
        """Report for admin data reconciliation: entities and missing links. No destructive changes."""
        from ..database import _relocation_cases_join_on  # lazy: avoid import cycle
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

    def list_employees(self, company_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            if company_id:
                rows = conn.execute(text(
                    "SELECT * FROM employees WHERE company_id = :cid ORDER BY created_at DESC"
                ), {"cid": company_id}).fetchall()
            else:
                rows = conn.execute(text("SELECT * FROM employees ORDER BY created_at DESC")).fetchall()
        return self._rows_to_list(rows)

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

    def mark_conversation_read(self, assignment_id: str, recipient_user_id: str) -> int:
        """Set read_at and dismissed_at for all messages in this assignment to the recipient. Returns count updated."""
        from ..database import _eq_text  # lazy: avoid import cycle
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

    def list_admin_message_threads(
        self,
        company_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Admin: list message threads (assignment-based) with company/participant context."""
        from ..database import _eq_text, _relocation_cases_join_on  # lazy: avoid import cycle
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
            LEFT JOIN companies c ON CAST(c.id AS TEXT) = COALESCE(rc.company_id, hu.company_id)
            LEFT JOIN profiles emp_p ON CAST(emp_p.id AS TEXT) = a.employee_user_id
            LEFT JOIN profiles hr_p ON CAST(hr_p.id AS TEXT) = a.hr_user_id
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

    def get_data_integrity_overview(self) -> Dict[str, Any]:
        """
        Admin-safe summary of entity counts and orphan flags for data-integrity dashboard.
        """
        from ..database import _relocation_cases_join_on  # lazy: avoid import cycle
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

    def get_answer_provenance_rollup(
        self,
        *,
        company_id: str,
        since: Optional[str] = None,
        feature_key: str = "policy_assistant",
    ) -> Dict[str, Any]:
        """W2-5: per-company answer-provenance rollup over policy_assistant_traces.

        Aggregates the queryable provenance columns (answer_kind / grounding_verdict
        / verification_skipped) into counts + rates for the HR widget. Grounding
        only runs on real answers, so grounded_rate is denominated on answered (not
        total). Returns zeros (never raises) when the table/columns are absent.
        """
        zero = {
            "total": 0,
            "answers": 0,
            "refusals": 0,
            "grounded": 0,
            "partially_grounded": 0,
            "ungrounded": 0,
            "unverified": 0,
            "refusal_rate": 0.0,
            "grounded_rate": 0.0,
            "unverified_count": 0,
        }
        params: Dict[str, Any] = {"cid": company_id, "fk": feature_key}
        where = ["company_id = :cid", "feature_key = :fk"]
        if since:
            where.append("created_at >= :since")
            params["since"] = since
        sql = (
            "SELECT "
            "COUNT(*) AS total, "
            "SUM(CASE WHEN answer_kind = 'answer' THEN 1 ELSE 0 END) AS answers, "
            "SUM(CASE WHEN answer_kind LIKE 'refusal%' THEN 1 ELSE 0 END) AS refusals, "
            "SUM(CASE WHEN grounding_verdict = 'grounded' THEN 1 ELSE 0 END) AS grounded, "
            "SUM(CASE WHEN grounding_verdict = 'partially_grounded' THEN 1 ELSE 0 END) AS partially_grounded, "
            "SUM(CASE WHEN grounding_verdict = 'ungrounded' THEN 1 ELSE 0 END) AS ungrounded, "
            "SUM(CASE WHEN verification_skipped THEN 1 ELSE 0 END) AS unverified "
            "FROM policy_assistant_traces WHERE " + " AND ".join(where)
        )
        try:
            with self.engine.connect() as conn:
                row = conn.execute(text(sql), params).mappings().first()
        except Exception:
            return dict(zero)
        if not row:
            return dict(zero)
        total = int(row["total"] or 0)
        answers = int(row["answers"] or 0)
        refusals = int(row["refusals"] or 0)
        grounded = int(row["grounded"] or 0)
        unverified = int(row["unverified"] or 0)
        return {
            "total": total,
            "answers": answers,
            "refusals": refusals,
            "grounded": grounded,
            "partially_grounded": int(row["partially_grounded"] or 0),
            "ungrounded": int(row["ungrounded"] or 0),
            "unverified": unverified,
            "refusal_rate": round(refusals / total, 4) if total else 0.0,
            "grounded_rate": round(grounded / answers, 4) if answers else 0.0,
            "unverified_count": unverified,
        }

    def _parse_json_col(self, d: Dict[str, Any], key: str) -> None:
        if d.get(key) and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except Exception:
                d[key] = None

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
                "readiness_templates unavailable — apply migration 20260321000002_case_readiness_core.sql: %s",
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

    def ensure_missing_readiness_templates(self) -> None:
        """
        Idempotent top-up: insert any destination templates present in the JSON
        seed file that are not yet in the database.  Safe to call every startup —
        rows that already exist (matched on destination_key + route_key) are
        skipped via INSERT OR IGNORE / ON CONFLICT DO NOTHING.
        """
        if not self._readiness_store_available():
            return
        seed_path = os.path.join(os.path.dirname(__file__), "seed_data", "readiness_templates.json")
        if not os.path.isfile(seed_path):
            return
        with open(seed_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        templates = payload.get("templates") or []
        _is_sqlite = str(self.engine.url).startswith("sqlite")
        now = datetime.utcnow().isoformat()
        for t in templates:
            dest = (t.get("destination_key") or "").strip().upper()
            route = (t.get("route_key") or DEFAULT_ROUTE_KEY).strip() or DEFAULT_ROUTE_KEY
            if not dest:
                continue
            # Check if this destination+route already exists
            with self.engine.connect() as conn:
                existing = conn.execute(
                    text("SELECT id FROM readiness_templates WHERE destination_key = :dk AND route_key = :rk"),
                    {"dk": dest, "rk": route},
                ).fetchone()
            if existing:
                continue  # already seeded
            # Insert template + children
            tid = str(uuid.uuid4())
            watchouts = json.dumps(t.get("watchouts") or [])
            with self.engine.begin() as conn:
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
                    conn.execute(
                        text(
                            "INSERT INTO readiness_template_checklist_items "
                            "(id, template_id, sort_order, title, owner_role, required, depends_on_sort_order, "
                            "notes_employee, notes_hr, stable_key) "
                            "VALUES (:id, :tid, :so, :title, :own, :req, :dep, :ne, :nh, :sk)"
                        ),
                        {
                            "id": str(uuid.uuid4()),
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
                    conn.execute(
                        text(
                            "INSERT INTO readiness_template_milestones "
                            "(id, template_id, sort_order, phase, title, body_employee, body_hr, owner_role, relative_timing) "
                            "VALUES (:id, :tid, :so, :ph, :title, :be, :bh, :own, :rt)"
                        ),
                        {
                            "id": str(uuid.uuid4()),
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
            log.info("readiness template seeded: %s / %s", dest, route)

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

    @staticmethod
    def get_db_info() -> Dict[str, Any]:
        """Return non-secret info about the database connection."""
        from ..database import _engine  # lazy: avoid import cycle
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
