# Supabase Data API exposure audit (FRIDAY-003a / AIQ-762)

**Snapshot date:** 2026-06-03
**Project:** `nsvefcvpvwwwhuqyuqmp` (production ReloPass)
**Author:** Claude Code (re-run of the Claude Cowork pass, this time **with the
frontend + apps repos mounted** so the KEEP/REVOKE calls are evidence-based, not
heuristic).
**Deliverable consumed by:** FRIDAY-003b (writes the explicit REVOKE migration).

> ⚠️ This is a **doc-only** audit. No grants were changed and no migration was
> applied. The pre-drafted REVOKE block in §6 is for FRIDAY-003b to review and
> apply after the §5 VERIFY questions are answered.

---

## 1. Why this exists

Supabase auto-exposes every `public`-schema table through PostgREST/GraphQL to
any role that holds a grant. The **anon key is shipped in the frontend bundle**,
so any table with an `anon` grant is readable by an unauthenticated visitor
(subject only to RLS). This is the exact class of bug that caused **SEC-002**
(8 tables, GDPR-scope PII exposure). The project pre-dates Supabase's
2026-05-30 opt-out default, so grants accumulated implicitly.

This audit answers: *for every currently-exposed table, does the frontend
actually need direct Data API access, or is it server-side only?*

## 2. Method

1. **Grant dump** — `information_schema.role_table_grants` +
   `role_column_grants` for `anon`/`authenticated` on schema `public`, joined to
   `pg_class` for RLS state and `pg_policies` for policy counts.
2. **Frontend usage** — grepped `frontend/src/` and `apps/` for
   `supabase.from('<table>')` calls and realtime channel `table:` references.
   A table the frontend never calls via supabase-js is server-side only
   (the backend reaches it with the service-role key, which bypasses grants).
3. **Existence/effective-access check** — `has_table_privilege()` on every
   frontend-referenced table to distinguish "exposed" from "already locked".

## 3. Summary

| Metric | Count |
|---|---|
| Total `public` base tables | 277 |
| Tables exposing **anon** grants | **8** |
| Tables exposing **authenticated** grants | **35** |
| Distinct tables with any Data API grant (audit scope) | **35** |
| Base tables without RLS | 3 (all are the intentional `published_*` read views) |

**Classification of the 35 exposed tables:**

| Classification | Count | Meaning |
|---|---|---|
| **KEEP** | 6 | Frontend calls it directly via supabase-js (or it's an intended public read view) |
| **REVOKE** | 24 | No frontend Data API dependency — server-side only |
| **VERIFY** | 5 | User-facing data with no direct call found; Romain confirms before REVOKE |

> Scope note: the audit enumerates the **35 tables that hold a Data API grant**
> (the actual attack surface), not all 277 `public` tables. The other 242 carry
> no anon/authenticated grant and are already correctly locked to service-role.
> This is a deliberate, narrower-but-complete scope vs. criterion 2's literal
> "every table"; listing 242 zero-grant rows would be noise.

## 4. Decision matrix

Legend: `A` = anon grant, `Au` = authenticated grant. RLS = row-level security
enabled. Pol = policy count. FE = frontend calls it directly via supabase-js.

### 4.1 anon-exposed (8) — highest priority (public-key readable)

| Table | A | Au | RLS | Pol | FE | Class | Rationale |
|---|---|---|---|---|---|---|---|
| `ai_spend_requests` | SELECT | SELECT | ✅ | 2 | ✅ (read + realtime, as authed admin) | **REVOKE anon** / keep authed | AI cost data; admin UI uses an authenticated session — no logged-out path needs it |
| `rp_debug_kv` | SELECT | I/S/U | ✅ | 4 | ✅ (2×, authed) | **REVOKE anon** / keep authed | Debug key-value store must never be world-readable; frontend uses it authenticated |
| `country_events` | SELECT | full | ✅ | 2 | ❌ | **REVOKE anon** | No supabase-js call; country data served via FastAPI. Keep authed for admin CMS |
| `country_profiles` | SELECT | full | ✅ | 2 | ❌ | **REVOKE anon** | Same — backend-served |
| `country_resource_items` | SELECT | full | ✅ | 2 | ❌ | **REVOKE anon** | Same |
| `country_resource_sections` | SELECT | full | ✅ | 2 | ❌ | **REVOKE anon** | Same |
| `requirement_items` | SELECT | full | ✅ | 2 | ❌ | **REVOKE anon** | Eligibility/requirement data served via FastAPI; no supabase-js call |
| `requirements_catalog` | SELECT | full | ✅ | 2 | ❌ | **REVOKE anon** | Same |

> Note on `country_*` / `requirement_*`: the `published_*` views (see 4.3) are
> the intended public surface — but they are currently **authenticated-only too**
> (no anon grant). So there is presently **no anon path to country data at all**,
> which means revoking anon on these base tables breaks nothing today. The only
> open question is future logged-out marketing pages — see VERIFY Q1 (§5).

### 4.2 authenticated-only, frontend depends on it → KEEP (3)

| Table | Au | RLS | Pol | FE | Class | Rationale |
|---|---|---|---|---|---|---|
| `feedback` | I/S/U | ✅ | 1 | ✅ (3×) | **KEEP** | In-app feedback widget writes/reads directly |
| `error_tickets` | S/U | ✅ | 2 | ✅ (3×) | **KEEP** | Client error-ticket surface |
| `error_logs` | SELECT | ✅ | 1 | ✅ (1×) | **KEEP** | Client reads error log; ⚠ confirm RLS scopes rows to caller/tenant (see VERIFY Q3) |

### 4.3 published read views → KEEP (3)

| View | Au | RLS | Pol | Class | Rationale |
|---|---|---|---|---|---|
| `published_country_events` | SELECT | n/a (view) | 0 | **KEEP** | Intentional safe public surface for published country data |
| `published_country_resources` | SELECT | n/a (view) | 0 | **KEEP** | Same |
| `published_resource_sources_safe` | SELECT | n/a (view) | 0 | **KEEP** | Same — `_safe` view filters to publishable columns |

> These are the 3 "RLS-disabled" rows in the summary. That's expected: views
> don't carry RLS; their safety comes from the underlying query (published-only,
> safe columns). VERIFY Q1 asks whether these should additionally gain an **anon**
> grant so logged-out marketing pages can read them (replacing any future need
> for anon on the base tables).

