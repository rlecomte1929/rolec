"""
Single source of truth for database configuration.
- Production (Render): Use DATABASE_URL from env only. Never load .env.
- Local dev: Optionally load .env (override=False) so existing env vars win.
"""
import os
from typing import Any, Dict
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
        # Load .env from project root (parent of backend/), so it's found regardless of cwd
        _backend_dir = os.path.dirname(os.path.abspath(__file__))
        _project_root = os.path.dirname(_backend_dir)
        _env_path = os.path.join(_project_root, ".env")
        load_dotenv(dotenv_path=_env_path, override=False)  # Never override existing env vars
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

# Supabase transaction-mode pooler (port 6543) requires username postgres.PROJECT_REF.
# A bare "postgres" username causes FATAL: password authentication failed, which
# increments the pooler's bad-auth counter and trips ECIRCUITBREAKER, blocking ALL
# subsequent connections.  Auto-correct by extracting the project ref from SUPABASE_URL.
import re as _re_pooler
_parsed_pooler = urlparse(_raw_url)
if (
    _raw_url.startswith("postgresql://")
    and "pooler.supabase.com" in _raw_url
    and ":6543" in _raw_url
    and (_parsed_pooler.username or "") == "postgres"
):
    _supa_url = os.getenv("SUPABASE_URL", "")
    _m_proj = _re_pooler.match(r"https?://([^.]+)\.supabase\.co", _supa_url)
    if _m_proj:
        _proj_ref = _m_proj.group(1)
        _pw_raw = _parsed_pooler.password or ""
        _raw_url = _raw_url.replace(
            f"postgresql://postgres:{_pw_raw}@",
            f"postgresql://postgres.{_proj_ref}:{_pw_raw}@",
            1,
        )

DATABASE_URL: str = _raw_url

# ---------------------------------------------------------------------------
# F3/AIQ-834: optional dedicated least-privilege connection for request-path
# queries (the non-superuser `relopass_api` role). When RELOPASS_API_DATABASE_URL
# is unset, the request path reuses DATABASE_URL (the existing superuser pool) —
# i.e. behaviour is UNCHANGED until a human provisions the role and sets this env
# var. Only the scheme/SSL transforms are applied (the URL must already carry the
# pooler-qualified username, e.g. relopass_api.<project_ref>, when it points at
# the Supabase transaction pooler).
# ---------------------------------------------------------------------------
_request_raw = os.getenv("RELOPASS_API_DATABASE_URL", "").strip()
if _request_raw:
    if _request_raw.startswith("postgres://"):
        _request_raw = _request_raw.replace("postgres://", "postgresql://", 1)
    if (
        _request_raw.startswith("postgresql://")
        and "pooler.supabase.com" in _request_raw
        and "sslmode=" not in _request_raw.lower()
    ):
        _request_raw = _request_raw + ("&" if "?" in _request_raw else "?") + "sslmode=require"
    REQUEST_DATABASE_URL: str = _request_raw
    REQUEST_DB_IS_DEDICATED: bool = True
else:
    REQUEST_DATABASE_URL = DATABASE_URL
    REQUEST_DB_IS_DEDICATED = False


def sqlalchemy_engine_kwargs(database_url: str) -> Dict[str, Any]:
    """
    SQLAlchemy create_engine kwargs: SQLite uses thread check; Postgres uses a small pool
    with pre-ping and recycle to survive Supabase/managed-DB idle disconnects.
    """
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {
        "pool_pre_ping": True,
        "pool_size": int(os.getenv("SQLALCHEMY_POOL_SIZE", "5")),
        "max_overflow": int(os.getenv("SQLALCHEMY_MAX_OVERFLOW", "10")),
        "pool_recycle": int(os.getenv("SQLALCHEMY_POOL_RECYCLE", "280")),
        "pool_timeout": int(os.getenv("SQLALCHEMY_POOL_TIMEOUT", "10")),
        "connect_args": {
            "connect_timeout": 10,
            "options": "-c statement_timeout=20000 -c lock_timeout=8000",
        },
    }


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
