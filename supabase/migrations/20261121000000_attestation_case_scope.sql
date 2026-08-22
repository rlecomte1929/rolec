-- ============================================================
-- corridor_attestation_requests: let an attestation be scoped to ONE case
-- ============================================================
--
-- WHAT THIS IS FOR. Every attestation request today is corridor-scoped: `scope = 'legal'`,
-- and `create_attestation` snapshots the approved `requirement_items` for a
-- (country_code, purpose) pair. That is the right unit for "has counsel signed off on
-- Ireland?" — it is the wrong unit for "has counsel signed off on THIS person's move?",
-- which is the question a customer actually pays for.
--
-- `case_id` is the hook for the second question. A case-scoped request snapshots the
-- requirements actually served to one case rather than a whole corridor, and ATT-3.2 builds
-- that snapshot.
--
-- WHY NO ENUM CHANGE FOR `scope`. `corridor_attestation_requests.scope` is plain `text`
-- with a `'legal'` server default and no CHECK constraint — the vocabulary lives in the
-- application, not the schema. `'case'` therefore becomes a legal value by convention the
-- moment ATT-3.2 writes it; there is nothing to alter here. Deliberately NOT adding a CHECK
-- on `scope` in this migration: doing so would pin a vocabulary that ATT-3.2 has not
-- finished designing, and a constraint added on a guess is harder to remove than to add.
--
-- WHY NULLABLE, AND WHY NO FOREIGN KEY. Nullable because every existing row is
-- corridor-scoped and has no case — a NOT NULL would require inventing a value for 0 rows
-- today and every corridor request forever after. No FK because this repo has more than one
-- case table (`public.cases`, `relocation_cases`, `wizard_cases`) and the canonical id
-- boundary is resolved in the application by `resolve_case_ids`; pinning an FK to one of
-- them here would encode a choice that belongs in ATT-3.2, and would fail on whichever
-- table the case ids do not come from. The column is typed `uuid`, which is the shape all
-- three use for their own ids.
--
-- WHAT THIS MIGRATION DOES NOT DO. **Nothing reads or writes `case_id` yet.** No code path
-- in `backend/` references it as of this migration; ATT-3.2 is what populates it. Existing
-- rows are untouched and keep `scope = 'legal'`, `case_id IS NULL`.
--
-- THE INDEX. `ix_cap_case_id` supports the only query ATT-3.2 will run against this column
-- — "the attestations for this case" — which is a point lookup on a table that will be
-- read on a case page. Created unconditionally rather than CONCURRENTLY because the table
-- holds 0 rows in production today (verified 2026-08-22), so there is no lock to avoid.
--
-- NO NEW TABLE, so CLAUDE.md's three gates (ENABLE RLS + policy + REVOKE anon) do not
-- apply — this is an ALTER on an existing table whose RLS posture is unchanged
-- (`corridor_attestation_requests` already has RLS enabled and a policy). Stated
-- explicitly so a reviewer applying that gate does not go looking.
--
-- ORDERING. Stamped above BOTH the repo max (20261119000000) and the production ledger max
-- (20261116000000), per CLAUDE.md "Choosing a migration timestamp". Independent of
-- 20261120000000 (ATT-2.1); either order applies cleanly.
--
-- IDEMPOTENT. `ADD COLUMN IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS`.
--
-- PROBE (run after applying; expect corridor rows unchanged, case_scoped=0):
--   SELECT scope, count(*) FILTER (WHERE case_id IS NULL) AS unscoped,
--          count(*) FILTER (WHERE case_id IS NOT NULL)    AS case_scoped
--     FROM public.corridor_attestation_requests
--    GROUP BY scope;
--
-- ROLLBACK (down):
--   DROP INDEX IF EXISTS public.ix_cap_case_id;
--   ALTER TABLE public.corridor_attestation_requests DROP COLUMN IF EXISTS case_id;
-- ============================================================

ALTER TABLE public.corridor_attestation_requests
  ADD COLUMN IF NOT EXISTS case_id uuid NULL;

CREATE INDEX IF NOT EXISTS ix_cap_case_id
  ON public.corridor_attestation_requests (case_id);

COMMENT ON COLUMN public.corridor_attestation_requests.case_id IS
  'The case this attestation is scoped to, when scope = ''case''. NULL for corridor-scoped '
  'requests, which is every row today. Intentionally has no FK: the canonical case-id '
  'boundary is resolved in the application (resolve_case_ids) across more than one case '
  'table. Written by ATT-3.2; no code reads it as of this migration.';