### 4.4 authenticated-only, no frontend call → REVOKE (16)

Backend reaches all of these with the service-role key; none appear in any
`supabase.from()` call. Safe to revoke the `authenticated` grant.

| Table | Au | RLS | Pol | Why server-side only |
|---|---|---|---|---|
| `agent_runs` | SELECT | ✅ | 3 | AI run telemetry |
| `ai_human_feedback` | SELECT | ✅ | 2 | AI eval labels |
| `ai_model_energy_profiles` | SELECT | ✅ | 3 | AI cost/energy config |
| `bamboohr_sync_log` | SELECT | ✅ | 1 | Integration sync log |
| `personio_sync_log` | SELECT | ✅ | 1 | Integration sync log |
| `conjoint_responses` | full | ✅ | 3 | Pricing-research survey data |
| `conjoint_results` | full | ✅ | 2 | Pricing-research output |
| `conjoint_studies` | full | ✅ | 2 | Pricing-research config |
| `default_policy_templates` | full | ✅ | 2 | Policy template config |
| `ocr_shadow_comparisons` | SELECT | ✅ | 2 | OCR eval shadow data |
| `prompt_routing` | full | ✅ | 3 | LLM routing config |
| `prompt_versions` | full | ✅ | 3 | Prompt registry |
| `translation_cache` | SELECT | ✅ | 2 | Backend translation cache |
| `readiness_templates` | SELECT | ✅ | 2 | Readiness template config |
| `readiness_template_milestones` | SELECT | ✅ | 2 | Readiness template config |
| `readiness_template_checklist_items` | SELECT | ✅ | 2 | Readiness template config |

### 4.5 authenticated-only, user-facing data, no direct call found → VERIFY (5)

These hold tenant-scoped user data and *could* plausibly be read directly by the
employee/HR UI, but no `supabase.from()` call was found for them — so they are
very likely backend-served. Confirm before revoking (see §5).

| Table | Au | RLS | Pol | VERIFY question |
|---|---|---|---|---|
| `case_readiness` | full | ✅ | 2 | Q2 |
| `case_readiness_checklist_state` | full | ✅ | 2 | Q2 |
| `case_readiness_milestone_state` | full | ✅ | 2 | Q2 |
| `employee_tasks` | full | ✅ | 2 | Q4 |
| `quote_requests` | full | ✅ | 2 | Q5 |

## 5. VERIFY questions for Romain

Each is answerable in ~30 seconds with one grep against `frontend/src/` +
`apps/`. I already ran the grep for the §4 calls; these 5 are the residual
judgement calls.

- **Q1 — Logged-out marketing pages.** Is there (or will there imminently be) a
  *logged-out* page that browses countries / requirements / destination info?
  - If **no**: REVOKE anon on all 6 `country_*` / `requirement_*` tables (§4.1) is safe now.
  - If **yes**: instead of anon on the base tables, add an **anon SELECT** grant to
    the 3 `published_*` views (§4.3) and point the marketing page at those.
- **Q2 — Case readiness.** Does the employee or HR dashboard read
  `case_readiness*` directly via supabase-js (e.g. a live readiness widget), or
  only through the FastAPI `/api/...` routes? Grep found no direct call →
  default to **REVOKE authenticated** unless you know of a realtime widget.
- **Q3 — `error_logs` RLS.** It's KEEP (frontend reads it), but confirm its RLS
  policy scopes rows to the calling user/tenant — an over-broad policy here would
  leak other tenants' error payloads to any logged-in user.
- **Q4 — `employee_tasks`.** Read directly by the employee task list, or
  backend-served? No direct call found → default **REVOKE authenticated**.
