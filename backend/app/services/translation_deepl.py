"""DeepL Pro adapter for the Parker-I translation layer.

The ``deepl`` SDK is lazy-imported inside :func:`translate` so this module (and the
service that imports it) loads cleanly in environments without the dep — tests
monkeypatch :func:`translate` or the lazily-imported ``deepl`` module. When the API
key or SDK is absent we raise :class:`TranslationUnavailable` so the service falls
back to NLLB rather than 500-ing.
"""
from __future__ import annotations

import os

from .translation_types import AdapterResult, TranslationUnavailable

MODEL_VERSION = "deepl-pro"
# DeepL API Pro list price ≈ $25 per 1M characters → per-char USD. Recorded on the
# cache row so AI unit-economics (Step G) can roll it up once that merges.
USD_PER_CHAR = 25.0 / 1_000_000


def _deepl_source_lang(bcp47: str) -> str:
    """DeepL source codes are the bare uppercased primary subtag (e.g. 'en-US' → 'EN')."""
    return bcp47.split("-", 1)[0].upper()


def _deepl_target_lang(bcp47: str) -> str:
    """DeepL target codes keep a region for EN/PT; otherwise the primary subtag.

    DeepL requires EN-GB/EN-US (not bare EN) and PT-BR/PT-PT as *targets*. We pass
    the full code uppercased when a region is present, else the primary subtag.
    """
    if "-" in bcp47:
        primary, region = bcp47.split("-", 1)
        return f"{primary.upper()}-{region.upper()}"
    return bcp47.upper()


def translate(text: str, src: str, tgt: str) -> AdapterResult:
    api_key = os.getenv("DEEPL_API_KEY")
    if not api_key:
        raise TranslationUnavailable("DEEPL_API_KEY is not set")
    try:
        import deepl  # noqa: PLC0415 — lazy so the module imports without the SDK
    except ImportError as exc:  # pragma: no cover - exercised via monkeypatch
        raise TranslationUnavailable("deepl SDK is not installed") from exc

    try:
        translator = deepl.Translator(api_key)
        result = translator.translate_text(
            text,
            source_lang=_deepl_source_lang(src),
            target_lang=_deepl_target_lang(tgt),
        )
    except Exception as exc:  # deepl.DeepLException etc. → uniform fallback signal
        raise TranslationUnavailable(f"DeepL request failed: {exc}") from exc

    return AdapterResult(
        text=result.text,
        provider="deepl",
        model_version=MODEL_VERSION,
        cost_usd=round(len(text) * USD_PER_CHAR, 6),
        quality_score=None,
    )
