#!/usr/bin/env python3
"""
Seed ReloPass local SQLite with the Testing April company and three test accounts.

Usage (from repo root):
  PYTHONPATH=. python backend/scripts/seed_testingapril_accounts.py

Accounts created:
  Admin:    admin@relopass.com    / AdminPass!1  (global)
  HR:       hr@testingapril.com   / HrPass!1     (Testing April)
  Employee: employee@testingapril.com / EmpPass!1 (Testing April)
"""
import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
os.chdir(repo_root)

os.environ.setdefault("DATABASE_URL", "sqlite:///./relopass.db")

from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from backend import database
from backend.dev_seed_auth import ensure_dev_seed_auth_user
from backend.db_config import DATABASE_URL

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

ACCOUNTS = [
    {
        "user_id":       "seed-admin-001",
        "email":         "admin@relopass.com",
        "password":      "AdminPass!1",
        "role":          "ADMIN",
        "name":          "ReloPass Admin",
        "company_id":    None,
    },
    {
        "user_id":       "seed-hr-testingapril",
        "email":         "hr@testingapril.com",
        "password":      "HrPass!1",
        "role":          "HR",
        "name":          "Hannah HR",
        "company_id":    "testing-april-001",
    },
    {
        "user_id":       "seed-emp-testingapril",
        "email":         "employee@testingapril.com",
        "password":      "EmpPass!1",
        "role":          "EMPLOYEE",
        "name":          "Testing April Employee",
        "company_id":    "testing-april-001",
    },
]

COMPANY_ID   = "testing-april-001"
COMPANY_NAME = "Testing April"


def main():
    db = database.Database()
    now = __import__("datetime").datetime.utcnow().isoformat()

    # ── Ensure Testing April company exists ───────────────────────────────────
    if not db.get_company(COMPANY_ID):
        if DATABASE_URL.startswith("sqlite"):
            with db.engine.begin() as conn:
                conn.execute(text(
                    "INSERT OR IGNORE INTO companies "
                    "(id, name, country, size_band, address, phone, hr_contact, created_at) "
                    "VALUES (:id, :name, :country, :sb, :addr, :phone, :hr, :ca)"
                ), {
                    "id": COMPANY_ID, "name": COMPANY_NAME,
                    "country": "UK", "sb": "50-200",
                    "addr": "", "phone": "", "hr": "", "ca": now,
                })
        else:
            db.create_company(COMPANY_ID, COMPANY_NAME, "UK", "50-200", "", "", "")
        print(f"  Created company: {COMPANY_NAME} ({COMPANY_ID})")
    else:
        print(f"  Company already exists: {COMPANY_NAME}")

    # ── Create / ensure each user ─────────────────────────────────────────────
    for acct in ACCOUNTS:
        pw_hash = pwd_context.hash(acct["password"])
        uid = ensure_dev_seed_auth_user(
            db,
            user_id=acct["user_id"],
            email=acct["email"],
            password_hash=pw_hash,
            role=acct["role"],
            name=acct["name"],
        )
        db.ensure_profile_record(
            uid,
            acct["email"],
            acct["role"],
            acct["name"],
            acct["company_id"],
        )
        if acct["role"] == "ADMIN":
            db.add_admin_allowlist(acct["email"], uid)
        if acct["role"] == "HR" and acct["company_id"]:
            try:
                db.create_hr_user(uid, acct["company_id"], uid, {"can_manage_policy": True})
            except IntegrityError:
                pass
        print(f"  {acct['role']:10s} {acct['email']:40s} ✓")

    print("\nDone. All accounts use the passwords defined in this script.")
    print(f"  Admin:    admin@relopass.com        / AdminPass!1")
    print(f"  HR:       hr@testingapril.com       / HrPass!1")
    print(f"  Employee: employee@testingapril.com / EmpPass!1")


if __name__ == "__main__":
    main()
