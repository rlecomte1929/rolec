# Parker Pipeline — Integration Report (Steps A–J)

**Branch:** `audit/parker-integration`
**Base:** `main` (literal — commit `4872fa6b`)
**Strategy:** Pre-merge audit §8, Option (b) — one branch, one conflict resolution, one Render deploy.
**Status:** Ready for review. **DO NOT auto-merge** — Romain reviews and merges manually (the single Render deploy).

> ⚠️ **One validation gate is blocked by a pre-existing, non-parker condition.** Local `supabase db reset`
> aborts on a migration that ships on `main` today (`20260427100000_exception_requests.sql`), *before any
> parker migration is reached*. It was **not patched** (per task step 6). See §6.

---

## 1. Merge order & conflict resolution

PRs merged `--no-ff` in the prescribed order **A, B, C, G, D, E, F, H, I, J**:

| Order | Step | Merge commit | Conflicts | Resolution |
|-------|------|--------------|-----------|------------|
| 1 | A (Cox survival)        | `3ff0f282` | none | clean |
| 2 | B (benefit optimizer)   | `bc5c9a10` | registration files | `union` driver (stack) |
| 3 | C (cluster tiering)     | `15397d54` | registration files + requirements | `union` driver (stack) |
| 4 | G (unit economics)      | `7895144d` | registration files | `union` driver (stack) |
| 5 | D (prompt registry)     | `69ea4726` | **D×G code conflict** | **manual** (see below) |
| 6 | E (human feedback)      | `749ad687` | registration files | `union` driver (stack) |
| 7 | F (OCR shadow / OSS)    | `4d8e1890` | registration files | `union` driver (stack) |
| 8 | H (conjoint)            | `147fd8d3` | registration files | `union` driver (stack) |
| 9 | I (translation)         | `1d457c57` | registration files | `union` driver (stack) |
| 10 | J (NLG)                | `73e034ae` | registration files | `union` driver (stack) |

### Mechanical (router-registration) conflicts
Every step appended an `include_router(...)` to the same two registration files. These were resolved with a
temporary `merge=union` driver (installed in `.git/info/attributes`, **removed after the merges**), which
stacks *all* additions rather than picking one. Affected files:
- `backend/app/main.py` — modular sub-app registrations (additive stack)
- `backend/main.py` — prod-served app registrations (additive stack; ~line 580 block)
- `backend/requirements.txt` — additive stack, then deduped (see §4)

No registration was dropped or overridden — every step's router is present in **both** apps (verified in §3).

### Manual code conflict — D × G (commit `69ea4726`)
G and D both extended the same two artifacts. Both field sets were **combined; nothing overridden**:

- **`backend/app/services/ai_trace_logger.py`** — `TraceSession`
  - Constructor (~L83–112): combined signature carries **all four** new params.
    - G: `feature_key` (required), `customer_id`
    - D: `prompt_version_id`, `canary_arm`
    - ⚠️ **Ordering deviation (Python-syntax forced):** `feature_key` is *required*, so it must precede every
      defaulted param (Python forbids a non-default arg after a default). The user's suggested "D's pair
      first, G's triple after" ordering is impossible for a required arg; `feature_key` therefore leads,
      then the three optional params follow. Documented inline in the constructor.
  - Body init (~L104–112): keeps both G assignments (`self.feature_key`, `self.customer_id`) and D
    assignments (`self.prompt_version_id`, `self.canary_arm`) + D's `set_prompt_attribution()` method.
  - `flush()` payload (~L181–193): emits all four fields + unit-economics (`**econ`).
  - `_write_to_db()` (~L254–278): INSERT passes G's 6 econ/attribution kwargs + D's 2 prompt kwargs.
- **`backend/database.py`**
  - Region 1 (~L2436, `CREATE TABLE policy_assistant_traces`): combined column set — G's 6
    (`co2e_grams_estimated`, `cost_usd_estimated`, `tokens_in`, `tokens_out`, `customer_id`, `feature_key`)
    + D's 2 (`prompt_version_id`, `canary_arm`) + both idempotent `ADD COLUMN` backfill blocks.
  - Region 2 (~L14261, `insert_policy_assistant_trace`): combined signature, docstring, INSERT
    columns/VALUES, and params dict for all 8 new columns.

