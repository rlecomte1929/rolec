# SEC-03 / AIQ-1166 — Backend LLM Call-Site PII Masking Coverage

**GDPR Art. 28/44 — data minimisation for LLM sub-processors (OpenAI + Anthropic, US-based).**
Hard rule (root `CLAUDE.md` § "Data minimisation"): any text that may contain user
PII MUST pass through `backend/app/services/pii_masker.py::mask_pii()` before it is
placed in a prompt / embedding payload sent to OpenAI or Anthropic. Published policy
document text, purely structured/enum inputs, and document-image OCR (which cannot be
masked pre-OCR) are exempt.

This document is the coverage matrix for every backend call site that reaches an LLM
or embeddings provider, produced for SEC-03. Date: 2026-06-26.

## Masking architecture (the key dependency)

Two shared clients sit under most call sites and behave differently:

- **`policy_assistant_llm_client.AnthropicClient.complete()`** masks `req.user_message`
  via `mask_pii()` (lines 110–111) before egress (sent at line 127). The `system`
  prompt is intentionally **not** masked (it is template text we control). Therefore
  **every caller routed through this client is masked transitively** even if it does
  not call `mask_pii` itself. This is the canonical chokepoint.
- **`llm_client.py`** (`complete` / `complete_text` / `claude_complete*`, OpenAI +
  Anthropic) does **NOT** mask — its docstring (lines 23–25) makes masking the
  caller's responsibility.
- **OpenAI embeddings** (`policy_assistant_embedder.OpenAIEmbedder.embed_batch`) is a
  separate egress that the chat-path masking does **not** cover.

## Coverage matrix

