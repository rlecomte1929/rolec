# Normalize vs publish (HR policy pipeline)

**Normalize** turns segmented `policy_document_clauses` into a **draft** `policy_version` plus Layer-2 rows (`policy_benefit_rules`, `policy_exclusions`, etc.). It succeeds with HTTP 200 when that draft can be persisted, even if the result is **not** eligible for employee-facing publication.

**Publish** (employee consumption) is a separate step governed by `policy_publish_gate.require_employee_publishable_policy_version`: at least one benefit rule or exclusion, provenance, and a non-failed source document. The normalize endpoint evaluates publish **after** persistence; gate failures return **HTTP 200** with `outcome: "publish_blocked"`, `normalization_result_code: "NORMALIZED_PUBLISH_BLOCKED"`, `publish_block_code` (e.g. `PUBLISH_BLOCKED_NO_LAYER2_RULES`), and `publish_block_detail` (human message)—not a schema/validation error.

422 **`NORMALIZATION_BLOCKED`** means normalization cannot produce a **meaningful draft** (e.g. failed document processing, or unknown scope with no mapped benefits/exclusions). Schema or DB issues use **`validation_failed`** / **`persistence_failed`** outcomes on the same 422 shape.

After a successful normalize, a rich **`normalization_draft`** snapshot (metadata, clause/rule **candidates**, readiness) is stored on **`policy_versions.normalization_draft_json`** and returned on the normalize response and HR **`GET .../normalized`** — independent of whether Layer-2 benefit/exclusion rows are empty.

See also: `normalization-readiness-and-validation.md`, `policy-processing-readiness.md`.
