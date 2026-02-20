"""Plugin registry for recommendation categories."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .plugins import (
    LivingAreasPlugin,
    MoversPlugin,
    SchoolsPlugin,
    BanksPlugin,
    InsurancePlugin,
    ElectricityPlugin,
    MedicalPlugin,
    TelecomPlugin,
    ChildcarePlugin,
    StoragePlugin,
    TransportPlugin,
    LanguageIntegrationPlugin,
    LegalAdminPlugin,
    TaxFinancePlugin,
)
from .plugins.base import BasePlugin

_REGISTRY: Dict[str, BasePlugin] = {}


def _init_registry() -> None:
    plugins = [
        LivingAreasPlugin(),
        MoversPlugin(),
        SchoolsPlugin(),
        BanksPlugin(),
        InsurancePlugin(),
        ElectricityPlugin(),
        MedicalPlugin(),
        TelecomPlugin(),
        ChildcarePlugin(),
        StoragePlugin(),
        TransportPlugin(),
        LanguageIntegrationPlugin(),
        LegalAdminPlugin(),
        TaxFinancePlugin(),
    ]
    for p in plugins:
        _REGISTRY[p.key] = p


def get_plugin(category: str) -> Optional[BasePlugin]:
    """Get plugin by category key."""
    if not _REGISTRY:
        _init_registry()
    return _REGISTRY.get(category)


def list_categories() -> List[Dict[str, Any]]:
    """List all categories with key, title, and schema info."""
    if not _REGISTRY:
        _init_registry()
    result = []
    for key, plugin in _REGISTRY.items():
        schema = plugin.CriteriaModel.model_json_schema()
        result.append({
            "key": key,
            "title": plugin.title,
            "schema": schema,
        })
    return result
