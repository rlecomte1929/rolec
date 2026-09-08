# Claude Code Execution Prompts — July 14 2026

Three tasks, in priority order. Run **Prompt 1 + Prompt 2 in parallel** (Conductor),
then **Prompt 3 after both are Done**.

---

## PROMPT 1 — AIQ-1528 (P0) · SQLite DDL boot bug

```
Use the relopass-fix-api-bug skill.

Execute AIQ-1528: "The backend runs SQLite-shaped CREATE TABLE against PRODUCTION Postgres on boot"
Notion: https://app.notion.com/39d887c64d48811bb094cc1ec3430b08

EXECUTE IN THIS EXACT ORDER — sequence is non-negotiable:

STEP 1 · Guard init_db() (low risk, do this first, stops the bleeding)
  File: backend/db/misc.py ~line 1560
  The exception_requests CREATE TABLE block has no `if _is_sqlite:` guard.
  Pattern to copy: the sibling block at ~line 2939 IS correctly guarded — mirror it exactly.
  This is a 2-line change. Do it before anything else.

STEP 2 · Full DDL audit of init_db() (read-only, no edits yet)
  Run: grep -n "CREATE TABLE\|CREATE INDEX\|ALTER TABLE" backend/db/misc.py
  For every hit: is it behind `if _is_sqlite:`? List every unguarded one.
  exception_requests is the one that triggered the CI gate — it is unlikely to be alone.
  Document the audit result. Fix each unguarded block with the same guard pattern.

STEP 3 · Reconciliation migration for exception_requests (high risk — live rows exist)
  DO NOT drop and recreate the table.
  First, verify all existing ids are castable:
    SELECT id FROM exception_requests
    WHERE id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';
  If 0 rows returned: safe to cast. Use:
    ALTER TABLE exception_requests ALTER COLUMN id TYPE UUID USING id::uuid;
    ALTER TABLE exception_requests ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at::timestamptz;
    ALTER TABLE exception_requests ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at::timestamptz;
  Test inside BEGIN...ROLLBACK before issuing COMMIT.
  Migration file: supabase/migrations/<timestamp>_fix_exception_requests_types.sql
  Must include: ENABLE ROW LEVEL SECURITY + policy + REVOKE ALL FROM anon (CLAUDE.md hard gate).
  Timestamp must be > max on origin/main:
    git ls-tree origin/main supabase/migrations/ | awk '{print $4}' | sort | tail -1

ACCEPTANCE TESTS:
  cd backend && pytest -k "init_db or schema" -q
  
  Real acceptance test (do this): enable RLS on exception_requests, boot the backend,
  confirm RLS is STILL enabled after boot. If init_db() still issues DDL, it will
  disable RLS again on every redeploy — which is exactly what happened twice today.

Mark AIQ-1528 → Human Review when all 3 steps pass.
```

---

## PROMPT 2 — AIQ-1527 (P1) · Budget false "within_budget"

```
Use the relopass-fix-api-bug skill.

Execute AIQ-1527: "BUG · Budget summary reports 'within_budget' without comparing anything"
Notion: https://app.notion.com/39d887c64d4881bda5dfd2a70ba89554

STEP 1 · Map the frontend consumers BEFORE changing any response shape
  Run this first, before opening cases_read.py:
    /usr/bin/grep -r 'within_budget\|no_cap\|budget_status\|budgetSummary\|budget\.summary' \
      frontend/src --include='*.tsx' --include='*.ts'
  Every hit is a consumer that must be updated to handle the new state.
  If you skip this step and change the shape, you will silently break the UI.

STEP 2 · Fix the hardcoding
  Primary target: backend/app/routers/cases_read.py ~line 2077
  The current code: "status": "within_budget" if total is not None else "no_cap"
  This never compares anything to a cap. It is a cosmetic green check.

  Pattern to follow (already exists in the codebase — do not invent a new pattern):
    backend/app/services/policy_config_cap_compare.py
    It returns `supported_comparison: False` + `reason_unsupported` when it cannot compare.
    Mirror this: when there is no estimate, return an explicit unknown state.

  The honest states are:
    "within_budget"   — only when estimate <= cap (both must be non-null)
    "over_budget"     — only when estimate > cap (both must be non-null)
    "no_cap_set"      — cap is null
    "no_estimate"     — estimate is null (the common case today: only 3 of 31 rows have one)

STEP 3 · The dead code check
  backend/app/routers/cases.py ~3195 and ~3208 have the same hardcoding.
  Verify it is dead: grep for cases.py router registration in backend/main.py.
  If NOT registered: leave it, add a comment "TODO: same fix needed if this router is ever wired".
  If IS registered: apply the same fix.

ACCEPTANCE TESTS:
  cd backend && pytest -k budget -q
  Manual: call the budget summary endpoint for a case with no estimated_cost rows.
  Response must NOT contain "within_budget". Must contain "no_estimate" (or equivalent).

Mark AIQ-1527 → Human Review when done.
```

