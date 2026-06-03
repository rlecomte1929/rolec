"""NLLB-200 adapter for the Parker-I translation layer.

NLLB-200 is reached over HTTP at ``TRANSLATION_NLLB_ENDPOINT`` (e.g. a Hugging Face
Inference Endpoint — see ADR-002). No heavy local-inference dependency is pulled in;
``requests`` is lazy-imported. When the endpoint is unset or the call fails we raise
:class:`TranslationUnavailable` so the service falls back to DeepL.
"""
from __future__ import annotations

import os

from .translation_types import AdapterResult, TranslationUnavailable

MODEL_VERSION = "nllb-200-distilled-600M"
# Self-hosted / managed-endpoint amortized cost ≈ $0.40 per 1M characters. Marginal
# cost is near-zero; recorded for cost attribution parity with the DeepL path.
USD_PER_CHAR = 0.40 / 1_000_000
_TIMEOUT_SECONDS = 30

# BCP-47 primary subtag → FLORES-200 code. Covers the common relocation corridors;
# unknown codes fall back to a Latin-script guess so the endpoint can still try.
_FLORES = {
    "en": "eng_Latn",
    "de": "deu_Latn",
    "fr": "fra_Latn",
    "es": "spa_Latn",
    "it": "ita_Latn",
    "pt": "por_Latn",
    "nl": "nld_Latn",
    "pl": "pol_Latn",
    "ja": "jpn_Jpan",
    "zh": "zho_Hans",
    "ar": "arb_Arab",
}


def _flores(bcp47: str) -> str:
    primary = bcp47.split("-", 1)[0].lower()
    return _FLORES.get(primary, f"{primary}_Latn")


def _auth_headers() -> dict:
    token = os.getenv("TRANSLATION_NLLB_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def translate(text: str, src: str, tgt: str) -> AdapterResult:
    endpoint = os.getenv("TRANSLATION_NLLB_ENDPOINT")
    if not endpoint:
        raise TranslationUnavailable("TRANSLATION_NLLB_ENDPOINT is not set")

    import requests  # noqa: PLC0415 — lazy import; mocked in tests

    try:
        resp = requests.post(
            endpoint.rstrip("/") + "/translate",
            json={"text": text, "source_lang": _flores(src), "target_lang": _flores(tgt)},
            headers=_auth_headers(),
            timeout=_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        raise TranslationUnavailable(f"NLLB request failed: {exc}") from exc

    translated = data.get("translated_text") or data.get("text")
    if not translated:
        raise TranslationUnavailable("NLLB endpoint returned no translation")

    return AdapterResult(
        text=translated,
        provider="nllb",
        model_version=data.get("model_version") or MODEL_VERSION,
        cost_usd=round(len(text) * USD_PER_CHAR, 6),
        quality_score=None,
    )
