# ReloPass — Techniques & Technologies to Enhance the Immigration, HR Policy RAG, and Supplier Selection Modules

Source list: [benchflow-ai/awesome-evals](https://github.com/benchflow-ai/awesome-evals) (curated, URL-verified Jun 2026), cross-referenced against the current ReloPass codebase.

**How to read the tables.** Each row is a technique or tool you could adopt. The *Reference* column links the canonical source and notes why it's trustworthy (who built it, stars, "MUST" = the list's own must-read tag). *Value for ReloPass* frames the opportunity against what your code does today. *Complexity* is the build effort to get a first useful version into your stack (Low = days, Medium = 1–2 weeks, High = multi-week / needs labeled data or infra).

**Where you are today (from the codebase):**
- *Immigration* — deterministic regime router (`immigration_regime.py`) + an emerging RAG roadmap pipeline (`immigration_retriever.py` → `roadmap_generator.py` → `factual_verifier.py`) over pgvector. No confidence scoring, hardcoded interview, substring-match document checks.
- *HR Policy RAG* — pgvector retrieval with quality gates (`policy_chunk_retriever.py`) but **template-based answers, no LLM synthesis yet**. Eval dashboard exists (`admin_rag_eval.py`) but runs on mock reports.
- *Supplier selection* — deterministic per-category scoring plugins (`recommendations/plugins/*`) with hardcoded weights + offline cluster tiering. No learning from user choices, no judge, no A/B harness.
- *Shared* — Anthropic + OpenAI clients, pgvector, `pii_masker.py`, Langfuse tracing already wired (`ai_trace_logger.py`), thin eval tests in `backend/tests/eval/`.

---

## Module 1 — Immigration (multi-turn eligibility + roadmap generation)

