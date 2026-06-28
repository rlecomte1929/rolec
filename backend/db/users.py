"""[AUDIT-C1.4] Users/profile-domain DB methods, extracted from backend/database.py.

User records, profiles, HR-user provisioning, the admin allowlist, and
assignment-invite helpers. These were methods on the monolithic ``Database``
class; they live here as a mixin (:class:`UsersMixin`) that ``Database``
inherits, so every caller (``db.create_user(...)`` etc.) keeps working
unchanged via normal MRO. Sibling calls (``self._exec``, ``self._row_to_dict``,
``self.create_employee``) resolve on the composed ``Database`` instance.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from ..identity_normalize import normalize_invite_key
from ..identity_observability import identity_event

from ..db_config import DATABASE_URL as _raw_url

log = logging.getLogger(__name__)

_is_sqlite = _raw_url.startswith("sqlite")

# Frozen False constant in backend/database.py (line 268): prod Postgres has
# no profiles.status column. Imported (not redefined) to keep one source of
# truth; defined there before the mixin imports, so this is cycle-safe.
from ..database import _profiles_has_status_column


class UsersMixin:
    """Users/profile-domain methods mixed into :class:`backend.database.Database`."""

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
        # AIQ-1347: match case-insensitively to mirror get_user_by_email (username
        # was previously case-SENSITIVE, so 'JohnDoe' registered + 'johndoe' typed
        # failed login). The exact-case-first tie-break keeps the result
        # deterministic if a future 'John'/'john' pair ever coexists (username's
        # UNIQUE constraint is case-sensitive), so no duplicate-match ambiguity.
        username_norm = (username or "").strip()
        if not username_norm:
            return None
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT * FROM users WHERE LOWER(TRIM(username)) = :u_lower "
                    "ORDER BY CASE WHEN TRIM(username) = :u_exact THEN 0 ELSE 1 END "
                    "LIMIT 1"
                ),
                {"u_lower": username_norm.lower(), "u_exact": username_norm},
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

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id}).fetchone()
        return self._row_to_dict(row)

    def get_user_roles(self, user_id: str) -> List[Dict[str, Any]]:
        """[AIQ-1353] Return the user's roles from public.user_roles as
        ``[{'role': str, 'is_primary': bool}, ...]``. Returns ``[]`` when the
        junction table is absent (pre-migration / SQLite) or the user has no rows;
        callers fall back to the legacy ``users.role``. Never raises."""
        uid = (user_id or "").strip()
        if not uid:
            return []
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(
                    text("SELECT role, is_primary FROM user_roles WHERE user_id = :uid"),
                    {"uid": uid},
                ).fetchall()
        except Exception:
            return []
        return [
            {"role": r._mapping["role"], "is_primary": bool(r._mapping["is_primary"])}
            for r in rows
        ]

    def set_primary_role(self, user_id: str, role: str) -> None:
        """[AIQ-1355] Make ``role`` the user's single primary role (all others
        non-primary) in one statement. Caller must validate ``role`` is held."""
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE user_roles SET is_primary = (role = :role) WHERE user_id = :uid"),
                {"role": role, "uid": user_id},
            )

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

    def _resolve_employee_profile_id(self, assignment: Dict[str, Any]) -> Optional[str]:
        """Resolve the employee's ``profiles.id`` for ``public.cases.employee_id``
        (an FK to ``profiles``), from a case_assignments row.

        Order: (1) ``employee_user_id`` if it is itself a profile id (uuid-native
        employees — the common case); (2) the employee's email (``users.email`` ->
        ``profiles.email``); (3) ``employee_contact_id`` if that happens to be a
        profile. Returns None if no profile can be resolved (the bridge then skips).
        """
        uid = str(assignment.get("employee_user_id") or "").strip()
        cid = str(assignment.get("employee_contact_id") or "").strip()
        try:
            with self.engine.connect() as conn:
                if uid:
                    r = conn.execute(
                        text("SELECT id FROM profiles WHERE CAST(id AS TEXT) = :u LIMIT 1"),
                        {"u": uid},
                    ).first()
                    if r:
                        return uid
                    r = conn.execute(
                        text(
                            "SELECT CAST(p.id AS TEXT) AS pid FROM users u "
                            "JOIN profiles p ON lower(p.email) = lower(u.email) "
                            "WHERE u.id = :u LIMIT 1"
                        ),
                        {"u": uid},
                    ).mappings().first()
                    if r and r.get("pid"):
                        return r["pid"]
                if cid:
                    r = conn.execute(
                        text("SELECT id FROM profiles WHERE CAST(id AS TEXT) = :c LIMIT 1"),
                        {"c": cid},
                    ).first()
                    if r:
                        return cid
        except Exception:
            log.exception("canonical-case bridge: employee profile resolution failed")
        return None

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

    def save_employee_profile(self, assignment_id: str, profile: Dict[str, Any]) -> None:
        # Wizard-profile store. Relocated from employee_profiles to
        # wizard_employee_profiles after the immigration-core migration took the
        # former over with an incompatible schema (AIQ-868).
        now = datetime.utcnow().isoformat()
        pj = json.dumps(profile)
        with self.engine.begin() as conn:
            existing = conn.execute(
                text("SELECT 1 FROM wizard_employee_profiles WHERE assignment_id = :aid"), {"aid": assignment_id}
            ).fetchone()
            if existing:
                conn.execute(text(
                    "UPDATE wizard_employee_profiles SET profile_json = :pj, updated_at = :now WHERE assignment_id = :aid"
                ), {"pj": pj, "now": now, "aid": assignment_id})
            else:
                conn.execute(text(
                    "INSERT INTO wizard_employee_profiles (assignment_id, profile_json, updated_at) VALUES (:aid, :pj, :now)"
                ), {"aid": assignment_id, "pj": pj, "now": now})

    def get_employee_profile(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        # Wizard-profile store — see save_employee_profile (AIQ-868). Reads from
        # wizard_employee_profiles, where the wizard profile blob now lives after
        # the immigration-core migration claimed public.employee_profiles.
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT profile_json FROM wizard_employee_profiles WHERE assignment_id = :aid"
            ), {"aid": assignment_id}).fetchone()
        return json.loads(row._mapping["profile_json"]) if row else None

    def ensure_profile_record(
        self,
        user_id: str,
        email: Optional[str],
        role: str,
        full_name: Optional[str],
        company_id: Optional[str] = None,
    ) -> None:
        # Supabase profiles table enforces CHECK (role IN ('employee','hr','admin'))
        # — always normalise to lowercase regardless of backend users.role casing.
        role_norm = (role or "employee").lower()
        email_norm = (email or "").strip().lower() if email else None
        full_name_norm = full_name or ""
        now = datetime.utcnow().isoformat()

        # Only query by id if user_id is a valid UUID — non-UUID legacy seed IDs
        # (e.g. "seed-hr-testingapril") cause a PostgreSQL cast error on uuid columns.
        #
        # When the id IS a valid uuid, bind it as a `uuid.UUID` object rather than
        # a Python string. Otherwise psycopg2 sends the parameter as text and
        # PostgreSQL refuses to compare it against the `uuid`-typed profiles.id
        # column with `operator does not exist: uuid = text`. Stringifying a
        # uuid.UUID object on SQLite is harmless (sqlite3 calls str() on it).
        try:
            user_uuid = uuid.UUID(user_id)
            user_id_is_uuid = True
        except (ValueError, AttributeError):
            user_uuid = None
            user_id_is_uuid = False
        id_param = user_uuid if user_id_is_uuid else user_id

        with self.engine.begin() as conn:
            existing = None
            if user_id_is_uuid:
                existing = conn.execute(
                    text("SELECT 1 FROM profiles WHERE id = :id"), {"id": id_param}
                ).fetchone()

            # --- Email fallback ---------------------------------------------------
            # When the backend users.id (UUID) differs from the Supabase auth UUID
            # (possible when fix_demo_passwords or supabase_auth_sync created the
            # auth user independently), the id-based lookup finds nothing but the
            # profile already exists under the Supabase auth UUID.  In that case
            # we UPDATE by email instead of blindly INSERTing (which would fail the
            # profiles_id_fkey FK constraint pointing at auth.users).
            if not existing and email_norm:
                existing_by_email = conn.execute(
                    text("SELECT 1 FROM profiles WHERE LOWER(TRIM(email)) = :email"),
                    {"email": email_norm},
                ).fetchone()
                if existing_by_email:
                    try:
                        if company_id is None:
                            conn.execute(text(
                                "UPDATE profiles SET role = :role, full_name = :full_name "
                                "WHERE LOWER(TRIM(email)) = :email"
                            ), {"role": role_norm, "full_name": full_name_norm, "email": email_norm})
                        else:
                            conn.execute(text(
                                "UPDATE profiles SET role = :role, full_name = :full_name, company_id = :company_id "
                                "WHERE LOWER(TRIM(email)) = :email"
                            ), {"role": role_norm, "full_name": full_name_norm,
                                "company_id": company_id, "email": email_norm})
                    except Exception as _ep:
                        log.warning(
                            "ensure_profile_record email-update failed user_id=%s email=%s error=%s",
                            (user_id or "")[:8], email_norm, _ep,
                        )
                    return
            # ----------------------------------------------------------------------

            if existing:
                if company_id is None:
                    conn.execute(text(
                        "UPDATE profiles SET role = :role, email = :email, full_name = :full_name "
                        "WHERE id = :id"
                    ), {
                        "id": id_param,
                        "role": role_norm,
                        "email": email_norm,
                        "full_name": full_name_norm,
                    })
                else:
                    conn.execute(text(
                        "UPDATE profiles SET role = :role, email = :email, full_name = :full_name, company_id = :company_id "
                        "WHERE id = :id"
                    ), {
                        "id": id_param,
                        "role": role_norm,
                        "email": email_norm,
                        "full_name": full_name_norm,
                        "company_id": company_id,
                    })
            else:
                # INSERT — may fail on Supabase if user_id is not in auth.users
                # (FK constraint).  Catch and log rather than surfacing a 500.
                # PRODSEED-3/AIQ-1130: durably stamp synthetic (…@testco.com) people
                # at registration. is_test is only added when the column exists, so
                # this stays valid before the migration applies and on test SQLite.
                from ..database import _table_columns  # lazy: avoid import cycle
                from .test_data_filter import looks_like_test_email
                _has_is_test = "is_test" in _table_columns(conn, "profiles")
                ins_params: Dict[str, Any] = {
                    "id": id_param,
                    "role": role_norm,
                    "email": email_norm,
                    "full_name": full_name_norm,
                    "company_id": company_id,
                    "created_at": now,
                }
                if _has_is_test:
                    ins_cols = "id, role, email, full_name, company_id, created_at, is_test"
                    ins_vals = ":id, :role, :email, :full_name, :company_id, :created_at, :is_test"
                    ins_params["is_test"] = looks_like_test_email(email_norm)
                else:
                    ins_cols = "id, role, email, full_name, company_id, created_at"
                    ins_vals = ":id, :role, :email, :full_name, :company_id, :created_at"
                try:
                    conn.execute(
                        text(f"INSERT INTO profiles ({ins_cols}) VALUES ({ins_vals})"),
                        ins_params,
                    )
                except Exception as _ei:
                    log.warning(
                        "ensure_profile_record insert failed user_id=%s email=%s error=%s",
                        (user_id or "")[:8], email_norm, _ei,
                    )

    def get_profile_record(self, user_id: str) -> Optional[Dict[str, Any]]:
        # Supabase profiles.id is uuid — non-UUID legacy seed IDs cause a cast
        # error; return None so callers fall back gracefully.
        # Bind the parameter as a uuid.UUID object so psycopg2 sends it as the
        # postgres uuid type (otherwise we'd hit `operator does not exist:
        # uuid = text`).
        try:
            user_uuid = uuid.UUID(user_id)
        except (ValueError, AttributeError):
            return None
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM profiles WHERE id = :id"), {"id": user_uuid}
            ).fetchone()
        return self._row_to_dict(row)

    def get_profile_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Look up a profiles row by email address (case-insensitive).

        Used as a fallback when the local ``users`` table has no entry for an
        employee who already has a Supabase auth account (e.g. accounts created
        via the magic-link / SSO flow that never touched the legacy users table).
        Returning the profile id lets the caller pass a real employee_user_id to
        create_assignment_with_contact_and_invites, which skips the invite path
        and avoids the hanging Supabase Auth inviteUserByEmail call.
        """
        email_norm = (email or "").strip().lower()
        if not email_norm:
            return None
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM profiles WHERE LOWER(TRIM(email)) = :email LIMIT 1"),
                {"email": email_norm},
            ).fetchone()
        return self._row_to_dict(row)

    def set_profile_company(self, user_id: str, company_id: str) -> None:
        """Set profile company and keep hr_users/employees in sync."""
        # profiles.id is uuid — bind as uuid.UUID to avoid
        # "operator does not exist: uuid = text" on Postgres.
        # hr_users.profile_id and employees.profile_id are TEXT, so plain string is fine.
        try:
            profiles_id_param = uuid.UUID(user_id)
        except (ValueError, AttributeError):
            profiles_id_param = user_id
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE profiles SET company_id = :cid WHERE id = :id"
            ), {"cid": company_id, "id": profiles_id_param})
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
            log.warning(
                "deactivate_profile: status=inactive update failed, falling back to delete person_id=%s err=%s",
                person_id,
                e,
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
        # profiles.role CHECK allows only lowercase: 'employee', 'hr', 'admin'
        role_clean = (role or "employee").strip().lower()
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
                # PRODSEED-3/AIQ-1130: durably stamp synthetic (…@testco.com) people
                # at creation. Only added when the column exists (deploy-safe).
                from .test_data_filter import looks_like_test_email
                base_cols = ["id", "email", "full_name", "role", "company_id", "created_at", "updated_at", "is_test"]
                insert_cols = [c for c in base_cols if c in existing]
                params: Dict[str, Any] = {
                    "id": person_id,
                    "email": email_clean,
                    "full_name": full_name,
                    "role": role_clean,
                    "company_id": company_id,
                    "created_at": now,
                    "updated_at": now,
                    "is_test": looks_like_test_email(email_clean),
                }
                values_clause = ", ".join(f":{c}" for c in insert_cols)
                update_sets = []
                for c in insert_cols:
                    # Never overwrite id/created_at; never un-flag is_test on re-upsert.
                    if c in ("id", "created_at", "is_test"):
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
        # PRODSEED-3/AIQ-1130: profiles corralled into the (synthetic) test company are
        # themselves test data — stamp is_test=true. Guarded on column presence so the
        # script stays valid before the migration applies.
        from ..database import _table_columns  # lazy: avoid import cycle
        with self.engine.connect() as _c:
            _set_is_test = ", is_test = true" if "is_test" in _table_columns(_c, "profiles") else ""
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
                        f"UPDATE profiles SET company_id = :cid, role = :role{_set_is_test} WHERE id = :id"
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

    def list_employees_with_profiles(
        self, company_id: str
    ) -> List[Dict[str, Any]]:
        """List employees with profile (full_name, email) for HR company-scoped view."""
        sql = """
            SELECT e.id, e.company_id, e.profile_id, e.band, e.assignment_type, e.relocation_case_id, e.status, e.created_at,
                   p.full_name, p.email
            FROM employees e
            LEFT JOIN profiles p ON CAST(p.id AS TEXT) = e.profile_id
            WHERE e.company_id = :cid
            ORDER BY p.full_name ASC NULLS LAST, e.created_at DESC
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"cid": company_id}).fetchall()
        return self._rows_to_list(rows)

    def get_employee_by_profile_for_company(
        self, profile_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get employee by profile_id if they belong to the given company."""
        sql = """
            SELECT e.id, e.company_id, e.profile_id, e.band, e.assignment_type, e.relocation_case_id, e.status, e.created_at,
                   p.full_name, p.email, p.role
            FROM employees e
            LEFT JOIN profiles p ON CAST(p.id AS TEXT) = e.profile_id
            WHERE e.profile_id = :pid AND e.company_id = :cid
        """
        with self.engine.connect() as conn:
            row = conn.execute(text(sql), {"pid": profile_id, "cid": company_id}).fetchone()
        return self._row_to_dict(row) if row else None

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
            LEFT JOIN profiles p ON CAST(p.id AS TEXT) = hu.profile_id
            WHERE hu.company_id = :cid
            ORDER BY hu.created_at DESC
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"cid": company_id}).fetchall()
        return self._rows_to_list(rows)

    def get_admin_people_index(
        self,
        company_id: Optional[str] = None,
        query: Optional[str] = None,
        role: Optional[str] = None,
        include_test: bool = False,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        List people (profiles) for admin with optional company, role, and text filters.
        Returns (list with company_name, status), summary with count and orphans_without_company.

        PRODSEED-3/AIQ-1130: synthetic e2e/verify people (is_test=true) are hidden by
        default; pass include_test=True to show them. Replaces the read-time @testco.com
        name filter (AIQ-913) with the durable flag, guarded on the column's presence so
        it degrades safely if the migration hasn't applied yet.
        """
        from ..database import _table_columns  # lazy: avoid import cycle
        params: Dict[str, Any] = {}
        clauses = []
        with self.engine.connect() as _c:
            _profiles_has_is_test = "is_test" in _table_columns(_c, "profiles")
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
        # PRODSEED-3/AIQ-1130: hide synthetic e2e/verify seed people via the durable
        # is_test flag (replaces the AIQ-913 …@testco.com read-time pattern). Guarded
        # on column presence so it no-ops safely before the migration applies.
        if not include_test and _profiles_has_is_test:
            clauses.append("COALESCE(p.is_test, false) = false")
        where = " AND " + " AND ".join(clauses) if clauses else ""
        # B9b: p.created_at removed — column may not exist in production Supabase profiles
        # table (schema drift). Ordering falls back to full_name-only to avoid
        # ProgrammingError → 500. If created_at is later confirmed present, add it back.
        sql = f"""
            SELECT p.id, p.role, p.email, p.full_name, p.company_id,
                   'active' AS status,
                   c.name AS company_name,
                   (SELECT COUNT(*) FROM hr_users hu WHERE hu.profile_id = p.id) AS hr_link_count,
                   (SELECT COUNT(*) FROM employees e WHERE e.profile_id = p.id) AS employee_link_count
            FROM profiles p
            LEFT JOIN companies c ON c.id = p.company_id
            WHERE 1=1 {where}
            ORDER BY p.full_name ASC NULLS LAST
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
        people = [dict(r._mapping) for r in rows]
        for row in people:
            row["name"] = row.get("full_name") or row.get("email") or row.get("id")
        # Orphans: profiles with role in ('HR','EMPLOYEE','EMPLOYEE_USER') and no company_id
        try:
            # PRODSEED-3: exclude synthetic people from the orphan count via the flag
            # (guarded so it stays valid before the migration applies).
            orphan_test_clause = (
                "AND COALESCE(is_test, false) = false"
                if (not include_test and _profiles_has_is_test)
                else ""
            )
            orphan_sql = text(f"""
                SELECT COUNT(*) AS n FROM profiles
                WHERE (role IN ('HR','EMPLOYEE','EMPLOYEE_USER') OR role IS NULL)
                AND (company_id IS NULL OR TRIM(company_id) = '')
                {orphan_test_clause}
            """)
            with self.engine.connect() as conn:
                orphan_row = conn.execute(orphan_sql, {}).fetchone()
            orphans = int(orphan_row._mapping["n"]) if orphan_row else 0
        except Exception as e:
            log.warning("admin_people_index: orphan count failed: %s", e)
            orphans = 0
        summary = {"count": len(people), "orphans_without_company": orphans}
        return people, summary
