"""Per-document-type Extraction Agents.

The module-level ``EXTRACTION_AGENT_REGISTRY`` maps a document-type ``code``
(matching ``rce.document_types.code``) to the agent factory for that type. The
document classifier / orchestrator looks up the agent class by code here, so a
new document type is wired in by registering its factory in this map.
"""

from typing import Callable, Dict

from .diploma import (
    DIPLOMA_AGENT_NAME,
    DIPLOMA_DOCUMENT_TYPE,
    DiplomaAgent,
    DiplomaResult,
    infer_isced_level_from_title,
    load_diploma_prompt,
)
from .passport_td3 import (
    DI_FIELD_KEYS,
    LLM_FIELD_KEYS,
    MRZ_FIELD_KEYS,
    PASSPORT_TD3_AGENT,
    PASSPORT_TD3_AGENT_NAME,
    PHI_CLASS_BIOMETRIC,
    AzureDiPassportOutput,
    Bbox,
    NullAzureDIProvider,
    PassportTd3Agent,
    PassportTd3Result,
    load_passport_td3_prompt,
)
from .tax_cert_de import (
    TAX_CERT_DE_AGENT_NAME,
    TaxCertDeAgent,
    load_tax_cert_de_prompt,
)
from .tax_cert_fr import (
    TAX_CERT_FR_AGENT_NAME,
    TaxCertFrAgent,
    load_tax_cert_fr_prompt,
)
from .tax_cert_no import (
    TAX_CERT_NO_AGENT_NAME,
    TaxCertNoAgent,
    load_tax_cert_no_prompt,
)
from .id_card import (
    ID_CARD_AGENT_NAME,
    ID_CARD_DOCUMENT_TYPE,
    IdCardAgent,
    IdCardResult,
    load_id_card_prompt,
)
from .marriage_cert import (
    MARRIAGE_CERT_AGENT_NAME,
    MARRIAGE_CERT_DOCUMENT_TYPE,
    MarriageCertAgent,
    MarriageCertResult,
    load_marriage_cert_prompt,
)
from .birth_cert import (
    BIRTH_CERT_AGENT_NAME,
    BIRTH_CERT_DOCUMENT_TYPE,
    BirthCertAgent,
    BirthCertResult,
    ParentResolution,
    load_birth_cert_prompt,
)
from .foster_care_order import (
    DEPENDENCY_TYPES,
    FOSTER_CARE_ORDER_AGENT_NAME,
    FOSTER_CARE_ORDER_DOCUMENT_TYPE,
    FosterCareOrderAgent,
    FosterCareOrderResult,
    GuardianResolution,
    load_foster_care_order_prompt,
    normalize_dependency_type,
)
from .visa_permit import (
    VISA_PERMIT_AGENT_NAME,
    VISA_PERMIT_DOCUMENT_TYPE,
    VisaPermitAgent,
    VisaPermitResult,
    load_visa_permit_prompt,
)

# ─────────────────────────────────────────────────────────────────────────────
# Document-type → agent-class registry (C2-01 wiring)
# ─────────────────────────────────────────────────────────────────────────────
#
# Keyed by rce.document_types.code. The orchestrator resolves the agent for a
# classified document by looking up its code here. Values are the agent classes
# themselves (callers construct them with registry + sink + optional resolver).

EXTRACTION_AGENT_REGISTRY: Dict[str, Callable[..., object]] = {
    MARRIAGE_CERT_DOCUMENT_TYPE: MarriageCertAgent,
    BIRTH_CERT_DOCUMENT_TYPE: BirthCertAgent,
    FOSTER_CARE_ORDER_DOCUMENT_TYPE: FosterCareOrderAgent,
    ID_CARD_DOCUMENT_TYPE: IdCardAgent,
    VISA_PERMIT_DOCUMENT_TYPE: VisaPermitAgent,
    DIPLOMA_DOCUMENT_TYPE: DiplomaAgent,
}

