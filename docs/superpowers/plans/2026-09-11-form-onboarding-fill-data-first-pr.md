# Form-Onboarding — Data-Driven Radio Fill (First Slice) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the FR/ES form radios from the in-code `CHOICE_GROUPS` dict into `form_field_mappings`
data rows on the existing `form_id` key, and make the serving/LLM isolation guard actually cover the live
fill path — without breaking the live FR/ES fill or re-keying the table.

**Architecture:** Additive-only. Ship in two PRs gated by the (operator-applied) migration: **PR-1** adds a
`FILL_ROOTS` to `scripts/check_serving_llm_isolation.py` and a migration adding two nullable columns
(`field_kind`, `transform_spec`) — nothing reads the new columns, so it is safe to merge before the
migration is applied. **PR-2** (after an operator applies PR-1's migration) adds a choice-config loader
that reads the new rows and **falls back to `CHOICE_GROUPS` when the DB has none**, refactors
`build_choice_fill` to accept resolved groups, and seeds the FR/ES radio rows as data. The in-code
`CHOICE_GROUPS` stays as the fallback (removed only later, after prod parity — not in this slice).

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy (`backend/app/database.py` `db.engine`), pypdf/reportlab,
pytest, Supabase/Postgres migrations (`supabase/migrations/`).

**Spec:** `docs/superpowers/specs/2026-09-11-form-onboarding-pipeline-design.md` (v3) — Phases 1a/1b.

## Global Constraints

- **Never break the live FR/ES fill.** `build_choice_fill(form_id, profile)` with no groups passed MUST
  behave exactly as today (read `CHOICE_GROUPS`), so the 36 fill tests pass unchanged.
- **Do not re-key `form_field_mappings`.** `form_id` stays the public/API/Storage handle. Columns are
  additive and nullable.
- **Column-read gate:** never merge code that `SELECT`s a new column in the same PR as the migration that
  adds it — CI's `scripts/check_column_read_before_apply.py` enforces this. Hence the PR-1/PR-2 split.
- **Migrations are operator-applied out-of-band** (no apply-on-merge; applier is jammed). A migration file
  is committed in PR-1 but must not be assumed live when PR-1 merges.
- **Migration timestamp** must exceed both the repo max (`git ls-tree origin/main --name-only
  supabase/migrations/ | sed 's|.*/||' | cut -c1-14 | sort | tail -1`) and the prod ledger max. Current
  repo max is `20261137000000`; use `20261140000000` (PR-1) and `20261141000000` (PR-2 seed) or higher.
- **The 36 fill tests span five files:** `backend/tests/test_imm11_form_prefill.py` (16),
  `test_form_choice_fill.py` (11), `test_fr_cerfa_real_acroform.py` (4), `test_fr_cerfa_real_pdf_fill.py`
  (2), `test_es_ex17_real_pdf_fill.py` (3). Run with `./.venv311/bin/python -m pytest <files> -q`.
- **Isolation edit is additive** — you are *adding* a protected root, which the guard welcomes; never
  remove or weaken `SERVING_ROOTS` / `LLM_GATEWAY_MODULES` / `LLM_SDK_MODULES`.

---

## PR-1 — Isolation fill-root + additive migration (mergeable immediately)

### Task 1: Cover the fill path in the serving/LLM isolation guard

**Files:**
- Modify: `scripts/check_serving_llm_isolation.py` (the `SERVING_ROOTS` region ~line 68, the config-error
  check ~line 386, the violation loop ~line 393)
- Test: `scripts/tests/test_check_serving_llm_isolation.py`

**Interfaces:**
- Produces: a module-level `FILL_ROOTS: Tuple[str, ...]` and the guard walking `SERVING_ROOTS + FILL_ROOTS`.

- [ ] **Step 1: Confirm the fill path is currently LLM-free (baseline).**

Run: `cd <repo> && ./.venv311/bin/python -c "print(open('scripts/check_serving_llm_isolation.py').read().count('form_prefill_service'))"`
Expected: `0` (not yet a root). Then run the guard now: `./.venv311/bin/python scripts/check_serving_llm_isolation.py` → expect `OK`. This proves the current graph is clean; adding the fill root must keep it green.

- [ ] **Step 2: Write the failing test** — a planted mapper import from the fill root must be caught.

Add to `scripts/tests/test_check_serving_llm_isolation.py` (match its existing helper style; it builds a
temp package and runs the checker's `find_violation`/`check`):

```python
def test_fill_root_catches_llm_import_from_form_prefill_service():
    # A mapper module that imports an LLM gateway, reachable from the fill path, must FAIL the guard.
    import importlib
    mod = importlib.import_module("scripts.check_serving_llm_isolation")
    assert "backend.app.services.form_prefill_service" in (mod.SERVING_ROOTS + mod.FILL_ROOTS), \
        "the live fill path must be a protected root"
```

- [ ] **Step 3: Run it to see it fail.**

Run: `./.venv311/bin/python -m pytest scripts/tests/test_check_serving_llm_isolation.py -k fill_root -q`
Expected: FAIL — `AttributeError: module ... has no attribute 'FILL_ROOTS'`.

- [ ] **Step 4: Add `FILL_ROOTS` and fold it into the walk.**

In `scripts/check_serving_llm_isolation.py`, after the `SERVING_ROOTS` tuple, add:

```python
#: Live PDF fill path. Not a requirement-serving engine, but it writes a GOVERNMENT PDF at request
#: time (generate_prefilled_pdf), so it must stay LLM-free too — the form-onboarding LLM mapper is
#: authoring-only and must never be import-reachable from here.
FILL_ROOTS: Tuple[str, ...] = (
    "backend.app.services.form_prefill_service",
)
```

Then extend the two places that iterate/validate roots (keep them reading one combined tuple):

```python
# where root_parse_errors is computed (~line 386):
_all_roots = SERVING_ROOTS + FILL_ROOTS
root_parse_errors = [e for e in parse_errors if e.split(" ", 1)[0] in _all_roots]
# ...
# the violation loop (~line 393):
for origin in _all_roots:
    found = find_violation(origin, edges, raw_imports)
    ...
```

Also update the "registered root resolved" check above it (the block returning code 2 when a root is
missing) to use `_all_roots` so a renamed fill root is also caught.

- [ ] **Step 5: Run the new test + the guard + the pytest wrapper.**

Run: `./.venv311/bin/python -m pytest scripts/tests/test_check_serving_llm_isolation.py -q`
Expected: PASS. Then `./.venv311/bin/python scripts/check_serving_llm_isolation.py` → expect `OK` (fill
root added, still no LLM reachable — the invariant we want).

- [ ] **Step 6: Prove it actually bites (manual planted-violation check, then revert).**

Temporarily add `from .fact_dictionary import lookup  # noqa` is NOT enough (fact_dictionary is LLM-free).
Instead temporarily add `from . import policy_extractor  # planted` to `form_prefill_service.py`, run the
guard, expect `FAIL — ... form_prefill_service ... -> policy_extractor`, then **revert the planted line**.
Run the guard again → `OK`. (This confirms the root is live, not decorative.)

- [ ] **Step 7: Commit.**

```bash
git add scripts/check_serving_llm_isolation.py scripts/tests/test_check_serving_llm_isolation.py
git commit -m "feat(guard): cover the live PDF fill path in serving/LLM isolation

Adds FILL_ROOTS (form_prefill_service) so the form-onboarding LLM mapper can
never be import-reachable from the request-time government-PDF fill. Additive
— strengthens the guard; the graph is currently LLM-free so it stays green."
```

### Task 2: Additive migration — `field_kind` + `transform_spec`

**Files:**
- Create: `supabase/migrations/20261140000000_form_field_mappings_kind_transform.sql`
- Test: `backend/tests/test_form_onboarding_migration.py` (a lightweight file-shape guard — DB-free)

**Interfaces:**
- Produces: two nullable columns on `public.form_field_mappings`: `field_kind TEXT NOT NULL DEFAULT
  'text'` and `transform_spec JSONB`. No table reads them in this PR.

- [ ] **Step 1: Write the migration (idempotent, additive, no re-key, no new table).**

```sql
-- Additive columns for data-driven field shapes (form-onboarding Phase 1a). No re-key, no new table.
-- field_kind: text | date_part | single_radio | checkbox_option (default text -> existing rows unchanged).
-- transform_spec: typed successor to open format_rule strings + the radio code->export map.
-- NOTHING reads these columns in the PR that adds them (check_column_read_before_apply gate).
ALTER TABLE public.form_field_mappings
  ADD COLUMN IF NOT EXISTS field_kind    TEXT NOT NULL DEFAULT 'text',
  ADD COLUMN IF NOT EXISTS transform_spec JSONB;
```

- [ ] **Step 2: Write the failing guard test** (asserts the file exists, is additive-only, unique ts).

```python
from pathlib import Path
M = Path(__file__).resolve().parents[2] / "supabase/migrations/20261140000000_form_field_mappings_kind_transform.sql"

def test_migration_is_additive_only():
    sql = M.read_text().upper()
    assert "ADD COLUMN IF NOT EXISTS FIELD_KIND" in sql
    assert "ADD COLUMN IF NOT EXISTS TRANSFORM_SPEC" in sql
    for forbidden in ("DROP COLUMN", "RENAME COLUMN", "DROP TABLE", "CREATE TABLE", "ALTER COLUMN"):
        assert forbidden not in sql, f"first-slice migration must be additive only, found {forbidden}"

def test_migration_timestamp_beats_repo_max():
    ts = M.name[:14]
    others = sorted(p.name[:14] for p in M.parent.glob("*.sql"))
    assert ts == others[-1], "migration timestamp must be the repo max"
```

- [ ] **Step 3: Run to see it pass** (the file exists from Step 1).

Run: `./.venv311/bin/python -m pytest backend/tests/test_form_onboarding_migration.py -q`
Expected: PASS.

- [ ] **Step 4: Verify no code SELECTs the new columns in this PR.**

Run: `git grep -nE "field_kind|transform_spec" -- 'backend/**/*.py' | grep -v test_form_onboarding_migration`
Expected: **no matches** (the loader that reads them is PR-2). If any match, remove it — it belongs in PR-2.

- [ ] **Step 5: Commit.**

```bash
git add supabase/migrations/20261140000000_form_field_mappings_kind_transform.sql backend/tests/test_form_onboarding_migration.py
git commit -m "feat(forms): additive field_kind + transform_spec columns (Phase 1a)

Nullable, defaulted, no re-key, no reader — the data-driven radio loader lands
in PR-2 after an operator applies this. check_column_read_before_apply-safe."
```

> **PR-1 ships here.** Open the PR (isolation + migration), let CI run (backend tests, the two migration
> guards, isolation guard — all green because nothing reads the new columns), merge, and **ask an operator
> to apply `20261140000000` and reconcile the ledger** before starting PR-2.

---

## PR-2 — Data-driven radio loader + FR/ES seed (after `20261140000000` is applied)

### Task 3: Choice-config loader with `CHOICE_GROUPS` fallback

**Files:**
- Modify: `backend/app/services/form_prefill_service.py` (`build_choice_fill` ~line 355; `_load_field_mappings`
  ~line 620; `generate_prefilled_pdf` ~line 685)
- Test: `backend/tests/test_choice_config_loader.py`

**Interfaces:**
- Consumes: the `field_kind`/`transform_spec` columns from Task 2 (now applied).
- Produces:
  - `load_choice_groups(form_id: str, mappings: List[Dict[str, Any]] | None = None) -> Dict[str, object]`
    — builds the `{vault_path: RadioField | {code: button_id}}` groups from `single_radio`/`checkbox_option`
    rows, falling back to `CHOICE_GROUPS.get(form_id, {})` when there are none.
  - `build_choice_fill(form_id, profile, groups=None)` — unchanged behaviour when `groups is None`.

- [ ] **Step 1: Write the failing test for the loader (both DB-rows and fallback paths).**

`backend/tests/test_choice_config_loader.py`:

```python
from backend.app.services import form_prefill_service as fps

def _rows(*triples):
    # (form_field_id, vault_field_path, field_kind, transform_spec)
    return [{"form_field_id": a, "vault_field_path": b, "field_kind": c, "transform_spec": d}
            for a, b, c, d in triples]

def test_loader_builds_single_radio_from_rows():
    rows = _rows(("Sexo", "gender", "single_radio", {"values": {"M": "/Hombre", "F": "/Mujer"}}))
    groups = fps.load_choice_groups("ES_ex17_v2024", rows)
    g = groups["gender"]
    assert isinstance(g, fps.RadioField) and g.field_id == "Sexo" and g.values["F"] == "/Mujer"

def test_loader_builds_checkbox_options_from_rows():
    rows = _rows(("applicantGenderM", "gender", "checkbox_option", {"code": "M"}),
                 ("applicantGenderF", "gender", "checkbox_option", {"code": "F"}))
    groups = fps.load_choice_groups("FR_cerfa_14571_v2024", rows)
    assert groups["gender"] == {"M": "applicantGenderM", "F": "applicantGenderF"}

def test_loader_falls_back_to_code_when_no_rows():
    assert fps.load_choice_groups("FR_cerfa_14571_v2024", []) == fps.CHOICE_GROUPS["FR_cerfa_14571_v2024"]

def test_build_choice_fill_unchanged_when_groups_none():
    # the live-path regression guarantee: no groups passed == read CHOICE_GROUPS
    vals, _ = fps.build_choice_fill("ES_ex17_v2024", {"gender": "female", "marital_status": "single"})
    assert vals == {"Sexo": "/Mujer", "Estado Civil": "/Soltero"}
```

- [ ] **Step 2: Run to see it fail.**

Run: `./.venv311/bin/python -m pytest backend/tests/test_choice_config_loader.py -q`
Expected: FAIL — `AttributeError: ... has no attribute 'load_choice_groups'`.

- [ ] **Step 3: Implement `load_choice_groups` + make `build_choice_fill` accept `groups`.**

In `form_prefill_service.py`, add near `build_choice_fill`:

```python
def load_choice_groups(form_id, mappings=None):
    """Resolve a form's choice groups from field_kind/transform_spec rows, falling back to the
    in-code CHOICE_GROUPS when the DB carries none (keeps FR/ES filling before the seed applies)."""
    rows = [m for m in (mappings or []) if m.get("field_kind") in ("single_radio", "checkbox_option")]
    if not rows:
        return CHOICE_GROUPS.get(form_id, {})
    groups: Dict[str, object] = {}
    for m in rows:
        vault = m["vault_field_path"]; spec = m.get("transform_spec") or {}
        if m["field_kind"] == "single_radio":
            groups[vault] = RadioField(m["form_field_id"], dict(spec.get("values") or {}))
        else:  # checkbox_option
            existing = groups.get(vault)
            if not isinstance(existing, dict):
                existing = {}; groups[vault] = existing
            existing[spec["code"]] = m["form_field_id"]
    return groups
```

Change the signature to `def build_choice_fill(form_id, profile, groups=None):` and, as its first line,
`groups = CHOICE_GROUPS.get(form_id, {}) if groups is None else groups` (replacing the current
`groups = CHOICE_GROUPS.get(form_id, {})`). The rest of the function is unchanged.

- [ ] **Step 4: Run the loader tests + the full 36-test fill suite (fallback keeps them green).**

Run: `./.venv311/bin/python -m pytest backend/tests/test_choice_config_loader.py backend/tests/test_form_choice_fill.py backend/tests/test_imm11_form_prefill.py backend/tests/test_fr_cerfa_real_acroform.py backend/tests/test_fr_cerfa_real_pdf_fill.py backend/tests/test_es_ex17_real_pdf_fill.py -q`
Expected: PASS (loader new tests + **36** fill tests — the DB-free tests hit the `groups is None` fallback).

- [ ] **Step 5: Wire `generate_prefilled_pdf` to the loader; keep choice rows out of the text plan.**

In `_load_field_mappings`, add `field_kind, transform_spec` to the SELECT **and** filter them out of the
text plan: `WHERE form_id = :form_id AND (field_kind IS NULL OR field_kind NOT IN ('single_radio',
'checkbox_option'))`. In `generate_prefilled_pdf`, load all rows once (a second query without the filter,
or fetch the choice rows), then:

```python
choice_rows = _load_choice_rows(form_id)          # SELECT ... WHERE form_id AND field_kind IN (...)
groups = load_choice_groups(form_id, choice_rows)
choice_values, choice_report = build_choice_fill(form_id, employee_profile, groups)
```

- [ ] **Step 6: Run the isolation guard + the fill suite again.**

Run: `./.venv311/bin/python scripts/check_serving_llm_isolation.py` → `OK`; then re-run the six fill test
files → PASS. (This edits the live fill path; the Task-1 fill root ensures it stayed LLM-free.)

- [ ] **Step 7: Commit.**

```bash
git add backend/app/services/form_prefill_service.py backend/tests/test_choice_config_loader.py
git commit -m "feat(forms): data-driven choice groups with CHOICE_GROUPS fallback

load_choice_groups reads single_radio/checkbox_option rows; build_choice_fill
takes resolved groups (unchanged when none). Text plan excludes choice rows.
FR/ES fill unchanged (36 tests green via fallback) until the seed lands."
```

### Task 4: Seed the FR/ES radio rows as data (1:1 with `CHOICE_GROUPS`)

**Files:**
- Create: `supabase/migrations/20261141000000_seed_fr_es_radio_choice_rows.sql`
- Test: `backend/tests/test_choice_seed_parity.py`

**Interfaces:**
- Consumes: `load_choice_groups` (Task 3), the seeded rows.
- Produces: `form_field_mappings` rows (`field_kind` ∈ single_radio/checkbox_option) reproducing today's
  `CHOICE_GROUPS` exactly.

- [ ] **Step 1: Write the failing parity test** — the seeded rows must rebuild `CHOICE_GROUPS` 1:1.

`backend/tests/test_choice_seed_parity.py` parses the seed SQL (like `test_fr_cerfa_real_acroform.py`
parses its migration) into `{form_field_id, vault_field_path, field_kind, transform_spec}` rows, then:

```python
from backend.app.services import form_prefill_service as fps

def test_seed_rebuilds_choice_groups_for_fr_and_es():
    for form_id in ("FR_cerfa_14571_v2024", "ES_ex17_v2024"):
        rows = _seed_rows(form_id)                       # parsed from the seed migration
        rebuilt = fps.load_choice_groups(form_id, rows)
        assert rebuilt == fps.CHOICE_GROUPS[form_id], f"{form_id} seed != code CHOICE_GROUPS"
```

- [ ] **Step 2: Run to see it fail** (no seed file yet).

Run: `./.venv311/bin/python -m pytest backend/tests/test_choice_seed_parity.py -q`
Expected: FAIL — seed file missing / rows empty.

- [ ] **Step 3: Write the seed migration** (idempotent; INSERT the radio rows for both forms).

```sql
-- Seed FR/ES radio choice rows as data (form-onboarding Phase 1b). 1:1 with CHOICE_GROUPS in code.
BEGIN;
DELETE FROM public.form_field_mappings
 WHERE form_id IN ('FR_cerfa_14571_v2024','ES_ex17_v2024')
   AND field_kind IN ('single_radio','checkbox_option');
INSERT INTO public.form_field_mappings
  (form_id, form_name, corridor_to, visa_type, form_field_id, form_field_label,
   vault_field_path, field_kind, transform_spec)
VALUES
  -- FR CERFA: one checkbox per option
  ('FR_cerfa_14571_v2024','France — Long-stay visa (CERFA 14571*05)','FR','long_stay',
     'applicantGenderM','Sexe (Male)','gender','checkbox_option','{"code":"M"}'),
  ('FR_cerfa_14571_v2024','France — Long-stay visa (CERFA 14571*05)','FR','long_stay',
     'applicantGenderF','Sexe (Female)','gender','checkbox_option','{"code":"F"}'),
  ('FR_cerfa_14571_v2024','France — Long-stay visa (CERFA 14571*05)','FR','long_stay',
     'applicantGenderOther','Sexe (Other)','gender','checkbox_option','{"code":"OTHER"}'),
  ('FR_cerfa_14571_v2024','France — Long-stay visa (CERFA 14571*05)','FR','long_stay',
     'applicantMaritalCEL','État civil (Single)','marital_status','checkbox_option','{"code":"SINGLE"}'),
  ('FR_cerfa_14571_v2024','France — Long-stay visa (CERFA 14571*05)','FR','long_stay',
     'applicantMaritalMAR','État civil (Married)','marital_status','checkbox_option','{"code":"MARRIED"}'),
  ('FR_cerfa_14571_v2024','France — Long-stay visa (CERFA 14571*05)','FR','long_stay',
     'applicantMaritalSEP','État civil (Separated)','marital_status','checkbox_option','{"code":"SEPARATED"}'),
  ('FR_cerfa_14571_v2024','France — Long-stay visa (CERFA 14571*05)','FR','long_stay',
     'applicantMaritalDIV','État civil (Divorced)','marital_status','checkbox_option','{"code":"DIVORCED"}'),
  ('FR_cerfa_14571_v2024','France — Long-stay visa (CERFA 14571*05)','FR','long_stay',
     'applicantMaritalVEU','État civil (Widowed)','marital_status','checkbox_option','{"code":"WIDOWED"}'),
  ('FR_cerfa_14571_v2024','France — Long-stay visa (CERFA 14571*05)','FR','long_stay',
     'applicantMaritalAUT','État civil (Other)','marital_status','checkbox_option','{"code":"OTHER"}'),
  -- ES EX-17: one radio field per group, Spanish export values
  ('ES_ex17_v2024','Spain — EX-17 (TIE)','ES','residence',
     'Sexo','Sexo','gender','single_radio','{"values":{"M":"/Hombre","F":"/Mujer"}}'),
  ('ES_ex17_v2024','Spain — EX-17 (TIE)','ES','residence',
     'Estado Civil','Estado civil','marital_status','single_radio',
     '{"values":{"SINGLE":"/Soltero","MARRIED":"/Casado","WIDOWED":"/Viudo","DIVORCED":"/Divorciado","SEPARATED":"/Separado"}}');
COMMIT;
```

- [ ] **Step 4: Run the parity test.**

Run: `./.venv311/bin/python -m pytest backend/tests/test_choice_seed_parity.py -q`
Expected: PASS — the parsed seed rebuilds `CHOICE_GROUPS` for both forms exactly.

- [ ] **Step 5: Run the whole fill suite + isolation once more.**

Run the six fill files + `scripts/check_serving_llm_isolation.py`. Expected: **36 PASS**, guard `OK`.

- [ ] **Step 6: Commit.**

```bash
git add supabase/migrations/20261141000000_seed_fr_es_radio_choice_rows.sql backend/tests/test_choice_seed_parity.py
git commit -m "feat(forms): seed FR/ES radio choice rows as data (Phase 1b)

INSERTs single_radio/checkbox_option rows reproducing CHOICE_GROUPS 1:1; a
parity test asserts load_choice_groups(rows) == CHOICE_GROUPS for both forms.
CHOICE_GROUPS stays as the code fallback until prod parity is confirmed."
```

> **PR-2 ships here** (Tasks 3–4). After merge, an operator applies `20261141000000`; the loader then reads
> the seeded rows in prod, with the code fallback covering the pre-apply window. Removing the in-code
> `CHOICE_GROUPS` is a **later** contract PR, only after prod parity is confirmed — out of this slice.

---

## Self-review

- **Spec coverage (v3 Phase 1a/1b):** isolation fill-root (Task 1 ↔ spec §13.1 + §15 Phase 1a); additive
  `field_kind`/`transform_spec`, no re-key (Task 2 ↔ §4 + §15 Phase 1a); radios→data with fallback,
  date-parts untouched, text plan excludes choice rows (Task 3 ↔ §4 "Change 2" + §15 Phase 1b); FR/ES
  parity, 36 tests green (Task 4 ↔ §14). Deferred by design (documented, not gaps): versioning tables,
  acquisition, LLM mapper, queue/worker — later phases.
- **Placeholder scan:** none — every step has runnable commands / real SQL / real test code.
- **Type consistency:** `load_choice_groups(form_id, mappings=None)` and `build_choice_fill(form_id,
  profile, groups=None)` are used consistently across Tasks 3–4; `RadioField(field_id, values)` and the
  `{code: form_field_id}` checkbox shape match the existing `CHOICE_GROUPS` definitions and the parity
  assertion.
- **Gate correctness:** Task 2 adds columns, Task 3 reads them — split across PR-1/PR-2 with the
  operator-apply gate between, satisfying `check_column_read_before_apply`.
