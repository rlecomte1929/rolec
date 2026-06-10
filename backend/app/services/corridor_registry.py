"""
Corridor registry (I-3) — declarative per-corridor config that is the single
source of truth for cross-cutting immigration concerns.

Stage 1 models **retrieval scope** (trust tiers + similarity floor). Later stages
add prompt version, intake follow-ups and SLA durations under the same corridor
identity. The eligibility "Corridor Agent" pathways (backend/relopass/corridors,
loaded separately) will be folded in under `pathways:` in the final stage.

Keyed by the canonical corridor id ``ORIGIN_DEST`` (underscore form, e.g.
``FR_NO``) — the same key ``immigration_corpus_chunks.corridor`` uses. Files live
at ``corridors/<ID>/corridor.yaml``.

**Fallback-safe by design:** an unknown corridor, a missing file, a parse error,
or an absent section returns ``None`` so every consumer keeps its current default
behaviour. This module never raises into a caller.
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

log = logging.getLogger(__name__)

# corridors/ lives at the repo root: this file is backend/app/services/<f>.py.
_DEFAULT_REGISTRY_DIR = Path(__file__).resolve().parents[3] / "corridors"

_CACHE: Dict[str, Optional["CorridorProfile"]] = {}
_LOCK = threading.Lock()


@dataclass(frozen=True)
class CorridorRetrievalScope:
    """Per-corridor retrieval scope. Any field None → consumer keeps its default."""

    trust_tiers: Optional[Tuple[int, ...]] = None
    min_similarity: Optional[float] = None


@dataclass(frozen=True)
class CorridorPromptConfig:
    """Per-corridor prompt selection (I-3 Stage 2). `task_key` names the
    prompt_registry task whose active version the immigration answer engine
    should use; the engine falls back to its module SYSTEM_PROMPT when the key
    is absent or has no registered version."""

    task_key: str


@dataclass(frozen=True)
class CorridorIntakeConfig:
    """Per-corridor intake follow-ups (I-3 Stage 3). `questions_file` is a
    filename resolved relative to the corridor's registry directory
    (corridors/<id>/); the interview engine falls back to the global question
    set when it is absent or the file is missing."""

    questions_file: str


@dataclass(frozen=True)
class CorridorSlaConfig:
    """Per-corridor timeline-SLA tunables (I-3 Stage 4). Override the
    sla_rules module defaults (AT_RISK_WINDOW_DAYS / AT_RISK_PCT) for the HR
    command-center timeline lens. Either field None → keep the module default."""

    at_risk_window_days: Optional[int] = None
    at_risk_pct: Optional[int] = None


@dataclass(frozen=True)
class CorridorProfile:
    corridor_id: str
    origin_iso: Optional[str] = None
    destination_iso: Optional[str] = None
    display_name: Optional[str] = None
    aliases: Tuple[str, ...] = ()
    retrieval: Optional[CorridorRetrievalScope] = None
    prompt: Optional[CorridorPromptConfig] = None
    intake: Optional[CorridorIntakeConfig] = None
    sla: Optional[CorridorSlaConfig] = None


def _registry_dir() -> Path:
    override = os.getenv("CORRIDOR_REGISTRY_DIR")
    return Path(override) if override else _DEFAULT_REGISTRY_DIR


def normalize_corridor_id(corridor: str) -> str:
    """Canonicalise to the underscore form, e.g. 'fr→no'/'FR-NO' → 'FR_NO'."""
    s = (corridor or "").strip().upper()
    for sep in ("→", "->", "-", " "):
        s = s.replace(sep, "_")
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_")


def _coerce_scope(raw: Any) -> Optional[CorridorRetrievalScope]:
    if not isinstance(raw, Mapping):
        return None
    tiers_raw = raw.get("trust_tiers")
    tiers: Optional[Tuple[int, ...]] = None
    if isinstance(tiers_raw, (list, tuple)) and tiers_raw:
        try:
            tiers = tuple(int(t) for t in tiers_raw)
        except (TypeError, ValueError):
            tiers = None
    min_sim_raw = raw.get("min_similarity")
    min_sim: Optional[float] = None
    if min_sim_raw is not None:
        try:
            min_sim = float(min_sim_raw)
        except (TypeError, ValueError):
            min_sim = None
    if tiers is None and min_sim is None:
        return None
    return CorridorRetrievalScope(trust_tiers=tiers, min_similarity=min_sim)


def _coerce_prompt(raw: Any) -> Optional[CorridorPromptConfig]:
    if not isinstance(raw, Mapping):
        return None
    task_key = raw.get("task_key")
    if not task_key or not str(task_key).strip():
        return None
    return CorridorPromptConfig(task_key=str(task_key).strip())


def _coerce_intake(raw: Any) -> Optional[CorridorIntakeConfig]:
    if not isinstance(raw, Mapping):
        return None
    qf = raw.get("questions_file")
    if not qf or not str(qf).strip():
        return None
    return CorridorIntakeConfig(questions_file=str(qf).strip())


def _coerce_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_sla(raw: Any) -> Optional[CorridorSlaConfig]:
    if not isinstance(raw, Mapping):
        return None
    window = _coerce_int(raw.get("at_risk_window_days"))
    pct = _coerce_int(raw.get("at_risk_pct"))
    if window is None and pct is None:
        return None
    return CorridorSlaConfig(at_risk_window_days=window, at_risk_pct=pct)


def _build_profile(corridor_id: str, doc: Mapping[str, Any]) -> CorridorProfile:
    block = doc.get("corridor") if isinstance(doc.get("corridor"), Mapping) else doc
    aliases_raw = block.get("aliases")
    aliases = tuple(str(a) for a in aliases_raw) if isinstance(aliases_raw, (list, tuple)) else ()
    return CorridorProfile(
        corridor_id=str(block.get("id") or corridor_id),
        origin_iso=(str(block["origin_iso"]) if block.get("origin_iso") else None),
        destination_iso=(str(block["destination_iso"]) if block.get("destination_iso") else None),
        display_name=(str(block["display_name"]) if block.get("display_name") else None),
        aliases=aliases,
        retrieval=_coerce_scope(block.get("retrieval")),
        prompt=_coerce_prompt(block.get("prompt")),
        intake=_coerce_intake(block.get("intake")),
        sla=_coerce_sla(block.get("sla")),
    )


def load_corridor_profile(corridor: str) -> Optional[CorridorProfile]:
    """Return the corridor's declarative profile, or None (fallback-safe).

    Cached per normalized id. A missing file / parse error / bad shape caches
    and returns None so consumers fall back to their defaults without retrying
    the filesystem on every call.
    """
    cid = normalize_corridor_id(corridor)
    if not cid:
        return None
    with _LOCK:
        if cid in _CACHE:
            return _CACHE[cid]
    profile: Optional[CorridorProfile] = None
    try:
        import yaml  # PyYAML is a prod dependency (backend/requirements.txt)

        path = _registry_dir() / cid / "corridor.yaml"
        if path.is_file():
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(doc, Mapping):
                profile = _build_profile(cid, doc)
    except Exception:  # noqa: BLE001 — registry must never break a consumer
        log.debug("corridor_registry: failed to load profile for %s", cid, exc_info=True)
        profile = None
    with _LOCK:
        _CACHE[cid] = profile
    return profile


def get_retrieval_scope(corridor: str) -> Optional[CorridorRetrievalScope]:
    """Convenience accessor for consumer #1 (immigration_retriever)."""
    profile = load_corridor_profile(corridor)
    return profile.retrieval if profile is not None else None


