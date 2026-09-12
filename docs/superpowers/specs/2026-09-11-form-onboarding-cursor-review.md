# Cursor review — form-onboarding pipeline spec (code-grounded)

**Date:** 2026-09-11
**Subject:** [`2026-09-11-form-onboarding-pipeline-design.md`](2026-09-11-form-onboarding-pipeline-design.md) v2.0 on `claude/form-onboarding-spec`
**Reviewer:** Cursor (repo-attached). Complementary to the repo-blind standards review already folded into v2.

## Verdict

**Approve with changes.** The v2 trust model (semantic gate, immutable version vs logical form, SSRF acquisition, lease-then-work queue) is compatible with this codebase and should stay. The spec’s *code* picture is wrong in several places that will break the live FR/ES fill path, overstate what `check_serving_llm_isolation.py` actually protects, and make Phase 1’s ~7-table migration larger than this repo’s migration reality can absorb.

Do not start Phase 1 as specified. Fold the collisions below into the spec, then ship a **fill-compat first PR** (additive columns + `CHOICE_GROUPS` → rows on the existing `form_id` key) before any versioning/queue/LLM work.

---

## Q1 — `form_field_mappings` version-scoping & consumers

**What exists.** The table is keyed on a string `form_id` (e.g. `FR_cerfa_14571_v2024`), not a version UUID. Schema:

```619:646:supabase/migrations/20260518120000_immigration_core_tables.sql
CREATE TABLE IF NOT EXISTS public.form_field_mappings (
  id                    TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  form_id               TEXT NOT NULL,   -- e.g. 'DE_blue_card_v2024'
  form_name             TEXT NOT NULL,
  corridor_to           TEXT NOT NULL,
  visa_type             TEXT NOT NULL,
  form_url              TEXT,
  form_field_id         TEXT NOT NULL,   -- AcroForm field name
  ...
  vault_field_path      TEXT NOT NULL,   -- field name in employee_profiles
  format_rule           TEXT,
```

There is **no** `UNIQUE (form_id, form_field_id)`, **no** `form_version_id`, **no** `field_kind` / `transform_spec`. RLS is `ENABLE` + `SELECT TO authenticated USING (true)` + service_role ALL; there is **no** `REVOKE ALL … FROM anon` on this table (contrast the hard gate in `CLAUDE.md`).

**Runtime consumers (will break if `form_id` is replaced or becomes non-unique across versions):**

| Consumer | What it assumes |
|---|---|
| `_load_field_mappings` | `WHERE form_id = :form_id` — all rows for that string; no version filter. `form_prefill_service.py:620–632` |
| `get_available_forms` | `GROUP BY form_id, form_name, corridor_to, visa_type` — catalogue = distinct `form_id`s. `:592–605` |
| `visa_types_for_corridor` | `SELECT DISTINCT visa_type … WHERE corridor_to` — `:563–589` |
| `generate_prefilled_pdf` | loads by `form_id`, fills, uploads. `:670–707` |
| `_download_template` | Storage object **`{form_id}.pdf`**. `:639–642` |
| `_upload_output` | `{case_id}/prefilled/{form_id}.pdf` with `upsert: true`. `:645–654` |
| `immigration_forms` router | HR + employee `available-forms` / `generate-form`; body is `{form_id: str}`. `backend/app/routers/immigration_forms.py:48–50, 134–239` |
| Frontend | `frontend/src/api/immigrationForms.ts` posts `{ form_id }`; `ImmigrationFormsPage.tsx` / `ImmigrationFormFill.tsx` key UI on `form.form_id` |
| Seed migrations | DELETE+INSERT by `form_id`: `20260605800000`, `20261135000000` (FR re-seed), `20261136000000` + `20261137000000` (ES + DOB split) |
| Tests | parse those SQL files by `form_id` (e.g. `test_fr_cerfa_real_pdf_fill.py:27–43`) |
| Seed script | uploads `form-templates/{form_id}.pdf` with **upsert**. `backend/scripts/seed_immigration_form_templates.py:77–81` |

