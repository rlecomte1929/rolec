# Claude Code — E2E Test Runbook
**Branch:** `fix/td-qa-services-batch-0719` | **Last updated:** 2026-08-15

## Pre-flight checks (run before anything else)

```bash
# 1. Confirm branch
git branch --show-current  # must output: fix/td-qa-services-batch-0719

# 2. NO-FR bundle integrity (critical — rollback risk)
grep -n "NOFR_BUNDLE" apps/case-command/datasheet-seed.ts
# Expected: at least one line showing NOFR_BUNDLE constant definition
# If missing: the NO-FR bundle was lost in the Aug 15 rollback — DO NOT publish before restoring

# 3. Hardcoded credential check (security gate)
grep -rn 'Bearer eyJ\|WORKSPACE_DB_TOKEN.*=.*"ey\|token.*=.*"ey' audos-workspace-776786/ apps/case-command/
# Expected: zero results — if anything found, block publish and fix first (#109311)

# 4. ES→IE rule count
grep -c 'es-ie-' apps/case-command/rule-engine.ts
# Expected: ≥60

# 5. Non-obvious block present
grep -n 'nonObviousPracticalRealities\|non_obvious_practical' apps/case-command/rule-engine.ts
# Expected: present for es-ie corridor
```

## Verification gate checks

```bash
# Run the 4-check pre-verification gate (task #109315 builds this tooling)
cd tools/corridor-facts

# Check 1: official gov source citation
node check-gate.js FR-NO --check source

# Check 2: source freshness (≤12 months)
node check-gate.js FR-NO --check freshness

# Check 3: schema completeness
node check-gate.js FR-NO --check schema

# Check 4: intra-corridor contradiction
node check-gate.js FR-NO --check contradiction

# Full gate run (all 4 checks, all 3 corridors)
node check-gate.js FR-NO && node check-gate.js NO-FR && node check-gate.js ES-IE
```

## Stripe E2E test (last commercial gate)

This is a MANUAL browser test. Steps:

1. Open: `https://audos.com/p/d0c29613-9cb5-4652-9c6a-494eeed352e5/test-drive-access`
2. Enter an email, complete OTP verification
3. Start a relocation case (FR→NO or ES→IE corridor)
4. Reach the CaseGate paywall
5. Click "Pay" — use Stripe test card: `4242 4242 4242 4242`, exp `12/30`, CVC `123`
6. Complete checkout
7. Verify: you are redirected back with `?payment=success&caseId=<id>` in the URL
8. Verify: in WorkspaceDB, the case row has `access_tier = 'roadmap'`

**WorkspaceDB query to verify access_tier flip:**
```sql
SELECT id, access_tier, updated_at 
FROM relocation_cases 
WHERE access_tier = 'roadmap' 
ORDER BY updated_at DESC 
LIMIT 5;
```

**If the flip does NOT happen:** check `relopass-webhook` hook logs. The webhook `we_1Tuy6W21rgQE53fA92D1CzRJ` must receive `checkout.session.completed` and call `handleReloPassCasePayment()` which sets `access_tier`.

## Post-gate publish sequence

Only run this AFTER all verification gate checks pass:

```
1. Publish FR-NO requirement_entities sync (task #109319 output)
2. Publish ES→IE supplier dossier (task #109318 output)  
3. Publish France gap categories + NO-FR corridor update (task #109320 output)
4. THEN consider: publish FR↔DE and IE↔DE corridors (task #108913 — lowest priority)
```

## Known failure patterns to avoid

| Pattern | Root cause | Corrected approach |
|---|---|---|
| Cursor writes DB rows directly | GitHub mode — Cursor has no WorkspaceDB access | Use `db_insert`/`db_update` tools in chat (Otto), not Cursor |
| Content-embedded commit tasks fail | Cursor can't push large inline content via GitHub REST | Stage content as a file in the task brief, not inline |
| Hardcoded env vars in task briefs | Copy-paste from WorkspaceDB | Always inject via `process.env.*`, never hardcode |
| NO-FR bundle lost after rollback | Audos platform rollback reverts to pre-task state | Always verify `datasheet-seed.ts` after any platform rollback |
