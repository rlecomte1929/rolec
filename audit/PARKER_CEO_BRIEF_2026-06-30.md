# ReloPass × Phil Parker — CEO Opportunity Brief
**Date:** 2026-06-30 · **Branch:** `fix/aiq-1259b-consolidate-plan-roadmap` · **Advisor:** Senior strategic AI review
**Sources (strict grounding):** `audit/parker-framework-audit.md` (2026-05-30) · `audit/FULL_EVAL_2026-06-30.md` · live codebase (files read, not edited).

> **Headline that reframes everything below.** The Parker audit (2026-05-30) concluded ReloPass was "**not yet doing data science**" — Framework 1/2 at "near zero," GenAI toolkit at "~25%." That snapshot is now **out of date**: **all ten of the audit's remediation prompts (A–J in §4) have since shipped to the backend** — verified on disk, dual-registered in both `backend/main.py` and `backend/app/main.py`, each with a migration and tests. The strategic problem has **inverted**: ReloPass no longer has a *build* gap, it has a **surfacing** gap. None of the new ML/AI capabilities are consumed by the frontend (`grep` for `predicted-duration | benefit-mix | conjoint | ai-unit-economics` across `frontend/src` → **0 hits**), and several are flag-gated dark by default (`PREDICTIONS_ENABLED=false` at `predictions.py:29`; `PASSPORT_OCR_OSS_SHARE=0.0` at `router.py`). The data-science substrate is paid for and untapped.

---

## §1 — PARKER FRAMEWORK SCORECARD

Score: 0 (absent) → 3 (exceeds spec). Each line cites a file:symbol I actually read, or "absent — not found in codebase."