**What breaks under a hard re-key to `form_version_id`:** every SQL above; template download (hash-addressed keys ≠ `{form_id}.pdf`); `get_available_forms` would list every edition unless filtered to `form_definitions.active_version_id`; the employee/HR API and SPA would need a new id type.

**Safe migration path (keep FR/ES live throughout):**

1. **Additive only.** `ALTER` add nullable `form_version_id`, `field_kind DEFAULT 'text'`, `transform_spec`. Do **not** drop or rename `form_id`. Existing SELECTs stay valid; `check_column_read_before_apply.py` (`.github/workflows/ci.yml:982`) forbids merging code that SELECTs the new columns in the same PR as the migration.
2. Backfill: one `form_definitions` + one `form_versions` row per existing `form_id` (`FR_cerfa_14571_v2024`, `ES_ex17_v2024`, `DE_blue_card_v2024`), then set `form_version_id` on current mapping rows. `active_version_id` points at that row.
3. Switch readers **after** apply: `_load_field_mappings` / `get_available_forms` join `form_definitions` and filter `active_version_id`, still exposing the stable logical id to the API as today’s `form_id` (or keep `form_id` as the public handle).
4. Change Storage key **only** for new versions; keep serving `{form_id}.pdf` (or copy/alias) until the download helper is updated.

Re-keying in the same PR as the fill refactor will take FR/ES offline the moment the code deploys before the operator applies DDL (this repo has **no** apply-on-merge — `CLAUDE.md` migration discipline).

**Related collision:** `form_id` already *looks* like an edition (`…_v2024`). `public.form_templates` (`20260521000000_dossier_forms_core.sql:56`) is a **different** catalog (System A dossier). The spec’s `form_definitions` is a third catalog unless it is explicitly the successor of System B’s `form_id`, not of System A. Spec §2 already says System A/B unification is a non-goal — keep `form_definitions` as the System B logical-form table and do not join it to `form_templates` in Phase 1.

---

## Q2 — Migration feasibility

**Repo reality (not theoretical):**

- Apply-on-merge does not exist. Operator apply + ledger reconcile. Never `supabase db push` (`CLAUDE.md` “Migration discipline”).
- Applier jammed at `MIGRATIONS_FAILED` since 2026-04-22; 148 pending versions interleaved with later applied ones. A 7-table file is fine **as a committed file**; it is **not** auto-applied, and it must not be assumed live when code merges.
- Timestamp must beat **both** repo max and prod ledger max (`CLAUDE.md`).
- New `public` tables need RLS + policy + `REVOKE anon`. The *existing* `form_field_mappings` table already fails the third of those (`20260518120000:648–658`) — new tables must not copy that pattern.
- “Register ALTERs in the PG16-parity lane” is **not** a general ledger. The lane is `backend-tests-postgres` (`.github/workflows/ci.yml:592–606`, `postgres:16`) replaying a **curated** `_AUTHORITATIVE_DDL` in `backend/tests/postgres/conftest.py:49–70`. That list today is attestation + funding grants only. Form tables are **not** in it. Register there only if you add `@pytest.mark.postgres` tests that replay these migrations. The real “don’t SELECT new columns before apply” gate is `scripts/check_column_read_before_apply.py`.

**Is 7 tables realistic?** As *one* idempotent migration file, yes — but it is a large operator apply, and Phase 1 as specified also re-keys the live fill table. That combination is not realistic for a single primary maintainer on a jammed applier.

**Smallest schema slice that unblocks a useful Phase 1 without the risky set:**

```sql
-- one file, additive, no re-key
ALTER TABLE public.form_field_mappings
  ADD COLUMN IF NOT EXISTS field_kind TEXT NOT NULL DEFAULT 'text',
  ADD COLUMN IF NOT EXISTS transform_spec JSONB;
-- optional, nullable, no FK to a table that does not exist yet:
-- form_version_id TEXT
```

Defer `form_definitions` / `form_versions` / demand / queue / `mapping_runs` / `verification_runs` until a later migration, after fill behaviour is data-driven on the current `form_id` key.

If you still want a logical-form table early: **two** tables (`form_definitions`, `form_versions`) + nullable FK, no queue, no provenance tables. Queue tables are useless until Phase 6.

