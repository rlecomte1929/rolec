"""
Idempotent helpers for **dev/demo** rows in `users` only.

Canonical product rule: HR creates `employee_contacts` + assignments without creating auth users.
This module is for SQLite demo seed and `scripts/seed_local_accounts.py` — not assignment provisioning.
"""
from __future__ import annotations

from typing import Any


def ensure_dev_seed_auth_user(
    db: Any,
    *,
    user_id: str,
    email: str,
    password_hash: str,
    role: str,
    name: str,
) -> str:
    """
    Ensure a `users` row exists for `email`. Returns the user id (existing or newly created).

    Race: if `create_user` fails due to uniqueness, resolves via `get_user_by_email`.
    """
    get_user_by_email = db.get_user_by_email
    create_user = db.create_user

    existing = get_user_by_email(email)
    if existing:
        return str(existing["id"])
    created = create_user(
        user_id=user_id,
        username=None,
        email=email,
        password_hash=password_hash,
        role=role,
        name=name,
    )
    if created:
        return user_id
    again = get_user_by_email(email)
    if again:
        return str(again["id"])
    raise RuntimeError(f"ensure_dev_seed_auth_user: could not create or resolve email={email!r}")
