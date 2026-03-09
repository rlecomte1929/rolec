"""Deduplication logic for staged candidates."""

from .dedupe import check_resource_duplicate, check_event_duplicate

__all__ = ["check_resource_duplicate", "check_event_duplicate"]
