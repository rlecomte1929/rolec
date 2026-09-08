"""Shared CORS policy for the prod app (`backend.main`) and the modular app."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Vite fallback ports 3002–3005 for local dev.
_DEFAULT_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://localhost:3003",
    "http://localhost:3004",
    "http://localhost:3005",
    "http://localhost:5173",
    "https://relopass.com",
    "https://www.relopass.com",
]
# Match apex + subdomains (fullmatch). A plain `https://.*\.relopass\.com` misses https://relopass.com.
_DEFAULT_ORIGIN_REGEX = r"^https://([\w-]+\.)*relopass\.com$"


def cors_origins() -> list[str]:
    origins = list(_DEFAULT_ORIGINS)
    env_origins = os.getenv("CORS_ORIGINS")
    if env_origins:
        extra = [o.strip() for o in env_origins.split(",") if o.strip()]
        origins = list(dict.fromkeys(origins + extra))
    return origins


def cors_origin_regex() -> str:
    return os.getenv("CORS_ORIGIN_REGEX") or _DEFAULT_ORIGIN_REGEX


def install_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_origin_regex=cors_origin_regex(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Server-Timing"],
        # Fewer preflight round-trips on repeat requests (helps perceived lag on slow networks).
        max_age=86400,
    )