# ─────────────────────────────────────────────────────────────────────────────
# Agents that exist but are deliberately NOT reachable yet, each with the reason.
# ─────────────────────────────────────────────────────────────────────────────
#
# The registry is keyed by document-type code, and the orchestrator selects with
# `_agent_class(document_type_code)` — the code is the ONLY input it receives.
#
# TaxCertDeAgent / TaxCertFrAgent / TaxCertNoAgent are three country-specific
# agents (each pins its own `_COUNTRY_ISO3`, e.g. "DEU") behind ONE prod
# document-type code, `TAX_CERT`. Selecting between them needs the issuing
# country, which is not available at the selection point: `dispatch_and_run`
# receives only `ocr_result`, `document_type_code`, `sink`, `agent_storage` and
# `resolver`. `document_subtype` cannot serve either — the agent EMITS it, so
# using it to choose the agent is circular.
#
# Registering an arbitrary one (e.g. DE) would silently run a German-specific
# prompt over a French tax certificate and emit confident, wrong fields. That is
# worse than the current skip, so TAX_CERT stays unreachable until a selector is
# designed. Tracked by test_extraction_agent_wiring.py, which fails if this entry
# is removed without the agents becoming reachable.
UNREACHABLE_AGENTS: Dict[str, str] = {
    "TaxCertDeAgent": "TAX_CERT selector undesigned — 3 country agents, 1 code, no country at the selection point",
    "TaxCertFrAgent": "TAX_CERT selector undesigned — see TaxCertDeAgent",
    "TaxCertNoAgent": "TAX_CERT selector undesigned — see TaxCertDeAgent",
}


def get_extraction_agent_class(document_type_code: str) -> Callable[..., object]:
    """Return the agent class registered for ``document_type_code``.

    Raises ``KeyError`` for an unregistered document type so the orchestrator
    surfaces a clear "no agent for this type" error rather than silently
    skipping extraction.
    """
    return EXTRACTION_AGENT_REGISTRY[document_type_code]


__all__ = [
    # diploma (C1-05e)
    "DIPLOMA_AGENT_NAME",
    "DiplomaAgent",
    "DiplomaResult",
    "infer_isced_level_from_title",
    "load_diploma_prompt",
    # passport_td3 (C1-05b) — MRZ+DI+LLM orchestrator; not in EXTRACTION_AGENT_REGISTRY
    # (its construction contract differs from the family agents' registry+sink path).
    "DI_FIELD_KEYS",
    "LLM_FIELD_KEYS",
    "MRZ_FIELD_KEYS",
    "PASSPORT_TD3_AGENT",
    "PASSPORT_TD3_AGENT_NAME",
    "PHI_CLASS_BIOMETRIC",
    "AzureDiPassportOutput",
    "Bbox",
    "NullAzureDIProvider",
    "PassportTd3Agent",
    "PassportTd3Result",
    "load_passport_td3_prompt",
    # tax_cert (C2-02b)
    "TAX_CERT_FR_AGENT_NAME",
    "TaxCertFrAgent",
    "load_tax_cert_fr_prompt",
    "TAX_CERT_DE_AGENT_NAME",
    "TaxCertDeAgent",
    "load_tax_cert_de_prompt",
    "TAX_CERT_NO_AGENT_NAME",
    "TaxCertNoAgent",
    "load_tax_cert_no_prompt",
    # id_card (C2-02 / C2-09 nationality source) — MRZ-deterministic
    "ID_CARD_AGENT_NAME",
    "ID_CARD_DOCUMENT_TYPE",
    "IdCardAgent",
    "IdCardResult",
    "load_id_card_prompt",
    # marriage_cert (C2-01)
    "MARRIAGE_CERT_AGENT_NAME",
    "MARRIAGE_CERT_DOCUMENT_TYPE",
    "MarriageCertAgent",
    "MarriageCertResult",
    "load_marriage_cert_prompt",
    # birth_cert (C2-01)
    "BIRTH_CERT_AGENT_NAME",
    "BIRTH_CERT_DOCUMENT_TYPE",
    "BirthCertAgent",
    "BirthCertResult",
    "ParentResolution",
    "load_birth_cert_prompt",
    # foster_care_order (C2-01)
    "DEPENDENCY_TYPES",
    "FOSTER_CARE_ORDER_AGENT_NAME",
    "FOSTER_CARE_ORDER_DOCUMENT_TYPE",
    "FosterCareOrderAgent",
    "FosterCareOrderResult",
    "GuardianResolution",
    "load_foster_care_order_prompt",
    "normalize_dependency_type",
    # visa_permit (AIQ-1309 follow-up)
    "VISA_PERMIT_AGENT_NAME",
    "VISA_PERMIT_DOCUMENT_TYPE",
    "VisaPermitAgent",
    "VisaPermitResult",
    "load_visa_permit_prompt",
    # registry wiring (C2-01)
    "EXTRACTION_AGENT_REGISTRY",
    "get_extraction_agent_class",
]
