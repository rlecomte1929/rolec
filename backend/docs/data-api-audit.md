# Supabase Data API Exposure Audit — ReloPass

**Project**: `nsvefcvpvwwwhuqyuqmp` · ReloPass (eu-west-1)
**Audit date**: 2026-06-03
**Task**: FRIDAY-003a (parent: FRIDAY-003 · Supabase Data API audit + opt-out enable)
**Auditor**: Claude Cowork via Supabase MCP
**Source**: `https://supabase.com/changelog/45702-developer-update-may-2026`

---

## Why this audit exists

Supabase changed its default on **May 30, 2026** — new projects ship with the Data API opt-out enabled. ReloPass (created 2026-02-16) pre-dates this change, so every `public` schema table is **still auto-exposed via PostgREST and GraphQL**. This audit determines per-table which exposure must stay (frontend depends on it) and which can be revoked (backend-only access via service_role).

**The win**: revoking unused grants reduces attack surface, strengthens SOC 2 / HR-buyer trust story, and pairs cleanly with the existing RLS hardening work (SEC-002, AUDIT-A3, MVP-9).

---

## Summary

| Classification | Count | Action |
|---|---|---|
| **REVOKE** — backend-only, no frontend direct call | 17 | Migration removes anon + authenticated grants |
| **VERIFY** — need Romain to confirm before deciding | 12 | Open questions below |
| **KEEP** — frontend depends on direct Data API call | 3 | No change |
| **Total tables with public grants** | 32 | |

**RLS state across all 32 tables**: 100% RLS-enabled with at least one policy. None have `FORCE ROW LEVEL SECURITY` set — that's a defense-in-depth gap separate from this audit (RLS still applies to anon/authenticated, but service_role bypasses unless forced).

**Frontend codebase**: not mounted to this Cowork session. Frontend-call detection done by table-name heuristics (REVOKE candidates are clearly internal/infrastructure). The VERIFY rows are the ones where Romain needs to confirm.

---

## Per-table classification

Columns: `Anon` / `Auth` = current grants (`R` = SELECT, `W` = INSERT/UPDATE/DELETE).

### 🔴 REVOKE — backend-only (17 tables)

| Table | Anon | Auth | RLS | Policies | Why REVOKE |
|---|---|---|---|---|---|
| `agent_runs` | — | R | ✅ | 3 | AI agent execution logs — internal observability. Backend writes via service_role. |
| `ai_human_feedback` | — | R | ✅ | 2 | Internal RLHF feedback dataset. Backend-only ingestion. |
| `ai_model_energy_profiles` | — | R | ✅ | 3 | Internal AI infra config (cost tracking). Backend-only. |
| `ai_spend_requests` | R | R | ✅ | 2 | Internal spend approval workflow. **Anon grant is suspicious — almost certainly leftover.** |
| `bamboohr_sync_log` | — | R | ✅ | 1 | HRIS sync log. Backend-only ingestion. |
| `error_logs` | — | R | ✅ | 1 | Internal error logging. Backend-only writes; HR/admin viewers go via backend route. |
| `error_tickets` | — | R+W | ✅ | 2 | Internal error tickets. Same pattern. |
| `ocr_shadow_comparisons` | — | R | ✅ | 2 | OCR eval data (Mistral vs Azure shadow runs). Internal. |
| `personio_sync_log` | — | R | ✅ | 1 | HRIS sync log. Backend-only. |
| `prompt_routing` | — | R+W | ✅ | 3 | AI prompt routing config. Internal infra. |
| `prompt_versions` | — | R+W | ✅ | 3 | AI prompt version registry. Internal infra. |
| `rp_debug_kv` | **R** | R+W | ✅ | 4 | **Debug-only KV store. Anon grant + write access from authenticated = surface area to remove urgently.** |
| `translation_cache` | — | R | ✅ | 2 | Internal i18n cache. Backend-only. |
| `conjoint_responses` | — | R+W | ✅ | 3 | Conjoint research experiment data. Internal. |
| `conjoint_results` | — | R+W | ✅ | 2 | Conjoint research experiment outputs. Internal. |
| `conjoint_studies` | — | R+W | ✅ | 2 | Conjoint research experiment config. Internal. |
| `feedback` | — | R+W (no delete) | ✅ | 1 | If feedback collection is via backend `/api/feedback`, this is REVOKE. If frontend POSTs directly with supabase-js, move to VERIFY. **Spot-check needed.** |

### 🟡 VERIFY — need Romain to confirm (12 tables)

