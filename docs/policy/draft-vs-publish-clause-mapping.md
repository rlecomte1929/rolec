# Draft vs publish-layer clause mapping

Policy clauses are mapped in **`normalize_clauses_to_objects`** (`backend/services/policy_normalization.py`) to two levels:

## A. `draft_rule_candidates` (retention / review)

Emitted whenever a clause has enough signal to be worth surfacing: resolved or inferred service hints, exclusion wording, numeric or currency fragments, applicability (assignment type, family context, role hints), duration/quantity snippets, non-trivial text, or extractor hints.

Each candidate includes **`publishability_assessment`** and **`publish_layer_targets`** so the UI and automation can tell what was actually written to relational Layer 2 in this run.

- **Narrative or vague coverage** (“may be provided”, “depending on …”) → usually **`draft_only`**: not dropped, but no `policy_benefit_rules` row unless there is a **structured cap** or other strong signal.
- **Ambiguous narrative** with no taxonomy match → **`draft_only`** with `candidate_coverage_status: unknown`.

Draft rows are also stored on the version under **`normalization_draft_json.draft_rule_candidates`** (see `build_normalization_draft_model`).

## B. Publish-layer rows (relational policy)

Created only when current rules say the clause is safe to materialize:

| Output | When |
|--------|------|
| **`policy_benefit_rules`** | `clause_type` is benefit-like, a **benefit key** resolves, the clause is **not** treated as a published exclusion for that pass, and either the wording is **not** vague framing **or** there is a **structured monetary cap** (amount + currency or percent-of-salary style cap). |
| **`policy_exclusions`** | `clause_type` / hint says exclusion, or the text matches **exclusion phrases**. Standalone exclusion text without a resolved benefit still publishes as a **scope** exclusion unless a **structured cap** is present in the same clause (avoids suppressing a benefit in mixed sentences). Service-specific lines (e.g. school search) publish with **`domain: benefit`** when a key resolves. |
| **`policy_rule_condition` / applicability** | Only when a **benefit rule** was emitted for that clause (no orphan conditions). |

Employee-facing publish gates still rely on **relational Layer 2 + readiness**; draft candidates are for HR review, diagnostics, and future promotion into rules.