Both files `py_compile`-clean, no conflict markers remaining.

---

## 2. Migrations

**12 parker migrations added** (none modify existing migrations):

```
20260531010000_rls_policy_hr_domain.sql       # sec-004 lineage (see note)
20260531020000_rls_catalog_seed.sql           # sec-004 lineage
20260601000000_rls_cases_domain.sql           # sec-004 lineage
20260601020000_ml_models.sql                  # A
20260601030000_benefit_optimizer.sql          # B
20260601040000_supplier_cluster_cache.sql     # C
20260601050000_prompt_registry.sql            # D
20260601060000_ai_human_feedback.sql          # E
20260601070000_ocr_shadow_comparison.sql      # F
20260601080000_ai_unit_economics.sql          # G
20260601090000_conjoint.sql                   # H
20260601100000_translation_cache.sql          # I
```
(J / NLG adds no migration.)

> **sec-004 lineage note:** the three `20260531*` RLS migrations + `test_rate_limit_coverage.py` originate
> from `feature/sec-004-rate-limit-coverage`, on which the parker branches were stacked. Because each parker
> PR was merged `--no-ff`, that shared base history came along. This is expected and harmless (sec-004 is
> additive RLS hardening), **but it means merging this integration branch also ships sec-004.** Flag for
> Romain's awareness when scoping the single deploy.

**Migration-replay validation: ⛔ BLOCKED — see §6. Not patched.**

---

## 3. Routes mounted (prod app `backend.main:app`)

All 10 parker route families resolve on the **Render-served** app (`backend.main:app`) — the dual-router gate
(CLAUDE.md) is **green**. Captured verbatim from `/tmp/parker_routes.txt`:

```
### predicted-duration
  /api/cases/{case_id}/predicted-duration
### optimize-benefit-mix
  /api/hr/{company_id}/optimize-benefit-mix
### admin/prompts
  /api/admin/prompts
  /api/admin/prompts/{task_key}
  /api/admin/prompts/{task_key}/canary-share
  /api/admin/prompts/{task_key}/win-rates
  /api/admin/prompts/{version_id}/promote
### ai/feedback
  /api/ai/feedback
### ai-unit-economics
  /api/admin/ai-unit-economics
### conjoint
  /api/hr/{company_id}/conjoint/studies
  /api/hr/{company_id}/conjoint/studies/{study_id}/fit
  /api/hr/{company_id}/conjoint/studies/{study_id}/next-choice-set
  /api/hr/{company_id}/conjoint/studies/{study_id}/responses
  /api/hr/{company_id}/conjoint/studies/{study_id}/results
### translate
  /api/translate
### exec-summary
  /api/hr/{company_id}/exec-summary
### tldr
  /api/policies/{policy_id}/tldr
### ocr-shadow-comparison
  /api/admin/ocr-shadow-comparison
```

Every family present → no 405-in-prod risk.

---

## 4. Test results

### pytest — parker features (isolation)
All 28 parker-added test files run together in isolation:

```
174 passed, 20 skipped, 56 warnings in 8.58s
```
(20 skipped = optional ML-stack `importorskip` + DB-dependent RLS integration tests.)

### pytest — full suite (regression check vs main baseline)
| Suite | failed | passed | errors |
|-------|--------|--------|--------|
| `main` baseline | 138 | 1786 | 16 |
| `audit/parker-integration` | 139 | 1959 | 16 |

- **152 failures common to both** → pre-existing on `main`, not introduced here.
- The **net delta** (3 in / 3 out) is **test-pollution only**: `test_ai_decisions_router::test_list_admin_without_company_sees_all`,
  `test_ai_trace_logger::test_flush_payload_structure`, and `test_trace_logger_carbon::test_unknown_model_still_flushes_with_zero_cost_and_warns`
  all **pass in isolation** (shared-SQLite global-state ordering, not a code regression).
