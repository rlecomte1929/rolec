"""
Read-only diagnostics for the policy intake → clause → normalize_clauses_to_objects pipeline.

Used by scripts and optional env-gated logging (RELOPASS_POLICY_PIPELINE_DIAG). Does not alter
mapping output — only observes it.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Matches dotted section / clause numbers (2.1, 6.5.1) anywhere in text
_SECTION_REF_TOKEN_RE = re.compile(r"(?:^|[\s:;])(\d+(?:\.\d+){1,4})\b")
# Line that is mostly numbering (heading row)
_HEADING_NUM_PREFIX_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+.+")
# Small decimals that often come from section refs mistaken for amounts (e.g. 2.1, 8.3)
_SMALL_DECIMAL_RE = re.compile(r"^\d+\.\d+$")


def raw_text_diagnostic_flags(
    raw: str,
    hints: Optional[Dict[str, Any]],
    section_label: Optional[str],
    *,
    is_table_row_shape: bool = False,
) -> List[str]:
    """Heuristic flags for inflation / leakage (no ML)."""
    flags: List[str] = []
    hints = hints if isinstance(hints, dict) else {}
    r = raw or ""
    rl = r.lower().strip()

    if _SECTION_REF_TOKEN_RE.search(r):
        flags.append("section_ref_in_text")
    m = _HEADING_NUM_PREFIX_RE.match(r.strip())
    if m:
        flags.append("numbered_heading_shape")

    nums = hints.get("candidate_numeric_values") or []
    if isinstance(nums, list) and nums:
        for n in nums[:5]:
            try:
                s = str(float(n))
            except (TypeError, ValueError):
                continue
            if _SMALL_DECIMAL_RE.match(s):
                flags.append("hint_numeric_looks_like_section_decimal")
                break
            if float(n) < 20 and float(n) > 0 and float(n) != int(float(n)):
                flags.append("hint_numeric_small_decimal")
                break

    sl = (section_label or "").strip()
    if sl and re.match(r"^\d+(?:\.\d+)*\s*$", sl):
        flags.append("section_label_numeric_only")

    if is_table_row_shape or (" | " in r and len(r) < 800):
        flags.append("table_row_shape")

    if len(rl) < 48 and flags and "numbered_heading_shape" in flags:
        flags.append("short_numbered_clause")

    return sorted(set(flags))


def _normalize_excerpt_key(excerpt: str, max_len: int = 72) -> str:
    s = re.sub(r"\s+", " ", (excerpt or "").strip().lower())[:max_len]
    return s


def cluster_draft_candidates_by_service_and_text(
    draft_rule_candidates: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Groups draft_rule_candidates that share the same service key and nearly the same excerpt prefix.
    Large clusters indicate fragment inflation or repeated mapping from similar rows.
    """
    buckets: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    for d in draft_rule_candidates:
        if not isinstance(d, dict):
            continue
        sk = str(d.get("candidate_service_key") or "none")
        ex = _normalize_excerpt_key(str(d.get("source_excerpt") or ""))
        key = (sk, ex)
        idx = d.get("clause_index")
        if isinstance(idx, int):
            buckets[key].append(idx)
    clusters: List[Dict[str, Any]] = []
    for (sk, ex), idxs in buckets.items():
        if len(idxs) <= 1:
            continue
        clusters.append(
            {
                "candidate_service_key": sk,
                "excerpt_key": ex,
                "clause_indices": sorted(idxs),
                "size": len(idxs),
            }
        )
    clusters.sort(key=lambda x: -x["size"])
    return clusters


