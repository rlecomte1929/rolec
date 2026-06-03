# ReloPass × Phil Parker Framework — Strategic AI/ML Audit

**Date:** 2026-05-30
**Auditor:** Claude (acting as AI/IT software-development expert)
**Source documents:**
- `Phil Parker AI models Dec 2025.pdf` (4 pages, decoded)
- Codebase inventory of `/rolec` (40+ files reviewed across backend + frontend)

---

## 1. What Parker's document actually prescribes

Parker presents four frameworks. Treat them as four lenses on the same question — "Are we using the right tool for the job at every layer of the stack?"

**Framework 1 — Selecting a Statistical / ML Method.** A decision tree keyed on (a) number of variables, (b) statistical objective — *describe / classify / compare / predict / explain*, (c) scale of measurement (discrete vs continuous), (d) dependent vs independent variables, (e) autocorrelation by location or time. For each leaf it names the canonical method: PCA / factor analysis / MDS / correspondence for reduction; cluster / discriminant / classification trees / logistic regression for classify; ANOVA / Kruskal-Wallis / Mann-Whitney for compare; regression / SVR / CART / Random Forest / Neural Nets / GP for predict; structural / Bayesian / causal models for explain; ARIMA / VAR / kriging / variogramming for autocorrelated data.

**Framework 2 — AI for C-Suite & Startups (AutoML / Adaptive ML / DMG).** A two-step recipe — *Objectives* then *Audit*. Objectives split human work into five buckets: **perception, preferences, knowledge, motivation, communication** (plus GPU / favorite models as practical constraints). Audit is a full data lifecycle: **Exploration → Cleaning → Transformation → Missing-value handling → Data reduction (PCA/HFA/MDS/SVD) → Sample balancing (SMOTE, under/over) → Modeling (cross-sectional vs time-series, statistical vs ML) → Tools (descriptive, NLG, NLP/NLU/NLC, optimization, deliverables)**. Explicitly calls out optimization deliverables: optimal budgets, optimal stock, Markowitz MPT, Sharpe ratio, Black-Litterman, Fama-French, Kelly Criterion, stochastic knapsack, LP/IP/NLP/Geometric programming.

**Framework 3 — GenAI Flowchart.** Strategic posture ladder: *lip service* → *cheap LLM* → *"strategic partner" with vendor* → *pivot to digital transformation* → *get funding*. Then per-modality choices across **Images, Video, Audio, Coding, Translation, Text & Chat, Presentations/NLG**. For each modality: pick subscription API, open-source teacher, distilled student, or fully custom model. Also lists RLHF, RLAIF, DPO, self-play, iterative refinement, MetaRL, curriculum learning, reward modeling as fine-tuning options. Lists 15 NLG variants (template, rule, data-to-text, hybrid, grammar, decision-tree, extractive, abstractive, frame, graph, ontology, chunk-and-merge, lexicon-driven, narrative-planning).

**Framework 4 — GenAI Strategic Tradeoffs.** A 4×N matrix per modality scoring subscription / open-source / distilled / fully-custom on these dimensions: **TCO, ROI / revenue uplift, data prep, integration cost, compliance/ops, security risks (model inversion, poisoning, deepfake, membership-inference), child protection, IP & copyright, vendor lock-in, regulatory exposure, environmental impact, payback period, scalability**.

---

## 2. Where ReloPass actually sits today

### 2.1 What's working — areas of strength

These are real and would survive Parker's scrutiny:

- **Deterministic LLM router** (`backend/relopass/llm/router.py`). Rules-first task → model mapping with confidence escalation thresholds (0.80 classify, 0.85 extract). This is exactly Parker's "rules-based first" instinct on Page 2.
- **Cost & token tracking** (`ai_trace_logger.py`, `AgentRunRecord`). Token-in / token-out / cost-USD / latency per call. Optional LangSmith forwarding. Matches Parker's TCO-aware bias.
- **Evaluation harness with golden dataset** (`frontend/src/features/policy-builder/eval_pipeline.ts`). Explicit targets: ≥92% classification accuracy, ≥95% extraction precision, ≥98% conflict-detection recall. Most startups have nothing here.
- **PII masking before LLM calls** (`pii_masker.py`, `pii_log_filter.py`). Aligns with Parker's privacy-risk emphasis in Framework 4 and your GDPR posture (SEC-002 lesson learned).
- **Schema-validated LLM output** (Anthropic tool_use in `llm_policy_extractor.py`, structured JSON in `llm_client.py`). Output cannot drift into free-text where it matters.
- **Deterministic-check-on-AI-output** (ICAO 9303 MRZ checksum on passport OCR). Belt-and-suspenders, exactly the right pattern.
- **Plugin-based recommendation architecture**. The interface (`load_dataset / score / normalize / tier`) is clean enough that a heuristic plugin can later be swapped for an ML one without ripping out the engine.
- **RAG with embeddings + HashEmbedder fallback for tests**. The two-implementation pattern (real + free-deterministic-for-CI) is sophisticated.

### 2.2 Areas of weakness — what's missing or mis-built

Parker's lens makes these jump out:

**W1. There is no actual statistics in the product.** No `numpy / pandas / scipy / sklearn / statsmodels` anywhere meaningful. Everything Parker would call "describe / classify / compare / predict / explain" is implemented as weighted-sum heuristics with admin-tunable constants. You are skipping Framework 1 entirely.

**W2. No audit phase per Framework 2.** There is no codified pipeline for EDA, distribution testing (KS / Anderson-Darling / Shapiro-Wilk), outlier detection, scaling (z-score / min-max / RobustScaler), or imputation across your policy / supplier / case data. Each service module reinvents validation ad hoc.

**W3. No data reduction.** You have hundreds of policy attributes, supplier attributes, employee attributes — Parker's first instinct ("WAY TOO MANY → cluster / PCA / factor analysis / MDS") is never applied. You're likely overfitting recommendation logic to specific countries / categories because you have no compressed representation of the space.

**W4. No predictive modeling.** Case duration, employee churn, supplier conversion, HR-buyer ARR expansion — none of these have models. They are excellent supervised-ML targets given your Supabase data. The Parker tree says: continuous-y → regression / SVR / CART / Random Forest / NN; discrete-y → logistic / classification trees / discriminant analysis. You have none of these.

**W5. No survival / hazard model for case timelines.** This is the textbook tool for "how long until X event," which is literally your core deliverable to HR buyers. Parker lists "Survival hazard (Cox regression)" explicitly. Absent.

**W6. No optimization layer.** Parker enumerates "Optimal budgets, Optimal stock, Markowitz MPT, Sharpe, Black-Litterman, Fama-French, Kelly Criterion, stochastic knapsack, LP/IP/NLP/Geometric programming." Your product literally allocates HR budgets across benefit categories and across suppliers per employee — this is a constrained optimization problem you're solving with hand-tuned weights. No `pulp`, `ortools`, `cvxpy`, or `scipy.optimize` in the inventory.

**W7. No conjoint analysis or stated-preference work on benefits.** Conjoint is the standard tool for "which combination of benefits maximizes employee perceived value at a given employer cost." It would directly justify HR pricing conversations. Parker calls it out twice. Absent.

**W8. No translation in product.** Relocation is intrinsically multilingual. Parker lists DeepL, NLLB-200, OPUS-MT, mBART, MarianMT. Your `i18n` story appears to be frontend strings only — no document translation, no policy translation, no real-time chat translation.

**W9. Vendor concentration risk.** You depend on OpenAI + Anthropic with no open-source fallback. Parker's Framework 4 is explicit: subscription-only is rated "Vendor lock-in, regulatory exposure, IP leakage." There is no LLaMA / Mixtral / Qwen / DeepSeek path in router.py — if either vendor changes pricing or terms, your unit economics break overnight. No distillation strategy for high-volume tasks (passport extraction, policy classification) that would make sense to self-host.

