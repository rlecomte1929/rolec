"""
AI carbon estimator — Parker Step G.

Converts an LLM call's token counts into an estimated CO₂e value using the standard
chain::

    grams_CO2e = (tokens_in · J_in + tokens_out · J_out) / 3_600_000  (J → kWh)
                 · region_gCO2e_per_kWh

Per-model energy constants live in the ``ai_model_energy_profiles`` table; this module
reads them best-effort and caches them in-process. When the table is absent (CI / dev
without the migration) or the model is unknown, it falls back to in-code seed defaults
(identical to the migration seed) and finally a conservative global default — so the
estimate is ALWAYS available and never depends on the DB being reachable.

The estimate is approximate: vendor per-token energy intensity is not public.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

_JOULES_PER_KWH = 3_600_000.0


@dataclass(frozen=True)
class EnergyProfile:
    """Per-model energy + grid-carbon constants."""

    model_name: str
    joules_per_input_token: float
    joules_per_output_token: float
    region_gco2_per_kwh: float
    source_url: Optional[str] = None


# In-code seed — MUST match supabase/migrations/20260601080000_ai_unit_economics.sql.
# Rough public estimates (Patterson et al. 2021; Luccioni et al. 2023; mlco2.github.io).
_DEFAULT_PROFILES: Dict[str, EnergyProfile] = {
    "claude-sonnet-4-6":      EnergyProfile("claude-sonnet-4-6",      0.40, 0.80, 400.0),
    "claude-haiku-4-5":       EnergyProfile("claude-haiku-4-5",       0.12, 0.24, 400.0),
    "gpt-4o":                 EnergyProfile("gpt-4o",                 0.40, 0.80, 400.0),
    "gpt-4o-mini":            EnergyProfile("gpt-4o-mini",            0.12, 0.24, 400.0),
    "text-embedding-3-small": EnergyProfile("text-embedding-3-small", 0.05, 0.00, 400.0),
}

# Conservative fallback for a model with no profile anywhere — frontier-class energy
# so we never under-report carbon for an unknown (likely large) model.
_GLOBAL_DEFAULT = EnergyProfile("__default__", 0.40, 0.80, 400.0)

_cache: Dict[str, EnergyProfile] = {}
_cache_lock = threading.Lock()


def clear_cache() -> None:
    """Test hook — drop the in-process profile cache."""
    with _cache_lock:
        _cache.clear()


def _load_profile_from_db(model_name: str) -> Optional[EnergyProfile]:
    """Best-effort read of one profile row. Returns None on any failure/absence."""
    try:
        from ..db import SessionLocal  # local import: avoid DB import at module load
        from sqlalchemy import text

        session = SessionLocal()
        try:
            row = session.execute(
                text(
                    "SELECT model_name, joules_per_input_token, joules_per_output_token, "
                    "region_gco2_per_kwh, source_url "
                    "FROM ai_model_energy_profiles WHERE model_name = :m"
                ),
                {"m": model_name},
            ).first()
        finally:
            session.close()
        if row is None:
            return None
        return EnergyProfile(
            model_name=row[0],
            joules_per_input_token=float(row[1]),
            joules_per_output_token=float(row[2]),
            region_gco2_per_kwh=float(row[3]),
            source_url=row[4],
        )
    except Exception:
        log.debug("ai_carbon: db profile read failed for %s", model_name, exc_info=True)
        return None


def get_energy_profile(model_name: str, *, session: Any = None) -> EnergyProfile:
    """Resolve a model's energy profile: cache → DB → seed default → global default.

    A ``session`` may be injected (tests); otherwise a best-effort DB read is attempted.
    Unknown models log a warning and fall back to the global default.
    """
    with _cache_lock:
        cached = _cache.get(model_name)
    if cached is not None:
        return cached

    profile: Optional[EnergyProfile] = None
    if session is not None:
        profile = _load_profile_from_session(session, model_name)
    else:
        profile = _load_profile_from_db(model_name)

    if profile is None:
        profile = _DEFAULT_PROFILES.get(model_name)

    if profile is None:
        log.warning(
            "ai_carbon: no energy profile for model %r — using global default", model_name
        )
        profile = _GLOBAL_DEFAULT

    with _cache_lock:
        _cache[model_name] = profile
    return profile


def _load_profile_from_session(session: Any, model_name: str) -> Optional[EnergyProfile]:
    try:
        from sqlalchemy import text

        row = session.execute(
            text(
                "SELECT model_name, joules_per_input_token, joules_per_output_token, "
                "region_gco2_per_kwh, source_url "
                "FROM ai_model_energy_profiles WHERE model_name = :m"
            ),
            {"m": model_name},
        ).first()
        if row is None:
            return None
        return EnergyProfile(
            model_name=row[0],
            joules_per_input_token=float(row[1]),
            joules_per_output_token=float(row[2]),
            region_gco2_per_kwh=float(row[3]),
            source_url=row[4],
        )
    except Exception:
        log.debug("ai_carbon: session profile read failed for %s", model_name, exc_info=True)
        return None


def estimate_co2e_grams(
    model_name: str, tokens_in: int, tokens_out: int, *, session: Any = None
) -> float:
    """Estimate grams of CO₂e for one LLM call.

    ``grams = (tokens_in·J_in + tokens_out·J_out) / 3_600_000 · gCO2e/kWh``.
    Always returns a value (falls back to defaults when the profile/DB is absent).
    """
    profile = get_energy_profile(model_name, session=session)
    joules = (
        max(0, int(tokens_in)) * profile.joules_per_input_token
        + max(0, int(tokens_out)) * profile.joules_per_output_token
    )
    kwh = joules / _JOULES_PER_KWH
    return kwh * profile.region_gco2_per_kwh
