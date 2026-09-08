# Mistral — Request for Article 9 GDPR Addendum

**To:** Mistral AI Sales / Legal (`enterprise@mistral.ai` — confirm with your sales contact)
**From:** Romain Lecomte, ReloPass (`romain_lecomte@hotmail.com`)
**Subject:** Article 9 GDPR Data Processing Addendum — ReloPass / Mistral La Plateforme + Mistral OCR

---

## Pre-send checklist

- [ ] Confirm the recipient address with the sales rep who walked you through the platform demo.
- [ ] Attach (or link to) your most recent ReloPass DPIA summary if you have one ready.
- [ ] CC `legal@<your-domain>` if you have a legal/counsel address routed for compliance correspondence.

---

## Email body (copy-paste)

Hi Mistral team,

I'm following up on our use of Mistral La Plateforme and Mistral OCR for ReloPass, a B2B SaaS platform supporting cross-border employee relocations across the EU/EEA. As part of our GDPR Article 30 Records of Processing Activities and Article 35 DPIA, I need written confirmation on how Mistral handles special-category data under Article 9 GDPR.

**Background on our processing**

Our pipeline processes identity and employment-related documents from relocating employees and their family members, specifically:

- Passport images including biometric photo regions (Article 9(1) biometric data when used for identification)
- National ID cards
- Residence permits
- Marriage and birth certificates
- Criminal-record extracts (Article 10 data — processed under Member State law authorization, e.g. AufenthG §18g supporting documentation in Germany)
- Employment contracts and payslips

We use Mistral OCR for text extraction from these documents and intend to evaluate Mistral Large for downstream structured-field extraction.

**Your published DPA**

Your standard Data Processing Addendum at `https://legal.mistral.ai/terms/data-processing-addendum` covers Article 6 (general personal data) and the standard sub-processor structure, but does not explicitly address Article 9 (special-category data) or Article 10 (criminal-conviction data). We need this gap closed in writing before we can process passport images or criminal-record content through your services.

**What we are asking for**

A written addendum or written confirmation covering the following four points:

1. **Article 9(2)(b) basis confirmed.** Confirmation that Mistral, as processor, supports processing under Article 9(2)(b) GDPR (employment / social-security / social-protection law obligations of the controller). We process under this basis on behalf of our employer customers (the controllers).

2. **Technical and organisational measures specific to special-category data.** Brief written description of the additional safeguards Mistral applies to special-category and Article 10 data — including encryption at rest, encryption in transit, access controls on the inference logs, and retention windows for special-category inputs/outputs.

3. **Zero-data-retention option for special-category processing.** Confirmation of how to enable ZDR on our account (we understand it's available on enterprise contracts), and written confirmation that with ZDR enabled, Mistral does not retain prompt content or model outputs beyond the inference window — explicitly extended to special-category inputs.

4. **EU data residency on special-category processing.** Written confirmation that special-category inputs processed by our account never leave the EEA, including any sub-processors involved in the inference pipeline (we noted your published commitment to EU hosting; we need this explicitly extended to Article 9 data).

If signing a bespoke addendum is heavier than a written letter, a signed letter on Mistral letterhead covering points 1–4 above is sufficient for our DPIA records.

**Timeline**

We have a P0 internal milestone of ReloPass Cohort 1 pilot launch in early Q3 2026. If Article 9 confirmation is achievable on a 2–4 week timeline, we proceed with Mistral as the primary OCR + LLM provider for our document pipeline. If the timeline is materially longer, we will need to restrict Mistral usage to non-passport, non-criminal-record document types (employment contracts, payslips, diplomas) and route biometric and Article 10 content through alternative providers — which is a path we would prefer to avoid.

Happy to schedule a 30-minute call with your sales or legal team if useful, or to sign your standard NDA first if the addendum process requires it.

Thanks in advance for moving this quickly.

Best,
Romain Lecomte
Founder, ReloPass
romain_lecomte@hotmail.com

---

## Internal notes (do NOT send)

- The "30-minute call" offer is the lever — Mistral sales tends to escalate written-only DPA requests but moves quickly when a deal-blocking call is on the table.
- The "preferred path" framing at the end signals you ARE willing to walk away, which usually shortens the cycle.
- If Mistral comes back asking for ReloPass volume estimates: be honest that you're at the pilot stage. They've been responsive to small-pilot accounts.
- File response under `audit/compliance/responses/mistral_article_9_<YYYY-MM-DD>.pdf` when it arrives.
- If response is positive: update `audit/AI_TOOLS_AND_FLYWHEEL.md` §1.C7 and `audit/AI_NODE_INVENTORY.md` row for `ocr.passport_extractor` (Mistral row).
- If response is negative or > 4 weeks: restrict Mistral OCR to non-passport doc types per `audit/AI_AGENT_STRATEGY.md` §5 tooling table, escalate Azure DI prebuilt-ID for passports.