**W10. No RLHF / DPO / human-feedback loop.** You log AI decisions but I see no pipeline that turns Human Review approvals/rejections in Notion into a preference dataset that improves the model. Parker lists RLHF, RLAIF, DPO, self-play, MetaRL — at minimum, a thumbs-up/down → preference table → DPO-style scoring is achievable.

**W11. NLG is monoculture.** You generate guidance markdown with templates, period. Parker lists 14 NLG approaches — template-based, rule-based, data-to-text, hybrid, grammar, decision-tree, extractive, abstractive, frame-based, graph-based, ontology, chunk-and-merge, lexicon-driven, narrative-planning. Different documents (policy summary, employee briefing, supplier scorecard, executive report) want different NLG strategies. You're using the cheapest one for all of them.

**W12. No prompt versioning or experiment tracking.** Prompts live in Python source. No prompt registry, no A/B test framework, no canary, no rollback. Changes to a system prompt are indistinguishable from code refactors in `git log`. Parker is explicit about "Modeling Workshop" + "Killer Ideas Workshop" iteration loops.

**W13. No deepfake / synthetic-document detection.** Your passport OCR trusts the image. Parker calls this out in Framework 4 ("deepfakes" listed under cons of subscription-API for vision). Given that schools/childcare are categories you serve, child-protection concerns Parker raises also apply to identity-verification flows.

**W14. No carbon / environmental tracking.** Parker explicitly lists "environmental impact" as a Framework 4 evaluation dimension. You track tokens and cost — converting tokens → kWh → CO₂e is a 10-line addition and an increasingly mandatory ESG disclosure for EU customers.

**W15. No cluster analysis on suppliers / companies / employees.** Recommendation tiers are absolute thresholds (85/70/50) rather than cluster-relative. A "BEST_MATCH" in Belgium might be a "GOOD_FIT" in Singapore — without clustering, the tiering is mis-calibrated by geography.

**W16. No causal / structural models.** Parker's "EXPLAIN" leaf explicitly points to Bayesian Belief Networks, structural equation modeling, and DAG-based causal inference. Your "Why was this supplier recommended?" answer is currently a weighted-sum explanation, which is correlational at best. Buyers will ask "why" in procurement reviews — a proper causal explanation is what protects the deal.

**W17. No human-objective taxonomy.** Parker's Page 2 Step-1 forces you to label each AI feature as perception / preference / knowledge / motivation / communication. ReloPass features are not catalogued this way. The result: the same model (Claude Sonnet) is used for tasks that span four of the five categories with the same prompt template, instead of specialising.

**W18. No "Killer Ideas / Co-creation / Problem-finding / Framing" workshops in the product playbook.** Parker spends real estate on creativity loops (Killer Ideas Workshop, Co-creation, Problem Finding, Framing, Ideation, Creative Thinking). You have an "AI Work Queue" in Notion but no structured ideation pipeline that lifts findings from customer interviews into hypotheses scored against a 2×2 (ease vs. impact, per Parker).

### 2.3 Gap analysis — strategic posture (Framework 3)

You are sitting at "**Sign up cheap LLM + call them strategic partner**" on Parker's posture ladder. To reach "**Pivot to digital transformation leveraging SOTA AI**" (which is what justifies a YC valuation premium and an HR-buyer ARR uplift) the missing artefacts are: (i) at least one self-hosted model for a high-volume task, (ii) a measurable feedback-loop closing customer signals into model quality, (iii) a public-facing technical narrative ("our policy classifier hits 95% precision on a 500-doc benchmark"), (iv) a quantified AI ROI claim per dollar of HR spend.

### 2.4 Gap analysis — modality coverage (Framework 4)

