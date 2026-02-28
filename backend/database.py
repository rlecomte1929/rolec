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
from typing import Optional, Dict, Any, List
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from .db_config import DATABASE_URL as _raw_url

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine setup (shared logic with backend/app/db.py)
# ---------------------------------------------------------------------------
_connect_args: dict = {}
if _raw_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

_engine = create_engine(_raw_url, connect_args=_connect_args)

_is_sqlite = _raw_url.startswith("sqlite")


def _auto_id_col() -> str:
    """Return the DDL fragment for an auto-incrementing integer PK."""
    if _is_sqlite:
        return "INTEGER PRIMARY KEY AUTOINCREMENT"
    return "SERIAL PRIMARY KEY"


class Database:
    def __init__(self) -> None:
        self.engine = _engine
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

    # ------------------------------------------------------------------
    # Schema creation
    # ------------------------------------------------------------------
    def init_db(self) -> None:
        # In production (Render), avoid runtime DDL. Use Supabase migrations instead.
        if not _is_sqlite and os.getenv("DISABLE_RUNTIME_DDL", "").lower() in ("1", "true", "yes"):
            with self.engine.connect() as conn:
                self._db_healthcheck(conn)
            log.info("Runtime DDL disabled via DISABLE_RUNTIME_DDL. Skipping init_db DDL.")
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
                for col in ("legal_name", "website", "hq_city", "industry", "logo_url", "brand_color", "updated_at", "default_destination_country", "support_email", "default_working_location"):
                    cols = conn.execute(text("PRAGMA table_info(companies)")).fetchall()
                    col_names = {r[1] for r in cols}
                    if col not in col_names:
                        conn.execute(text(f"ALTER TABLE companies ADD COLUMN {col} TEXT"))
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
                for col in ("legal_name", "website", "hq_city", "industry", "logo_url", "brand_color", "updated_at", "default_destination_country", "support_email", "default_working_location"):
                    conn.execute(text(f"ALTER TABLE companies ADD COLUMN IF NOT EXISTS {col} TEXT"))
                conn.execute(text("ALTER TABLE relocation_cases ADD COLUMN IF NOT EXISTS company_id TEXT"))
                conn.execute(text("ALTER TABLE relocation_cases ADD COLUMN IF NOT EXISTS employee_id TEXT"))
                conn.execute(text("ALTER TABLE relocation_cases ADD COLUMN IF NOT EXISTS status TEXT"))
                conn.execute(text("ALTER TABLE relocation_cases ADD COLUMN IF NOT EXISTS stage TEXT"))
                conn.execute(text("ALTER TABLE relocation_cases ADD COLUMN IF NOT EXISTS host_country TEXT"))
                conn.execute(text("ALTER TABLE relocation_cases ADD COLUMN IF NOT EXISTS home_country TEXT"))

            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_profiles_email ON profiles(email)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_support_cases_status ON support_cases(status)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_support_cases_severity ON support_cases(severity)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_relocation_cases_status ON relocation_cases(status)"))

            # HR Command Center: risk/budget columns, tasks, case_events
            if _is_sqlite:
                cc_cols = [
                    ("case_assignments", "risk_status", "TEXT"),
                    ("case_assignments", "budget_limit", "REAL"),
                    ("case_assignments", "budget_estimated", "REAL"),
                    ("case_assignments", "expected_start_date", "TEXT"),
                ]
                for tbl, col, typ in cc_cols:
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
            except Exception:
                pass

        log.info("DB schema ensured (legacy tables) — %s",
                 _raw_url.split("@")[-1] if "@" in _raw_url else _raw_url)

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
    def create_case(self, case_id: str, hr_user_id: str, profile: Dict[str, Any]) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO relocation_cases (id, hr_user_id, profile_json, created_at, updated_at) "
                "VALUES (:id, :hr, :pj, :ca, :ua)"
            ), {"id": case_id, "hr": hr_user_id, "pj": json.dumps(profile), "ca": now, "ua": now})

    def get_case_by_id(self, case_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM relocation_cases WHERE id = :id"), {"id": case_id}).fetchone()
        return self._row_to_dict(row)

    def create_assignment(
        self,
        assignment_id: str,
        case_id: str,
        hr_user_id: str,
        employee_user_id: Optional[str],
        employee_identifier: str,
        status: str,
        request_id: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            self._exec(
                conn,
                "INSERT INTO case_assignments "
                "(id, case_id, hr_user_id, employee_user_id, employee_identifier, status, created_at, updated_at) "
                "VALUES (:id, :cid, :hr, :emp, :ident, :status, :ca, :ua)",
                {
                    "id": assignment_id,
                    "cid": case_id,
                    "hr": hr_user_id,
                    "emp": employee_user_id,
                    "ident": employee_identifier,
                    "status": status,
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
        with self.engine.begin() as conn:
            self._exec(
                conn,
                "UPDATE case_assignments SET employee_user_id = :emp, updated_at = :ua WHERE id = :id",
                {"emp": employee_user_id, "ua": datetime.utcnow().isoformat(), "id": assignment_id},
                op_name="attach_employee_to_assignment",
                request_id=request_id,
            )

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
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT * FROM case_assignments WHERE case_id = :cid",
                {"cid": case_id},
                op_name="get_assignment_by_case_id",
                request_id=request_id,
            ).fetchone()
        return self._row_to_dict(row)

    def get_assignment_for_employee(
        self,
        employee_user_id: str,
        request_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT * FROM case_assignments WHERE employee_user_id = :emp ORDER BY created_at DESC LIMIT 1",
                {"emp": employee_user_id},
                op_name="get_assignment_for_employee",
                request_id=request_id,
            ).fetchone()
        return self._row_to_dict(row)

    def get_unassigned_assignment_by_identifier(
        self,
        identifier: str,
        request_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT * FROM case_assignments "
                "WHERE employee_user_id IS NULL AND employee_identifier = :ident "
                "ORDER BY created_at DESC LIMIT 1",
                {"ident": identifier},
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
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM dossier_answers WHERE case_id = :cid AND user_id = :uid"
            ), {"cid": case_id, "uid": user_id}).fetchall()
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
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM dossier_case_questions WHERE case_id = :cid ORDER BY created_at ASC"
            ), {"cid": case_id}).fetchall()
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
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM dossier_case_answers WHERE case_id = :cid AND user_id = :uid"
            ), {"cid": case_id, "uid": user_id}).fetchall()
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
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM dossier_source_suggestions WHERE case_id = :cid ORDER BY created_at DESC"
            ), {"cid": case_id}).fetchall()
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
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT * FROM relocation_guidance_packs "
                "WHERE case_id = :cid AND user_id = :uid ORDER BY created_at DESC LIMIT 1"
            ), {"cid": case_id, "uid": user_id}).fetchone()
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
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM relocation_trace_events WHERE case_id = :cid "
                "ORDER BY created_at DESC LIMIT :lim"
            ), {"cid": case_id, "lim": limit}).fetchall()
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
    def get_command_center_kpis(self, hr_user_id: Optional[str] = None) -> Dict[str, Any]:
        """Aggregate KPIs. hr_user_id=None means admin (all cases)."""
        try:
            with self.engine.connect() as conn:
                where = "WHERE hr_user_id = :hr" if hr_user_id else ""
                params: Dict[str, Any] = {"hr": hr_user_id} if hr_user_id else {}
                base = f"SELECT * FROM case_assignments {where}"
                rows = conn.execute(text(f"{base} ORDER BY created_at DESC"), params).fetchall()
                assignments = self._rows_to_list(rows)
        except Exception:
            return {
                "activeCases": 0, "atRiskCount": 0, "attentionNeededCount": 0,
                "overdueTasksCount": 0, "avgVisaDurationDays": None, "budgetOverrunsCount": 0,
                "actionRequiredCount": 0, "departingSoonCount": 0, "completedCount": 0,
            }
        at_risk = sum(1 for a in assignments if (a.get("risk_status") or "green") == "red")
        attention = sum(1 for a in assignments if (a.get("risk_status") or "green") == "yellow")
        budget_overruns = 0
        action_required = 0
        departing_soon = 0
        completed = 0
        now = datetime.utcnow()

        def _parse_date(value: Optional[str]) -> Optional[datetime]:
            if not value:
                return None
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except Exception:
                return None

        def _days_until(target: datetime) -> int:
            diff = target - now
            return int(math.ceil(diff.total_seconds() / (60 * 60 * 24)))
        for a in assignments:
            bl, be = a.get("budget_limit"), a.get("budget_estimated")
            if bl is not None and be is not None and float(be or 0) > float(bl or 0):
                budget_overruns += 1

            status = a.get("status")
            created_at = _parse_date(a.get("created_at"))
            if status == "approved":
                if created_at is None or created_at.year == now.year:
                    completed += 1

            is_action_required = status == "submitted"
            try:
                report = self.get_latest_compliance_report(a["id"])
                checks = report.get("checks") if isinstance(report, dict) else None
                if checks and any((c.get("status") != "COMPLIANT") for c in checks if isinstance(c, dict)):
                    is_action_required = True
            except Exception:
                pass
            if is_action_required:
                action_required += 1

            try:
                profile = self.get_employee_profile(a["id"]) or {}
                move_plan = profile.get("movePlan") if isinstance(profile, dict) else {}
                target_date = _parse_date(move_plan.get("targetArrivalDate") if isinstance(move_plan, dict) else None)
                if target_date:
                    remaining = _days_until(target_date)
                    if 0 <= remaining <= 30:
                        departing_soon += 1
                else:
                    submitted_at = _parse_date(a.get("submitted_at"))
                    if submitted_at:
                        remaining = _days_until(submitted_at)
                        if 0 <= remaining <= 14:
                            departing_soon += 1
            except Exception:
                pass
        overdue = 0
        try:
            for a in assignments:
                with self.engine.connect() as conn:
                    r = conn.execute(text(
                        "SELECT COUNT(*) FROM relocation_tasks WHERE assignment_id = :aid AND status = 'overdue'"
                    ), {"aid": a["id"]}).fetchone()
                    overdue += (r[0] or 0)
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
        hr_user_id: Optional[str] = None,
        page: int = 1,
        limit: int = 25,
        risk_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Paginated cases with task % and risk. hr_user_id=None for admin."""
        try:
            with self.engine.connect() as conn:
                where = "WHERE ca.hr_user_id = :hr" if hr_user_id else "WHERE 1=1"
                params: Dict[str, Any] = {"limit": limit, "offset": (page - 1) * limit}
                if hr_user_id:
                    params["hr"] = hr_user_id
                if risk_filter:
                    where += " AND COALESCE(ca.risk_status, 'green') = :risk"
                    params["risk"] = risk_filter
                sql = f"""
                    SELECT ca.id, ca.employee_identifier, ca.status,
                           COALESCE(ca.risk_status, 'green') as risk_status,
                           ca.budget_limit, ca.budget_estimated, ca.expected_start_date,
                           rc.host_country as dest_country
                    FROM case_assignments ca
                    LEFT JOIN relocation_cases rc ON rc.id = ca.case_id
                    {where}
                    ORDER BY ca.updated_at DESC
                    LIMIT :limit OFFSET :offset
                """
                rows = conn.execute(text(sql), params).fetchall()
                result = []
                for row in rows:
                    m = row._mapping
                    a_id = m["id"]
                    tasks_done, tasks_total = 0, 0
                    next_due = None
                    try:
                        tr = conn.execute(text(
                            "SELECT status, due_date FROM relocation_tasks WHERE assignment_id = :aid"
                        ), {"aid": a_id}).fetchall()
                        tasks_total = len(tr)
                        tasks_done = sum(1 for r in tr if r._mapping.get("status") in ("done",))
                        overdues = [r._mapping.get("due_date") for r in tr if r._mapping.get("status") == "overdue" and r._mapping.get("due_date")]
                        next_due = min(overdues) if overdues else None
                    except Exception:
                        pass
                    pct = round(100 * tasks_done / tasks_total) if tasks_total else 0
                    result.append({
                        "id": a_id,
                        "employeeIdentifier": m.get("employee_identifier") or "",
                        "destCountry": m.get("dest_country"),
                        "status": m.get("status") or "",
                        "riskStatus": m.get("risk_status") or "green",
                        "tasksDonePercent": pct,
                        "budgetLimit": m.get("budget_limit"),
                        "budgetEstimated": m.get("budget_estimated"),
                        "nextDeadline": str(next_due) if next_due else None,
                    })
                return result
        except Exception as e:
            log.warning("list_command_center_cases: %s", e)
            return []

    def get_command_center_case_detail(
        self, assignment_id: str, hr_user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Full case detail: tasks, budget, events."""
        try:
            with self.engine.connect() as conn:
                where = "ca.id = :aid"
                params: Dict[str, Any] = {"aid": assignment_id}
                if hr_user_id:
                    where += " AND ca.hr_user_id = :hr"
                    params["hr"] = hr_user_id
                row = conn.execute(text(f"""
                    SELECT ca.*, rc.host_country as dest_country
                    FROM case_assignments ca
                    LEFT JOIN relocation_cases rc ON rc.id = ca.case_id
                    WHERE {where}
                """), params).fetchone()
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
            conn.execute(text("DELETE FROM assignment_invites WHERE case_id = :cid"), {"cid": case_id})
            conn.execute(text("DELETE FROM case_assignments WHERE id = :id"), {"id": assignment_id})
            conn.execute(text("DELETE FROM relocation_cases WHERE id = :cid"), {"cid": case_id})
        return True

    # ==================================================================
    # Assignment invites
    # ==================================================================
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

    def mark_invites_claimed(self, employee_identifier: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE assignment_invites SET status = 'CLAIMED' WHERE employee_identifier = :ident"
            ), {"ident": employee_identifier})

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
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE profiles SET company_id = :cid WHERE id = :id"
            ), {"cid": company_id, "id": user_id})

    def get_company_for_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        profile = self.get_profile_record(user_id)
        if not profile or not profile.get("company_id"):
            return None
        return self.get_company(profile["company_id"])

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
        now = datetime.utcnow().isoformat()
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

    def create_company(
        self,
        company_id: str,
        name: str,
        country: Optional[str],
        size_band: Optional[str],
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
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO companies (id, name, country, size_band, address, phone, hr_contact, created_at, "
                "legal_name, website, hq_city, industry, logo_url, brand_color, updated_at, "
                "default_destination_country, support_email, default_working_location) "
                "VALUES (:id, :name, :country, :size_band, :address, :phone, :hr_contact, :created_at, "
                ":legal_name, :website, :hq_city, :industry, :logo_url, :brand_color, :updated_at, "
                ":default_destination_country, :support_email, :default_working_location) "
                "ON CONFLICT(id) DO UPDATE SET "
                "name = excluded.name, country = excluded.country, size_band = excluded.size_band, "
                "address = excluded.address, phone = excluded.phone, hr_contact = excluded.hr_contact, "
                "legal_name = COALESCE(excluded.legal_name, companies.legal_name), "
                "website = COALESCE(excluded.website, companies.website), "
                "hq_city = COALESCE(excluded.hq_city, companies.hq_city), "
                "industry = COALESCE(excluded.industry, companies.industry), "
                "logo_url = COALESCE(excluded.logo_url, companies.logo_url), "
                "brand_color = COALESCE(excluded.brand_color, companies.brand_color), "
                "updated_at = excluded.updated_at, "
                "default_destination_country = COALESCE(excluded.default_destination_country, companies.default_destination_country), "
                "support_email = COALESCE(excluded.support_email, companies.support_email), "
                "default_working_location = COALESCE(excluded.default_working_location, companies.default_working_location)"
            ), {
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
            })

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
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO support_cases "
                "(id, company_id, created_by_profile_id, employee_id, hr_profile_id, category, severity, status, summary, last_error_code, last_error_context_json, created_at, updated_at) "
                "VALUES (:id, :cid, :cbp, :eid, :hid, :cat, :sev, :status, :summary, :err, :ctx, :created_at, :updated_at) "
                "ON CONFLICT(id) DO UPDATE SET company_id = excluded.company_id, status = excluded.status, summary = excluded.summary, "
                "last_error_code = excluded.last_error_code, last_error_context_json = excluded.last_error_context_json, updated_at = excluded.updated_at"
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

    def list_hr_users(self, company_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            if company_id:
                rows = conn.execute(text(
                    "SELECT * FROM hr_users WHERE company_id = :cid ORDER BY created_at DESC"
                ), {"cid": company_id}).fetchall()
            else:
                rows = conn.execute(text("SELECT * FROM hr_users ORDER BY created_at DESC")).fetchall()
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

    def list_support_cases(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        company_id: Optional[str] = None,
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
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                f"SELECT * FROM support_cases {where} ORDER BY updated_at DESC"
            ), params).fetchall()
        return self._rows_to_list(rows)

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
            rows = conn.execute(text(
                "SELECT * FROM messages WHERE hr_user_id = :hr ORDER BY created_at DESC"
            ), {"hr": hr_user_id}).fetchall()
        return self._rows_to_list(rows)

    def list_messages_for_employee(self, employee_user_id: str) -> List[Dict[str, Any]]:
        assignment = self.get_assignment_for_employee(employee_user_id)
        if not assignment:
            return []
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM messages WHERE assignment_id = :aid ORDER BY created_at DESC"
            ), {"aid": assignment["id"]}).fetchall()
        return self._rows_to_list(rows)

    def mark_conversation_read(self, assignment_id: str, recipient_user_id: str) -> int:
        """Set read_at and dismissed_at for all messages in this assignment to the recipient. Returns count updated."""
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            result = conn.execute(text(
                "UPDATE messages SET read_at = :now, dismissed_at = :now "
                "WHERE assignment_id = :aid AND recipient_user_id = :uid AND read_at IS NULL"
            ), {"now": now, "aid": assignment_id, "uid": recipient_user_id})
        return result.rowcount if hasattr(result, "rowcount") else 0

    def dismiss_message_notification(self, message_id: str, recipient_user_id: str) -> bool:
        """Set dismissed_at for one message. Returns True if updated."""
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            result = conn.execute(text(
                "UPDATE messages SET dismissed_at = :now "
                "WHERE id = :mid AND recipient_user_id = :uid AND dismissed_at IS NULL"
            ), {"now": now, "mid": message_id, "uid": recipient_user_id})
        return (result.rowcount if hasattr(result, "rowcount") else 0) > 0

    def get_unread_message_count(self, recipient_user_id: str) -> int:
        """Count messages where recipient hasn't read and hasn't dismissed."""
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT COUNT(*) as n FROM messages "
                "WHERE recipient_user_id = :uid AND read_at IS NULL AND dismissed_at IS NULL"
            ), {"uid": recipient_user_id}).fetchone()
        return row[0] if row else 0

    def list_unread_message_notifications(
        self, recipient_user_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """List unread, non-dismissed messages for the recipient with sender name and snippet."""
        with self.engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT m.id as message_id, m.assignment_id as conversation_id,
                       m.body, m.created_at,
                       COALESCE(u.name, u.email, u.username, 'HR') as sender_name
                FROM messages m
                LEFT JOIN users u ON u.id = COALESCE(m.sender_user_id, m.hr_user_id)
                WHERE m.recipient_user_id = :uid AND m.read_at IS NULL AND m.dismissed_at IS NULL
                ORDER BY m.created_at DESC
                LIMIT :lim
            """), {"uid": recipient_user_id, "lim": limit}).fetchall()
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


# Global database instance
db = Database()
