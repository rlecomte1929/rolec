#!/usr/bin/env python3
"""
Create Admin and HR (and optional Employee) accounts for local testing.
Works with both SQLite and Postgres. Run once after starting a fresh DB.

Usage (from repo root):
  PYTHONPATH=. python backend/scripts/seed_local_accounts.py

All seeded accounts use password: Passw0rd!
"""
import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
os.chdir(repo_root)

os.environ.setdefault("DATABASE_URL", "sqlite:///./backend/relopass.db")

from passlib.context import CryptContext
from backend import database
from backend.dev_seed_auth import ensure_dev_seed_auth_user

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
PASSWORD_HASH = pwd_context.hash("Passw0rd!")


def main():
    db = database.Database()

    demo_company = "demo-company-001"
    test_company = "test-company-001"
    # Ensure companies exist (SQLite-safe insert; Postgres may use create_company)
    from backend.db_config import DATABASE_URL
    from sqlalchemy import text
    now = __import__("datetime").datetime.utcnow().isoformat()
    if not db.get_company(demo_company):
        if DATABASE_URL.startswith("sqlite"):
            with db.engine.begin() as conn:
                conn.execute(text(
                    "INSERT OR IGNORE INTO companies (id, name, country, size_band, address, phone, hr_contact, created_at) "
                    "VALUES (:id, :name, :country, :sb, :addr, :phone, :hr, :ca)"
                ), {"id": demo_company, "name": "Acme Corp", "country": "Singapore", "sb": "200-500", "addr": "", "phone": "", "hr": "", "ca": now})
        else:
            db.create_company(demo_company, "Acme Corp", "Singapore", "200-500", "", "", "")
    if not db.get_company(test_company):
        if DATABASE_URL.startswith("sqlite"):
            with db.engine.begin() as conn:
                conn.execute(text(
                    "INSERT OR IGNORE INTO companies (id, name, country, size_band, address, phone, hr_contact, created_at) "
                    "VALUES (:id, :name, :country, :sb, :addr, :phone, :hr, :ca)"
                ), {"id": test_company, "name": "test", "country": "Singapore", "sb": "1-50", "addr": "", "phone": "", "hr": "", "ca": now})
        else:
            db.create_company(test_company, "test", "Singapore", "1-50", "", "", "")

    admin_id = ensure_dev_seed_auth_user(
        db,
        user_id="demo-admin-001",
        email="admin@relopass.com",
        password_hash=PASSWORD_HASH,
        role="ADMIN",
        name="ReloPass Admin",
    )
    hr_id = ensure_dev_seed_auth_user(
        db,
        user_id="demo-hr-002",
        email="hr@relopass.com",
        password_hash=PASSWORD_HASH,
        role="HR",
        name="HR Manager",
    )
    emp_id = ensure_dev_seed_auth_user(
        db,
        user_id="test-emp-test",
        email="testEMPtest@relopass.com",
        password_hash=PASSWORD_HASH,
        role="EMPLOYEE",
        name="Test Employee",
    )

    db.add_admin_allowlist("admin@relopass.com", admin_id)
    db.ensure_profile_record(admin_id, "admin@relopass.com", "ADMIN", "ReloPass Admin", None)
    db.ensure_profile_record(hr_id, "hr@relopass.com", "HR", "HR Manager", demo_company)
    db.ensure_profile_record(emp_id, "testEMPtest@relopass.com", "EMPLOYEE", "Test Employee", test_company)

    from sqlalchemy.exc import IntegrityError
    for hr_id_val, cid in [("hr-002", demo_company), ("hr-003", test_company)]:
        try:
            db.create_hr_user(hr_id_val, cid, hr_id, {"can_manage_policy": True})
        except IntegrityError:
            pass

    print("Local test accounts created (password for all: Passw0rd!)")
    print("  Admin:  admin@relopass.com")
    print("  HR:     hr@relopass.com")
    print("  Employee: testEMPtest@relopass.com")
    print("Companies: Acme Corp (demo-company-001), test (test-company-001)")


if __name__ == "__main__":
    main()
