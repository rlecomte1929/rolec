# PRIV-001 · Right-to-Erasure Runbook + Anonymisation Strategy v1 · ReloPass

**Task**: AIQ-469 · PRIV-001 (partial — runbook + anonymisation + PII inventory shipped here; API endpoints + UI wiring to be shipped by Claude Code)
**Author**: Claude Cowork via notion-task-executor
**Date**: 2026-06-03
**Owner**: Romain (CTO + acting DPO)
**Regulation reference**: GDPR Articles 17 + 20; EU AI Act Art. 12 (audit retention exception)
**Cross-references**: PRIV-003 retention policy (`outputs/priv-003_data_retention_policy_v1.md`); P1-07e case-outcomes GDPR (`outputs/p1-07e_case_outcomes_gdpr.md`); AI-006 risk register R-SUBJECT-01

---

## 1. Purpose

This runbook tells the on-duty operator (Romain or a designated support engineer) exactly what to do when a GDPR Article 17 erasure request lands. It also documents the **anonymisation strategy** for fields that survive erasure under the Art. 17(3)(b) audit exception, and ships a **PII table inventory** that drives both the erasure procedure and the PRIV-003 retention enforcement.

This document is the **doc-shaped half** of PRIV-001. The remaining half (FastAPI `/api/gdpr/erasure` endpoint, `/api/gdpr/data-export` endpoint, the React confirmation UI, the email-notification cron) requires the codebase and is queued for Claude Code.

---

## 2. Erasure request intake

### 2.1 How requests arrive

| Channel | Who handles it | SLA clock starts |
|---|---|---|
| In-product "Delete my data" button (Pathway) | Auto: triggers API → Romain notified by email | At click |
| Email to `dpo@relopass.com` | Romain | At email receipt |
| Email to `support@relopass.com` (auto-routed to DPO) | Romain | At auto-route |
| Letter to ReloPass SAS registered address | Romain | At letter receipt (date-stamped) |
| Via the customer (HR user forwards employee request) | Romain | At HR-user forward |
| Regulator complaint relayed by CNIL or other authority | Romain + counsel | At authority contact |

### 2.2 Identity verification

Before any data is deleted, verify the requester is who they say they are:

- **In-product** (already authenticated): identity is verified by the active session. Confirm via in-app modal that the user understands the request.
- **Email + offline**: respond with a verification challenge. Acceptable proofs (one of):
  1. Reply from the email address on file in `profiles.email`.
  2. Photo of identity document (matched against the passport on file in `case_documents` if any).
  3. Confirmation from the HR user that the employee was associated with the company.

Document the verification step in the case audit log with timestamp + verification method.

### 2.3 SLA

- **Acknowledge** within 72 hours of receipt (per CNIL guidance).
- **Complete** within 1 month per Art. 12(3); extendable by 2 months for complex cases with notification in the initial month.
- **Notify the requester** in writing of: what was erased, what was retained under audit exception, and the right to lodge a complaint with the supervisory authority.

---

## 3. Procedure — step by step

### 3.1 Open the case file

1. Look up the requester in Notion + Supabase (employee_id + company_id).
2. Open the response template at §6 below.
3. Date-stamp the SLA clock.

### 3.2 Identity verification

Per §2.2. Record method + timestamp.

### 3.3 Scope confirmation

Clarify with the requester what they want erased:

- All their data (most common).
- Specific items (e.g., "delete my last passport upload but keep my profile").
- Specific time range (rare).

Document the scope in the response template.

### 3.4 Determine the audit-exception subset

Pull the PII inventory in §7 below. For each row, check:

- Is the row marked **Erasable**? → erase.
- Is the row marked **Retained under Art. 17(3)(b)**? → anonymise (per §4 strategy) instead of erase; document.
- Is the row marked **Pseudonymised at intake**? → no action needed; explain in response.

### 3.5 Execute deletion

Use the API endpoint (Claude Code task — currently manual):

```bash
# Manual procedure until /api/gdpr/erasure ships
psql "$SUPABASE_DB_URL" <<SQL
BEGIN;
SELECT public.fn_erase_employee_data(
  p_employee_id := '<EMPLOYEE_UUID>',
  p_scope := '<full|partial:json>',
  p_request_id := '<REQUEST_REF>',
  p_operator := '<OPERATOR_EMAIL>'
);
-- inspect output: should return JSON listing erased + retained rows
COMMIT;
SQL
```

Until `fn_erase_employee_data` ships (Claude Code task), use the manual SQL recipes in §8.

