-- C2-01 · Seed family document types into rce.document_types
--
-- Adds MARRIAGE_CERT / BIRTH_CERT / FOSTER_CARE_ORDER rows to the existing
-- rce.document_types catalog (created by C1-01 / 20260528020000_relopass_case_engine_v1.sql).
--
-- Seed-only: NO new table in the public (or rce) schema, so the SEC-003 hard
-- gate (ENABLE RLS + policy + REVOKE FROM anon) does not apply here — the
-- target table already carries its RLS from C1-01. This migration only inserts
-- rows. Idempotent: ON CONFLICT (code) DO NOTHING so it is safe to re-run and
-- collides cleanly with any C1-01b seed that may land the same codes first.
--
-- expected_fields_json mirrors the ExtractedField keys each C2-01 extraction
-- agent emits (backend/relopass/agents/extraction/{marriage_cert,birth_cert,
-- foster_care_order}.py). validator_pack names the per-type validator bundle.

INSERT INTO rce.document_types (code, expected_fields_json, validator_pack)
VALUES
  (
    'MARRIAGE_CERT',
    '{
      "fields": [
        "spouse_1_name",
        "spouse_2_name",
        "marriage_date",
        "place_of_marriage",
        "registering_authority",
        "maiden_surname"
      ],
      "optional": ["maiden_surname"],
      "establishes_relationship": "SPOUSE"
    }'::jsonb,
    'family_marriage_v1'
  ),
  (
    'BIRTH_CERT',
    '{
      "fields": [
        "child_name",
        "parent_1_name",
        "parent_2_name",
        "dob",
        "place_of_birth",
        "issuing_authority"
      ],
      "resolves_parents_to_canonical": true,
      "establishes_relationship": "CHILD"
    }'::jsonb,
    'family_birth_v1'
  ),
  (
    'FOSTER_CARE_ORDER',
    '{
      "fields": [
        "dependent_name",
        "guardian_name",
        "jurisdiction",
        "order_date",
        "dependency_type"
      ],
      "dependency_type_vocab": ["FOSTER_CARE", "GUARDIANSHIP", "KAFALA", "CUSTODY", "OTHER"],
      "relationship_establishing_equivalent_to": "BIRTH_CERT",
      "establishes_relationship": "DEPENDENT"
    }'::jsonb,
    'family_foster_care_v1'
  )
ON CONFLICT (code) DO NOTHING;