| Modality | Parker says | ReloPass today | Verdict |
|---|---|---|---|
| Text & Chat | Subscription + open-source fallback advised | Subscription only (OpenAI, Anthropic) | Vendor concentration risk |
| Vision (passport, diploma) | High-value for distillation given volume | Subscription only (GPT-4o vision) | Margin leak at scale |
| Translation | Critical for relocation product | Not implemented in product | Strategic gap |
| Audio | Not core to ReloPass | Not implemented | OK to skip |
| Video | Not core to ReloPass | Not implemented | OK to skip |
| Image generation | Could power policy infographics | Not implemented | Optional |
| Code generation | Internal dev only (Claude Code) | Dev-side only | OK |
| Presentations / NLG | 14 variants exist; you use 1 | Markdown templates only | Major coverage gap |
| Embeddings / semantic search | Yes; cost-aware | Implemented (text-embedding-3-small + HashEmbedder for tests) | Good |

---

## 3. Conclusion — the headline

ReloPass has built a **good engineering substrate for LLM-based features** (router, traces, evals, PII masking, schema validation, deterministic checks), but it is **not yet doing data science**. You are using Phil Parker's Page-3 GenAI toolkit at maybe 25% of capability and his Page-1 + Page-2 statistical / ML toolkit at near zero. Three concentrated bets would close most of the gap:

1. **Optimization & predictive analytics layer** (Frameworks 1 + 2). Add a real `scipy / sklearn / lifelines / cvxpy` stack and ship: (a) a Cox survival model on case duration, (b) a benefit-mix optimizer using Markowitz-style constrained allocation, (c) a clustering pass on suppliers per (country, category) that recalibrates BEST/GOOD/OK tiers. These are weeks of work, not months, against your existing Supabase data.

2. **GenAI maturity loop** (Framework 3). Stand up (a) prompt versioning + canary, (b) an RLHF-lite preference dataset fed by the Notion Human Review queue, (c) one distilled / self-hosted task (passport OCR is the obvious candidate — high volume, narrow domain, regulatory upside), (d) a translation service via NLLB-200 or DeepL Pro behind a router fallback.

3. **TCO + ESG accounting** (Framework 4). Extend `ai_trace_logger.py` to emit cost-per-feature, cost-per-customer, cost-per-decision, and carbon-per-decision rollups, with a Supabase view that surfaces unit economics per HR buyer. This is what makes the YC pitch and the Series-A pitch defensible.

The rest of the gap (NLG variety, conjoint analysis, deepfake detection, child-protection filter on the school/childcare category, causal explanations) is incremental — important, but not as leverage-bearing as the three above.

---

## 4. Claude Code prompts — engineered for your repo

Run these inside the `rolec` repo, from the project root, with Claude Code in the standard agentic mode. They are sequenced from highest-leverage to lowest. Each prompt is self-contained and references actual file paths in your codebase.

### Prompt A — Cox survival model for case timelines (highest leverage, fits Parker Framework 1 leaf "predict + time-dependent")

```text
Build a Cox proportional-hazards survival model that predicts time-to-completion for relocation cases. Use the existing Supabase data — start by reading backend/app/models.py and backend/app/services/case_milestones.py to understand the case lifecycle schema and milestone events.

Implementation:
1. Add `lifelines>=0.27` to backend/requirements.txt.
2. Create backend/app/services/case_duration_model.py with: (a) a dataset builder that joins cases + case_milestones + employee_assignments + assignment metadata into a survival frame (duration, event_observed, covariates), (b) a `fit_cox_model()` function that fits with regularization and 5-fold cross-validated concordance, (c) a `predict_remaining_duration(case_id)` function returning median + 80% CI.
3. Cache the trained model in Supabase as a pickled blob in a new `ml_models` table — write the migration following the hard RLS/REVOKE rules in CLAUDE.md.
4. Expose GET /api/cases/{case_id}/predicted-duration in a new router backend/app/routers/predictions.py, registered in backend/app/main.py per the dual-layer convention.
5. Write pytest tests using a synthetic case-event fixture; concordance target ≥0.65 on synthetic data.
6. Type-check (cd frontend && npx tsc --noEmit not required here; backend is Python) and run cd backend && pytest backend/tests/test_case_duration_model.py.

Constraints: do not touch backend/main.py monolith. Follow the SessionLocal/ORM pattern from app/db.py. Add a feature flag PREDICTIONS_ENABLED so this can be canary-rolled.
```

