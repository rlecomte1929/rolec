# Corridor-import automation harness — design spec

- **Status:** DRAFT — awaiting founder review
- **Date:** 2026-09-08
- **Author:** Claude Code (wired applier + coordinator)
- **Branch:** `claude/relopass-import-automation-4327e6`

## 1. Goal

One command that, given an Otto GCS manifest URL **or** an already-fetched
`docs/imports/<batch>/` directory, runs the whole **treatment** of a corridor-fact batch
deterministically and stops at a **promote dry-run report** — never an unattended prod write.

```
harness run <manifest-url | docs/imports/<batch>/>        # full dry-run: writes NOTHING to the DB
harness run <…> --stage                                    # opt-in: writes otto_staging (status='new'), then promote dry-run
```

The **real prod promote** (`import_otto_facts.py --promote`, scoped) and the **/admin/countries
lawyer approval** stay MANUAL, by design. The harness has **no code path that commits a promote or
persistently flips a staged row to `ready`.**

## 2. What it wires (the real tools, as they exist on this branch)

The harness is a thin orchestrator over CLIs that already exist. It adds **zero coupling** — it
subprocesses each tool and reads its exit code (CLAUDE.md: never modify the parsers/importer to fit
a batch).

| Stage tool | Real signature | Exit contract |
|---|---|---|
| `scripts/check_otto_batches.py` | `<batch-id>` \| `--all` `[--json report.json]` | 0 ok · 1 fail · 2 usage |
| `scripts/convert_*_to_otto_jsonl.py` (per-batch today) | `[--check]` | 0/nonzero |
| `scripts/verify_ledger.py` (**the referee**) | `<ledger.ndjson> [--apply] [--out DIR] [--no-fetch] [--config F]` | 0 ran/importable · 1 empty/nothing importable · 2 can't run |
| `scripts/verify_batch_quotes.py` | `<batch_dir> [--refetch] [--stamp]` (+ `--grounding-dir` to be added) | 1 if any quote missing/unreachable · else 0 |
| `scripts/import_otto_facts.py` | `<batch-id\|path> [--apply] [--promote] [--source-label S] [--expected N] [--batch-id B]` | 0 ok · 1 rejections · 2 not-found/parse/no-DB · 3 reconcile PARTIAL |
| `scripts/check_nationality_scope.py` | `[--db]` | 0 clean · 1 violations · 2 can't run |
| `backend/imports/otto/executor.py::promote` | `promote(session, *, country=None, dry_run=True)` — **no `run_ids=`; NOT batch-scoped** | — |

**Four corrections to the original brief, baked into this design:**

1. **There is no `confirm_quotes.py`.** The "referee" is `verify_ledger.py` (source-authority +
   V2 liveness + V3 quote-grounding, one pass) plus the standalone `verify_batch_quotes.py`. The
   spec's "confirm_quotes referee" and "verify_ledger source-authority" collapse into **one referee
   stage**.
2. **`promote()` takes `country=` only, and is not batch-scoped** — `promote(country=IN)` counts
   *every* `status='ready'` India row across *all* batches. The harness must enumerate what else is
   `ready` for the country before the dry-run (§8).
3. **The append-only "approved count + md5 fingerprint, expert_verified==0" tripwire is not inside
   `promote()`.** `promote()`'s own guard is a uuid5 id + a skip of any row already
   `verification_status ∈ {verified, expert_verified}`. The md5/approved-count fingerprint is
   **applier SQL** the harness captures as a baseline and I re-check after the real (manual) promote.
4. **No bridge client or GCS fetch exists in-repo.** Today Otto's files arrive via the
   `[audos-sync]` commit and are re-hashed by `check_otto_batches.py`. Stage 0 (ingest-from-URL) is
   net-new code, isolated to one stage; the local-dir entry point needs none of it.

Also: `import_otto_facts.py` reads `DATABASE_URL` **even in dry-run** (it reads existing keys to
compute "already present"). The harness always needs DB read access; it writes only under `--stage`.

## 3. Hard guardrails (unchanged) → where each is enforced

