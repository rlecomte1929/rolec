"""
Unified database layer — works with both SQLite and Postgres.
Uses DATABASE_URL from db_config (single source of truth).
"""
import json
import uuid
import logging
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

    # ------------------------------------------------------------------
    # Schema creation
    # ------------------------------------------------------------------
    def init_db(self) -> None:
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

            # Best-effort schema extensions for relocation_cases
            if _is_sqlite:
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
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO case_assignments "
                "(id, case_id, hr_user_id, employee_user_id, employee_identifier, status, created_at, updated_at) "
                "VALUES (:id, :cid, :hr, :emp, :ident, :status, :ca, :ua)"
            ), {
                "id": assignment_id, "cid": case_id, "hr": hr_user_id,
                "emp": employee_user_id, "ident": employee_identifier,
                "status": status, "ca": now, "ua": now,
            })

    def update_assignment_status(self, assignment_id: str, status: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE case_assignments SET status = :status, updated_at = :ua WHERE id = :id"
            ), {"status": status, "ua": datetime.utcnow().isoformat(), "id": assignment_id})

    def update_assignment_identifier(self, assignment_id: str, employee_identifier: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE case_assignments SET employee_identifier = :ident, updated_at = :ua WHERE id = :id"
            ), {"ident": employee_identifier, "ua": datetime.utcnow().isoformat(), "id": assignment_id})

    def attach_employee_to_assignment(self, assignment_id: str, employee_user_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE case_assignments SET employee_user_id = :emp, updated_at = :ua WHERE id = :id"
            ), {"emp": employee_user_id, "ua": datetime.utcnow().isoformat(), "id": assignment_id})

    def set_assignment_submitted(self, assignment_id: str) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE case_assignments SET status = 'EMPLOYEE_SUBMITTED', submitted_at = :now, updated_at = :now WHERE id = :id"
            ), {"now": now, "id": assignment_id})

    def set_assignment_decision(self, assignment_id: str, decision: str, notes: Optional[str]) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE case_assignments SET status = :decision, decision = :decision, hr_notes = :notes, updated_at = :ua WHERE id = :id"
            ), {"decision": decision, "notes": notes, "ua": datetime.utcnow().isoformat(), "id": assignment_id})

    def get_assignment_by_id(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM case_assignments WHERE id = :id"), {"id": assignment_id}).fetchone()
        return self._row_to_dict(row)

    def get_assignment_by_case_id(self, case_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM case_assignments WHERE case_id = :cid"), {"cid": case_id}).fetchone()
        return self._row_to_dict(row)

    def get_assignment_for_employee(self, employee_user_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT * FROM case_assignments WHERE employee_user_id = :emp ORDER BY created_at DESC LIMIT 1"
            ), {"emp": employee_user_id}).fetchone()
        return self._row_to_dict(row)

    def get_unassigned_assignment_by_identifier(self, identifier: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT * FROM case_assignments "
                "WHERE employee_user_id IS NULL AND employee_identifier = :ident "
                "ORDER BY created_at DESC LIMIT 1"
            ), {"ident": identifier}).fetchone()
        return self._row_to_dict(row)

    def list_assignments_for_hr(self, hr_user_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM case_assignments WHERE hr_user_id = :hr ORDER BY created_at DESC"
            ), {"hr": hr_user_id}).fetchall()
        return self._rows_to_list(rows)

    def list_all_assignments(self) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text("SELECT * FROM case_assignments ORDER BY created_at DESC")).fetchall()
        return self._rows_to_list(rows)

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

    def create_company(self, company_id: str, name: str, country: Optional[str], size_band: Optional[str]) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO companies (id, name, country, size_band, created_at) "
                "VALUES (:id, :name, :country, :size_band, :created_at) "
                "ON CONFLICT(id) DO UPDATE SET name = excluded.name, country = excluded.country, size_band = excluded.size_band"
            ), {"id": company_id, "name": name, "country": country, "size_band": size_band, "created_at": now})

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