This is effectively an *agentic, compliance-critical workflow* with a verifiable ground truth (a corridor either requires a given permit or it doesn't). That makes it the best candidate for outcome-grading and deterministic scoring.

| Technique / Technology | Reference (and why it's credible) | Value for ReloPass | Complexity |
|---|---|---|---|
| **Outcome / final-state grading** (grade the final eligibility decision + roadmap, not the steps) | [Anthropic — Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) (list MUST-read) | Catch wrong `regime_id` detection directly; gives you a single pass/fail you can trust over the whole pipeline | Low |
| **Golden dataset + deterministic verifier** (four-primitive template: fixtures, difficulty inputs, tools, deterministic grader) | [Eugene Yan — Patterns for Building Evals](https://eugeneyan.com/writing/cybersecurity-evals/) (widely-cited practitioner) | 30–50 labeled real corridors becomes a regression suite that fails CI when regime routing breaks | Medium |
| **Inspect AI harness** (`@task` binds dataset + solver + scorer, sandboxed tools) | [UKGovernmentBEIS/inspect_ai](https://github.com/UKGovernmentBEIS/inspect_ai) (UK AISI; the reference agent-eval framework, MUST) | One framework to run immigration cases through scorers in CI; replaces the ad-hoc `tests/eval/` scripts | Medium |
| **User-simulation + state-diff grading** (simulate applicants, grade the DB/world state after the interview) | [τ-bench / τ²-bench](https://github.com/sierra-research/tau-bench) (Sierra; list MUST-read) | Stress-test the hardcoded interview engine across thousands of synthetic applicant profiles before real users hit edge cases | High |
| **Claim-level RAG diagnosis** (separate retriever vs generator errors for the roadmap) | [RAGChecker](https://github.com/amazon-science/RAGChecker) (Amazon Science) | Tells you whether a bad roadmap step came from bad retrieval or bad generation — your `factual_verifier.py` only flags, doesn't localize | Medium |
| **Policy-constraint grading** (Completion-under-Policy: did the agent obey hard rules / never suggest a non-compliant pathway) | [ST-WebAgentBench](https://arxiv.org/abs/2410.06703) (IBM Research) | Immigration advice is legally sensitive — measure rule-adherence, not just task success | Medium |
| **pass@k / pass^k reliability** (is regime detection stable across reruns) | [Han-Chung Lee — pass@k explained](https://leehanchung.github.io/blogs/2025/09/08/pass-at-k/) | Quantify non-determinism risk in the LLM roadmap step before you trust it in prod | Low |
| **Prompt-injection / document red-teaming** (uploads are attacker-controlled) | [Giskard](https://github.com/Giskard-AI/giskard-oss) · [promptfoo red-team](https://github.com/promptfoo/promptfoo) (MUST) | Passport/contract uploads flow into prompts — auto-generate adversarial docs to test extraction safety | Medium |

---

## Module 2 — HR Policy RAG (retrieval + answer synthesis)

Your retrieval layer is solid; the gap is (a) you template answers instead of synthesizing, and (b) the eval dashboard runs on mock data. Adopt RAG-specific scorers *before* you turn on LLM synthesis, so you can prove the synthesized answers are grounded.

| Technique / Technology | Reference (and why it's credible) | Value for ReloPass | Complexity |
|---|---|---|---|
| **RAG triad** (context relevance · groundedness · answer relevance) | [TruLens](https://github.com/truera/trulens) (the canonical RAG-triad instrumentation, now OTel) | The three metrics that should gate every synthesized policy answer; turns your mock dashboard into real numbers | Medium |
| **Claim-level RAG checker** (retriever vs generator error split) | [RAGChecker](https://github.com/amazon-science/RAGChecker) (Amazon Science) | Pinpoints whether to fix chunking/retrieval or the prompt when an answer is wrong | Medium |
| **Synthetic-query benchmark + confidence intervals** (build a labeled set cheaply) | [ARES](https://github.com/stanford-futuredata/ARES) (Stanford) | Generate a HR-policy QA benchmark without hand-labeling 100s of questions; get CIs not point estimates | High |
| **Hallucination / groundedness judge** (gate answers that aren't supported by retrieved policy) | [Patronus Lynx](https://github.com/patronus-ai/Lynx-hallucination-detection) · [G-Eval via DeepEval](https://github.com/confident-ai/deepeval) (DeepEval = "pytest for LLMs", ~2M evals/day) | Hard requirement before synthesis ships — a wrong housing-cap answer is a compliance liability | Medium |
| **Cross-encoder reranking** (second-pass rerank of top-k chunks) — *enhancement, measured by the scorers above* | [continuous-eval (Relari)](https://github.com/relari-ai/continuous-eval) (per-module retrieval metrics) | Your retriever returns top-k as-is; reranking lifts precision before the answer is built | Medium |
| **Prompt regression + git-diffable eval configs** (every prompt change runs the eval suite in CI) | [promptfoo](https://github.com/promptfoo/promptfoo) (MIT, MUST) | Stops a prompt tweak from silently regressing groundedness; fits your PR/CI discipline | Low |
| **LLM-judge alignment loop** (validate the judge against ONE expert before trusting it) | [Hamel Husain — LLM-as-a-Judge](https://hamel.dev/blog/posts/llm-judge/) · [EvalGen](https://arxiv.org/abs/2404.12272) (UIST'24) | Without this your judge scores are noise; this is the discipline that makes the dashboard meaningful | Low |
| **Online eval + feedback flywheel** (capture HR/employee "helpful?" votes → datasets) | [Langfuse](https://github.com/langfuse/langfuse) (already in your stack via `ai_trace_logger.py`) · [Arize Phoenix](https://github.com/Arize-ai/phoenix) (MUST) | You already trace calls — add scored feedback to build the retraining/corpus-improvement loop you lack | Medium |

---

## Module 3 — Supplier / Service-Provider Selection (ranking & recommendation)

This is a ranking problem, not RAG. The opportunity is to (a) judge ranking quality, (b) learn weights from real choices instead of hardcoding them, and (c) get an A/B harness so scoring changes are measured, not guessed.

| Technique / Technology | Reference (and why it's credible) | Value for ReloPass | Complexity |
|---|---|---|---|
| **Offline↔online eval harness** (score ranking changes against golden datasets + production logs) | [Braintrust Eval SDK](https://www.braintrust.dev/docs/start/eval-sdk) (MUST; used by Notion/Stripe/Vercel) | Turn hardcoded-weight tweaks into measured experiments instead of blind edits to `plugins/*` | Medium |
| **LLM-as-judge for ranking quality** (pairwise: is supplier A a better fit than B for this case) | [Prometheus 2](https://github.com/prometheus-eval/prometheus-eval) (open evaluator LMs, rubric + pairwise) | A judge that scores your ranked list against criteria — catches cases where the formula ranks oddly | Medium |
| **Compound / verifiable judges** (debate + verification + aggregation for trade-off calls) | [verdict](https://github.com/haizelabs/verdict) (Haize Labs, arXiv:2502.18018) | Supplier choice is multi-factor (cost vs digital vs expat support) — compound judges evaluate trade-offs better than one score | Medium |
| **Label-free trajectory ranking** (rank recommendation runs with no ground-truth labels) | [RULER (OpenPipe ART)](https://github.com/OpenPipe/ART) (list "industry must-read") | You have no labeled "best supplier" data — RULER ranks outputs without labels, a path to weights without a labeling project | High |
| **Preference learning from user choices** (turn accept/reject history into learned weights) | [RewardBench](https://github.com/allenai/reward-bench) (AI2) · [reward-kit](https://github.com/fw-ai-external/reward-kit) (Fireworks) | Replaces hardcoded `language 0.2 / fees 0.15 …` with weights learned per segment — your biggest personalization lever | High |
| **Business-scenario agent eval** (closest published analog to B2B selection tasks) | [CRMArena-Pro](https://arxiv.org/abs/2505.18878) (Salesforce Research) | A template for evaluating recommendation reliability across many case scenarios (single vs multi-turn gap) | Medium |
| **Data flywheel discipline** (binary metrics + error analysis on real choices) | [Shreya Shankar — Data Flywheels](https://www.sh-reya.com/blog/ai-engineering-flywheel/) | Your `supplier_cluster_cache` is offline/stale — a flywheel turns live acceptance data into continuous tier refresh | Medium |

---

## Cross-cutting foundations (do these first — they pay off in all three modules)

| Technique / Technology | Reference | Value for ReloPass | Complexity |
|---|---|---|---|
| **Error analysis before metrics** (review ≥100 traces, prefer binary over Likert, build a first-failure transition matrix) | [Hamel & Shankar — LLM Evals FAQ](https://hamel.dev/blog/posts/evals-faq/) · [Eugene Yan — LLM-evaluators](https://eugeneyan.com/writing/llm-evaluators/) (MUST) | The cheapest, highest-leverage step — tells you *which* of the techniques above to actually build | Low |
| **One harness across modules** (code-first, CI-runnable) | [Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai) + [promptfoo](https://github.com/promptfoo/promptfoo) (both MUST) | Standardize how all three modules are scored; wire into your existing PR/CI gates | Medium |
| **Observability + scored feedback** (you're already on Langfuse) | [Langfuse](https://github.com/langfuse/langfuse) · [Arize Phoenix](https://github.com/Arize-ai/phoenix) (MUST) | Extend `ai_trace_logger.py` from tracing-only to online scoring + datasets — the backbone of every flywheel above | Medium |
| **Production-grade judge building** (20–30 calibration examples, SME agreement gating) | [Databricks — Pilot to Production Custom Judges](https://www.databricks.com/blog/pilot-production-custom-judges) | Makes any LLM-judge you deploy defensible (agreement-gated), important given the compliance stakes | Medium |
| **PII / safety signals in production** (you already mask pre-prompt) | [WhyLabs LangKit](https://github.com/whylabs/langkit) (toxicity/PII/jailbreak signals) | Complements `pii_masker.py` with monitoring of what actually leaves the platform — GDPR Art. 28/44 evidence | Medium |
| **Guard against benchmark self-deception** (contamination, label errors, Goodhart) | [The LLM Evaluation Guidebook (HF)](https://github.com/huggingface/evaluation-guidebook) · [AI Agents That Matter](https://arxiv.org/abs/2407.01502) (MUST) | Keeps your golden sets honest as you reuse them — avoids "passing the eval, failing the user" | Low |

---

## Suggested sequencing

1. **Error analysis (Low)** on real traces from all three modules — decide where quality actually hurts before building anything.
2. **Immigration golden set + outcome grading (Low→Medium)** — you have ground truth here, so it's the fastest path to a trustworthy metric.
3. **RAG triad + hallucination judge (Medium)** — gate this *before* turning on LLM answer synthesis in HR Policy RAG.
4. **Braintrust/promptfoo harness wired into CI (Medium)** — so every prompt/weight change is measured.
5. **Preference learning for suppliers (High)** — once the flywheel is capturing accept/reject data, replace hardcoded weights.

**One caution from the list itself:** off-the-shelf evals rarely transfer, and accuracy alone is too coarse ([Eugene Yan](https://eugeneyan.com/writing/evals/)). Treat every tool above as a starting harness you calibrate against your own expert-labeled ReloPass cases — the labeling discipline matters more than the tool choice.
