# PRIV-003 · Data Retention Policy v1 · ReloPass

**Task**: AIQ-471 · PRIV-003
**Author**: Claude Cowork via notion-task-executor
**Date**: 2026-06-03
**Owner**: Romain (CTO + acting DPO) — must approve schedule before any code ships
**Regulation reference**: GDPR Articles 5(1)(e) storage limitation + 17 right to erasure; EU AI Act Articles 10 + 12 (data governance + record-keeping)
**Cross-references**: AI-003 Annex IV §2.4 (data lifecycle); AI-006 risk register R-PII-* + R-SUBJECT-01; AI-004 traceability matrix (Art. 10)
**Document status**: v1 — policy doc gating PRIV-001 (erasure) and PRIV-002 (audit log) implementation. Once approved, pg_cron SQL implementation can ship.

---

## 1. Purpose and scope

This policy defines, per table or data class, how long ReloPass retains personal data and what happens at the end of the retention period. It serves three audiences:

- **Engineers** building the automated enforcement (pg_cron + soft-delete + anonymisation pipelines).
- **Auditors / counsel** asking "show me your retention schedule" during a procurement or regulator review.
- **HR users (deployers)** who need to answer their own employees' questions about how long ReloPass keeps their data.

Scope: all personal data processed by ReloPass (both employee and HR-user identities). Out of scope: aggregated/anonymised analytics data (governed separately under §6).

---

## 2. Retention principles (GDPR Art. 5(1)(e))

1. **Lawful basis drives retention**. Data retained under a contract-performance basis is kept only as long as the contract requires; data retained under a legal-obligation basis is kept for the period mandated by the relevant statute.
2. **Active case duration is the unit**. Most operational data is retained for the duration of the active relocation case PLUS a defined post-case window (typically 12 months for operational continuity + dispute resolution).
3. **Audit records have longer retention** to satisfy AI Act Article 12 (high-risk system log retention obligations) and accounting law (6-year tax/business records).
4. **Deletion is the default**. At end of retention, records are deleted unless explicitly listed for anonymisation (rare).
5. **Anonymisation** (not pseudonymisation) is reserved for cases where aggregate analysis must survive a retention boundary — see §6.
6. **Right-to-erasure overrides** the schedule for valid Art. 17 requests, with the documented exceptions in §7.

---

## 3. Retention schedule — by table

Format per row: data class → table(s) → trigger that starts the clock → retention period → end-of-retention action → lawful basis. **Romain must approve every row before code ships.**

### 3.1 Operational personal data (employee + HR user identifiers)

| # | Data class | Tables | Trigger | Retention | EoR action | Lawful basis |
|---|---|---|---|---|---|---|
| 1 | Employee profile data (name, DOB, contact) | `employees`, `profiles` (where role = 'EMPLOYEE') | Case `closed_at` | + 12 months | Delete row + cascade | GDPR Art. 6(1)(b) contract performance |
| 2 | HR user profile data | `profiles` (where role IN ('HR_AGENT','HR_LEAD','ADMIN')) | Last activity timestamp | + 36 months | Delete row | Art. 6(1)(b) contract; Art. 6(1)(f) legitimate-interest for resigned-user account recovery |
| 3 | Employee uploaded documents (passport, contract, certs) | `case_documents` + Supabase storage objects | Case `closed_at` | + 12 months | Delete blob + delete row | Art. 6(1)(b) + Art. 9(2)(b) employment law derogation |
| 4 | Extracted document fields (OCR + LLM outputs) | `case_form_field_values`, `case_dossier_packages` | Case `closed_at` | + 12 months | Delete row | Art. 6(1)(b) |
| 5 | Family member data (spouse + dependants) | `case_family_members` | Case `closed_at` | + 12 months | Delete row | Art. 6(1)(b) + Art. 9(2)(b) |
| 6 | Pet data | `pets`, `pet_import_rules` (case-scoped) | Case `closed_at` | + 12 months | Delete row | Art. 6(1)(b) |
| 7 | Pathway session state | `pathway_sessions`, `pathway_answers` | Session expiry | + 90 days | Delete row | Art. 6(1)(b) |

