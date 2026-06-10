-- C2-09b · Idempotency UNIQUE on rce.contradictions
--
-- The contradiction detector (C1-08/C2-09) dedups on the tuple
--   (case_id, canonical_entity_id, field_key, content_hash)
-- in its in-memory store. The production SupabaseContradictionStore relies on a
-- DB-level UNIQUE so concurrent / re-run detections can use INSERT ... ON CONFLICT
-- DO NOTHING and stay idempotent.
--
-- canonical_entity_id is NULLABLE (a contradiction can predate canonical-entity
-- resolution). A plain UNIQUE treats NULLs as distinct, which would let duplicate
-- NULL-entity contradictions through. NULLS NOT DISTINCT (PostgreSQL 15+, which
-- Supabase runs) makes two NULLs collide — matching the in-memory store's tuple
-- semantics exactly.
--
-- Additive + idempotent: CREATE UNIQUE INDEX IF NOT EXISTS. No table/columns
-- change, no data rewrite, so existing rows are untouched and the SEC-003 new-table
-- gate does not apply. Safe to re-run.
--
-- NOTE: if any duplicate (case_id, canonical_entity_id, field_key, content_hash)
-- rows already exist, this index build will fail — that itself is the signal that
-- the detector previously double-wrote and needs a dedup backfill first. As of
-- 2026-06-10 rce.contradictions has no writer yet, so the table is effectively
-- empty and the index builds cleanly.

CREATE UNIQUE INDEX IF NOT EXISTS uq_rce_contradictions_idempotency
  ON rce.contradictions (case_id, canonical_entity_id, field_key, content_hash)
  NULLS NOT DISTINCT;
