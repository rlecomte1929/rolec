# Pipeline — step ordering, dependencies, and rationale

## UI impact per step (at a glance)

Romain's mandate: maximize reuse of existing UI/UX. The 10 main pipeline steps
are deliberately backend-heavy. Anything significant on the frontend is
deferred to a follow-up prompt under `prompts/followups/` that you trigger
manually after reviewing a UI proposal.

| Step | UI impact | Approval gate |
|------|-----------|---------------|
| A — Cox survival | None | — |
| B — Benefit optimizer | None | — |
| C — Cluster tiering | None (tier labels unchanged) | — |
| D — Prompt registry | One small admin table at `/admin/prompts` | No |
| E — RLHF-lite | Adds one column to D's table | No |
| F — Passport OCR OSS | None (admin JSON endpoint only) | — |
| G — Carbon TCO | None (panel deferred to `followups/G-frontend.md`) | UI proposal required |
| H — Conjoint | None (employee+HR pages deferred to `followups/H-frontend.md`) | 2 UI proposals required |
| I — Translation | One small `<TranslatedText>` wrapper + 1 settings field | No |
| J — NLG variety | In-place updates to existing pages only | No |

**Deferred follow-up prompts** (paste manually after the main step ships):

- `prompts/followups/G-frontend.md` — Admin AI unit-economics panel.
- `prompts/followups/H-frontend.md` — Conjoint employee flow + HR results page.

The preamble template forces Claude Code to write `UI-PROPOSAL.md` and stop
before building any significant UI surface. You approve the proposal, then the
prompt is re-run to build the UI. This is the gate.



This file is the authoritative description of what each step does, in what
order, and which prior steps it consults. The orchestrator's hardcoded
`step_deps()` function reflects this graph.

## Sequencing

```
A → B → C → D → E → F → G → H → I → J
```

Sequential because each step opens a single PR and waits for human review.
Parallelisation is possible (independent steps can run on side branches) but
out of scope for the v1 orchestrator — checkpoint mode is by design.

## Dependency graph

| Step | Title | Hard deps | Soft deps |
|------|-------|-----------|-----------|
| A | Cox survival model for case timelines | — | — |
| B | Benefit-mix portfolio optimizer | — | A (optional duration weighting) |
| C | Cluster-relative supplier tiering | — | — |
| D | Prompt registry + canary A/B | — | — |
| E | RLHF-lite preference dataset | **D** | — |
| F | Open-source fallback for passport OCR | — | **D** (route pattern) |
| G | Carbon + per-customer AI unit economics | — | F (OSS cost model) |
| H | Conjoint analysis on benefit preferences | — | B (priors path) |
| I | Neural translation layer | — | **D** (registry), G (feature_key) |
| J | NLG variety | — | I (optional translated output) |

**Hard dep** = step writes code that compiles only after the dep ships.
**Soft dep** = step works without the dep but is better with it. If the soft
dep hasn't shipped, the prompt instructs Claude Code to fall back and note the
deviation in RESULT.md.

## Why this order

Three constraints drove the ordering:

1. **D before E, F, I.** Prompt registry is a platform unlock — once it exists,
   downstream steps register their prompts cleanly.
2. **G after F.** F documents the OSS passport OCR cost model; G ingests it
   for unit economics.
3. **A and B early.** Both surface metrics customers immediately ask about
   ("when will my case close" / "what's the optimal benefit mix"). Highest
   commercial leverage per unit of risk.

The strict A→J alphabetical sequence respects all three.

## Per-step quick reference

### A — Cox survival model for case timelines
- Stack: lifelines, scikit-learn.
- New table: `ml_models`.
- New route: `GET /api/cases/{case_id}/predicted-duration`.
- Env flag: `PREDICTIONS_ENABLED`.

### B — Benefit-mix portfolio optimizer
- Stack: cvxpy (fallback pulp).
- New table: `benefit_priors`.
- New route: `POST /api/hr/{company_id}/optimize-benefit-mix`.
- Returns shadow prices for buyer-facing explanations.

### C — Cluster-relative supplier tiering
- Stack: scikit-learn (KMeans), scipy.
- New table: `supplier_cluster_cache`.
- Modifies: `engine.tier()` signature (backward-compatible default).
- CLI: `python -m backend.scripts.refresh_supplier_clusters`.

### D — Prompt registry + canary
- New tables: `prompt_versions`, `prompt_routing`.
- New service: `prompt_registry.get_active_prompt(task_key)`.
- New admin route: `/api/admin/prompts` + promote/canary endpoints.
- Frontend: `/admin/prompts` page.
- **Contractual artefact:** canonical task_keys + `ActivePrompt` shape — E, F, I depend on these.

### E — RLHF-lite preference dataset
- New table: `ai_human_feedback`.
- New route: `POST /api/ai/feedback` (called by Notion review skill).
- New CLI: `python -m backend.scripts.export_preference_dataset`.
- Extends D's admin page with per-version win rates.

### F — Open-source fallback for passport OCR
- Stack: PaddleOCR + Florence-2 (via HF Inference Endpoints).
- New service: `passport_ocr_oss.py`.
- New env vars: `PASSPORT_OCR_OSS_SHARE` (rollout %), `SHADOW_COMPARE`.
- New view: `mv_ocr_shadow_comparison`.
- New admin route: `/api/admin/ocr-shadow-comparison`.
- ADR: `audit/adr/adr-001-self-hosted-passport-ocr.md`.

### G — Carbon + per-customer AI unit economics
- New table: `ai_model_energy_profiles` (seeded).
- New view: `mv_ai_unit_economics`.
- New service: `ai_carbon_estimator.py`.
- New module: `ai_feature_keys.py` (`Literal` types end-to-end).
- New admin route: `/api/admin/ai-unit-economics`.
- New frontend panel: `/admin/ai-economics`.

### H — Conjoint analysis on benefit preferences
- Stack: statsmodels.
- New tables: `conjoint_studies`, `conjoint_responses`, `conjoint_results`.
- New routes: `/api/hr/{company_id}/conjoint/*`.
- New frontend: employee choice flow + HR results page.
- Optionally pushes part-worths into B's `benefit_priors`.

### I — Neural translation layer
- Stack: deepl SDK + NLLB-200 via HF Inference Endpoints.
- New table: `translation_cache`.
- New service: `translation_service.translate()`.
- New route: `POST /api/translate`.
- New frontend: `<TranslatedText>` component, employee `preferred_language` setting.
- ADR: `audit/adr/adr-002-translation-routing.md`.

### J — NLG variety (3 of Parker's 14)
- Stack: networkx (TextRank), babel (locale formatting).
- New package: `backend/app/services/nlg/` with `data_to_text`, `frame_based`,
  `extractive_summarizer`.
- New routes: `/api/hr/{company_id}/exec-summary`, `/api/policies/{policy_id}/tldr`.
- All three functions LLM-free by design.

## Total surface modified (estimated)

- New tables: **9** (ml_models, benefit_priors, supplier_cluster_cache,
  prompt_versions, prompt_routing, ai_human_feedback, ai_model_energy_profiles,
  conjoint_studies, conjoint_responses, conjoint_results, translation_cache).
- New materialised views: **2** (mv_ocr_shadow_comparison, mv_ai_unit_economics).
- New routers: **9**.
- New frontend pages: **5** (admin/prompts, admin/ai-economics, hr/conjoint,
  journey/conjoint, hr/command-center NLG patches).
- New Python deps: lifelines, cvxpy (or pulp), scikit-learn, scipy, statsmodels,
  deepl, networkx, babel.

This is a non-trivial set of changes. Hence: checkpoint mode, one PR per step,
human review at every gate.
