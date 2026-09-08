# Cursor Brief E — scope `import_supplier_candidates.py --promote` by run_id (safety fix)

- **Deliverable:** modified `scripts/import_supplier_candidates.py` (return the FULL file) +
  `scripts/tests/test_import_supplier_candidates_scope.py` (new).
- **Runtime:** Python 3.11, stdlib + sqlalchemy. No new deps.
- **You (Cursor) have no repo access** — the full current file and the executor contracts are embedded
  below. Return the whole modified file.

## The bug (a live prod hazard)
`--promote` calls the supplier promoter **unscoped**, so it promotes the ENTIRE pending
`vendor_candidates` backlog (450+ pending rows of prior-batch junk — Ukraine immigration firms, storage
co's, pet relocation), not just the rows this run staged. That is a footgun every provider batch
(London/Berlin, and every future one) walks into.

## The fix
`backend/imports/suppliers/executor` already supports scoping — the CLI just never wires it:
```python
def stage(conn, candidates, *, dry_run=True) -> tuple[list[StageResult], list[str]]: ...
#   each StageResult has `.run_id` (str) — the run that staged that row (executor.py:158)
def promote(session, *, dry_run=True, run_ids: Optional[Sequence[str]] = None) -> tuple[int,int,list]: ...
#   "Pass run_ids to promote ONLY what those runs staged. Omit it and every unpromoted candidate is
#    promoted." (executor.py:260-277)
```
Thread the run_ids from `stage` into `promote`:
```python
run_ids = sorted({r.run_id for r in results if getattr(r, "run_id", "")})
n, skipped, problems = promote(session, dry_run=not args.promote, run_ids=run_ids)
```
So `--promote` promotes exactly this run's staged suppliers, never the backlog.

**Dry-run nuance to preserve:** without `--apply`, `stage` is rolled back, so its run_ids don't exist
in the DB and a scoped promote-preview shows 0. That is correct (nothing was staged) — but keep the
preview honest: when `run_ids` is empty OR not `--apply`, print a line making clear the promote preview
is scoped to *this run* and shows 0 until `--apply` stages it (do NOT fall back to the unscoped whole-
backlog promote just to show a non-zero number — that is the bug).

## Full current file to modify
```python
<<PASTE scripts/import_supplier_candidates.py verbatim — the integrator will inline it when handing
this brief to you; it is 117 lines, unchanged except the promote() call on line 96 and a scoping line
just before it, per the fix above.>>
```
*(Integrator note: I inline the current file when dispatching. The only changes are: build `run_ids`
from `results` after `summarise`, pass `run_ids=` to `promote`, and the honest-preview line.)*

## Acceptance tests you deliver green (no DB, no network)
Inject a fake `promote` (record the `run_ids` kwarg) and a fake `stage` (returns `StageResult`s with
known run_ids). Load the module by path (`importlib.util.spec_from_file_location`; scripts/ vs
backend/scripts/ shadowing).
1. **scoped on --apply --promote:** stage returns run_ids `{A,B}` ⇒ `promote` is called with
   `run_ids={A,B}`, never with `run_ids=None`/omitted.
2. **never unscoped:** assert no code path calls `promote` without a `run_ids` keyword.
3. **empty run_ids ⇒ no whole-backlog promote:** if `results` is empty, `promote` is called with an
   empty `run_ids` (which promotes nothing), not omitted.
4. existing behaviour otherwise unchanged (exit codes, rejection gating).

## Return
The full modified file + the test, via the same GCS/manifest contract (or abs_path + sha256 on the
final bytes). Don't commit or PR.
