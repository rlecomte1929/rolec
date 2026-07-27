# Case-ID Unification Audit (AIQ-1720 · Subtask 1)

**Date:** 2026-07-27 · **Author:** Claude Code (relopass-dev-queue) · **Type:** read-only audit
**Purpose:** decide whether `UNIQUE(canonical_case_id)` on `case_assignments` — the AIQ-1720
parent's stated target — is the *correct* constraint, and inventory every row that blocks it, so
Subtasks 2–4 (cleanup → constraint → `public.cases` backfill) can execute against real data.

> Source of truth: live prod (`nsvefcvpvwwwhuqyuqmp`) as of 2026-07-27. All queries were
> read-only. **Context:** this is a pre-launch platform — the data is demo/test/seed, not real
> customers (see `project_platform_prelaunch_fake_data`). That materially informs the verdict.

---

## VERDICT

**The model is 1:1 (one `canonical_case_id` ↔ one relocation/assignment). `UNIQUE(canonical_case_id)`
IS the correct target — after Subtask 2 cleans the offending rows.**

Every one of the 9 duplicate-canonical groups is a **data artifact**, not a legitimate
"one case, many assignments" pattern:
- **Demo seeds** (`demo-bca-00{1,2,3}` / `demo-ca-00{1,2,3}`) colliding with real-looking rows.
- **Batch test data**: `641e0156…` has 4 different employees created 15:33–15:49 in one sitting;
  `b652d482…` has **14** assignments where `employee_user_id == hr_user_id` (same person),
  created every ~16 seconds — a load/test artifact.
- **Retry duplicates**: `7181b3a4…` is the *same* employee twice plus a NULL-employee row,
  created within 70 seconds.

None shows a clean production **reassignment** shape (an old assignment closed/superseded + a new
active one). So the intended invariant is one relocating employee = one case = one assignment.

**Caveat for the future (carry into Subtask 3):** a *plain* `UNIQUE` forbids ever reusing a
`canonical_case_id` across two assignment rows. If the product later adds "reassign this case to a
new employee" and models it as two rows sharing the canonical, a plain UNIQUE would block it. Today
there is **no such flow and no such data**, so plain UNIQUE is right — but Subtask 3 should note
that a future reassignment feature must either mint a new canonical per assignment **or** switch to
a *partial* unique on active rows (`WHERE status <> 'closed'`).

---

## Inventory (33 rows block the constraint)

Prod `case_assignments`: **489 rows**. Blockers: **6** NULL canonical · **9** duplicate-canonical
groups · **18** dangling canonical. (Some rows appear in more than one bucket — e.g. `641e0156…`
and `79fb2d6f…` are both duplicated *and* dangling.)

### A. NULL / blank `canonical_case_id` — 6 rows (fail `NOT NULL`)
Fix in S2: backfill `canonical_case_id = case_id` (each `case_id` below is a valid case key).

| assignment_id | case_id | employee | status | note |
|---|---|---|---|---|
| `af4bbb3f-eb0c-49cb-a8f6-3bb0fbd90c8a` | d41e3576… | 94a6c8a6 | awaiting_intake | real-shaped |
| `51a4761f-7754-452d-8622-ef7a729d6e58` | 374702e3… | fbf615f6 | assigned | real-shaped |
| `demo-ca-002` | 1cbc563e… | d0e00200 | submitted | demo seed; case_id is a dup canonical |
| `demo-ca-003` | 65d7aea8… | d0e00300 | assigned | demo seed; case_id is a dup canonical |
| `demo-ca-001` | 5b16522e… | d0e00100 | approved | demo seed; case_id is a dup canonical |
| `rlst_531bf32490-asg-a` | 9fa250d7… | dde4e785 | created | seed |

### B. Duplicate `canonical_case_id` — 9 groups (fail `UNIQUE`)
All classified **DATA ERROR / SEED** (see Verdict). S2 resolves each; none is a legitimate 1:N.

