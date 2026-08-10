# Research Task Playbook — schema & codebase investigations

How to phrase and run "find X / verify Y" research tasks in this workspace so they
succeed on the first pass. Born from the `relopass_vendors` DDL investigation
(2026-08-10), which nearly pointed at the wrong place because the request assumed
the table lived in the repo's Supabase migrations when it actually lives in
WorkspaceDB.

Use this playbook whenever a task asks: "find where X is defined", "report the
schema of X", "list everything that references X", or "confirm Y does not exist".

---

## Why research requests fail here (context)

1. **Two systems of record.** This workspace has BOTH a WorkspaceDB (platform
   tables like `app_relopass_vendors`, created via `workspace_db_create_table`)
   AND an imported repo snapshot (`imported-source/rolec-main/` with 555 Supabase
   migrations). A table name can exist in one, the other, both, or as near-miss
   aliases (`vendors`, `suppliers`, `vendor_providers`, `relopass_vendors`).
2. **No server-side grep.** The audos bridge exposes `list_files` / `read_file`
   only. "Search every file for string S" over hundreds of files is only feasible
   as: (a) full filename enumeration, plus (b) content reads of a candidate subset
   chosen by an explicit rule. Requests must define that rule or accept the agent's.
3. **Docs are evidence.** In-repo design docs (e.g. `supabase/seed/vendors/_SCHEMA.md`)
   often state authoritatively where something lives. Reading them early collapses
   the search space.

---

## The four pieces (run in order; stop early when answered)

### Piece 1 — Locate the system of record
- **Goal:** Determine authoritatively WHERE the object is defined: WorkspaceDB,
  repo migrations, or both. Do this BEFORE extracting anything.
- **Spec:** Check `workspace_db_list_tables` first; repo migration filenames second;
  design docs (`_SCHEMA.md`, `docs/*audit*.md`, `docs/*investigation*.md`) third.
  Name known aliases up front so they aren't conflated.
- **Plan:** One list call per source; stop as soon as one source claims ownership
  with corroborating documentation.
- **Metrics:** Exactly one definitive answer, with a cited source (tool output or
  doc quote) — not an inference.
- **Validation:** Two independent signals must agree (e.g. the live table's
  `createdBy`/`createdAt` AND a doc stating the design intent).
- **Evals:** Could a second agent, given only the report, reach the same location
  without re-searching? "It's probably X" = fail.

### Piece 2 — Extract ground-truth DDL
- **Goal:** Full column/constraint/index definition from the LIVE catalog, not prose.
- **Spec:** `workspace_db_describe_table` PLUS raw catalog queries via
  `workspace_db_raw_query`: `information_schema.columns`, `pg_indexes`,
  `pg_constraint`. Return verbatim catalog output AND a reconstructed CREATE TABLE.
- **Plan:** One query per catalog view.
- **Metrics:** Every column accounted for (count returned = count expected);
  constraints and indexes enumerated exhaustively.
- **Validation:** Describe-tool output and raw catalog must agree. (In the worked
  example the raw catalog also surfaced a second schema variant in another
  workspace schema that the describe tool alone would have missed.)
- **Evals:** Someone could recreate the table from the report alone.

### Piece 3 — Repo cross-reference (with an honesty clause)
- **Goal:** Confirm presence/absence of the object in the repo.
- **Spec:** State the exact strings to search (the object name + alias list) and
  the candidate-selection rule (e.g. any filename containing `vendor`, `supplier`,
  `relopass`, plus ALL baseline/`remote_schema` dumps).
- **Plan:** Enumerate every filename; content-read candidates only.
- **Metrics:** Files enumerated / files content-read / hits found — all three numbers
  reported.
- **Validation:** Absence claims cite the method ("filename scan of all N +
  content read of M candidates"), never "searched everything" when only a subset
  was content-read.
- **Evals:** The absence claim is auditable: the report lists which files were
  content-read so a reviewer can extend the search rather than redo it.

### Piece 4 — Dependency map
- **Goal:** Everything that references the object.
- **Spec:** FK query against `pg_constraint` in BOTH directions (referencing and
  referenced); optionally scan app files that read/write the table at runtime.
- **Plan:** One catalog query; targeted app-file reads if runtime usage matters.
- **Metrics:** Zero unexplained references; each hit named with its definition.
- **Validation:** Cross-check against the describe tool's `foreignKeys` field.
- **Evals:** A migration or rename plan could be written from the map alone.

---

## Request template (paste and fill)

```
RESEARCH ONLY — make zero changes to any file.

Object: <table/function/config name> (known aliases: <list — or "none">)
First confirm where this object is actually defined — do NOT assume the repo.
Sources to check, in order: WorkspaceDB, imported repo (<path>), design docs.

Report:
1. System of record, with cited evidence.
2. Full ground-truth definition (raw catalog excerpts + reconstructed DDL).
3. Repo cross-reference: search strings <S1, S2, ...>; candidate rule
   <e.g. filenames containing X, plus baseline dumps>; report files
   enumerated / content-read / hits.
4. Everything referencing it (FKs both directions; app usage if relevant).
5. If absent from a source, say so explicitly and state the search method used.

Return raw excerpts, not paraphrases.
```

---

## Worked example — `relopass_vendors` (completed 2026-08-10)

- **Piece 1:** WorkspaceDB table `app_relopass_vendors`, created 2026-07-18 by
  `audos-code` via `workspace_db_create_table`. Corroborated by
  `supabase/seed/vendors/_SCHEMA.md`: "As of 2026-07-18 no migration for that
  table exists in this repo." NOT in the repo's migrations.
- **Piece 2:** 22 columns; `serial id` PK; `UNIQUE (vendor_key)`; index on
  `session_id`; defaults `is_preferred=false`, `verification_status='unverified'`,
  `created_at`/`updated_at=now()`; NO CHECK constraints (enum-like columns are
  doc-enforced only).
- **Piece 3:** All 555 migration filenames enumerated (none names it); content-read
  candidates: both `remote_schema` baselines (zero occurrences of "vendor"),
  `vendor_directory_extension`, `vendor_metric_snapshots`, `deprecate_vendors_write`,
  `quote_requests_vendors`, `relopass_case_engine_v1`, `relopass_api_rls_barrier`,
  `harden_pac_select_relopass_api_safe_uuid`. Repo's vendor tables are
  `public.vendors`, `public.suppliers`, `public.vendor_metric_snapshots` — distinct
  objects, do not conflate.
- **Piece 4:** Zero foreign keys in either direction (`pg_constraint` scan).
