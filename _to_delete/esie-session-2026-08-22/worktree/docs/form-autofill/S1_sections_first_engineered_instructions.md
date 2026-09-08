# S1 — Sections as first-class template data: Engineered Build Instructions

> **Task:** make `form_templates` section-first, so the DE/FR data sheets can express what the
> FR→NO one could not. **Tier:** 🟡 Yellow — additive schema + two renderers, no auth, no money,
> no PII. **Owner:** `rolec` (Claude Code). **Prereq state:** all of AIQ-1770's facts,
> AIQ-1795/1795b, C1 localised labels and D2 country codes are merged.
> **Anchors verified against `origin/main` on 2026-08-11** — trust the live repo over this doc
> where they differ, and note the delta.

---

## 0. How to use this document

Execute §5 in order; each phase has a `Verify:` gate and none advances until its gate passes.
The author asked for **goals → spec → plan → metrics → validation**; those are §1, §4, §5, §6, §7.

**§3 is the section to read twice.** It lists four traps that have already cost real defects in
this exact area. Three of them are silent: they produce a passing test suite and wrong behaviour.

---

## 1. Goals & non-goals

### 1.1 Primary goal

A template's sections carry their own content — number, title, authority, portal, deadline hint,
grouping, callouts, and which fields they contain — instead of every heading living in two
hardcoded code maps.

### 1.2 Success in one sentence

> The FR→NO sheet renders **byte-identically** while its five sections come from the database, a
> section with **zero fields** renders as a real section, and `d_number` + `skattekort` present as
> **one Skatteetaten visit**.

### 1.3 Non-goals — do NOT build these now

1. **The DE/FR seeds.** They are S4/S5 and they depend on this contract settling. Build the
   plumbing; seed nothing new.
2. **The Full/Sparse toggle.** It is a prototype affordance that hides nothing — it blanks values
   to demo the empty state. Not a product feature.
3. **Translating field values.** Labels only, asserted in four places. Untouched.
4. **The admin authoring UI for section content.** Adding `sections` makes the existing
   `normalizeFields()` data loss worse (see §3.4) — record it, do not fix it here; that is S3.
5. **Any `verification_status` change.** Nothing becomes `verified`.
6. **Consolidating the other EEA-ish country sets.** `immigration_regime._EU_EEA_COUNTRIES` and
   `family_propagation._EU_EEA_COUNTRIES` hold country *names* and answer a different question.

---

## 2. Current state — confirmed by code read

**`public.form_templates` has 16 columns and no `sections`.** Confirmed against prod:
`id, code, name, authority_code, authority_name, country, category, original_pdf_url, fields,
trigger_rules, version, created_at, updated_at, source_url, verification_status, source_language`.
84 rows, all `verification_status = 'representative'`, 49 with a `source_url`.

**Sections today are a bare string on each field, and every heading is hardcoded twice:**

| where | what |
|---|---|
| `backend/app/services/data_sheet_pdf.py:45` | `_SECTION_LABELS` — 5 entries |
| `backend/app/services/data_sheet_pdf.py:66` | `_section_label()`, empty key → **`"Your details"`** (`:68`) |
| `backend/app/services/data_sheet_pdf.py:151-157` | groups by `fd["section"]`, order = first appearance after sorting by `position` |
| `frontend/src/pages/employee/FormEditorPage.tsx:55` | `SECTION_LABELS` — the mirror, kept in step by a comment |
| `.../FormEditorPage.tsx:75` / `:80` | `humaniseSection()` / `sectionLabel()`; empty key → **`'Form fields'`** (`:81`, `:92`) |
| `.../FormEditorPage.tsx:87` | `groupBySection()` — relies on the server having sorted by `position` |

**Both renderers group *by field*, so a section with no fields cannot exist.** That is the blocker
for France's "nothing to register on arrival", which is a section that is a statement.

**The loader you must extend:** `backend/app/routers/cases_read.py:525` `_load_form_with_template`
selects `ft.fields` (`:549`) and `ft.source_language` (`:554`). A second, larger query at `:1301`
/ `:1304` feeds the field-values endpoint. **C1 had to add `source_language` to the first one
because it wasn't selected** — the same omission will silently disable `sections`.

**Reuse, do not reinvent:** `backend/app/services/localised_labels.py` — `localised_label()` and
`label_key_for()`, added in C1, already resolve a per-language string off
`form_templates.source_language`. Use them for any localised section title.
`render_data_sheet()` already takes `source_language` (`data_sheet_pdf.py:83`).