def get_prompt_config(corridor: str) -> Optional[CorridorPromptConfig]:
    """Convenience accessor for consumer #2 (immigration_answer_engine)."""
    profile = load_corridor_profile(corridor)
    return profile.prompt if profile is not None else None


def get_intake_config(corridor: str) -> Optional[CorridorIntakeConfig]:
    """Convenience accessor for consumer #3 (immigration_interview_engine)."""
    profile = load_corridor_profile(corridor)
    return profile.intake if profile is not None else None


def get_sla_config(corridor: str) -> Optional[CorridorSlaConfig]:
    """Convenience accessor for consumer #4 (HR command-center timeline SLA)."""
    profile = load_corridor_profile(corridor)
    return profile.sla if profile is not None else None


def get_intake_questions_path(corridor: str) -> Optional[Path]:
    """Resolve a corridor's intake question file to an existing absolute Path,
    or None (→ caller uses its global question set). Never raises."""
    try:
        cfg = get_intake_config(corridor)
        if cfg is None:
            return None
        path = _registry_dir() / normalize_corridor_id(corridor) / cfg.questions_file
        return path if path.is_file() else None
    except Exception:  # noqa: BLE001
        return None


def list_corridors() -> List[str]:
    """Canonical ids that have a corridor.yaml. Best-effort, never raises."""
    try:
        root = _registry_dir()
        if not root.is_dir():
            return []
        return sorted(
            p.name for p in root.iterdir()
            if p.is_dir() and (p / "corridor.yaml").is_file()
        )
    except Exception:  # noqa: BLE001
        return []


def _reset_cache_for_tests() -> None:
    with _LOCK:
        _CACHE.clear()
