"""Per-document-type Extraction Agents (C1-05b–f).

Each agent in this sub-package wraps the C1-05a runtime + the relevant
document-specific primitives (MRZ parser for passports, locale-aware
money parser for payslips, etc.). They register a Parsewise-style
:class:`ExtractionAgent` with the registry and orchestrate the deterministic
+ LLM-driven extraction layers into a single :class:`ExtractionRunResult`.

Currently implemented:

* :mod:`backend.relopass.agents.extraction.passport_td3` — C1-05b
"""

from .passport_td3 import (
    DI_FIELD_KEYS,
    LLM_FIELD_KEYS,
    MRZ_FIELD_KEYS,
    PASSPORT_TD3_AGENT,
    PASSPORT_TD3_AGENT_NAME,
    AzureDiPassportOutput,
    AzureDIProvider,
    Bbox,
    NullAzureDIProvider,
    PassportTd3Agent,
    PassportTd3Result,
    PHI_CLASS_BIOMETRIC,
    load_passport_td3_prompt,
)

__all__ = [
    "DI_FIELD_KEYS",
    "LLM_FIELD_KEYS",
    "MRZ_FIELD_KEYS",
    "PASSPORT_TD3_AGENT",
    "PASSPORT_TD3_AGENT_NAME",
    "PHI_CLASS_BIOMETRIC",
    "AzureDIProvider",
    "AzureDiPassportOutput",
    "Bbox",
    "NullAzureDIProvider",
    "PassportTd3Agent",
    "PassportTd3Result",
    "load_passport_td3_prompt",
]
