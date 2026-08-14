"""Recommendation engine orchestration."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .explanation import build_explanation
from .registry import get_plugin
from .weights import derive_segment
from . import tiering
from .types import (
    RecommendationExplanation,
    RecommendationItem,
    RecommendationResponse,
    RecommendationTier,
)

logger = logging.getLogger(__name__)


def _absolute_tier(score: float) -> RecommendationTier:
    """Legacy absolute thresholds (85/70/50) — the cluster-tiering fallback."""
    if score >= 85:
        return RecommendationTier.BEST_MATCH
    if score >= 70:
        return RecommendationTier.GOOD_FIT
    if score >= 50:
        return RecommendationTier.OK
    return RecommendationTier.WEAK


def _country_iso2(criteria: Dict[str, Any]) -> Optional[str]:
    cc = (criteria.get("destination_country") or "").strip().upper()[:2]
    return cc or None


def _load_cluster_cache(
    category: str, country_iso2: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Load the latest supplier_cluster_cache cell. Best-effort, never raises.

    Returns ``None`` when the country is unknown, the table is absent (pre-
    migration), or the cell has never been refreshed — callers then tier with
    absolute thresholds.
    """
    if not country_iso2:
        return None
    try:
        from sqlalchemy import text

        from ..db import SessionLocal

        sql = text(
            """
            select cluster_size, thresholds_json, supplier_ids_json
            from public.supplier_cluster_cache
            where service_category = :cat and country_iso2 = :cc
            order by computed_at desc
            limit 1
            """
        )
        with SessionLocal() as session:
            row = session.execute(sql, {"cat": category, "cc": country_iso2}).first()
        if row is None:
            return None
        return {
            "cluster_size": row[0] or 0,
            "thresholds_json": row[1] or {},
            "supplier_ids_json": row[2] or {},
        }
    except Exception:
        return None


def _cluster_tier_for(
    score: float, supplier_id: Optional[str], cache: Optional[Dict[str, Any]]
) -> Optional[RecommendationTier]:
    """Cluster-relative tier for one supplier, or ``None`` if not applicable."""
    if cache is None or not supplier_id:
        return None
    if (cache.get("cluster_size") or 0) < tiering.MIN_CLUSTER_CELL:
        return None
    ids_by_cluster = cache.get("supplier_ids_json") or {}
    thresholds = cache.get("thresholds_json") or {}
    for cid, ids in ids_by_cluster.items():
        if str(supplier_id) in [str(x) for x in ids]:
            try:
                return tiering.tier_with_cluster_context(score, int(cid), thresholds)
            except (KeyError, ValueError):
                return None
    return None


def tier(
    score: float,
    *,
    category: Optional[str] = None,
    country_iso2: Optional[str] = None,
    supplier_id: Optional[str] = None,
    cache: Optional[Dict[str, Any]] = None,
    plugin: Any = None,
) -> RecommendationTier:
    """Tier a normalized score, cluster-relative when a refreshed cell covers it.

    Dispatches to ``tiering.tier_with_cluster_context`` when ``cache`` holds the
    supplier's (category, country) cell with >= MIN_CLUSTER_CELL suppliers; else
    falls back to ``plugin.tier`` (or absolute thresholds) and bumps the
    ``cluster_tiering_fallback_total`` counter.
    """
    result = _cluster_tier_for(score, supplier_id, cache)
    if result is not None:
        return result
    tiering.incr_fallback()
    if plugin is not None:
        return plugin.tier(score)
    return _absolute_tier(score)


