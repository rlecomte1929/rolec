"""ReloPass scheduled jobs — deterministic, vendor-SDK-free primitives.

Jobs in this package are the planner/orchestration side of recurring work
(rule scraping, freshness sweeps, etc.). Per the
:file:`backend/relopass/__init__.py` constraint, modules here MUST NOT import
from ``backend/app/``, FastAPI, SQLAlchemy, or any vendor SDK. Network I/O and
persistence are expressed as injected Protocols so the jobs run hermetically in
tests; the concrete httpx fetcher and Supabase writer live one layer up in the
service layer and the Edge Function that the cron invokes.

Created as part of C2-04 (AIQ-555 · UDI/BAMF/dejure rule-change scraper).
"""

from .rule_scraper import (
    RULE_SCRAPER_SOURCES,
    HtmlFetcher,
    ProposalStatus,
    RuleChangeProposal,
    RuleScraper,
    RuleSource,
    ScrapeResult,
    InMemoryProposalStore,
    ProposalStore,
    normalize_text,
    sha256_hex,
)

__all__ = [
    "RULE_SCRAPER_SOURCES",
    "HtmlFetcher",
    "InMemoryProposalStore",
    "ProposalStatus",
    "ProposalStore",
    "RuleChangeProposal",
    "RuleScraper",
    "RuleSource",
    "ScrapeResult",
    "normalize_text",
    "sha256_hex",
]
