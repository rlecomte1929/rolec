"""Per-document-type Extraction Agents."""

from .diploma import (
    DIPLOMA_AGENT_NAME,
    DiplomaAgent,
    DiplomaResult,
    infer_isced_level_from_title,
    load_diploma_prompt,
)

__all__ = [
    "DIPLOMA_AGENT_NAME",
    "DiplomaAgent",
    "DiplomaResult",
    "infer_isced_level_from_title",
    "load_diploma_prompt",
]
