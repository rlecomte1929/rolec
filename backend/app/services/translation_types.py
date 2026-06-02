"""Shared types for the Parker-I neural translation layer.

Kept in a dedicated module so the service and both adapters can import the result
type and the unavailable-signal without a circular import (the service imports the
adapters; the adapters import from here, not from the service).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class TranslationUnavailable(RuntimeError):
    """An adapter cannot service the request (missing API key, unset endpoint,
    SDK not installed, or a transport error). The service catches this to fall
    back to the other provider."""


@dataclass
class AdapterResult:
    text: str
    provider: str          # 'deepl' | 'nllb'
    model_version: str
    cost_usd: float
    quality_score: Optional[float] = None
