# ReloPass Pilot — Data Handling Agreement

**Document type:** Pilot data-handling agreement (must be counter-signed before any document is uploaded)
**Prepared:** 2026-06-04
**Notion:** AIQ-257 · P6-1
**Status:** ⚠️ Template — **not legal advice.** Have counsel review before sending to a pilot participant.

---

> **Operator note (delete before sending):** This is a plain-language pilot agreement drafted to satisfy the task's hard constraint — *"Data handling agreement signed before any documents are uploaded."* It is **not** a substitute for a lawyer-reviewed DPA. For a real-customer pilot involving any personal data, replace this with a counsel-approved Data Processing Agreement that meets GDPR Art. 28. See `docs/privacy/data-residency-and-gdpr.md` for ReloPass's existing residency/GDPR posture.

## Parties

- **ReloPass** ("we", "the Platform"), operated by [legal entity name], [address].
- **[Company Name]** ("you", "the Participant"), [address], represented by [HR contact name, title].

## 1. Purpose

You are participating in a time-boxed evaluation pilot of the ReloPass relocation platform. The purpose is limited to: evaluating the Policy Builder, document extraction, HR review queue, comparison dashboard, and AI assistant, and giving structured feedback. The pilot is **not** a commercial production use of the Platform.

## 2. What data you will provide

- **One or more relocation/benefits policy documents.** You agree to **remove all employee personal data (PII)** from these documents before upload — names, addresses, salaries tied to named individuals, national ID / passport / SSN / IBAN numbers, and any other identifier of a real person. Policy *terms* (entitlements, thresholds, tiers) are expected; personal data is not.
- **Test employee accounts.** A small number (2–5) of accounts used to exercise the employee-facing flow. These should use **test or pseudonymous identities**, not real employee records, wherever possible.

## 3. What we do with it

- Documents are processed in the ReloPass **staging** environment (not production).
- Extraction runs through the Platform's AI pipeline. Per our security review (AIQ-256), the user's query text is masked for the five PII patterns (phone, IBAN, passport, SSN, national ID) before any third-party LLM call, and assistant traces store a hashed query, never raw text.
- Access to your uploaded documents is limited to the ReloPass pilot operator and the engineering team. It is **not** shared with other pilot participants.

## 4. What we will NOT do

- We will not use your documents to train third-party models.
- We will not load your data into production or expose it to other tenants.
- We will not retain your documents beyond the retention window in §6.

## 5. Confidentiality

Both parties keep the other's non-public information confidential. Your policy contents are your confidential information; the Platform's unreleased features and any pre-GA behaviour you observe are ours.

## 6. Retention & deletion

- Pilot data is retained only for the duration of the pilot plus **30 days** for analysis.
- On written request, or at the end of the retention window, we delete your uploaded documents and associated extracted records from staging.
- AI assistant traces (hashed queries only, 90-day retention per P5-8) are exempt as they contain no document content or PII.

## 7. No warranty / pilot status

The Platform is pre-GA. It is provided for the pilot **"as is"**, with no warranty of accuracy or availability. **Extracted policy values and AI assistant answers must be independently verified by you before any real-world reliance.** This is an evaluation, not legal or immigration advice.

## 8. Liability

Neither party is liable to the other for indirect or consequential losses arising from the pilot. [Insert any cap / carve-outs your counsel requires.]

## 9. Term & termination

- The pilot runs for approximately **3 weeks** from the onboarding date.
- Either party may end participation at any time with written notice; §5 (Confidentiality) and §6 (Retention & deletion) survive termination.

## 10. Governing law

This agreement is governed by the laws of [jurisdiction]. [Adjust to ReloPass's standard.]

---

## Signatures

By signing, both parties agree to the terms above. **No document will be uploaded to the Platform until both signatures are in place.**

| | ReloPass | Participant |
|---|---|---|
| Name | | |
| Title | | |
| Signature | | |
| Date | | |

---

### Pre-upload checklist (operator confirms before enabling upload)

- [ ] Agreement counter-signed by both parties.
- [ ] Participant has confirmed all employee PII is removed from the policy document(s).
- [ ] Pilot is running on **staging**, not production.
- [ ] If real (un-redacted) customer data is involved: external pen test (P5-9 §3) is complete. _Otherwise: redacted/synthetic data only._
