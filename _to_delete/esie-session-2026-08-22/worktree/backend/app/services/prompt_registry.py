"""
Prompt registry + canary A/B (Parker Step D).

Versioned LLM system prompts / templates live in two tables:

* ``prompt_versions`` — one row per ``(task_key, version)``. Exactly one row per
  task_key may have ``status='prod'`` (enforced by a partial unique index). A
  ``status='canary'`` row may coexist; :func:`get_active_prompt` serves it with
  probability ``prompt_routing.canary_share``.
* ``prompt_routing`` — per-task canary share.

Contract for downstream steps (E/F/I): :class:`ActivePrompt` is the typed shape
returned by :func:`get_active_prompt`. ``canary_arm`` is ``'prod'`` or
``'canary'`` so callers can attribute traces to the arm that served the request.

**Consumer-fallback guarantee.** :func:`get_active_prompt` returns ``None`` when
the registry table is absent/empty or any read fails. Consumers MUST treat
``None`` as "use the literal constant" so nothing breaks before the migration is
applied.
"""
from __future__ import annotations

import logging
import random
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ..db import SessionLocal

log = logging.getLogger(__name__)

_DEFAULT_RNG = random.Random()
_VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
_VALID_STATUS = ("draft", "canary", "prod", "archived")


@dataclass(frozen=True)
class ActivePrompt:
    """The prompt configuration chosen for a single request."""

    id: str
    version: int
    system_prompt: str
    user_template: Optional[str]
    model_name: str
    temperature: float
    max_tokens: int
    canary_arm: str  # 'prod' | 'canary'


# ── Pure helpers ──────────────────────────────────────────────────────────────


def _pick_arm(canary_share: float, rng: random.Random) -> str:
    """Return ``'canary'`` with probability ``canary_share``, else ``'prod'``.

    Pure and deterministic for a seeded ``rng`` — unit-tested directly.
    """
    try:
        share = float(canary_share)
    except (TypeError, ValueError):
        return "prod"
    if share <= 0.0:
        return "prod"
    if share >= 1.0:
        return "canary"
    return "canary" if rng.random() < share else "prod"


def render_user_message(
    template: Optional[str], variables: Dict[str, Any]
) -> Optional[str]:
    """Substitute ``{{var}}`` placeholders. Returns ``None`` when template is None.

    Missing variables render as empty string. Not Jinja — deliberately a flat
    single-pass substitution so prompt authors can't inject control flow.
    """
    if template is None:
        return None

    def _repl(m: "re.Match[str]") -> str:
        val = variables.get(m.group(1))
        return "" if val is None else str(val)

    return _VAR_RE.sub(_repl, template)


# ── Read path (best-effort; never raises) ─────────────────────────────────────


def get_active_prompt(
    task_key: str,
    *,
    rng: Optional[random.Random] = None,
    session: Any = None,
) -> Optional[ActivePrompt]:
    """Resolve the active prompt for ``task_key``.

    Picks the ``prod`` row. When a ``canary`` row exists, serves it with
    probability ``prompt_routing.canary_share`` (``canary_arm='canary'``).
    Returns ``None`` when there is no prod row, the table is absent, or any
    read fails — consumers fall back to their literal constants.
    """
    rng = rng or _DEFAULT_RNG
    own = session is None
    s = session or SessionLocal()
    try:
        rows = (
            s.execute(
                text(
                    "SELECT id, version, system_prompt, user_template, model_name, "
                    "temperature, max_tokens, status FROM prompt_versions "
                    "WHERE task_key = :tk AND status IN ('prod', 'canary')"
                ),
                {"tk": task_key},
            )
            .mappings()
            .all()
        )
        prod = next((r for r in rows if r["status"] == "prod"), None)
        if prod is None:
            return None
        canary = next((r for r in rows if r["status"] == "canary"), None)

        share = 0.0
        if canary is not None:
            share_row = s.execute(
                text("SELECT canary_share FROM prompt_routing WHERE task_key = :tk"),
                {"tk": task_key},
            ).scalar()
            if share_row is not None:
                share = float(share_row)

        arm = _pick_arm(share, rng) if canary is not None else "prod"
        chosen = canary if (arm == "canary" and canary is not None) else prod
        return ActivePrompt(
            id=str(chosen["id"]),
            version=int(chosen["version"]),
            system_prompt=chosen["system_prompt"],
            user_template=chosen["user_template"],
            model_name=chosen["model_name"],
            temperature=float(chosen["temperature"]),
            max_tokens=int(chosen["max_tokens"]),
            canary_arm="canary" if chosen is canary else "prod",
        )
    except Exception:
        log.debug("get_active_prompt(%s): registry unavailable; consumer falls back", task_key, exc_info=True)
        return None
    finally:
        if own:
            s.close()


# ── Admin / write path (raises on error — admin needs feedback) ───────────────


