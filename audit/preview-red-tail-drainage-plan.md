# Preview-red tail drainage — follow-up project (scoped 2026-06-02)

**Predecessor:** the baseline-reconciliation milestone (drift entries 10/13/14 + auth-schema fix) landed via **#224 (`54d84c4f`)**, draining the baseline-collision class. Supabase Preview now clears all of `platform_redesign` (advanced stmt 6 → past 138) and dies in the **post-redesign tail**. This project drains that tail to **Preview-green**.

## Goal
Supabase Preview GREEN. Each fix uses **prod as oracle** (match prod's live object byte-for-byte) with **per-site verification** and **pause-and-surface on any unknown class** — the same discipline as #224.

## Known landmines (enumerated; more may surface as Preview advances)

### Entry 15 — `uuid = text` type-mismatch in RLS policy
- **File:** `20260521060000_case_form_comments_events.sql`, 2 policies (`case_form_comments_access`, `case_form_events_access`).
- **Bug:** `c.employee_id = auth.uid()::text` where `cases.employee_id` is **uuid** → `operator does not exist: uuid = text` (42883). Also `p.id::uuid = auth.uid()` (redundant cast).
- **Prod oracle (verified):** prod's live policy uses `c.employee_id = auth.uid()` and `p.id = auth.uid()` (no casts).
- **Fix:** drop `::text` on L39/74; drop `::uuid` on `p.id` L35/70. Match prod exactly.
- **Status:** prod-verified, ready to execute.

### Entry 16 — reverse-drift orphans (= original inventory entries 3/4)
- **Files:** `20260522100000_policy_conflicts.sql`, `20260522110000_policy_chunks_vector_index.sql`.
- **Finding:** both tables (`policy_conflicts`, `policy_chunks`) are **ABSENT on prod** (verified via `information_schema.tables`) — repo-only orphans. They contain `profiles.id = auth.uid()::text` (uuid=text) but with **no prod policy as oracle**.
- **Action:** **drop the files** (orphan cleanup, the inventory-sanctioned action) — NOT fix-to-replay, which would keep repo-only tables prod lacks. Before dropping, verify no later migration references either table.

### Entry 17 — invalid PG syntax
- **File:** `20260524000005_support_tickets.sql` — `CREATE POLICY IF NOT EXISTS` (×3), not valid PostgreSQL.
- **Note:** its `user_id = auth.uid()::text` is **correct** (`support_tickets.user_id` is text on prod) — do NOT touch that.
- **Fix:** rewrite to `DROP POLICY IF EXISTS … ; CREATE POLICY …`, matching prod's live policies.

## Discipline (carried from #224)
1. **Prod is the oracle.** Match prod's live form; never invent.
2. **Per-site verification.** For each `auth.uid()::text` site: check the column's `data_type` on prod AND prod's live policy. `text` column + prod uses `::text` → **skip** (correct convention for legacy/IMM text-keyed tables — already confirmed for `support_tickets.user_id`, `case_messages.sender_id`, `case_assignments.employee_user_id`, `relocation_cases.hr_user_id`). `uuid` column + prod uses no cast → **fix**. Anything else → **pause and surface**.
3. **One class per change; pause-and-surface on unknown classes.** Do not bundle orphan-removal, syntax fixes, and cast fixes blindly — classify each.
4. **Hybrid stopping rule.** If the tail proves much larger / structurally divergent, re-assess rather than open-ended "fix everything past stmt 138".

## Out of scope (unchanged)
`public.case_budget_lines` RLS-disabled (separate security finding, Supabase advisor); the 17 pre-May-20 proven-benign collisions; the broader `_remote_stub` backfill.
