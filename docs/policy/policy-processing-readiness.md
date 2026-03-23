# Policy processing readiness (three tiers)

HR and diagnostics expose a single object **`policy_readiness`** with three independent slices:

| Slice | Question |
|--------|----------|
| `normalization_readiness` | Can we justify a **meaningful draft** from intake (classify, scope, clauses, mapped Layer-2)? |
| `publish_readiness` | Can the current data satisfy **employee publish** (Layer-2 bar + source document health + published state for stored policies)? |
| `comparison_readiness` | Can the **service comparison** engine run meaningful within/exceeds checks (canonical benefit keys, caps/amounts, applicability)? |

Each slice is:

```json
{ "status": "ready|partial|not_ready", "issues": [{ "code": "...", "message": "...", "field": "..." }] }
```

Stable issue codes include: `MISSING_DOCUMENT_TYPE`, `MISSING_SCOPE`, `NO_CLAUSE_CANDIDATES`, `NO_LAYER2_RULES`, `NO_PUBLISHABLE_BENEFITS_OR_EXCLUSIONS`, `NO_CANONICAL_SERVICE_MATCH`, `NO_STRUCTURED_LIMITS`, `ONLY_SUMMARY_LEVEL_SIGNALS`, `COVERAGE_ONLY_NO_CAPS`, `READY_FOR_DRAFT_ONLY`, `READY_FOR_PUBLISH`, `READY_FOR_COMPARISON`, `SOURCE_DOCUMENT_FAILED`, `APPLICABILITY_INSUFFICIENT`.

## Normalization draft blob

Persisted on **`policy_versions.normalization_draft_json`** after a successful normalize (and returned as **`normalization_draft`** on the normalize response and **`GET .../normalized`**). It duplicates **`readiness`** inside the JSON for offline diagnostics and HR review, and adds **`document_metadata`**, **`clause_candidates`**, and **`rule_candidates`** so narrative / summary policies retain structured signal even when Layer-2 rows are empty. Employees still consume only published relational Layer-2 + comparison gates.

## Where it appears

- **`POST /api/hr/policy-documents/{id}/normalize`** — success body includes `policy_readiness` and `normalization_draft`; `NORMALIZATION_BLOCKED` (422) includes `policy_readiness` when mapping ran.
- **`GET /api/company-policies/{policy_id}/normalized`** — `policy_readiness` when `include_readiness=true` (default); **`normalization_draft`** from the latest version row (large JSON omitted from the nested `version` object; use top-level `normalization_draft`). Summary mode loads Layer-2 rows only for readiness evaluation.
- **`backend/scripts/diagnose_policy_normalize_document.py`** — prints the envelope after clause mapping.

See also `normalize-vs-publish.md` and `policy_comparison_readiness.py` (published-version gate for employees).
