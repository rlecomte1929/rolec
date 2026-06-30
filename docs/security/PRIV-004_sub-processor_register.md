# Sub-Processor Register — ReloPass (GDPR Art. 28 & 44)

**Task:** PRIV-004 (AIQ-472) · **Version:** v1.2 · **Last verified:** 2026-06-09 (against `main`)
**Owner:** Romain Lecomte · **Status:** register complete; DPA signatures pending (human action)

> GDPR Art. 28 requires a signed Data Processing Agreement (DPA) with every sub-processor
> before they handle personal data on our behalf. Art. 44–49 require an adequate transfer
> mechanism (SCCs / DPF) for any EU personal data sent outside the EEA. This register is the
> source of truth for both. Re-verify whenever a sub-processor is added or removed from the stack.

## Register

| Sub-processor | Role | Region / residency | EU transfer mechanism | DPA status | Evidence (code) |
|---|---|---|---|---|---|
| **Supabase** | Database + Auth + Storage | **AWS eu-west-1 (Ireland)** ✅ | Data in EU — no transfer | ⬜ Sign via dashboard | Project `nsvefcvpvwwwhuqyuqmp` |
| **Render** | Frontend Static Site + Backend Web Service | Confirm deployment region (US default; EU/Frankfurt plan-dependent) | SCCs via Render DPA if US | ⬜ Sign + confirm region | `README.md` deploy section |
| **Cloudflare** | DNS / CDN (frontend) | Global edge; US entity | Cloudflare customer DPA (SCCs) | ⬜ Confirm in account Legal | `README.md`, `README_DEPLOY_CLOUDFLARE.md` |
| **OpenAI** | LLM — embeddings + policy extraction/Q&A | **US** | DPA + DPF/SCCs | ⬜ Confirm on platform | `openai==1.51.2`; `policy_assistant_embedder.py`, `llm_client.py` |
| **Anthropic** | LLM — Policy Assistant, roadmap, entity resolution | **US** | DPA (Commercial Terms) + SCCs | ⬜ Confirm Commercial plan | `anthropic==0.39.0`; `llm_client.py`, `policy_assistant_llm_client.py`, `roadmap_generator.py` |
| **Mistral AI** | Document AI OCR — general document text extraction (rce pipeline; non-passport civil-status documents) | **EU (France)** ✅ | Data in EU — no transfer | ⬜ Confirm DPA on console | `MISTRAL_API_KEY`; `mistral_ocr_client.py`, `rce_ocr_parser.py` |
| **Resend** | Transactional email | US entity | SCCs via Resend DPA | ⬜ Self-service DPA | `RESEND_API_KEY` / `EMAIL_PROVIDER=resend`; `dossier_notifications.py`, edge fn `send-notification-email` |
| **PostHog** | Product analytics | **US host by default** (`us.i.posthog.com`) | EU Cloud option or SCCs | ⬜ Conditional — see note | `frontend/src/analytics.ts` (`posthog-js`) |

## Notes & corrections (v1.1 → v1.2)

- **PostHog added.** `frontend/src/analytics.ts` initialises `posthog-js` against `https://us.i.posthog.com`
  by default. It is **gated on `VITE_POSTHOG_KEY`**, which is not present in `.env.example`, so it is
  most likely disabled in production today. **Before enabling it for EU users:** either point
  `VITE_POSTHOG_HOST` at PostHog EU Cloud (`https://eu.i.posthog.com`) or sign the PostHog DPA + SCCs,
  and disable `autocapture` of PII. Until enabled it ships in the bundle but transmits nothing.
- **Anthropic re-listed as a live sub-processor.** The v1.1 register treated Anthropic as replaced by
  OpenAI; the codebase now uses **both**. Anthropic powers the Policy Assistant and several internal
  AI features. DPA is auto-incorporated on Anthropic Commercial Terms — confirm the account is on the
  paid/Commercial API plan.
