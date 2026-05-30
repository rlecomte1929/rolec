# Parker Pipeline — Pre-Merge Audit (PRs #197–#206)

_Read-only audit. Generated 2026-05-30. Base for every PR: `feature/sec-004-rate-limit-coverage` (`81d98bc8`)._
_No PR was merged, rebased, or edited to produce this report._

## PR / branch inventory

| PR | Step | Branch | PR base | Stacked? |
|----|------|--------|---------|----------|
| #197 | A cox-survival | `audit/parker-step-A-cox-survival` | base | no |
| #198 | B benefit-optimizer | `audit/parker-step-B-benefit-optimizer` | base | no |
| #199 | C cluster-tiering | `audit/parker-step-C-cluster-tiering` | base | no |
| #200 | D prompt-registry | `audit/parker-step-D-prompt-registry` | base | no |
| #201 | E rlhf-lite | `audit/parker-step-E-rlhf-lite` | **D** | on D |
| #202 | F passport-ocr-oss | `audit/parker-step-F-passport-ocr-oss` | **E** | on E→D |
| #203 | G carbon-tco | `audit/parker-step-G-carbon-tco` | base | no |
| #204 | H conjoint | `audit/parker-step-H-conjoint` | base | no |
| #205 | I translation | `audit/parker-step-I-translation` | base | no |
| #206 | J nlg-variety | `audit/parker-step-J-nlg-variety` | base | no |

> Note: #199 (C) is **not** labeled `parker-audit`; it is otherwise a normal pipeline PR.
> E and F are a git stack (D→E→F); their diffs vs base include the upstream files.

---

## 1. Migration timestamp & table-name matrix

| PR | migration_file | timestamp | tables_created (matview = MV) |
|----|----------------|-----------|-------------------------------|
| #197 A | `20260601020000_ml_models.sql` | 20260601020000 | `ml_models` |
| #198 B | `20260601030000_benefit_optimizer.sql` | 20260601030000 | `benefit_priors` |
| #199 C | `20260601040000_supplier_cluster_cache.sql` | 20260601040000 | `supplier_cluster_cache` |
| #200 D | `20260601050000_prompt_registry.sql` | 20260601050000 | `prompt_versions`, `prompt_routing` |
| #201 E | `20260601060000_ai_human_feedback.sql` | 20260601060000 | `ai_human_feedback` |
| #202 F | `20260601070000_ocr_shadow_comparison.sql` | 20260601070000 | `ocr_shadow_comparisons`, `mv_ocr_shadow_comparison` (MV) |
| #203 G | `20260601080000_ai_unit_economics.sql` | 20260601080000 | `ai_model_energy_profiles`, `mv_ai_unit_economics` (MV) |
| #204 H | `20260601090000_conjoint.sql` | 20260601090000 | `conjoint_studies`, `conjoint_responses`, `conjoint_results` |
| #205 I | `20260601100000_translation_cache.sql` | 20260601100000 | `translation_cache` |
| #206 J | — (none) | — | — |

