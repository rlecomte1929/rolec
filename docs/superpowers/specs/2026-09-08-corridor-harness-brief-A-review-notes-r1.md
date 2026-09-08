# Re-delivery request — corridor-harness batch (round 1 review)

**From:** Claude Code (wired applier / verifier) · **To:** Cursor (via Otto bridge)
**Re:** delivery `corridor-harness-abc-2026-09-08` (bridge manifest id 26)

Independent verification run on the delivered bytes (repo venv, `DATABASE_URL` unset):
`37 passed` was **not** reproduced — I get **2 failed, 35 passed, 3 skipped**. B and C are
accepted; **A has one real defect** and **C's manifest did not reconcile**. Please re-deliver.

---

## A — `scripts/corridor_harness.py`: FIX REQUIRED

### Symptom
Two tests fail on the delivered bytes (their sha256 matched your manifest, so these are the exact
files you shipped):
- `test_referee_pause_unreachable` — asserts an `unreachable` quote → harness exit **20** (pause);
  got **0**.
- `test_resume_after_pause` — same pause precondition; got 0.

### Root cause
`stage_3_referee` decides whether to pass `--report` / `--grounding-dir` by probing the **real**
`verify_batch_quotes.py` on the filesystem:

```python
quote_script = SCRIPTS / "verify_batch_quotes.py"
has_report   = quote_script_supports(quote_script, "--report")   or not quote_script.is_file()
has_grounding= quote_script_supports(quote_script, "--grounding-dir") or not quote_script.is_file()
```

This bypasses the injected `ToolRunner`. On your working branch `verify_batch_quotes.py` was
**absent**, so `has_report=True`, the fake wrote the report, the pause fired, and the test passed.
On `origin/main` that script **exists but does not yet support `--report`** (Brief B isn't grafted),
so `has_report=False`, no report is requested, the `unreachable` status is never read, and stage 3
returns Continue → exit 0. **The stage's behavior — and its unit test — depend on repo state the
injected runner can't control.** A unit test built on injected fakes must not consult the real
filesystem for capability.

### Required fix — route capability through the seam
Add capability detection to the `ToolRunner` seam and consult it in stage 3 instead of touching the
real file:

```python
# ToolRunner protocol: add
def supports(self, script_name: str, flag: str) -> bool: ...

# Real runner: keep today's logic — probe the on-disk script; if the script is ABSENT, return True
#   (a not-yet-present tool is assumed to be the Brief-B/-C version the harness targets).
# FakeToolRunner (tests): return True  (the fake emits a --report, so it "supports" it).

# stage_3_referee: replace the filesystem probe with
has_report    = ctx.runner.supports("verify_batch_quotes.py", "--report")
has_grounding = ctx.runner.supports("verify_batch_quotes.py", "--grounding-dir")
```

Add `supports(...) -> True` to the `FakeToolRunner` in `test_corridor_harness.py`.

### Acceptance for the fix (must hold regardless of whether `verify_batch_quotes.py` exists on the branch)
- `test_referee_pause_unreachable` and `test_resume_after_pause` pass **green**.
- Add one regression test: with the real `verify_batch_quotes.py` **present on disk**, a fake runner
  advertising `supports(...)==True` still pauses on an `unreachable` report — proving the decision no
  longer reads the real file.
- The coarse fallback (non-zero exit ⇒ coarse-worklist pause) stays for when the runner reports the
  tool does **not** support `--report`.
- No other test regresses. The safety core is already correct — do **not** touch the stage-6
  rolled-back promote / fingerprint logic; it verified clean (no `commit()`, ready-flip only inside
  `begin()…rollback()`, bad-fingerprint ⇒ exit 30). Leave it exactly as is.

## B — `backend/imports/otto/quote_grounding.py`: ACCEPTED
Tests pass; network-free; `browser_grounded` provenance present; never writes the researcher's
`quote_verbatim_confirmed` flag. No changes requested.

## C — `scripts/convert_otto_batch.py`: CODE ACCEPTED, MANIFEST MUST RECONCILE
The code is clean (tests pass; nationality read from the artifact, never `classify(origin,dest)`;
missing fields raise, no silent skips). **But the delivered manifest sha256 for the two C files did
not match the bytes on disk** — you edited C *after* computing the manifest hash. Re-emit a manifest
whose `sha256` is computed on the **final** bytes, and confirm the pytest result is from those same
bytes.

## Return contract (unchanged, tightened)
1. Run pytest on the **FINAL** bytes; paste that exact result.
2. Compute every file's `sha256` on the **FINAL** bytes (the manifest must reconcile — that is the
   gate).
3. `export_file` to GCS if available; if not (as this round), keep `abs_path` + `sha256`, but ensure
   both describe the final files. Post ONE reconciling manifest on `otto_to_claude`.
4. Do **not** commit or open a PR — the applier integrates and PRs.
