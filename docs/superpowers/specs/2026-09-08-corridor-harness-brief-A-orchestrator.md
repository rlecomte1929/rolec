# Cursor Brief A — Corridor-import orchestrator CLI

- **Deliverable:** `scripts/corridor_harness.py` (new) + `scripts/tests/test_corridor_harness.py` (new)
- **Runtime:** Python 3.11. Stdlib + `sqlalchemy` (already a repo dependency) **only**. No new deps
  (no Playwright, no requests-html, no click). Use `argparse`.
- **You (Cursor) have no repo access.** Everything you need to call is embedded below verbatim. Do
  not assume any file layout beyond what is stated. Return the two files; the integrator (Claude
  Code, wired applier) reviews, wires `DATABASE_URL`/venv, and runs against prod.

---

## 0. What this is

A **resumable subprocess stage-machine** that treats one corridor-fact batch end to end and stops at
a **promote dry-run report** — it never commits a promote. It orchestrates CLIs that already exist by
shelling out to them and reading their exit codes; it adds no coupling to their internals.

```
harness run <manifest-url | local-batch-dir>          # full dry-run: writes NOTHING to the DB
harness run <…> --stage                               # opt-in: writes otto_staging (status='new'), then promote dry-run
harness resume <batch-id>                             # re-enter at the first non-ok stage
harness status <batch-id>                             # print the checkpoint
```

### Non-negotiable invariants (make each one testable — see §9, §10)

1. **No code path commits a promote.** The promote dry-run (stage 6) runs inside `BEGIN … ROLLBACK`
   and always rolls back. There is no `--promote-for-real` flag anywhere.
2. **No persistent `status→ready` flip.** Stage 6 may flip `status='new'→'ready'` for *this batch's*
   rows only *inside the rolled-back transaction*, never in a committed one.
3. **Default writes nothing to the DB.** Only `--stage` triggers the single DB-write stage (staging,
   `status='new'`). Without it, staging runs in dry-run.
4. **No headless browser, ever.** Unreachable sources cause a *pause* (exit 20), not a bypass.
5. **The bus row is never acked** by this tool.

---

## 1. The tools it drives (embedded contracts — call these by subprocess)

Invoke each with `[sys.executable, "<script>", …]`. Interpret the **exit code** as the primary
signal; read **files** for counts (do not scrape human stdout for numbers). Capture stdout/stderr to
the checkpoint for the report.

### 1a. `scripts/check_otto_batches.py` — reconcile gate (stage 1)
```
python scripts/check_otto_batches.py <batch-id> --json <out.json>
```
- `<batch-id>` is the directory name under `docs/imports/`.
- Exit: **0** ok · **1** fail · **2** usage. Writes a JSON report to `--json`.
- Verifies manifest sha256 + record/line counts + citation quality vs the files on disk.

### 1b. Vocabulary converter (stage 2) — general converter from Brief C
```
python scripts/convert_otto_batch.py <in.ndjson> --out <clean-input.ndjson>          # (Brief C deliverable)
```
- Until Brief C lands, stage 2 is a **pass-through** when the input is already in parsers vocab
  (detect: every record has keys `entity_topic_key`, `fact_key`, `destination_country`). If not in
  parsers vocab and no general converter exists, stage 2 **gates** (exit 10) with a clear message.
- Contract to code against: converter exit **0** ok · non-zero = fail; writes `--out`.

### 1c. `scripts/verify_ledger.py` — the referee (stage 3)
```
python scripts/verify_ledger.py <clean-input.ndjson> --apply --out <dir> [--no-fetch]
```
- Positional: an NDJSON ledger path. `--apply` writes `clean.ndjson` + `worklist.ndjson` into
  `--out`. `--no-fetch` skips liveness (record that it was skipped).
- Exit: **0** ran, clean file importable · **1** empty / nothing importable · **2** cannot run
  (missing file/config).
- Outputs you consume: `<dir>/clean.ndjson` (importable rows), `<dir>/worklist.ndjson` (rejections).
- The unreachable-source signal for the pause comes from `verify_batch_quotes` (1d), not from parsing
  this tool's stdout.

