# Operator runbook — apply `20261015000000_seed_frno_data_sheet.sql`

**Why this matters:** six merged, CI-green tasks (AIQ-1753…1758) are invisible in production
because this one seed was never applied. It is the highest-leverage action available on the
project right now, and it is ~2 minutes.

Claude deliberately did **not** apply it: the file header says `No MCP apply`, and CLAUDE.md
reserves production application for a human operator.

---

## 1. Confirm the gap is still there

```sql
SELECT version FROM supabase_migrations.schema_migrations
WHERE version BETWEEN '20261014000000' AND '20261017000000' ORDER BY version;
```

Expected today — one gap in an otherwise contiguous run:

```
20261014000000   ✓
                 ← 20261015000000 MISSING
20261016000000   ✓
20261017000000   ✓
```

## 2. Apply the file

Pure data, no DDL: 2 × `INSERT`, 2 × column-guarded `UPDATE`. Idempotent via
`ON CONFLICT (code, version) DO NOTHING` / `ON CONFLICT (id) DO NOTHING`, and the
`form_field_mappings` ids are `md5(...)::uuid`, so a re-run is a genuine no-op.

⛔ **Do not** `supabase db push` — 147 migrations are pending back to 2026-04-27, two of them
confirmed destructive.

Either the Supabase SQL editor (paste the file), or:

```bash
psql "$DATABASE_URL" -f supabase/migrations/20261015000000_seed_frno_data_sheet.sql
```

## 3. Reconcile the ledger

```bash
# session mode — port 5432, NOT the 6543 pooler (migration list fails there)
supabase migration repair --status applied 20261015000000 --db-url "$DATABASE_URL"
```

Run it from a checkout that actually contains the file, or `repair` fails with
"file does not exist".

## 4. Verify — both queries currently return 0

```sql
-- the template now exists
SELECT count(*) FROM form_templates WHERE code = 'RP-NO-DATASHEET';        -- expect 1

-- and its fields carry Norwegian labels, which is what un-breaks the EN/NO toggle
SELECT count(*) FROM form_templates ft
  CROSS JOIN LATERAL jsonb_array_elements(ft.fields) f
  WHERE ft.code = 'RP-NO-DATASHEET'
    AND NULLIF(f->>'label_nb','') IS NOT NULL;                             -- expect 18

-- the machine mapping for the prefill service
SELECT count(*) FROM form_field_mappings WHERE form_id = 'NO_datasheet_v2026';  -- expect 9
```

Then open an FR→NO case in the employee dossier. The EN/NO toggle should appear **for the
first time** — it is gated on `hasNbLabels = fields.some(f => !!f.label_nb)`, which has been
`false` for every user since AIQ-1756 shipped.

## 5. What this unblocks

| Task | Becomes verifiable |
|---|---|
| AIQ-1754 | the data-sheet exists at all |
| AIQ-1755 | prefill has a template to fill |
| AIQ-1756 | EN/NO toggle renders; source badges / NEEDS INPUT visible |
| AIQ-1758 | `register-prefilled` has an artifact to register |

All four sit at `Human Review` and none is genuinely reviewable until this lands.

## Note on provenance

The seed sets `verification_status = 'representative'` — **not** authoritative. Its own header
requires every legal fact (deadlines, the D-number/national-ID 6-month split, the 50%
withholding rule, A1 issued by France) to be reconciled against
`ReloPass_FR-NO_Requirements_VERIFICATION.md` and signed off on a golden FR→NO case before
anything is flipped to `verified`. Applying the seed does not discharge that.