---

## Q3 — Serve/LLM isolation guard efficacy

**Source of truth:** `scripts/check_serving_llm_isolation.py`. CI job at `.github/workflows/ci.yml:814`.

**(a) Is `form_prefill_service` inside `SERVING_ROOTS`?** **No.** Roots are:

```68:83:scripts/check_serving_llm_isolation.py
SERVING_ROOTS: Tuple[str, ...] = (
    "backend.app.services.requirements_builder",
    "backend.app.services.rules_engine",
    "backend.app.services.requirement_evaluation_service",
    "backend.app.services.immigration_requirement_service",
    "backend.app.services.hr_policy_resolver",
    "backend.app.services.data_sheet_service",
)
```

`form_prefill_service` is not listed. Nothing in `backend/app/services/` imports it except itself (datasheet_export only mentions it in a comment, `:35`). So the fill path is **outside** the closure today.

The spec’s “`form_prefill_service` is System B / authoring, not a serving root” (`design.md` §4) is **half true**: it is not a serving root. It is **not** authoring. It is the **live employee/HR fill path** that writes a government PDF (`generate_prefilled_pdf`, `immigration_forms.py:107–131`). Calling it “authoring” will cause someone to put the mapper next to it.

`data_sheet_service` **is** a serving root (`:82`) and imports `fact_dictionary` (`data_sheet_service.py:33`). That is the dictionary the mapper would bind to. Fine as long as `fact_dictionary.py` stays LLM-free (it is: a module-level `_FACTS` list, no version field).

**(b) Would the guard fail if the mapper were import-reachable from a serving root?** **Yes**, including lazy imports. The script AST-walks all import nesting (`imports_of`, `:184–224`) and BFS-walks from each root (`check`, `:392–397`). A function-local `from .llm_client import complete` is recorded (`module docstring:17–20`). If `mapper.py` imports `llm_client` / an SDK, and any serving root can reach `mapper`, CI exits 1.

Registering `app/authoring/form_onboarding/mapper.py` as a new gateway is **not** required if it imports `llm_client` (already in `LLM_GATEWAY_MODULES`, `:88–98`). It **is** required if it calls OpenAI over raw HTTP without an SDK / without `llm_client`.

**(c) Fill-path isolation: does the guard cover it?** **No.** Hard gate #1 in the spec (“mapper import-unreachable from every `SERVING_ROOT` **and** the fill path”) is **not** what the script asserts. `form_prefill_service.generate_prefilled_pdf` could `from .authoring…mapper import …` and the guard would still print OK.

**Required spec change:** add a `FILL_ROOTS` (or put `backend.app.services.form_prefill_service` in `SERVING_ROOTS` — slightly wrong conceptually, but it is the only list the guard walks). Also add `backend.app.routers.immigration_forms` if you care about the HTTP handler. Do not claim the existing script already enforces fill isolation.

---

## Q4 — `CHOICE_GROUPS` → data refactor safety

**All code consumers** (grep on `*.py`):

- Definitions + fill: `form_prefill_service.py` `CHECKBOX_ON` `:276–280`, `_GENDER_CODES`/`_MARITAL_CODES` `:287–307`, `RadioField` `:310–317`, `CHOICE_GROUPS` `:323–352`, `build_choice_fill` `:355–408`, `_resolve_checkbox_states` `:436–452`, `fill_acroform` `:455–504`, `generate_prefilled_pdf` `:685–688`, `build_synthetic_acroform` `:714–726`.
- Tests: `test_form_choice_fill.py`, `test_fr_cerfa_real_pdf_fill.py:76`, `test_es_ex17_real_pdf_fill.py` (same pattern).

**Date-part rules are already data**, not `CHOICE_GROUPS`. They are `format_rule` values `date_day|date_month|date_year` in `apply_format_rule` (`form_prefill_service.py:172–179`) and seeded in `20261137000000_es_ex17_dob_split.sql:29–34`. Moving date-parts into `transform_spec` is a **rename** of an existing column. The radio/checkbox layer is the real move: FR/ES radios are **explicitly not** in `form_field_mappings`:

```11:13:supabase/migrations/20261137000000_es_ex17_dob_split.sql
-- The Sexo and Estado Civil single-radio fields are filled by build_choice_fill
-- (CHOICE_GROUPS["ES_ex17_v2024"], code — not the mappings table), matching how
-- the FR CERFA radios are handled.
```

Same note in the FR re-seed (`20261135000000:15–19`).

**36 tests — count is correct if you include five files, not four.** The brief names four; the suite is:

| File | `test_*` methods |
|---|---|
| `test_imm11_form_prefill.py` | 16 |
| `test_form_choice_fill.py` | 11 |
| `test_fr_cerfa_real_acroform.py` | 4 |
| `test_fr_cerfa_real_pdf_fill.py` | 2 |
| `test_es_ex17_real_pdf_fill.py` | 3 |
| **Total** | **36** |

They will **not** pass unchanged if `build_choice_fill` only reads `form_field_mappings` rows: today `CHOICE_GROUPS` is in-process, tests call `build_choice_fill(FORM, profile)` with **no DB**. Real-PDF tests parse SQL for *text* mappings and still call `build_choice_fill` for radios (`test_fr_cerfa_real_pdf_fill.py:73–77`). After the refactor you must either (1) inject mapping rows into `build_choice_fill`, or (2) keep a test double. “Pass unchanged” is only true if the public behaviour (which button/`/Hombre` is written) is identical **and** tests are updated to feed the same groups as data.

**Hidden coupling the spec underplays:**

1. **Synonym tables are still code.** `_canonical_choice` (`:301–307`) maps `femme`/`marié`/… → `M`/`MARRIED`. `transform_spec` `{"male":"/Hombre"}` does not replace that unless you also persist the synonym map. Tests in `test_form_choice_fill.py:26–35` lock those synonyms.
2. **`CHECKBOX_ON` sentinel + `_resolve_checkbox_states`.** Fill emits `/Yes`; `fill_acroform` rewrites to the template’s real on-state (`:478–482`). Real CERFA uses `/On` (`test_fr_cerfa_real_pdf_fill.py:9–10`). Data rows must keep the sentinel contract, not bake `/Yes` as the stored export.
3. **`reconcile_report_against_pdf`** (`:507–556`) only checks `/V` non-empty on `form_field_id`. It does **not** compare expected vs actual value. A swap of two filled fields both non-empty still reports `filled`. That is why v2’s sentinel gate is not “the 36 tests.”
4. **`generate_prefilled_pdf` merges choice after `build_fill_plan`** (`:683–688`). If choice rows are also in `_load_field_mappings`, you can double-write or skip — query must exclude `field_kind` in (`single_radio`,`checkbox_option`) from the text plan, or `build_choice_fill` must be the only consumer of those rows.

**Will FR/ES behaviour preserve?** Yes *if* you migrate `CHOICE_GROUPS` 1:1 (including FR checkbox groups vs ES `RadioField` shapes) and keep `_canonical_choice` + checkbox resolution in code. The 36 tests are a necessary regression net, not a sufficient semantic net.

---

## Q5 — Atomic publish across Postgres and Storage

**How Storage is used today:** service-role client (`get_supabase_admin_client`, `supabase_client.py:52–66`). Templates: `download(f"{form_id}.pdf")`. Outputs: `upload(..., {upsert: "true"})` (`form_prefill_service.py:649–653`). Seed templates also **upsert** (`seed_immigration_form_templates.py:78–81`). There is **no** two-phase Storage API and no DB transaction around Storage.

**Implication:** the spec is right that Postgres cannot transactionally commit an object. The live code’s `upsert: true` on `{form_id}.pdf` is the **opposite** of immutable artifacts — a publish that overwrites `{form_id}.pdf` *is* a destructive replace of the live template.

**Achievable sequence (matches v2 intent, not current helpers):**

