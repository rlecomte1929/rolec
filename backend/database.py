"""
Unified database layer — works with both SQLite and Postgres.
Uses DATABASE_URL from db_config (single source of truth).
"""
import json
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