### 3.6 Write to audit log

The erasure act itself is a logged event. Record in `case_audit_events`:

```json
{
  "event_type": "gdpr_erasure_executed",
  "request_id": "<ref>",
  "operator": "<email>",
  "scope": "<full|partial>",
  "rows_erased": <int>,
  "rows_retained_audit_exception": <int>,
  "timestamp": "<iso>"
}
```

### 3.7 Notify the requester

Send the §6 response template, completed:

- What was erased (with table-level summary).
- What was retained (with Art. 17(3)(b) audit-exception explanation).
- The right to complain to the CNIL (or relevant authority).
- The link to the data-portability download if requested per Art. 20.

### 3.8 Update Notion

Log the case in a "GDPR Requests" Notion database (TBC — see §10 gap). At minimum: requester, request date, completion date, scope, operator, audit-exception rows retained.

---

## 4. Anonymisation strategy (for rows kept under Art. 17(3)(b) audit exception)

Articles 12 + 19 + 72 of the EU AI Act require retention of audit logs for the operational lifetime + 6 months minimum (and 6 years per accounting law). When an employee is erased, the audit chain referring to them must be **anonymised**, not deleted, to preserve audit integrity.

### 4.1 Anonymisation principle

After anonymisation, **no combination of the retained fields can be used to re-identify** the data subject, even by an internal operator with database access. The transformation must be:

- **Irreversible** — no key kept that could reverse the hash.
- **Stable** — the same employee identifier produces the same anonymised value (so audit chains remain join-able).
- **Locality-preserving for aggregate analysis** — coarse buckets retained where useful (e.g., year of birth instead of date of birth).

### 4.2 Fields to anonymise (per audit chain)

| Source field | Anonymised replacement | Rule |
|---|---|---|
| `employee_id` (UUID) | `anon_employee_hash` = sha256(employee_id ‖ pepper) | Salt stored OUT of the database (env or vault); same employee = same hash |
| `employee.full_name` | NULL | Delete |
| `employee.email` | NULL | Delete |
| `employee.dob` | `birth_year` | Year only retained |
| `employee.home_address` | `country_code_origin` | Country only retained |
| `family_member.full_name` | NULL | Delete |
| `family_member.relationship` | retained (no PII content) | Keep |
| `case.id` (UUID) | retained | Keep — case identifier is system metadata |
| Free-text notes (`case_outcomes.notes`, `audit_events.free_text`) | NULL | Delete |
| Document references (`case_documents.id`) | retained | Keep — but storage blob deleted per PRIV-003 |
| OCR-extracted text values | NULL | Delete (already deleted with the source document per PRIV-003 row 4) |
| `agent_runs.input_hash` | retained | Hash — no PII |

### 4.3 Pepper key management

The pepper used in employee-id hashing:

- Generated once at project start.
- Stored in a secrets vault (e.g., Render env or a dedicated KMS).
- Never logged.
- Never co-located with the hashed values.
- Rotated only on compromise — rotation breaks join-ability across the rotation boundary, so it should be very rare.

### 4.4 Anonymisation SQL pattern (for `fn_erase_employee_data`)

```sql
CREATE OR REPLACE FUNCTION public.fn_erase_employee_data(
  p_employee_id uuid,
  p_scope text DEFAULT 'full',
  p_request_id text DEFAULT NULL,
  p_operator text DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
AS $$
DECLARE
  v_anon_hash text := encode(
    digest(p_employee_id::text || current_setting('app.pii_pepper'), 'sha256'),
    'hex'
  );
  v_summary jsonb := jsonb_build_object();
BEGIN
  -- ERASE: operational data (PRIV-003 §3.1)
  WITH erased AS (
    DELETE FROM public.employees WHERE id = p_employee_id
    RETURNING id
  )
  SELECT v_summary || jsonb_build_object('employees_erased', COUNT(*)) INTO v_summary FROM erased;
  -- … repeat for documents, family_members, case_form_field_values, etc.

  -- ANONYMISE: audit chain (PRIV-003 §3.2)
  UPDATE public.case_audit_events
  SET employee_id_hash = v_anon_hash,
      employee_id = NULL,
      free_text = NULL,
      pii_redacted_at = now()
  WHERE employee_id = p_employee_id;

  UPDATE public.rce.rule_citations
  SET employee_id_hash = v_anon_hash,
      employee_id = NULL,
      pii_redacted_at = now()
  WHERE employee_id = p_employee_id;

  -- AUDIT: log the erasure act itself
  INSERT INTO public.case_audit_events(event_type, request_id, operator, payload)
  VALUES (
    'gdpr_erasure_executed',
    p_request_id,
    p_operator,
    jsonb_build_object('summary', v_summary, 'anon_hash', v_anon_hash)
  );

  RETURN v_summary;
END;
$$;
```