### 3.2 Audit, oversight + AI-system records (longer retention)

| # | Data class | Tables | Trigger | Retention | EoR action | Lawful basis |
|---|---|---|---|---|---|---|
| 8 | Case-level audit events | `case_audit_events` | Case `closed_at` | + 6 years | Delete row | Art. 6(1)(c) legal obligation (AI Act Art. 12 + accounting law) |
| 9 | AI extraction / classification runs | `agent_runs` | Run `created_at` | + 6 months minimum (AI Act Art. 19); 6 years if linked to a case-audit-event | Delete row | Art. 6(1)(c) |
| 10 | Rule citation chain | `rce.rule_citations` | Citation `created_at` | + 6 years | Delete row | Art. 6(1)(c) (Art. 12 audit trail) |
| 11 | OCR shadow comparisons | `ocr_shadow_comparisons` | Run `created_at` | + 12 months | Aggregate counts then delete row | Art. 6(1)(f) AI-quality monitoring |
| 12 | Human feedback / corrections | `ai_human_feedback` | Feedback `created_at` | + 24 months | Aggregate counts then delete row | Art. 6(1)(f) AI-quality improvement |
| 13 | Exception requests | `exception_requests`, `specialist_review_events`, `roadmap_review_status` | Resolution `resolved_at` | + 6 years | Delete row | Art. 6(1)(c) AI Act Art. 12 |

### 3.3 Communications + support

| # | Data class | Tables | Trigger | Retention | EoR action | Lawful basis |
|---|---|---|---|---|---|---|
| 14 | Email / message logs to employees | `case_messages`, `email_log` | Message `sent_at` | + 24 months | Delete row | Art. 6(1)(f) + Art. 6(1)(b) |
| 15 | Support tickets + tagged transcripts | `support_tickets` | Ticket `closed_at` | + 24 months | Delete row | Art. 6(1)(f) |
| 16 | Provider RFQ + quote requests | `quote_requests` (decision deferred per Option-2 MVP — table may not ship MVP) | Request `created_at` | + 24 months | Delete row | Art. 6(1)(b) |

### 3.4 Account + access security data

| # | Data class | Tables | Trigger | Retention | EoR action | Lawful basis |
|---|---|---|---|---|---|---|
| 17 | Supabase Auth sessions | `auth.sessions` | Session expiry | Supabase default (30 days) | Auto-delete by Supabase | Art. 6(1)(b) |
| 18 | Login + auth audit events | `error_logs` (auth subset), Supabase Auth audit | Event `created_at` | + 12 months | Delete row | Art. 6(1)(f) + Art. 6(1)(c) breach-detection |
| 19 | Failed login + lockout records | Within Supabase Auth | Per Supabase Auth retention | Supabase default | Auto | Art. 6(1)(f) |

### 3.5 Aggregate + telemetry (anonymised at intake — no PII retention)

| # | Data class | Tables | Trigger | Retention | EoR action | Lawful basis |
|---|---|---|---|---|---|---|
| 20 | Page-view + product-usage analytics | `error_tickets` (telemetry) + product analytics provider | Event `created_at` | Indefinite (anonymised at intake) | N/A | n/a |
| 21 | Cost telemetry (`ai_unit_economics`) | `ai_unit_economics` | Event `created_at` | + 36 months | Delete row | Art. 6(1)(f) |
| 22 | Spend approvals | `ai_spend_requests` | Approval `created_at` | + 6 years | Delete row | Art. 6(1)(c) accounting |

### 3.6 Provider-side data

For data held by sub-processors (Mistral DI, Azure DI, Anthropic, OpenAI, Supabase, Render, Cloudflare), ReloPass requires zero-data-retention on the inference path where the provider offers it, and minimum-necessary retention everywhere else. Verification: PRIV-004 + Annex IV §6 attestation gap.

---

## 4. End-of-retention enforcement (engineering spec)

### 4.1 Mechanism

Use **pg_cron** scheduled jobs in Supabase to enforce the schedule. One job per data class, runs daily at 03:00 UTC (off-peak EU + US west). Each job:

1. Identifies rows whose retention period has expired (`trigger_timestamp + retention_interval < now()`).
2. Logs a "retention enforcement run" row to `audit.retention_runs` with count + table + action.
3. Executes the EoR action (delete or anonymise).
4. Emits a structured log line + metric to observability (CloudWatch / Sentry tag).

### 4.2 Reference SQL stub (for engineer to fold into pg_cron)

```sql
-- Example: row 1, employee profile data
SELECT cron.schedule(
  'retention-employees-12mo',
  '0 3 * * *',  -- daily 03:00 UTC
  $$
  WITH deleted AS (
    DELETE FROM public.employees e
    USING public.cases c
    WHERE e.case_id = c.id
      AND c.closed_at IS NOT NULL
      AND c.closed_at < (NOW() - INTERVAL '12 months')
    RETURNING e.id, e.case_id
  )
  INSERT INTO audit.retention_runs(table_name, action, row_count, run_at)
  SELECT 'employees', 'delete', COUNT(*), NOW() FROM deleted;
  $$
);
```

Repeat per schedule row, parameterising:
- `table_name`
- `trigger_column` (e.g., `c.closed_at`)
- `retention_interval`
- `action` (`delete` or `anonymise`)

### 4.3 Soft-delete vs hard-delete decision

- **Soft-delete (set `deleted_at`)** for active operational tables that may be touched by foreign keys. Cascade hard-delete after a 7-day grace window (recovery from accidental triggers).
- **Hard-delete** for audit + system tables where the retention period itself is the only allowed lifetime.

### 4.4 Test plan

- **Unit**: each cron job tested against a fixture row with a contrived `trigger_timestamp` past the retention boundary; assert deletion + audit row.
- **Integration**: end-to-end on a staging case that is closed and rewind-aged to exceed retention; assert all 17+ tables' rows for that case are removed.
- **Observability**: `audit.retention_runs` count is non-zero on every job-day; alert fires if a job logs zero deletes when historically it deletes >0.

---

## 5. Right-to-erasure interplay (Art. 17)

This policy describes the **default** retention schedule. A valid Art. 17 erasure request **overrides** the schedule for the affected data subject, subject to the exceptions documented in PRIV-001:

- Audit records linked to the data subject's case are retained per row 8 above for the full 6-year period, even if the employee requests erasure, because the AI Act Art. 12 record-keeping obligation is a legal-basis exception under Art. 17(3)(b).
- Records pseudonymised in audit logs (employee identifier replaced with a stable hash) are not considered personal data and are retained without separate erasure.
- See PRIV-001 erasure runbook for the operational procedure.

---

## 6. Anonymisation as an alternative to deletion

Used sparingly — when aggregate analysis (e.g., per-origin accuracy in risk register R-BIAS-01) must survive a retention boundary. The anonymisation process:

1. Replace direct identifiers (name, email, employee_id, case_id) with stable hashes salted with a key NOT stored alongside the data.
2. Drop indirect identifiers (free-text fields, addresses) where retention isn't necessary for the aggregate.
3. Generalise quasi-identifiers (date of birth → year of birth; address → country only).
4. Document the anonymisation transformation in `audit/anonymisation/<table>_<date>.md`.

Tables currently scheduled for anonymisation (not deletion):
- `ocr_shadow_comparisons` row 11 — keep model id + agreement flag, drop document text + bbox values.
- `ai_human_feedback` row 12 — keep extractor id + correction-type flag, drop original + corrected values.

All other tables in §3 are scheduled for **deletion**, not anonymisation.

---

## 7. Out-of-cycle deletion triggers

The retention schedule is the default. Deletion happens **earlier than the schedule** when:

| Trigger | Effect |
|---|---|
| Valid GDPR Art. 17 erasure request from data subject | Per PRIV-001 runbook |
| Tenant offboards (HR customer cancels) | Per offboarding runbook — see §10 gap |
| Court order | Per legal counsel guidance |
| Discovered breach (data needs containment) | Per incident response runbook (Annex IV §8 gap) |

Deletion does NOT happen earlier than the schedule when:

