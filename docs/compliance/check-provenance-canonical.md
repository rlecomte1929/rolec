# Canonical check + provenance shape (v1)

This is the **target contract** for APIs and UI. v1 implements a subset in JSON + Python enrichment; DB tables can mirror later.

## Check definition (catalog)

| Field | Type | Notes |
|-------|------|--------|
| `check_key` | string | Stable id, e.g. `readiness.checklist.sg_ep_contract` |
| `title` | string | Display |
| `description` | string | Longer text |
| `destination_key` | string? | ISO2 or null for global |
| `route_key` | string? | e.g. `employment` |
| `severity` | enum | `info` / `low` / `medium` / `high` |
| `check_type` | enum | `deterministic` / `heuristic` / `advisory` |
| `human_review_required_if_unverified` | bool | Default true for immigration-adjacent |

## Check execution (result)

| Field | Type | Notes |
|-------|------|--------|
| `assignment_id` | string | |
| `check_key` | string | |
| `status` | enum | `pass` / `fail` / `warning` / `unknown` |
| `reason` | string | Human-readable |
| `matched_inputs` | object | Redacted snapshot of fields used |
| `generated_action` | object? | Title, owner, urgency |
| `confidence_level` | enum | `high` / `medium` / `low` / `none` |
| `human_review_required` | bool | |

## Reference / provenance

| Field | Type | Notes |
|-------|------|--------|
| `source_type` | enum | `official_gov` / `official_agency` / `company_policy` / `internal_template` / `manual_expert` / `unverified` |
| `source_title` | string | |
| `source_url` | string? | No URL in UI hardcoding |
| `source_publisher` | string? | |
| `source_last_reviewed_at` | date? | |
| `source_effective_date` | date? | |
| `source_quote_or_excerpt` | string? | Optional short excerpt; respect copyright |
| `reference_strength` | enum | `official` / `secondary` / `internal` / `unverified` |

## Principle

No compliance **statement** is presented as authoritative immigration fact without a stored provenance record **and** explicit labeling. Unknown → `unknown` status + human review.

## v1 mapping

- **Readiness checklist row** → execution row is implied by `status` + template item; provenance = `primary_reference` + `content_tier` + `reference_note`.
- **Assignment compliance** → `ComplianceCheck` extended fields + `meta` on report.