### 1d. `scripts/verify_batch_quotes.py` — verbatim quote check + browser-grounding (stage 3)
```
python scripts/verify_batch_quotes.py <batch_dir>                                    # today
python scripts/verify_batch_quotes.py <batch_dir> --grounding-dir <dir>              # (Brief B adds this)
```
- Exit: **1** if any quote is missing or any source unreachable · **0** otherwise.
- **Brief B** adds `--grounding-dir` (match quotes against applier-captured page text) and a
  machine-readable `--report <json>` listing per-source `{source_url, evidence_quote, dedupe_key,
  status}` where status ∈ `confirmed | not_on_page | unreachable | blocked`. Code stage 3 against
  that `--report` JSON: any `unreachable`/`blocked` source ⇒ write the grounding worklist and
  **PAUSE** (exit 20). Until Brief B lands, treat a non-zero exit as "unconfirmed quotes present" and
  pause with a coarse worklist (the whole `worklist.ndjson`).

### 1e. `scripts/import_otto_facts.py` — stage (stage 4)
```
python scripts/import_otto_facts.py <clean.ndjson> [--apply] --expected <N> [--source-label <S>]
```
- Exit: **0** ok · **1** rows rejected on sourcing · **2** not found / parse / `DATABASE_URL` unset ·
  **3** reconcile PARTIAL (accounted-for < expected).
- `--apply` writes `otto_staging.immigration_entities` + `immigration_fact_candidates`
  (`status='new'`), a `load_log` row, a `processing_queue` update. Without `--apply` it is a dry run
  (reads the DB, writes nothing).
- **`--expected N` is mandatory** or a clean full load returns **3**. Derive `N` from the manifest
  (see §3) — the count of importable rows after stage 3 (i.e. `wc -l clean.ndjson`).
- Reads env `DATABASE_URL` even in dry run.

### 1f. `scripts/check_nationality_scope.py` — scope lint (stage 5)
```
python scripts/check_nationality_scope.py --db
```
- Exit: **0** clean · **1** violations (EEA registration/permit rows scoped to `OWN_NATIONAL`) · **2**
  cannot run (`DATABASE_URL` unset / query error). Reads `DATABASE_URL`.

### 1g. `backend/imports/otto/executor.py::promote` — promote dry-run (stage 6, in-process)
Import and call in-process (do **not** subprocess this one — you need the transaction):
```python
def promote(session, *, country: str | None = None, dry_run: bool = True) -> PromoteResult: ...
# PromoteResult has: .promoted (int), .skipped_verified (list[str]), .unmapped (list[str]), .drafts (list)
```
- `country=` scopes to one destination; **it is NOT batch-scoped** — with `dry_run=True` it counts
  every `status='ready'` row for that country across all batches. That is deliberate; stage 5/6 must
  label this-batch vs other-batch drafts (see §7).
- Reads `otto_staging.immigration_fact_candidates` where `status='ready'`; staging writes `'new'`, so
  stage 6 simulates the flip inside the rolled-back tx (see §7).

**Wrap the executor import behind an injected callable** (§3) so unit tests never import it.

---

## 2. Batch-dir layout it reads/writes

```
docs/imports/<batch-id>/
  manifest.json            # delivered
  *.ndjson                 # delivered fact stream(s)
  _harness/
    run.json               # the checkpoint (schema §5)
    reconcile.json         # stage 1 --json output
    clean-input.ndjson     # stage 2 converter output
    clean.ndjson           # stage 3 importable rows      (verify_ledger --out)
    worklist.ndjson        # stage 3 rejections
    grounding/
      worklist.json        # sources needing an applier browser hop (stage 3 pause)
      index.json           # {source_url: text-filename} — the applier fills this + the text files
      <url-slug>.txt       # applier-captured page text (Brief B defines this dir's format)
    prepromote.json        # stage 5 lint findings
    promote_preview.json   # stage 6 per-country drafts
    fingerprint.baseline.json
    report.md              # the run's deliverable
```

`<batch-id>` = `manifest.json`'s `batch_id` field if present, else the directory name.

