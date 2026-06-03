# P1-07e · GDPR Compliance Checklist + Retention Policy · Case Outcomes

**Task**: AIQ-688 · P1-07e
**Author**: Claude Cowork via notion-task-executor
**Date**: 2026-06-03
**Owner**: Romain (CTO + acting DPO) · target location in repo: `docs/case_outcomes_gdpr.md`
**Regulation reference**: GDPR (Regulation 2016/679) Articles 5, 6, 9, 12-23, 30, 35; cross-reference EU AI Act Art. 10
**Cross-references**: PRIV-003 retention policy (`outputs/priv-003_data_retention_policy_v1.md`); PRIV-001 erasure runbook (being drafted); AI-003 Annex IV §2.4; AI-006 risk register R-PII-* + R-SUBJECT-01

---

## 1. Why this document exists

Case-outcome data — the resolution state of a closed relocation case — has a longer useful life than active case data. HR teams reference it for headcount reporting, mobility analytics, and (occasionally) returning-employee re-onboarding. But the same data carries the heaviest GDPR weight: it captures completed processing of special-category data over many months.

This document is the **per-data-class compliance checklist** for case-outcome records. It maps every field that survives case closure to a GDPR obligation. The PRIV-003 retention policy is the master document; this file is its case-outcomes-specific companion.

---

## 2. What "case outcomes" means

A relocation case has a lifecycle: created → in-progress → submitted-to-authorities → approved/rejected → closed. **Case outcomes** is the snapshot taken at the moment `cases.closed_at` is set. It captures:

- Outcome label (approved / rejected / withdrawn / abandoned).
- Outcome date.
- Final dossier reference (link to rendered submission).
- Aggregate metadata (corridor, immigration pathway, family size, processing time).
- Pointer to audit chain (case_audit_events).

It does **not** include the underlying documents or raw extracted fields — those follow the operational retention rules in PRIV-003 §3.1 (delete at close + 12 months).

---

## 3. Field-level GDPR compliance checklist

| # | Field | PII? | Special category? | Lawful basis | Retention (per PRIV-003) | Erasure-overrideable? | Subject access surfaceable? |
|---|---|---|---|---|---|---|---|
| 1 | `cases.id` (UUID) | Indirect | No | Art. 6(1)(b) contract | + 6 years (in audit chain) | No — pseudonymised in audit | Yes — surfaced as case reference |
| 2 | `cases.employee_id` (FK) | Direct (pointer) | No | Art. 6(1)(b) | + 12 months (PRIV-003 row 1) | Yes (Art. 17) | Yes |
| 3 | `cases.closed_at` (timestamp) | No | No | n/a | + 6 years | n/a | Yes — date only |
| 4 | `cases.outcome_status` (enum) | No | No | Art. 6(1)(b) + Art. 6(1)(c) | + 6 years | No — needed for audit | Yes |
| 5 | `cases.corridor` (FR→NO) | No (system metadata) | No | Art. 6(1)(b) | + 6 years | No | Yes |
| 6 | `cases.pathway_type` (e.g., Skilled Worker / EU Reg) | No | No | Art. 6(1)(b) | + 6 years | No | Yes |
| 7 | `cases.family_size` (integer) | Indirect | Indirect (reveals family composition) | Art. 6(1)(b) + Art. 9(2)(b) | + 12 months | Yes | Yes |
| 8 | `cases.dossier_package_id` (FK) | Indirect (points to documents) | n/a | Art. 6(1)(b) | + 12 months | Yes — child docs deletable | Yes |
| 9 | `cases.processing_days` (integer, derived) | No | No | Art. 6(1)(f) analytics | + 36 months (aggregate) | No | Yes |
| 10 | `case_outcomes.notes` (free text) | Likely | Possibly | Art. 6(1)(b) | + 12 months | Yes | Yes |
| 11 | `case_outcomes.closed_by_user_id` (FK to HR user) | Direct (HR user) | No | Art. 6(1)(b) | + 36 months (HR user retention) | Yes (Art. 17 for the HR user) | Yes |
| 12 | `case_outcomes.failure_reason` (enum, if rejected) | No | Indirect | Art. 6(1)(b) | + 6 years | No | Yes |