1. Upload to a **new** key only, no upsert: `form-templates/versions/{form_definition_id}/{sha256}.pdf`. Treat any existing object at that hash as success (idempotent).
2. Verify bytes (`pdf_sha256`) and run gates against that object.
3. INSERT version-scoped mapping rows + `form_versions` row `status=verified` in **one** DB transaction.
4. UPDATE `form_definitions.active_version_id` (and old version → `superseded`) in a **second** short DB transaction. Crash before (4) → previous live pointer + previous `{form_id}.pdf` (or old `artifact_key`) unchanged.
5. **Do not** overwrite `{form_id}.pdf` until/unless a separate compatibility copy is written *after* the pointer swap, and never delete the old hash object.

Rollback = pointer swap only (`design.md` §10). That part is DB-only and is atomic. Spec should say explicitly: Storage write is **outside** the DB transaction; uniqueness of `artifact_key` + “never upsert live key” is the Storage invariant.

`statement_timeout=20000` / `lock_timeout=8000` (`db_config.py:116–117`) apply to the app engine. Publish SQL must stay tiny; do not hold a transaction open across the upload.

---

## Q6 — Durable queue on the transaction-mode pooler

**Facts:**

- Prod `DATABASE_URL` is the Supabase **transaction-mode** pooler, port **6543** (`CLAUDE.md` env; `db_config.py:51–61`).
- Session-level features fail there: `SET ROLE`, prepared-statement reuse (`CLAUDE.md:382–383`; `docs/security/rls-second-barrier.md:57–59`).
- `FOR UPDATE SKIP LOCKED` does **not** appear anywhere in the repo today (only in this spec). No in-tree pattern to copy.
- Engine kwargs set `statement_timeout=20000` (`db_config.py:117`). A claim transaction that does network/LLM work will be killed.

**Does `SKIP LOCKED` work on 6543?** **Yes, if the claim is one short transaction** that writes `lease_owner` / `lease_expires_at` and **commits before** fetch/LLM. Row locks are transaction-scoped; pgbouncer transaction mode releases the connection at COMMIT. That is exactly the spec’s “claim, commit, *then* network” (`design.md` §11).

**What does *not* work on 6543:** holding `FOR UPDATE` across HTTP; `pg_advisory_lock`; `LISTEN/NOTIFY`; session `SET`. Do not “fix” the queue with those.

**Session-mode (5432) is not required** for this lease design. It *is* required for `supabase migration list` / `SET ROLE` proofs. Point the GH worker at the same 6543 URL the app uses **or** a dedicated 5432 URL; both are valid if claim SQL is one transaction. Prefer 6543 + existing `sslmode`/`postgres.PROJECT_REF` rewrite so the worker does not invent a second connection dialect.

**Do not** reuse the request engine’s 20s statement timeout for a worker that keeps a connection idle during OpenAI — because the spec already commits first, the next statements are new transactions. Fine.

---

## Q7 — Executor + secrets reuse

**Closest existing jobs:**

| Workflow | Pattern | Secrets |
|---|---|---|
| `immigration-indexer.yml` | `workflow_dispatch`, `ubuntu-latest`, pip from `backend/requirements.txt`, **repo** `DATABASE_URL` + `OPENAI_API_KEY`, fail-fast if missing | `:21–49` |
| `reindex-corridor-chunks.yml` | same two secrets | |
| `outbox-dispatch.yml` | **schedule + `workflow_dispatch`**, `concurrency.group` with `cancel-in-progress: false`, gated on `vars.*`, calls the **API** with `CRON_SECRET` rather than holding DB keys | `:18–32` |
| `rag-eval-reports.yml` | `DATABASE_URL` + `OPENAI_API_KEY` | |

**There is no GitHub Environment** in `.github/workflows` (grep for `environment:` → none). Secrets are repo-wide. SHA-pinning is mostly `@v4`/`@v7` tags, not commit SHAs. `immigration-indexer` does **not** hold `SUPABASE_SERVICE_ROLE_KEY`; fill/publish **must**, because Storage goes through `get_supabase_admin_client()` (`supabase_client.py:61–65`).

**Reuse recommendation:** copy `outbox-dispatch`’s concurrency + schedule-as-sweep, and `immigration-indexer`’s Python/setup. Add `SUPABASE_SERVICE_ROLE_KEY` + `OPENAI_API_KEY` + `DATABASE_URL`. Do not run this on Render (free plan, `--workers 1`, spin-down — `CLAUDE.md:143–145`).