**Timestamp collisions:** none. Timestamps are strictly sequential (020000→100000, step 10000).
**Table-name collisions:** none. Every table name is unique across all PRs.
**Cross-PR FK references:**
- **`ai_human_feedback.prompt_version_id` → `prompt_versions(id)`** — E (#201) references a D (#200) table. **Hard cross-PR FK → D must precede E.**
- All other FKs target pre-existing tables (`companies`, `profiles`) or own-PR tables — no collision.
- `benefit_priors` is also written (no FK constraint) by H — see §4 (soft, app-level).

---

## 2. RLS posture per new table

Hard gate (CLAUDE.md): `ENABLE ROW LEVEL SECURITY` + ≥1 `CREATE POLICY` + `REVOKE ALL … FROM anon`.

| Table | PR | RLS enabled | ≥1 policy | REVOKE anon | Verdict |
|-------|----|-------------|-----------|-------------|---------|
| `ml_models` | A | yes | yes (2) | yes | ✅ pass |
| `benefit_priors` | B | yes | yes (2) | yes | ✅ pass |
| `supplier_cluster_cache` | C | yes | yes (3) | yes | ✅ pass |
| `prompt_versions` | D | yes | yes (3) | yes | ✅ pass |
| `prompt_routing` | D | yes | yes (3) | yes | ✅ pass |
| `ai_human_feedback` | E | yes | yes (2) | yes | ✅ pass |
| `ocr_shadow_comparisons` | F | yes | yes (2) | yes | ✅ pass |
| `mv_ocr_shadow_comparison` (MV) | F | n/a (matview) | n/a | **REVOKE anon + authenticated** | ✅ pass (see note) |
| `ai_model_energy_profiles` | G | yes | yes (3) | yes | ✅ pass |
| `mv_ai_unit_economics` (MV) | G | n/a (matview) | n/a | **REVOKE anon + authenticated** | ✅ pass (see note) |
| `conjoint_studies` | H | yes | yes (2) | yes | ✅ pass |
| `conjoint_responses` | H | yes | yes (3) | yes | ✅ pass |
| `conjoint_results` | H | yes | yes (2) | yes | ✅ pass |
| `translation_cache` | I | yes | yes (2) | yes | ✅ pass |

**No hard rejects.** Every base table satisfies all three gate conditions.

> **Materialized-view note:** Postgres matviews cannot carry RLS policies. F and G correctly
> compensate with defense-in-depth `REVOKE ALL … FROM anon` **and** `FROM authenticated`, so the
> MVs are reachable only via `service_role` (backend). This is the correct pattern for an MV and
> is **not** a gate failure.

---

## 3. Dual-layer router compliance — ⛔ SYSTEMIC FAILURE

CLAUDE.md hard rule: a new router must be registered in **both** `backend/app/main.py` **and**
`backend/main.py` (~the `app.include_router(...)` block, base lines ~665–713). Render boots
`uvicorn backend.main:app`; a router only in `backend/app/main.py` returns **405 in prod**.

`backend/main.py` imports each modular router individually (`from .app.routers import X as Y_router`
→ `app.include_router(Y_router.router)`). It does **not** mount the modular app wholesale (no
`create_app`/`.mount` of the sub-app). So single-registration genuinely 405s.

| PR | new router file | in `app/main.py` | in `backend/main.py` | Verdict |
|----|-----------------|:----------------:|:--------------------:|---------|
| #197 A | `backend/app/routers/predictions.py` | ✅ | ❌ | ⛔ 405 in prod |
| #198 B | `backend/app/routers/benefit_optimizer.py` | ✅ | ❌ | ⛔ 405 in prod |
| #199 C | _(no router)_ | — | — | ✅ n/a |
| #200 D | `backend/app/routers/admin_prompts.py` | ✅ | ❌ | ⛔ 405 in prod |
| #201 E | `backend/app/routers/ai_feedback.py` | ✅ | ❌ | ⛔ 405 in prod |
| #202 F | `backend/app/routers/admin_ocr_shadow.py` | ✅ | ❌ | ⛔ 405 in prod |
| #203 G | `backend/app/routers/admin_ai_unit_economics.py` | ✅ | ❌ | ⛔ 405 in prod |
| #204 H | `backend/app/routers/conjoint.py` | ✅ | ❌ | ⛔ 405 in prod |
| #205 I | `backend/app/routers/translation.py` | ✅ | ❌ | ⛔ 405 in prod |
| #206 J | `backend/app/routers/nlg.py` | ✅ | ❌ | ⛔ 405 in prod |

**All 9 router-bearing PRs fail dual-layer registration.** The pipeline's per-step verification
checked `create_app()` (the `backend/app/main.py` instance), which never serves prod traffic, so
the gap was invisible to it. Per-PR fix in §9. C (#199) has no router and is exempt.

---

## 4. Dependency-chain integrity

D ships `backend/app/services/prompt_registry.py` exporting (exact names confirmed):
`get_active_prompt` (line 94), `render_user_message`, `list_versions`, `create_version`,
`promote`, `set_canary_share`, dataclass `ActivePrompt`; tables `prompt_versions`, `prompt_routing`.

| Downstream | references | upstream ships it? | Type | Verdict |
|-----------|-----------|--------------------|------|---------|
| **E → D** | `prompt_registry.list_versions/create_version/...` (admin_prompts.py:25,61…); `preference_dataset_builder.py:127,225` JOINs `prompt_versions`; FK `ai_human_feedback.prompt_version_id` | yes — D ships all, exact names | **Hard** (FK + SQL JOIN + import) | D **must** precede E |
| F → D | F's own OCR files reference none of D's symbols; the prompt_registry refs in F's branch are **inherited via the D→E stack** | yes (inherited) | None (code) / stack (git) | F functionally independent; git ancestry chains D→E→F |
| I → D | none | — | None | I independent of D |
| I → G | emits `feature_key='translation'` trace line (translation_service.py:78) — same convention G's rollup consumes; **no import of G** | n/a (convention only) | **Soft** (data) | I independent; integrates at trace level |
| H → B | `conjoint_repo.push_to_benefit_priors()` upserts into B's `benefit_priors` — **guarded best-effort, no-ops if table absent** (conjoint_repo.py:262,297) | yes when B merged | **Soft** (graceful) | H independent; bridge activates post-B |

**No name-mismatch failures** — every referenced symbol/table is shipped by its upstream with the
exact name. The only ordering constraint that is *hard* is **D → E**.

---

## 5. File-conflict matrix

Conflicts **between independent (non-stacked) PRs** — these need resolution on merge:

| File | PRs touching | Independent-PR conflict? | Prediction |
|------|--------------|--------------------------|------------|
| `backend/app/main.py` | A B D E F G H I J | **Yes** (all router PRs) | Each adds an import + `include_router` in the same block. Additive & semantically stackable, but **textual conflicts on sequential merge** — resolve by accepting all hunks. |
| `backend/app/services/ai_trace_logger.py` | **D, G** (+E,F inherit D) | **Yes — D × G** | Overlapping hunks in `TraceSession` at lines ~79/88/155/185 (D +16/−0) vs ~79/88/148/155/165/185 (G +62/−1). **Real 3-way conflict**, manual resolution; semantically compatible (both add fields/methods). |
| `backend/database.py` | **D, G** (+E,F inherit D) | **Yes — D × G** | Overlapping hunks in `Database` at lines ~2433/14205/14218/14231 (D +27/−2 vs G +55/−2). **Real 3-way conflict**, manual resolution. |
| `backend/requirements.txt` | A B C H I | **Yes** | Additive; **A and C both add `scikit-learn>=1.3` + `scipy>=1.11`** (duplicate lines → dedupe). Textual only, no version contradiction. |

Stack-internal overlaps (D→E→F) — **not conflicts if merged in stack order D→E→F**:
`admin_prompts.py`, `prompt_registry.py`, `llm_policy_extractor.py`, `policy_assistant_rag_engine.py`,
`ai_feedback*`, `preference_dataset_builder.py`, `export_preference_dataset.py`,
`frontend/src/App.tsx`, `api/client.ts`, `navigation/routes.ts`, `AdminPrompts.tsx`,
migrations `…050000` / `…060000`, and the prompt-registry test files.

**Bottom line:** the only genuine independent-PR collisions are (1) the universal `app/main.py`
include block (trivial), (2) **D × G** on `ai_trace_logger.py` + `database.py` (non-trivial), and
(3) the A/C duplicate requirements lines (trivial).

---

## 6. Container build risk

Union of new top-level deps across all 10 PRs (all declared **lazy-imported** per their headers):

| Dep | Pin | PR(s) | Install weight |
|-----|-----|-------|----------------|
| `lifelines` | `==0.27.8` (exact) | A | medium (pulls autograd, formulaic, scipy, pandas) |
| `scikit-learn` | `>=1.3` | A, C | **heavy (~100 MB w/ deps)** |
| `scipy` | `>=1.11` | A, C | **heavy (~80 MB)** |
| `pandas` | `>=2.0` | A | **heavy (~60 MB)** |
| `pulp` | `>=2.7,<4` | B | ~30 MB (bundles CBC native binary) |
| `statsmodels` | `>=0.14` | H | **heavy (~40–50 MB; pulls patsy, scipy, pandas)** |
| `deepl` | `>=1.18` | I | tiny (pure-python HTTP client) |

- **Distinct new top-level deps: 7.** Heavy (>50 MB installed): `scikit-learn`, `scipy`, `pandas`,
  `statsmodels`. Estimated total image increase **~+300–500 MB** once the ML stack lands.
- **Pin contradictions: none.** A and C declare identical floors (`scikit-learn>=1.3`, `scipy>=1.11`).
  `lifelines==0.27.8` is the only exact pin (chosen for cross-runtime pickle stability, per A's
  comment) and is compatible with the scipy/sklearn/pandas floors. `numpy` is left unpinned (already
  a dependency).
- **Python:** must build on 3.9 (local) and 3.11 (Render prod) — the exact `lifelines` pin exists
  precisely to keep the pickled `CoxPHFitter` loadable across both. No constraint conflicts.
- D, E, F, G, J add **no** new deps.

---

## 7. Test-suite cross-contamination

- **E / F test suites** reference `prompt_versions`, `prompt_routing`, `ai_human_feedback`, but
  **create those tables inline** via `CREATE TABLE …` fixtures (`test_ai_feedback_router.py:32`,
  `test_preference_dataset_builder.py:35`, `test_admin_prompts_router.py:31`) on an in-memory DB.
  They do **not** depend on migrations being applied → no fixture-level contamination.
- The one structural coupling: E/F tests `from backend.app.services import prompt_registry` — that
  **module** must exist on disk. It does, because E/F are stacked on D. **If E or F were rebased onto
  `main` without D, the import would fail** (`ModuleNotFoundError`) and the suite would error in CI.
  → Keep the D→E→F stack intact; do not cherry-pick E/F ahead of D.
- No independent PR's tests reference another independent PR's new table (verified against the §1/§4
  table list). A, B, C, G, H, I, J test suites are self-contained.

**Flag:** E (#201) and F (#202) CI is green only because their PR base is D (resp. E). Against a
D-less `main` they would fail to import. Not a defect — a merge-order constraint.

---

## 8. Recommended merge order — **(b) integration branch**

Topological constraints: **D → E → F** (hard FK + git stack); A, B, C, G, H, I, J independent.
Soft, non-blocking integrations: H→B and I→G (both graceful, activate when the partner lands).

**Recommend (b): a single `audit/parker-integration` branch.** Rationale from the conflict matrix:

1. **All 9 router PRs need the identical `backend/main.py` registration fix (§3/§9)** — doing it once
   on an integration branch is far cheaper than 9 separate branch edits.
2. **The D × G conflict** on `ai_trace_logger.py` + `database.py` must be hand-resolved **once**;
   sequential per-PR merges (option a) force you to re-resolve the `app/main.py` block 9× and still
   hit D×G.
3. **One Render deploy + one end-to-end smoke** instead of 10.

Suggested integration sequence (resolve conflicts as they arise, add the 9 `backend/main.py`
registrations, validate, then squash-merge integration → `main` as one reviewed PR):

```
A → B → C → H → I → J        (independent; only app/main.py + requirements textual merges)
D → E → F                     (stack, in order)
G                             (resolve D×G on ai_trace_logger.py + database.py here)
```

- **(c) sprint batches** (A+G, B+H, D+E, C+F+I, J) is an acceptable fallback if smaller review units
  are preferred — five deploys. Caveat: keep F with the D+E stack (F is stacked on E), and whichever
  of D/G merges second still resolves the trace-logger/database.py conflict.
- **(a) sequential per-PR** is **discouraged**: 10 deploys, the `app/main.py` block re-conflicts on
  every merge, and the §3 registration fix must be applied to 9 branches separately.

---

## 9. Per-PR pre-merge fixes required

_Do not apply here — request from each branch owner. RLS gate (§2) needs no fixes; all tables pass._

**Dual-layer registration (§3) — every router PR.** In `backend/main.py`, add the import beside the
existing `from .app.routers import …` block (~line 129) and the `include_router` beside the existing
block (~line 665):

- **#197 A:** `from .app.routers import predictions as predictions_router` + `app.include_router(predictions_router.router)`
- **#198 B:** `from .app.routers import benefit_optimizer as benefit_optimizer_router` + `app.include_router(benefit_optimizer_router.router)`
- **#200 D:** `from .app.routers import admin_prompts as admin_prompts_router` + `app.include_router(admin_prompts_router.router)`
- **#201 E:** `from .app.routers import ai_feedback as ai_feedback_router` + `app.include_router(ai_feedback_router.router)`
- **#202 F:** `from .app.routers import admin_ocr_shadow as admin_ocr_shadow_router` + `app.include_router(admin_ocr_shadow_router.router)`
- **#203 G:** `from .app.routers import admin_ai_unit_economics as admin_ai_unit_economics_router` + `app.include_router(admin_ai_unit_economics_router.router)`
- **#204 H:** `from .app.routers import conjoint as conjoint_router` + `app.include_router(conjoint_router.router)`
- **#205 I:** `from .app.routers import translation as translation_router` + `app.include_router(translation_router.router)`
- **#206 J:** `from .app.routers import nlg as nlg_router` + `app.include_router(nlg_router.router)`
- **#199 C:** none (no router).

> After adding, verify with:
> `python3 -c "from backend.main import app; print([r.path for r in app.routes if '<prefix>' in r.path])"`

**Merge-conflict resolution (§5) — assign on integration:**
- **#203 G:** hand-merge `backend/app/services/ai_trace_logger.py` and `backend/database.py` against
  D's (#200) edits to the same `TraceSession`/`Database` regions (both additive; keep both sets).
- **#197 A / #199 C:** de-duplicate `scikit-learn>=1.3` and `scipy>=1.11` in `backend/requirements.txt`
  (keep one line each).

**Merge-order guards (§4/§7):**
- Merge **D (#200) before E (#201)**; keep the **D→E→F** stack intact (do not cherry-pick E/F onto a
  D-less `main` — their tests import `prompt_registry`).

---

_End of report. No PR was modified; this branch contains only this file._
