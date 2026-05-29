"""Per-document-type Extraction Agents.

Currently implemented:

* :mod:`backend.relopass.agents.extraction.payslip` — C1-05d (FR/DE/NO)
"""

from .payslip import (
    PAYSLIP_AGENT_NAME,
    Locale,
    PayslipAgent,
    PayslipResult,
    load_payslip_prompt,
)

__all__ = [
    "PAYSLIP_AGENT_NAME",
    "Locale",
    "PayslipAgent",
    "PayslipResult",
    "load_payslip_prompt",
]