| Trigger | Effect |
|---|---|
| Customer ad-hoc request to "clean things up" | Refuse — schedule governs |
| Engineer convenience (e.g., "we want a smaller backup") | Refuse |
| Bug suspected in row | Refuse — bug should be triaged, not data deleted |

---

## 8. Approval workflow

This policy goes through a single-pass approval before any code ships:

1. **Romain (acting DPO)** reviews row-by-row and either:
   - ✅ Approves the row as-is.
   - ✏️ Edits the row (new retention period, new EoR action, new lawful basis).
   - ❌ Rejects the row (data class doesn't exist or shouldn't be retained at all).
2. **External counsel** reviews the approved schedule against current GDPR + AI Act guidance. Counsel signs off in §11 below.
3. **Engineering** implements §4 pg_cron jobs against the approved schedule.
4. **Romain** verifies a staging dry-run before production deploy.

Approval row tracker (Romain fills in):

```
Row  | Decision (✅/✏️/❌) | Edits if any                 | Date
-----|--------------------|------------------------------|------
1    | _                  |                              |
2    | _                  |                              |
...  | _                  |                              |
22   | _                  |                              |

Counsel approval: ____  Date: ____
```

---

## 9. Customer-facing summary (privacy notice extract)

This text feeds into PRIV-005 (privacy notice at point of collection):

> *We keep your data only as long as we need to. Active case data is retained while your relocation is in progress and for 12 months after the case closes. Audit records — proof that we followed the rules — are kept for 6 years to meet our legal obligations under the EU AI Act and accounting law. You can ask us to delete your data at any time using the request form below, except where law requires us to keep audit records.*

---

## 10. Known gaps

- ⚠ **Tenant offboarding runbook** — what happens when an HR customer cancels: extension of retention for in-flight cases? Bulk deletion of company-scoped data? Define + ship before first customer churn.
- ⚠ **Backup retention policy** — Supabase point-in-time recovery has its own retention window (typically 7-30 days). Document this in §3 as an honest carve-out: deleted data may persist in PITR for the backup window. Counsel should review whether GDPR Art. 17 obligates earlier PITR purge.
- ⚠ **PII inventory cross-check** — confirm every table in §3 against a PII inventory (feeds PRIV-001 deliverable).
- ⚠ **Sub-processor retention attestations** — PRIV-004 must capture, per provider, what the provider retains and for how long.

---

## 11. Approval log

```
Drafted by Claude Cowork on 2026-06-03 (this document, v1).

Romain (DPO) approval:    ____  Date: ____  Notes: ____
External counsel approval: ____  Date: ____  Notes: ____
First pg_cron job deployed: ____  Date: ____  Owner: ____
First staging dry-run audit: ____  Date: ____  Result: ____
First production deploy:   ____  Date: ____  Result: ____
```

---

## 12. Validation against AIQ-471 criteria

- ✅ **Criterion: Retention schedule (per data class / per table) drafted** — 22 rows in §3 covering all major operational + audit + comms + security + analytics + accounting tables.
- ✅ **Criterion: Trigger + period + action + lawful basis per row** — column structure of §3 enforces this for every row.
- ⚠ **Criterion: Schedule approved by Romain** — explicitly out of scope for this v1 draft. Approval workflow defined in §8.
- ✅ **Criterion: pg_cron implementation pattern documented** — §4 with reference SQL stub.
- ✅ **Criterion: Cross-references PRIV-001 erasure + PRIV-002 audit + PRIV-004 sub-processor + Annex IV §6** — see §1, §5, §6, §10.

---

## 13. Document metadata

- **Version**: v1.0.
- **Generated**: 2026-06-03.
- **Generator**: Claude Cowork via notion-task-executor.
- **Source materials**: GDPR Art. 5(1)(e), 6, 9, 17; AI Act Art. 10, 12, 19, 72; today's ReloPass production schema; AI-003 Annex IV doc; AI-006 risk register.
- **Next planned revision**: v1.1 after Romain row-by-row approval + counsel review.

---

*Generated 2026-06-03 by Claude Cowork via notion-task-executor. Policy gates PRIV-001 (erasure) and PRIV-002 (audit) implementation. Once approved, ship the §4 pg_cron jobs and the schedule becomes operational.*
