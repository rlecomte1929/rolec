import sqlite3
import json
from typing import Optional, Dict, Any, List
from datetime import datetime


class Database:
    def __init__(self, db_path: str = "relopass.db"):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        self._ensure_users_table(conn)

        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Profile state table (legacy individual profile flow)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS profile_state (
                user_id TEXT PRIMARY KEY,
                profile_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Answers audit trail (legacy individual profile flow)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                answer_json TEXT NOT NULL,
                is_unknown INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Relocation cases (owned by HR)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relocation_cases (
                id TEXT PRIMARY KEY,
                hr_user_id TEXT NOT NULL,
                profile_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (hr_user_id) REFERENCES users(id)
            )
        """)

        # Case assignments
        cursor.execute("""
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
                FOREIGN KEY (case_id) REFERENCES relocation_cases(id),
                FOREIGN KEY (hr_user_id) REFERENCES users(id),
                FOREIGN KEY (employee_user_id) REFERENCES users(id)
            )
        """)

        # Assignment invites
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assignment_invites (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                hr_user_id TEXT NOT NULL,
                employee_identifier TEXT NOT NULL,
                token TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Employee answers
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employee_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignment_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                answer_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (assignment_id) REFERENCES case_assignments(id)
            )
        """)

        # Employee profile snapshots
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employee_profiles (
                assignment_id TEXT PRIMARY KEY,
                profile_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (assignment_id) REFERENCES case_assignments(id)
            )
        """)

        # Compliance reports
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS compliance_reports (
                id TEXT PRIMARY KEY,
                assignment_id TEXT NOT NULL,
                report_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (assignment_id) REFERENCES case_assignments(id)
            )
        """)

        # Compliance runs (HR workflow)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS compliance_runs (
                id TEXT PRIMARY KEY,
                assignment_id TEXT NOT NULL,
                report_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (assignment_id) REFERENCES case_assignments(id)
            )
        """)

        # Policy exception requests
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS policy_exceptions (
                id TEXT PRIMARY KEY,
                assignment_id TEXT NOT NULL,
                category TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT,
                requested_amount REAL,
                requested_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (assignment_id) REFERENCES case_assignments(id)
            )
        """)

        # Compliance action audit trail
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS compliance_actions (
                id TEXT PRIMARY KEY,
                assignment_id TEXT NOT NULL,
                check_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                notes TEXT,
                actor_user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (assignment_id) REFERENCES case_assignments(id)
            )
        """)

        conn.commit()
        conn.close()

    def _ensure_users_table(self, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        table_exists = cursor.fetchone() is not None

        if not table_exists:
            self._create_users_table(cursor)
            conn.commit()
            return

        cursor.execute("PRAGMA table_info(users)")
        columns = {row["name"]: row for row in cursor.fetchall()}
        needs_migration = False

        # We need nullable email/username and new auth fields
        if "username" not in columns or "password_hash" not in columns or "role" not in columns:
            needs_migration = True
        if "email" in columns and columns["email"]["notnull"] == 1:
            needs_migration = True

        if needs_migration:
            cursor.execute("ALTER TABLE users RENAME TO users_old")
            self._create_users_table(cursor)
            cursor.execute(
                """INSERT INTO users (id, email, created_at, role)
                   SELECT id, email, created_at, 'EMPLOYEE' FROM users_old"""
            )
            cursor.execute("DROP TABLE users_old")
            conn.commit()
            return

        # Ensure role defaults for existing rows
        cursor.execute("UPDATE users SET role = 'EMPLOYEE' WHERE role IS NULL")
        conn.commit()

    def _create_users_table(self, cursor: sqlite3.Cursor) -> None:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE,
                email TEXT UNIQUE,
                password_hash TEXT,
                role TEXT NOT NULL,
                name TEXT,
                created_at TEXT NOT NULL,
                CHECK (username IS NOT NULL OR email IS NOT NULL)
            )
        """)

    # User operations
    def create_user(
        self,
        user_id: str,
        username: Optional[str],
        email: Optional[str],
        password_hash: str,
        role: str,
        name: Optional[str],
    ) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO users (id, username, email, password_hash, role, name, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, username, email, password_hash, role, name, datetime.utcnow().isoformat())
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_user_by_identifier(self, identifier: str) -> Optional[Dict[str, Any]]:
        user = self.get_user_by_username(identifier)
        if user:
            return user
        return self.get_user_by_email(identifier)

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # Session operations
    def create_session(self, token: str, user_id: str) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user_id, datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()
        return True

    def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM sessions WHERE token = ?", (token,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return self.get_user_by_id(row["user_id"])

    # Profile operations (legacy)
    def save_profile(self, user_id: str, profile: Dict[str, Any]) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO profile_state (user_id, profile_json, updated_at)
               VALUES (?, ?, ?)""",
            (user_id, json.dumps(profile), datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()
        return True

    def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT profile_json FROM profile_state WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return json.loads(row["profile_json"]) if row else None

    # Answer operations (legacy)
    def save_answer(self, user_id: str, question_id: str, answer: Any, is_unknown: bool = False) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO answers (user_id, question_id, answer_json, is_unknown, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, question_id, json.dumps(answer), 1 if is_unknown else 0, datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()
        return True

    def get_answers(self, user_id: str) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT question_id, answer_json, is_unknown FROM answers WHERE user_id = ? ORDER BY created_at",
            (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # HR cases and assignments
    def create_case(self, case_id: str, hr_user_id: str, profile: Dict[str, Any]) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO relocation_cases (id, hr_user_id, profile_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (case_id, hr_user_id, json.dumps(profile), datetime.utcnow().isoformat(), datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()

    def get_case_by_id(self, case_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM relocation_cases WHERE id = ?", (case_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def create_assignment(
        self,
        assignment_id: str,
        case_id: str,
        hr_user_id: str,
        employee_user_id: Optional[str],
        employee_identifier: str,
        status: str,
    ) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO case_assignments
               (id, case_id, hr_user_id, employee_user_id, employee_identifier, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                assignment_id,
                case_id,
                hr_user_id,
                employee_user_id,
                employee_identifier,
                status,
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat(),
            )
        )
        conn.commit()
        conn.close()

    def update_assignment_status(self, assignment_id: str, status: str) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE case_assignments SET status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.utcnow().isoformat(), assignment_id)
        )
        conn.commit()
        conn.close()

    def update_assignment_identifier(self, assignment_id: str, employee_identifier: str) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE case_assignments
               SET employee_identifier = ?, updated_at = ?
               WHERE id = ?""",
            (employee_identifier, datetime.utcnow().isoformat(), assignment_id)
        )
        conn.commit()
        conn.close()

    def attach_employee_to_assignment(self, assignment_id: str, employee_user_id: str) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE case_assignments
               SET employee_user_id = ?, updated_at = ?
               WHERE id = ?""",
            (employee_user_id, datetime.utcnow().isoformat(), assignment_id)
        )
        conn.commit()
        conn.close()

    def set_assignment_submitted(self, assignment_id: str) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE case_assignments
               SET status = ?, submitted_at = ?, updated_at = ?
               WHERE id = ?""",
            ("EMPLOYEE_SUBMITTED", datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), assignment_id)
        )
        conn.commit()
        conn.close()

    def set_assignment_decision(self, assignment_id: str, decision: str, notes: Optional[str]) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE case_assignments
               SET status = ?, decision = ?, hr_notes = ?, updated_at = ?
               WHERE id = ?""",
            (decision, decision, notes, datetime.utcnow().isoformat(), assignment_id)
        )
        conn.commit()
        conn.close()

    def get_assignment_by_id(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM case_assignments WHERE id = ?", (assignment_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_assignment_for_employee(self, employee_user_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM case_assignments
               WHERE employee_user_id = ?
               ORDER BY created_at DESC
               LIMIT 1""",
            (employee_user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_unassigned_assignment_by_identifier(self, identifier: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM case_assignments
               WHERE employee_user_id IS NULL AND employee_identifier = ?
               ORDER BY created_at DESC
               LIMIT 1""",
            (identifier,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_assignments_for_hr(self, hr_user_id: str) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM case_assignments
               WHERE hr_user_id = ?
               ORDER BY created_at DESC""",
            (hr_user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def list_all_assignments(self) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM case_assignments
               ORDER BY created_at DESC"""
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def create_assignment_invite(
        self,
        invite_id: str,
        case_id: str,
        hr_user_id: str,
        employee_identifier: str,
        token: str,
    ) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO assignment_invites
               (id, case_id, hr_user_id, employee_identifier, token, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (invite_id, case_id, hr_user_id, employee_identifier, token, "ACTIVE", datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()

    def mark_invites_claimed(self, employee_identifier: str) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE assignment_invites
               SET status = 'CLAIMED'
               WHERE employee_identifier = ?""",
            (employee_identifier,)
        )
        conn.commit()
        conn.close()

    # Employee journey data
    def save_employee_answer(self, assignment_id: str, question_id: str, answer: Any) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO employee_answers (assignment_id, question_id, answer_json, created_at)
               VALUES (?, ?, ?, ?)""",
            (assignment_id, question_id, json.dumps(answer), datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()

    def get_employee_answers(self, assignment_id: str) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT question_id, answer_json
               FROM employee_answers
               WHERE assignment_id = ?
               ORDER BY created_at""",
            (assignment_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def save_employee_profile(self, assignment_id: str, profile: Dict[str, Any]) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO employee_profiles (assignment_id, profile_json, updated_at)
               VALUES (?, ?, ?)""",
            (assignment_id, json.dumps(profile), datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()

    def get_employee_profile(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT profile_json FROM employee_profiles WHERE assignment_id = ?",
            (assignment_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return json.loads(row["profile_json"]) if row else None

    # Compliance reports
    def save_compliance_report(self, report_id: str, assignment_id: str, report: Dict[str, Any]) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO compliance_reports (id, assignment_id, report_json, created_at)
               VALUES (?, ?, ?, ?)""",
            (report_id, assignment_id, json.dumps(report), datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()

    def get_latest_compliance_report(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT report_json FROM compliance_reports
               WHERE assignment_id = ?
               ORDER BY created_at DESC
               LIMIT 1""",
            (assignment_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return json.loads(row["report_json"]) if row else None

    def save_compliance_run(self, run_id: str, assignment_id: str, report: Dict[str, Any]) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO compliance_runs (id, assignment_id, report_json, created_at) VALUES (?, ?, ?, ?)",
            (run_id, assignment_id, json.dumps(report), datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()

    def get_latest_compliance_run(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT report_json, created_at FROM compliance_runs WHERE assignment_id = ? ORDER BY created_at DESC LIMIT 1",
            (assignment_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        report = json.loads(row["report_json"])
        report["lastVerified"] = row["created_at"]
        return report

    def list_policy_exceptions(self, assignment_id: str) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM policy_exceptions WHERE assignment_id = ? ORDER BY created_at DESC",
            (assignment_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

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
        conn = self.get_connection()
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat()
        cursor.execute(
            """INSERT INTO policy_exceptions
               (id, assignment_id, category, status, reason, requested_amount, requested_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (exception_id, assignment_id, category, status, reason, requested_amount, requested_by, now, now)
        )
        conn.commit()
        conn.close()

    def create_compliance_action(
        self,
        action_id: str,
        assignment_id: str,
        check_id: str,
        action_type: str,
        notes: Optional[str],
        actor_user_id: str,
    ) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO compliance_actions
               (id, assignment_id, check_id, action_type, notes, actor_user_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (action_id, assignment_id, check_id, action_type, notes, actor_user_id, datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()

    def list_compliance_actions(self, assignment_id: str) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM compliance_actions WHERE assignment_id = ? ORDER BY created_at DESC",
            (assignment_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]


# Global database instance
db = Database()
