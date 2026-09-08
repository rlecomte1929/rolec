# Canonical entitlement model

ReloPass uses **Layer 2** (`policy_benefit_rules`, `policy_exclusions`) for persistence and the **publish gate**, while employees and the services wizard need a richer, stable notion of an **entitlement rule** (coverage, strength, limits, readiness). The canonical model lives in code as:

- **`backend/services/policy_entitlement_model.py`** — enums/constants, TypedDict shapes, JSON Schema dict, mapping helpers.

This document explains how that model relates to **draft normalization**, **Layer 2**, and **employee read** payloads.

---

## Core rule shape (`CanonicalEntitlementRule`)

| Field | Purpose |
|--------|---------|
| `service_key` | Product vocabulary (`CanonicalServiceKey`), e.g. `visa_support`, `temporary_housing`. Maps to legacy `benefit_key` via `CANONICAL_SERVICE_TO_LEGACY_BENEFIT_KEY`. |
| `category` | HR / UI grouping (`EntitlementCategory`), e.g. `immigration`, `housing`. |
| `coverage_status` | `included` \| `excluded` \| `conditional` \| `unknown` (`CoverageStatus`). |
| `rule_strength` | `draft_only` \| `informational` \| `comparison_ready` \| `publish_ready` (`RuleStrength`). Controls how far the rule may surface (draft only vs narrative vs comparison vs publish bar). |
| `applicability` | Assignment types, family status, role hints, duration hints (`ApplicabilityFragment`). |
| `limit` | Optional structured limits (`LimitModel`); may be empty for informational rules. |
| `approval_required` | Boolean; can be sourced from rule metadata or HR override. |
| `employee_visible_value` | Employee-safe display subset (`EmployeeVisibleValue`). |
| `notes` | HR-only; overrides and clarifications (e.g. disambiguate `tax_briefing` vs `tax_filing_support` when both map to legacy `tax`). |
| `source_excerpt` | Clause / document excerpt. |
| `confidence` | Normalizer/extractor confidence. |
| `publishability` | Rule-level posture (`PublishabilityState`): draft-only vs eligible under gate vs published employee-visible. |
| `comparison_readiness` | `not_ready` \| `partial` \| `ready` (`ComparisonReadiness`), aligned with the comparison readiness **slice** in `policy_processing_readiness`. |
| Lineage (optional) | `layer2_benefit_rule_id`, `layer2_exclusion_id`, `source_clause_id`, `policy_document_id`, `policy_version_id`. |

**JSON Schema (draft-07):** `CANONICAL_ENTITLEMENT_RULE_JSON_SCHEMA` in the same module (for OpenAPI / validators).

---

## Canonical service keys (minimum set)

| `service_key` | Default legacy `benefit_key` | Default `EntitlementCategory` |
|---------------|------------------------------|--------------------------------|
| `visa_support` | `immigration` | `immigration` |
| `temporary_housing` | `temporary_housing` | `housing` |
| `home_search` | `relocation_services` | `housing` |
| `school_search` | `schooling` | `education` |
| `household_goods_shipment` | `shipment` | `relocation_logistics` |
| `tax_briefing` | `tax` | `tax` |
| `tax_filing_support` | `tax` | `tax` |
| `destination_orientation` | `relocation_services` | `integration` |
| `spouse_support` | `spouse_support` | `family` |
| `language_training` | `language_training` | `integration` |

**Note:** Two canonical tax services share one legacy key (`tax`); use `notes`, `source_excerpt`, or future metadata to distinguish. Similarly `home_search` and `destination_orientation` both default to `relocation_services` until Layer-2 taxonomy splits.

Helpers: `canonical_service_for_legacy_benefit_key`, `legacy_benefit_key_for_canonical_service`.

---

## Mapping: draft `draft_rule_candidates`

Normalization produces **`draft_rule_candidates`** on the mapped result and in `normalization_draft_json` (see `normalize_clauses_to_objects`, `build_normalization_draft_model`).

