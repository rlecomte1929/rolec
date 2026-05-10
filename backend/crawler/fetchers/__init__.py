"""Content fetchers for crawler pipeline."""

from .http_fetcher import fetch_page, FetchResult

__all__ = ["fetch_page", "FetchResult"]
