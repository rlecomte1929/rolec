"""
Immigration-partner adapter selector (AIQ-379c).

A single feature-flagged entry point that returns the active ``PartnerAdapter``.
Production sync code (AIQ-379d) depends on THIS, never on a concrete adapter, so
swapping mock → live (AIQ-379e) is an env-var change, not a code change.

Convention mirrors ``ai_feature_keys.py``: a closed ``Literal`` set so an unknown
mode fails loudly rather than silently picking a default.
"""
from __future__ import annotations

import os
from typing import Literal, Optional, Tuple, get_args

from .immigration_partner_adapter import PartnerAdapter

#: Env var that selects the adapter. Defaults to "mock" until AIQ-379e ships live.
ADAPTER_MODE_ENV = "IMMIGRATION_PARTNER_ADAPTER"

PartnerAdapterMode = Literal["mock", "live"]
ALL_ADAPTER_MODES: Tuple[PartnerAdapterMode, ...] = get_args(PartnerAdapterMode)
_DEFAULT_MODE: PartnerAdapterMode = "mock"


def get_partner_adapter(mode: Optional[str] = None) -> PartnerAdapter:
    """Return the active ``PartnerAdapter``.

    Resolution order: explicit ``mode`` arg → ``IMMIGRATION_PARTNER_ADAPTER`` env
    → ``"mock"``. Raises ``ValueError`` on an unknown mode and ``NotImplementedError``
    for ``"live"`` until AIQ-379e provides ``LivePartnerAdapter``.
    """
    resolved = (mode or os.environ.get(ADAPTER_MODE_ENV) or _DEFAULT_MODE).lower()

    if resolved == "mock":
        # Imported lazily so the contract module never depends on a concrete adapter.
        from .immigration_partner_mock import MockPartnerAdapter

        return MockPartnerAdapter()

    if resolved == "live":
        raise NotImplementedError(
            "LivePartnerAdapter ships in AIQ-379e. "
            f"Set {ADAPTER_MODE_ENV}=mock until then."
        )

    raise ValueError(
        f"Unknown {ADAPTER_MODE_ENV}={resolved!r}; expected one of {ALL_ADAPTER_MODES}."
    )
