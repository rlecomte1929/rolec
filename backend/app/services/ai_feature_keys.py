"""
Canonical AI feature keys — Parker Step G.

``feature_key`` is the master attribution dimension for AI unit economics
(cost-per-feature, carbon-per-feature, per customer). Keep it a closed ``Literal``
set so an unknown key fails at edit time, not at runtime. When a new LLM-using
surface is added, register its key here first.
"""
from __future__ import annotations

from typing import Literal, Tuple, get_args

FeatureKey = Literal[
    "policy_assistant",   # policy_assistant_rag_engine.py
    "policy_extraction",  # llm_policy_extractor.py
    "passport_ocr",       # ocr_passport_extractor.py (GPT-4o vision)
    "passport_ocr_oss",   # passport_ocr_oss.py (self-hosted, Parker Step F)
]

# String constants for ergonomic, typo-proof call sites.
POLICY_ASSISTANT: FeatureKey = "policy_assistant"
POLICY_EXTRACTION: FeatureKey = "policy_extraction"
PASSPORT_OCR: FeatureKey = "passport_ocr"
PASSPORT_OCR_OSS: FeatureKey = "passport_ocr_oss"

ALL_FEATURE_KEYS: Tuple[FeatureKey, ...] = get_args(FeatureKey)


def is_valid_feature_key(value: str) -> bool:
    """True if ``value`` is one of the canonical feature keys."""
    return value in ALL_FEATURE_KEYS
