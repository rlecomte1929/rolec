# Scoping spec — temporary / project-based relocations (AIQ-1349)

**Status:** Draft for decision · **Date:** 2026-06-29 · **Type:** Research / scoping (no code)
**Source:** Beta-tester feedback 2026-06-28 (item #6, FR: *"Comment faire pour des relocations
temporaires (projets etc.)"*). **Decision owner:** Romain.

> ReloPass today models relocation as a single implicit shape (a permanent/long-term move). Beta
> feedback asks how temporary/project assignments fit. This spec enumerates the assignment types,
> maps what the current data model can and can't represent (grounded in the live schema), defines the
> minimal change, and gives a build/skip recommendation. **Validated facts** are cited to schema/code;
> **hypotheses** are labelled.

---

## 1. Assignment types corporate mobility recognizes

| Type | Typical duration | Defining traits |
|---|---|---|
| **Permanent transfer** | indefinite | Localized to host payroll; full immigration (often PR track); family relocates; full services. |
| **Long-term assignment (LTA)** | 1–5 yrs | Home-payroll/secondment; work permit; family usually relocates; full services. |
| **Short-term assignment (STA)** | 3–12 mo | Often home payroll + per-diem; simpler permit; family usually stays; **lighter** housing/school/tax. |
| **Commuter** | ongoing, recurring | Lives in home country, commutes to host weekly/bi-weekly; no family move; minimal housing. |
| **Rotational** | fixed on/off cycles | Project sites (energy/eng); accommodation provided; no dependants on-site. |
| **Business trip / project** | days–weeks | Not a relocation; travel + (sometimes) posted-worker/short permit only. |

The **temporal** axis (how long, does family move, is it host-localized) is what changes the journey —
it is orthogonal to the **geographic** axis (domestic vs international) the product already captures.

## 2. Current-model coverage — what we can / can't represent today

**Validated (live schema, `origin/main` / prod `nsvefcvpvwwwhuqyuqmp`):**

- **The case spine carries no assignment type or duration.** `public.cases` columns are: `…, purpose,
  target_move_date, actual_move_date, status, stage, …, policy_tier_id, intake_data, …` — **no
  `assignment_type`, no `end_date`/`duration`** (only a single move date). So the journey object can't
  distinguish a 6-month STA from a permanent move.
- **A duration signal is already collected at intake but not persisted to the case.**
  `backend/schemas.py:101` → `expectedDurationMonths: Optional[int]`. It lives in `intake_data` (jsonb)
  at best; nothing promotes it to a first-class, queryable case field.
- **The roadmap & requirements engines ignore assignment type entirely.** `grep` of
  `roadmap_generator.py`, `requirement_evaluation_service.py`, `requirements_builder.py` →
  **zero** references to `assignment_type` / `move_type` / `STA` / `LTA` / `short_term`. ⇒ every case
  gets the same roadmap and requirement set regardless of duration. *This is the core gap.*
- **The policy layer is already assignment-type aware** (asymmetry): `policy_assignment_type_applicability`
  (values **`STA`, `LTA`**), `policy_benefit_jurisdiction_overrides.assignment_type`,
  `policy_config_benefits.assignment_types`, and canonical facts carry
  `assignment_types_json` + `duration_value`/`duration_unit` (`backend/app/models.py:256,314,319-320`).
  So benefits *can* differ by STA/LTA — but nothing feeds a case's type into that resolution.
- **Existing type-ish fields are unreliable / wrong axis:**
  - `employees.assignment_type` exists but is **sparse + uncontrolled**: 158 null, "Permanent"×4,
    "Long-Term"×4, "lta"×1 (free text, no enum).
  - `wizard_cases.move_type` = **`international`(250) / `domestic`(27) / null(265)** — **geographic**,
    not temporal. Not a substitute for assignment type.

**Conclusion:** the *policy* half of the platform already speaks STA/LTA; the *case/journey* half
(intake → `cases` → roadmap → requirements) is duration-blind. The vocabulary mismatch (policy: STA/LTA;
employees: free text; wizard: geographic) means there's no single controlled assignment-type field
threaded end-to-end.

## 3. Minimal model change to support "temporary" assignments

Smallest change that makes the journey duration-aware, reusing what exists:

1. **One controlled field on the case.** Add `assignment_type` to `public.cases` as a CHECK-constrained
   enum aligned to the policy layer (`PERMANENT, LTA, STA, COMMUTER, ROTATIONAL, BUSINESS_TRIP`) +
   `expected_duration_months int` (and/or `expected_end_date`). Migration must follow the RLS/idempotency
   gates (new columns on an existing RLS table need no new policy; keep it a plain `ALTER TABLE … ADD
   COLUMN IF NOT EXISTS`).
2. **Persist what intake already collects.** Promote `expectedDurationMonths` (`schemas.py:101`) from
   `intake_data` to the new column at submit, and add a single intake question for `assignment_type`
   (default-inferred from duration: <12mo → STA, 1–5yr → LTA, indefinite → PERMANENT — hypothesis,
   confirm thresholds with mobility norms).
3. **Thread the type into the two duration-blind engines.** Pass `assignment_type`/duration into
   `roadmap_generator` + `requirement_evaluation_service` so a temporary assignment yields a tailored
   plan: STA/commuter → drop permanent-residency & school-enrolment steps, lighter housing
   (serviced/temp), simpler permit; reuse the **already-existing** policy resolution keyed on STA/LTA
   (`resolved_assignment_policies`, `policy_assignment_type_applicability`) instead of inventing new
   benefit logic.
4. **Normalize the legacy fields** (cleanup, not blocker): map `employees.assignment_type` free-text →
   the enum; leave `wizard_cases.move_type` as the geographic axis (rename mentally, don't conflate).

No new tables; one migration (2–3 columns), one intake field, and conditional branches in two services
that already receive the case. The policy/benefit side needs **no** change — it's waiting for the input.

## 4. Recommendation + effort

**Recommendation: BUILD a thin "assignment-type aware" slice — but AFTER launch, not now.**

- **Why build (eventually):** STA/commuter/rotational are a large share of corporate mobility, the
  *policy* engine is already built for STA/LTA, and the gap is small + well-bounded (the expensive part —
  type-aware benefits — already exists). Shipping it unlocks a differentiated, honest journey for
  temporary moves and stops over-prescribing permanent-move steps to short-term assignees.
- **Why not now:** it's not a launch blocker — current corridors are framed as full relocations, prod
  data is pre-launch/fake, and adding an intake branch + roadmap conditionals touches the core journey
  during the pre-launch hardening window. A single beta comment shouldn't silently expand launch scope.
- **Effort (hypothesis):** **~Medium, ~2–3 focused PRs.** (a) migration + intake field + persist
  `expectedDurationMonths` (S); (b) thread type/duration into `roadmap_generator` +
  `requirement_evaluation_service`, wire to existing STA/LTA policy resolution (M); (c) STA/commuter
  roadmap-template pruning + copy + tests (M). Biggest unknown = the per-type roadmap/requirement rules
  (product/content work), not the plumbing.

**Suggested next step if approved:** convert §3 into a 3-subtask epic (migration → engine threading →
STA roadmap template) via `notion-decomposition`, scheduled post-launch.

---

### Evidence index
- `public.cases` columns, `policy_assignment_type_applicability` (STA/LTA), `employees.assignment_type`
  distribution, `wizard_cases.move_type` distribution — Supabase MCP, prod `nsvefcvpvwwwhuqyuqmp`,
  2026-06-29.
- `backend/schemas.py:101` (`expectedDurationMonths`); `backend/app/models.py:256,314,319-320`
  (policy assignment_types_json + duration); zero assignment-type refs in `roadmap_generator.py` /
  `requirement_evaluation_service.py` / `requirements_builder.py` — `origin/main`.