**Least-privilege worker DB role:** designed, **not live**. `relopass_api` exists in a migration; `RELOPASS_API_DATABASE_URL` falls back to the superuser URL until a human provisions it (`db_config.py:77–99`; `rls-second-barrier.md:71–74`). Grants today are for `policy_assistant_chunks`, not form tables. Storage has no finer key than the service role in this client.

**Realistic isolation story for Phase 6:** one dedicated **GitHub Environment** (`form-onboarding-worker`) with the service role + LLM key (the spec’s “isolated to one workflow” — that Environment does not exist yet). A custom Storage-only key is not how `supabase-py` is wired. A custom DB role is a **human** follow-up, same runbook as `relopass_api`; do not block the worker on it. Spec’s open question §16 is correct; the default should be “isolated service key in an Environment,” not “invent a DB role in the first worker PR.”

---

## Q8 — Reuse vs greenfield

| Building block | Reuse? | Notes |
|---|---|---|
| RLS template | Partial | `form_field_mappings` is a bad template (open `authenticated` SELECT, no `REVOKE anon`). Prefer `ai_decisions` (`20260527000000:55–84`) + the CLAUDE.md trio. These tables are **catalog/system**, not tenant case data — `USING (true)` for authenticated read of *definitions* may be OK; writes service_role only; **must** `REVOKE anon`. |
| Authoring location | `backend/app/authoring/` **does not exist** (glob: 0 files). LLM authoring today is `backend/app/services/` (`llm_client`, `policy_extractor.py:381`, `llm_policy_extractor.py`). Spec path `app/authoring/form_onboarding/mapper.py` is a **new package**. That is the right cut so serving roots never import it. Do not put the mapper in `backend/app/services/` next to `form_prefill_service`. `backend/agents/` are rule orchestrators, not LLM — do not put the mapper there (`CLAUDE.md`). |
| Fill primitives | **Reuse as-is** | `fill_acroform`, `build_fill_plan`, `_resolve_checkbox_states`, `reconcile_report_against_pdf` are the verification substrate. Do not rewrite pypdf fill for onboarding. |
| Worklist | **Catalog of names, not a fetch allowlist** | `docs/form-autofill/form-acquisition-worklist.md` is 498 pairs / 57 coded-PDF **heuristics**, including **tax** (ATO NAT 3092, IRS 1040, HMRC CA3837, …). Spec §2/§12 forbids inferring tax from immigration. Using this file as the acquisition allowlist would onboard tax forms. Treat it as a search index; the allowlist must be a **server-side immigration-authority host list**, not this table. |
| `fact_dictionary.py` | Vocabulary **without** versioning | `FactEntry` has `fact_key`, `label`, `category`, `professional_review_required`, `prefill_source`, `field_ids` (`:43–57`). **No** `version`, **no** hash, **no** enum/export-state schema. Lookup is `prefill_source` then `field_id` (`:138–149`), while mappings store **bare vault columns** (`legal_last_name`). Join is “prefill_source tail == vault_path” (`test_fact_dictionary.py:31–38`). Spec’s `fact_dictionary_version` and “every `source_enum` value defined by the bound dictionary version” **do not exist**. Mapper target `fact_key` ≠ fill’s `vault_field_path` — you need an explicit join (or persist `vault_field_path` on the mapping as today). Dictionary also contains **tax/social-security** facts flagged `professional_review_required` (`:115–126`) — mapper must refuse those (spec §12); the flag is the hook. Hash the module source (or a frozen JSON dump) if you need a version string; don’t pretend a column exists. |

---

## Q9 — Spec claims about the code that may be wrong

