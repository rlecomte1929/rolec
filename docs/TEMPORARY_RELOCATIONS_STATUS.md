# Temporary / Project-Based Relocations (AIQ-1349) — Status Report

Prepared: 2026-07-01 · Verified against `origin/main` (code) + prod Supabase `nsvefcvpvwwwhuqyuqmp` (data),
not just commit messages.

## Bottom line

Two days ago (2026-06-29) the platform was, in the scope doc's own words, "duration-blind" — no
assignment-type field existed anywhere in the case/journey layer. Since then, 21 commits landed and the
gap is now real infrastructure, not just a plan. But coverage is partial and at least one legacy code
path was missed. Verdict: **it can handle it for the tested, narrow path (STA dependents waiver +
policy resolution across the 7 covered countries); partial-to-soft everywhere else.**

## What's actually shipped (verified, not assumed)

1. **Intake** — a real, required "Assignment type" question (STA under 12mo / LTA 1–5yr / PERMANENT),
   defaults to LTA. `frontend/.../EmployeeIntakePage.tsx`.
2. **Persistence** — `public.cases.assignment_type` + `expected_duration_months` columns exist and are
   written via a careful `COALESCE`-based upsert (`backend/db/cases.py`) that won't clobber existing
   values. Confirmed live in prod: of 33 cases, 4 are LTA, 1 is STA (with duration=6), 28 are still
   NULL — expected, since those predate the feature, and NULL safely falls back to "applies to
   everyone."
3. **Policy resolution** — `backend/app/routers/policy_config.py` threads `assignment_type` through
   most of the benefit/wizard-criteria endpoints. The policy layer was already STA/LTA-shaped before
   this epic (per the original scope doc); it's now actually being fed real per-case data.
4. **Requirements — two mechanisms:**
   - *Deterministic (reliable):* `rules_engine.py` hardcodes suppression of two specific
     rule-generated requirements (school enrolment, dependent work authorization) for STA cases.
     Narrow but always-on and tested.
   - *Data-driven (partial):* a new `requirement_items.applies_to_assignment_types_json` column +
     filtering in `apply_rules`. Real and working, but only **34 of 94** requirement rows (36%) have
     it populated, unevenly: US 9/18, Norway/UK/Singapore 6/12, Germany 3/6, **France 2/18, Netherlands
     2/16** — the two corpus-grounded "flagship" corridors from this same epic have the thinnest
     assignment-type tagging of all seven.
5. **Roadmap** — `assignment_type` is threaded into the LLM prompt (rendered in the SUBJECT block,
   plus a prompt rule telling the model to favor entry/work-authorization steps and drop
   permanent-residency/school for STA). This is **prompt engineering, not code-level filtering** — the
   commit's own tests only prove the signal reaches the prompt, not that the LLM's output actually
   differs between STA and LTA for the same corridor.
6. **Non-liability disclaimer framework** — broad, real rollout: dedicated component
   (`ImmigrationDisclaimer.tsx`), content module, backend service, wired into the requirement list,
   roadmap screen, app shell, and PDF export. This looks solid.
7. **Research-request workflow** (employee/HR flags a corridor with no coverage → admin queue →
   publish) — backend router correctly registered in *both* `backend/main.py` and
   `backend/app/main.py` (the project's own documented dual-registration rule, done correctly), full
   P2a→P3 pipeline, plus an admin page and a provenance/expert-verification queue for what it produces.
8. **Content coverage today:** 7 countries have requirement content (US, UK, Germany, France,
   Netherlands, Norway, Singapore); France and Netherlands are the two corpus-grounded corridors this
   epic added.

## Gaps found

1. **A legacy endpoint still ignores the new field.** `backend/main.py` (~line 14364), an
   employee-facing "get applicable HR policy + wizard criteria" handler, hardcodes
   `assignment_type = "Long-Term"` — it never reads the case's real value. An STA employee hitting this
   endpoint still gets Long-Term-shaped policy/wizard defaults. This predates AIQ-1349 and wasn't
   touched by it — the dual-layer risk your own CLAUDE.md warns about, showing up here.
2. **`expected_duration_months` has no real intake question** that I could find — the one populated
   value in prod (6 months, on the single STA case) looks seed/test-created rather than user-entered.
   The assignment-type chip alone drives the branching logic today, so this may be an intentional
   simplification rather than an oversight — worth a quick confirm rather than treating it as broken.
3. **STA waivers are invisible to the user.** `flags.staWaived` is set server-side "for transparency"
   but nothing in the frontend reads or displays it — an STA employee just sees a shorter requirement
   list with no explanation of why items are missing.
4. **Data-driven tagging covers ~a third of content, unevenly**, and is thinnest on the two flagship
   corpus-grounded corridors (France, Netherlands).
5. **Roadmap differentiation is unproven.** No test diffs an actual STA vs. LTA roadmap output for the
   same corridor — only that the signal reaches the prompt.

## Suggested next steps, roughly in priority order

1. Fix the `backend/main.py:14364` hardcode to read the real case `assignment_type` — small, contained.
2. Backfill `applies_to_assignment_types_json`, prioritizing France/Netherlands.
3. Surface `flags.staWaived` in the employee/HR UI so a waived requirement is explained, not silently missing.
4. Decide whether `expected_duration_months` needs a real UI question or should be dropped from scope.
5. Add an eval that actually compares STA vs. LTA roadmap output for the same corridor, rather than just confirming the prompt received the signal.

## Evidence trail

Git: `origin/main` commit log filtered on `1349` (21 commits, 2026-06-29), diffed against each
`feat/aiq-1349-*` / `fix/aiq-1349-*` branch to confirm content matches what merged (no orphaned
unmerged work found). Prod DB: `public.cases` (assignment_type/expected_duration_months
distribution), `requirement_items` (applies_to_assignment_types_json coverage by country) — Supabase
project `nsvefcvpvwwwhuqyuqmp`, queried 2026-07-01. Router registration checked against both
`backend/main.py` and `backend/app/main.py` per CLAUDE.md's dual-registration rule.