### Prompt B — Benefit-mix portfolio optimizer (Parker explicit deliverable "Optimal budgets / Markowitz MPT")

```text
Build a constrained optimization engine that, given an HR company's total relocation budget and a set of candidate benefits with (cost, employee_satisfaction_score, eligibility_constraints), returns the benefit mix that maximizes a Markowitz-style utility (expected satisfaction - λ × variance) subject to budget, mandatory-benefit, and per-category-cap constraints.

Read backend/app/services/hr_policy_resolver.py, backend/app/recommendations/engine.py, and backend/app/services/requirement_evaluation_service.py to understand current benefit & policy schemas.

Implementation:
1. Add cvxpy>=1.4 (or pulp>=2.7 if cvxpy is too heavy) to backend/requirements.txt.
2. Create backend/app/services/benefit_optimizer.py with: (a) a typed dataclass BenefitCandidate(id, category, cost_per_employee, expected_satisfaction, variance, hard_constraints), (b) an `optimize(budget, candidates, mandatory_ids, category_caps, lambda_risk)` function returning the optimal portfolio + dual variables for explainability.
3. Add a Supabase view `v_benefit_candidates_per_company` aggregating expected satisfaction from any existing feedback / NPS / engagement data — if none exists, fall back to admin-set priors stored in a new `benefit_priors` table (RLS-scoped to company_id).
4. Expose POST /api/hr/{company_id}/optimize-benefit-mix in a new router backend/app/routers/benefit_optimizer.py.
5. In the response, include shadow prices ("each additional €1000 of budget yields +X satisfaction") — this is the salesy artefact HR buyers want.
6. Write pytest tests with a deterministic fixture; verify the optimizer matches a hand-solved 3-benefit toy case.

Constraints: respect CLAUDE.md migration security rules (RLS + policies + REVOKE FROM anon on every new table). No new routes in backend/main.py.
```

### Prompt C — Cluster-relative supplier tiering (Parker Framework 1 leaf "WAY TOO MANY variables → cluster / PCA")

```text
Re-engineer the recommendation engine in backend/app/recommendations/engine.py so that BEST_MATCH / GOOD_FIT / OK / WEAK tiers are derived from per-cluster percentiles instead of absolute thresholds (currently 85/70/50). Today, a strong supplier in a thin market gets unfairly demoted; this is mis-calibrated tiering.

Read backend/app/recommendations/engine.py, backend/app/services/supplier_registry.py, and one example plugin (backend/app/recommendations/plugins/banks.py) before writing.

Implementation:
1. Add scikit-learn>=1.3, scipy>=1.11 to backend/requirements.txt.
2. Create backend/app/recommendations/tiering.py: (a) cluster suppliers within (service_category, country_iso2) using KMeans with silhouette-selected K∈[2,6], (b) within each cluster, compute the 4-tier mapping using empirical quantiles of the heuristic score, (c) cache cluster assignments and threshold vectors in a new `supplier_cluster_cache` table (with RLS, policies, REVOKE FROM anon — follow CLAUDE.md).
3. Modify engine.tier() to dispatch to tiering.tier_with_cluster_context(...) when at least 8 suppliers exist in the (category, country) cell; fall back to the absolute thresholds otherwise.
4. Add a Supabase cron / scheduled task to recompute clusters weekly.
5. Add observability: log per-category-per-country cluster K and silhouette score to ai_trace_logger.py.
6. Tests: verify tier reproducibility (deterministic seed), verify fallback when <8 suppliers, verify that a known top-3 supplier in a fixture cluster is tiered BEST_MATCH.

No changes to plugin scoring contracts.
```