| Spec claim | Code |
|---|---|
| `form_prefill_service` is “System B / authoring, not a serving root” | Not a serving root: true (`check_serving_llm_isolation.py:68–83`). **Authoring: false.** It is the live fill service. |
| Isolation guard covers the fill path | **False** (Q3). |
| “the 36 form-fill tests” | **True** across **five** files (Q4). Brief omitted `test_fr_cerfa_real_acroform.py`. |
| Dual router registration | **True** and already done for today’s forms API: `backend/main.py:904`, `backend/app/main.py:224`. New onboarding routes need the same. Prod boots `backend.main:app`. |
| “register ALTERs in the PG16-parity lane” | Overstated. Lane is a **curated** `_AUTHORITATIVE_DDL` (`conftest.py:26–35, 49–70`), not “every ALTER.” Form mappings are not in the lane. |
| `app/authoring/` layer | **Does not exist.** |
| `form_field_mappings` + `transform_spec` replaces `format_rule` | Live fill **only** reads `format_rule` (`_load_field_mappings:624–625`, `apply_format_rule:144–180`). Date-parts already live there. |
| Mappings keyed to `form_id` today | True; `form_id` is also the Storage object name. |
| Demand API under `/api/employee/cases/.../forms/{form_definition_id}/onboarding` | Today’s contract is `.../immigration/available-forms` + `generate-form` with string `form_id` (`immigration_forms.py:194–239`, `immigrationForms.ts`). Spec is a **new** surface, not an extension of the existing one. Wire into `immigration_forms.py` rather than a greenfield router if you want one dual-registration site. |
| Render “native, no apt” in `CLAUDE.md` | **Not in `CLAUDE.md`.** What *is* there: free plan, `--workers 1`, spin-down (`:143–145`). Worker should be GH Actions (`ubuntu-latest` **can** `apt-get`). Do not run acquisition/parse/render on Render. |
| Worklist as authority/source catalog | Heuristic, multilingual **and tax-heavy** (Q8). |
| `0 not_in_pdf` as structural proof | `reconcile_report_against_pdf` only tests non-empty `/V` (`:531–536`). Spec v2 already knows this; the **code** still has no sentinel compare. |

Stale nearby doc: `docs/form-autofill/FINDINGS.md` H1 says the frontend never calls generate-form; that is **obsolete** (`immigrationForms.ts`, `ImmigrationFormsPage.tsx`). Do not take FINDINGS as current wiring.

---

## Q10 — Effort & sequencing realism

v2 Phases 1–8 as a single program is **not** realistic: monolith + dual router registration, jammed migration applier, operator-applied DDL, free Render (so the worker **must** be Actions), one maintainer, and a fill path whose IDs/Storage keys are the product.

Phase 1 as written (7 tables + version-scoped mappings + keep FR/ES unchanged) is the **highest-risk** first merge: it changes the live catalogue key before the data-driven fill exists.

**Cut / defer:** provenance tables (`mapping_runs`, `verification_runs`) until Phase 4–5; demand≠work tables until Phase 6; rendering/reference-viewer until a GH Actions image with poppler/pdfium exists; least-privilege DB role; source-freshness (Phase 9); any tax form on the worklist.

**Keep:** precision-over-recall; four gates as *product* requirements; SSRF on whatever eventually fetches; dual registration; PII canary; isolation **with a fill root**.

---

## Standards-review blockers vs this code

1. **Semantic verification / sentinel round-trip — implementable?** **Mostly, with a new helper, not with `reconcile_report_against_pdf`.** You can `fill_acroform(template, {field: unique_sentinel})` then `PdfReader.get_fields()` (same as reconcile `:522–536`) and assert `str(/V) == sentinel` **and** that no other mapped field contains that sentinel. That catches field swaps. It does **not** prove the box is the right *question* (v2’s semantic gate). Unique sentinels must respect `/MaxLen` and radio export enums (`/Hombre`, not `ALPHA17`). Radio/checkbox: write the real export state, not a random string. `set_need_appearances_writer(True)` (`fill_acroform:493–500`) is not a rendering check.

2. **Form edition / atomic publish** — Q1 + Q5. Today’s `{form_id}.pdf` + upsert is a mutable live object. Spec’s hash key is a real change to `_download_template`.

3. **SSRF acquisition — where it runs.** **GitHub Actions `ubuntu-latest`**, not Render. Limits (timeouts, max bytes) are enforceable in Python in that job; IP/DNS checks are enforceable there too. Isolated parse = same job, pypdf limits; there is no extra sandbox in-repo. France-Visas 403 is already on-record (`20261135000000:21–26`) — auto-acquire of CERFA will `blocked_source_access`; the fixture PDF in `docs/form-autofill/artifacts/` is how tests work today. Spec’s “human-supplied PDF resumes” is the only way CERFA stays in the pipeline.