def _load_dataset_with_registry(category: str, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Load recommendation candidates. Supplier Registry is primary when it has data;
    static JSON is fallback when registry returns zero items.
    """
    plugin = get_plugin(category)
    static_dataset = plugin.load_dataset() if plugin else []

    # Advisory categories (e.g. living_areas neighbourhoods) are ranked from the
    # static/geo dataset only — the supplier registry must not shadow the rich rows
    # with field-poor supplier shells. Skip the registry entirely for them.
    if getattr(plugin, "advisory", False):
        return list(static_dataset)

    registry_items: List[Dict[str, Any]] = []
    try:
        from ..db import SessionLocal
        from ..services.supplier_registry import search_by_service_destination

        dest_city = (criteria.get("destination_city") or "").strip()
        dest_country = (criteria.get("destination_country") or "").strip()
        if dest_city or dest_country:
            with SessionLocal() as session:
                registry_items = search_by_service_destination(
                    session,
                    service_category=category,
                    destination_city=dest_city or None,
                    destination_country=dest_country or None,
                    limit=50,
                )
    except Exception:
        pass

    if registry_items:
        # Registry is primary: use registry items, optionally merge non-duplicate static items
        existing_ids = {str((r.get("item_id") or "")) for r in registry_items}
        # AIQ-1690: a registry candidate (item_id = supplier id) and its legacy static
        # twin (item_id = 'm-N') are the SAME supplier but never collide on item_id, so
        # both used to be scored — one supplier could occupy two of the top_n slots and
        # push a different distinct approved supplier below the cut (apply_hr_curation
        # dedups by master id, but only after the cut). The link is the master's
        # supplier_id. Best-effort: if the catalog is unreachable, merge as before.
        try:
            from ..services.service_catalog import external_ids_for_supplier_ids
            twin_ids = external_ids_for_supplier_ids(category, sorted(existing_ids))
        except Exception:
            twin_ids = set()
        dataset = list(registry_items)
        for d in static_dataset:
            iid = str((d.get("item_id") or ""))
            if iid and iid not in existing_ids and iid not in twin_ids:
                dataset.append(d)
                existing_ids.add(iid)
    else:
        # Fallback: static JSON only when registry has no matching suppliers
        dataset = list(static_dataset)

    return dataset


def recommend(
    category: str,
    criteria: Dict[str, Any],
    top_n: int = 10,
    company_id: Optional[str] = None,
) -> RecommendationResponse:
    """
    Run recommendation for a category with given criteria.

    When `company_id` is supplied, the result is filtered through the
    employee-recommendations-filter (Phase 2c): only master items HR has
    explicitly approved for the company are kept, and HR custom vendors
    are appended. When HR has zero approvals for the (company, category,
    destination_city) scope, the response returns an empty list with
    `criteria_echo.hr_curation_status = 'hr_pending'` so the UI can render
    a "HR is finalizing providers" placeholder rather than the raw master.

    When `company_id` is None (admin debug, internal jobs), the filter is
    skipped — the legacy un-curated behavior is preserved.
    """
    plugin = get_plugin(category)
    if not plugin:
        raise ValueError(f"Unknown category: {category}")

    criteria_obj = plugin.validate_and_parse(criteria)
    dataset = _load_dataset_with_registry(category, criteria)

    scored_items: List[Dict[str, Any]] = []
    for item in dataset:
        try:
            result = plugin.score(criteria_obj, item)
        except Exception:
            # One malformed item must not blank the whole category. Drop it (score 0)
            # and keep ranking the rest. (Was: any raise propagated out of recommend()
            # and _run_one returned an empty block → the "(0)" / hr_pending symptom.)
            logger.exception(
                "recommendation score() failed category=%s item_id=%s",
                category, (item or {}).get("item_id"),
            )
            continue
        score_raw = result.get("score_raw") or 0.0
        # Admin/manual ranking boost (supplier_registry): add directly to raw score so it affects rank
        admin_score = item.get("_admin_score")
        if admin_score is not None:
            try:
                score_raw = score_raw + float(admin_score)
            except (TypeError, ValueError):
                pass
        manual_priority = item.get("_manual_priority")
        if manual_priority is not None:
            try:
                score_raw = score_raw + int(manual_priority) * 2.0  # scale so priority 10 => +20 raw
            except (TypeError, ValueError):
                pass
        scored_items.append({
            "item": item,
            **result,
            "score_raw": score_raw,
        })

    raw_scores = [s["score_raw"] for s in scored_items]
    norm_scores = plugin.normalize(raw_scores)

    cc = _country_iso2(criteria)
    cluster_cache = _load_cluster_cache(category, cc)

    for i, sc in enumerate(scored_items):
        sc["norm_score"] = norm_scores[i] if i < len(norm_scores) else 0
        sc["tier"] = tier(
            sc["norm_score"],
            category=category,
            country_iso2=cc,
            supplier_id=str((sc.get("item") or {}).get("item_id") or ""),
            cache=cluster_cache,
            plugin=plugin,
        )

    # Filter out items that don't match destination (score 0 = wrong city, etc.)
    matching = [s for s in scored_items if s["score_raw"] > 0]

    preferred_ids: set = set()
    for sid in (criteria.get("_preferred_supplier_ids") or []):
        if sid:
            preferred_ids.add(str(sid))

    def _is_preferred(x: Dict[str, Any]) -> bool:
        item = x.get("item") or {}
        iid = str(item.get("item_id") or "")
        if iid in preferred_ids:
            return True
        return bool(item.get("_preferred_partner"))

    # Deterministic ranking: preferred first (boost), then score desc, then item_id/name asc
    PREFERRED_BOOST = 15  # Add to norm_score so preferred rank higher
    for s in matching:
        if _is_preferred(s):
            s["norm_score"] = (s.get("norm_score") or 0) + PREFERRED_BOOST
            s["_company_preferred"] = True
            s["tier"] = tier(
                min(100, s["norm_score"]),
                category=category,
                country_iso2=cc,
                supplier_id=str((s.get("item") or {}).get("item_id") or ""),
                cache=cluster_cache,
                plugin=plugin,
            )
        else:
            s["_company_preferred"] = False

    matching.sort(
        key=lambda x: (
            -(x.get("norm_score") or 0),
            str((x.get("item") or {}).get("item_id") or ""),
            str((x.get("item") or {}).get("name") or ""),
        )
    )
    # AIQ-1700: when HR curation will run, build items for the FULL ranked list and
    # slice AFTER curating. Slicing first meant curation only ever saw the top_n, so a
    # supplier HR approved but that ranked below the cut was discarded before the
    # allowlist was ever consulted — 74 of 78 companies rendered fewer providers than
    # they had approved. On the un-curated path (admin debug, advisory categories) the
    # slice is unchanged and still bounds the work.
    will_curate = bool(company_id) and not getattr(plugin, "advisory", False)
    top = matching if will_curate else matching[:top_n]

    items: List[RecommendationItem] = []
    for t in top:
        item = t["item"]
        avail = t.get("metadata", {}).get("availability_level", "high")
        company_preferred = t.get("_company_preferred", False)

        expl_dict = build_explanation(item, t, criteria, category)
        explanation = RecommendationExplanation(**expl_dict)

        rec = RecommendationItem(
            item_id=item.get("item_id", ""),
            name=item.get("name", ""),
            score=round(min(100, t["norm_score"]), 1),  # Cap score display at 100
            tier=t["tier"],
            summary=t.get("summary", ""),
            rationale=t.get("rationale", ""),
            breakdown=t.get("breakdown", {}),
            pros=t.get("pros", []),
            cons=t.get("cons", []),
            metadata={
                **(t.get("metadata") or {}),
                "availability_level": avail,
                "company_preferred": company_preferred,
            },
            explanation=explanation,
        )
        items.append(rec)

    criteria_echo = _sanitize_criteria(criteria)
    # Add office address for map directions (living areas, schools)
    dest_city = (criteria.get("destination_city") or "").strip()
    office = (criteria.get("office_address") or "").strip()
    criteria_echo["office_address"] = office or _default_office_for_city(dest_city)
    # Phase 2: surface the geocoded office coords so the neighborhood map can pin
    # the office without a second client-side geocode.
    if criteria.get("office_lat") is not None and criteria.get("office_lng") is not None:
        criteria_echo["office_lat"] = criteria.get("office_lat")
        criteria_echo["office_lng"] = criteria.get("office_lng")
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    hr_curation_status: Optional[str] = None
    if will_curate:
        # Phase 2c — filter through HR's curation. Advisory categories (neighbourhood
        # overviews) are informational content, not vendors, so they are never gated:
        # gating them dropped every la-* row against the never-seeded catalog masters
        # → ([], 'hr_pending') → the Living Areas = 0 symptom.
        from ..services.employee_recommendations_filter import apply_hr_curation
        dest_country = (criteria.get("destination_country") or "").strip() or None
        items, hr_curation_status = apply_hr_curation(
            category=category,
            items=items,
            company_id=company_id,
            destination_city=dest_city or None,
            destination_country=dest_country,
        )
        # Show-all-vetted (2026-07-27, product decision): the employee must be able to
        # REACH every vetted provider, so we no longer drop masters beyond top_n. Return
        # the FULL curated set (ranked); `display_cap` + `masters_capped_by_display_limit`
        # tell the client to default to the top `top_n` and reveal the rest via a
        # "Show N more" control. top_n is a DISPLAY default here, not a hard cut — the
        # vetting/eligibility gate (apply_hr_curation) is untouched, and the top-`top_n`
        # ranking order is unchanged (AIQ-1700/1722 lineage; superseded cap-as-drop).
        _curated_masters = sum(1 for it in items if not (it.metadata or {}).get("hr_custom"))
        _beyond_cap = max(0, _curated_masters - top_n)
        if _beyond_cap > 0:
            criteria_echo["masters_capped_by_display_limit"] = _beyond_cap
            criteria_echo["display_cap"] = top_n
            logger.info(
                "recommendations: %d vetted %s master(s) beyond display_cap %d are "
                "reachable via expand for company=%s (curated=%d)",
                _beyond_cap, category, top_n, company_id, _curated_masters,
            )
        if hr_curation_status:
            criteria_echo["hr_curation_status"] = hr_curation_status

    response = RecommendationResponse(
        category=category,
        generated_at=generated_at,
        criteria_echo=criteria_echo,
        recommendations=items,
    )

    # AIQ-1694: production-time AI-decision audit record (PII-masked input + the model
    # output), so an overseer's later accept/override/reject links back to what was shown.
    # Deduped by a stable id (same picks → one 'produced' row, not one per page-view) and
    # company-scoped (no company → no tenant to audit). Only logs a NON-EMPTY result — an
    # empty/hr_pending response is not a recommendation to audit. Side-effect only +
    # best-effort: never alters or blocks the recommendation.
    if company_id and items:
        try:
            from ..services.ai_decision_logger import (
                record_ai_recommendation,
                stable_recommendation_id,
            )
            rec_id = stable_recommendation_id(
                company_id, category, *[it.item_id for it in items]
            )
            record_ai_recommendation(
                feature=f"supplier_reco:{category}",
                recommendation_id=rec_id,
                input_context=criteria_echo,
                ai_output=response.model_dump(mode="json"),
                company_id=company_id,
                model_name="rule-based",
                skip_if_exists=True,
            )
        except Exception:  # audit logging must never affect the recommendation
            pass

    return response


def recommend_debug(
    category: str,
    criteria: Dict[str, Any],
    top_n: int = 100,
) -> Dict[str, Any]:
    """
    Same as recommend() but returns debug payload: criteria_echo, dataset_count,
    and full ranked list with score_raw, norm_score, preferred, item_id, name, tier.
    Used by GET /api/admin/recommendations/debug.
    """
    plugin = get_plugin(category)
    if not plugin:
        raise ValueError(f"Unknown category: {category}")

    criteria_obj = plugin.validate_and_parse(criteria)
    dataset = _load_dataset_with_registry(category, criteria)

    scored_items = []
    for item in dataset:
        try:
            result = plugin.score(criteria_obj, item)
        except Exception:
            logger.exception(
                "recommendation score() failed (debug) category=%s item_id=%s",
                category, (item or {}).get("item_id"),
            )
            continue
        score_raw = result.get("score_raw") or 0.0
        admin_score = item.get("_admin_score")
        if admin_score is not None:
            try:
                score_raw = score_raw + float(admin_score)
            except (TypeError, ValueError):
                pass
        manual_priority = item.get("_manual_priority")
        if manual_priority is not None:
            try:
                score_raw = score_raw + int(manual_priority) * 2.0
            except (TypeError, ValueError):
                pass
        scored_items.append({"item": item, **result, "score_raw": score_raw})

    raw_scores = [s["score_raw"] for s in scored_items]
    norm_scores = plugin.normalize(raw_scores)
    cc = _country_iso2(criteria)
    cluster_cache = _load_cluster_cache(category, cc)
    for i, sc in enumerate(scored_items):
        sc["norm_score"] = norm_scores[i] if i < len(norm_scores) else 0
        sc["tier"] = tier(
            sc["norm_score"],
            category=category,
            country_iso2=cc,
            supplier_id=str((sc.get("item") or {}).get("item_id") or ""),
            cache=cluster_cache,
            plugin=plugin,
        )

    matching = [s for s in scored_items if s["score_raw"] > 0]
    preferred_ids = {str(sid) for sid in (criteria.get("_preferred_supplier_ids") or []) if sid}

    def _is_preferred(x):
        it = x.get("item") or {}
        iid = str(it.get("item_id") or "")
        return iid in preferred_ids or bool(it.get("_preferred_partner"))

    PREFERRED_BOOST = 15
    for s in matching:
        if _is_preferred(s):
            s["norm_score"] = (s.get("norm_score") or 0) + PREFERRED_BOOST
            s["_company_preferred"] = True
            s["tier"] = tier(
                min(100, s["norm_score"]),
                category=category,
                country_iso2=cc,
                supplier_id=str((s.get("item") or {}).get("item_id") or ""),
                cache=cluster_cache,
                plugin=plugin,
            )
        else:
            s["_company_preferred"] = False

    matching.sort(
        key=lambda x: (
            -(x.get("norm_score") or 0),
            str((x.get("item") or {}).get("item_id") or ""),
            str((x.get("item") or {}).get("name") or ""),
        )
    )
    ranked = matching[:top_n]

    rows = []
    for rank, s in enumerate(ranked, 1):
        item = s.get("item") or {}
        rows.append({
            "rank": rank,
            "item_id": item.get("item_id"),
            "name": item.get("name"),
            "score_raw": round(s.get("score_raw") or 0, 2),
            "norm_score": round(s.get("norm_score") or 0, 2),
            "tier": str(s.get("tier", "")),
            "company_preferred": s.get("_company_preferred", False),
            "source": item.get("_source", "static"),
            # [P2] per-factor breakdown so slate logging captures the feature
            # vector the score was built from (chosen-vs-shown training signal).
            "breakdown": s.get("breakdown", {}),
        })

    criteria_echo = _sanitize_criteria(criteria)
    return {
        "category": category,
        # [P2] learned-ranking segment key (matches plugin serve-time derivation).
        "segment": derive_segment(criteria_obj),
        "criteria_echo": criteria_echo,
        "dataset_count": len(dataset),
        "matching_count": len(matching),
        "ranked": rows,
    }


def _default_office_for_city(city: str) -> str:
    """Default office location for commute directions by city."""
    city_lower = (city or "").lower()
    defaults = {
        "singapore": "Raffles Place MRT, Singapore",
        "london": "Canary Wharf, London, UK",
        "new york": "Midtown Manhattan, New York, NY",
        "san francisco": "1 Market St, San Francisco, CA",
        "berlin": "Mitte, Berlin, Germany",
        "oslo": "Sentrum, Oslo, Norway",
    }
    return defaults.get(city_lower) or f"{city}, city center"


def _sanitize_criteria(criteria: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive fields from criteria echo."""
    skip = {"password", "token", "secret"}
    out = {}
    for k, v in criteria.items():
        if k.lower() in skip:
            continue
        if isinstance(v, dict):
            out[k] = _sanitize_criteria(v)
        else:
            out[k] = v
    return out