(Stub — to be hardened by Claude Code in implementation.)

---

## 5. PII table inventory (drives both erasure + retention)

This inventory is the source of truth for what data is **about a natural person**. Every table in the public schema is either:

- **Personal data**: directly identifies a person (full_name, email, document content).
- **Indirect personal data**: identifies via linkage (employee_id, case_id when joined).
- **Non-personal data**: system metadata, configs, dictionaries.

Engineers MUST update this inventory when a new table is added.

### 5.1 Personal data tables

| Table | Direct/Indirect | Erasable on Art. 17 | Anonymise instead? | Notes |
|---|---|---|---|---|
| `profiles` | Direct | Yes | No | Source of identity |
| `employees` | Direct | Yes | No | Employee personal data |
| `case_documents` (+ storage blobs) | Direct (document content) | Yes | No | Heavy PII |
| `case_form_field_values` | Direct | Yes | No | Extracted PII |
| `case_family_members` | Direct | Yes | No | Family PII |
| `pets` | Indirect (vet records) | Yes | No | Pet care PII |
| `pathway_sessions` | Indirect | Yes | No | Session state |
| `pathway_answers` | Direct (free text answers) | Yes | No | Heavy PII |
| `email_log` / `case_messages` | Direct (recipient + content) | Yes | No | Communications |
| `support_tickets` | Direct (requester + content) | Yes | No | Comms PII |
| `case_outcomes.notes` | Direct (free text) | Yes | No | Heavy PII |

### 5.2 Audit + AI-system records (retain under Art. 17(3)(b); anonymise)

| Table | Direct/Indirect | Anonymise strategy |
|---|---|---|
| `case_audit_events` | Indirect (employee_id FK) | Replace employee_id with anon_employee_hash; null free_text |
| `rce.rule_citations` | Indirect | Same as above |
| `agent_runs` | Indirect (hash of input) | Already pseudonymous; retain |
| `ocr_shadow_comparisons` | Indirect | Already pseudonymous; retain (until §3.2 row 11 retention expiry) |
| `ai_human_feedback` | Indirect | Aggregate counters only after employee erasure |
| `exception_requests` | Indirect | Anonymise per §4.2 |

### 5.3 Non-personal (system / metadata) tables

| Table | Why non-personal |
|---|---|
| `companies` (legal entity data only) | Legal entity ≠ natural person |
| `form_templates`, `requirement_items`, `requirements_catalog` | Catalog / template, no PII |
| `prompt_versions`, `prompt_routing` | AI infra config |
| `ai_model_energy_profiles`, `ai_unit_economics` | Cost telemetry |
| `country_*` tables | Public reference data |
| `default_policy_templates`, `readiness_templates*` | Catalog |
| `published_*` views | Filtered public data |
| `translation_cache` | Pseudonymised cache |
| `error_logs`, `error_tickets` | Operational logs — should be PII-stripped at write time (current gap — confirm) |

---

## 6. Response template (to send the requester)

```
Subject: Your data erasure request — confirmation

Dear [Name],

We have completed your request, received on [date], to erase your personal data
held by ReloPass. This message confirms what was done and what was retained.

WHAT WE ERASED
─────────────
- Your profile (name, email, contact details)
- All documents you uploaded (passports, contracts, certificates, etc.)
- All extracted values from those documents
- All family-member information you provided
- All free-text notes about your case
- All session data from your Pathway workspace

WHAT WE RETAINED, AND WHY
────────────────────────
The EU AI Act (Article 12) requires us to keep an audit trail of how our AI
system processed information about each case, for six years from case closure.
This retention is the limited exception allowed under GDPR Article 17(3)(b)
(processing for compliance with a legal obligation).

We retained the following, ANONYMISED so that you cannot be re-identified
from it:
- The fact that a case existed in your country corridor
- The pathway type (e.g., Skilled Worker)
- The outcome of the case (approved / rejected / withdrawn)
- The dates and durations of the case
- An anonymous identifier derived from a one-way hash of your employee ID

These records cannot be used to identify you.

YOUR RIGHTS
───────────
You have the right to lodge a complaint with a data protection authority. In
France, this is the Commission Nationale de l'Informatique et des Libertés
(CNIL) at https://www.cnil.fr/.

If you would like a copy of the data we held before erasure, please reply to
this email and we will send you the export within the original SLA window.

OPERATOR + AUDIT
───────────────
Erasure executed by: [operator email]
Request reference:   [ref]
Executed at:         [iso timestamp]
Audit event id:      [uuid]

Best regards,
The ReloPass team
dpo@relopass.com
```

