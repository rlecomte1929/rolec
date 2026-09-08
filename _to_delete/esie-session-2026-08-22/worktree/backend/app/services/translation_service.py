"""Parker-I neural translation layer — routing, caching, cost trace.

``translate()`` is the single public entry point. It:
  1. Returns a cache hit (sha256 of text|src|tgt|domain) with zero provider cost.
  2. Otherwise routes to a provider — premium tier OR short text (< 500 chars) → DeepL
     Pro; long text on the fast tier → NLLB-200. ``TRANSLATION_FORCE_PROVIDER`` overrides.
  3. Falls back to the other provider if the chosen one is unavailable (missing key /
     unset endpoint), and persists the result + records real spend on the cache row.
  4. Emits one structured JSON trace line (feature_key='translation') so the spend
     slots into Step G's AI-unit-economics rollup once that merges. DeepL/NLLB bill
     per *character*, not per token, so G's token→CO2e estimator is intentionally not
     used here — see this step's PLAN.md / RESULT.md (soft-dep fallback).
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Literal, Optional

from ..db import SessionLocal
from . import translation_cache_repo as cache_repo
from .translation_types import AdapterResult, TranslationUnavailable

log = logging.getLogger("relopass.translation")

QualityTier = Literal["fast", "premium"]
Domain = Literal["policy", "comm", "supplier", "ui"]

# Short text routes to premium DeepL even on the fast tier — cheap and higher quality.
DEEPL_MAX_CHARS = 500
_VALID_PROVIDERS = ("deepl", "nllb")


@dataclass
class Translation:
    text: str
    provider: str
    model_version: str
    cost_usd: float
    cache_hit: bool


def _choose_provider(text: str, quality_tier: str) -> str:
    forced = os.getenv("TRANSLATION_FORCE_PROVIDER")
    if forced in _VALID_PROVIDERS:
        return forced
    if quality_tier == "premium" or len(text) < DEEPL_MAX_CHARS:
        return "deepl"
    return "nllb"


def _invoke(provider: str, text: str, src: str, tgt: str) -> AdapterResult:
    """Call the chosen provider, falling back to the other on TranslationUnavailable.
    Adapters are imported lazily so this module loads without the deepl SDK / requests."""
    from . import translation_deepl, translation_nllb  # noqa: PLC0415 — lazy

    order = ["deepl", "nllb"] if provider == "deepl" else ["nllb", "deepl"]
    adapters = {"deepl": translation_deepl, "nllb": translation_nllb}
    last_exc: Optional[Exception] = None
    for name in order:
        try:
            return adapters[name].translate(text, src, tgt)
        except TranslationUnavailable as exc:
            last_exc = exc
            log.info("translation provider %s unavailable: %s", name, exc)
    raise TranslationUnavailable(
        f"no translation provider available (last: {last_exc})"
    )


def _trace(*, provider: str, src: str, tgt: str, domain: str, chars: int,
           cost_usd: float, cache_hit: bool) -> None:
    """Structured JSON trace line. feature_key='translation' keeps it compatible with
    Step G's AI-unit-economics rollup (add 'translation' to G's FeatureKey to ingest)."""
    log.info(json.dumps({
        "feature_key": "translation",
        "provider": provider,
        "source_lang": src,
        "target_lang": tgt,
        "domain": domain,
        "chars": chars,
        "cost_usd": cost_usd,
        "cache_hit": cache_hit,
    }))


def translate(
    text: str,
    src: str,
    tgt: str,
    *,
    domain: Domain = "comm",
    quality_tier: QualityTier = "fast",
    session=None,
) -> Translation:
    if not text or not text.strip():
        return Translation(text=text, provider="none", model_version="", cost_usd=0.0, cache_hit=False)

    own_session = session is None
    session = session or SessionLocal()
    try:
        source_hash = cache_repo.compute_hash(text, src, tgt, domain)
        cached = cache_repo.get_by_hash(session, source_hash)
        if cached is not None:
            _trace(provider=cached.provider, src=src, tgt=tgt, domain=domain,
                   chars=len(text), cost_usd=0.0, cache_hit=True)
            return Translation(
                text=cached.translated_text,
                provider=cached.provider,
                model_version=cached.model_version or "",
                cost_usd=0.0,
                cache_hit=True,
            )

        provider = _choose_provider(text, quality_tier)
        result = _invoke(provider, text, src, tgt)

        cache_repo.insert_translation(
            session,
            source_hash=source_hash,
            source_text=text,
            translated_text=result.text,
            source_lang=src,
            target_lang=tgt,
            domain=domain,
            provider=result.provider,
            model_version=result.model_version,
            quality_score=result.quality_score,
            cost_usd=result.cost_usd,
        )
        session.commit()
        _trace(provider=result.provider, src=src, tgt=tgt, domain=domain,
               chars=len(text), cost_usd=result.cost_usd, cache_hit=False)
        return Translation(
            text=result.text,
            provider=result.provider,
            model_version=result.model_version,
            cost_usd=result.cost_usd,
            cache_hit=False,
        )
    finally:
        if own_session:
            session.close()
