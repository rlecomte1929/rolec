"""Per-document-type Extraction Agents.

The module-level ``EXTRACTION_AGENT_REGISTRY`` maps a document-type ``code``
(matching ``rce.document_types.code``) to the agent factory for that type. The
document classifier / orchestrator looks up the agent class by code here, so a
new document type is wired in by registering its factory in this map.
"""

from typing import Callable, Dict

from .diploma import (
    DIPLOMA_AGENT_NAME,
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
    # registry wiring (C2-01)
    "EXTRACTION_AGENT_REGISTRY",
    "get_extraction_agent_class",
]
