# Published policy — what employees may consume

This document defines the **publishing model** for company HR policies: which artifacts exist, what HR sees before publish, what employees see after publish, and how **valid / normalized / comparison-ready** state is expressed.

Implementation touchpoints:

- **Publish gate:** `backend/services/policy_publish_gate.py` → `require_employee_publishable_policy_version`
- **Employee resolution:** `policy_resolution.resolve_policy_for_assignment` + `get_published_policy_version` (only `policy_versions.status = 'published'`)
- **Comparison readiness:** `policy_comparison_readiness.evaluate_version_comparison_readiness` (explicit non-ready vs ready; see [comparison-readiness-and-fallback.md](./comparison-readiness-and-fallback.md))
- **Services page:** [services-page-policy-consumption.md](./services-page-policy-consumption.md)

---

## 1. Draft vs extracted vs normalized vs published (distinctions)

| Layer | Artifact | Typical location | Employee-visible? |
|-------|-----------|------------------|---------------------|
| **Upload** | Raw file / storage object | `policy_documents.storage_path` | **No** — not used for benefit or comparison logic. |
| **Extracted** | Text, optional `extracted_metadata`, `processing_status` on document | `policy_documents` | **No** — metadata is **Layer 1**; must not drive employee comparison (see [metadata-vs-decision-layer.md](./metadata-vs-decision-layer.md)). |
| **Segmented** | Clauses + `normalized_hint_json` (hints, not authoritative policy) | `policy_document_clauses` | **No** for employee UX; input to normalization only. |
| **Normalized (structured)** | `policy_version` + `policy_benefit_rules`, `policy_exclusions`, conditions, links | `policy_versions` (+ child tables) | **Only after publish** — draft / `auto_generated` / review rows are HR-only until `status = published`. |
| **Published** | Same structured rows, version row `status = 'published'` | `policy_versions` | **Yes** — this is the sole consumable contract for employee policy APIs below. |
| **Resolved (per assignment)** | Snapshot for an assignment | `resolved_assignment_policies` | **Yes** — derived from **published** version + assignment context; safe cache for reads. |

**Valid** (operational meaning in this repo):

- Normalization **input** validated by `normalization_input.validate_and_prepare_normalization_input` before `run_normalization` (blocking issues → 422, no new version).
- **Publish** validated by `require_employee_publishable_policy_version`: non-empty structured output (≥1 benefit rule or exclusion), provenance (`source_policy_document_id` and/or `auto_generated`), and source document not `processing_status = failed` when linked.

Failed normalization that **does not** create a publishable version never becomes employee-visible. If normalization persists a version but **publish** fails (e.g. empty rules), the publish gate returns **400**; auto-publish after normalize propagates that **HTTPException** to the client.

**Comparison-ready** vs **explicitly non-ready**:

- Computed at read time from published version rules (`policy_comparison_readiness`) and exposed as `comparison_available` on employee policy payloads.
- A published policy may be **valid and normalized** but **not** comparison-ready; employees still see **resolved benefits** where appropriate, but **must not** run gated comparison UX (see comparison-readiness doc).

---

## 2. What employee views are allowed to consume

Employee-facing features **must** use only:

1. **`policy_versions` with `status = 'published'`** (via `get_published_policy_version` / `find_first_published_company_policy`), and  
2. **Structured child data** for that version (benefit rules, exclusions, …) and/or **`resolved_assignment_policies`** built from that version.

**Allowed sources (canonical company policy path):**

| Surface | Consumes |
|---------|----------|
| Assignment policy, policy-budget, services-policy-context, policy-service-comparison (gated), policy-envelope | Resolved benefits + published version id; **no** `extracted_metadata` for decisions |
| Package summary / comparison bars | Policy-budget + comparison gate (Layer 2) |
| Services cards | `services-policy-context` from resolution |

**Not allowed for employee policy **decisions**\*:**

- Raw `policy_documents` file or text alone  
- `policy_documents.extracted_metadata` alone  
- Clause-level hints as the authority for “covered / capped” (hints feed normalization; published rules are authoritative)

\*HR workspace may show documents and extraction for editing; that is not employee consumption.

**Legacy note:** `GET /api/employee/policy/applicable` may use the separate **`hr_policies`** JSON store (`get_published_hr_policy_for_employee`). That path is **not** the same as `company_policies` / `policy_versions`. Prefer **`getResolvedPolicy`** / assignment policy endpoints for the canonical model.

---

## 3. What HR sees before publish vs what employees see after publish

### Before publish (HR / admin)

- **Policy documents:** upload status, extraction, reprocess, clauses, Layer-1 metadata and hints.  
- **Draft / auto_generated / review versions:** full benefit rules, exclusions, version status in review workspace.  
- **Normalize:** creates a new `policy_version` (typically `auto_generated`) and attached rows; may **auto-publish** when publish gate passes.  
- **Publish actions:** `POST .../versions/{id}/publish`, `POST .../versions/latest/publish`, admin `publish_version_id`, or PATCH `status: published`. All run **`require_employee_publishable_policy_version`** before `status` becomes `published`.

HR can edit structured rules on **non-published** versions without affecting employees until a version is successfully published.

### After publish (employees)

- **Only** the **published** `policy_version` for that company policy (others archived from employee lookup by publish helper).  
- **Resolved** benefits for their assignment (assignment type, family, etc.).  
- **`comparison_available`** and per-category hints where implemented — reflects **comparison-ready** or **explicitly non-ready**, not raw extraction quality.

Employees **do not** see:

- Unpublished versions  
- Upload-only state without a published normalized version  
- Empty structured versions (blocked at publish)

---

## 4. Publish gate rules (summary)

`require_employee_publishable_policy_version` enforces:

1. **Non-empty Layer 2:** at least one `policy_benefit_rules` or `policy_exclusions` row for the version.  
2. **Provenance:** `source_policy_document_id` **or** `auto_generated` truthy (normalize + template flows).  
3. **Failed document:** if `source_policy_document_id` is set, the source `policy_documents.processing_status` must not be `failed`.

This prevents “usable policy” from being an empty shell or an untraced row while still allowing template-seeded companies (`auto_generated`, rules present, document optional).

---

## 5. Related documents

- [metadata-vs-decision-layer.md](./metadata-vs-decision-layer.md)  
- [comparison-readiness-and-fallback.md](./comparison-readiness-and-fallback.md)  
- [services-page-policy-consumption.md](./services-page-policy-consumption.md)  
- [minimum-normalized-policy-schema.md](./minimum-normalized-policy-schema.md)  
