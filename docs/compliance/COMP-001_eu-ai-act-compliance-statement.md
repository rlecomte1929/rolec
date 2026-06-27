# EU AI Act Compliance Statement — ReloPass

**Document ID:** COMP-001  
**Version:** 0.1 (draft — Human Review required before publication)  
**Date:** 2026-06-27  
**Author:** AI Research (AIQ-1222)  
**Status:** Draft — requires legal review before any external use

---

## 1. Scope and Purpose

This document assesses ReloPass's obligations under **Regulation (EU) 2024/1689** (EU Artificial Intelligence Act) as a provider and deployer of AI systems used in cross-border corporate relocation services. It covers all AI functionality shipped in the ReloPass platform as of Q2 2026.

**Applicable implementation timeline:**

| Milestone | Date | Status |
|-----------|------|--------|
| Prohibited AI practices | 2 Feb 2025 | In force |
| GPAI model obligations | 2 Aug 2025 | In force |
| High-risk AI system obligations (Annex III) | 2 Aug 2026 | Upcoming |
| Remaining high-risk systems (Annex I) | 2 Aug 2027 | Future |

---

## 2. AI System Inventory

| System | Description | Technology | Output |
|--------|-------------|------------|--------|
| **Policy Extractor** | Extracts structured requirements from employer relocation policy PDFs | Claude Fable 5 (Anthropic) via Files API | Structured JSON: allowances, eligibility, caps |
| **Policy Assistant (RAG)** | Answers employee/HR questions about relocation policy | Claude Sonnet + retrieval (pgvector) | Free-text responses with citations |
| **Recommendation Engine** | Suggests suppliers (banks, movers, insurance, housing) per policy | Rule-based orchestrator + LLM ranking | Ranked supplier list with budget estimates |
| **Roadmap Generator** | Produces a step-by-step immigration/logistics roadmap | LLM (Claude Sonnet) + deterministic rules | Timeline of tasks with deadlines |
| **Document OCR** | Extracts structured data from receipts, leases, visa documents | Mistral OCR 4 (planned, AIQ-1147) | Structured fields (amount, date, vendor) |

**Third-party AI sub-processors:**
- Anthropic (Claude Fable 5, Claude Sonnet) — US-based, DPA in place (PRIV-004)
- Mistral AI (mistral-ocr-latest) — EU-based (France), DPA pending (PRIV-004 update required)
- OpenAI (legacy, being phased out) — US-based, DPA in place (PRIV-004)

---

## 3. Risk Classification

### 3.1 High-Risk Assessment (Annex III)

The EU AI Act Annex III, Point 4 lists as high-risk: "AI systems used for recruitment or selection of natural persons, notably for advertising vacancies, screening or filtering applications, evaluating candidates in the course of interviews or tests, **and in the context of monitoring and evaluating the performance of persons during a work relationship.**"

**Assessment for ReloPass:**

| Question | Answer |
|----------|--------|
| Does ReloPass make decisions about employment? | No — the platform supports relocation logistics, not hiring/firing decisions |
| Does ReloPass evaluate employee performance? | No — relocation case status is administrative, not performance-related |
| Does ReloPass affect access to employment (cross-border move)? | Indirectly — a denied relocation could affect mobility, but ReloPass executes HR decisions, it does not make them |
| Does ReloPass provide immigration advice? | Information only; no legal conclusions; disclaimers required |

**Preliminary classification: Limited Risk (Article 50) + GPAI Deployer obligations**

The Policy Extractor and Policy Assistant are not high-risk under Annex III as currently deployed because:
1. They extract/present policy content; humans (HR) make all consequential decisions.
2. No automated decisions with legal/significant effect are made without human review.
3. The system does not evaluate employees or rank candidates for employment.

**⚠️ Risk flag:** If ReloPass ever adds automated eligibility determination (e.g., "AI says employee is not eligible for housing allowance"), that decision pathway would likely be high-risk and would require a conformity assessment.

### 3.2 General Purpose AI (GPAI) Obligations

ReloPass deploys GPAI models (Claude, Mistral) as a downstream deployer. As a deployer (not a provider) of GPAI models:
- ReloPass is not required to publish technical summaries or comply with provider-level GPAI obligations.
- ReloPass must comply with applicable transparency obligations when using GPAI outputs that interact with humans.

---

## 4. Transparency Obligations (Article 50)

