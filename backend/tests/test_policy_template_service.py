"""N12/AIQ-852 — unified policy template schema + service.

Covers the five validation criteria for unifying the four legacy template systems
into one versioned schema + service, without breaking the W4 gap-fill.
"""
from __future__ import annotations

import os
import re
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pytest

from backend.app.services.policy_template_service import (
    PolicyTemplateSchema,
    PolicyTemplateService,
    TemplateBenefit,
)

_MIGRATION = os.path.join(
    _REPO_ROOT, "supabase", "migrations", "20260617010000_policy_templates_v2.sql"
)


# --- Criterion 1: LTA standard has >= 20 benefits ---------------------------


def test_lta_standard_has_at_least_20_benefits():
    svc = PolicyTemplateService()
    tmpl = svc.get_template(policy_type="LTA", generosity_tier="standard")
    assert isinstance(tmpl, PolicyTemplateSchema)
    assert tmpl.policy_type == "LTA"
    assert tmpl.generosity_tier == "standard"
    assert len(tmpl.benefits) >= 20
    assert all(isinstance(b, TemplateBenefit) for b in tmpl.benefits)


# --- Criterion 2: STA standard is a valid template --------------------------


def test_sta_standard_is_valid_template():
    svc = PolicyTemplateService()
    tmpl = svc.get_template(policy_type="STA", generosity_tier="standard")
    assert isinstance(tmpl, PolicyTemplateSchema)
    assert tmpl.policy_type == "STA"
    assert len(tmpl.benefits) >= 1
    # at least one STA benefit carries a numeric default (the new placeholder content)
    assert any(b.default_value is not None for b in tmpl.benefits)


def test_all_six_templates_present_with_semver():
    svc = PolicyTemplateService()
    templates = svc.list_templates()
    assert len(templates) >= 6  # 3 tiers x LTA + 3 tiers x STA
    ids = {t.template_id for t in templates}
    for tier in ("conservative", "standard", "premium"):
        assert f"LTA_{tier}" in ids
        assert f"STA_{tier}" in ids
    # version is semver (three dot-separated numeric parts), not free-text
    for t in templates:
        parts = t.version.split(".")
        assert len(parts) == 3 and all(p.isdigit() for p in parts), t.version


def test_get_template_unknown_raises():
    svc = PolicyTemplateService()
    with pytest.raises(KeyError):
        svc.get_template(policy_type="commuter", generosity_tier="standard")


def test_geography_industry_accepted_forward_compatible():
    svc = PolicyTemplateService()
    tmpl = svc.get_template(
        policy_type="LTA", generosity_tier="standard", geography="DE", industry="tech"
    )
    assert isinstance(tmpl, PolicyTemplateSchema)


# --- Criterion 3: migration creates the table and seeds >= 6 rows -----------


def test_migration_creates_rls_gated_table_and_seeds_six_templates():
    assert os.path.exists(_MIGRATION), "policy_templates_v2 migration file missing"
    sql = open(_MIGRATION, encoding="utf-8").read()
    # table + child table
    assert "CREATE TABLE IF NOT EXISTS public.policy_templates_v2" in sql
    assert "CREATE TABLE IF NOT EXISTS public.policy_template_benefits" in sql
    # version archiving mechanism (superseded_by FK)
    assert "superseded_by uuid REFERENCES public.policy_templates_v2(id)" in sql
    # RLS hard gates (CLAUDE.md): enable RLS + policy + revoke anon
    assert "ALTER TABLE public.policy_templates_v2 ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE public.policy_template_benefits ENABLE ROW LEVEL SECURITY" in sql
    assert "CREATE POLICY" in sql
    assert "REVOKE ALL ON public.policy_templates_v2 FROM anon" in sql
    assert "REVOKE ALL ON public.policy_template_benefits FROM anon" in sql
    # seeds >= 6 parent template rows (one '1.0.0' tuple per template row)
    parent_block = sql.split("INSERT INTO public.policy_template_benefits", 1)[0]
    assert parent_block.count("'1.0.0'") >= 6


def _parse_seed(sql):
    """Parse seed → {template_id: pk} and {(pk, benefit_key): (default_value, value_type)}."""
    parents = {}
    for m in re.finditer(r"\('([0-9a-f-]{36})',\s*'((?:LTA|STA)_\w+)',\s*'1\.0\.0'", sql):
        parents[m.group(2)] = m.group(1)
    benefits = {}
    for m in re.finditer(
        r"\('[0-9a-f-]{36}',\s*'([0-9a-f-]{36})',\s*'(\w+)',\s*(NULL|[0-9.]+),\s*'(\w+)'", sql
    ):
        pk, key, val, vtype = m.groups()
        benefits[(pk, key)] = (None if val == "NULL" else float(val), vtype)
    return parents, benefits


def test_migration_seed_matches_service_registry():
    """The migration seed must mirror the Python registry exactly (no drift)."""
    sql = open(_MIGRATION, encoding="utf-8").read()
    parents, benefits = _parse_seed(sql)
    svc = PolicyTemplateService()
    for t in svc.list_templates():
        assert t.template_id in parents, t.template_id
        pk = parents[t.template_id]
        for b in t.benefits:
            key = (pk, b.benefit_key)
            assert key in benefits, (t.template_id, b.benefit_key)
            seed_value, seed_vtype = benefits[key]
            assert seed_value == b.default_value, (t.template_id, b.benefit_key, seed_value, b.default_value)
            assert seed_vtype == b.value_type, (t.template_id, b.benefit_key, seed_vtype, b.value_type)


