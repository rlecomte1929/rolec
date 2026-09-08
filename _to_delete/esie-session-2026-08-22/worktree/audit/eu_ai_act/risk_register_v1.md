# EU AI Act — Risk Register v1 · ReloPass

**Task**: AI-006 · AIQ-654
**Author**: Claude Cowork via notion-task-executor
**Date**: 2026-06-03
**Owner**: Romain (CTO + acting CISO)
**Regulation reference**: EU AI Act (Regulation 2024/1689) Article 9; ISO/IEC 23894:2023 (AI risk management)
**Cross-references**: Annex IV technical doc §4 (`outputs/annex_iv_technical_doc_v1.md`); AI-001 risk classification
**Document status**: v1 — first formal register. Living document; quarterly review cadence.

---

## How this register is used

Article 9 of the EU AI Act requires a continuous risk management process across the high-risk AI system's lifecycle. This register is the living artefact that satisfies that requirement. It:

1. **Identifies** every meaningful risk to fundamental rights, health, safety, and operational integrity.
2. **Estimates** likelihood × impact in plain language.
3. **Names** the mitigation in place + its current evidence.
4. **Calls out residual risk** — what remains after mitigation.
5. **Assigns** an owner and a review cadence.

Review cadence: **quarterly** (next: 2026-Q3 mid-month). Out-of-cycle review triggered by: new third-party provider, new AI capability added, serious incident per Article 73, change in EU AI Act guidance, customer-reported issue rated H.

Scoring conventions:
- **Likelihood**: Low (rare, <1 incident/year) · Medium (occasional, 1–10/year) · High (frequent, >10/year)
- **Impact**: Low (no harm; recoverable in hours) · Medium (recoverable in days; reputational risk) · High (fundamental-rights harm OR business-existential)
- **Residual rating**: Inherent rating after mitigation. Targets: H residual = unacceptable; M residual = monitor and improve; L residual = accept.

---

## Risk register table

