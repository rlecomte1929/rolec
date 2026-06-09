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

## PII-in-prompts posture (criterion 5)

- A centralised masker exists: `backend/app/services/pii_masker.py` (`mask_pii()`), masking phone, IBAN,
  passport, SSN/D-number, national ID, email.
- It is currently wired into `policy_assistant_llm_client.py` only. The general `llm_client.py`
  (`complete()`/`complete_text()`) paths do **not** mask. The data-minimisation rule added to `CLAUDE.md`
  makes masking a hard rule for all new LLM calls; retro-fitting the existing general paths is tracked
  as a follow-up.

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
