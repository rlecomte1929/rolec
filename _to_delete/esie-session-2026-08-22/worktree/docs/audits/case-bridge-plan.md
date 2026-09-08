# CASE-BRIDGE — Case-identity schism: investigation & migration plan

**Date:** 2026-06-14
**Author:** relopass audit (Claude Code)
**Status:** Investigation only — **no schema change made**. Awaiting a canonical-table decision.
**Notion:** [CASE-BRIDGE] task `37f887c6-4d48-81b3-90fa-deab468d7d3c`

---

## TL;DR

HR case creation (`POST /api/hr/cases`) writes to **`case_assignments`** + **`relocation_cases`**, but an entire **dossier / forms / documents / roadmap** subsystem (19 tables) is FK-anchored to **`public.cases`** — a legacy table with **14 rows and 4 code references**. Almost no case is bridged into it, so every *write* to those 19 tables fails its foreign key (~97% of cases). Reads silently return empty (no existence check), which hid the problem until the write paths were exercised.

This is the shared root cause behind the live findings:

- **[DOC-UPLOAD-502]** — document upload (depends on a `case_forms` row).
- **[ADHOC-FORM]** — `POST …/forms/adhoc` → 500 FK on unbridged cases (the 404 variant was a *separate* bug, fixed in PR #735).
- **[DOSSIER-ID]** — dossier shows 0 forms (id-mismatch, fixed in PR #732; but writes still FK-fail for unbridged cases).

---

## The three case tables

| Table | Rows (prod) | Code refs | # tables FK'd to it | Role |
|---|---|---|---|---|
| `public.cases` | **14** | 4 | **19** | **Abandoned anchor** of the dossier/forms/documents/roadmap cluster |
| `relocation_cases` | **814** | 66 | 6 | **Live "case engine v1"** (migration `20260528020000_relopass_case_engine_v1`) |
| `case_assignments` | 549 | 79 | 7 | Employee↔case link layer |

Row counts and FK map captured live from prod (`nsvefcvpvwwwhuqyuqmp`) on 2026-06-14. `530 / 549` assignments have no matching `public.cases` row.

### Tables FK'd to `public.cases` (19 — the broken cluster)
`agent_runs`, `case_dependents`, `case_discovery_runs`, `case_form_documents`, `case_forms`, `case_plans`, `documents`, `dossier_packages`, `forms`, `pets`, `plan_versions`, `policy_exceptions`, `requirements`, `retrieval_run_chunks`, `retrieval_runs`, `roadmap_steps`, `roadmap_tracks`, `threads`.
*(Delete rule: mostly CASCADE.)*

### Tables FK'd to `relocation_cases` (6 — the live engine)
`case_alerts`, `compliance_alerts`, `document_uploads`, `employee_tasks`, `immigration_cases`, `rfq_requests`.

### Tables FK'd to `case_assignments` (7)
`assignment_claim_invites`, `assignment_mobility_links`, `case_events`, `case_evidence`, `case_feedback`, `legacy_employee_profiles`, `relocation_tasks`.

---

## Why writes fail

1. HR creates a case → rows in `case_assignments` (+ canonical `relocation_cases`). **No `public.cases` row is created.**
2. The employee/HR opens the dossier → forms/documents/roadmap features try to write `case_forms` / `case_form_documents` / etc.
3. Those tables `FK → public.cases(id)`. The case id isn't there → **FK violation → 500/502**.
4. Read endpoints (`GET …/forms`) don't check existence — they return `[]`, so the gap is invisible until a write.

`public.cases` is still written by 2 rarely-hit `INSERT INTO cases` paths (`backend/database.py:7383`, `:7392`) and read by access checks (`backend/app/services/case_service.py:197`, `backend/app/routers/hr_coordination.py:162`). It is not part of the main case-creation flow.

### `public.cases` NOT NULL columns without a default (needed for any backfill)
`company_id`, `employee_id`, `origin_country_code`, `dest_country_code`.
`employee_id` must be sourced from `case_assignments` (the employee↔case link); countries from `relocation_cases` (host/home). All other NOT NULLs have safe defaults (`status='active'`, `stage='discovery'`, `purpose='work'`, `currency='EUR'`, `intake_data='{}'`, progress/risk/delay, timestamps).

---

## Options & risk assessment

> **Important:** "repoint `case_forms`'s FK to `relocation_cases`" is **insufficient** — 18 other tables share the same broken anchor. Any real fix must address the whole cluster.

### Option A — Backfill `public.cases` (+ keep-in-sync)
Insert an id-matched `cases` row for every `relocation_cases` case, sourcing the 4 no-default NOT NULLs by joining `relocation_cases` ⊕ `case_assignments`; add a trigger or app-write so new cases always get a `cases` row.

- **Pros:** Unblocks **all 19** dependent features at once; **zero FK or code changes**; fully reversible; smallest blast radius for an immediate fix.
- **Cons / risks:** Backfill join must be correct (esp. `employee_id` from `case_assignments`, and cases with >1 assignment); ongoing sync must be reliable (a missed sync re-introduces the bug for new cases); **perpetuates the dead table** as permanent tech debt.

### Option B — Repoint the 19 FKs → `relocation_cases`, then drop `public.cases`
Migrate the whole cluster onto the live engine.

- **Pros:** Architecturally correct; one canonical case table; permanently kills the schism.
- **Cons / risks:** **19 FK migrations**; every dependent table's existing `case_id`s must be verified present in `relocation_cases` (orphan sweep) or those rows break on FK re-add; the 2 `INSERT INTO cases` writers + 2 access-check readers must be moved; large surface area; harder to roll back. This is a **multi-PR epic**, not a single change.

---

## Recommendation — phased

1. **Phase 1 (now — low-risk, reversible): Option A backfill + sync.** Restores dossier visibility, document upload, ad-hoc forms, roadmap-from-forms, requirements, etc. for *all* real cases immediately. Complements the already-open PRs #732 (DOSSIER-ID) and #735 (ADHOC-FORM).
2. **Phase 2 (tracked epic): Option B consolidation** onto `relocation_cases` (the strategic canonical), then retire `public.cases`.

### Open decision (blocks Phase 1 authoring)
Confirm **`relocation_cases` is the strategic canonical** case table. Its name (`relopass_case_engine_v1`), 814 rows, and 66 code refs all indicate yes. If instead `public.cases` is intended to be canonical long-term, the plan flips (migrate the engine *to* it — a much larger effort).

---

## Validation approach (for whichever migration is authored)

- Author as an **idempotent** `supabase/migrations/<ts>_*.sql` file (project rule: never apply via MCP/dashboard).
- Prove safety in a **rollback transaction** first (inline DDL + seed + asserts, end with `RAISE EXCEPTION 'ALL_TESTS_PASSED'` so it always rolls back) per `docs`/memory `reference_migration_validation_rollback`.
- Phase 1 acceptance: `SELECT count(*) FROM case_assignments ca WHERE NOT EXISTS (SELECT 1 FROM public.cases c WHERE c.id::text = COALESCE(NULLIF(TRIM(ca.canonical_case_id),''), ca.case_id)) = 0`; and `POST /api/cases/{any active case}/forms/adhoc → 201` (no FK 500).

---

## Evidence references

- FK map + row counts: live `execute_sql` against prod 2026-06-14.
- Code usage counts: `backend/**.py` — `cases`=4, `relocation_cases`=66, `case_assignments`=79, `case_forms`=51 refs.
- Related queue items: `[B1-B3-S1/S3]` (canonical_case_id resolution + functional index), `AUTH-ID-2` (canonical auth_uuid), `roadmap_representation_schism`.