**Total fields catalogued: 12.** All have explicit lawful basis + retention boundary + erasure-overrideability status + subject-access surfaceability.

---

## 4. Lawful basis decisions

### 4.1 Contract performance (Art. 6(1)(b))

The dominant basis. The employee entered into a relocation arrangement via their employer; ReloPass is processing their data to fulfil that arrangement. Survives case closure for the operational 12-month window because:

- Disputes about the outcome may arise post-closure.
- Tax/payroll downstream consumes the outcome state.
- Returning-employee onboarding (within 12 months) re-uses the prior case context.

### 4.2 Legal obligation (Art. 6(1)(c))

Carries the audit-chain fields (case audit events, outcome status, failure reason). EU AI Act Article 12 requires record-keeping of high-risk system outputs. Accounting law (French Code de commerce L123-22) requires 10-year retention of supporting business documents; ReloPass uses 6-year minimum to align with most EU member state tax codes.

### 4.3 Legitimate interest (Art. 6(1)(f))

The analytics-aggregated processing-time field (row 9). LIA (legitimate-interest assessment) on file: necessary for service quality monitoring + AI Act post-market obligations; balanced against minimal identifiability post-aggregation; data subjects can opt out via §6 procedure.

### 4.4 Special-category data handling (Art. 9)

Where rows 7 + 10 + 12 indirectly reveal special-category data (family composition can reveal household, marital, parental status; free-text notes may capture health or religion info), the Art. 9(2)(b) derogation (employment + social security + social protection law) applies. Counsel sign-off: required.

---

## 5. Subject access right (Art. 15) — what surfaces in a SAR response

When an employee files a Subject Access Request, the response must include:

