"""
Template-first HR policy import: fill the canonical LTA template from parsed rows.

Uploads are treated as evidence for a fixed template — not as a source of unbounded
benefit rows. Unmapped and draft-only rows are surfaced for HR review without
auto-publishing to Layer-2 benefits.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .policy_canonical_lta_template import (
    CanonicalLtaTemplateField,
    PolicyTemplateValueType,
    list_canonical_lta_template_fields,
)
from .policy_row_to_template_mapper import _merge_sub_values

TEMPLATE_FIRST_MODE = "canonical_lta_template_first"


def _drafts_by_clause_index(
    draft_rule_candidates: Sequence[Dict[str, Any]],
) -> Dict[int, List[Dict[str, Any]]]:
    out: Dict[int, List[Dict[str, Any]]] = {}
    for d in draft_rule_candidates:
        if not isinstance(d, dict):
            continue
        idx = d.get("clause_index")
        if not isinstance(idx, int):
            continue
        out.setdefault(idx, []).append(d)
    return out


def _merge_comparison_hints(hints: Sequence[str]) -> str:
    hs = [str(h or "partial").strip() for h in hints if h]
    if not hs:
        return "partial"
    if any(h == "draft_only" for h in hs):
        return "draft_only"
    if any(h == "not_ready" for h in hs):
        return "not_ready"
    if any(h == "external_reference" for h in hs):
        return "external_reference"
    if any(h == "partial" for h in hs):
        return "partial"
    if all(h == "ready" for h in hs):
        return "ready"
    return hs[-1]


def _merge_coverage_statuses(statuses: Sequence[str]) -> str:
    xs = [str(s or "mentioned") for s in statuses if s]
    if not xs:
        return "mentioned"
    if any(x == "excluded" for x in xs):
        return "excluded"
    rank = {
        "ambiguous": 1,
        "mentioned": 2,
        "covered": 3,
        "specified": 4,
        "capped_external": 5,
    }
    best = "mentioned"
    best_r = 0
    for x in xs:
        r = rank.get(x, 0)
        if r > best_r:
            best_r = r
            best = x
    return best


def _merge_lta_row_mappings(maps: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    maps = [m for m in maps if isinstance(m, dict)]
    if not maps:
        return {}
    sub: Dict[str, Any] = {}
    quant: Dict[str, Any] = {}
    apps: List[str] = []
    merged_ids: List[str] = []
    provs: List[Dict[str, Any]] = []
    hints: List[str] = []
    covs: List[str] = []
    for m in maps:
        sub = _merge_sub_values(sub, m.get("sub_values") or {})
        mq = m.get("quantification") or {}
        if isinstance(mq, dict):
            quant = {**quant, **mq}
        a = m.get("applicability") or []
        if isinstance(a, list):
            apps.extend(str(x) for x in a if x)
        mids = m.get("merged_source_row_ids") or []
        if isinstance(mids, list):
            merged_ids.extend(str(x) for x in mids if x)
        p = m.get("provenance") or {}
        if isinstance(p, dict) and p:
            provs.append(p)
        hints.append(str(m.get("comparison_readiness_hint") or "partial"))
        covs.append(str(m.get("coverage_status") or "mentioned"))
    base = dict(maps[-1])
    base["primary_canonical_key"] = maps[0].get("primary_canonical_key")
    base["sub_values"] = sub
    base["quantification"] = quant
    base["applicability"] = sorted(set(apps))
    base["merged_source_row_ids"] = list(dict.fromkeys(merged_ids))
    base["comparison_readiness_hint"] = _merge_comparison_hints(hints)
    base["coverage_status"] = _merge_coverage_statuses(covs)
    base["provenance"] = {"merged_sources": provs} if len(provs) > 1 else (provs[0] if provs else {})
    base["draft_only_unresolved"] = any(bool(m.get("draft_only_unresolved")) for m in maps)
    return base


def _build_source_ref(
    clause_indices: Sequence[int],
    maps: Sequence[Dict[str, Any]],
    drafts_by_clause: Dict[int, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    excerpts: List[str] = []
    section_refs: List[str] = []
    pages: List[int] = []
    doc_ids: List[str] = []

    for m in maps:
        p = m.get("provenance") or {}
        if isinstance(p, dict):
            st = p.get("summary_text")
            if isinstance(st, str) and st.strip():
                excerpts.append(st.strip()[:400])
            sr = p.get("section_reference")
            if isinstance(sr, str) and sr.strip():
                section_refs.append(sr.strip())
            pg = p.get("page_number")
            if isinstance(pg, int):
                pages.append(pg)
            did = p.get("source_document_id")
            if isinstance(did, str) and did.strip():
                doc_ids.append(did.strip())

    for ci in clause_indices:
        for d in drafts_by_clause.get(int(ci), []) or []:
            ex = d.get("source_excerpt")
            if isinstance(ex, str) and ex.strip():
                excerpts.append(ex.strip()[:400])
            tr = d.get("source_trace") or {}
            if isinstance(tr, dict):
                sr = tr.get("section_ref")
                if isinstance(sr, str) and sr.strip():
                    section_refs.append(sr.strip())
                did = tr.get("document_id")
                if isinstance(did, str) and did.strip():
                    doc_ids.append(did.strip())
                for key in ("source_page_start", "source_page_end"):
                    pg = tr.get(key)
                    if isinstance(pg, int):
                        pages.append(pg)

    return {
        "clause_indices": list(clause_indices),
        "section_refs": sorted(set(section_refs)),
        "text_excerpts": excerpts[:8],
        "page_numbers": sorted(set(pages)),
        "document_ids": sorted(set(doc_ids)),
    }


def _external_reference_flag(
    field: CanonicalLtaTemplateField,
    merged_mapping: Dict[str, Any],
) -> bool:
    hint = str(merged_mapping.get("comparison_readiness_hint") or "")
    if hint == "external_reference":
        return True
    sv = merged_mapping.get("sub_values") or {}
    if not isinstance(sv, dict):
        return False
    if sv.get("cap_basis") == "external_or_third_party":
        return True
    eg = sv.get("external_governance")
    if isinstance(eg, dict) and eg.get("is_externally_governed"):
        return True
    if field.value_type == PolicyTemplateValueType.EXTERNAL_REFERENCE:
        return True
    return False


def _confidence_from_maps_and_drafts(
    clause_indices: Sequence[int],
    maps: Sequence[Dict[str, Any]],
    clauses: Sequence[Dict[str, Any]],
    drafts_by_clause: Dict[int, List[Dict[str, Any]]],
) -> Optional[float]:
    scores: List[float] = []
    for m in maps:
        p = m.get("provenance") or {}
        if isinstance(p, dict):
            try:
                pc = float(p.get("parse_confidence") or 0)
                if pc > 0:
                    scores.append(pc)
            except (TypeError, ValueError):
                pass
    for ci in clause_indices:
        cl = clauses[ci] if 0 <= ci < len(clauses) else None
        if isinstance(cl, dict):
            try:
                c = float(cl.get("confidence") or 0)
                if c > 0:
                    scores.append(c)
            except (TypeError, ValueError):
                pass
        for d in drafts_by_clause.get(int(ci), []) or []:
            try:
                cf = float(d.get("confidence") or 0)
                if cf > 0:
                    scores.append(cf)
            except (TypeError, ValueError):
                pass
    if not scores:
        return None
    return min(0.99, max(scores))


def _collect_clause_mappings(
    clauses: Sequence[Dict[str, Any]],
) -> Tuple[Dict[str, List[Tuple[int, Dict[str, Any]]]], List[Dict[str, Any]]]:
    """
    Returns (buckets by primary canonical key -> list of (clause_index, mapping)),
    and draft_only rows as list of dicts for HR.
    """
    buckets: Dict[str, List[Tuple[int, Dict[str, Any]]]] = {}
    draft_only_rows: List[Dict[str, Any]] = []

    for i, cl in enumerate(clauses):
        if not isinstance(cl, dict):
            continue
        hints = cl.get("normalized_hint_json")
        if not isinstance(hints, dict):
            continue
        m = hints.get("canonical_lta_row_mapping")
        if not isinstance(m, dict):
            continue
        if m.get("draft_only_unresolved") or not m.get("primary_canonical_key"):
            draft_only_rows.append(
                {
                    "clause_index": i,
                    "reason": "draft_only_unresolved"
                    if m.get("draft_only_unresolved")
                    else "no_primary_template_key",
                    "summary_excerpt": (cl.get("raw_text") or "")[:500],
                    "canonical_lta_row_mapping": m,
                }
            )
            continue
        pk = str(m.get("primary_canonical_key"))
        buckets.setdefault(pk, []).append((i, m))

    return buckets, draft_only_rows


def _legacy_unmapped_draft_rows(
    clauses: Sequence[Dict[str, Any]],
    draft_rule_candidates: Sequence[Dict[str, Any]],
    draft_only_clause_indices: set,
) -> List[Dict[str, Any]]:
    """Clauses that have normalization drafts but no canonical LTA mapping (legacy path)."""
    draft_indices = set()
    for d in draft_rule_candidates:
        if isinstance(d, dict) and isinstance(d.get("clause_index"), int):
            draft_indices.add(int(d["clause_index"]))
    out: List[Dict[str, Any]] = []
    for i in sorted(draft_indices):
        if i in draft_only_clause_indices:
            continue
        cl = clauses[i] if 0 <= i < len(clauses) else None
        if not isinstance(cl, dict):
            continue
        hints = cl.get("normalized_hint_json")
        if isinstance(hints, dict) and isinstance(hints.get("canonical_lta_row_mapping"), dict):
            continue
        out.append(
            {
                "clause_index": i,
                "reason": "no_template_mapping",
                "summary_excerpt": (cl.get("raw_text") or "")[:500],
                "canonical_lta_row_mapping": None,
            }
        )
    return out


def _duplicate_merge_counts(
    buckets: Dict[str, List[Tuple[int, Dict[str, Any]]]],
) -> int:
    total = 0
    for _pk, entries in buckets.items():
        k = len(entries)
        if k > 1:
            total += k - 1
        for _ci, m in entries:
            mids = m.get("merged_source_row_ids") or []
            if isinstance(mids, list) and len(mids) > 1:
                total += len(mids) - 1
    return total


def build_template_first_import_payload(
    clauses: Sequence[Dict[str, Any]],
    draft_rule_candidates: Sequence[Dict[str, Any]],
    *,
    grouped_policy_items_count: int = 0,
) -> Dict[str, Any]:
    """
    Build full-template view + import summary for HR review.

    Does not create or mutate Layer-2 benefit rows.
    """
    clause_list = [c for c in clauses if isinstance(c, dict)]
    drafts_by = _drafts_by_clause_index(draft_rule_candidates)

    buckets, draft_only_rows = _collect_clause_mappings(clause_list)
    draft_only_idx = {r["clause_index"] for r in draft_only_rows if isinstance(r.get("clause_index"), int)}
    legacy_unmapped = _legacy_unmapped_draft_rows(
        clause_list, draft_rule_candidates, draft_only_idx
    )
    draft_only_import_rows = draft_only_rows + legacy_unmapped

    duplicate_rows_merged_count = _duplicate_merge_counts(buckets)
    mapped_items_count = len(buckets)
    unmapped_rows_count = len(draft_only_import_rows)

    template_fields = list_canonical_lta_template_fields()
    template_items: List[Dict[str, Any]] = []

    for field in template_fields:
        entries = buckets.get(field.key) or []
        if not entries:
            review_needed = bool(field.drives_comparison)
            template_items.append(
                {
                    "canonical_key": field.key,
                    "domain_id": field.domain_id,
                    "employee_visible_label": field.employee_visible_label,
                    "template_value_type": field.value_type.value,
                    "drives_comparison": field.drives_comparison,
                    "import_status": "unmapped",
                    "sub_values": {},
                    "applicability": [],
                    "coverage_status": None,
                    "quantification": {},
                    "comparison_readiness_hint": None,
                    "parse_confidence": None,
                    "source_ref": None,
                    "merged_source_row_ids": [],
                    "clause_indices": [],
                    "external_reference_flag": False,
                    "review_needed": review_needed,
                }
            )
            continue

        indices = [t[0] for t in entries]
        maps = [t[1] for t in entries]
        merged = _merge_lta_row_mappings(maps)
        conf = _confidence_from_maps_and_drafts(indices, maps, clause_list, drafts_by)
        source_ref = _build_source_ref(indices, maps, drafts_by)
        ext_flag = _external_reference_flag(field, merged)
        hint = str(merged.get("comparison_readiness_hint") or "partial")
        review_needed = False
        if field.drives_comparison and hint not in ("ready",):
            review_needed = True
        if ext_flag:
            review_needed = True
        if field.value_type == PolicyTemplateValueType.EXTERNAL_REFERENCE and merged.get("primary_canonical_key"):
            review_needed = True

        template_items.append(
            {
                "canonical_key": field.key,
                "domain_id": field.domain_id,
                "employee_visible_label": field.employee_visible_label,
                "template_value_type": field.value_type.value,
                "drives_comparison": field.drives_comparison,
                "import_status": "mapped",
                "sub_values": merged.get("sub_values") or {},
                "applicability": merged.get("applicability") or [],
                "coverage_status": merged.get("coverage_status"),
                "quantification": merged.get("quantification") or {},
                "comparison_readiness_hint": hint,
                "parse_confidence": conf,
                "source_ref": source_ref,
                "merged_source_row_ids": merged.get("merged_source_row_ids") or [],
                "clause_indices": indices,
                "external_reference_flag": ext_flag,
                "review_needed": review_needed,
            }
        )

    review_required_items_count = sum(1 for it in template_items if it.get("review_needed"))

    return {
        "mode": TEMPLATE_FIRST_MODE,
        "template_schema_version": "canonical_lta_template_v1",
        "template_items": template_items,
        "draft_only_import_rows": draft_only_import_rows,
        "import_summary": {
            "mapped_items_count": mapped_items_count,
            "grouped_items_count": int(grouped_policy_items_count),
            "unmapped_rows_count": unmapped_rows_count,
            "duplicate_rows_merged_count": duplicate_rows_merged_count,
            "review_required_items_count": review_required_items_count,
            "template_field_count": len(template_fields),
        },
    }
