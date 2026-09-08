"""
HR policy pipeline: explicit separation of Layer 1 (document metadata) vs Layer 2 (decision output).

Layer 1 is descriptive / exploratory — useful for HR triage and labeling — and must NOT drive
employee comparison or eligibility.

Layer 2 is the published normalized policy graph + per-assignment resolution consumed by
`policy_resolution` and `policy_service_comparison`.

See: docs/policy/metadata-vs-decision-layer.md
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# Keys inside policy_documents.extracted_metadata (and normalize_extracted_metadata output)
LAYER1_EXTRACTED_METADATA_KEYS = frozenset(
    {
        "detected_title",
        "detected_version",
        "detected_effective_date",
        "mentioned_assignment_types",
        "mentioned_family_status_terms",
        "mentioned_benefit_categories",
        "mentioned_units",
        "likely_table_heavy",
        "likely_country_addendum",
        "likely_tax_specific",
        "likely_contains_exclusions",
        "likely_contains_approval_rules",
        "likely_contains_evidence_rules",
    }
)

# Legacy aliases still merged by normalize_extracted_metadata (Layer 1 only)
LAYER1_EXTRACTED_METADATA_LEGACY_ALIASES = frozenset(
    {"policy_title", "version", "effective_date", "assignment_types_mentioned", "benefit_categories_mentioned", "contains_tables"}
)


def layer1_extracted_metadata_subset(extracted_metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return only Layer-1 keys present on the document metadata blob (for API `layer1` envelope)."""
    if not isinstance(extracted_metadata, dict):
        return {}
    keys = LAYER1_EXTRACTED_METADATA_KEYS | LAYER1_EXTRACTED_METADATA_LEGACY_ALIASES
    return {k: extracted_metadata[k] for k in keys if k in extracted_metadata}


def layer1_fields_for_company_policy_shell(
    extracted_metadata: Optional[Dict[str, Any]],
    *,
    filename: Optional[str] = None,
    version_label_row: Any = None,
    effective_date_row: Any = None,
) -> Dict[str, Any]:
    """
    Layer 1 → administrative labels on company_policies only (title / version string / date).
    These fields do not grant coverage; Layer 2 rules do.
    """
    meta = extracted_metadata if isinstance(extracted_metadata, dict) else {}
    title = (meta.get("detected_title") or meta.get("policy_title") or "").strip()
    if not title and filename:
        title = str(filename).strip()
    return {
        "title": title or "Policy",
        "version": meta.get("detected_version") or meta.get("version") or version_label_row,
        "effective_date": meta.get("detected_effective_date") or meta.get("effective_date") or effective_date_row,
    }


def enrich_policy_document_for_hr(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Attach an explicit `layer1` envelope to a policy_documents row for HR APIs.
    Top-level fields remain for backward compatibility; clients should treat `layer1` as the
    canonical metadata profile and must not use it for employee comparison.
    """
    if not doc:
        return doc
    out = dict(doc)
    em = out.get("extracted_metadata")
    out["layer1"] = {
        "kind": "document_metadata_profile",
        "extracted_metadata": layer1_extracted_metadata_subset(em if isinstance(em, dict) else None),
        "classification": {
            "detected_document_type": out.get("detected_document_type"),
            "detected_policy_scope": out.get("detected_policy_scope"),
        },
        "labels": {
            "version_label": out.get("version_label"),
            "effective_date": out.get("effective_date"),
        },
    }
    return out


# Clause-level heuristics (stored in normalized_hint_json) — Layer 1 input to normalization, not decisions.
LAYER1_CLAUSE_HINT_PREFIX = "candidate_"
LAYER1_CLAUSE_HINT_FLAGS = frozenset(
    {
        "candidate_exclusion_flag",
        "candidate_approval_flag",
    }
)