def build_per_clause_pipeline_table(
    clauses: Sequence[Dict[str, Any]],
    mapped: Dict[str, Any],
    *,
    document_id: str = "",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    One row per source clause with downstream counts and flags.

    Returns (rows, summary) where summary aggregates inflation hints.
    """
    drafts = [d for d in (mapped.get("draft_rule_candidates") or []) if isinstance(d, dict)]
    draft_by_idx: Dict[int, Dict[str, Any]] = {}
    for d in drafts:
        ci = d.get("clause_index")
        if isinstance(ci, int):
            draft_by_idx[ci] = d

    brs = mapped.get("benefit_rules") or []
    exs = mapped.get("exclusions") or []
    conds = mapped.get("conditions") or []
    evs = mapped.get("evidence_requirements") or []

    def br_for_clause(i: int) -> List[Dict[str, Any]]:
        return [r for r in brs if isinstance(r, dict) and r.get("_clause_idx") == i]

    def _clause_raw_short(i: int) -> str:
        if i >= len(clauses):
            return ""
        c = clauses[i]
        return ((c.get("raw_text") or "") if isinstance(c, dict) else "").strip()[:800]

    def ex_for_clause(i: int) -> List[Dict[str, Any]]:
        if i >= len(clauses):
            return []
        cid = clauses[i].get("id")
        c_raw = _clause_raw_short(i)
        out: List[Dict[str, Any]] = []
        for r in exs:
            if not isinstance(r, dict):
                continue
            if cid is not None and r.get("_clause_id") == cid:
                out.append(r)
            elif cid is None and c_raw:
                er = str(r.get("raw_text") or "").strip()[:800]
                if er and (er == c_raw or (len(c_raw) >= 24 and er.startswith(c_raw[:40]))):
                    out.append(r)
        return out

    def cond_for_benefit_clause(i: int) -> List[Dict[str, Any]]:
        return [r for r in conds if isinstance(r, dict) and r.get("_benefit_clause_idx") == i]

    def ev_for_clause(i: int) -> List[Dict[str, Any]]:
        if i >= len(clauses):
            return []
        cid = clauses[i].get("id")
        c_raw = _clause_raw_short(i)
        out: List[Dict[str, Any]] = []
        for r in evs:
            if not isinstance(r, dict):
                continue
            if cid is not None and r.get("_clause_id") == cid:
                out.append(r)
            elif cid is None and c_raw:
                er = str(r.get("raw_text") or "").strip()[:800]
                if er and (er == c_raw or (len(c_raw) >= 24 and er.startswith(c_raw[:40]))):
                    out.append(r)
        return out

    rows: List[Dict[str, Any]] = []
    summary = {
        "document_id": document_id,
        "clause_count": len(clauses),
        "draft_rule_candidates_count": len(drafts),
        "benefit_rules_count": len(brs),
        "exclusions_count": len(exs),
        "conditions_count": len(conds),
        "evidence_requirements_count": len(evs),
        "clauses_with_section_ref_flag": 0,
        "clauses_with_hint_section_decimal": 0,
        "clauses_table_shaped": 0,
        "total_publish_layer_rows_attributed": 0,
        "max_conditions_for_single_clause": 0,
    }

    for i, c in enumerate(clauses):
        if not isinstance(c, dict):
            continue
        raw = (c.get("raw_text") or "").strip()
        hints = c.get("normalized_hint_json") if isinstance(c.get("normalized_hint_json"), dict) else {}
        section = c.get("section_label")
        ctype = c.get("clause_type") or "unknown"
        is_table = " | " in raw and len(raw) < 1200

        flags = raw_text_diagnostic_flags(raw, hints, section, is_table_row_shape=is_table)
        if "section_ref_in_text" in flags:
            summary["clauses_with_section_ref_flag"] += 1
        if "hint_numeric_looks_like_section_decimal" in flags or "hint_numeric_small_decimal" in flags:
            summary["clauses_with_hint_section_decimal"] += 1
        if "table_row_shape" in flags:
            summary["clauses_table_shaped"] += 1

        br_i = br_for_clause(i)
        ex_i = ex_for_clause(i)
        cd_i = cond_for_benefit_clause(i)
        ev_i = ev_for_clause(i)
        d = draft_by_idx.get(i)

        pub_total = len(br_i) + len(ex_i) + len(cd_i) + len(ev_i)
        summary["total_publish_layer_rows_attributed"] += pub_total
        if len(cd_i) > summary["max_conditions_for_single_clause"]:
            summary["max_conditions_for_single_clause"] = len(cd_i)

        excerpt_preview = raw.replace("\n", " ")[:120]
        rows.append(
            {
                "clause_index": i,
                "clause_id": c.get("id"),
                "clause_type": ctype,
                "section_label": section,
                "section_path": c.get("section_path"),
                "raw_preview": excerpt_preview + ("…" if len(raw) > 120 else ""),
                "raw_char_len": len(raw),
                "mapped_service_key": (d or {}).get("candidate_service_key"),
                "draft_candidate": 1 if d else 0,
                "publish_benefit_rules": len(br_i),
                "publish_exclusions": len(ex_i),
                "publish_conditions": len(cd_i),
                "publish_evidence": len(ev_i),
                "publish_layer_total": pub_total,
                "coverage_status": (d or {}).get("candidate_coverage_status"),
                "publishability_assessment": (d or {}).get("publishability_assessment"),
                "publish_layer_targets": (d or {}).get("publish_layer_targets") or [],
                "diagnostic_flags": flags,
            }
        )

    summary["duplicate_draft_clusters"] = cluster_draft_candidates_by_service_and_text(drafts)
    summary["duplicate_cluster_count"] = len(summary["duplicate_draft_clusters"])
    return rows, summary


def format_pipeline_table_markdown(rows: List[Dict[str, Any]], max_rows: Optional[int] = None) -> str:
    """Markdown table for pasting into audits."""
    lines = [
        "| idx | section | service | draft | ben | excl | cond | ev | flags | preview |",
        "|-----|---------|---------|-------|-----|------|------|-------|-------|---------|",
    ]
    for r in rows[: max_rows or len(rows)]:
        prev = (r.get("raw_preview") or "").replace("|", "\\|")
        flags = ",".join(r.get("diagnostic_flags") or []) or "—"
        sec = str(r.get("section_label") or "—").replace("|", "\\|")[:32]
        lines.append(
            f"| {r.get('clause_index')} | {sec} | {r.get('mapped_service_key') or '—'} | "
            f"{r.get('draft_candidate')} | {r.get('publish_benefit_rules')} | {r.get('publish_exclusions')} | "
            f"{r.get('publish_conditions')} | {r.get('publish_evidence')} | {flags[:40]} | {prev[:56]} |"
        )
    return "\n".join(lines)


def pipeline_fingerprint(clauses: Sequence[Dict[str, Any]], mapped: Dict[str, Any]) -> str:
    """Stable short hash for comparing runs (not cryptographic)."""
    parts = [str(len(clauses)), str(len(mapped.get("draft_rule_candidates") or []))]
    for c in clauses[:50]:
        if isinstance(c, dict):
            parts.append((c.get("raw_text") or "")[:40])
    h = hashlib.sha256("\n".join(parts).encode("utf-8", errors="replace")).hexdigest()
    return h[:16]