---

## 7. Edge cases

| Case | Handling |
|---|---|
| Employee is mid-case (active relocation) | Confirm scope: erasure during an active case will likely terminate the relocation. Get explicit confirmation in writing. |
| Employee is a former employee of a former customer (company churned) | Same procedure; identity verification may take longer. |
| Multiple cases under same employee (rare — returning relocations) | Erase all cases unless scope limits to one. |
| HR user requests erasure of an employee's data | Refuse — only the data subject themselves can exercise Art. 17. Redirect HR user to the employee or to a documented "tenant offboarding" procedure (PRIV-003 §10 gap). |
| Employee requests erasure of HR user's data referenced in their case | Refuse — the HR user is also a data subject with their own rights; erase the employee's data only. |
| Court order to retain (e.g., active litigation) | Halt erasure; preserve under legal hold; notify counsel. |
| Spam / impersonation suspected | Decline pending stronger identity verification. |
| Erasure SQL fails partway through | The function runs in a transaction; on failure, all changes roll back. Re-run after diagnosis. |

---

## 8. Manual SQL recipes (until `/api/gdpr/erasure` ships)

```sql
-- 1. Inspect what would be erased before doing it
SELECT 'employees' AS t, COUNT(*) FROM public.employees WHERE id = '<UUID>'
UNION ALL SELECT 'case_documents', COUNT(*) FROM public.case_documents WHERE employee_id = '<UUID>'
UNION ALL SELECT 'case_family_members', COUNT(*) FROM public.case_family_members WHERE employee_id = '<UUID>'
UNION ALL SELECT 'pathway_sessions', COUNT(*) FROM public.pathway_sessions WHERE employee_id = '<UUID>'
-- … etc per §5.1
;

-- 2. Run erasure in a single transaction
BEGIN;
DELETE FROM public.pathway_sessions WHERE employee_id = '<UUID>';
DELETE FROM public.case_family_members WHERE employee_id = '<UUID>';
DELETE FROM public.case_form_field_values WHERE case_id IN (SELECT id FROM public.cases WHERE employee_id = '<UUID>');
-- … etc
DELETE FROM public.employees WHERE id = '<UUID>';

-- 3. Anonymise audit chain
UPDATE public.case_audit_events
SET employee_id_hash = encode(digest('<UUID>' || current_setting('app.pii_pepper'), 'sha256'), 'hex'),
    employee_id = NULL,
    free_text = NULL,
    pii_redacted_at = now()
WHERE employee_id = '<UUID>';

UPDATE public.rce.rule_citations
SET employee_id_hash = encode(digest('<UUID>' || current_setting('app.pii_pepper'), 'sha256'), 'hex'),
    employee_id = NULL,
    pii_redacted_at = now()
WHERE employee_id = '<UUID>';

-- 4. Log the erasure
INSERT INTO public.case_audit_events(event_type, payload)
VALUES ('gdpr_erasure_executed', jsonb_build_object('subject_uuid_hash', '<HASH>', 'operator', '<EMAIL>'));

COMMIT;
```

---

## 9. Validation against AIQ-469 criteria (PRIV-001 partial — Cowork half)

- ✅ **Criterion: Internal runbook documenting how to handle a manual erasure request received outside the API** — §3 procedure + §8 manual SQL.
- ✅ **Criterion: Anonymisation strategy document** — §4.
- ✅ **Criterion: PII table inventory** — §5.
- ⚠ **Criterion: FastAPI `/api/gdpr/erasure` endpoint** — out of scope; ships in Claude Code follow-up.
- ⚠ **Criterion: FastAPI `/api/gdpr/data-export` endpoint** — out of scope; ships in Claude Code follow-up.
- ⚠ **Criterion: React UI for "Delete my data" button in Pathway** — out of scope; ships in Claude Code follow-up.

**Recommendation**: mark PRIV-001 in Notion as **Validation** rather than Done — the doc half is complete, the code half waits for Claude Code.

---

## 10. Known gaps