| Draft field | Canonical target |
|-------------|-------------------|
| `candidate_service_key` | Map legacy `benefit_key` → `service_key` via `canonical_service_for_legacy_benefit_key` (or set `service_key` directly when product adds it to draft). |
| `candidate_category` / theme | Map to `EntitlementCategory` (theme → category table can live in a future adapter). |
| `candidate_coverage_status` | Maps to `coverage_status` (same vocabulary where possible; normalize synonyms). |
| `candidate_exclusion_flag` | Contributes to `coverage_status` = `excluded` when true. |
| `amount_fragments`, `duration_quantity_fragments` | Populate `limit` and `applicability`. |
| `applicability_fragments` | `ApplicabilityFragment`. |
| `source_excerpt`, `confidence` | Direct. |
| `publishability_assessment` / `publish_layer_targets` | Inform `publishability` + `rule_strength` (MVP: use `infer_rule_strength` / `merge_publishability` heuristics). |

Rules that never become Layer-2 rows typically remain **`rule_strength: draft_only`** and **`publishability: draft_only`**, but stay valuable for HR review and future promotion.

---

## Mapping: Layer-2 publish rows

| Source | Canonical target |
|--------|-------------------|
| `policy_benefit_rules.benefit_key` | `service_key` via `canonical_service_for_legacy_benefit_key` (fallback: use key as legacy-only until mapped). |
| `benefit_category` | `category` (map theme → `EntitlementCategory` if needed). |
| `amount_*`, `currency`, `frequency`, `calc_type` | `limit` (+ derived `employee_visible_value`). |
| `metadata_json` (e.g. `approval_required`) | `approval_required`, extra notes. |
| `policy_exclusions` | Same `service_key` when `domain = benefit` and `benefit_key` set; `coverage_status` = `excluded`. |

**Publish gate** (`policy_publish_gate`) answers whether a **version** may be published; **`PublishabilityState`** on a rule describes that rule’s relationship to persistence and employee visibility (e.g. `eligible_under_gate` vs `published_employee_visible`).

---

## Mapping: employee read-only entitlements

Employee APIs should expose a **projection** of `CanonicalEntitlementRule`:

- Include **`employee_visible_value`**, **`coverage_status`**, **`service_key`** (or legacy `benefit_key` for backward compatibility), and **`rule_strength`** ≥ `informational` when product policy allows narrative display.
- Omit or redact **`notes`**, internal lineage, and draft-only rows unless explicitly product-approved.
- **Comparison** surfaces should require **`comparison_readiness: ready`** (and/or `rule_strength: comparison_ready` / `publish_ready`) consistent with `policy_comparison_readiness` / `benefit_rule_has_decision_signal`.

Resolved benefits from `policy_resolution` today are the runtime **read model**; the canonical model is the **target shape** for serializing those results and HR-facing merged views (implement adapters incrementally).

---

## Heuristic helpers (MVP)

In `policy_entitlement_model.py`:

- `infer_rule_strength(...)` — draft vs informational vs comparison vs publish-ready from booleans.
- `infer_comparison_readiness_from_flags(...)` — aligns with “required keys + decision signal” thinking from comparison readiness.
- `merge_publishability(...)` — combines Layer-2 presence, published version, gate blocked.

These are **defaults**; HR overrides and company policy may set `rule_strength`, `publishability`, and `comparison_readiness` explicitly in a future entitlement store.

---

## Relationship to existing modules

| Module | Role |
|--------|------|
| `policy_taxonomy` | Legacy `benefit_key` vocabulary and keyword resolution. |
| `policy_comparison_readiness` | Version-level comparison gate and `benefit_rule_has_decision_signal`. |
| `policy_publish_gate` | Employee publish gate on `policy_version`. |
| `policy_processing_readiness` | Normalization / publish / comparison **slices** for HR payloads. |
| `policy_entitlement_model` | **Canonical rule** enums, mappings, and JSON schema between the above. |