def list_versions(task_key: Optional[str] = None, *, session: Any = None) -> List[Dict[str, Any]]:
    """All prompt versions, newest task/version first. Optionally filtered by task."""
    own = session is None
    s = session or SessionLocal()
    try:
        sql = (
            "SELECT id, task_key, version, system_prompt, user_template, model_name, "
            "temperature, max_tokens, status, created_at, notes FROM prompt_versions"
        )
        params: Dict[str, Any] = {}
        if task_key:
            sql += " WHERE task_key = :tk"
            params["tk"] = task_key
        sql += " ORDER BY task_key ASC, version DESC"
        rows = s.execute(text(sql), params).mappings().all()
        return [dict(r) for r in rows]
    finally:
        if own:
            s.close()


def create_version(
    *,
    task_key: str,
    system_prompt: str,
    model_name: str,
    user_template: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 1024,
    status: str = "draft",
    notes: Optional[str] = None,
    created_by: Optional[str] = None,
    session: Any = None,
) -> Dict[str, Any]:
    """Insert a new version for ``task_key`` (auto-incremented version number)."""
    if status not in _VALID_STATUS:
        raise ValueError(f"invalid status: {status}")
    own = session is None
    s = session or SessionLocal()
    try:
        max_v = s.execute(
            text("SELECT COALESCE(MAX(version), 0) FROM prompt_versions WHERE task_key = :tk"),
            {"tk": task_key},
        ).scalar()
        next_v = int(max_v or 0) + 1

        # When inserting straight to prod, demote any existing prod first so the
        # partial unique index (one prod per task) is never violated.
        if status == "prod":
            s.execute(
                text(
                    "UPDATE prompt_versions SET status = 'archived' "
                    "WHERE task_key = :tk AND status = 'prod'"
                ),
                {"tk": task_key},
            )

        s.execute(
            text(
                "INSERT INTO prompt_versions "
                "(task_key, version, system_prompt, user_template, model_name, "
                " temperature, max_tokens, status, notes, created_by) "
                "VALUES (:tk, :v, :sp, :ut, :mn, :temp, :mt, :st, :notes, :cb)"
            ),
            {
                "tk": task_key,
                "v": next_v,
                "sp": system_prompt,
                "ut": user_template,
                "mn": model_name,
                "temp": temperature,
                "mt": max_tokens,
                "st": status,
                "notes": notes,
                "cb": created_by,
            },
        )
        row = (
            s.execute(
                text(
                    "SELECT id, task_key, version, status FROM prompt_versions "
                    "WHERE task_key = :tk AND version = :v"
                ),
                {"tk": task_key, "v": next_v},
            )
            .mappings()
            .first()
        )
        s.commit()
        return dict(row) if row else {"task_key": task_key, "version": next_v, "status": status}
    except Exception:
        s.rollback()
        raise
    finally:
        if own:
            s.close()


def promote(version_id: str, target_status: str, *, session: Any = None) -> Dict[str, Any]:
    """Move a version to ``target_status``.

    Promoting to ``'prod'`` first demotes the task's current prod row to
    ``'archived'`` so the one-prod-per-task invariant holds.
    """
    if target_status not in _VALID_STATUS:
        raise ValueError(f"invalid status: {target_status}")
    own = session is None
    s = session or SessionLocal()
    try:
        cur = (
            s.execute(
                text("SELECT id, task_key FROM prompt_versions WHERE id = :id"),
                {"id": version_id},
            )
            .mappings()
            .first()
        )
        if cur is None:
            raise ValueError(f"unknown version_id: {version_id}")
        task_key = cur["task_key"]

        if target_status == "prod":
            s.execute(
                text(
                    "UPDATE prompt_versions SET status = 'archived' "
                    "WHERE task_key = :tk AND status = 'prod' AND id <> :id"
                ),
                {"tk": task_key, "id": version_id},
            )
        s.execute(
            text("UPDATE prompt_versions SET status = :st WHERE id = :id"),
            {"st": target_status, "id": version_id},
        )
        s.commit()
        return {"id": str(version_id), "task_key": task_key, "status": target_status}
    except Exception:
        s.rollback()
        raise
    finally:
        if own:
            s.close()


def set_canary_share(task_key: str, canary_share: float, *, session: Any = None) -> Dict[str, Any]:
    """Upsert the canary share for ``task_key`` (clamped to [0, 1])."""
    share = max(0.0, min(1.0, float(canary_share)))
    own = session is None
    s = session or SessionLocal()
    try:
        updated = s.execute(
            text("UPDATE prompt_routing SET canary_share = :cs WHERE task_key = :tk"),
            {"cs": share, "tk": task_key},
        ).rowcount
        if not updated:
            s.execute(
                text(
                    "INSERT INTO prompt_routing (task_key, canary_share) VALUES (:tk, :cs)"
                ),
                {"tk": task_key, "cs": share},
            )
        s.commit()
        return {"task_key": task_key, "canary_share": share}
    except Exception:
        s.rollback()
        raise
    finally:
        if own:
            s.close()