# --- Criterion 4: W4 gap-fill still works (template_default rows) -----------


def test_get_default_benefits_is_w4_compatible():
    svc = PolicyTemplateService()
    defaults = svc.get_default_benefits()  # default = LTA_standard
    assert defaults, "gap-fill defaults must be non-empty"
    # keyed by benefit-taxonomy key, matching the canonical LTA field taxonomy mapping
    for taxonomy_key in ("immigration", "temporary_housing", "schooling", "shipment"):
        assert taxonomy_key in defaults, taxonomy_key
        rule = defaults[taxonomy_key]
        # same shape the legacy snapshot_json benefit_rules carried
        assert set(rule.keys()) >= {
            "benefit_key",
            "benefit_category",
            "calc_type",
            "amount_value",
            "currency",
        }
        assert rule["amount_value"] is not None


def test_w4_resolve_template_defaults_uses_unified_service():
    from backend.app.services.policy_hr_review_service import _resolve_template_defaults

    class _DbNoTemplates:
        def list_default_policy_templates(self):
            return []  # legacy fallback would yield {} — unified path must win

    resolved = _resolve_template_defaults(_DbNoTemplates())
    assert resolved, "rewired gap-fill must resolve defaults via the unified service"
    assert "temporary_housing" in resolved


def test_w4_gap_fill_produces_template_default_items():
    """End-to-end: unmapped canonical fields get filled from unified defaults."""
    from backend.app.services.policy_template_first_import import (
        build_template_first_import_payload,
    )

    svc = PolicyTemplateService()
    defaults = svc.get_default_benefits()
    # No extracted clauses -> unmapped canonical fields fall back to template defaults.
    payload = build_template_first_import_payload([], [], template_defaults=defaults)
    items = payload["template_items"]
    statuses = [it.get("import_status") for it in items if isinstance(it, dict)]
    sources = [it.get("source") for it in items if isinstance(it, dict)]
    assert "template_default" in statuses
    assert "template_default" in sources


# --- Criterion 5: the four legacy systems still exist (deprecated, not deleted)


def test_legacy_template_systems_still_present():
    # 1. POLICY_TEMPLATES dict
    from backend.app.services.policy_config_templates import POLICY_TEMPLATES

    assert {"conservative", "standard", "premium"} <= set(POLICY_TEMPLATES)
    # 2. Starter per-service caps — [TPL-1/AIQ-1131] the legacy _TIER_CAPS dict was
    #    retired and ported verbatim into PolicyTemplateService.get_starter_template_caps().
    caps = PolicyTemplateService.get_starter_template_caps()
    assert {"conservative", "standard", "premium"} <= set(caps)
    assert caps["standard"]["home_search"] == 2500  # the cap _LTA_TIER_DEFAULTS lacks
    # 3. benefits_templates table router still mounted
    from backend.app.routers import policy_templates as benefits_templates_router

    assert benefits_templates_router.router is not None
    # 4. canonical LTA template (35-field tuple)
    from backend.app.services.policy_canonical_lta_template import (
        CANONICAL_LTA_TEMPLATE_FIELDS,
    )

    assert len(CANONICAL_LTA_TEMPLATE_FIELDS) == 35


# --- AIQ-889: category-level benchmark reference library --------------------

def test_benchmark_library_has_three_tiers_fourteen_categories():
    svc = PolicyTemplateService()
    lib = svc.get_benchmark_library()
    assert [t["tier"] for t in lib] == ["Conservative", "Standard", "Premium"]
    assert all(len(t["categories"]) == 14 for t in lib)
    total = sum(len(t["categories"]) for t in lib)
    assert total == 42  # count parity with the ported benefits_templates rows


def test_benchmark_library_currency_is_eur_not_coerced():
    svc = PolicyTemplateService()
    lib = svc.get_benchmark_library()
    currencies = {c["cap_currency"] for t in lib for c in t["categories"]}
    assert currencies == {"EUR"}


def test_benchmark_caps_monotonic_conservative_le_standard_le_premium():
    svc = PolicyTemplateService()
    by_tier = {t["tier"]: {c["code"]: c["cap_value"] for c in t["categories"]} for t in svc.get_benchmark_library()}
    for code in by_tier["Conservative"]:
        assert by_tier["Conservative"][code] <= by_tier["Standard"][code] <= by_tier["Premium"][code], code


def test_benchmark_library_preserves_provenance_and_units():
    svc = PolicyTemplateService()
    cats = svc.get_benchmark_library()[0]["categories"]
    assert all(c["benchmark_source"] for c in cats)
    assert {c["cap_unit"] for c in cats} <= {"month", "year", "per_move"}


def test_benchmark_does_not_disturb_lta_sta_registry():
    svc = PolicyTemplateService()
    ids = {t.template_id for t in svc.list_templates()}
    assert ids == {"LTA_conservative", "LTA_standard", "LTA_premium", "STA_conservative", "STA_standard", "STA_premium"}
