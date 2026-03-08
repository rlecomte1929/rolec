"""
Resources module: public (published views) and admin (base tables) access.
"""
from .dto import (
    PublicResourceDto,
    PublicEventDto,
    PublicCategoryDto,
    PublicTagDto,
    ResourceContextDto,
    ResourcesPagePayload,
)
from .public_service import (
    get_resource_context,
    get_published_resources,
    get_published_events,
    get_recommended_resources,
    get_resources_page_data,
)
from .context_service import build_resource_context_from_draft

__all__ = [
    "PublicResourceDto",
    "PublicEventDto",
    "PublicCategoryDto",
    "PublicTagDto",
    "ResourceContextDto",
    "ResourcesPagePayload",
    "get_resource_context",
    "get_published_resources",
    "get_published_events",
    "get_recommended_resources",
    "get_resources_page_data",
    "build_resource_context_from_draft",
]