- **Supabase region confirmed EU** — no migration required.
- **Mistral AI added (E-PIPE-OCR).** General OCR engine for the rce extraction pipeline — receives the raw
  document image/PDF (marriage/birth certs, foster orders, tax certs, diplomas). OCR inherently sends the
  document content (you cannot `mask_pii` an image you must read), mirroring the existing GPT-4o passport
  path. Mistral is **EU-hosted (France)** so no transfer mechanism is required. Gated on `MISTRAL_API_KEY`
  — disabled (no OCR, fail-soft empty text) until the key is provisioned. Confirm the DPA on the Mistral
  console before processing real customer documents.

## PII-in-prompts posture (criterion 5)

- A centralised masker exists: `backend/app/services/pii_masker.py` (`mask_pii()`), masking phone, IBAN,
  passport, SSN/D-number, national ID, email, and person names.
- **The `policy_assistant_llm_client.py` path** masks `user_message` at a single chokepoint
  (`AnthropicClient.complete()`), so every caller routed through it — Policy Assistant RAG, immigration
  answers, factual/contradiction verifiers, and the **roadmap generator** — inherits masking. (The
  roadmap generator is additionally data-minimised by construction: its prompt SUBJECT is built only from
  ISO country codes + corridor/pathway classification, never names/email/passport.)
- **The general `llm_client.py` path** (`complete` / `complete_text` / `claude_complete` /
  `claude_complete_text` + sync bridges) does **not** mask — its docstring states masking is the caller's
  responsibility. **GAP CLOSED (H1, 2026-06-30):** every one of its call sites is now reviewed and either
  masks user free-text before building the prompt, or is exempt (no user PII / published-corpus grounding
  text that must not be masked). Status by call site:

  | Call site | Status | Notes |
  |---|---|---|
  | `services/receipt_field_extractor.py` | MASKED | `mask_pii(ocr_text)` before `complete()` |
  | `services/requirement_fact_extractor.py` | MASKED | `mask_pii(raw)` before `complete_text()` |
  | `services/policy_query_answering.py` | MASKED | query redacted via `redact_pii_from_query()`→`mask_pii()` upstream; context = published policy chunks |
  | `routers/support.py` | MASKED (H1) | `mask_pii(subject)` + `mask_pii(content)` — support-ticket free-text |
  | `routers/analytics_query.py` | MASKED (H1) | `mask_pii(question)` — analyst free-text; aggregate context left intact |
  | `services/prospect_enrichment_service.py` | MASKED (H1) | `mask_pii(raw_input_notes)` — admin free-text; published web evidence left intact |
  | `services/catalog_scraper.py` | EXEMPT | prompt = service category + destination city/country codes; no user PII |
  | `services/policy_canonical_extraction.py` | EXEMPT | user = published corporate policy document text; masking would corrupt extraction grounding |
  | `services/ocr_passport_extractor.py` | EXEMPT | prompt text is a static instruction; PII is in the image (vision OCR; `mask_pii` is text-only), mirroring the Mistral OCR path above |

- **Regression guard:** `backend/tests/test_llm_client_caller_allowlist.py` enumerates every module that
  imports a general `llm_client` entry point and fails CI when a new, unreviewed caller appears — forcing
  a MASKED/EXEMPT classification on each new call site. Caller-level masking is asserted in
  `backend/tests/test_pii_masking_llm_egress.py`.

## Actions still requiring human sign-off (AI cannot perform)

1. **Sign DPAs** — Supabase (dashboard/PandaDoc), Render (`render.com/privacy`),
   OpenAI (`openai.com/policies/data-processing-addendum`), Anthropic (confirm Commercial Terms),
   Resend (`resend.com/dpa`), Cloudflare (account Legal), PostHog (only if enabled).
2. **Confirm Render deployment region** and whether EU hosting is available on the current plan.
3. **Store signed DPA copies** in a durable legal/compliance location.
4. **Re-run this register** whenever a sub-processor is added.

## Source

GDPR compliance gap — Security Audit follow-up (2026-05-27), re-verified against `main` 2026-06-09.
Severity: High · Category: gdpr / international_transfers / sub-processors.
