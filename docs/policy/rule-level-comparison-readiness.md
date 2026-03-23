# Rule-level comparison readiness

Version-level gates (`evaluate_version_comparison_readiness`) answer whether the **published** policy is structurally usable for the wizard. **Rule-level** readiness (`policy_rule_comparison_readiness`) answers whether each **Layer-2 row or draft candidate** supports:

| Level | Meaning |
|-------|---------|
| `full` | Numeric/duration caps, or deterministic inclusion/exclusion (no budget delta for pure exclusions). |
| `partial` | Coverage/included/excluded can be shown; budget delta vs quotes is not reliable. |
| `not_ready` | Too ambiguous (e.g. vague framing + low confidence). |

## API

- `evaluate_rule_comparison_readiness(rule, rule_kind=None)` — benefit rule, exclusion, or `draft_candidate`.
- `evaluate_policy_comparison_readiness(normalized=...)` or `(benefit_rules=..., exclusions=...)` or `(policy_version_id, db)` — aggregates required comparison keys (`temporary_housing`, `schooling`, `shipment`) into `policy_level` and `per_benefit_key`.

## Integrations

- **`evaluate_version_comparison_readiness`** — merges `rule_comparison_readiness`, `rule_evaluations`, and `comparison_ready_strict` into the cached version payload.
- **`build_processing_readiness_envelope` / `evaluate_stored_policy_readiness`** — adds `comparison_rule_readiness` (summary) to HR `policy_readiness`.
- **Employee policy** — `_finalize_employee_policy_resolution` enriches each benefit with `rule_comparison_readiness` via source `policy_benefit_rules` (no DB migration on resolved rows).
- **`compute_policy_service_comparison`** — enriches benefits, copies readiness onto each comparison row, and uses it in `_compare_single` for `informational` / `uncertain` statuses when caps are missing.

See module docstring in `backend/services/policy_rule_comparison_readiness.py` for reason codes.