### Prompt D — Prompt registry + A/B canary (Parker "Modeling Workshop" + Framework 3 maturity gap)

```text
Build a prompt registry so system prompts and few-shot examples are versioned, A/B-testable, and rollback-able. Today prompts live in Python source in services like backend/app/services/llm_policy_extractor.py and backend/app/services/policy_assistant_rag_engine.py; we want them externalised and traceable.

Read backend/relopass/llm/router.py, backend/app/services/ai_trace_logger.py, and backend/app/services/llm_policy_extractor.py.

Implementation:
1. Create a `prompt_versions` table with columns (id, task_key, version, system_prompt, user_template, model_name, temperature, max_tokens, status [draft|canary|prod|archived], created_at, created_by). Follow CLAUDE.md migration security rules.
2. Create backend/app/services/prompt_registry.py with: get_active_prompt(task_key, *, canary_share=None) which returns the prod prompt 90% of the time and a canary variant 10% (or whatever is set in a `prompt_routing` table).
3. Refactor llm_policy_extractor.py and policy_assistant_rag_engine.py to fetch their prompts via prompt_registry.get_active_prompt() instead of string constants.
4. Extend ai_trace_logger TraceSession to include prompt_version_id and canary_arm so traces can be aggregated by variant.
5. Build a tiny admin route GET /api/admin/prompts and POST /api/admin/prompts/{id}/promote (admin-only via is_admin allowlist check).
6. Frontend: add a minimal `/admin/prompts` page under frontend/src/features/admin showing prompt versions, their canary win rates (avg eval score from policy-builder eval_pipeline), and a promote button.
7. Tests covering: canary split is statistically ~10%, traces include the right prompt_version_id, promote moves status from canary→prod and demotes the prior prod row to archived.

Type-check frontend (cd frontend && npx tsc --noEmit) and run backend pytest before declaring done.
```

### Prompt E — RLHF-lite preference dataset from Notion Human Review (Parker "RLHF" option, Framework 3)

```text
Close the loop between Notion's Human Review queue and model quality by emitting a preference dataset suitable for DPO-style fine-tuning or for re-ranking prompt-registry canaries.

Read backend/app/services/ai_trace_logger.py and the notion-review-validator skill at /var/folders/.../anthropic-skills/notion-review-validator/SKILL.md to understand the review payload schema.

Implementation:
1. Create `ai_human_feedback` table linking (trace_session_id, reviewer_user_id, verdict [approved|rejected|edited], edited_output_json, comment, prompt_version_id). RLS + policies + REVOKE FROM anon per CLAUDE.md.
2. Add a Supabase Edge Function or backend route POST /api/ai/feedback that the notion-review-validator skill can call when Romain approves/rejects a task; idempotent on (trace_session_id, reviewer_user_id).
3. Create backend/app/services/preference_dataset_builder.py with `build_dpo_pairs(task_key, min_pairs=50)` that returns chosen/rejected pairs in the {prompt, chosen, rejected} format DPO and KTO expect.
4. Add a CLI: `python -m backend.scripts.export_preference_dataset --task policy_classification --out preferences/policy_classification_$(date +%Y%m%d).jsonl` so we can run distillation / fine-tuning experiments offline.
5. Aggregate weekly per-task win rates and surface them in the prompt registry admin page (Prompt D).
6. Tests: schema validation, idempotency of the feedback endpoint, dataset builder produces well-formed JSONL.

Do not auto-fine-tune anything yet — the goal of this prompt is the dataset and the loop, not the training run.
```

### Prompt F — Open-source fallback for passport OCR (Framework 4 vendor-lock-in + margin)

