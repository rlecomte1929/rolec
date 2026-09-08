"""
Employee recommendations filter — Phase 2c.

Closes the authority loop:

    ADMIN  →  service_catalog_items   (Phase 2a)
                  ↓
    HR     →  company_vendor_selections   (Phase 2d)
                  ↓ (THIS FILTER)
    EMPLOYEE  →  recommendations API filtered through HR's selections

Strict default: an employee sees a master vendor ONLY when HR has an
explicit selected=true row for it. Items HR has no decision on are
hidden, not shown. HR's custom vendors are added to the result as
synthesized recommendation rows.

Empty-state contract: when the (company, category, city) has zero
HR-approved rows (no master selections + no customs), the filter
returns ([], "hr_pending") so the caller can render a "Your HR is
finalizing providers for {category}" placeholder rather than the
raw master.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from ..recommendations.types import (
    RecommendationExplanation,
    RecommendationItem,
    RecommendationTier,
)
from ...database import db
from . import service_catalog, vendor_curation

log = logging.getLogger(__name__)

# Synthesized score for HR custom vendors. They didn't go through the
# scoring engine but HR explicitly approved them for this company →
# treat as "good fit" baseline; UX adds an "HR preferred" badge.
_HR_CUSTOM_SCORE = 80.0

# AIQ-1857: same idea for an HR-approved master the engine never ranked. The engine
# only produces registry suppliers (item_id = supplier uuid) or static-dataset rows;
# a catalog row with no supplier_id belongs to neither id space, so it can never be
# scored. Slightly below the HR-custom baseline so an explicitly hand-added vendor
# still leads on a score tie. `unscored: true` in metadata marks it as a synthesized
# figure rather than an engine result.
_HR_APPROVED_UNRANKED_SCORE = 75.0


def _canon_country(value: Optional[str]) -> str:
    """ISO-2 country code, or "" when the input is not confidently a code.

    Destination country reaches this module as whatever intake captured — sometimes
    "FR", sometimes "France". Only compare when BOTH sides are two-letter codes; a
    name-vs-code comparison would silently mismatch ("Germany"[:2] == "GE" != "DE")
    and hide a vendor HR explicitly approved. Unknown → don't block.
    """
    v = (value or "").strip()
    return v.upper() if len(v) == 2 else ""


def _approved_capability_covers_destination(
    supplier_id: str,
    category: str,
    dest_country: str,
) -> bool:
    """True when an approved capability covers dest (country match or global).

    Mirrors ``vendor_proposal``'s JOIN: ``platform_vetting_status = 'approved'``
    and ``coverage_scope_type = 'global' OR country_code = dest``.
    """
    if not supplier_id or not category or not dest_country:
        return False
    sql = (
        "SELECT 1 FROM supplier_service_capabilities "
        "WHERE supplier_id = :sid AND service_category = :cat "
        "AND platform_vetting_status = 'approved' "
        "AND (coverage_scope_type = 'global' OR country_code = :dest) "
        "LIMIT 1"
    )
    try:
        with db.engine.begin() as conn:
            row = conn.execute(
                text(sql),
                {"sid": supplier_id, "cat": category, "dest": dest_country},
            ).first()
    except Exception:
        log.exception(
            "hr_curation_filter: capability coverage lookup failed "
            "supplier_id=%s category=%s dest=%s",
            supplier_id,
            category,
            dest_country,
        )
        return False
    return row is not None


def _serves_destination(
    master: Dict[str, Any],
    destination_city: Optional[str],
    destination_country: Optional[str],
) -> bool:
    """Whether an HR-approved master may be surfaced for this destination.

    Engine candidates are already destination-scoped by the registry query, so this
    gate exists only for masters synthesized straight from HR's approvals — without
    it, a city-agnostic selection row pointing at a Madrid vendor would surface on a
    Paris case. City is the decisive signal (canonicalised the same way HR's curation
    rows are, per AIQ-1457); country is a fallback; when neither side can be compared
    confidently, HR's explicit approval stands.

    ADR-002: a country-agnostic master (``country`` NULL) must NOT pass through for
    every destination. Gate it on the linked supplier's approved capabilities, the
    same way ``vendor_proposal`` does. City-first comparison stays for country-tagged
    masters only — a leftover city on a multi-country row must not hide other
    countries the capabilities cover.
    """
    m_country = _canon_country(master.get("country"))
    d_country = _canon_country(destination_country)
    if not m_country:
        return _approved_capability_covers_destination(
            str(master.get("supplier_id") or ""),
            str(master.get("category") or ""),
            d_country,
        )
    m_city = vendor_curation._canon_city(master.get("city"))
    d_city = vendor_curation._canon_city(destination_city)
    if m_city and d_city:
        return m_city == d_city
    if m_country and d_country:
        return m_country == d_country
    return True


def _master_to_recommendation(master: Dict[str, Any]) -> RecommendationItem:
    """Synthesize an employee-facing item from an HR-approved catalog master.

    ``item_id`` is the master's ``external_id`` — the shape the downstream RFQ path
    already documents for a master vendor (see ``employee_quotes.VendorPick``), so a
    synthesized card shortlists and requests quotes like any other.
    """
    attrs = master.get("attributes_json") or {}
    verified = bool(attrs.get("verified"))
    name = str(master.get("name") or "(unnamed)")
    metadata: Dict[str, Any] = {
        "company_preferred": True,
        "hr_approved_catalog": True,
        # The score below is a baseline, not an engine result — say so, so the UI can
        # avoid presenting it as a computed match.
        "unscored": True,
        "verified": verified,
    }
    if master.get("city"):
        metadata["city"] = str(master["city"])
    website = attrs.get("website") or attrs.get("url")
    if website:
        metadata["website"] = str(website)
    return RecommendationItem(
        item_id=str(master.get("external_id") or master.get("id")),
        name=name,
        score=_HR_APPROVED_UNRANKED_SCORE,
        tier=RecommendationTier.GOOD_FIT,
        summary="Approved by your HR team",
        rationale="Your HR team approved this provider for your destination.",
        breakdown={},
        pros=["HR-approved for your company"],
        cons=[],
        metadata=metadata,
        explanation=RecommendationExplanation(
            match_reasons=["HR-approved vendor"],
            explanation_summary="HR-approved vendor for your company",
        ),
    )


def _custom_to_recommendation(row: Dict[str, Any]) -> RecommendationItem:
    payload = row.get("custom_item_json") or {}
    name = str(payload.get("name") or "(unnamed)")
    notes = payload.get("notes")
    metadata: Dict[str, Any] = {
        "hr_custom": True,
        "company_preferred": True,
    }
    if notes:
        metadata["notes"] = str(notes)
    rationale_bits = ["Approved by your HR team for this company."]
    if notes:
        rationale_bits.append(str(notes))
    explanation = RecommendationExplanation(
        match_reasons=["HR-approved vendor"],
        explanation_summary="HR-approved vendor for your company",
    )
    return RecommendationItem(
        item_id=f"hr-custom-{row['id']}",
        name=name,
        score=_HR_CUSTOM_SCORE,
        tier=RecommendationTier.GOOD_FIT,
        summary="Approved by your HR team",
        rationale=" ".join(rationale_bits),
        breakdown={},
        pros=["HR-approved for your company"],
        cons=[],
        metadata=metadata,
        explanation=explanation,
    )


def apply_hr_curation(
    *,
    category: str,
    items: List[RecommendationItem],
    company_id: Optional[str],
    destination_city: Optional[str],
    destination_country: Optional[str] = None,
) -> Tuple[List[RecommendationItem], Optional[str]]:
    """
    Filter the engine's ranked items down to those HR has approved for the
    company, and append HR's custom vendors. Returns (filtered_items, status)
    where status is one of:

      - None              → curation applied (or no company context — pass through)
      - "hr_pending"      → company exists but HR hasn't approved anything in
                            this category × city; UI should render placeholder.
      - "hr_destination_gap" → AIQ-1857: HR HAS approved vendors in this category,
                            but none of them is usable for this destination. Telling
                            this employee "HR is finalizing" would be false — HR has
                            decided; the decision just doesn't cover where they're
                            going. Distinct so the UI can say the true thing.
    """
    if not company_id:
        # No tenant context (admin debug calls, unauth flows): pass through.
        return items, None

    # 1. Pull HR's selections for the (company, category, city) scope.
    selections = vendor_curation.list_curation(
        company_id=company_id,
        category=category,
        destination_city=destination_city,
    )
    approved_master_ids = {
        s["master_item_id"]
        for s in selections
        if s.get("master_item_id") and s.get("selected")
    }
    # [AIQ-1530] HR's display_order is the ranking intent. selected=true is already a hard gate
    # (only approved items survive step 2), so ordering the survivors by display_order is what
    # makes "the vendor HR ranked first sorts first for the employee" true. This is the employee
    # path; the engine's global sort is left untouched.
    order_by_master = {
        s["master_item_id"]: s.get("display_order", 0)
        for s in selections
        if s.get("master_item_id") and s.get("selected")
    }
    customs = [
        s
        for s in selections
        if not s.get("master_item_id") and s.get("custom_item_json") and s.get("selected")
    ]

    # 2. Walk each engine item; keep only when its master_item_id is in
    # the approved set. Items that don't have a master row at all (e.g.
    # legacy datasets that haven't been backfilled) are dropped — HR
    # can't curate what isn't in the master.
    #
    # AIQ-1688: resolve the master by external_id OR supplier_id. Registry-backed
    # items are keyed item_id=supplier UUID, but their masters are often keyed
    # external_id='m-N' with supplier_id=<that UUID>; matching only external_id
    # dropped every such HR-approved item (movers rendered empty). Dedup by master
    # id so a registry item and its legacy static twin (both resolving to the same
    # approved master) don't both render — keep the first (highest-ranked) one.
    # AIQ-1700: one batched lookup instead of one query per item. The engine now hands
    # us the FULL ranked candidate list (so an approved supplier ranked below top_n is
    # no longer discarded before we see it), which would otherwise make this loop issue
    # a query per candidate on the employee hot path.
    masters_by_item_id = service_catalog.find_masters_by_supplier_or_external_ids(
        category, [rec.item_id for rec in items]
    )
    kept: List[Tuple[int, RecommendationItem]] = []
    seen_master_ids: set = set()
    for rec in items:
        master = masters_by_item_id.get(str(rec.item_id))
        if not master:
            log.debug(
                "hr_curation_filter dropped item with no master entry: "
                "category=%s item_id=%s",
                category,
                rec.item_id,
            )
            continue
        if master["id"] in approved_master_ids and master["id"] not in seen_master_ids:
            seen_master_ids.add(master["id"])
            kept.append((order_by_master.get(master["id"], 0), rec))

    # 2b. AIQ-1857: surface the approved masters NO engine candidate resolved to.
    #
    # The curation catalog and the engine rank different vendor populations. HR curates
    # `service_catalog_items` (crowdsourced/scraped: no supplier_id, slug external_ids);
    # the engine emits registry suppliers (item_id = supplier uuid) or static-dataset
    # rows. Neither predicate in find_masters_by_supplier_or_external_ids can match a
    # row that is in neither id space, so HR's picks silently became ([], "hr_pending")
    # and the employee was told HR was still deciding — measured on 2026-08-17 for a
    # Paris case where HR had approved 4 housing agencies, 9 schools and 4 movers, and
    # for housing_agencies the engine had produced ZERO candidates to match against.
    #
    # Product decision (2026-08-17): the catalog is authoritative for curation, so an
    # approved master is shown on HR's say-so even when the engine cannot score it.
    # The gate is unchanged — only ids already in `approved_master_ids` get here, and
    # _serves_destination re-imposes the destination scoping the engine would have.
    unmatched_ids = approved_master_ids - seen_master_ids
    catalog_read_ok = True
    if unmatched_ids:
        try:
            for master in service_catalog.find_masters_by_ids(sorted(unmatched_ids)):
                if not _serves_destination(master, destination_city, destination_country):
                    continue
                mid = str(master.get("id"))
                seen_master_ids.add(mid)
                kept.append((order_by_master.get(mid, 0), _master_to_recommendation(master)))
        except Exception:
            # Never break the employee's recommendations over the catalog read — the
            # pre-AIQ-1857 behaviour (engine-matched masters only) is the fallback.
            catalog_read_ok = False
            log.exception("hr_curation_filter: approved-master fallback read failed")

    # Order by HR's display_order (stable: engine order breaks ties within the same rank,
    # and an engine-scored item precedes a synthesized one at the same rank).
    kept.sort(key=lambda pair: pair[0])
    ordered: List[RecommendationItem] = [rec for _, rec in kept]

    # 3. Append HR custom vendors (display_order-ordered) after the master picks.
    for c in sorted(customs, key=lambda s: s.get("display_order", 0)):
        ordered.append(_custom_to_recommendation(c))

    if not ordered:
        # AIQ-1550: distinguish "HR hasn't curated anything" (normal pending) from "HR curated,
        # but none of their approved masters matched the engine's candidate item_ids" — the
        # latter is a real defect (e.g. a service_catalog_items external_id backfill gap) worth
        # surfacing loudly instead of silently showing the same empty state.
        if approved_master_ids:
            # AIQ-1857: this used to assert "likely a service_catalog_items external_id
            # mismatch". That was a guess, and it was wrong — the two sides held
            # different vendors, so there was no id to match. Since approved masters are
            # now surfaced directly, reaching here means every one of them was either
            # missing/inactive in the catalog or scoped to another destination. State
            # only that, and name the ids so the next reader can check rather than guess.
            log.warning(
                "hr_curation_filter: company=%s has %d approved %s master(s) but none is "
                "usable for city=%s country=%s — each was inactive, absent from "
                "service_catalog_items, or scoped to a different destination. "
                "approved_master_ids=%s",
                company_id, len(approved_master_ids), category, destination_city,
                destination_country, sorted(approved_master_ids),
            )
        # Record the demand signal so HR can see who's waiting on what.
        # Best-effort — never raise on the filter path.
        try:
            from . import employee_demand
            employee_demand.record_demand(
                company_id=company_id,
                category=category,
                destination_city=destination_city,
                destination_country=destination_country,
            )
        except Exception:
            log.exception("record_demand dispatch failed")
        # AIQ-1857: "HR is finalizing" is only true when HR has decided nothing. When
        # they have approved vendors that simply don't cover this destination, say that
        # instead of implying they are still choosing. Only claim the destination gap
        # when the catalog read actually succeeded — if it failed we did not check, and
        # asserting a gap we never measured is the kind of confident-and-wrong message
        # this task exists to remove.
        gap = bool(approved_master_ids) and catalog_read_ok
        return [], ("hr_destination_gap" if gap else "hr_pending")
    return ordered, None