**The accepted-but-unimplemented requirement this delivers:** `docs/form-autofill/FINDINGS.md`
Appendix A.3 — *"the production build should present [D-number and skattekort] as one portal
visit"*. Ratified 30 Jul 2026, never built, because there was nowhere to put it.

---

## 3. Traps that have already bitten. Read twice.

### 3.1 `blocks[0]` — the golden harness parses positionally

`backend/tests/test_golden_case_fr_no_datasheet.py:143`:

```python
blocks = re.findall(r"'(\[\s*\{.*?\}\s*\])'::jsonb", sql, re.S)
...
return json.loads(blocks[0])          # :146
```

It takes the **first** `'[{…}]'::jsonb` literal in the migration file. If your backfill writes a
`sections` array *before* `fields`, this silently parses **sections as fields** and the "0 blank /
0 wrong" assertions start covering nothing. Either keep `sections` after `fields`, or key the
parse off the column name. **Do not modify the FR→NO harness's expectations to make it pass.**

### 3.2 A `;`, `$$`, or `--` inside a migration breaks naive SQL parsing

`scripts/check_form_template_honesty.py` lost three templates to exactly this — a semicolon inside
a seeded `note`, `$$Dependant's Pass$$` dollar-quoting whose apostrophe desynchronised the scanner,
and a `--` comment sitting *between two values inside* an INSERT. Each dropped the row **without a
word**. If you write anything that parses migrations, reuse that module's `_skip_literal()` and
assert coverage rather than hoping.

### 3.3 Clever SQL can defeat the guards that read SQL

`20261024000000` first used `DO $$ … WHERE code = t.code`. The honesty checker detects "this rule
was rewritten later" by looking for a **literal** `WHERE code = '<CODE>'`, so a loop variable made
the fix invisible and the guard would have reported the defect forever. Prefer explicit literal
statements in migrations over loops.

### 3.4 The admin editor silently strips data-sheet richness

`frontend/src/pages/admin/AdminFormTemplateEditor.tsx` `normalizeFields()` knows 11 keys and drops
`section`, `label_nb`, `note`, `portal_url`, `consult_professional`. Saving `RP-NO-DATASHEET`
through the admin UI reduces it to a bare field list. **Adding `sections` makes this worse.** Note
it in the PR; the fix is S3.

---

## 4. Spec

### 4.1 The `sections` contract

New column: `form_templates.sections jsonb NOT NULL DEFAULT '[]'`. Additive; the table already has
RLS and policies, so no new security surface and no new policy needed. **Array order is display
order** — do not re-derive it from `position`.

```jsonc
{
  "id": "d_number",                 // machine key; matches fields[].section for the fallback
  "number": 1,                      // explicit, not baked into the title
  "title": "D-number application",
  "authority": "Skatteetaten",
  "portal_url": "https://www.skatteetaten.no/en/...",   // a real href
  "deadline_hint": "Apply before your first payroll run",
  "session_group": "skatteetaten",  // sections sharing a key are ONE visit — FINDINGS A.3
  "callout_top": null,              // rendered ABOVE the fields
  "callout_bottom": "The registration certificate is issued BY the police …",
  "field_ids": ["full_name", "date_of_birth"]           // [] is legal and meaningful
}
```

`field_ids` reference `fields[].id`. **One field may appear in several sections** — each authority
appointment needs its own complete packet. Do **not** duplicate field definitions to achieve that:
five copies of `full_name` would write five `case_form_field_values` rows for one datum and let
them drift.

### 4.2 Resolution order in both renderers

If `sections` is non-empty, drive layout from it. Otherwise fall back to today's
group-by-`fields[].section` plus the hardcoded maps. **Keep `fields[].section` populated** in any
seed so the fallback path stays truthful. Pick one empty-key fallback string and use it in both
renderers — they currently disagree (`"Your details"` vs `'Form fields'`).

### 4.3 Files

