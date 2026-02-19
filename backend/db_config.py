"""
Single source of truth for database configuration.
- Production (Render): Use DATABASE_URL from env only. Never load .env.
- Local dev: Optionally load .env (override=False) so existing env vars win.
"""
import os
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Production guard: never load dotenv when running on Render or ENV=production
# ---------------------------------------------------------------------------
_IS_PRODUCTION = (
    os.getenv("RENDER") == "true"
    or os.getenv("RENDER") == "1"
    or os.getenv("ENV") == "production"
)

if not _IS_PRODUCTION:
    try:
        from dotenv import load_dotenv
        load_dotenv(override=False)  # Never override existing env vars
    except ImportError:
        pass  # python-dotenv not installed — rely on shell env only

# ---------------------------------------------------------------------------
# DATABASE_URL: single source of truth
# We never modify username, host, or port. Only safe transforms:
# 1) postgres:// -> postgresql:// (scheme)
# 2) append ?sslmode=require for Supabase pooler when missing
# ---------------------------------------------------------------------------
_raw_url = os.getenv("DATABASE_URL", "sqlite:///./relopass.db")

# SQLAlchemy 2.x rejects postgres://; Supabase/Render may expose it
if _raw_url.startswith("postgres://"):
    _raw_url = _raw_url.replace("postgres://", "postgresql://", 1)

# Supabase pooler requires SSL; without sslmode=require, psycopg2 gets
# "SSL connection has been closed unexpectedly"
if (
    _raw_url.startswith("postgresql://")
    and "pooler.supabase.com" in _raw_url
    and "sslmode=" not in _raw_url.lower()
):
    _raw_url = _raw_url + ("&" if "?" in _raw_url else "?") + "sslmode=require"

DATABASE_URL: str = _raw_url


def get_masked_db_log_line() -> str:
    """
    Return a safe log string with parsed URL components (password masked).
    TODO: Remove this diagnostic after confirming production DB connectivity.
    """
    try:
        parsed = urlparse(DATABASE_URL)
        if parsed.scheme in ("sqlite", "sqlite3"):
            return f"db_config: scheme=sqlite, path={parsed.path or '(memory)'}"
        user = parsed.username or "(none)"
        host = parsed.hostname or "(none)"
        port = parsed.port or 5432
        dbname = (parsed.path or "/").lstrip("/") or "(default)"
        ssl = "sslmode=" in (parsed.query or "") or "sslmode=" in DATABASE_URL
        return (
            f"db_config: scheme={parsed.scheme} user={user} host={host} port={port} "
            f"database={dbname} sslmode={'present' if ssl else 'absent'} password=***"
        )
    except Exception:
        return "db_config: (could not parse URL)"