| # | Call site (file:line) | Reaches LLM? | User PII in payload? | Masked? | Logged safely? | Verdict / Action |
|---|---|---|---|---|---|---|
| 1 | `policy_assistant_llm_client.py:127` (`AnthropicClient.complete`) | Yes (Anthropic) | Yes (user_message) | **Yes** — `mask_pii` L111 | n/a | **MASKED** (canonical chokepoint). Now regression-tested. |
| 2 | `immigration_answer_engine.py:281` | Yes (Anthropic) | Yes — `QUESTION: {query}` free-text (origin `immigration_retrieve.py:120` → `body.query`) | **Yes** — transitively via #1 | trace stores query_hash, not raw | **MASKED** (transitive). No code change. |
| 3 | `immigration_answer_verifier.py:124` | Yes (Anthropic) | Low — generated answer + corpus chunks | Yes — transitively via #1 | yes | **MASKED / N-A**. |
| 4 | `immigration_contradiction_detector.py:87` | Yes (Anthropic) | No — compares two published corpus chunks | n/a (corpus) | yes | **N-A** (published corpus only). |
| 5 | `policy_assistant_rag_engine.py:389/414` | Yes (Anthropic) | Yes — `USER QUESTION` + prior turns | **Yes** — transitively via #1 | raw question to DB audit only (not LLM) | **MASKED** (the CLAUDE.md reference path). |
| 6 | `policy_chunk_retriever.py:156` → `embedder.embed(query)` (OpenAI embeddings) | Yes (OpenAI) | Yes — raw user query (callers: rag_engine + policy_query_answering) | **Yes — FIXED** (`mask_pii(query)` added) | n/a | **FIXED** — was UNMASKED; single chokepoint now masks every retrieval caller. |
| 7 | `policy_query_answering.py:209` (`complete_text_sync`, OpenAI) | Yes (OpenAI) | Yes — user query | **Yes — FIXED** (`redact_pii_from_query` now delegates to `mask_pii`) | redacted query + hash in audit | **FIXED** — bespoke regex missed IBAN/passport/SSN; now uses canonical masker. |
| 8 | `briefing.py:110` (direct `anthropic` SDK) | Yes (Anthropic) | Yes — employee **name** + free-text dependants | **Yes — FIXED** (name → `[REDACTED_PERSON]`; dependants → `mask_pii`) | no raw logging | **FIXED** — was a live unmasked-PII egress (self-flagged in code). |
| 9 | `policy_assistant_embedder.py:139` (`embeddings.create`) | Yes (OpenAI) | Indexing = published policy text; query = via #6 | indexing exempt; query masked at #6 | does not log text | **N-A** (egress masked upstream at #6). |
| 10 | `dossier_suggestion_service.py:203` | Yes (Anthropic) | No — structured corridor + published corpus + generic retrieval query | Yes — transitively via #1 | logs corridor only | **MASKED / N-A**. |
| 11 | `factual_verifier.py:177` | Yes (Anthropic) | No — generated roadmap step + published chunks | Yes — transitively via #1 | logs step title only | **MASKED / N-A**. |
| 12 | `roadmap_generator.py:136` | Yes (Anthropic, via #1) | No — structured profile (country/ISO/enum) + published RAG chunks; no names/contacts | Yes — transitively via #1 | logs via `safe_log_text` | **N-A** (structured + corpus). |
| 13 | `rce_entity_resolution_ai.py:149` (OpenAI) | Yes (OpenAI) | Yes — identity text | **Yes** — `mask_pii` at L80/116/117/130/131 | n/a | **MASKED** (already compliant). |
| 14 | `crawler/extractors/llm_resource_extractor.py:104` | Yes | Published scraped page text | `mask_pii` applied (defense) L104 | yes | **MASKED / N-A** (published page text). |
| 15 | `llm_policy_extractor.py:300` (direct Anthropic SDK) | Yes (Anthropic) | Policy **document** text (exempt) | No masking layer (direct SDK) | LangSmith metadata only; raw text never sent to tracer | **N-A (exempt) — FLAG**: if an uploaded "policy" doc embeds an individual's PII it would egress unmasked. Human review. |
| 16 | `policy_canonical_extraction.py:117` (`complete_text_sync`, OpenAI) | Yes (OpenAI) | Policy **document** chunk text (exempt) | No masking layer | no raw logging | **N-A (exempt) — FLAG**: same residual risk as #15. Human review. |
| 17 | `ocr_passport_extractor.py:337` (OpenAI vision) | Yes (OpenAI) | PII enters as passport **image**, prompt text is static | Cannot mask an image pre-OCR | no raw-text logging | **N-A** (document-image OCR — exempt). |
| 18 | `mistral_ocr_client.py:57` (Mistral Document AI) | OCR (not a prompt) | Document **bytes** | Cannot mask pre-OCR | never logs returned text (PHI) | **N-A** (document OCR — exempt; Mistral is a separate sub-processor, tracked in PRIV-004). |
| 19 | `relopass/agents/extraction/passport_td3.py:351/362` | Yes (via `route_llm`) | OCR'd passport body + MRFields | No masking | logs routing exc only | **N-A (extraction-by-design) — FLAG + INERT**: no `register_completer` in prod → raises `LLMRoutingError`, never egresses today. Masking would defeat field extraction (same rationale as OCR). If a prod completer is ever wired, revisit. |
| 20 | `relopass/agents/runtime.py:197/212` | Yes (via `route_llm`) | OCR'd document body | No masking | n/a | **N-A (extraction-by-design) — FLAG + INERT** (same as #19). |
| 21 | `relopass/agents/extraction/_common.py:80/90` | Dispatch helper | Pass-through (caller-supplied) | No masking | logs task/model only | **N-A** — plumbing; concern lives in callers #19/#20. INERT in prod. |
| 22 | `relopass/llm/router.py:351` | Routing only | Sees pre-built prompt; sha256-hashes it for audit | n/a (hash, not leak) | digests only | **N-A** (deterministic router, no egress here). |
| 23 | `llm_client.py:160/294/471/500` | Yes (OpenAI/Anthropic) | Whatever callers pass — masking is the caller's contract | n/a (infra) | structured logging, no raw user text | **N-A** (shared infra; per-caller masking enforced above). |

## Summary

- **Call sites audited:** 23.
- **Confirmed unmasked user-input paths found and fixed:** 3
  - `policy_chunk_retriever.py` — query masked before OpenAI embeddings (covers both retrieval callers).
  - `policy_query_answering.py` — `redact_pii_from_query()` now delegates to canonical `mask_pii()` (gains IBAN/passport/SSN/national-ID coverage).
  - `briefing.py` — employee name anonymised + dependants masked before the direct Anthropic call (was a live, self-flagged egress).
- **Already compliant:** the AnthropicClient chokepoint (#1) and everything routed through it (#2,#3,#5,#10,#11,#12), plus `rce_entity_resolution_ai` (#13) and `llm_resource_extractor` (#14).
- **Exempt:** published-policy-document and document-image OCR paths (#4,#9,#14,#17,#18).

## Flagged for human review (uncertain / residual risk)

1. **`llm_policy_extractor.py` (#15) & `policy_canonical_extraction.py` (#16)** — send
   HR-uploaded policy **document** text (exempt category) to Anthropic/OpenAI with **no
   masking layer** and (for #15) via the raw SDK. If an uploaded policy PDF embeds an
   individual's name / contact / ID (e.g. a worked example or a signatory), it would
   egress unmasked. Low likelihood, but worth a product decision on whether to mask
   uploaded-document text.
2. **`relopass/agents/extraction/*` (#19–#21)** — put post-OCR document PII into prompts
   with no masking. **Inert in production today** (no `register_completer` outside tests
   → `LLMRoutingError`). Their purpose is field extraction, so masking is self-defeating
   (same as the passport OCR exemption). If a completer is ever wired for prod, this
   becomes a live unmasked egress and needs a documented exemption + DPA note.
3. **`outputs/friday_005_policy_ingestion_spike.py`** — the briefing module docstring
   asks to keep `build_user_prompt` byte-identical with this spike artifact. The SEC-03
   masking change was applied to the prod module only; the spike is a historical
   one-off and was left untouched.

## Verification

New regression test: `backend/tests/test_pii_masking_llm_egress.py` (added to the CI
curated list in `.github/workflows/ci.yml`). It mocks each client and asserts the
payload it receives contains the `[REDACTED_*]` placeholders, not the raw PII, for:
the AnthropicClient chokepoint, the embeddings retrieval path, the policy-query
redactor, and the briefing prompt.