---

## PROMPT 3 — AIQ-1529 (P1) · Dedupe service_catalog_items
### Run AFTER Prompts 1 and 2 are both in Human Review

```
Use the relopass-dev-queue skill.

Execute AIQ-1529: "S1 · Dedupe service_catalog_items — HR is ticking duplicate vendors"
Notion: https://app.notion.com/39d887c64d48818d909cc264845096d0

READ THESE FILES BEFORE WRITING ANYTHING:
  supabase/migrations/20260913000000_dedupe_seed_suppliers.sql   ← your structural template
  supabase/migrations/20260918000000_rfq_supplier_identity.sql   ← shows supplier_id shape
  backend/app/recommendations/engine.py ~line 382               ← shows how external_id is used

THE external_id TRAP — burned us in AIQ-1520, do not repeat:
  The recommendation engine resolves: rec.item_id → find_master_by_external_id(category, external_id)
  If you drop the catalog item whose external_id the engine emits (e.g. 'm-9'), that vendor
  becomes silently invisible to all employees — no error, just gone from recommendations.
  
  Before writing the migration, for EACH duplicate supplier, run:
    SELECT id, external_id, name, created_at
    FROM service_catalog_items
    WHERE supplier_id = '<supplier_id>'
    ORDER BY created_at ASC;
  KEEP the item whose external_id matches what the recommendation dataset emits.
  DELETE the other one.

SOFT REFERENCE SWEEP (beyond FK constraints):
  /usr/bin/grep -rn 'external_id\|master_item_id' backend/ --include='*.py' | grep -v test
  Every soft/string reference to a deleted item's id or external_id must resolve to the canonical one.

MANDATORY SAFETY PROTOCOL — non-negotiable:
  1. Record the before-state:
       SELECT COUNT(*) FROM company_vendor_selections WHERE selected = true;
       SELECT COUNT(*) FROM service_catalog_items;
  2. Run the ENTIRE migration inside BEGIN ... ROLLBACK.
       Inspect: which rows were reassigned, which were deleted, what the after-counts are.
       Confirm the canonical items retained the right external_ids.
  3. Only if the BEGIN...ROLLBACK output looks correct: run inside BEGIN ... COMMIT.
  4. The migration MUST issue RAISE EXCEPTION rather than silently deleting any row
     it cannot safely reassign. Abort-on-uncertainty, never delete-and-hope.

MIGRATION REQUIREMENTS:
  - Idempotent (safe to re-run)
  - REASSIGN every company_vendor_selections.master_item_id before deleting any duplicate
  - UNIQUE INDEX ON service_catalog_items (category, lower(trim(name))) at the end
  - Migration timestamp > max on origin/main:
      git ls-tree origin/main supabase/migrations/ | awk '{print $4}' | sort | tail -1
    Duplicate timestamps silently never apply — verify this before pushing.

ACCEPTANCE TESTS:
  cd backend && pytest -k 'catalog or curation or recommend' -v

  Then verify against prod (read-only):
    SELECT COUNT(*) FROM (
      SELECT category, lower(trim(name))
      FROM service_catalog_items
      GROUP BY 1, 2
      HAVING COUNT(*) > 1
    ) AS dups;
  Must return 0.

  Also verify: no HR curation row is lost.
    SELECT COUNT(*) FROM company_vendor_selections WHERE selected = true;
  After-count must be >= before-count minus any intentional collapses (report the delta).

Mark AIQ-1529 → Human Review when done.
```

---

## Notes

**Can Prompts 1 + 2 run in parallel?**
Yes. They touch entirely different files (misc.py vs cases_read.py) with no shared state.
Use Conductor with two worktrees if available. Otherwise run 1 then 2 sequentially — both are fast.

**After all three are in Human Review:**
- Review each diff before marking Done
- AIQ-1529 specifically: confirm the prod SQL check returns 0 duplicates before approving
- Once AIQ-1529 is Done, AIQ-1530 → 1531 → 1532 auto-unblock (run them in sequence next session)

**Your action still needed:**
Approve AIQ-1523 in Notion Human Review → that unblocks the full RFQ flow (AIQ-1516).