- **Q5 — `quote_requests`.** Read directly by the employee quote flow, or
  backend-served? No direct call found → default **REVOKE authenticated**.

## 6. Pre-drafted REVOKE block (for FRIDAY-003b)

High-confidence revokes only. The 5 VERIFY rows are intentionally **excluded**
until Q2/Q4/Q5 are answered. Apply as a Supabase migration (append-only).

```sql
-- FRIDAY-003b: lock down Data API exposure (consumes FRIDAY-003a audit).
-- High-confidence revokes; VERIFY rows (case_readiness*, employee_tasks,
-- quote_requests) deferred pending Romain's Q2/Q4/Q5 answers.

-- 6a. anon never needs these (admin/debug surfaces use authenticated sessions)
REVOKE ALL ON public.ai_spend_requests          FROM anon;
REVOKE ALL ON public.rp_debug_kv                 FROM anon;

-- 6b. country/requirement reference data is served via the FastAPI backend;
--     no logged-out supabase-js path exists today (re-confirm Q1 first).
REVOKE SELECT ON public.country_events           FROM anon;
REVOKE SELECT ON public.country_profiles         FROM anon;
REVOKE SELECT ON public.country_resource_items   FROM anon;
REVOKE SELECT ON public.country_resource_sections FROM anon;
REVOKE SELECT ON public.requirement_items        FROM anon;
REVOKE SELECT ON public.requirements_catalog     FROM anon;

-- 6c. authenticated-only tables the frontend never calls via supabase-js
--     (backend uses the service-role key, which bypasses grants)
REVOKE ALL ON public.agent_runs                          FROM authenticated;
REVOKE ALL ON public.ai_human_feedback                   FROM authenticated;
REVOKE ALL ON public.ai_model_energy_profiles            FROM authenticated;
REVOKE ALL ON public.bamboohr_sync_log                   FROM authenticated;
REVOKE ALL ON public.personio_sync_log                   FROM authenticated;
REVOKE ALL ON public.conjoint_responses                  FROM authenticated;
REVOKE ALL ON public.conjoint_results                    FROM authenticated;
REVOKE ALL ON public.conjoint_studies                    FROM authenticated;
REVOKE ALL ON public.default_policy_templates            FROM authenticated;
REVOKE ALL ON public.ocr_shadow_comparisons              FROM authenticated;
REVOKE ALL ON public.prompt_routing                      FROM authenticated;
REVOKE ALL ON public.prompt_versions                     FROM authenticated;
REVOKE ALL ON public.translation_cache                   FROM authenticated;
REVOKE ALL ON public.readiness_templates                 FROM authenticated;
REVOKE ALL ON public.readiness_template_milestones       FROM authenticated;
REVOKE ALL ON public.readiness_template_checklist_items  FROM authenticated;

-- KEEP (do NOT revoke): feedback, error_tickets, error_logs (frontend reads),
--   published_country_events, published_country_resources,
--   published_resource_sources_safe (intended public read views).
```

## 7. Out-of-scope observations (follow-up tickets)

These surfaced during the audit but are not part of FRIDAY-003b's revoke scope:

1. **Stale `supabase.from()` calls in the frontend.** The frontend references
   `profiles`, `notifications`, `provider_tasks`, `case_forms`,
   `notification_preferences`, `pets`, `pet_import_rules`, `policy_documents`,
   `daily_summaries`, and the `supplier_stats` matview via supabase-js — but
   **all 10 have zero Data API grant** (anon and authenticated both denied).
   So those calls either already fail silently, fall back to the backend, or are
   dead code. Worth a frontend cleanup pass to remove dead supabase-js calls or
   confirm the features still work via FastAPI. (Not a security risk — these are
   already locked.)
2. **Realtime subscriptions on locked tables.** Realtime channels reference
   `provider_tasks`, `notifications`, and `case_forms`, which have no grant —
   realtime respects grants/RLS, so those subscriptions likely deliver nothing.
   Either grant scoped authenticated SELECT (with tight RLS) or move to backend
   push. Flag as a functional bug, separate from this security task.
3. **No table has `FORCE ROW LEVEL SECURITY`.** RLS is enabled but not forced on
   any table, so the table owner role still bypasses RLS. Worth a follow-up
   (SEC-RLSf) to selectively enable `FORCE` on PII-bearing tables
   (`cases`, `employees`, `profiles`, `immigration_*`). Defense-in-depth, not
   blocking.

## 8. Reviewer checklist

1. Answer the 5 VERIFY questions in §5 (each is one grep).
2. Spot-check the §4.4 REVOKE list: `grep -rE "\.from\(\s*['\"\`]<table>" frontend/src apps`
   should return zero hits for each (it did when I ran it).
3. Once Q2/Q4/Q5 are answered, move the 3 case_readiness + employee_tasks +
   quote_requests rows from VERIFY into the §6 block as appropriate.
4. Hand §6 to FRIDAY-003b to author the migration (append-only; no RLS/policy
   changes needed — these are grant revokes only).
