import os
from typing import Any

try:
    # Prefer the supabase-py client from site-packages.
    # Note: a local ./supabase folder (Supabase CLI project) can shadow the package;
    # this try/except prevents import-time crashes in that case.
    from supabase import create_client, Client  # type: ignore
except Exception:  # pragma: no cover - defensive fallback
    create_client = None  # type: ignore[assignment]
    Client = Any  # type: ignore[assignment]


def _ensure_supabase_client_available() -> None:
    if create_client is None:
        # This keeps module importable even when the supabase package is shadowed
        # or not installed, and fails lazily only when a Supabase-backed endpoint is used.
        raise RuntimeError(
            "Supabase Python client is not available. "
            "For local dev with SQLite you can ignore Supabase-backed endpoints, "
            "or install supabase-py in the backend venv."
        )


def get_supabase_client(user_jwt: str) -> Client:
    """
    User-scoped Supabase client (anon key + user JWT).
    Used when we want RLS to apply for the current user.
    """
    _ensure_supabase_client_available()
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")
    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY are required")

    client = create_client(supabase_url, supabase_key)
    try:
        client.postgrest.auth(user_jwt)
    except Exception:
        try:
            client.postgrest.session.headers.update(
                {"Authorization": f"Bearer {user_jwt}"}
            )
        except Exception:
            pass
    return client


def get_supabase_admin_client() -> Client:
    """
    Admin Supabase client (service-role) for backend-only operations.
    Reads SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY as required.
    """
    _ensure_supabase_client_available()
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    return create_client(supabase_url, service_key)
