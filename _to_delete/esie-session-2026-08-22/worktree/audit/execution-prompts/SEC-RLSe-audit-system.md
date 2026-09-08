# Execution Prompt — SEC-RLSe · RLS for Audit / System-Only Tables

**Notion:** AIQ-662 — `https://www.notion.so/370887c64d48819cbb18c1010064d5f3`
**Parent sprint:** AIQ-649. Parallel with SEC-RLSa/b/c/d; SEC-RLSf closes.
**Priority:** **P0** · **Complexity:** Medium · **Branch:** `audit/stage-1-rls-e-audit-system`

## Role
Backend engineer. You triage tables that are server-write-only / system-internal: they don't need tenant-scoped policies, but they DO need an explicit allowlist comment so the CI gate stops being a "this is policy-less and we shrugged" pile.

## Read first
- `supabase/rls_allowlist.txt` — the source. Identify server-only tables.
- `scripts/check_rls_coverage.py` — CI gate; tables with policies or allowlisted-with-reason both pass.
- The backend services that write each table (helps justify the comment).

## Tables in scope (triage from rls_allowlist.txt — verify each)
Likely candidates (server-write-only; never exposed to anon or authenticated clients):
- Audit / event tables: `audit_log`, `audit_logs`, `assignment_audit_log`, `staging_review_audit_log`, `canonical_policy_query_audit_logs`, `policy_benefit_rule_hr_override_audit`, `policy_assistant_answer_audits`
- Background-job state: `crawl_runs`, `crawl_schedules`, `crawl_job_runs`, `crawled_source_chunks`, `crawled_source_documents`, `source_records`, `research_source_candidates`, `staged_event_candidates`, `staged_resource_candidates`, `knowledge_doc_ingest_jobs`, `policy_processing_runs`, `policy_extraction_locks`, `relocation_runs`, `form_prefill_instances`, `requirement_research_jobs`, `roadmap_gap_questions`, `roadmap_generation_jobs`, `freshness_alerts`, `freshness_snapshots`, `document_change_events`
- Error reporting: `error_logs`, `error_tickets`, `support_case_notes`
- Notifications / outbox: `notification_outbox`, `ops_notification_events`, `collaboration_notifications`
- Sessions / admin: `admin_allowlist`, `admin_sessions`, `sessions`, `analytics_events`
- Demo / prospect: `demo_request_rate_limits`, `demo_requests`, `prospect_candidates`
- Review queue: `review_queue_activity_log`, `review_queue_items`

**Triage rule (per table):**
1. Does the frontend (anon or authenticated) ever read this table directly via Supabase JS? → If yes, it doesn't belong here; bump to SEC-RLSa or b.
2. Is it written exclusively by the backend (service_role) and never by clients? → Keep on allowlist; add `# reason` comment.
3. Is it readable by admin only via PostgREST as part of an admin tool? → Add a SELECT policy gated on `admin_allowlist`, and remove from allowlist.

## Two output paths per table

### Path A — keep on allowlist with reason comment
Add a `# reason` comment to the line. Comments live ON THE SAME LINE as the table name, after `#`. The parser already supports this (see allowlist header).

Example:
```
audit_logs                # server-role only — written by FastAPI middleware, never read by client
admin_sessions            # server-role only — session table, FastAPI maintains
ops_notification_events   # server-role only — webhook outbox, drained by background worker
```

### Path B — promote to a real policy
If the table is readable by admin tooling via PostgREST, ship a migration:
```sql
ALTER TABLE public.<table> ENABLE ROW LEVEL SECURITY;

CREATE POLICY "<table>_admin_select" ON public.<table>
  FOR SELECT TO authenticated
  USING (auth.uid() IN (SELECT user_id FROM public.admin_allowlist));

REVOKE ALL ON public.<table> FROM anon;
```
Then remove the line from `rls_allowlist.txt`.

## Allowlist hygiene
For tables you keep on the allowlist:
- One reason per line.
- Reason format: `# <category> — <one-line justification>` (e.g. `# server-role only — outbox drained by background worker`).
- Group lines under section comments (`# ── Audit logs ──`, `# ── Background jobs ──`, etc.) for readability.

This sets up SEC-RLSf, which verifies every retained line has a comment.

## Tests
`backend/tests/integration/test_rls_audit_system_tables.py`:
1. Anon GET on each table → 401 / empty.
2. Authenticated non-admin user GET → 401 / empty.
3. Admin user GET on any table that got a Path-B policy → returns rows.
4. Service-role (backend) writes still work — exercise one INSERT per table category via a fixture using `SUPABASE_SERVICE_ROLE_KEY`.

## Constraints
- Do not give writes to anon or non-admin authenticated users on any table in this group.
- `admin_allowlist` itself: must remain readable to the backend (uses it to authorize admin checks). Add a SELECT policy gated on `service_role` only, OR keep on allowlist with `# server-role only — admin authorization source` reason.
- Migration (if any) is reversible.

## Test commands
```
python scripts/check_rls_coverage.py --allowlist supabase/rls_allowlist.txt
cd backend && pytest backend/tests/integration/test_rls_audit_system_tables.py -v
# Confirm every kept line has a reason:
grep -E "^[a-z_]" supabase/rls_allowlist.txt | grep -v "#" && echo "MISSING REASONS" || echo "all reasoned"
```

## Definition of done
- Every audit/system table is either policy-ized (Path B) or has a `# reason` comment on the allowlist (Path A).
- Tests prove no anon / non-admin read access.
- Service-role write paths unbroken (sample insert per category).
- `check_rls_coverage.py` green.
- Notion AIQ-662 → Human Review with the Path A / Path B breakdown table + allowlist delta in Execution Notes.
- Commit per CLAUDE.md Build Hygiene rules.
