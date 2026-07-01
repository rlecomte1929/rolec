"""Setup & Help Assistant knowledge base.

A curated, bounded, read-only how-to corpus for HR users covering the ReloPass
setup chain (company profile -> policy -> case -> invite) plus core feature
how-tos. The corpus is intentionally small so it fits a prompt-cached system
block; the assistant grounds answers in it and must not invent features/steps.
"""
from .knowledge_base import (
    load_setup_guide,
    render_for_prompt,
    topic_ids,
    all_routes,
)

__all__ = [
    "load_setup_guide",
    "render_for_prompt",
    "topic_ids",
    "all_routes",
]
