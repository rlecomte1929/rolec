"""Classical, LLM-free NLG strategies (Parker framework W11).

Three deterministic NLG approaches, each suited to a different buyer artefact:
  - data_to_text       — executive KPI summaries
  - frame_based        — slot-filled incident / case reports
  - extractive_summarizer — TextRank TL;DR of long policy documents
"""
from . import data_to_text, extractive_summarizer, frame_based
from .data_to_text import KPI, KPISet, summarise_kpis
from .extractive_summarizer import summarise
from .frame_based import (
    Frame,
    MissingSlotError,
    UnknownFrameError,
    registered_event_types,
    render,
    translation_key_for,
)

__all__ = [
    "data_to_text",
    "frame_based",
    "extractive_summarizer",
    "KPI",
    "KPISet",
    "summarise_kpis",
    "Frame",
    "render",
    "registered_event_types",
    "translation_key_for",
    "MissingSlotError",
    "UnknownFrameError",
    "summarise",
]