| # | ID | Category | Risk | Inherent L × I | Mitigation in place | Evidence | Residual | Owner | Review |
|---|---|---|---|---|---|---|---|---|---|
| 1 | R-BIAS-01 | Discrimination | OCR accuracy systematically lower for non-Latin scripts (Hindi, Arabic, CJK) → de facto disparate treatment of employees from non-EU origins | M × H | Confidence thresholds force HR review on low-confidence; HR sees full document; per-origin accuracy tracked via `ai_human_feedback`; refuse-to-classify on UNKNOWN <0.50 | C1-04 classifier (AIQ-489); ai_human_feedback table | M | Romain | Q3 |
| 2 | R-BIAS-02 | Discrimination | Extraction agents validated only for FR/DE/NO; downstream forms may de-prioritise employees from other corridors | M × M | All corridors route through general extraction with explicit lower-confidence threshold + mandatory HR review; corridor coverage roadmap published in Cohort 4 plan | C1-05P-b/c/d/e specs; Option-2 MVP doc | M | Romain | Q3 |
| 3 | R-BIAS-03 | Discrimination | Foundation models trained on biased corpora may misread names with diacritics or non-Western patterns | M × H | Shadow OCR (Mistral vs Azure) flags disagreement; per-field human confirm step; corrections logged | ocr_shadow_comparisons table; Pathway confirm UI; ai_human_feedback | M | Romain | Q3 |
| 4 | R-HALL-01 | Hallucination | LLM extractor returns a value the source document does not contain (fabrication) | M × H | Strict JSON schema validation; bbox citation required for every extracted value; values lacking bbox are rejected; refuse-and-escalate on schema parse failure | extraction agents; rce.rule_citations; Pathway citation UI | L | Romain | Q3 |
| 5 | R-HALL-02 | Hallucination | LLM classifier confidently mis-classifies a document → wrong downstream workflow | L × H | UNKNOWN floor at <0.50; escalation tier (gpt-4o-mini → gpt-4o on confidence band); HR review on classification mismatch | C1-04 classifier (AIQ-489) | L | Romain | Q3 |
| 6 | R-INJ-01 | Prompt injection | Adversarial text embedded in uploaded document tricks LLM into changing extraction behaviour | M × M | Input guardrails (P5-1) strip control sequences before LLM; strict schema bounds output; bbox citation back-references prevent output from naming non-source values; refuse-and-escalate on schema parse failure | P5-1 guardrails (in progress); rce.rule_citations | M | Romain | Q3 |
| 7 | R-INJ-02 | Prompt injection | Employee inputs free-text question containing injection payload aimed at policy decision | L × M | Policy questions explicitly out of scope; route to HR via escalation pattern (Pathway "we don't pretend"); no LLM produces policy answer; pathway strings hard-coded for policy refusal | pathway_strings_v1.json `we_cannot.policy_question`; escalate flow | L | Romain | Q3 |
| 8 | R-DRIFT-01 | OCR drift | Mistral DI silently updates model weights causing systematic field-extraction degradation | M × M | Shadow comparison with Azure detects drift; weekly aggregate review of `ocr_shadow_comparisons` disagreement rate; provider model card snapshots on every version bump | ocr_shadow_comparisons; provider model card archive (gap in §2 Annex IV) | M | Romain | Q3 |
| 9 | R-DRIFT-02 | Model drift | Anthropic/OpenAI deprecate or change the LLM behind the classifier; outputs change post-rollout | M × M | Model id pinned per call in `agent_runs.model_id`; deprecation notices feed an immediate prompt-version planning cycle; staging eval against C1-17b fixture corpus before production rollout | agent_runs.model_id; prompt_versions | L | Romain | Q3 |
| 10 | R-PII-01 | Privacy / fundamental rights | Employee documents contain Art. 9 special-category data (e.g., marriage cert reveals sexual orientation; religion docs reveal beliefs) — accidental exposure to wrong tenant or to support team | M × H | RLS enforced multi-tenant isolation; AUDIT-A3 CI guard verifies; service-role access logged; PII stripping from observability logs (P5-1); support access requires audit-logged break-glass | RLS migrations; AUDIT-A3 CI; SEC-001 (PR #192) | L | Romain | Q3 |
| 11 | R-PII-02 | Privacy | LLM provider retains submitted text contrary to DPA (training-data leakage) | L × H | DPAs explicitly forbid training on customer data with each provider; per-provider verification annually (PRIV-004); zero-data-retention flag set on each call where available | PRIV-004 (in progress); provider DPAs | M | Romain | Q3 |
| 12 | R-PII-03 | Privacy | Caching layer (e.g., `translation_cache`) inadvertently caches PII across tenants | L × H | Cache keys hash-only; PII forbidden as cache value; cache writes audited in `agent_runs.cache_hit` | translation_cache table policy; cache key hashing | L | Romain | Q3 |
| 13 | R-AUTH-01 | Security | Auth bypass via debug endpoints exposed in production | (closed) | SEC-001 gated 8 debug routes behind `ENABLE_DEBUG_ENDPOINTS` env flag; production curl probes verify 404 | SEC-001 (AIQ-466, Done); PR #192/#211 | L | Romain | Q3 |
| 14 | R-AUTH-02 | Security | RLS bypass allowing one tenant to read another's data | L × H | RLS enabled on all multi-tenant tables; AUDIT-A3 CI guard blocks merge on RLS misconfig; SEC-002 (RLS + tenant-scoped policies) shipped | SEC-002 (AIQ-487); AUDIT-A3 CI | L | Romain | Q3 |
| 15 | R-UPLOAD-01 | Security | Malicious file uploaded as employee document — RCE via parser, XSS via stored content | L × H | libmagic MIME validation; private Supabase storage bucket; antivirus scan before OCR (gap — confirm scanner status); content rendered with strict CSP | SEC-006 (AIQ-478, in Validation); private bucket audit confirmed | M | Romain | Q3 |
| 16 | R-OVERRELY-01 | Human oversight | HR user blindly accepts AI-extracted values without reading source document → erodes the human-in-loop safeguard | M × M | Reviewer instructions on every AI flag; statutory note on every dossier ("Drafted by ReloPass with AI assistance. Review before submission."); correction rate trended | AIQ-680 disclaimer (PR #231); Pathway statutory note; ai_human_feedback | M | Romain (+ deployer playbook gap) | Q3 |
| 17 | R-AUDIT-01 | Audit + accountability | Audit trail breaks because a code change forgets to write to `case_audit_events` — auditability gap goes undetected | L × H | C1-01c citation audit table shipped (AIQ-751); chain-of-custody integrity test in CI (gap — verify scope); manual quarterly audit-trail walk | rce.rule_citations; case_audit_events; AIQ-751 PR #245 | L | Romain | Q3 |
| 18 | R-INC-01 | Incident response | Serious incident per Art. 73 not detected promptly or not reported within 15 days | M × H | Sentry + uptime monitoring; PagerDuty (gap — single on-call); incident log template (gap — see §8 Annex IV); customer notification template (gap) | observability stack; Annex IV §8 gaps catalogued | M | Romain | Q3 |
| 19 | R-VENDOR-01 | Third-party | Provider outage (Mistral DI / Azure DI / Anthropic / OpenAI) blocks all AI flows | M × M | Shadow OCR path provides graceful degradation; classifier escalation tier provides model failover; clear UX state "I can't read this right now — try again in a minute" | ocr_shadow_comparisons; pathway_strings_v1.json error.network | L | Romain | Q3 |
| 20 | R-VENDOR-02 | Third-party | Provider changes terms of service mid-contract; data residency or retention promises break | M × M | DPAs reviewed annually (PRIV-004); provider DPA snapshots stored; provider EU-residency attestation per Annex IV §6 gap | PRIV-004; Annex IV §6 gap | M | Romain | Q3 |
| 21 | R-REG-01 | Regulatory drift | EU AI Act guidance updates change conformity obligations after submission | L × M | External counsel relationship for AI Act monitoring; quarterly review cadence captures emerging guidance; CEN-CENELEC JTC 21 deliverables tracked | counsel (TBC); Annex IV §6 standards table | M | Romain | Q3 |
| 22 | R-REG-02 | Regulatory drift | GDPR DPA template gets superseded by EDPB guidance; customer DPAs out of compliance | M × M | DPA template review triggered annually + on EDPB guidance publication; tracked under PRIV-004 | PRIV-004 | M | Romain | Q3 |
| 23 | R-CUSTOMER-01 | Customer-side misuse | Deployer (HR user) uses AI surfaces in ways outside the intended purpose (e.g., for hiring decisions, not relocation) | M × H | Intended-purpose statement in deployer onboarding; statutory note on every dossier; ToS prohibits use for Annex III decisions beyond mobility | Annex IV §1.1; ToS (TBC) | M | Romain (+ deployer playbook gap) | Q3 |
| 24 | R-SUBJECT-01 | Data subject rights | Employee asks for SAR / erasure during active relocation case → conflict with contract performance + legal-retention obligations | L × M | SAR + erasure workflow documented (PRIV-001); retention policy = case + 12 months; lawful basis matrix in Annex IV §2.4.2 | PRIV-001 (Ready for AI); retention policy doc | M | Romain | Q3 |
| 25 | R-FAB-01 | Document fabrication | Employee uploads a forged document; OCR extracts a "valid" value; HR commits it | L × H | Bbox citation requires plausible coordinates → forced human eyeball on source; shadow OCR catches some forgeries via parser disagreement; passport MRZ check-digit validation; downstream regulatory submission flags forged docs at the gov side | extraction agents; MRZ check digit logic | M (residual is inherent — fabrications by sophisticated actors will pass our checks) | Romain | Q3 |

**Total documented risks: 25** (covers ≥15 criterion 1 target).

---

## Risk category summary

| Category | # of risks | Residual H | Residual M | Residual L |
|---|---|---|---|---|
| Discrimination / bias | 3 | 0 | 3 | 0 |
| Hallucination | 2 | 0 | 0 | 2 |
| Prompt injection | 2 | 0 | 1 | 1 |
| Model + OCR drift | 2 | 0 | 1 | 1 |
| Privacy / fundamental rights | 3 | 0 | 1 | 2 |
| Security | 3 | 0 | 1 | 2 |
| Human oversight | 2 | 0 | 1 | 1 |
| Third-party / vendor | 2 | 0 | 1 | 1 |
| Regulatory drift | 2 | 0 | 2 | 0 |
| Customer / subject side | 3 | 0 | 2 | 1 |
| Document integrity | 1 | 0 | 1 | 0 |
| **Total** | **25** | **0** | **14** | **11** |

**No Residual-High risks remain.** All H-likelihood-or-impact risks are mitigated to M or L. The 14 Residual-M risks form the monitoring queue; the 11 Residual-L are accepted.

---

## Top-3 risks to monitor most actively (Q3 2026)

These are the risks where mitigation evidence is weakest or where impact-if-realised is highest:

### 1. R-BIAS-01 / R-BIAS-03 — non-Latin script accuracy + foundation model bias

Why: discrimination risks have the highest impact (fundamental rights) and the mitigation depends on monitoring (correction rate by origin) rather than prevention. If the monitoring lags, the discrimination goes undetected.

Action for Q3:
- Build a per-origin / per-script accuracy dashboard from `ai_human_feedback`.
- Set explicit thresholds: >15% correction-rate delta vs the FR/DE/NO baseline triggers a prompt-revision cycle within 30 days.
- Document the dashboard + thresholds in the post-market monitoring plan (Annex IV §8).

### 2. R-INC-01 — incident response readiness

Why: single-person on-call + missing incident templates means the 15-day Art. 73 reporting window is exposed to operational gaps.

Action for Q3:
- Designate a backup on-call (even informally — Romain + one trusted contractor).
- Initialise `audit/incidents/` directory + customer notification template + national-competent-authority contact list.
- Tabletop exercise once per quarter.

### 3. R-FAB-01 — document fabrication

Why: it's the one Residual-M where the residual is inherent — sophisticated forgeries will always pass our automated checks. The mitigation is layered (bbox forces human eye + MRZ check + downstream regulator catches), not single-point.

Action for Q3:
- Document the layered defence explicitly in the deployer playbook (gap from Annex IV §1).
- Add a "report suspected fabrication" path in the HR review UI (currently informal).

---

## Monitoring + review process

### Continuous monitoring (already in place)

- Daily: OCR disagreement rate.
- Daily: classifier escalation rate.
- Weekly: human correction rate by extractor.
- Weekly: support tickets tagged `ai-output`.
- Per merge: AUDIT-A3 RLS CI guard.
- Continuous: dependabot security advisories.

### Quarterly register review (this document)

Every quarter:
1. Walk the table; update mitigation evidence references.
2. Re-score residual ratings against latest production state.
3. Surface any new risks identified in the quarter.
4. Update the Top-3 monitoring list.
5. Close out risks that have been fully mitigated to L for two consecutive quarters.

### Annual full re-assessment

Once per year (next: 2027-Q2 alongside external security review):
1. Full re-walk including AI-001 Annex III classification re-validation.
2. External counsel review of register + Annex IV doc.
3. Renewal of provider DPAs + residency attestations.

### Incident-triggered out-of-cycle review

Trigger an out-of-cycle review whenever:
- A new third-party provider is added.
- A new AI capability launches.
- A serious incident occurs per Article 73.
- EU AI Act / EDPB / national guidance materially updates.
- A customer reports an incident rated H.

---

## Connections to other documents

| Reference | Source | What it shows |
|---|---|---|
| Annex IV §4 Risk Management | `outputs/annex_iv_technical_doc_v1.md` | The Article 9 four-pillar narrative that this register operationalises |
| AI-001 Annex III risk classification | Notion AIQ-xxx (Done) | The upstream decision that classified ReloPass as high-risk |
| AI-002 human oversight mechanism | Notion AIQ-475 (Archived; shipped) | The implementation behind R-OVERRELY-01 + R-AUDIT-01 mitigations |
| AI-003 Annex IV technical doc | Notion AIQ-651 (Done 2026-06-03) | Cross-referenced for every mitigation that cites an artefact |
| AI-004 Conformity assessment | Notion AIQ-652 (Ready for AI) | Will consume this register as evidence in its traceability matrix |
| SEC-001 / SEC-002 / SEC-006 | Notion AIQ-466 / AIQ-487 / AIQ-478 | Security-side mitigations |
| PRIV-001 / PRIV-004 | Notion (Ready for AI / in progress) | GDPR-side mitigations |
| Pathway strings v1 | `outputs/pathway_strings_v1.json` | UX-level enforcement of R-INJ-02 + R-OVERRELY-01 |

---

## Validation against AIQ-654 criteria

- ✅ **Criterion: ≥15 risks documented** — 25 risks identified.
- ✅ **Criterion: each risk has likelihood / impact / mitigation / residual** — see table.
- ✅ **Criterion: cross-referenced from AI-003** — every mitigation cites the same artefacts referenced in the Annex IV doc.
- ⚠ **Criterion: monthly cron entry to re-walk register** — see "Monitoring + review process" section above. Implementation is a deployer-side recurring calendar item (not a code cron); flagged as a follow-up rather than implemented in-line. Recommend formalising the cadence into a Notion recurring template or calendar event.

---

## Known gaps (recursive — to be folded into Annex IV §4 gaps)

- ⚠ **Q3 per-origin accuracy dashboard** — top-priority Q3 action.
- ⚠ **Incident response template + secondary on-call** — top-priority Q3 action.
- ⚠ **Deployer playbook including fabrication-report path** — feeds Annex IV §1 deployer playbook gap.
- ⚠ **Chain-of-custody integrity test in CI** — confirm scope of current AUDIT-A3 vs what's needed for the audit-trail walk.
- ⚠ **Provider EU-residency attestation file** — feeds Annex IV §6 gap.

---

## Document metadata

- **Version**: v1.0 (initial register).
- **Generated**: 2026-06-03.
- **Generator**: Claude Cowork via notion-task-executor.
- **Source materials**: AI Act Art. 9; ISO/IEC 23894:2023; today's ReloPass production state; AI-003 Annex IV doc (`outputs/annex_iv_technical_doc_v1.md`).
- **Next review**: 2026-Q3 (mid-month).

---

*Generated 2026-06-03 by Claude Cowork via notion-task-executor. Living document — quarterly review cadence; out-of-cycle reviews on provider/capability/incident/guidance change.*
