# Sub-Processor Register — ReloPass (GDPR Art. 28 & 44)

**Task:** PRIV-004 (AIQ-472) · **Version:** v1.5 · **Last verified:** 2026-07-16 (against `main`)
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
| **PostHog** | Product analytics (frontend `posthog-js` + **backend server-side events**) + session replay (**replay gated to test-drive only**) | **EU host** (`eu.i.posthog.com`) ✅ | EU Cloud — no transfer | ⬜ Confirm DPA on EU project | `frontend/src/analytics.ts` (`posthog-js`); replay gate `frontend/src/components/TestDriveReplayGate.tsx`; backend `backend/app/posthog_client.py` (`posthog` Python SDK) |

## Notes & corrections (v1.1 → v1.5)

- **PostHog backend server-side events added (v1.5, #1504).** `backend/app/posthog_client.py`
  initialises the `posthog` Python SDK in the app lifespan and captures eight product-analytics
  events server-side: `user_signed_up`, `user_logged_in`, `user_logged_out` (`auth.py`),
  `ai_decision_recorded` (`ai_decisions.py`), `recommendations_requested` (`recommendations/router.py`),
  `policy_published` (`policy_publish.py`), `case_created`, `case_assigned` (`main.py`). Unlike the
  frontend replay (test-drive-only, synthetic identities), this flow fires for **real HR / employee /
  admin users** in production, so the personal-data posture matters. Two controls keep it
  data-minimised: (1) **event properties are PII-free** — booleans, counts, enums, category names and
  durations only (e.g. `role`, `has_company`, `decision`, `feature`, `service_count`, `duration_ms`);
  no names, emails, free-text (`reason`/notes are sent only as `has_reason` booleans), or case
  contents leave the platform. `distinct_id` is the internal **user id** (a pseudonymous identifier),
  not the email. (2) **Exception autocapture is disabled** (`enable_exception_autocapture=False`) —
  server-side stack traces + local variables (which can contain raw PII: SQL params, request bodies)
  are **not** shipped; only the explicit events above are sent. The whole flow is gated on
  `POSTHOG_PROJECT_TOKEN`, so dev/CI (and any env without the token) is a silent no-op. Same EU host
  (`eu.i.posthog.com`) as the frontend — EU residency, no transfer. DPA on the PostHog EU project
  still needs signing (human action).

- **PostHog moved to EU + replay gated to test-drive (v1.4, TD-M2 / AIQ-1560).** `analytics.ts` now
  defaults `posthogHost` to `https://eu.i.posthog.com` (Render also sets `VITE_POSTHOG_HOST` to it), so
  EU personal data no longer transfers to the US host — the earlier hard gate is resolved on residency.
  The SDK still loads for behavioural analytics, but **session recording is OFF by default**
  (`disable_session_recording: true`) and is started **only inside a test-drive session**
  (`ensureTestDriveReplay()` fires only when the browser holds the provision-stashed session, via
  `TestDriveReplayGate`) — so **no real HR/employee/admin user is ever recorded**. Within the recordings
  we do capture: the on-screen relocation/case data is **synthetic** (test-drive uses seeded `@probe.test`
  identities + made-up case data), and the only real PII — the tester's name + email — is entered into
  **form inputs**, which are masked (`maskAllInputs: true`). Recordings are identified by the
  `test_sessions` session_id (`posthog.identify`) so the admin dashboard deep-links to each replay. DPA
  on the PostHog EU project still needs signing (human action).

## Notes & corrections (v1.1 → v1.3)

- **PostHog added.** `frontend/src/analytics.ts` initialises `posthog-js` against `https://us.i.posthog.com`
  by default. It is **gated on `VITE_POSTHOG_KEY`**, which is not present in `.env.example`, so it is
  most likely disabled in production today. **Before enabling it for EU users:** either point
  `VITE_POSTHOG_HOST` at PostHog EU Cloud (`https://eu.i.posthog.com`) or sign the PostHog DPA + SCCs,
  and disable `autocapture` of PII. Until enabled it ships in the bundle but transmits nothing.
- **PostHog session replay enabled (v1.3, AIQ-1434).** `frontend/src/analytics.ts` now sets
  `session_recording: { maskAllInputs: true }`. Input values (passwords, tokens, PII typed into fields)
  are masked, **but rendered on-screen text is NOT** — displayed names, emails, addresses and case
  details are captured in the replay DOM and transmitted to PostHog. This materially **widens the personal-data
  surface** sent to a US sub-processor beyond behavioural events. Consequence: the EU-Cloud-or-signed-DPA+SCCs
  requirement above is now a **hard gate** before relying on recordings for EU users in production, and
  `maskTextSelector` should be added if displayed PII text must also be masked. Recordings remain inert
  wherever `VITE_POSTHOG_KEY` is unset. **Owner decision still pending** — do not treat recordings as
  compliant-for-prod until the DPA/EU-residency posture is confirmed.
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
