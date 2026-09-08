-- E-PIPE-1 · Seed pipeline document types + rce.documents idempotency index
--
-- Two additive, idempotent changes for the rce extraction pipeline:
--
-- 1. Seed the rce.document_types codes the pipeline classifies into. Only the
--    three C2-01 family codes were seeded (20260610005000); the identity /
--    education / tax types the C1-05 extraction agents emit were missing, so an
--    ingested passport/id-card/diploma/tax-cert had no document_type_id to point
--    at. expected_fields_json mirrors the field_keys each agent emits
--    (passport_td3.py MRZ_FIELD_KEYS, id_card.py, diploma.py, tax_cert_*.py).
--    Idempotent: ON CONFLICT (code) DO NOTHING.
--
-- 2. A UNIQUE (case_id, sha256) index on rce.documents so the ingest writer can
--    use INSERT ... ON CONFLICT DO NOTHING and stay idempotent when the same file
--    is bridged twice. Additive; CREATE INDEX IF NOT EXISTS. rce.documents is
--    empty in prod so the build is clean.
--
-- No new table -> SEC-003 new-table gate N/A (rce.document_types / rce.documents
-- already carry their RLS from the case-engine v1 migration).

INSERT INTO rce.document_types (code, expected_fields_json, validator_pack)
VALUES
  (
    'PASSPORT_TD3',
    '{"fields":["surname","given_names","document_number","nationality_iso3","issuing_state_iso3","date_of_birth","sex","expiry_date","personal_number"],"source":"ICAO 9303 MRZ + DI + LLM"}'::jsonb,
    'identity_mrz_v1'
  ),
  (
    'ID_CARD',
    '{"fields":["surname","given_names","document_number","nationality_iso3","issuing_state_iso3","date_of_birth","sex","expiry_date"],"source":"ICAO 9303 MRZ (TD1/TD2)"}'::jsonb,
    'identity_mrz_v1'
  ),
  (
    'DIPLOMA',
    '{"fields":["institution_name","degree_title","isced_level","graduation_date","field_of_study"]}'::jsonb,
    'education_v1'
  ),
  (
    'TAX_CERT',
    '{"fields":["tax_year","tax_id","residence_country","gross_income"]}'::jsonb,
    'tax_v1'
  )
ON CONFLICT (code) DO NOTHING;

CREATE UNIQUE INDEX IF NOT EXISTS uq_rce_documents_case_sha256
  ON rce.documents (case_id, sha256);
