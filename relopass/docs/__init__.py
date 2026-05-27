"""Document parsing and validation primitives (MRZ, ID cards, etc.)."""

from .mrz import (
    DocumentValidationFinding,
    CheckDigitResult,
    MRZParseResult,
    compute_check_digit,
    parse_mrz,
)

__all__ = [
    "DocumentValidationFinding",
    "CheckDigitResult",
    "MRZParseResult",
    "compute_check_digit",
    "parse_mrz",
]
