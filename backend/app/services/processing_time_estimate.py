"""processing_time_estimate.py — corridor-level processing-time prediction (P2-04a).

Given a corridor (and pathway), estimate how many days the immigration process
takes, as a p50/p90 pair. Two sources, in priority order:

  1. ``platform_data`` — empirical p50/p90 computed from ReloPass's own completed
     cases for that corridor, but ONLY once there are >= MIN_PLATFORM_CASES of
     them (the statistical-significance floor). Carries the sample size so the UI
     can show "based on 47 similar cases".
  2. ``official_only`` — the authoritative statutory / official range seeded in
     ``corpus/official_processing_times.json`` (P2-04b). Used as the fallback
     while platform data is still accumulating. Carries a source citation.

If neither source can produce an estimate, the function returns ``None`` — the
caller MUST NOT render a processing time without a source.

This module is intentionally dependency-light (stdlib only): no pandas/numpy/ML
imports, so importing it never requires the ML extras and the pure estimation
core can be unit-tested anywhere. The DB read reuses the duration semantics from
case_duration_model.build_survival_frame (created_at -> last milestone actual),
restricted to completed cases.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional, Tuple, TypedDict

log = logging.getLogger(__name__)

# Statistical floor: below this many completed platform cases for a corridor we do
# not trust an empirical estimate and fall back to the official range.
MIN_PLATFORM_CASES = 20

# corpus/official_processing_times.json lives at the repo root. This file is at
# backend/app/services/processing_time_estimate.py, so the repo root is parents[3].
_OFFICIAL_RANGES_PATH = (
    Path(__file__).resolve().parents[3] / "corpus" / "official_processing_times.json"
)

# A case counts as completed (and therefore contributes a finished processing
# time) when its status is terminal. Mirrors case_duration_model's terminal set.
_TERMINAL_CASE_STATUSES = {"completed", "closed", "done", "archived"}


class ProcessingTimeEstimate(TypedDict, total=False):
    """Return shape of :func:`processing_time_estimate`.

    ``source_url`` is present only for the ``official_only`` branch (the citation
    the UI shows). ``sample_size`` is the number of completed platform cases
    behind a ``platform_data`` estimate, or 0 for ``official_only``.
    """

    p50_days: int
    p90_days: int
    source: str  # 'platform_data' | 'official_only'
    sample_size: int
    last_updated: str  # ISO-8601 date/datetime
    source_url: Optional[str]


# ──────────────────────────────────────────────────────────────────────────────
# Pure estimation core (no DB, no heavy deps) — fully unit-testable
# ──────────────────────────────────────────────────────────────────────────────


def _percentile(sorted_values: List[float], q: float) -> float:
    """Linear-interpolation percentile of an already-sorted list.

    ``q`` is in [0, 1]. Matches numpy's default ('linear') method so the result
    lines up with anything the analytics side computes with numpy. Assumes the
    input is non-empty and sorted ascending.
    """
    if not sorted_values:
        raise ValueError("percentile of empty sequence")
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = q * (len(sorted_values) - 1)
    low = int(rank)
    high = min(low + 1, len(sorted_values) - 1)
    frac = rank - low
    return float(sorted_values[low] + (sorted_values[high] - sorted_values[low]) * frac)


def estimate_from_durations(durations: List[int]) -> Optional[Tuple[int, int]]:
    """Empirical (p50, p90) in whole days from completed-case durations.

    Returns ``None`` when there are fewer than MIN_PLATFORM_CASES durations — the
    caller should fall back to the official source. Non-positive durations are
    dropped first (a 0-day "case" is data noise, not a real processing time).
    """
    clean = sorted(d for d in durations if d is not None and d > 0)
    if len(clean) < MIN_PLATFORM_CASES:
        return None
    p50 = round(_percentile(clean, 0.5))
    p90 = round(_percentile(clean, 0.9))
    return int(p50), int(p90)


# ──────────────────────────────────────────────────────────────────────────────
# Official-source fallback (corpus/official_processing_times.json)
# ──────────────────────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def load_official_ranges() -> dict:
    """Load the official-ranges seed file, keyed by (from, to, pathway_type).

    Cached for the process lifetime. Returns an empty index if the file is
    missing or malformed (the service then has no official fallback and returns
    None rather than crashing — fail safe, never sourceless).
    """
    try:
        raw = json.loads(_OFFICIAL_RANGES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning(
            "processing_time_estimate: could not load official ranges from %s (%s)",
            _OFFICIAL_RANGES_PATH, exc,
        )
        return {}

    index: dict = {}
    for entry in raw.get("entries", []):
        corridor = entry.get("corridor") or {}
        key = (
            str(corridor.get("from", "")).upper(),
            str(corridor.get("to", "")).upper(),
            str(entry.get("pathway_type", "")).upper(),
        )
        index[key] = entry
    return index


def _official_estimate(
    origin: str, dest: str, pathway_type: Optional[str]
) -> Optional[ProcessingTimeEstimate]:
    """Build an ``official_only`` estimate for a corridor, or None if not seeded.

    Maps the seed's ``low_days -> p50`` and ``high_days -> p90`` (the contract
    agreed in P2-04b's reviewer notes).
    """
    index = load_official_ranges()
    entry = index.get((origin.upper(), dest.upper(), (pathway_type or "").upper()))
    if entry is None and pathway_type:
        # Pathway not matched — accept a corridor-only match if exactly one exists,
        # so a caller that doesn't know the pathway still gets the official range.
        corridor_matches = [
            e for (f, t, _), e in index.items() if f == origin.upper() and t == dest.upper()
        ]
        entry = corridor_matches[0] if len(corridor_matches) == 1 else None
    if entry is None:
        return None

    low = entry.get("low_days")
    high = entry.get("high_days")
    if low is None or high is None:
        return None

    source = entry.get("source") or {}
    return ProcessingTimeEstimate(
        p50_days=int(low),
        p90_days=int(high),
        source="official_only",
        sample_size=0,
        last_updated=str(entry.get("fetched_at") or ""),
        source_url=source.get("url"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# DB read — completed-case durations for one corridor
# ──────────────────────────────────────────────────────────────────────────────


def _fetch_completed_durations(session: Any, origin: str, dest: str) -> List[int]:
    """Return processing durations (days) for completed cases on this corridor.

    A case is completed when its status is terminal OR every milestone is done.
    Duration is created_at -> last milestone actual_date (falling back to
    updated_at), matching case_duration_model.build_survival_frame, but here we
    keep only finished cases (in-flight cases have no final processing time).
    """
    from sqlalchemy import text as sql_text

    rows = session.execute(
        sql_text(
            """
            SELECT c.created_at AS created_at,
                   c.updated_at AS updated_at,
                   c.status     AS status,
                   m.total_ms   AS total_ms,
                   m.done_ms    AS done_ms,
                   m.last_actual AS last_actual
            FROM public.wizard_cases c
            LEFT JOIN (
                SELECT case_id,
                       COUNT(*)                               AS total_ms,
                       COUNT(*) FILTER (WHERE status = 'done') AS done_ms,
                       MAX(actual_date)                        AS last_actual
                FROM public.case_milestones
                GROUP BY case_id
            ) m ON m.case_id = c.id
            WHERE upper(c.origin_country) = :origin
              AND upper(c.dest_country)   = :dest
            """
        ),
        {"origin": origin.upper(), "dest": dest.upper()},
    ).mappings().all()

    durations: List[int] = []
    for r in rows:
        created = _as_datetime(r.get("created_at"))
        if created is None:
            continue
        total_ms = int(r.get("total_ms") or 0)
        done_ms = int(r.get("done_ms") or 0)
        status = (r.get("status") or "").lower()
        is_completed = status in _TERMINAL_CASE_STATUSES or (total_ms > 0 and done_ms == total_ms)
        if not is_completed:
            continue
        end = _as_datetime(r.get("last_actual")) or _as_datetime(r.get("updated_at"))
        if end is None:
            continue
        durations.append(max((end - created).days, 0))
    return durations


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────


def processing_time_estimate(
    *,
    pathway_type: Optional[str],
    corridor: Tuple[str, str],
    profile_complexity: Optional[str] = None,
    employer_size: Optional[str] = None,
    session: Any = None,
) -> Optional[ProcessingTimeEstimate]:
    """Estimate processing time for a corridor as {p50_days, p90_days, ...}.

    Args:
        pathway_type:       e.g. 'EU_BLUE_CARD', 'LONG_STAY_VISA' — selects the
                            official range and labels the corridor's route.
        corridor:           (origin_iso, dest_iso), e.g. ('IN', 'DE').
        profile_complexity: Accepted for API stability and forward-compatibility.
                            Not yet used to sub-segment the sample: segmenting the
                            platform sample by complexity today would push every
                            corridor below MIN_PLATFORM_CASES. Reserved for when
                            case volume supports profile-level slices.
        employer_size:      Accepted for the same forward-compat reason (would
                            eventually branch Blue Card fast-track).
        session:            SQLAlchemy session for the platform-data branch. When
                            None, the platform branch is skipped and the estimate
                            comes straight from the official source.

    Returns the estimate, or ``None`` when no source is available (caller renders
    nothing — never a processing time without a source).
    """
    origin, dest = corridor

    # 1. Platform-data branch (only when we have a session to read from).
    if session is not None:
        try:
            durations = _fetch_completed_durations(session, origin, dest)
            empirical = estimate_from_durations(durations)
            if empirical is not None:
                p50, p90 = empirical
                return ProcessingTimeEstimate(
                    p50_days=p50,
                    p90_days=p90,
                    source="platform_data",
                    sample_size=len([d for d in durations if d is not None and d > 0]),
                    last_updated=datetime.now(timezone.utc).date().isoformat(),
                    source_url=None,
                )
        except Exception as exc:  # a DB hiccup must not deny the official fallback
            log.warning(
                "processing_time_estimate: platform branch failed for %s->%s (%s); "
                "falling back to official source",
                origin, dest, exc,
            )

    # 2. Official-source fallback.
    return _official_estimate(origin, dest, pathway_type)


# ──────────────────────────────────────────────────────────────────────────────
# Small helpers (stdlib only)
# ──────────────────────────────────────────────────────────────────────────────


def _as_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