4. **Queue/publish** — Q5/Q6. Lease-then-commit is pooler-safe; cross-store atomicity is not.

---

## Prioritized code-grounded spec changes

1. **Stop calling `form_prefill_service` authoring.** It is the fill path. Add `FILL_ROOTS = (form_prefill_service,)` to `check_serving_llm_isolation.py` (or a sibling assertion). Spec hard gate #1 is otherwise false.
2. **Do not re-key `form_field_mappings` in the first schema PR.** Additive `field_kind` + `transform_spec`; keep `form_id` as the public/API/Storage handle until `_download_template` learns `artifact_key`.
3. **State that date-parts are already `format_rule` data**; only radios/checkboxes move out of code. Persist synonym maps or keep `_canonical_choice` in code.
4. **`build_choice_fill` tests are DB-free** — spec the test injection so “36 tests pass” is not read as “zero test edits.”
5. **Mapper targets:** bind to `fact_key` **and** `vault_field_path` (today’s fill column). Introduce `fact_dictionary` hash/version as a computed artifact, not a DB column that does not exist. Refuse `professional_review_required`.
6. **Worklist ≠ allowlist.** Immigration host allowlist is new data; worklist is a heuristic including tax forms, which §12 forbids.
7. **Publish sequence** as Storage-then-DB-pointer; forbid `upsert` on the live template key; change seed script accordingly.
8. **PG16 lane:** register migrations in `_AUTHORITATIVE_DDL` only if postgres-marked tests need them. The merge gate for “don’t read unapplied columns” is `check_column_read_before_apply.py`.
9. **Worker:** GH Actions Environment + service role; 6543 + claim-and-commit; do not require `relopass_api` for v1. `apt` is available on GHA, not assumed on Render.
10. **API:** extend `immigration_forms.py` (already dual-registered) rather than a new router; keep `form_id` in the employee SPA until a compatibility alias exists. New path with `form_definition_id` is a breaking frontend change (`immigrationForms.ts`).
11. **New tables:** RLS + policy + `REVOKE anon` (do not copy `form_field_mappings`’s missing revoke).
12. **`app/authoring/`** is a new package — say so; don’t imply it exists. Keep it off `backend/app/services/` import cycles with `data_sheet_service` / `fact_dictionary`.

---

## Recommended first-PR slice

**Not Phase 1 (7 tables). Not Phase 4 (LLM).**

**PR 0 / first implementation PR: data-driven fill on the current `form_id` key.**

1. Isolation: add `form_prefill_service` as a fill/serving root; prove a planted mapper import fails CI.
2. One additive migration: `field_kind`, `transform_spec` on `form_field_mappings` (RLS unchanged; no new tables). Do not SELECT the new columns in the same PR.
3. Follow-up PR (after operator apply): `build_choice_fill` reads version-unaware rows for `FR_cerfa_14571_v2024` and `ES_ex17_v2024`; keep `_canonical_choice` + `_resolve_checkbox_states`; seed radio/checkbox rows in **data** (service-role/SQL seed, or a second migration of INSERTs — INSERTs are data, but this repo historically uses migrations for mapping seeds).
4. Keep all 36 fill tests green (update fixtures/parsers as needed; behaviour identical).
5. Leave Storage as `{form_id}.pdf`. Leave APIs as `form_id`.

**Exit:** radios are data; FR/ES still fill; isolation actually covers fill. That disproves the riskiest *code* assumption (can we move `CHOICE_GROUPS` without breaking the real PDFs) **without** a 7-table apply or an LLM.

Then: tiny `form_definitions`/`form_versions` + nullable FK (true Phase 1), then acquisition on GHA, then mapper in `backend/app/authoring/`, then gates, then worker.

Phase 7’s “CERFA + EX-17 plus a diverse set” should not be automatic-acquire for CERFA (France-Visas 403). The pilot’s happy path for FR is **resume from the committed fixture**, not §6 fetch.
