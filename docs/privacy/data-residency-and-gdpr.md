# Data residency, retention, and erasure

Summary of where ReloPass stores user data, how long it keeps it, and how a data-erasure request is processed.

## What PII ReloPass collects

During the employee wizard, ReloPass collects:

- **Step 2 — Employee profile**: full name, nationality, passport country + expiry, residence country, email.
- **Step 3 — Family members**: spouse/child/dependent names, relationship, date of birth, nationalities.
- **Step 4 — Assignment context**: employer, contract type, compensation band.
- **Policy documents**: HR uploads PDF/DOCX policies that typically contain company-internal benefit rules (not employee PII).

Identity documents (passport scans, photos) are uploaded to Supabase Storage and referenced from the relational rows.

## Where data lives

| Data                                | Store                              | Region                                          |
| ----------------------------------- | ---------------------------------- | ----------------------------------------------- |
| Relational rows (cases, assignments, profiles, policies) | Supabase Postgres (project `nsvefcvpvwwwhuqyuqmp`) | **`eu-west-1` (Ireland, EU)** |
| Document uploads (passports, policy PDFs)                | Supabase Storage — buckets `hr-policies`, `employee-uploads` | `eu-west-1` (Ireland, EU) |
| Session tokens                      | Same Postgres DB (`sessions` table) | `eu-west-1`                                      |
| Audit log                           | Same Postgres DB (`audit_logs` table) | `eu-west-1`                                   |
| Logs                                | Render platform logs               | US (Render default region unless configured otherwise) |
| LLM processing (policy extraction, policy Q&A) | OpenAI API             | US (OpenAI infra)                               |

**EU data residency**: employee PII (cases, identity docs, family data) is stored in Supabase's Ireland region, which satisfies GDPR data-residency requirements for EU employees.

**Two non-EU data flows to disclose in a DPA:**
1. **Render platform logs** — request paths, log lines, and any structured log payloads sit in Render's US infrastructure by default. PII is actively redacted from logs (see `backend/services/policy_storage_health.py:_SECRET_PATTERN`) and `send_default_pii=False` on Sentry, but timestamps and user_id fingerprints do cross the Atlantic.
2. **OpenAI API calls** — policy document text (corporate policy content, not employee PII) and policy-assistant query text travel to OpenAI's US endpoints. No passport / nationality / family data is forwarded — see the "What we send to OpenAI" section below.

If an EU customer requires zero non-EU data flow, they must disable LLM features (set `OPENAI_API_KEY=""`) and Sentry (`SENTRY_DSN=""`), and accept degraded platform-log visibility.

## What we send to OpenAI

Two and only two call sites in the backend send data to OpenAI:

1. `backend/services/policy_canonical_extraction.py` — sends **chunks of the uploaded policy document text** to GPT for structured fact extraction. Employee PII is *not* sent by this path; policies are corporate documents.
2. `backend/services/policy_query_answering.py` — sends **the user's policy question** and **retrieved policy context blocks** to GPT. Query text may reference the employee (e.g. "am I eligible for X"). PII is not deliberately forwarded; the retrieved context is policy text only.

No passport numbers, identity photos, date-of-birth, or family data are sent to OpenAI by any code path.

If you need a zero-LLM deployment, set `OPENAI_API_KEY` to an invalid value — the extraction falls back to regex-based parsing and the policy assistant returns a refusal rather than a generated answer.

## Retention

Retention is by soft-delete, not hard-delete. Rows remain in Postgres with `archived_at` set; they're excluded from all HR-facing and employee-facing listings.

- **Active cases**: kept indefinitely while the employee is active.
- **Soft-deleted cases** (HR delete button, admin delete, or erasure request): the case + its assignments have `archived_at` set. A background purge job should run at a minimum cadence of 90 days after `archived_at` to hard-delete. That purge job has **not yet been implemented** — tracked as a follow-up. Until then, "erasure" redacts PII but keeps the row.
- **Audit logs**: retained indefinitely for compliance; no PII is stored in `old_value_json` / `new_value_json` for erasure rows by design.

## Erasure workflow (GDPR Article 17)

An employee or their representative can request erasure of a relocation case via HR:

1. HR identifies the case in `HrCommandCenter` or `AdminCompanyDetail`.
2. HR (or admin) calls `POST /api/hr/cases/{case_id}/erasure`.
3. The endpoint:
   - Verifies the caller belongs to the case's company (or is an admin).
   - Soft-deletes every `case_assignments` row for the case (each writes its own audit row).
   - Soft-deletes the parent `relocation_cases` row.
   - Redacts passport, nationality, DOB, family, addresses, phone, email, and emergency-contact fields in `profile_json` with `[redacted]` markers.
   - Writes an audit row with `action_type='erase'` and the actor's user id.
4. The employee's storage objects (passport scans, etc.) are **not yet automatically purged** — HR must delete them manually from the Supabase Storage bucket. Automated storage cleanup is a tracked follow-up.

## Consent

Consent is captured in the wizard on Step 5 (`frontend/src/pages/employee/wizard/Step5ReviewCreate.tsx`) via a required checkbox. The checkbox is gated on reading the privacy notice; the timestamp + privacy-notice version (`v1-2026-04`) are persisted per-case in browser `localStorage`. If the privacy notice changes materially, bump `PRIVACY_CONSENT_VERSION` and returning users will be re-prompted.

A future iteration should persist consent on the backend (new `case_consents` table or inline on the case) so HR can audit consent timestamps regardless of browser.

## Known gaps (tracked)

1. No scheduled purge job — soft-deleted rows live forever until manually cleaned up.
2. Storage objects (passport scans) not auto-purged on erasure.
3. Consent state lives in localStorage only, not on the server.
4. LLM request/response logs not systematically purged.
5. Backup retention policy for Supabase Postgres — defaults are Supabase-set; confirm with their data-processing agreement and document per-customer if needed.

If you receive a customer data-processing agreement (DPA) request: the Supabase DPA covers the relational and storage layer, OpenAI's API DPA covers LLM calls, Render's DPA covers hosting/logs.
