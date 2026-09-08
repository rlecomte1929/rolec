# Audos task brief — P0-1 follow-up: the persistence design is blocked

**Context date:** 2026-07-19 · **Repo:** `rlecomte1929/rolec`
**Reviewing:** `3f9ed63a49554f3d3db433e953928cbc42aa5e4b` on `audit/stage-p0-1-eager-policy-resolution`

---

## 0. What's good — keep all of this

- **You found a root cause we both missed.** The config-matrix branch never persisted its resolution. That explains why the 12 test-drive cases *with* a published policy still had zero resolved rows. Genuinely good diagnosis.
- **Eager hook** as the 6th post-creation hook, idempotent, never raising into creation — correct design.
- **Structured error events** replacing the silent warns — exactly right.
- **`policy_unavailable` / "Policy comparison unavailable"** as a state distinct from "No policy rule for this category" — this was the important product fix. A false business assertion is worse than a visible degraded state.
- **You did not make a migration and flagged the FK risk instead.** That was the right call and it respected the gate. Thank you.

**None of the above needs redoing.** The problem is confined to the persistence mechanism.

---

## 1. Correction 1 — the blocker is worse than "FK relaxation"

Your note says matrix persistence "will be rejected there" if prod carries the strict FK shape. Verified against production — it does, **and the column type is also wrong**:

```
policy_id           uuid  NOT NULL   FK → company_policies(id)   ON DELETE CASCADE
policy_version_id   uuid  NOT NULL   FK → policy_versions(id)    ON DELETE CASCADE
assignment_id       text  NOT NULL   UNIQUE
case_id             text  NULL
```

You intend to write `policy_id = 'policy_config_matrix:<vid>'`. That is a string containing a colon being written to a **`uuid NOT NULL`** column. It fails at the type cast, before the FK is evaluated. Relaxing the foreign keys would not make this work.

**Consequence:** as currently built, every matrix persistence attempt throws in production, `policy_resolution_persistence_error` fires on each one, and the coverage metric stays at 0. The eager hook, structured errors and degraded copy all still work — but the headline fix does not.

---

## 2. Correction 2 — the seed is still failing; you generalised from n=1

Your commit says: *"the AIQ-1621 seed DOES publish a policy-config version (31 rows, host_housing_cap covered) — confirming the failure is the lazy/never-persisted resolution, not the seed."*

That is true for the one session you provisioned. It is not true for the population:

| Day | Test companies created | With a published policy |
|---|---|---|
| 2026-07-19 | 47 | **11 (23%)** |
| 2026-07-18 | 45 | **4 (9%)** |

**77% of test-drive companies created today still have no published policy.** The seed is not fixed; it is intermittent. Both failures are real and independent — do not close the seed line of investigation.

---

## 3. Step 0 is still outstanding

The AIQ-1631 reconciliation was a hard gate: report a recommendation and wait for approval before implementing. It was skipped. Your commit does not touch `backend/main.py:9790` or `_with_legacy_benefit_key_aliases`, so no conflict was introduced — but the question is still open and still blocks merging `fix/f14-shared-taxonomy`.

**Deliver the Step 0 written recommendation before any further code.**

---

## 4. Decision required — how to persist a matrix resolution

Do **not** pick one and implement it. Assess all three, recommend one with reasoning, and wait for approval.

**Option A — relax the FKs and widen the columns to `text`.**
One migration. Simplest diff. Weakens referential integrity on a table holding policy data, for every row including real customers'. Probably the wrong trade.

**Option B — create shadow `company_policies` + `policy_versions` rows for the matrix policy.**
No migration, no schema weakening, FKs stay intact. But it writes synthetic rows into tables other queries treat as real, which risks confusing every consumer of `company_policies`. A hack that will be discovered later by someone else.

**Option C (recommended) — model the polymorphism honestly.**
Make `policy_id` / `policy_version_id` nullable, add `policy_config_version_id uuid` with an FK to `policy_config_versions`, and a CHECK constraint enforcing that exactly one source is populated. One migration, correct long-term, no weakened constraints, no fake rows. This table genuinely has two policy sources now; the schema should say so.

**Constraints on whichever is chosen:**
- Any migration is 🔴 **Red — human-gated**. Commit the file; the operator applies it out-of-band. **Never apply it yourself and never insert into `supabase_migrations.schema_migrations`.**
- Idempotent DDL only.
- Existing rows must keep working — real-customer resolution must not regress.
- If a new table were involved (it should not be): RLS + a policy + `REVOKE ALL FROM anon`, no exceptions.

---

## 5. Scope creep to explain or revert

`frontend/src/api/client.ts` and `frontend/src/pages/ProvidersPage.tsx` are in this commit and have no apparent relationship to policy resolution. Either justify them or split them into a separate change. Every changed line should trace to the task.

---

## 6. Verification — required, not optional

You reported the work as finished without any of this. Do not report done again without it.

**6.1** Paste the raw output of:

```sql
WITH pub AS (
  SELECT pc.company_id::text AS cid
  FROM policy_configs pc
  JOIN policy_config_versions pcv ON pcv.policy_config_id::text = pc.id::text
  WHERE pcv.status='published' GROUP BY 1
)
SELECT co.is_test,
       count(*)                                    AS cases,
       count(*) FILTER (WHERE pub.cid IS NOT NULL) AS company_has_published_policy,
       count(*) FILTER (WHERE pub.cid IS NULL)     AS company_missing_policy,
       count(rap.id)                               AS cases_with_resolution
FROM relocation_cases rc
JOIN companies co ON co.id::text = rc.company_id::text
LEFT JOIN pub ON pub.cid = co.id::text
LEFT JOIN resolved_assignment_policies rap ON rap.case_id::text = rc.id::text
WHERE rc.created_at::timestamptz > now() - interval '2 days'
GROUP BY co.is_test;
```

**6.2** Provision **5** fresh test-drive sessions (not one) on `?campaign=qa-p0-1&corridor=FR_NO`. Report how many got a published policy. This is the seed-intermittency measurement — n=1 is not a result.

**6.3** Run RUN 003 Segment B step B16 (`docs/audos-test-drive-e2e-scenario-run003.md`). Report the branch taken: does the Housing card show a real cap, or "No policy rule", or the new "Policy comparison unavailable"?

**6.4** Confirm no real-customer regression: real cases must still resolve. Current baseline is 3 of 21.

---

## 7. Reporting

Your last two chat reports contained no results — only the repo name and the prior commit hash. The work was good and the report made it look like nothing happened. **Always include: branch, commit SHA, what changed, what you measured, and what is still blocked.** If a PR cannot be opened (the PAT still needs "Pull requests: Read and write"), say so explicitly rather than omitting it.

```
STEP 0 — AIQ-1631 reconciliation
  Recommendation: ____ | What gets deleted: ____ | Amend fix/f14-shared-taxonomy? ____
  [STOP — await approval]

PERSISTENCE DESIGN
  Recommended option (A/B/C): ____  Reasoning: ____
  Migration required? ____ (if yes → Red, commit file only, do not apply)
  [STOP — await approval]

SEED INTERMITTENCY
  5 fresh sessions → ___/5 got a published policy
  Actual exception when it fails: ____

VERIFICATION
  [raw SQL output]
  RUN 003 B16: ____
  Real-customer baseline (was 3/21): ____

SCOPE
  client.ts / ProvidersPage.tsx justification: ____

BLOCKED / NOT DONE: ____
```

**Sequence:** Step 0 and the persistence design are both hard gates — report both, wait for approval, then implement. The seed investigation (6.2) can proceed in parallel; it needs no approval and it is 77% of the population.
