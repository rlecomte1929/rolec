# HR rule override layer

HR adjustments to **effective** entitlements live in `policy_benefit_rule_hr_overrides` (+ append-only `policy_benefit_rule_hr_override_audit`). They do **not** modify `policy_document_*`, `normalization_draft_json`, or baseline `policy_benefit_rules` rows.

## API

- `PATCH /api/company-policies/{policy_id}/versions/{version_id}/benefits/{benefit_rule_id}/hr-override` — merge JSON fields into the override row.
- `DELETE .../hr-override` — remove override (audit retained).

## Effective computation

`policy_hr_rule_override_layer.compute_entitlement_value_trace` returns:

- `baseline` — values read from Layer-2 benefit rule (+ metadata).
- `hr_override` — nullable HR-only patch fields.
- `effective` — merged outcome used for resolution and comparison.

Employee resolution attaches `entitlement_value_trace` on each resolved benefit. HR review payload includes `hr_overrides` and `entitlement_effective_preview`.

## Comparison

`evaluate_policy_comparison_readiness`, `enrich_resolved_benefits_with_rule_comparison`, and `evaluate_version_comparison_readiness` merge HR overrides before evaluating rules.