| # | Framework | Score | One-line evidence |
|---|-----------|:----:|-------------------|
| **1** | Statistical / ML method selection (describe·classify·compare·predict·explain) | **2** | Built+tested but unsurfaced: `case_duration_model.py` → `lifelines.CoxPHFitter` (predict+survival, closes W4/W5), `recommendations/tiering.py` → `KMeans`+`StandardScaler`+silhouette (classify/reduce, closes W3/W15), `conjoint_service.py:fit_conjoint` multinomial logit (explain/preference, closes W7). Gap holding it off 3: no causal/Bayesian structural model (W16 still absent), all of the above flag-gated / no UI. |
| **2** | C-Suite AutoML / Adaptive ML / DMG audit pipeline | **1** | Optimization deliverable present — `benefit_optimizer.py` (PuLP, Markowitz-style utility + shadow prices, closes W6). But Parker's *Audit lifecycle* (EDA → distribution testing → imputation → SMOTE/balancing as a codified DMG pipeline) is **absent** — `grep smote|imputer|shapiro|RobustScaler` across `backend/app` → none; only an ad-hoc `StandardScaler` in `tiering.py:116`. Human-objective taxonomy (perception/preference/knowledge/motivation/communication) absent (W17). |
| **3** | GenAI posture ladder + modality coverage | **2** | Posture primitives now real: `prompt_registry.py` + canary A/B (D), `preference_dataset_builder.py` RLHF-lite loop (E). Modality gaps filled: `translation_nllb.py` self-hosted NLLB-200 + `translation_deepl.py` (I, closes W8), `passport_ocr_oss.py` PaddleOCR/Florence-2 shadow path (F), `nlg/{data_to_text,frame_based,extractive_summarizer}.py` (J, 3-of-14, eases W11). Gap holding it off 3: core text/chat still **subscription-only** — no LLaMA/Mixtral/Qwen row in `relopass/llm/router.py` (W9 core stands); registry wired to only **3** call sites; RAG-quality dashboard serves `_MOCK_VALUES` (FULL_EVAL #13). |
| **4** | GenAI strategic tradeoffs (TCO · ROI · security · ESG) | **2** | TCO/ROI: `ai_trace_logger.py` per-call tokens+`cost_usd_estimated` → `mv_ai_unit_economics` (customer_id+feature_key) + `admin_ai_unit_economics.py` router. ESG: `ai_carbon_estimator.py` → `co2e_grams_estimated` on every trace (closes W14). Security: `pii_masker.mask_pii`, schema-validated tool_use, MRZ checksum; OSS-passport shadow cuts vendor lock-in. Gap holding it off 3: **no deepfake / synthetic-document detection** (`grep deepfake|liveness|tamper` → absent, W13), no child-protection filter on school/childcare, and the ROI rollup has **no frontend** (FULL_EVAL #14). |

**Aggregate: 2 · 1 · 2 · 2.** From the audit's effective `0·0·1·1` snapshot, every framework moved up — but each is capped at 2 by the *same root cause*: the work is built and not turned on.

---

## §2 — TOP 5 GAPS (ranked by demo impact × sprint size)

| # | Gap | Parker ref (§2.2) | File evidence | Demo impact | Sprint | Priority |
|---|-----|-------------------|---------------|:----------:|:------:|:--------:|
| 1 | **Admin Overview ships 4 literal "no data" placeholder strings + emoji icons** — reads as "unfinished product" on the screen an Admin buyer stares at | n/a — Parker frameworks don't cover UI; FULL_EVAL Phase 1 ITEM 4 | `AdminOverviewPage.tsx:234,244,254,264,274` ("No aggregate endpoint connected" / "Open the CMS for live counts") | **H** | **S** | **P0** |
| 2 | **TCO/ESG + RAG-quality dashboards exist in backend but show mock / have no UI** — the single most differentiating "trust & auditability" artefact, invisible | W14 (built via Prompt G, unsurfaced) | `admin_ai_unit_economics.py` (router exists) + **0 `frontend/src` consumers**; `AdminRagQualityPage` serves `_MOCK_VALUES` (FULL_EVAL #13) | **H** | **S** | **P0** |
| 3 | **Commercial ML artefacts built but dark** — Cox survival, benefit optimizer, conjoint are exactly what Parker said HR buyers ask for, all flag-off / un-surfaced | W4·W5 (A), W6 (B), W7 (H) | `predictions.py:29` `PREDICTIONS_ENABLED=false`; `benefit_optimizer.py` + `conjoint_service.py` routers live, **0 frontend consumers** | **H** | **M** | **P1** |
| 4 | **Prompt registry + trace instrumentation only on 3 of N LLM call sites** — periphery (briefing, entity-resolution, contradiction) is hardcoded & untraced | W12 (built via Prompt D, partial adoption) | `get_active_prompt` consumed only by `policy_assistant_rag_engine.py`, `llm_policy_extractor.py`, `immigration_answer_engine.py` (FULL_EVAL #6/#15) | **M** | **M** | **P1** |
| 5 | **No inline grounding/human gate on employee-facing generative output** — an AI can tell an employee the wrong visa rule before any check | W10-adjacent (RLHF loop E built; no inline gate); FULL_EVAL #16/#3 | `factual_verifier.py` exists but is **not** called inline on Policy-Assistant answers / AI roadmap steps | **M** | **M** | **P1** |

Note: the still-purely-absent Parker weaknesses (W13 deepfake, W16 causal models, W17 objective taxonomy, W2 DMG data-audit lifecycle) are real but rank below these — all are low demo-impact and/or large sprints, so they do not make the top 5.

---

## §3 — THE 3 BETS FOR THE NEXT 90 DAYS

Drawn **only** from the §5 sequencing table (Sprint 1 = A+G, Sprint 2 = B+H). Because the code already shipped, each "bet" is now *activate + surface*, not *build* — which is what makes them one-sprint wins.

### Bet 1 — Ship the AI unit-economics + carbon dashboard (Prompt **G**, §5 Sprint 1)
- **What:** Put a founder/buyer-facing admin page over the already-built cost+CO₂e rollup so spend-per-customer and carbon-per-decision are visible, not SQL-only.
- **Closes:** **W14** (Framework 4 — TCO/ESG accounting).
- **Why it wins a 30-min HR demo:** Compliance-minded Global Mobility buyers buy auditability; "here's exactly what our AI costs you and its carbon footprint, per employee" is a differentiator no GPT-wrapper competitor can show.
- **MVV (Prompt G):** read-only `AdminAiUnitEconomicsPage` over the existing endpoint; no new backend.
- **De-risked by:** `ai_trace_logger.py` (co2e on every trace), `ai_carbon_estimator.py`, `mv_ai_unit_economics`, and `admin_ai_unit_economics.py` router **already exist** — only the React page is missing.

### Bet 2 — Turn on predicted case-duration and surface it in the HR case view (Prompt **A**, §5 Sprint 1)
- **What:** Flip `PREDICTIONS_ENABLED`, schedule the model fit, and render "median time-to-completion + 80% CI" on the HR case page.
- **Closes:** **W4 + W5** (Framework 1 — predictive + survival/hazard modeling).
- **Why it wins a 30-min HR demo:** "How long until my employee is settled?" is literally the HR buyer's core question; a calibrated Cox estimate is the answer Parker said you were missing — now you have it.
- **MVV (Prompt A):** flip the flag, expose `GET /api/cases/{id}/predicted-duration`, one HR-page widget.
- **De-risked by:** `case_duration_model.py` (`CoxPHFitter`, concordance guard), `predictions.py` router, `ml_models` migration, and `test_case_duration_model.py` **already exist and pass** — gated off, not unbuilt.

### Bet 3 — Surface the benefit-mix optimizer (Markowitz) in the HR command center (Prompt **B**, §5 Sprint 2 commercial artefacts)
- **What:** Render the optimizer's chosen benefit portfolio + budget shadow prices ("each +€1000 buys +X satisfaction") in the HR UI.
- **Closes:** **W6** (Framework 2 — optimization layer / optimal budgets / Markowitz MPT).
- **Why it wins a 30-min HR demo:** It moves the pitch from "we manage relocations" to "we *price your relocation benefits optimally*" — the single most commercial artefact for an HR-tech buyer.
- **MVV (Prompt B):** call the existing `POST /api/hr/{company_id}/optimize-benefit-mix`, show the portfolio + shadow prices.
- **De-risked by:** `benefit_optimizer.py` (PuLP, shadow-price output), its router, and the benefit-priors migration **already exist** — only the HR-side rendering is missing. (Conjoint, Prompt H, is the natural fast-follow on the same screen — `conjoint_service.py:fit_conjoint` is already built.)

---

## §4 — STRATEGIC POSTURE ASSESSMENT (Framework 3 ladder)

The 2026-05-30 audit placed ReloPass at "**Sign up cheap LLM + call them strategic partner**" and named the four artefacts required to climb to "**Pivot to digital transformation leveraging SOTA AI**": (i) a self-hosted model on a high-volume task, (ii) a measurable customer-signal → model-quality feedback loop, (iii) a public technical-quality narrative, (iv) a quantified AI-ROI-per-HR-dollar claim. **Three of the four now exist in code:** (i) self-hosted is shipped twice — `translation_nllb.py` (NLLB-200-distilled) and `passport_ocr_oss.py` (PaddleOCR + Florence-2 shadow path); (ii) the feedback loop is `preference_dataset_builder.py` + the `ai_human_feedback` table fed by Human Review; (iv) the ROI data exists as `mv_ai_unit_economics` (cost + CO₂e per customer per feature). ReloPass is therefore standing **on the threshold of the "digital transformation" rung but has not stepped onto it**, because artefact (iii) — the public, buyer-facing quality narrative — is the one thing still missing: `/admin/rag-quality` self-labels "Showing mock data" (FULL_EVAL #13) and the unit-economics rollup has no frontend (#14). **The single artefact that moves ReloPass up one rung is a live, buyer-facing dashboard that turns the already-computed eval scores + unit economics + citation trail into an on-screen claim** ("94% factual consistency, $0.04/answer, full citation trail") — i.e. kill the mock-data banner and ship Bet 1.

---

## §5 — THE ONE THING

**Stop building and start surfacing: flip the feature flags and ship the founder/buyer-facing dashboards over work that already exists — live AI unit-economics/carbon (Bet 1), predicted case duration (Bet 2), and the benefit-mix optimizer (Bet 3) — while deleting the four placeholder strings in `AdminOverviewPage.tsx`, because ReloPass has already paid to build Parker's entire data-science toolkit (prompts A–J) and is losing every demo that never gets to see it.**

---

*Grounded strictly in `audit/parker-framework-audit.md`, `audit/FULL_EVAL_2026-06-30.md`, and files read in the live codebase on 2026-06-30. No code changed. Where a capability was claimed absent by the May-30 audit but found shipped on disk, the file is cited; where genuinely absent, marked "absent — not found in codebase."*
