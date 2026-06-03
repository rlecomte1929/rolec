# EU AI Act — Conformity Assessment Record v1 · ReloPass

**Task**: AI-004 · AIQ-652
**Author**: Claude Cowork via notion-task-executor
**Date**: 2026-06-03
**Owner**: Romain (CTO + provider rep) → external counsel (sign-off)
**Regulation reference**: EU AI Act (Regulation 2024/1689) Article 43; Annex VI (conformity assessment based on internal control)
**Cross-references**: AI-001 Annex III classification (Done); AI-003 Annex IV technical doc (`outputs/annex_iv_technical_doc_v1.md`); AI-006 risk register (`outputs/risk_register_v1.md`)
**Document status**: v1 — engineer-perspective assessment. Counsel review required before Article 47 declaration of conformity is signed.

---

## 1. Assessment route selection (Article 43)

### 1.1 Why this route applies

Article 43(2) of the EU AI Act states:

> *For high-risk AI systems referred to in points 2 to 8 of Annex III, providers shall follow the conformity assessment procedure based on internal control referred to in Annex VI…*

ReloPass was classified as high-risk under **Annex III point 4** (employment, workers' management, access to self-employment) per AI-001. Point 4 is within the points-2-to-8 range, so the internal-control route (Annex VI) is the correct procedure.

### 1.2 Route selected

**Annex VI — Conformity assessment based on internal control.** This means ReloPass, as the provider, takes responsibility for verifying its own conformity, supported by:

- A quality management system per Article 17.
- A risk management system per Article 9 (operationalised in `outputs/risk_register_v1.md`).
- The complete technical documentation file per Article 11 + Annex IV (`outputs/annex_iv_technical_doc_v1.md`).
- An EU declaration of conformity per Article 47 (TBC — Annex IV §7 gap).
- CE marking before placing on the EU market (Article 48).

A **notified body** is not required for the points-2-to-8 internal-control route. Notified-body involvement is only mandatory for Annex III point 1 systems (biometrics-related) per Article 43(1).

### 1.3 What internal control requires (Annex VI)

Annex VI requires the provider to:

1. **Verify** that the quality management system meets Article 17.
2. **Examine** the technical documentation and assess conformity with Sections 2 (data + data governance), 3 (technical documentation), 4 (record-keeping), 5 (transparency + information to deployers), 6 (human oversight), 7 (accuracy + robustness + cybersecurity).
3. **Maintain** the technical documentation for 10 years after the AI system is placed on the market.
4. **Provide** the documentation to national competent authorities on request.

This document is the **examination record** of step 2 — the internal verification that ReloPass's high-risk AI system, as built today, conforms to the relevant Section requirements.

---

## 2. Quality management system verification (Article 17)

Article 17 requires a documented QMS proportional to the size of the provider organisation. For an early-stage provider, this is a lightweight but documented system, not an ISO-certified one.

| Article 17 requirement | ReloPass evidence | Status |
|---|---|---|
| (a) strategy for regulatory compliance | EU AI Act readiness roadmap; AI-003 / AI-006 / AI-004 / AI-007 worked through | ✅ underway |
| (b) techniques for design, design control, design verification | C1-* product specs; PR review process; code-owners file | ✅ in place |
| (c) techniques for development, quality control, quality assurance | Pytest + Vitest CI; AUDIT-A3 RLS guard; type checks | ✅ in place |
| (d) examination, test, validation procedures pre + during + post development | Staging deploy gate; C1-17 fixture corpus eval; `ai_human_feedback` post-deploy monitoring | ✅ in place |
| (e) technical specifications, standards applied | `outputs/annex_iv_technical_doc_v1.md` §6 (ISO 23894, ISO 42001 alignment) | ✅ documented |
| (f) systems + procedures for data management | GDPR data flow doc (TBC, PRIV-001); data-residency Annex IV §6 | ⚠ PRIV-001 in progress |
| (g) risk management system per Article 9 | `outputs/risk_register_v1.md` | ✅ in place |
| (h) post-market monitoring system per Article 72 | Annex IV §8 | ✅ documented |
| (i) procedures for reporting serious incidents per Article 73 | Annex IV §8.2 + register R-INC-01 | ⚠ template + secondary on-call gap |
| (j) handling of communication with national competent authorities | Counsel-mediated; provider contact log (TBC) | ⚠ formalise |
| (k) systems + procedures for record-keeping of relevant documentation | `audit/` directory in repo; Notion AI Work Queue | ✅ in place |
| (l) resource management, including security-of-supply measures | Provider DPAs + redundancy via shadow-OCR + multi-provider LLM | ✅ in place |
| (m) accountability framework — roles + responsibilities of management + staff | Single-founder org chart; Romain holds CTO + acting CISO + acting DPO | ⚠ document explicitly |

**Verification result**: QMS is **substantively in place** at a level proportional to provider size; 4 gaps explicitly noted. Counsel should pressure-test each gap against Article 17 interpretation guidance.

---

## 3. Technical documentation examination

The technical documentation (Annex IV) was generated at `outputs/annex_iv_technical_doc_v1.md` on 2026-06-03 by `notion-task-executor`. This examination walks each Section requirement and confirms the documentation covers it.

| Section requirement | Annex IV § | Examination result |
|---|---|---|
| Section 2: data + data governance (Art. 10) | §2.4 | ✅ covered — data lifecycle, retention, lawful basis, test data sources |
| Section 3: technical documentation (Art. 11 + Annex IV) | All 9 sections | ✅ covered — v1 doc complete with 18 catalogued gaps |
| Section 4: record-keeping (Art. 12) | §1.2 + §3 + §8 | ✅ covered — git SHA logs, agent_runs, case_audit_events, rce.rule_citations |
| Section 5: transparency + information to deployers (Art. 13) | §1.8 + §1.9 + §5.2 | ✅ covered — in-product reviewer instructions; statutory note; changelog plan |
| Section 6: human oversight (Art. 14) | §2.5 + §3.3 + §4.4 | ✅ covered — confirm-gate, review queue, override, audit trail, escalation |
| Section 7: accuracy + robustness + cybersecurity (Art. 15) | §2.7 + §3.1 + §4 | ✅ covered — metrics, limitations, security mitigations |

**Examination result**: Annex IV v1 doc **covers all six Section-2 requirements**. 18 gaps explicitly catalogued — none are showstopper; all closeable before submission.

---

## 4. Traceability matrix

Maps every Annex III high-risk obligation (relevant points) and every Chapter III Section requirement to the artefact that demonstrates conformity.

| Obligation source | Specific requirement | Demonstrated by | Status |
|---|---|---|---|
| Annex III point 4 | High-risk classification confirmed | AI-001 risk classification (Done) | ✅ |
| Article 9 | Risk management system established + maintained | `outputs/risk_register_v1.md` (AI-006, Done 2026-06-03) | ✅ |
| Article 10(1) | Data governance practices in place | Annex IV §2.4 | ✅ |
| Article 10(2)(a–g) | Training/validation/testing data quality | Annex IV §2.4.2 + §2.4.3 + C1-17 corpus | ⚠ benchmark dating |
| Article 10(3) | Datasets relevant + representative + free of errors + complete | C1-17b fixture corpus methodology | ⚠ Datasheets-for-Datasets gap |
| Article 10(4) | Statistical properties of datasets documented | Annex IV §2.4.3 | ⚠ formalise |
| Article 10(5) | Special-category data only where strictly necessary | Annex IV §3.2 R-PII risks + retention bounds | ✅ |
| Article 11 + Annex IV | Technical documentation drawn up + kept up-to-date | `outputs/annex_iv_technical_doc_v1.md` (AI-003, Done 2026-06-03) | ✅ |
| Article 12 | Automatic recording of events ("logs") | `agent_runs`, `case_audit_events`, `rce.rule_citations`, `ocr_shadow_comparisons` | ✅ |
| Article 13(1) | Operation sufficiently transparent for deployer to interpret outputs | Reviewer instructions; statutory note; AIQ-680 disclaimer (PR #231) | ✅ |
| Article 13(2) | Instructions for use accompany the system | In-product onboarding + Pathway sequencing | ⚠ deployer playbook gap |
| Article 13(3) | Instructions cover identity of provider + characteristics + capabilities + limitations + foreseeable misuse + maintenance + lifespan | Annex IV §1 + §3.1 + §3.2 + §5 | ✅ documented; ⚠ playbook still pending |
| Article 14(1) | Human oversight measures appropriate to risks | Annex IV §2.5 + §3.3 | ✅ |
| Article 14(2) | Oversight aims to prevent or minimise risks | risk register mitigations + Pathway confirm + HR override | ✅ |
| Article 14(3)(a) | Measures designed into the AI system | Pathway UX + HR review queue UX | ✅ |
| Article 14(3)(b) | Measures identified by provider before placing on market | This conformity assessment record | ✅ |
| Article 14(4)(a–e) | Specific oversight capabilities for the natural person | Annex IV §3.3 covers all 5 sub-points (interpret, deviate, override, decide-not-to-use, halt) | ✅ |
| Article 15(1) | Accuracy + robustness + cybersecurity at appropriate level | risk register R-* entries + Annex IV §2.7 metrics | ✅ |
| Article 15(2) | Levels of accuracy and metrics declared in instructions for use | Annex IV §2.7 (instruments) + §3.1 (capabilities) | ⚠ user-facing declaration not yet in deployer playbook |
| Article 15(3) | Robustness — resilient to errors + faults + inconsistencies | shadow-OCR, escalation tiers, schema validation, refusal-to-classify | ✅ |
| Article 15(4) | Resilient against attempts to alter use, outputs, performance | input guardrails (P5-1), prompt injection register (R-INJ-01/02) | ⚠ P5-1 in progress |
| Article 15(5) | Cybersecurity per state of the art | SEC-001 (Done), SEC-002 (Done), SEC-006 (Validation), Supabase platform security | ✅ |
| Article 16(c) | Conformity assessment procedure followed | This document (AI-004, v1) | ✅ this is it |
| Article 17 | QMS in place | §2 above | ⚠ 4 sub-points gap |
| Article 18 | Documentation kept for 10 years | `audit/` directory retention + Notion archive | ✅ |
| Article 19 | Automatically generated logs kept for at least 6 months | Database retention policy: extraction logs kept for case duration + 12 months; case_audit_events kept for 6 years per accounting | ✅ |
| Article 47 | EU Declaration of Conformity | Annex IV §7 — template + gap; will be signed after §1-§6 gaps closed | ⚠ deferred |
| Article 48 | CE marking applied | TBC after Article 47 signing | ⚠ deferred |
| Article 49 | Registration in EU database | TBC after CE marking | ⚠ deferred |
| Article 72 | Post-market monitoring plan | Annex IV §8 + risk register monitoring section | ✅ |
| Article 73 | Reporting of serious incidents | Annex IV §8.2 + risk register R-INC-01 | ⚠ template gap |

**Traceability summary**: Every applicable Article requirement is **either fully demonstrated or has a named, closeable gap**. No requirement is unaddressed.

---

## 5. Identified gaps that block formal sign-off

Aggregated from §2 (QMS), §3 (technical doc examination), and §4 (traceability matrix). Prioritised for closure:

### Tier 1 — must close before Declaration of Conformity is signed

1. **Article 17(j)** — formal communication procedure with national competent authorities. **Action**: counsel to confirm correct authority (likely AFNORM or future-named market surveillance body in France) + document contact log template.
2. **Article 17(m)** — explicit role + responsibility documentation. **Action**: short org-chart doc naming Romain as Provider Representative + CTO + acting CISO + acting DPO; counsel-reviewed.
3. **Article 47** — Declaration of Conformity drafted, reviewed, signed. **Action**: populate template at `audit/eu_ai_act/declaration_of_conformity_v1.md` once §6 gaps below closed.
4. **Article 10 datasheets** — Datasheets-for-Datasets format for C1-17b. **Action**: 3-page document per dataset.

### Tier 2 — must close before CE mark applied (Article 48)

5. **Annex IV §1 deployer playbook** — `audit/eu_ai_act/deployer_playbook.md`. **Action**: Cowork-feasible follow-up task.
6. **Article 15(2)** declared accuracy levels in instructions for use — folds into deployer playbook.
7. **Annex IV §6** provider EU residency attestations (4 providers).
8. **Annex IV §8** incident-response template + customer notification template + secondary on-call.

### Tier 3 — must close before EU database registration (Article 49)

9. **ISO 42001 gap analysis** — strengthens the QMS Article 17 narrative.
10. **Annex IV §4** risk register monthly/quarterly recurring template in Notion + calendar.
11. **Article 14 self-assessment** standalone audit file.

### Tier 4 — strongly recommended, not formally gated

12. Public changelog page on relopass.com.
13. Public versioning policy page.
14. SOC 2 trajectory work.

---

## 6. Internal verification statement (engineer's perspective)

I have examined the technical documentation file (`outputs/annex_iv_technical_doc_v1.md`) and the risk management system (`outputs/risk_register_v1.md`). Both v1 deliverables, as of 2026-06-03, **substantively address every applicable Chapter III Section 2 requirement**. The 14 explicit gaps catalogued above are closeable within a 4-6 week engineering + counsel + administrative effort.

This document does **not** constitute legal sign-off. It is the engineering verification record per Annex VI step 2. Counsel review and the Declaration of Conformity per Article 47 follow.

— Generated 2026-06-03 by Claude Cowork on behalf of the Provider engineering function.

---

## 7. Counsel review checklist

External counsel should pressure-test:

1. **Confirm Annex VI route selection** — is internal control the right procedure given Annex III point 4 classification + ReloPass's role as Provider (not Deployer)?
2. **Validate QMS Article 17 coverage** — is the 4-gap remediation list complete?
3. **Validate traceability matrix Article-by-Article** — any obligation missed?
4. **Confirm Article 47 Declaration of Conformity template** — once drafted, validate the fields against current OJ guidance.
5. **Determine national competent authority** — which French authority is the market-surveillance authority for AI Act enforcement?
6. **Confirm 10-year + 6-month retention adequacy** — do current ReloPass data-retention policies meet Article 18 + 19?
7. **Confirm Article 49 EU database registration timing** — what's the registration cadence post-CE-marking?

---

## 8. Recommended follow-up tasks (not auto-filed)

To close the 14 catalogued gaps, suggest filing:

- **AI-004a** · Draft Article 17 QMS documentation gap closures (4 sub-points). Research, Low, Cowork-feasible.
- **AI-004b** · Draft Article 47 Declaration of Conformity v1 template. Research, Low, Cowork-feasible.
- **AI-004c** · Datasheets-for-Datasets for C1-17b corpus. Research, Low, Cowork-feasible.
- **AI-004d** · Deployer playbook (audit/eu_ai_act/deployer_playbook.md). UX Copy + Research, Medium, Cowork-feasible.
- **AI-004e** · Provider EU residency attestation file (4 providers). Research, Low, Cowork-feasible.
- **AI-004f** · Incident response template + customer notification template + secondary on-call assignment. Operations, Low.
- **AI-004g** · ISO 42001 gap analysis. Research, Medium, Cowork-feasible.

Not auto-filed; flag for Romain.

---

## 9. Document metadata

- **Version**: v1.0.
- **Generated**: 2026-06-03.
- **Generator**: Claude Cowork via notion-task-executor.
- **Source materials**: Regulation 2024/1689 Articles 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 43, 47, 48, 49, 72, 73; Annex IV; Annex VI; AI-001 risk classification (Done); AI-003 Annex IV doc (Done 2026-06-03); AI-006 risk register (Done 2026-06-03).
- **Next planned revision**: v1.1 once Tier-1 gaps closed.

---

*Generated 2026-06-03 by Claude Cowork via notion-task-executor. Engineering-side conformity assessment record per Annex VI internal-control route. Counsel review and Article 47 Declaration of Conformity follow.*