---

## 3. Manifest normalization

Manifests come in two shapes in the repo. Support both; expose one internal accessor.

```jsonc
// shape A (sg-ec)                         // shape B (B3)
{ "batch_id": "...",                       { "batch_id": "...",
  "files": {                                 "artifacts": [
    "facts.ndjson": {                          { "path": "corridor_facts.ndjson",
      "records": 10,                             "record_count": 20,
      "sha256": "…" } } }                        "sha256": "…" } ] }
```
`manifest_records(manifest)` → total declared record count across all fact streams (sum of
`files.*.records` **or** `artifacts[*].record_count`). `manifest_ndjson_urls(manifest, base_url)` →
the object URLs to fetch (for the manifest-URL entry point), resolved relative to the manifest URL's
directory. If neither shape matches, raise a clear error (exit 2, usage).

---

## 4. CLI surface

```
harness run <target> [--stage] [--no-fetch] [--out DIR] [--from-bus] [--python PATH]
harness resume <batch-id> [--stage] [--no-fetch]
harness status <batch-id>
```
- `<target>`: a local `docs/imports/<batch>/` dir, OR an `https`/`file` manifest URL.
- `--stage`: enable the single DB-write stage (4). Default off ⇒ stage 4 runs dry.
- `--from-bus`: resolve `<target>` by pulling the latest `otto_to_claude` delivery (transport is
  injected — §3-transport below). Optional; not required for the local/URL paths.
- `--python PATH`: interpreter used to subprocess the tools (default `sys.executable`).
- `--out DIR`: override `docs/imports/<batch>/_harness/` (used by tests).

---

## 5. Checkpoint schema — `_harness/run.json`

```jsonc
{
  "batch_id": "otto-resource-2026-09-08",
  "entry": {"kind": "local|url|bus", "value": "<target>"},
  "started_at": "ISO-8601", "updated_at": "ISO-8601",
  "stage_flag": {"stage_write_enabled": false, "no_fetch": false},
  "stages": [
    {"n": 0, "name": "ingest",      "status": "ok",     "exit": 0, "at": "…", "stdout_tail": "…", "notes": "…"},
    {"n": 1, "name": "reconcile",   "status": "ok",     "exit": 0, "at": "…", "artifact": "_harness/reconcile.json"},
    {"n": 2, "name": "convert",     "status": "skipped", "exit": 0, "at": "…", "notes": "already parsers vocab"},
    {"n": 3, "name": "referee",     "status": "paused", "exit": 20, "at": "…", "artifact": "_harness/grounding/worklist.json"},
    {"n": 4, "name": "stage",       "status": "pending"},
    {"n": 5, "name": "prepromote",  "status": "pending"},
    {"n": 6, "name": "promote_dry", "status": "pending"}
  ],
  "harness_exit": 20
}
```
`status ∈ {pending, ok, gated, paused, skipped}`. `resume` re-enters at the first stage whose status
is not `ok`/`skipped`. Writing `run.json` must be atomic (write temp + `os.replace`).

---

## 6. Stage contracts

Each stage is a function `stage_n(ctx) -> StageOutcome` where `StageOutcome` is one of
`Continue | Gate(code, msg) | Pause(code, worklist_path)`. The driver runs stages in order, persists
the checkpoint after each, and stops on the first Gate/Pause.

| n | precondition | action | interpret | on failure |
|---|---|---|---|---|
| 0 ingest | target given | local: verify dir has manifest+ndjson · url: fetch (injected transport) · bus: resolve then url | dir populated | Gate 2 (bad target / fetch error) |
| 1 reconcile | dir populated | run 1a → `_harness/reconcile.json` | exit 0 ⇒ Continue | Gate 10 (exit≠0) |
| 2 convert | reconcile ok | parsers-vocab? → pass-through (skipped). else run 1b | exit 0 ⇒ Continue | Gate 10 |
| 3 referee | clean-input exists | run 1c `--apply`; run 1d (`--report` if available) | all quotes confirmed ⇒ Continue · any unreachable/blocked ⇒ Pause 20 (write grounding worklist) · verify_ledger exit 1/2 ⇒ Gate 10 | — |
| 4 stage | clean.ndjson exists | `--stage`: run 1e `--apply --expected N`; else run 1e dry | exit 0 ⇒ Continue · exit 3 (PARTIAL) ⇒ Gate 10 · exit 1/2 ⇒ Gate 10 | — |
| 5 prepromote | staged (or would-stage) | scope lint (§ below) + run 1f `--db` (skip if not `--stage`) | no violations ⇒ Continue | Gate 30 (scope violation) |
| 6 promote_dry | prepromote ok | in-process rolled-back promote-dry-run (§7) | write preview + fingerprint | Gate 30 (fingerprint violation) |