```text
Add a self-hosted open-source fallback for backend/app/services/ocr_passport_extractor.py so that high-volume passport extraction can be served without GPT-4o vision. Goal: route N% of traffic to the local model, compare extraction accuracy + MRZ-checksum-pass-rate via the existing eval harness, and decide whether to graduate to 100%.

Read backend/app/services/ocr_passport_extractor.py and backend/relopass/llm/router.py to align with the routing pattern.

Implementation:
1. Pick a model: PaddleOCR for text + a small VLM (Qwen2-VL-2B or Florence-2-base) for structured field extraction. Document the choice with a 5-line ADR in audit/adr/adr-001-self-hosted-passport-ocr.md.
2. Create backend/app/services/passport_ocr_oss.py exposing the same interface as the GPT-4o extractor.
3. Wire it into backend/relopass/llm/router.py ROUTING_TABLE under task_class="mrz_extraction" with an environment-controlled split (PASSPORT_OCR_OSS_SHARE=0.0 default).
4. Run both extractors in shadow mode for a sample (config: SHADOW_COMPARE=true) and log per-field disagreement to ai_trace_logger.
5. Add a comparison dashboard route GET /api/admin/ocr-shadow-comparison surfacing per-field agreement rate, MRZ-pass rate, and cost-per-extraction for both pipelines.
6. Tests against a small fixture set of synthetic passport images (use existing fixtures if any, otherwise generate via a passport-image-mock library).

Constraints: do NOT enable in production until the shadow comparison shows ≥99% field agreement on the existing eval set. Document the GPU / CPU requirements in the ADR.
```

### Prompt G — Carbon + per-customer unit economics on AI traces (Framework 4 environmental + TCO)

```text
Extend ai_trace_logger.py so every LLM call also records an estimated CO₂e value and a customer attribution, and produce a rollup view that surfaces cost-per-customer and carbon-per-customer per feature.

Read backend/app/services/ai_trace_logger.py and any usage sites under backend/app/services/policy_assistant_*.py.

Implementation:
1. Add a small backend/app/services/ai_carbon_estimator.py implementing the standard "tokens × J/token × kWh/J × gCO2/kWh" estimator, with a config table `ai_model_energy_profiles` (model_name, joules_per_input_token, joules_per_output_token, region_gco2_per_kwh). Seed with public OpenAI / Anthropic estimates (cite sources in code comments).
2. Extend TraceSession to include co2e_grams_estimated, customer_id (company_id where applicable), feature_key.
3. Create a Supabase materialized view mv_ai_unit_economics aggregating (week, customer_id, feature_key) → total_cost_usd, total_tokens, total_co2e_grams, n_calls; refresh nightly via Supabase cron.
4. Expose GET /api/admin/ai-unit-economics?customer_id=...&from=...&to=... returning per-feature rollups; admin-only.
5. Frontend: add a small panel to the existing AIPanel.tsx or to an admin page summarising "AI spend per customer this month" + "AI CO₂e per customer this month".
6. Tests on the estimator (deterministic) + view freshness.

Follow CLAUDE.md migration security rules (RLS + policies + REVOKE FROM anon on every new table).
```

### Prompt H — Conjoint analysis on benefit preferences (Parker explicit deliverable)

```text
Build a conjoint-analysis micro-service that, given a small set of stated-preference responses (employees ranking benefit bundles), estimates per-attribute part-worths and runs market-share simulations for proposed bundles.

Read backend/app/services/employee_recommendations_filter.py and backend/app/services/hr_policy_resolver.py to understand benefit attributes.

Implementation:
1. Add statsmodels>=0.14 to backend/requirements.txt.
2. Create backend/app/services/conjoint_service.py with: (a) `fit_conjoint(responses)` using multinomial logit, (b) `simulate_market_share(bundles, part_worths)`, (c) `recommend_bundle(budget, attribute_costs, part_worths)`.
3. Create a `conjoint_studies` and `conjoint_responses` schema (RLS + REVOKE per CLAUDE.md) so an HR company can launch a study against their employee base.
4. Build a minimal employee-facing flow (frontend) that presents 8–12 forced-choice questions ("Bundle A vs Bundle B?").
5. Surface the part-worth chart + recommended bundle in the HR command center.
6. Tests with the standard Sawtooth-style synthetic conjoint dataset.

This is a high-value PR — conjoint analysis is the strongest commercial artefact for an HR-tech pitch because it lets the buyer say "our employees prefer X over Y by Z%".
```