- ⚠ **GDPR Requests Notion database** — set up a simple database to track every Art. 15-22 request received.
- ⚠ **`fn_erase_employee_data` function** — to be implemented in Supabase (Claude Code task).
- ⚠ **`/api/gdpr/erasure` + `/api/gdpr/data-export` endpoints** — Claude Code task.
- ⚠ **React "Delete my data" UI** — Claude Code task.
- ⚠ **PII inventory drift** — needs CI gate or quarterly audit to prevent §5 from going stale.
- ⚠ **Tenant offboarding runbook** — referenced from PRIV-003 §10; ship in parallel.

---

## 11. Document metadata

- **Version**: v1.0 (Cowork-deliverable half of PRIV-001).
- **Generated**: 2026-06-03.
- **Generator**: Claude Cowork via notion-task-executor.
- **Source materials**: GDPR Art. 17, 20; AI Act Art. 12, 19, 72; PRIV-003 retention policy; P1-07e GDPR checklist; AI-006 risk register.
- **Next planned revision**: v1.1 after `/api/gdpr/*` endpoints ship (Claude Code) + Romain ops sign-off.

---

*Generated 2026-06-03 by Claude Cowork via notion-task-executor. Doc half of PRIV-001 — runbook, anonymisation strategy, PII inventory shipped. Code half (endpoints + UI) awaits Claude Code session.*

---

## 11. As-built erasure map (code-accurate — 2026-06-09, AIQ-469 / PRIV-001b)

The export (`GET /api/users/{id}/data-export`) and erasure (`DELETE /api/users/{id}/data`)
endpoints shipped in `backend/app/routers/gdpr.py` (PRs #545 + erasure follow-up). The
endpoint operates in Python (per-table `SAVEPOINT`, fail-soft) rather than the §4.4
`fn_erase_employee_data` SQL stub, because that stub assumed a pepper and tables that do
**not** exist in prod.

**Inventory correction.** The §5/§7 inventory referenced 6 tables that do not exist in the
prod `public` schema and were dropped from the erasure surface: `case_audit_events`,
`case_family_members`, `case_outcomes`, `email_log`, `pathway_sessions`, `pathway_answers`.
The verified live surface is the 17 tables below.

**Anonymisation choice (pre-launch).** Null-only / soft, not pepper-hashed (Romain, 2026-06-09).
PII columns are set to `NULL` and operational rows hard-deleted; opaque UUIDs left in
accountability tables no longer resolve to a person once `profiles`/`employees` are erased.
Pepper-based stable hashing (§4.2/§4.3) is a deferred refinement for when audit-chain
analytics need to survive erasure.

| Table | Action | Detail |
|---|---|---|
| `employees`, `employee_tasks`, `quote_requests`, `case_documents`, `case_forms`, `pets` | **hard-delete** | Operational data, no retention obligation |
| `case_messages` | **hard-delete (authored)** | Only rows where `sender_id` = subject |
| `profiles` | anonymise | NULL `email`, `full_name`, `avatar_url` |
| `cases` | anonymise | NULL `intake_data`, `notes` |
| `relocation_cases` | anonymise | NULL `profile_json` |
| `case_assignments` | anonymise | NULL names, `employee_identifier`, `hr_notes`, `intake_draft`, `employee_contact_id` |
| `imm_employee_profiles` | anonymise | NULL the passport/DOB/salary/spouse/dependents block + `field_sources`/`field_conflicts`; stamp `anonymised_at = now()` |
| `support_tickets` | anonymise | NULL `from_email`, `from_name`, `subject`, `raw_content`, `html_content` |
| `exception_requests` | anonymise | NULL `reason`, `resolution_notes`, `ai_insight` |
| `consent_records` | **retain**, null network PII | Keep consent proof; NULL `ip_address`, `user_agent` |
| `data_access_log` | **retain**, null network PII | AI Act Art. 12 audit log; NULL `ip_address` |
| `erasure_requests` | **retain + fulfil** | Compliance record; mark subject's open requests `completed` |

**Supabase `auth.users`** is deleted **last**, outside the DB transaction, via the
service-role admin client (`_call_with_timeout(client.auth.admin.delete_user, id)`),
fail-soft so a wedged GoTrue cannot roll back the committed app-data erasure.

**Known limitations (follow-ups):**
- Storage blobs behind `case_documents` / `case_forms` (Supabase Storage) are not purged by
  the SQL path — needs a storage-API sweep (separate task).
- HR-authored `case_messages` referencing the subject are retained (erasing another data
  subject's records is out of scope); only subject-authored messages are removed.
- Point-in-time-recovery backups retain erased rows for the PITR window (see PRIV-003 §10).
