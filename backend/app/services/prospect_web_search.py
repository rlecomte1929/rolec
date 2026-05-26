"""
Optional web search adjunct for the prospect enrichment agent.

Off by default. When the admin enables it for a batch, each prospect
triggers one Tavily search targeted at mobility signals (funding,
expansion, international hiring). Tavily chosen because its "search +
snippets" API maps cleanly onto LLM context without scraping.

Env:
  TAVILY_API_KEY   — required when web search is enabled per-batch.

Cost note (April 2026): Tavily basic search is roughly $0.005 per query.
500 prospects with one search each = ~$2.50. The admin UI surfaces an
estimate before the batch runs.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional

import requests

log = logging.getLogger(__name__)

TAVILY_ENDPOINT = "https://api.tavily.com/search"
DEFAULT_TIMEOUT_S = 15
DEFAULT_MAX_RESULTS = 5
# Keep public so the admin UI / pricing endpoint can surface a live estimate.
TAVILY_COST_PER_QUERY_USD = 0.005


@dataclass
class WebSearchResult:
    title: str
    url: str
    snippet: str


@dataclass
class ProspectWebSearchOutcome:
    query: str
    results: List[WebSearchResult] = field(default_factory=list)
    error: Optional[str] = None

    def to_prompt_text(self) -> str:
        if self.error:
            return f"WEB SEARCH ERROR ({self.query}): {self.error}"
        if not self.results:
            return f"WEB SEARCH ({self.query}): no results"
        lines = [f"WEB SEARCH ({self.query}):"]
        for r in self.results:
            lines.append(f"- {r.title} — {r.url}\n  {r.snippet}")
        return "\n".join(lines)


def _build_query(company_name: str) -> str:
    return (
        f'"{company_name}" '
        "(relocation OR \"international hiring\" OR \"global mobility\" "
        "OR \"new office\" OR expansion OR funding)"
    )


def run_prospect_web_search(
    company_name: str,
    *,
    api_key: Optional[str] = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> ProspectWebSearchOutcome:
    """Run one mobility-oriented search for the given company.

    Never raises on transport failure — the caller uses `.error` to
    decide whether to retry or fall back to website-only enrichment.
    """
    query = _build_query(company_name)
    key = api_key or os.getenv("TAVILY_API_KEY")
    if not key:
        return ProspectWebSearchOutcome(query=query, error="TAVILY_API_KEY not set")
    payload = {
        "api_key": key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
        "include_answer": False,
    }
    try:
        resp = requests.post(TAVILY_ENDPOINT, json=payload, timeout=timeout_s)
    except requests.RequestException as exc:
        return ProspectWebSearchOutcome(query=query, error=f"request failed: {exc}")
    if resp.status_code >= 400:
        return ProspectWebSearchOutcome(
            query=query,
            error=f"tavily http {resp.status_code}: {resp.text[:200]}",
        )
    try:
        data = resp.json()
    except ValueError as exc:
        return ProspectWebSearchOutcome(query=query, error=f"non-json: {exc}")
    results: List[WebSearchResult] = []
    for item in (data.get("results") or [])[:max_results]:
        results.append(
            WebSearchResult(
                title=str(item.get("title") or "")[:200],
                url=str(item.get("url") or ""),
                snippet=str(item.get("content") or "")[:500],
            )
        )
    return ProspectWebSearchOutcome(query=query, results=results)


def estimate_batch_cost_usd(prospect_count: int) -> float:
    """Approximate marginal cost of enabling web search for a batch."""
    return round(prospect_count * TAVILY_COST_PER_QUERY_USD, 4)