- `supabase/migrations/<ts>_form_templates_sections.sql` — add the column, backfill
  `RP-NO-DATASHEET`'s five sections including `session_group: "skatteetaten"` on `d_number` and
  `skattekort`. Timestamp above **both** the repo max and the prod ledger max, and above every
  version an open PR claims. As of 2026-08-11: repo max `20261024000000` (in PR #1778), ledger max
  `20261020000000` → use `20261025000000` and re-check immediately before pushing.
- `backend/app/routers/cases_read.py` — SELECT the column in **both** queries (`~:549` and
  `~:1301`); expose sections on the form/dossier response.
- `backend/app/services/data_sheet_pdf.py` — render from `sections` when present.
- `frontend/src/pages/employee/FormEditorPage.tsx`, `frontend/src/api/formEditor.ts` — same.
- `backend/tests/test_data_sheet_sections.py` — new.

---

## 5. Plan — phased, each with a verify gate

**Phase A — capture the baseline BEFORE touching anything.** Dump the FR→NO rendered PDF text and
the `/fields` JSON payload to the scratchpad.
`Verify:` both artifacts exist and are non-empty. Without this, "no regression" is an opinion.

**Phase B — migration: column + FR→NO backfill.** Idempotent; `sections` written **after** `fields`
in the file (§3.1).
`Verify:` `check_migration_drift.py --no-db --added …` clean; a read-only `SELECT` of the
`jsonb_build_array` expression against prod returns the expected 5 sections and reports how many
rows the UPDATE would touch. **Do not apply it.**

**Phase C — backend renders from `sections`.** Loader selects the column; PDF prefers `sections`
and falls back.
`Verify:` re-dump the PDF text and **`diff` against Phase A — must be identical**. Plus a new test
that a zero-field section renders a heading and its callout.

**Phase D — frontend renders from `sections`.**
`Verify:` re-dump `/fields` and diff against Phase A; `npx tsc --noEmit` clean; existing
`CaseFormCard` / `DataSheetFieldRow` tests green.

**Phase E — session grouping (FINDINGS A.3).** Sections sharing a `session_group` present as one
visit.
`Verify:` a test asserts `d_number` and `skattekort` are grouped, and that sections with distinct
or null `session_group` keys are not.

**Phase F — guards.** A test asserting every `field_ids` entry exists in `fields[]`, and every
`fields[].id` appears in at least one section (for templates that declare `sections`).
`Verify:` each guard proven to fail when broken — break it, capture the output, restore.

---

## 6. Metrics

1. FR→NO PDF text and `/fields` JSON **byte-identical** before/after (Phases C and D).
2. A section with `field_ids: []` renders a heading + callout in **both** renderers.
3. A field referenced by *n* sections yields exactly **one** `case_form_field_values` row.
4. `sections` and `fields[].section` agree for every seeded template — no orphan field, no section
   referencing a missing id.
5. `d_number` + `skattekort` render as one Skatteetaten visit.
6. `test_golden_case_fr_no_datasheet.py` green **unmodified**.
7. `check_form_template_honesty.py` exit 0; `check_migration_drift.py --no-db --added` clean.
8. `npx tsc --noEmit` clean; backend + frontend suites green.

---

## 7. Validation process

- **Regression by diff, not by assertion.** Phase A exists so §6.1 is a `diff`, not a claim.
- **Every new guard proven to fail first.** Break it, capture the failure, restore, capture the
  pass. This session that caught a `'UK'` → `'UK'` bug, a permanently-red test, and three silent
  parser blind spots.
- **Prod stays read-only.** Confirm state with `execute_sql` SELECTs. Migrations are committed,
  never applied — the apply is operator-only and out-of-band.
- **Report what you did not verify.** Several suites cannot be collected locally
  (`test_blocking_logic`, `test_case_dossier_forms`, `test_hr_case_detail_feasibility` — missing
  `passlib` and a MagicMock DTO issue, both reproducible on clean `main`). Say so; do not imply
  coverage you did not get.

---

## 8. Guardrails — non-negotiable

- **Register nothing new in one main only.** Any new router goes in `backend/main.py` **and**
  `backend/app/main.py`, or it 405s in production. Not expected here — no new routes.
- **Migrations are committed, never applied.** No `apply_migration`, no `db push` (147+ pending,
  two destructive).
- **Timestamp above BOTH the repo max and the ledger max**, and above every open PR's versions.
- **`verification_status` stays `representative`.** It is never self-declared by seed data.
- **No compliance-status claims** in any copy (`scripts/check_compliance_claims.py` gates this).
- **Never `git stash`** and never work in the shared checkout — use a worktree; parallel agents
  move `HEAD`.
- **Values are never translated.** Labels only.

---

## 9. First message to paste

> Execute `docs/form-autofill/S1_sections_first_engineered_instructions.md`
> — S1, sections as first-class template data. Start with Phase A: capture the FR→NO PDF text and
> `/fields` baseline to the scratchpad before changing anything, because §6.1 is a diff. Then work
> through B→F, stopping at each `Verify:` gate. Read §3 twice before writing any code that parses a
> migration. Do not seed DE/FR — that is S4/S5.