**Stage 5 lint** (deterministic reads over the staged rows' `applies_to`; when not `--stage`, read
the would-stage rows from `clean.ndjson` instead of the DB):
- rows whose `applies_to.status` is absent/unrecognised ⇒ will land `purpose='other'` (list them);
- EEA registration/permit-concept rows not scoped `["EU_EEA"]` ⇒ list, and run `check_nationality_scope --db`;
- rows whose `applies_to.nationality` is absent/disagreeing within a topic ⇒ list (never promote);
- cross-batch `ready` enumeration, labelled this-batch vs other-batch (see §7).
Write all findings to `_harness/prepromote.json`. A `check_nationality_scope` exit 1 ⇒ Gate 30.

After stage 6 succeeds, write `report.md` (§8) and exit 0.

---

## 7. Stage 6 — the rolled-back promote dry-run (the trust core)

In-process, per destination country in the batch. Everything inside **one** `BEGIN … ROLLBACK`:

```
for iso in batch_destinations:
    with session_factory() as session:          # injected
        session.begin()                          # explicit tx
        base = fingerprint(session, iso)         # SQL below, BEFORE
        # simulate the human ready-gate for THIS batch's rows only:
        session.execute(text(
          "UPDATE otto_staging.immigration_fact_candidates SET status='ready' "
          "WHERE batch_id=:b AND destination_country=:iso AND status='new'"),
          {"b": batch_id, "iso": iso})
        result = promote_fn(session, country=iso, dry_run=True)   # injected executor.promote
        after = fingerprint(session, iso)         # SQL below, AFTER
        assert after == base                      # append-only: protected set unchanged
        session.rollback()                        # NOTHING PERSISTS
```

`fingerprint(session, iso)` runs exactly this and returns `(approved, human_verified, fp_protected)`:
```sql
SELECT count(*) FILTER (WHERE review_status='approved')                              AS approved,
       count(*) FILTER (WHERE verification_status IN ('verified','expert_verified')) AS human_verified,
       md5(string_agg(id||title||coalesce(description,'')||coalesce(verification_status,'')||coalesce(review_status,''),
                      '|' ORDER BY id)
           FILTER (WHERE review_status='approved'
                      OR verification_status IN ('verified','expert_verified')))     AS fp_protected
FROM public.requirement_items
WHERE country_code = :iso;
```

Because the fingerprint covers only the **protected** set (approved / human-verified), the pending
rows a promote adds are outside it — so `after == base` is a provable append-only assertion, not an
impossible one. On mismatch: **do not** clear the assert — Gate 30, roll back, surface the diff.

`promote_preview.json` per country: `{would_promote_this_batch: N, titles: [...],
already_ready_other_batches: M, other_titles: [...], skipped_verified: [...], unmapped: [...]}`.
`already_ready_other_batches` = rows counted by `promote_fn` minus the rows this batch simulated to
`ready` (label them separately — never merge; see O2).

`fingerprint.baseline.json`: the per-country `(approved, human_verified, fp_protected)` before the
op — the applier re-runs the same SQL by hand after the *real* promote to prove the invariant held in
prod.

---

## 8. `report.md`

One page: batch id · corridors/countries · reconcile PASS · referee mix (importable / quotes
confirmed vs the list of unconfirmed) · staged N or would-stage N · scope-guard findings ·
per-country would-promote titles (this-batch, then the labelled other-batch `ready` sweep) ·
append-only baseline · and the exact **manual** next commands (flip ready scoped, real scoped
`--promote`, /admin/countries). Deterministic; assert its presence in tests, not its prose.

