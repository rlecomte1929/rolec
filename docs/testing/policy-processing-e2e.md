# Policy processing E2E tests

## Location

- Tests: `backend/tests/test_policy_processing_e2e.py`
- Fixtures: `backend/tests/fixtures/policy_processing_e2e_fixtures.py`

## How to run

From the **repository root** (so `backend` is importable as a package):

```bash
PYTHONPATH=. ./venv/bin/python -m unittest backend.tests.test_policy_processing_e2e.PolicyProcessingE2ETests -v
```

Uses the same SQLite file / `DATABASE_URL` as `backend.main` when the app is imported (typically `./relopass.db` in dev).

## What is covered

| Path | Flow |
|------|------|
| **A — Summary-only** | HR-owned policy document + weak narrative clauses → `POST .../normalize` → draft, not publishable, comparison tier partial/not_ready, employee entitlements 200. |
| **B — Starter template** | Empty company → `POST /api/hr/company-policy/initialize-from-template` (draft) → explicit publish → employee entitlements + `POST .../service-comparison-engine` with selected services. |
| **C — Structured upload** | Assignment-policy document + capped benefits + exclusion → normalize (auto-publish when publishable) → publish readiness `ready`, published, entitlements + within/exceed envelope checks. |

Service slice exercised in B/C: `visa_support`, `temporary_housing`, `home_search`, `school_search`, `household_goods_shipment` (via Layer-2 `benefit_key` mapping and canonical service keys on the comparison engine).

## Architectural gaps / sharp edges

1. **`initialize-from-template` requires zero existing `company_policies` for that company**  
   E2E therefore **must** use an isolated `company_id` per scenario (or ordered teardown). Reusing a demo company that already has a policy yields `409 POLICY_ALREADY_EXISTS`.

2. **`Database.create_company` is Postgres-oriented**  
   It introspects `information_schema.columns`, which **does not exist on SQLite**. The E2E helper `_create_company_for_e2e` inserts into `companies` using `PRAGMA table_info` on SQLite and delegates to `create_company` on other dialects. A durable fix would be to teach `create_company` to branch on dialect (same pattern as other legacy SQLite paths).

3. **Section labels steer `resolve_benefit_key` before raw text**  
   A clause with `section_label` `"Housing"` can resolve to generic `housing` instead of `temporary_housing` even when `raw_text` says “temporary housing”. The employee comparison gate requires **`temporary_housing`** (not `housing`), so structured fixtures must avoid ambiguous section titles. This is easy to hit with real extraction/segmentation output.

4. **Starter template is draft-only until HR publishes**  
   Product API intentionally does not publish on init. E2E B calls `POST /api/company-policies/{policy_id}/versions/{version_id}/publish` so resolution, entitlements, and the comparison engine see a **published** version (required for `published_comparison_ready` and ungated numeric deltas on the employee path).

5. **In-process comparison-readiness cache**  
   `evaluate_version_comparison_readiness` caches per `policy_version_id` for a short TTL. Tests call `invalidate_comparison_readiness_cache(version_id)` after publish to avoid flakiness when the suite runs quickly in one process.

6. **Auth password hashing in tests**  
   Login uses `pbkdf2_sha256` (see `backend/main.py`); E2E seeds users with the same scheme. Do not use bcrypt-only hashes in these tests unless the app’s login path is aligned.
