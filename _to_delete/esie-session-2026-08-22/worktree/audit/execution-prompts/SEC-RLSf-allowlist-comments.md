# Execution Prompt — SEC-RLSf · Final Allowlist Reason-Comment Pass

**Notion:** AIQ-663 — `https://www.notion.so/370887c64d48815aa972df0bdc864444`
**Parent sprint:** AIQ-649. **Runs LAST** — blocked by SEC-RLSa, SEC-RLSb, SEC-RLSc, SEC-RLSd, SEC-RLSe.
**Priority:** **P0** · **Complexity:** Low · **Branch:** `audit/stage-1-rls-f-closeout`

## Role
Backend engineer. You're the closer. After a-e have drained the allowlist of policy-able tables, you make sure 100% of retained lines carry a justification comment so the next maintainer doesn't have to re-do the analysis.

## ⚠️ Run order
Do NOT start until SEC-RLSa, b, c, d, e are all merged or at least in Human Review with their migrations applied. If you start early, you'll be reasoning about lines that are about to disappear and the diff will be noise.

Verify before starting:
- AIQ-658 (SEC-RLSa) — status ≥ Human Review.
- AIQ-659 (SEC-RLSb) — status ≥ Human Review.
- AIQ-660 (SEC-RLSc) — status ≥ Human Review.
- AIQ-661 (SEC-RLSd) — status ≥ Human Review.
- AIQ-662 (SEC-RLSe) — status ≥ Human Review.

If any are still "AI in Progress" or earlier, raise the dependency with Romain and stop.

## Read first
- `supabase/rls_allowlist.txt` — should be much shorter than 113 entries now.
- `scripts/check_rls_coverage.py` — CI gate. Adapt it to **fail when a non-comment table line lacks an inline reason comment**, if it doesn't already (verify the parser).

## Deliverable
1. **Every retained line** in `supabase/rls_allowlist.txt` carries a `# reason` either inline or in the immediately-preceding non-blank section header comment.

   Acceptable shapes:
   ```
   audit_logs                # server-role only — FastAPI middleware writes only
   demo_requests             # server-role only — public form intake, drained by ops
   ```
   Or group-style:
   ```
   # ── Outbox / background jobs (server-role only) ──
   crawl_runs
   crawl_schedules
   knowledge_doc_ingest_jobs
   ```
   Either is fine, but if you go group-style, every member of the group must be unambiguously covered by the section header.

2. **CI enforcement** — update `scripts/check_rls_coverage.py` so that:
   - Every table line is either policy-ized OR carries an explicit reason (inline OR under a section header).
   - A new failure mode: "table on allowlist without reason comment" exits 1 with the offending line(s).
   - Add a unit test for the script under `scripts/tests/test_check_rls_coverage.py` (create if missing).

3. **Final count delta** — report at the top of `supabase/rls_allowlist.txt`:
   ```
   # Allowlist size on 2026-05-25 (seed):                       113
   # Allowlist size after SEC-RLS sprint (this commit):         <N>
   # Steady-state floor (server-only by design):                <N>
   ```

## Validation
```bash
python scripts/check_rls_coverage.py --allowlist supabase/rls_allowlist.txt
pytest scripts/tests/test_check_rls_coverage.py -v
# Hard gate: no table line without reason.
awk '/^[a-z_]/ && !/#/' supabase/rls_allowlist.txt  # must return nothing
```

## Constraints
- Do not add tables back to the allowlist that a-e successfully policy-ized.
- Do not invent reasons — every reason should describe how the table is actually used. Cross-reference the relevant a-e Execution Notes if the call isn't obvious.
- Keep the file readable: max ~120 char lines; group related tables.
- CI script changes must remain backwards-compatible with existing test invocations.

## Definition of done
- 100% of non-comment lines in `rls_allowlist.txt` are reason-justified.
- CI script enforces the new rule and has a passing unit test.
- Final count delta is documented at the top of the file.
- `check_rls_coverage.py` exits 0; new failure-mode unit test exits 0 with a fixture missing-reason file.
- Notion AIQ-663 → Human Review with final count delta + before/after sample lines in Execution Notes.
- Notion AIQ-649 (parent) → Human Review; all 4 parent validation criteria satisfied.
- Commit per CLAUDE.md Build Hygiene rules.