| Table | Anon | Auth | Question for Romain |
|---|---|---|---|
| `case_readiness` | — | R+W | Does the frontend read/write this directly via supabase-js, or only through the case-readiness backend service? If through backend → REVOKE. |
| `case_readiness_checklist_state` | — | R+W | Same as above — frontend or backend? |
| `case_readiness_milestone_state` | — | R+W | Same as above. |
| `default_policy_templates` | — | R+W | Used in Policy Builder. Does the UI fetch templates via supabase-js, or via `/api/policy/templates`? |
| `employee_tasks` | — | R+W | Employee portal — does the UI fetch tasks directly, or via `/api/employee/tasks`? |
| `quote_requests` | — | R+W | MVP capability 8 (curated providers + RFQ). Direct frontend call or backend? |
| `readiness_templates` | — | R | Template browse — frontend or backend? |
| `readiness_template_checklist_items` | — | R | Template child rows — same q. |
| `readiness_template_milestones` | — | R | Template child rows — same q. |
| `requirement_items` | **R** | R+W | Anon grant suggests this is meant to be publicly browsable (eligibility checker / public marketing surfaces). Confirm. |
| `requirements_catalog` | **R** | R+W | Same as above — public marketing surface? |
| `country_*` (4 tables: events, profiles, resource_items, resource_sections) | **R** | R+W | All four have anon grants, suggesting public country browse content (likely on the marketing/landing pages and the employee destination page). Confirm. |

### 🟢 KEEP — confirmed user-facing (3 tables/views)

| Object | Type | Anon | Auth | Why KEEP |
|---|---|---|---|---|
| `published_country_events` | view | — | R | Naming convention "published_*" indicates filtered public surface over `country_events`. Used by employee destination pages. |
| `published_country_resources` | view | — | R | Same — public country resources for employee browse. |
| `published_resource_sources_safe` | view | — | R | "Safe" view — explicitly designed to expose vetted source metadata to authenticated users. |

---

## VERIFY questions for Romain (action required before FRIDAY-003b)

Each question takes ~30 seconds to answer. Use the table name + frontend grep:

1. **`case_readiness` / `case_readiness_checklist_state` / `case_readiness_milestone_state`** — does the frontend call `supabase.from('case_readiness...')` directly, or go through `/api/hr/cases/:id/readiness` (or similar)?
2. **`default_policy_templates`** — Policy Builder fetches templates via supabase-js or via backend?
3. **`employee_tasks`** — Employee portal supabase-js direct or backend?
4. **`quote_requests`** — RFQ flow supabase-js direct or backend?
5. **`readiness_templates` + `readiness_template_checklist_items` + `readiness_template_milestones`** — direct or backend?
6. **`requirement_items` + `requirements_catalog`** — currently have **anon** grants. Are these intentionally publicly browsable (e.g. the free eligibility checker)? If yes → KEEP, if no → REVOKE both.
7. **`country_events` / `country_profiles` / `country_resource_items` / `country_resource_sections`** — all have **anon** grants. The `published_*` views over these are KEEP — but do anon users need to read the raw tables directly? If the views are the only public path → REVOKE the underlying tables' anon grants and rely on the views.
8. **`feedback`** — direct frontend POST or backend `/api/feedback`?

Fast answer pattern: run `grep -r "supabase.from('<table_name>" frontend/src/` on each. Any hit → KEEP. Zero hits → REVOKE.

---

## Defense-in-depth observation (out of scope but worth a follow-up ticket)

None of the 32 tables have `FORCE ROW LEVEL SECURITY` enabled. This means service_role bypasses RLS (which is normal for backend operations) — but it also means that any future bug exposing the service_role key has no second-line defense. Worth a SEC-RLSf follow-up to selectively enable `FORCE` on the highest-stakes tables (PII-bearing: cases, employees, profiles, immigration_*).

---

## Hand-off to FRIDAY-003b

Once Romain answers the 8 VERIFY questions, the migration in FRIDAY-003b can be written deterministically:

```sql
-- REVOKE statements (run after VERIFY answers come back)
REVOKE SELECT, INSERT, UPDATE, DELETE ON public.agent_runs FROM anon, authenticated;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public.ai_human_feedback FROM anon, authenticated;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public.ai_model_energy_profiles FROM anon, authenticated;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public.ai_spend_requests FROM anon, authenticated;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public.bamboohr_sync_log FROM anon, authenticated;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public.conjoint_responses FROM anon, authenticated;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public.conjoint_results FROM anon, authenticated;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public.conjoint_studies FROM anon, authenticated;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public.error_logs FROM anon, authenticated;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public.error_tickets FROM anon, authenticated;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public.ocr_shadow_comparisons FROM anon, authenticated;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public.personio_sync_log FROM anon, authenticated;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public.prompt_routing FROM anon, authenticated;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public.prompt_versions FROM anon, authenticated;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public.rp_debug_kv FROM anon, authenticated;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public.translation_cache FROM anon, authenticated;
-- (feedback added pending Romain's confirmation)
```

Plus REVOKEs for whatever of the 12 VERIFY-list tables come back as backend-only.

---

## Methodology notes

- Grant enumeration: `information_schema.table_privileges` filtered to `public` schema, grantees `anon`/`authenticated`. Service_role grants not included (those are always present and required for backend operations).
- RLS state: `pg_class.relrowsecurity` + `pg_class.relforcerowsecurity` + count of policies via `pg_policies`.
- Frontend classification: done by table-name heuristics + naming conventions because the frontend codebase isn't mounted to this Cowork session. The 12 VERIFY rows are the ones where heuristics aren't enough.
- The three `published_*` rows are views, not tables. They have grants because Supabase Auth-managed views inherit grant semantics from PostgREST exposure rules. Keeping them is correct.

---

*Generated 2026-06-03 by Claude Cowork executing FRIDAY-003a.*
