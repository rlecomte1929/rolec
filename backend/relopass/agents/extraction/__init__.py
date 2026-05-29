"""Per-document-type Extraction Agents (C1-05b–f).

Currently implemented:

* :mod:`backend.relopass.agents.extraction.employment_contract` — C1-05c
  (FR / DE / NO multi-jurisdiction)
"""

from .employment_contract import (
    EMPLOYMENT_CONTRACT_AGENT_NAME,
    EmploymentContractAgent,
    EmploymentContractResult,
    Jurisdiction,
    load_employment_contract_prompt,
)

__all__ = [
    "EMPLOYMENT_CONTRACT_AGENT_NAME",
    "EmploymentContractAgent",
    "EmploymentContractResult",
    "Jurisdiction",
    "load_employment_contract_prompt",
]