### Prompt I — Add neural translation layer (Framework 4 coverage gap)

```text
Add a neural translation service so policy summaries, supplier briefings, and case communications can be served in the employee's preferred language. Route between DeepL Pro (subscription) for low volume / high quality and NLLB-200 (self-hosted) for high volume / cost-sensitive.

Implementation:
1. Create backend/app/services/translation_service.py exposing translate(text, src, tgt, domain, quality_tier) with a router under backend/relopass/llm/router.py (new task_class="translation").
2. Vendor adapter for DeepL Pro (subscription); open-source adapter for NLLB-200 served via Hugging Face Inference Endpoints or local GPU.
3. Cache translations keyed by hash(text, src, tgt, model_version) in a `translation_cache` table (RLS + REVOKE per CLAUDE.md).
4. Add a "Preferred language" field to employee_assignments and surface translated content in the employee journey wizard at /journey.
5. Tests: round-trip translation EN→DE→EN preserves entity names; cost-router selects DeepL when text < 500 chars, NLLB when > 5000 chars.

Document carbon + cost characteristics in an ADR.
```

### Prompt J — NLG variety: add 3 of Parker's 14 NLG approaches (Framework 3 NLG monoculture gap)

```text
Diversify NLG. Today we produce markdown templates only; Parker enumerates 14 NLG approaches. Add three high-leverage ones: (1) data-to-text for executive HR dashboards, (2) frame-based NLG for incident / case reports, (3) extractive summarisation for long policy documents.

Read backend/app/services/guidance_markdown.py and backend/app/services/policy_session_pdf.py.

Implementation:
1. Create backend/app/services/nlg/data_to_text.py: takes a structured dict (KPIs, deltas, anomalies) and produces a 3–5 sentence executive summary using deterministic templates + sentence ordering by salience.
2. Create backend/app/services/nlg/frame_based.py: define a Frame(event_type, slots) schema for incident reports (e.g., "passport_expiry_at_risk") and render to text using slot-filled templates.
3. Create backend/app/services/nlg/extractive_summarizer.py: a TextRank-style extractive summariser over policy chunks (no LLM call — pure NLP), useful for "TL;DR" of a 40-page policy doc.
4. Hook (1) into the HR command center exec summary, (2) into the case alerts feed, (3) into the policy viewer.
5. Tests with deterministic fixtures + at least one snapshot test per NLG type.

Constraint: extractive_summarizer.py must run without an LLM call — Parker's whole point is that classical NLG is cheaper, auditable, and often sufficient.
```

---

## 5. Suggested sequencing

| Sprint | Prompt | Justification |
|---|---|---|
| Sprint 1 (high leverage, low integration risk) | A (Cox survival) + G (carbon/TCO) | Both surface metrics customers immediately ask about; no impact on existing user flows. |
| Sprint 2 (commercial artefacts) | B (benefit optimizer) + H (conjoint) | These are what your HR-buyer pitch most needs; they unlock "AI-priced benefits" narrative. |
| Sprint 3 (platform maturity) | D (prompt registry) + E (RLHF-lite) | Without these you can't safely iterate on the LLM features above. |
| Sprint 4 (margin & coverage) | C (cluster tiering) + F (OSS fallback) + I (translation) | Margin work + coverage gap; lowest user-visible risk. |
| Sprint 5 (NLG diversity) | J (NLG variety) | Quality-of-life across all written outputs. |

---

*End of audit. Sources: Phil Parker AI models Dec 2025.pdf, decoded; codebase inventory of /rolec compiled 2026-05-30.*