| Guardrail | Enforcement point in the harness |
|---|---|
| Promote-to-PENDING only | Stage 6 is `dry_run=True` + `ROLLBACK`; no real-promote path exists in the harness |
| Never an unattended prod write | Default writes nothing; `--stage` is the only DB-write path (staging, `status='new'`) |
| Append-only: approved count + md5 fingerprint unchanged, `expert_verified==0` per op | Stage 6 captures the pre-op fingerprint; the simulated promote runs in a rolled-back tx; the real post-promote re-check is applier SQL (§8) |
| Never bare `--promote`; scope by `country=` | Stage 6 promote is per-destination from the batch's own rows; stage 5 enumerates other `ready` rows for the country |
| Re-scope EEA registration/permit rows to `["EU_EEA"]` + run `check_nationality_scope.py` | Stage 5 pre-promote lint |
| NEVER `supabase db push` | Not invoked anywhere; the harness touches no migration path |
| Never fabricate a source/quote/number | Stage 3 rejects `UNOFFICIAL`; quotes confirmed only against a fetched-or-browser-grounded page; unconfirmed quotes surface in the worklist, never invented |
| Verify every quote independently (researcher's `quote_verbatim_confirmed` has been wrong) | Browser-grounding is an **applier hop** (§7), not a headless auto-confirm; a grounded quote lands REVIEW until I read it |
| Work in a worktree, commit explicit paths, PRs | Process, not code; the orchestrator + tool PRs come from Cursor and I integrate |
| Never bypass CAPTCHAs | Stage 3 marks CAPTCHA/geo-gated sources REVIEW and stops; it never attempts a bypass |

## 4. Architecture

A **resumable subprocess stage-machine.** Each stage is a pure function `(ctx) -> StageResult`
that shells out to one tool (or runs one in-process applier step), records its result to a
checkpoint, and either continues, gates (hard stop on failure), or **pauses** for an applier hop.

- **Language / runtime:** Python 3.11, `/Users/romainlecomte/Documents/GitHub/rolec/.venv311/bin/python`.
  Stdlib + the repo's existing deps only (no Playwright, no new heavy dep — see §7).
- **Entry:** `scripts/corridor_harness.py` (new). Subcommands: `run`, `resume`, `status`.
- **State / artifacts:** everything under `docs/imports/<batch>/_harness/`:
  - `run.json` — the checkpoint: batch id, entry point, resolved country set, per-stage status
    (`pending|ok|gated|paused|skipped`), timestamps, the tool exit code + a stdout tail per stage.
  - `reconcile.json`, `referee.stdout.txt`, `clean.ndjson`, `worklist.ndjson`,
    `grounding/` (applier-captured page text), `prepromote.json`, `promote_preview.json`,
    `fingerprint.baseline.json`.
  - `report.md` — the human-readable end-of-run summary (the "promote dry-run report").
- **Resumability:** `harness resume <batch>` re-enters at the first non-`ok` stage. Stages are
  idempotent: reconcile/referee/lint are pure reads; `--stage` is `ON CONFLICT DO NOTHING`; stage 6
  always rolls back. Re-running never double-writes.
- **Exit-code contract (harness → operator/CI):** `0` reached the promote dry-run cleanly ·
  `10` a hard gate failed (reconcile/referee/parse) · `20` paused for an applier browser hop ·
  `30` scope-guard violation (needs an applier fix before staging) · `2` usage/config error.
  A pause (`20`) is not a failure — it is the designed hand-off to me.

### Stage order (corrected)

Reconcile runs on the **raw delivered** files (the manifest's sha256 is over what Otto shipped),
*before* conversion rewrites them.

```
0 INGEST       URL → bus-pull + GCS-fetch → docs/imports/<batch>/   |  local dir → skip
1 RECONCILE    check_otto_batches.py  — sha256 + counts + citation quality vs manifest   [HARD GATE]
2 CONVERT      convert_*_to_otto_jsonl → parsers vocab (both spellings; require applies_to.status; nationality FROM artifact)
3 REFEREE      verify_ledger.py (+ verify_batch_quotes.py) → clean.ndjson / worklist.ndjson
                  └─ unreachable sources → PAUSE for applier browser hop → resume (§7)
4 STAGE        import_otto_facts.py --apply --expected N → otto_staging (status='new')   [DB write, --stage only]
5 PRE-PROMOTE  scope-guard lint: purpose='other' fallthrough · EEA rows not ["EU_EEA"]
                  (check_nationality_scope) · UNMAPPED nationality · enumerate other 'ready' rows
6 PROMOTE-DRY  simulate ready-flip in BEGIN…ROLLBACK; promote(country=ISO, dry_run=True);
                  capture before/after count + approved-count + md5 fingerprint + expert_verified==0
                  ── STOP. Write report.md. ──
```

Applier-only, **outside** the harness: flip `status→ready` (scoped) · real
`import_otto_facts.py --promote` · the post-promote md5 re-check · the /admin/countries lawyer gate.

## 5. Stage specifications

### 0 · INGEST
- **URL entry:** pull the delivery message from the bridge (`{action:"pull",direction:"otto_to_claude"}`,
  secret from `~/.otto-bridge-secret`, header only), extract the manifest + NDJSON GCS URLs, fetch
  the objects byte-for-byte into `docs/imports/<batch>/`. (Net-new; the only stage that touches the
  bus/GCS. Cursor builds a testable client with the bus/GCS calls injectable so acceptance tests run
  offline against a local fixture.)
- **Local entry:** `<dir>` already contains `manifest.json` + the NDJSON — skip fetch.
- **Output:** a populated batch dir + `run.json` seeded. **Never** acks the bus row until the batch
  is committed to the repo (an un-committed GCS object is one bucket-cleanup from gone).

### 1 · RECONCILE — hard gate
- Run `check_otto_batches.py <batch-id> --json _harness/reconcile.json`.
- **Gate:** exit ≠ 0 → harness exit `10`, stop. The manifest's declared record count, line count,
  every histogram, each declared source's citation count, and the NDJSON's own size + **sha256**
  must match disk. A discrepancy is the batch's problem to explain, not ours to reconcile away.

### 2 · CONVERT
- Detect the delivered vocabulary; run the vocabulary converter (§11 item C) to emit the parsers
  vocabulary (`entity_topic_key`, `entity_title`, `destination_country`, `fact_key`) **and** the
  loader/gate vocabulary (`target_table`, `topic_key`, `entity{}`, `confidence_score`) — both
  spellings, asserted equal. Requires `applies_to.status` (absent ⇒ silent `purpose='other'`).
  Reads `applies_to_nationality_classes` **from the artifact** — never derives it from the corridor.
- If the batch is already in parsers vocab, this is a pass-through (recorded as `skipped`).
- **Output:** `<batch>/clean-input.ndjson` (converter output), fed to stage 3.

### 3 · REFEREE
- Run `verify_ledger.py <clean-input.ndjson> --apply --out _harness/`. Produces `clean.ndjson`
  (importable) + `worklist.ndjson` (rejected). Records source-authority mix, V2 liveness, V3
  grounding.
- Run `verify_batch_quotes.py <batch_dir>` for per-quote verbatim confirmation.
- **Unreachable sources** (V2 `source_failed` / robots-skipped / JS-SPA / PDF that the HTTP fetch
  can't confirm a quote on): collect `{source_url, evidence_quote, dedupe_key}` into
  `_harness/grounding/worklist.json` and **PAUSE** (harness exit `20`). See §7.
- **Gate:** `verify_ledger` exit 1 (nothing importable) or 2 (can't run) → harness exit `10`.
  A non-empty `clean.ndjson` with some unconfirmed quotes is **not** a gate — those rows may stage
  at `status='new'`, but stage 6's report flags every unconfirmed quote and I read them before any
  real promote.

### 4 · STAGE — `--stage` only, DB write
- Run `import_otto_facts.py <clean.ndjson> --apply --expected <manifest.record_count>
  --source-label <label>`. Writes `otto_staging.immigration_entities` +
  `immigration_fact_candidates` at `status='new'`, a `load_log` row, a `processing_queue` update.
- **`--expected` is mandatory** or a clean full load exits 3 (PARTIAL). The harness reads it from
  the manifest — normalising across the two manifest shapes in the repo (`files.<name>.records` in
  the sg-ec manifest vs a per-artifact `record_count` in B3). The count is the referee's importable
  count after stage 3, not the raw delivered count, when the two differ (rejections removed).
- **Exit handling:** 0 ok · 1 rejections (should be empty — stage 3 already removed them; a
  non-zero here means drift, gate `10`) · 2 fatal (`10`) · 3 PARTIAL (surface loudly; the batch is
  incomplete against its own manifest — gate `10`).
- Without `--stage`, this stage runs `import_otto_facts.py <clean.ndjson>` (dry-run) instead, and
  the promote preview in stage 6 reports "would stage N".

### 5 · PRE-PROMOTE LINT — scope guard
Deterministic reads over the staged (or would-stage) rows' `applies_to`:
- **purpose fallthrough:** any row whose `applies_to.status` is absent/unrecognised → will land
  `purpose='other'` and be invisible to the corridor call. List them; the per-draft purpose preview
  is the only warning (importer trap #6).
- **EEA re-scope:** any registration/permit-concept row not scoped `["EU_EEA"]`. Then run
  `check_nationality_scope.py --db`; exit 1 → harness exit `30` (applier fixes the staged
  `applies_to` in place — `status='new'`, dedupe_key stable — before proceeding).
- **UNMAPPED nationality:** rows whose `applies_to.nationality` is absent/disagreeing within a topic
  → never promote. List them.
- **Cross-batch `ready` enumeration:** count what else is already `status='ready'` for each of this
  batch's destinations, so the operator sees the *full* set a real `promote(country=ISO)` would
  sweep — not just this batch's rows.

### 6 · PROMOTE DRY-RUN — applier-owned, always rolled back
In-process (imports `executor.promote`), inside a single `BEGIN … ROLLBACK`:
1. Capture the **baseline fingerprint** for each destination country (§8):
   `approved_count`, `expert_verified_count`, and the md5 over the untouched-rows string_agg.
2. Simulate the human gate: `UPDATE …_fact_candidates SET status='ready' WHERE <this batch's rows>`
   (scoped to the batch; never the whole schema).
3. `promote(session, country=ISO, dry_run=True)` per destination → the promotable drafts + titles.
4. Re-capture the fingerprint *within the same tx* and assert: `expert_verified_count` unchanged and
   `== 0` delta, approved-count delta explained only by new pending rows, md5 over pre-existing rows
   unchanged.
5. `ROLLBACK`. Nothing persists — rows remain `status='new'`.
- **Output:** `promote_preview.json` (per-country: would-insert N, the titles, skipped-verified,
  unmapped) + `fingerprint.baseline.json`, folded into `report.md`.
- The harness **stops here** with exit `0`.

## 6. `report.md` — the promote dry-run report (the deliverable of a run)
One page: batch id · corridors/countries · reconcile PASS · referee mix (importable / promotable /
quotes confirmed vs unconfirmed, with the unconfirmed ones listed) · staged N (or would-stage) ·
scope-guard findings · per-country would-promote titles · the append-only baseline · and the exact
**manual** next commands (flip ready, real `--promote` scoped, /admin/countries). This is what a
human reads to decide whether to promote.

## 7. Browser-grounding protocol (applier hop)

Stage 3 pauses (exit `20`) with `_harness/grounding/worklist.json` = the sources the HTTP referee
could not confirm a quote on. Then:

1. **I** (applier) open each `source_url` in the in-app browser (`mcp__Claude_Browser__navigate` +
   `get_page_text` / `javascript_tool`), wait for JS render, and read the rendered DOM. If the page
   is a real CAPTCHA/geo-gate, I mark it `blocked` and move on — **never** a bypass.
2. I confirm the `evidence_quote` is present **verbatim** on the rendered page myself — the
   researcher's `quote_verbatim_confirmed` is not trusted (Indonesia BPJS, Taiwan). I save the
   rendered text to `_harness/grounding/<host>.txt`.
3. `harness resume <batch>` re-runs `verify_batch_quotes.py <batch_dir> --grounding-dir
   _harness/grounding/` (the new mode, §11 item B): it matches each quote against my captured text
   and stamps a *distinct* provenance (`browser_grounded`, not the researcher's flag). Rows whose
   quote I could not find stay in the worklist and never promote.

The grounding mode must target `clean.ndjson` explicitly (the importable set), not "the first
`*.ndjson` in the dir" — by the grounding step the batch dir holds several NDJSON files (raw,
`clean-input`, `clean`, `worklist`), and the current file-picker would be ambiguous. Item B's brief
pins this.

Net: everything is automated except the page-read, which must stay a judgment call.

## 8. Append-only fingerprint (applier SQL, the trust core)

Captured per destination country in stage 6, before and after the simulated promote, both inside the
rolled-back tx (and again by me by hand after the *real* promote):

```sql
-- The fingerprint covers ONLY the protected set (rows a promote must never touch), so the N pending
-- rows this batch adds fall outside the FILTER and cannot change fp_protected by construction — that
-- is exactly what makes "unchanged" a provable append-only assertion rather than an impossible one.
SELECT count(*) FILTER (WHERE review_status='approved')                              AS approved,
       count(*) FILTER (WHERE verification_status IN ('verified','expert_verified')) AS human_verified,
       md5(string_agg(id||title||coalesce(description,'')||coalesce(verification_status,'')||coalesce(review_status,''),
                      '|' ORDER BY id)
           FILTER (WHERE review_status='approved'
                      OR verification_status IN ('verified','expert_verified')))     AS fp_protected
FROM public.requirement_items
WHERE country_code = :iso;
```

Invariants per op: `fp_protected` unchanged; `approved` unchanged; `human_verified` unchanged;
`expert_verified` delta `== 0` (the batch adds only `review_status='pending'` rows, which are neither
approved nor human-verified). A violation → roll back, do not promote, surface. The real (manual)
promote is followed by the same query re-run by me to prove the invariant held in prod.

## 9. Trust boundary

| Actor | May do | Must never |
|---|---|---|
| **Harness (Cursor-built code, I run)** | ingest · reconcile · convert · referee · `--stage` write to `otto_staging` (`status='new'`) · promote **dry-run in a rolled-back tx** · capture fingerprints · write reports | commit a promote · persistently flip `status→ready` · write `requirement_items` · ack the bus before commit · bypass a CAPTCHA |
| **Applier (me, out-of-harness)** | browser-ground quotes · fix staged `applies_to` in place · flip `status→ready` scoped · run the real scoped `--promote` · re-check the fingerprint in prod | promote on `quote_verbatim_confirmed` alone · unscoped `--promote` · `supabase db push` |
| **Human (founder / lawyer)** | /admin/countries approval → serve; PR merge to main | — |

## 10. Non-goals / YAGNI

- **No headless browser** in the repo/CI (Playwright). The applier hop covers the residue and keeps
  the independent read the guardrail requires. Ratchet to headless later only if the residue proves
  large *and* CAPTCHA-free.
- **No auto-promote, ever.** The harness has no real-promote path; adding one is out of scope.
- **No migration/DDL path.** The harness never touches `supabase`.
- **No new orchestration framework.** A stage list + a JSON checkpoint, nothing more.

## 11. Derived work-items (each gets its own self-contained Cursor brief)

Briefs — schema + contract + acceptance tests — are written separately and handed to Cursor; I
integrate the returned PRs, run against prod, and keep the gates.

- **A · Orchestrator CLI** (`scripts/corridor_harness.py`) — stages 0–6, checkpoint, resume,
  exit-code contract, `report.md`. Stage 0's bus/GCS client injectable for offline tests. Includes
  stage 6's rolled-back promote-dry-run + fingerprint capture.
- **B · `verify_batch_quotes.py --grounding-dir` mode** — consume applier-captured page text, match
  quotes against it, stamp `browser_grounded` provenance (distinct from the researcher's flag). No
  network in this mode.
- **C · Vocabulary-converter hardening** — one general `convert_otto_batch.py` replacing the
  per-batch scripts: emit both spellings (assert paired), require `applies_to.status`, read
  nationality from the artifact, park unknown keys in `applies_to`. Fixtured on the existing B3 /
  VE→IE / ES→IE conversions (must reproduce them byte-for-byte).
- **D · Coverage-snapshot exporter** (`scripts/export_coverage_snapshot.py`) — read-only aggregate
  of `public.requirement_items` (approved/pending per country×category) + `supplier_service_capabilities`
  (provider counts) → the JSON shape the Coverage Master artifact consumes. Standalone; the flywheel's
  progress meter. (Later feeds the queued live `/admin` dashboard.)

## 12. Acceptance

1. **Offline regression:** `harness run docs/imports/<existing-batch>/` (no `--stage`) reproduces a
   clean reconcile + referee + promote-preview against the **21 committed batch dirs**, writing
   nothing to the DB. This is the primary test surface and needs no live GCS.
2. **First real exercise — Otto batch 21** (`otto-resource-2026-09-08`, IN/BR/IL/PT/EE): when it
   delivers, `harness run <manifest-url>` ingests it, I browser-ground the residue, `--stage` writes
   `status='new'`, and the promote dry-run report is produced — with **every quote independently
   verified** before I run the manual promote.
3. **Full P1 suite green** — `pytest backend/tests scripts/tests` — before any of the four PRs is
   flagged done (not a subset).

## 13. Open questions for review

- **O1 — Stage 0 GCS reach.** Otto sometimes delivers to GCS without posting URLs on the bus
  (dispatch mechanics). If the bus row carries no GCS URL, the URL entry point can't self-fetch;
  the local-dir entry point is the fallback. Accept this asymmetry, or should stage 0 also accept a
  raw GCS URL argument?
- **O2 — `--stage` idempotency across re-runs of a partially-promoted batch.** If some of a batch's
  rows were promoted manually between runs, they sit `status='promoted'`; the harness should report
  the status mix rather than treat `promote: 0` as either "done" or "not ready". Confirmed handled
  by the cross-batch `ready` enumeration in stage 5 — flagging for explicit sign-off.