---

## 9. Harness exit-code contract

`0` reached promote dry-run cleanly · `10` hard gate failed (reconcile/convert/referee/stage) ·
`20` paused for an applier browser hop · `30` scope-guard or fingerprint violation · `2` usage/config
error. A `20` is a designed hand-off, not a failure.

---

## 10. Acceptance tests you (Cursor) deliver green — NO DB, NO network

Build the orchestrator around two injected seams so all of this is unit-testable:
- `ToolRunner` — `run(argv: list[str]) -> CompletedProcess(returncode, stdout, stderr)`. Real impl
  subprocesses; the **FakeToolRunner** returns canned `(exit, stdout)` keyed by the script name, and
  records the argv it was called with.
- `SessionFactory` + `promote_fn` — real impls bind `executor.promote` and a sqlalchemy session; the
  **FakeSession** records every `execute()` SQL and whether `rollback()`/`commit()` was called;
  **fake promote_fn** returns a canned `PromoteResult`.

Required tests (name them clearly):
1. **happy path, dry (no `--stage`)** — fake tools all exit 0, quotes confirmed ⇒ stages 0–6 run,
   `harness_exit==0`, `report.md` written, checkpoint all `ok`/`skipped`. Assert **no fake tool was
   called with `--apply`** and **the FakeSession recorded `rollback` and never `commit`**.
2. **`--stage` path** — asserts stage 4 called `import_otto_facts … --apply --expected <N>` with N =
   `wc -l clean.ndjson`; still no commit anywhere.
3. **reconcile gate** — 1a exits 1 ⇒ `harness_exit==10`, stage 1 `gated`, stages 2+ `pending`.
4. **referee pause** — 1d reports an `unreachable` source ⇒ `harness_exit==20`, stage 3 `paused`,
   `grounding/worklist.json` written with the source rows.
5. **resume after pause** — with grounding files present and 1d now all-confirmed, `resume`
   re-enters at stage 3 and completes to `0`.
6. **stage-4 PARTIAL** — 1e exits 3 ⇒ `harness_exit==10` (never silently 0).
7. **scope gate** — 1f exits 1 ⇒ `harness_exit==30`, stage 5 `gated`.
8. **fingerprint invariant** — with a FakeSession whose `fingerprint` query returns a **different**
   protected fp after the simulated promote, stage 6 ⇒ `harness_exit==30` and `rollback` still
   called. With an equal fp ⇒ `0`.
9. **manifest normalization** — `manifest_records`/`manifest_ndjson_urls` handle both shape A and
   shape B; unknown shape ⇒ exit 2.
10. **checkpoint atomicity/idempotency** — a second `run` on a completed batch is a no-op that
    reports `ok`; `status` prints the checkpoint.

Use `importlib.util.spec_from_file_location` to load the orchestrator by path in the test (the
repo has a `scripts/` vs `backend/scripts/` shadowing hazard — do not `from scripts.corridor_harness
import …`).

---

## 11. Integration tests the applier runs (NOT your responsibility to green)

Against a real staging DB: the rolled-back-tx leaves **zero** rows changed (row counts + the protected
fingerprint identical before/after a full `--stage` run); a real batch's `--expected` reconciles PASS.
List these as `@pytest.mark.integration` skipped-without-`DATABASE_URL` so the suite stays green in CI.

---

## 12. Do NOT
- add any real-promote path, any `commit()` on the promote session, or any persistent `status='ready'`
  update;
- add a headless browser or any new dependency;
- parse tool stdout for counts (use files + exit codes);
- modify `import_otto_facts.py`, `verify_ledger.py`, the parsers, or `executor.py` — orchestrate them
  as-is;
- ack the bus.

## 13. Return to the integrator
The two files, plus a 5-line note listing: which stages are pass-through until Briefs B/C land, any
assumption you made about a tool's output you could not see, and the exact `pytest` command that runs
your tests green.
