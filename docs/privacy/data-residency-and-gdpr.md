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
| Relational rows (cases, assignments, profiles, policies) | Supabase Postgres       | Configured per Supabase project — check dashboard → Settings → General |
| Document uploads (passports, policy PDFs)                | Supabase Storage — bucket `hr-policies`, `employee-uploads` | Same region as Postgres |
| Session tokens                      | Same Postgres DB (`sessions` table) | Same region                                     |
| Audit log                           | Same Postgres DB (`audit_logs` table) | Same region                                  |
| Logs                                | Render platform logs               | US (Render default region unless configured otherwise) |
| LLM processing (policy extraction, policy Q&A) | OpenAI API             | US (OpenAI infra)                               |

**Important**: confirm the Supabase project region matches the compliance requirements of the EU customers you onboard. For customers with strict EU-data-residency requirements, provision a separate Supabase project in `eu-central-1` / `eu-west-1` and point the backend at it via `SUPABASE_URL` + `DATABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`.

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
