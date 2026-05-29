"""Per-document-type Extraction Agents."""

from .eu_residence_permit import (
    EU_RESIDENCE_PERMIT_AGENT_NAME,
    MRZ_FIELD_KEYS,
    RESIDENCE_PURPOSE_VOCABULARY,
    EuResidencePermitAgent,
    EuResidencePermitResult,
    load_eu_residence_permit_prompt,
)

__all__ = [
    "EU_RESIDENCE_PERMIT_AGENT_NAME",
    "MRZ_FIELD_KEYS",
    "RESIDENCE_PURPOSE_VOCABULARY",
    "EuResidencePermitAgent",
    "EuResidencePermitResult",
    "load_eu_residence_permit_prompt",
]