Under Article 50, limited-risk AI systems interacting with humans must disclose they are AI.

| Feature | User-facing interaction | Disclosure required | Current status |
|---------|------------------------|--------------------|-|
| Policy Assistant chatbot | Employee/HR chat | Yes — must disclose AI | **Gap** — no AI disclosure banner |
| Roadmap Generator | Displays generated roadmap | Yes — generated content | Partially met — no explicit "AI-generated" label |
| Recommendation Engine | Shows ranked suppliers | Borderline — if presented as objective, disclosure recommended | **Gap** — no "AI-curated" label |
| Document OCR | Extracted fields shown to HR | No direct interaction | No obligation |

---

## 5. Human Oversight (Article 14 — if high-risk applies)

Although currently assessed as limited-risk, best-practice alignment with Article 14 human oversight principles is recommended:

| Principle | Current implementation | Gap |
|-----------|----------------------|-----|
| Human can override AI output | Yes — HR reviews all AI-extracted policy data | ✅ Met |
| Log of AI decisions | Partial — `ai_decisions` table exists; not all paths logged | ⚠️ Partial |
| Explanation of AI decisions | Policy citations shown in Policy Assistant | ✅ Met for Policy Assistant; missing for Roadmap |
| No fully automated significant decisions | Policy: HR approves all | ✅ Met |

---

## 6. Data Governance and PII

| Requirement | Implementation | Status |
|-------------|---------------|--------|
| Data minimization in AI prompts | `pii_masker.py` masks phone, IBAN, passport, SSN, email before any LLM call | ✅ Implemented |
| Sub-processor register | `PRIV-004_sub-processor_register.md` | ✅ Exists — update needed for Mistral OCR |
| GDPR Art. 22 — no purely automated decisions | All AI outputs are advisory; HR/Employee confirms | ✅ Met |
| Data residency | Anthropic/OpenAI are US sub-processors with SCCs; Mistral is EU-based | ⚠️ SCCs must be verified for Anthropic/OpenAI |

---

## 7. Prohibited Practices Check (Article 5)

The following prohibited practices are not present in ReloPass:

- [ ] Subliminal manipulation — Not applicable (no persuasion system)
- [ ] Exploitation of vulnerabilities — Not applicable
- [ ] Social scoring by public authorities — Not applicable (private B2B platform)
- [ ] Real-time biometric identification — Not applicable
- [ ] Emotion recognition in workplace — Not applicable
- [ ] Biometric categorization by protected attributes — Not applicable

---

## 8. Action Items and Gaps

| ID | Finding | Severity | Owner | Target |
|----|---------|----------|-------|--------|
| AI-ACT-01 | Add AI disclosure banner to Policy Assistant chat | Medium | Frontend | Q3 2026 |
| AI-ACT-02 | Add "AI-generated" label to Roadmap and recommendation cards | Low | Frontend | Q3 2026 |
| AI-ACT-03 | Update PRIV-004 with Mistral OCR 4 as sub-processor | Medium | Legal/Ops | Before OCR launch |
| AI-ACT-04 | Verify SCC coverage for Anthropic and OpenAI sub-processor agreements | Medium | Legal | Q3 2026 |
| AI-ACT-05 | Extend `ai_decisions` logging to Roadmap Generator outputs | Low | Backend | Q4 2026 |
| AI-ACT-06 | Establish internal AI governance policy (responsible-use, annual review) | Medium | Leadership | Q3 2026 |
| AI-ACT-07 | Monitor EU AI Office guidance on Annex III Point 4 — relocation could be re-scoped as employment-adjacent | Low | Legal | Ongoing |

---

## 9. Conclusion

As of 2026-06-27, ReloPass's AI systems are preliminarily classified as **Limited Risk** under the EU AI Act. The primary immediate obligations are transparency disclosures (Article 50) for the Policy Assistant and Recommendation Engine. No high-risk obligations apply unless the system is modified to make automated eligibility determinations.

The most critical upcoming work is ensuring GPAI sub-processor agreements (Anthropic, Mistral) include EU AI Act-compliant clauses and that transparency disclosures are added to user-facing AI features before Q3 2026.

**This document requires legal review before being treated as authoritative compliance guidance.**

---

*See also: `docs/security/PRIV-004_sub-processor_register.md` (GDPR Art. 28 sub-processor register)*
