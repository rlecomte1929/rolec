#!/usr/bin/env python3
"""
One-off: reset a demo account's password in BOTH auth systems (AIQ-875 / UIAUDIT-G1).

ReloPass runs two auth systems in parallel, so a password reset must touch both
or they drift (which is exactly the bug this fixes):
  1. public.users (PBKDF2 / passlib)  — the ReloPass session-token login used by
     POST /api/auth/login.
  2. Supabase Auth                    — the JWT / RLS path (signInWithPassword).

SECURITY: the new password is read from the NEW_ADMIN_PW environment variable so
it never enters a git-tracked file or any log line. Run from the repo root, e.g.

    NEW_ADMIN_PW='your-strong-password' python scripts/reset_demo_admin_password.py
    # optional override: TARGET_EMAIL=hr@relopass.com NEW_ADMIN_PW='…' python …

Requires the usual backend env: DATABASE_URL, and for the Supabase Auth side
SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY (loaded from .env like the app). If the
Supabase env is absent, the public.users reset still applies (so /api/auth/login
works) but the script exits non-zero so the cross-system drift is surfaced loudly.

Exit codes:
  0 — both auth paths reset and verified
  1 — bad input or the public.users reset failed (nothing usable changed)
  2 — public.users reset OK, but the Supabase Auth side could not be synced
"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)


def _die(msg: str, code: int = 1) -> None:
    print(f"[reset-demo-admin] ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def _find_supabase_auth_uid(client, email):
    """Best-effort: page admin.list_users() to find the auth uid for email."""
    try:
        resp = client.auth.admin.list_users()
    except Exception:
        return None
    users = getattr(resp, "users", None)
    if users is None:
        users = resp if isinstance(resp, list) else []
    for u in users:
        ue = getattr(u, "email", None)
        if ue is None and isinstance(u, dict):
            ue = u.get("email")
        if (ue or "").strip().lower() == email:
            uid = getattr(u, "id", None)
            if uid is None and isinstance(u, dict):
                uid = u.get("id")
            return uid
    return None


def main() -> int:
    # Validate input BEFORE importing anything DB-bound, so the common
    # "forgot to set NEW_ADMIN_PW" mistake fails fast with no DB connection.
    new_pw = os.environ.get("NEW_ADMIN_PW", "")
    if len(new_pw) < 8:
        _die(
            "NEW_ADMIN_PW env var is required and must be >= 8 chars.\n"
            "  Run: NEW_ADMIN_PW='your-strong-password' "
            "python scripts/reset_demo_admin_password.py"
        )
    email = os.environ.get("TARGET_EMAIL", "admin@relopass.com").strip().lower()

    from passlib.context import CryptContext
    from sqlalchemy import text

    from backend import database

    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    new_hash = pwd_context.hash(new_pw)

    # ── 1) public.users (ReloPass session-token path) ─────────────────────────
    db = database.Database()
    with db.engine.begin() as conn:
        row = conn.execute(
            text("SELECT id FROM users WHERE lower(email) = :e"), {"e": email}
        ).mappings().first()
        if not row:
            _die(f"no users row for {email!r} — nothing to reset")
        uid = row["id"]
        conn.execute(
            text("UPDATE users SET password_hash = :h WHERE lower(email) = :e"),
            {"h": new_hash, "e": email},
        )
        check = conn.execute(
            text("SELECT password_hash FROM users WHERE lower(email) = :e"), {"e": email}
        ).mappings().first()
    if not check or not pwd_context.verify(new_pw, check["password_hash"]):
        _die("post-update verification failed — the new hash does not validate")
    print(f"[reset-demo-admin] public.users password reset + verified for {email} (id={uid})")

    # ── 2) Supabase Auth (JWT / RLS path) ─────────────────────────────────────
    try:
        from backend.app.services.supabase_client import get_supabase_admin_client

        client = get_supabase_admin_client()
    except Exception as ex:  # missing env / package
        print(
            f"[reset-demo-admin] WARNING: Supabase admin client unavailable ({ex}). "
            "public.users is reset (/api/auth/login works) but Supabase Auth is NOT "
            "in sync — set SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY and re-run.",
            file=sys.stderr,
        )
        return 2

    try:
        auth_uid = _find_supabase_auth_uid(client, email)
        if auth_uid:
            client.auth.admin.update_user_by_id(auth_uid, {"password": new_pw})
            print(
                f"[reset-demo-admin] Supabase Auth password updated for {email} "
                f"(uid={str(auth_uid)[:8]}…)"
            )
        else:
            client.auth.admin.create_user(
                {"email": email, "password": new_pw, "email_confirm": True}
            )
            print(f"[reset-demo-admin] Supabase Auth user created for {email}")
    except Exception as ex:
        print(
            f"[reset-demo-admin] WARNING: Supabase Auth update failed ({ex}). "
            "public.users is reset but the JWT/RLS path is not in sync.",
            file=sys.stderr,
        )
        return 2

    print(
        "[reset-demo-admin] DONE — both auth paths reset. "
        "Record the password where the e2e skill / one-click demo reads it; "
        "do NOT commit it to git."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
