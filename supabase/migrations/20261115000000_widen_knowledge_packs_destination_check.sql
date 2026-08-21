-- ============================================================
-- [AIQ-1832] Widen knowledge_packs.destination_country to admit 16 more destinations
-- ============================================================
--
-- WHY THIS EXISTS, AND WHY IT IS A DELIBERATE WIDENING RATHER THAN A REPAIR.
--
-- `public.knowledge_docs.pack_id` is NOT NULL, so a document cannot exist without a
-- knowledge pack, and `knowledge_packs.destination_country` is fenced by a CHECK listing
-- 21 destinations. That constraint was doing its job: it encodes which corridors the
-- product covers, and it refused to let an over-collecting research batch quietly widen
-- that claim by inserting rows.
--
-- MEASURED IN PROD, 2026-08-21. A single scaffold row in knowledge_docs,
-- source_url = 'otto://research-intake/pending', held 1,502 requirement_facts across 37
-- destinations — 64% of the entire pending batch. Its archived excerpt was 19,072 chars
-- about importing a vehicle into Ireland, so a German residence-permit fact was being
-- evidence-checked against Irish car-import text and could never verify. Every fact
-- carried its own real source_url; only the source_doc_id join was wrong.
--
-- 1,212 of those have since been repointed onto real per-URL knowledge_docs rows (871 for
-- destinations that already had a pack, then 341 more once DE/AE/JP/IT packs were created
-- — those four were already inside this CHECK). The pending verified rate moved 8.2% -> 18.0%
-- as a direct result.
--
-- 290 facts remain stranded, in 16 destinations this CHECK excludes:
--   TR(39) FI(33) LU(32) SA(30) TH(30) QA(19) PL(18) HK(11) IN(11)
--   ZA(10) CZ(10) IL(10) KR(10) RU(9) UA(9) BR(9)
-- They cannot be repointed while the constraint stands, so their evidence verdict is
-- permanently "unverified" for a reason that has nothing to do with the facts.
--
-- WHAT THIS MIGRATION DOES AND DOES NOT MEAN. It makes those 16 destinations *storable*.
-- It is not a statement that ReloPass serves them, and nothing here creates a pack, a
-- corridor, a requirement or a served row. Packs for these destinations should be created
-- with status='inactive' (the status CHECK already permits 'active'|'inactive') so the
-- data becomes repointable without the pack itself reading as corridor coverage to the
-- next person who queries the table.
--
-- NO NEW TABLE, so no RLS/policy/REVOKE clause is required here — this is an ALTER on an
-- existing table and its RLS posture is unchanged. Stated explicitly so a reviewer applying
-- the "every new public table needs RLS" gate does not go looking for one.
--
-- IDEMPOTENT: DROP ... IF EXISTS then ADD. Safe to re-run.
-- ============================================================

ALTER TABLE public.knowledge_packs
  DROP CONSTRAINT IF EXISTS knowledge_packs_destination_country_check;

ALTER TABLE public.knowledge_packs
  ADD CONSTRAINT knowledge_packs_destination_country_check
  CHECK (destination_country = ANY (ARRAY[
    -- the original 21, unchanged
    'SG'::text, 'US'::text, 'DE'::text, 'GB'::text, 'ES'::text, 'IT'::text,
    'AE'::text, 'FR'::text, 'NO'::text, 'JP'::text, 'NZ'::text, 'DK'::text,
    'BE'::text, 'AT'::text, 'PT'::text, 'CA'::text, 'AU'::text, 'NL'::text,
    'CH'::text, 'SE'::text, 'IE'::text,
    -- added 2026-08-21: destinations the Wave-2 otto-loader collected facts for.
    -- Storable, not served.
    'TR'::text, 'FI'::text, 'LU'::text, 'SA'::text, 'TH'::text, 'QA'::text,
    'PL'::text, 'HK'::text, 'IN'::text, 'ZA'::text, 'CZ'::text, 'IL'::text,
    'KR'::text, 'RU'::text, 'UA'::text, 'BR'::text
  ]));

COMMENT ON CONSTRAINT knowledge_packs_destination_country_check ON public.knowledge_packs IS
  'Destinations a knowledge pack may exist for. Storable is not the same as served: the 16 '
  'added on 2026-08-21 (TR FI LU SA TH QA PL HK IN ZA CZ IL KR RU UA BR) exist so that '
  'requirement_facts collected by the Wave-2 loader can point at their real source document '
  'instead of a shared scaffold. Create their packs status=''inactive''.';