| canonical_case_id | size | shape → classification |
|---|---|---|
| `1cbc563e-b984-44b5-adb3-74912d79a84d` | 2 | real (`bbe22a86`) + `demo-bca-002` → **demo collision** |
| `2e96a142-e979-4294-bce3-328792db62af` | 2 | 2 diff employees, same HR, 4 min apart → **seed batch** |
| `5b16522e-e899-4db2-bc8d-95af00af8c79` | 2 | real (`fb500b0f`) + `demo-bca-001` → **demo collision** |
| `641e0156-2f01-4159-ba16-d88ab38102a3` | 4 | 4 diff employees, one HR, 15:33–15:49 → **seed batch** (also dangling) |
| `65d7aea8-bc11-413a-8d28-8b9818190a2a` | 2 | real (`b8a41ee8`) + `demo-bca-003` → **demo collision** |
| `7181b3a4-8c7e-422c-b960-46cc4d61df80` | 3 | same employee ×2 + a NULL-employee row, <70s → **retry dup** |
| `79fb2d6f-59df-443d-a41a-3f6c1721ff1a` | 2 | 2 diff employees, same HR, 24 min apart → **seed batch** (also dangling) |
| `b652d482-fcba-489a-ab0e-98b291d17121` | 14 | 14 rows, employee==HR (`6d860169`), ~16s apart → **load/test artifact** |
| `e26e4d7a-d467-467e-b37c-76277572d486` | 2 | 2 diff employees, same HR, 6 min apart → **seed batch** |

### C. Dangling `canonical_case_id` — 18 rows (canonical matches no `relocation_cases` NOR `cases`)
S2 repairs (repoint to the real case) or removes (orphan seed). Full list of assignment_ids →
their dangling canonical (this is the `canonical_case_id` value, not `case_id`):

`f8568178→5ee1fbd3`, `3ad3e10e→efb65839`, `98ff929f→641e0156`, `3e92a8e5→641e0156`,
`21bab6ab→641e0156`, `ae9d5804→641e0156`, `18d47f4d→6936e4f8`, `70e5d93d→aaa7e7d2`,
`c6818bcb→3fbcda5e`, `ea7bf702→239c7066`, `93df1a39→528d99de`, `e1af7c12→79fb2d6f`,
`442393a1→79fb2d6f`, `3a45a622→79d04ea0`, `7c739cad→a39dcd8d`, `51454dc6→ae344ebe`,
`rlst_531bf32490-asg-b→43176870`, `8bd1358e→e7d96c2f`.

(`641e0156` ×4 and `79fb2d6f` ×2 overlap group B — those canonicals are both duplicated and orphaned.)

---

## D. `public.cases` coverage gap (feeds Subtask 4)

| metric | value |
|---|---|
| `relocation_cases` total | 748 |
| `public.cases` total | 168 |
| `relocation_cases` with no `public.cases` row | **581** |
| distinct assignment canonicals missing a `public.cases` row | 292 |
| — of those, backfillable from `relocation_cases` | **278** |
| — of those, orphan (no reloc row either) | 14 |

**Backfill scope for S4:** the **278** assignment-referenced canonicals that have a `relocation_cases`
row but no `public.cases` row are the priority (these are the cases the app actually loads). The
581-total figure includes legacy/unreferenced reloc rows S4 may choose to skip with a documented
reason. The 14 orphans are the dangling set (bucket C) — S2's job, not S4's.

---

## Recommendations (feed the blocked subtasks)

- **S2 (cleanup):** backfill the 6 NULL to `case_id`; for group B, drop the demo/test/retry
  duplicates keeping the real row per group (demo-collisions: keep the real, drop the `demo-*`;
  `b652d482` 14-row + `641e0156` 4-row + `7181b3a4`: keep one, remove the rest); repoint or remove
  the 18 dangling. Idempotent, reversible, out-of-band.
- **S3 (constraint):** `NOT NULL` + plain `UNIQUE(canonical_case_id)`. Record the reassignment
  caveat above.
- **S4 (backfill):** target the 278 backfillable canonicals; document any of the 581 legacy rows
  deliberately skipped.
- **Re-run before each stage:** the counts here are 2026-07-27; verify they still hold at execution.