- All 12 fields above for every case associated with them (current + closed).
- The free-text `case_outcomes.notes` field, with HR-user identifiers redacted unless legal basis to disclose (typically: yes for the employee's own case).
- The pointer to (but not the body of) the audit chain — the employee can request specific audit-event records separately.

**Format**: machine-readable JSON download (Art. 20 portability) + human-readable PDF summary. Templates: see PRIV-001 runbook (in progress).

**SLA**: 1 month from request per Art. 12(3); extendable by 2 months for complex cases with notification within the initial month.

---

## 6. Rectification (Art. 16)

The employee can request correction of:

- Their own profile data (corrected directly via Pathway, no formal request needed).
- Their case-outcome notes if factually incorrect (request handled by HR user — see PRIV-001 §5).

Corrections are logged with `corrected_by_user_id` + `correction_reason` + `corrected_at` in an audit event. The original value is preserved in the audit chain (necessary for Art. 12 audit integrity) but the customer-facing field shows the corrected value.

---

## 7. Erasure (Art. 17)

See PRIV-001 erasure runbook. Summary for case outcomes:

- **Erasable** (per request): fields marked "Yes" in the "Erasure-overrideable?" column. On erasure, the underlying values are deleted; the audit chain entries are pseudonymised (employee_id replaced with a stable hash, free text deleted).
- **Not erasable** (Art. 17(3)(b) exception): audit-required fields (corridor, pathway_type, outcome_status, failure_reason, processing_days). These are retained for the full audit retention period.

The employee is informed in writing at the point of erasure of which fields were deleted and which were retained under the audit obligation.

---

## 8. Restriction of processing (Art. 18)

Available where the employee contests data accuracy or processing lawfulness. Implementation: a `restricted_at` timestamp + `restriction_reason` on `cases`. Restricted cases are flagged in HR UI as read-only pending resolution. Audit chain continues to record; downstream form-fill is paused.

---

## 9. Right to object (Art. 21)

Specifically applicable to:

- Processing under legitimate-interest basis (the analytics-aggregated processing-time field). Objection is logged and that field is excluded from aggregate analytics for the objecting subject.

Not applicable to:

- Processing under contract-performance basis (case operational data).
- Processing under legal-obligation basis (audit chain).

---

## 10. International transfers (Art. 44-49)

The case-outcome data resides in EU (Supabase eu-west-1). It is **not transferred outside EU/EEA** for retention purposes. Per-call AI inference touches model providers per Annex IV §6 — out of scope of this case-outcome doc.

---

## 11. DPIA reference (Art. 35)

The processing described here is part of the wider ReloPass DPIA (PRIV-006 — to be filed if it doesn't exist; otherwise referenced from `audit/dpia/relopass_dpia_v1.md`). High-level risks affecting case outcomes: re-identification via outcome metadata (low — corridor + pathway are coarse), discrimination via aggregate analytics (mitigated per AI-006 R-BIAS-* risks).

---

## 12. Records of processing (Art. 30) — entry

This processing activity is recorded in ReloPass's Art. 30 RoPA register:

```
Processing activity:  Case-outcome retention + analytics
Controller:           Customer (HR org); ReloPass as processor
Purpose:              Performance of relocation contract; AI Act + accounting compliance
Categories of data:   See §3 above
Categories of subjects: Employees relocated via ReloPass; HR users
Recipients:           ReloPass internal staff (read), customer HR users (read), no external
International transfers: None for retention; per-inference per Annex IV §6
Retention:            Per §3 (12 months operational + 6 years audit)
Security measures:    RLS, EU residency, encryption at rest, audit logging
```

---

## 13. Engineering checklist (gates code before merge)

Before any code that touches case outcomes merges to main, verify:

- [ ] Field added/changed appears in §3 table.
- [ ] Lawful basis stated.
- [ ] Retention boundary defined.
- [ ] Erasure-overrideability tagged.
- [ ] Subject-access surfaceability tagged.
- [ ] PRIV-003 retention SQL stub written (or pointed to an existing stub).
- [ ] If special category: Art. 9 derogation cited.
- [ ] If new field is free-text: PII risk noted + erasure path defined.

CI integration: a markdown linter could enforce §3 row count matches the schema column count of `case_outcomes` (low priority follow-up).

---

## 14. Validation against AIQ-688 criteria

- ✅ **Criterion: Markdown file produced at the requested location** — `docs/case_outcomes_gdpr.md` (this file at `outputs/p1-07e_case_outcomes_gdpr.md`, ready for move to repo).
- ✅ **Criterion: Legal basis per field** — §3 column "Lawful basis"; §4 explanation.
- ✅ **Criterion: Retention period per field** — §3 column "Retention".
- ✅ **Criterion: Subject access procedure** — §5.
- ✅ **Criterion: Cross-references retention policy** — §1, §3, §7 cross-link to PRIV-003.

---

## 15. Known gaps

- ⚠ **Schema confirmation** — §3 assumes a `case_outcomes` table or analogous columns on `cases`. Engineer should verify the actual schema and update §3 if column names differ.
- ⚠ **Free-text PII scrubber** — row 10 (free-text notes) carries the highest PII drift risk. Recommend adding an inline PII detector (regex pass + LLM-confirm) on save, with HR-user warning if PII patterns detected.
- ⚠ **Backup retention** — same gap as PRIV-003 §10. PITR window may extend retention de facto.

---

## 16. Document metadata

- **Version**: v1.0.
- **Generated**: 2026-06-03.
- **Generator**: Claude Cowork via notion-task-executor.
- **Source materials**: GDPR Articles 5, 6, 9, 12-23, 30, 35; PRIV-003 retention policy; AI-003 Annex IV §2.4; AI-006 risk register.
- **Target location**: `docs/case_outcomes_gdpr.md` (move from `outputs/`).
- **Next planned revision**: v1.1 after schema reconciliation + counsel review.

---

*Generated 2026-06-03 by Claude Cowork via notion-task-executor. Companion doc to PRIV-003 retention policy. Case-outcome data is the heaviest-weight GDPR slice; this file is its compliance checklist.*
