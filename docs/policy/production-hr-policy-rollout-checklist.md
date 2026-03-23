# HR policy workflow — production schema & rollout checklist

Use this after deploying backend + running Supabase (or Postgres) migrations. Aligns code paths with `company_policies`, `policy_documents`, normalization, overrides, and policy review.

## A. Root cause addressed (initialize-from-template / normalize)

- **`company_policies.is_default_template`** is **`boolean`** in Postgres (`supabase/migrations/20260408000000_policy_template_and_source.sql`).
- Application inserts **must** bind Python `True`/`False` (or cast in SQL). Sending **integer 0/1** causes:
  - `(psycopg2.errors.DatatypeMismatch) column "is_default_template" is of type boolean but expression is of type integer`
- Backend fix: `Database.create_company_policy` uses `_policy_bool_bind()` for `is_default_template` (same pattern as `policy_versions.auto_generated`).

## B. Required migrations (verify applied in order)

| Area | Migration (representative) | Notes |
|------|----------------------------|--------|
| Company policies + benefits | `20260301021000_company_policies_and_benefits.sql` | Base `company_policies` / `policy_versions` / rules |
| Policy documents | `20260329000000_policy_documents.sql` | HR document intake |
| Document clauses | `20260330000000_policy_document_clauses.sql` | Segmentation |
| Normalization | `20260331000000_policy_normalization.sql` | Normalized artifacts |
| Version normalization state | `20260321120000_policy_versions_normalization_state.sql` | State machine |
| Draft JSON | `20260422100000_policy_versions_normalization_draft_json.sql` | Draft persistence |
| Template source + boolean | **`20260408000000_policy_template_and_source.sql`** | **`is_default_template` boolean**, `template_source`, `default_policy_templates` |
| Boolean repair (drift) | **`20260423130000_company_policies_is_default_template_boolean_repair.sql`** | If `is_default_template` exists as **integer**, coerces to **boolean** (fixes persistent `DatatypeMismatch` after bad manual DDL) |
| HR overrides | `20260422120000_policy_benefit_rule_hr_overrides.sql` | Override layer |
| Production catch-up | `20260404000000_production_policy_catchup.sql` | Environment-specific fixes |

If **`20260408000000`** is missing in production, template columns may be absent or differ; if an older manual column was **integer**, align to migration boolean or alter column type.

## C. Code paths vs schema

| Feature | Tables / columns | Missing migration symptom |
|---------|------------------|---------------------------|
| Starter template init | `company_policies` (+ optional template columns), `policy_versions`, `policy_benefit_rules` | 500 on insert; UndefinedColumn in logs |
| Upload | `policy_documents`, storage bucket `hr-policies` | 503 / upload error codes |
| Normalize | Same + clauses, normalization draft/state columns | 500 mid-transaction; partial rows |
| Policy review (API) | Depends on deployed review views/tables | Empty review or 404 |
| Overrides | `policy_benefit_rule_hr_overrides` | 500 on save |

## D. CORS + 500 responses

- **Single** global `Exception` handler should remain (duplicate handlers can override and confuse CORS/error bodies).
- If the browser shows **CORS error** on 500, also check **proxy/gateway timeout** (no response body → no ACAO). Fix DB 500 first; then increase proxy read timeout if uploads legitimately exceed it.

## E. Upload timeouts

- **`POST /api/hr/policy-documents/upload`** runs **synchronously**: storage upload → DB row → **extraction** → optional **clause segmentation** before HTTP response.
- **Status 0 / ERR_TIMED_OUT** is often **client or proxy timeout** while the server is still working; mitigations: raise proxy/browser limits, reduce file size for tests, or (product change) return **202 + job id** and process in background.

## F. Debug: prove bind type on failure

If `create_company_policy` still errors after deploy, server logs now include  
`bind_isdef_type=… bind_isdef_repr=… engine_is_sqlite=…` on that failure.

- Expect Postgres: `bind_isdef_type=bool`, `engine_is_sqlite=False`.
- If you see `int` or `engine_is_sqlite=True` against a Postgres URL, the wrong build or `DATABASE_URL` is in play.

Optional NDJSON (local dev): set `RELOPASS_DEBUG_NDJ=1` or `RELOPASS_DEBUG_NDJ=476bd2` and append lines to `.cursor/debug-476bd2.log` on insert failure.

## G. Post-deploy smoke (5 min)

1. HR: **initialize-from-template** on empty company → **200**, draft created.  
2. HR: **upload** small PDF → **200** or **207** with `request_id`; response includes `ingest_duration_ms` on success.  
3. HR: **normalize** on ready document → **200** (or structured error, not opaque 500).  
4. Employee: policy view with published policy loads without console CORS errors on API failures (after A–D).
