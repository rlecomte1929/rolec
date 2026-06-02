"""Persistence for the Parker-I translation cache.

ORM-backed via :class:`backend.app.models.TranslationCache` (String id → portable to
SQLite for tests). Dedup key is a sha256 of (text, src, tgt, domain); the Postgres
table enforces it with a UNIQUE constraint, this repo looks it up before any provider
call so a repeated translation is a cache hit with zero provider cost.
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Optional

from ..models import TranslationCache

_SEP = "\x1f"  # unit separator — unambiguous field delimiter for the hash input


def compute_hash(text: str, src: str, tgt: str, domain: str) -> str:
    raw = _SEP.join([text, src, tgt, domain or ""]).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def get_by_hash(session, source_hash: str) -> Optional[TranslationCache]:
    return (
        session.query(TranslationCache)
        .filter(TranslationCache.source_hash == source_hash)
        .one_or_none()
    )


def insert_translation(
    session,
    *,
    source_hash: str,
    source_text: str,
    translated_text: str,
    source_lang: str,
    target_lang: str,
    domain: str,
    provider: str,
    model_version: Optional[str],
    quality_score: Optional[float],
    cost_usd: float,
) -> TranslationCache:
    row = TranslationCache(
        id=str(uuid.uuid4()),
        source_hash=source_hash,
        source_text=source_text,
        translated_text=translated_text,
        source_lang=source_lang,
        target_lang=target_lang,
        domain=domain,
        provider=provider,
        model_version=model_version,
        quality_score=quality_score,
        cost_usd=cost_usd,
    )
    session.add(row)
    session.flush()
    return row