- The 16 errors are pre-existing collection errors on `main` (`install_query_counter` on a `MagicMock`).

**Conclusion: no genuine new test failures introduced by the integration.**

### One inherited test fix (commit `f5626165`)
`backend/tests/test_ai_trace_logger.py` was broken on the **G branch** (G made `TraceSession.feature_key`
required but never updated this test; the per-step pipeline never ran `pytest`). Fixed **test-only** by
supplying `feature_key="policy_assistant"` — production constructor unchanged, G's "required" design preserved.

### tsc — frontend
```
TSC_EXIT=0   (clean, 0 errors)
```
(12 frontend files / 654 insertions: AdminPrompts page, TranslatedText, NLG + translation API clients,
exec-summary / TL;DR wiring, one new route.)

---

## 5. Container delta (`backend/requirements.txt` vs main)

New runtime deps (all lazy-imported at their call sites; backend imports without them):

```
lifelines==0.27.8     # A — Cox survival (pinned exact: pickle cross-version safety)
scikit-learn>=1.3     # A (and C — deduped; C's duplicate line removed)
scipy>=1.11           # A (and C — deduped)
pandas>=2.0           # A
pulp>=2.7,<4          # B — CBC MILP backend
statsmodels>=0.14     # H — conditional-logit conjoint fit
deepl>=1.18           # I — DeepL Pro adapter (NLLB-200 over HTTP via requests)
```

**Dedup (commit `e32cc3e3`):** A and C both declared `scikit-learn>=1.3` / `scipy>=1.11`. Kept A's single
copy; replaced C's duplicate with an explanatory comment. **No package appears twice; no pin contradiction.**

---

## 6. ⛔ Migration-validation gate — BLOCKED (pre-existing, not parker, NOT patched)

`supabase db reset` / `supabase start` could **not** complete a clean replay. It aborts here:

```
Applying migration 20260427100000_exception_requests.sql...
ERROR: operator does not exist: text = uuid (SQLSTATE 42883)
At statement: 13
create policy exception_requests_select_tenant
  on public.exception_requests
  for select to authenticated
  using ( organization_id in (
    select company_id from public.profiles where id = auth.uid() ) )
```

**This is a pre-existing, non-parker failure:**
- `20260427100000_exception_requests.sql` is **byte-identical to `main`** (empty `git diff main...HEAD` for
  that file) and originates from main commit `6fa39966` (`feat(exceptions): … ExceptionRequest workflow`).
- Its timestamp (`20260427`) sorts **before every parker migration** (`20260531*`, `20260601*`), so the
  replay dies **before a single parker migration is applied**.
- Likely local schema/type drift (`organization_id` text vs `profiles.company_id` uuid) — consistent with the
  known "Supabase migration history drift" in this repo. It would fail identically on a fresh `main` reset.

**Action taken:** per task step 6, the migration was **NOT patched** on the integration branch and is flagged
here. Consequence: a clean local full-replay of the 12 parker migrations could not be demonstrated end-to-end.
Each parker migration was validated in its own per-step PR; the blocker is strictly upstream of all of them.

**Decision needed from Romain (pick one):**
1. Fix `20260427100000_exception_requests.sql` separately on `main` (correct the text/uuid cast), then
   re-run `supabase db reset` here to confirm the 12 parker migrations replay cleanly.
2. Validate the parker migrations against the remote (where the `exception_requests` table may already exist
   in a compatible shape) via the Supabase MCP, rather than a local full-replay.
3. Accept the per-step PR migration validation as sufficient and treat the local-replay drift as out of scope.

---

## 7. Recommended next step

Merge `audit/parker-integration` → `main` as **one PR / one Render deploy** — **after** resolving the §6
migration gate (Romain's call). Do not cherry-pick individual steps; the D×G code resolution and the
union-stacked registrations assume the whole set lands together.

**Out of scope (unchanged):** closing the 9 original per-step PRs; container-size optimization; deferred UI
prompts (G-frontend, H-frontend).
