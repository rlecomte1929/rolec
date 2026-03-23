# Policy normalization: readiness vs invalid `policy_versions` payload

## What was going wrong (typical “policy summary” case)

For documents classified as **`policy_summary`** (e.g. long-term assignment summaries), clause segmentation often yields **no mappable benefit or exclusion rows**. Earlier behavior treated that as a hard **normalization failure (422)** or surfaced **publish gate** errors as opaque **500**s with misleading “invalid policy_versions payload” copy in the UI.

## Root cause category

**Normalize vs publish** were conflated: **draft persistence** (Layer-2 mapping + `policy_version`) is separate from **employee publish**, which requires at least one benefit rule or exclusion plus provenance checks (`policy_publish_gate`).

## Current behavior

1. **Draft gate (422 `NORMALIZATION_BLOCKED`)** only when normalization cannot produce a **meaningful draft**: e.g. `processing_status == failed`, or **unknown scope with empty Layer-2** (no benefits and no exclusions).
2. **Known scope + empty Layer-2** (common for `policy_summary`): **HTTP 200** — draft `policy_version` is created with `publishable: false`, `outcome: "normalized_but_not_publishable"`, and `readiness_issues` explaining why auto-publish was skipped.
3. **Pydantic validation (422, `validation_failed`)** on the assembled `policy_versions[0]` row and Layer-2 payloads **before** `INSERT`.
4. **Persistence errors** → 422 `persistence_failed` (`error_code: PERSISTENCE_FAILED`, with `persistence_stage` = `policy_version` or `layer2`) where we catch `IntegrityError` / `OperationalError`.
5. **Publish** runs **after** persistence only if `publishable` is true. **Publish gate** failures → **HTTP 200** with `outcome: "publish_blocked"` and `publish_block_detail`, not `normalization_failed`.

See **`normalize-vs-publish.md`** for the separation in one page.

## Diagnostic CLI

```bash
PYTHONPATH=. python3 backend/scripts/diagnose_policy_normalize_document.py '<policy_documents.uuid>'
```

Prints readiness (`draft_blocked`, `publishable`, `readiness_status`), a JSON preview of the version payload, and pydantic validation results (no DB writes).

## API shape (422)

```json
{
  "ok": false,
  "normalized": false,
  "publishable": false,
  "published": false,
  "outcome": "normalization_blocked",
  "error_code": "NORMALIZATION_BLOCKED",
  "message": "...",
  "details": [{ "field": "...", "issue": "...", "expected": "...", "actual": "..." }],
  "request_id": "...",
  "document_id": "..."
}
```

`outcome` is `validation_failed` or `persistence_failed` for the corresponding `error_code` values. `INVALID_POLICY_VERSION_SCHEMA` uses the same envelope with Pydantic-derived `details` (legacy clients may still see `INVALID_POLICY_VERSIONS_PAYLOAD` in old logs).

## Success shape (200)

```json
{
  "ok": true,
  "normalized": true,
  "publishable": false,
  "published": false,
  "outcome": "normalized_but_not_publishable",
  "readiness_status": "draft_no_benefits_or_exclusions",
  "readiness_issues": [],
  "policy_id": "...",
  "policy_version_id": "...",
  "summary": {}
}
```
