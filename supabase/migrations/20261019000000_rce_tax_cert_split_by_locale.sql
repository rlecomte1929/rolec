-- AIQ-1774 — split the bare TAX_CERT document type into TAX_CERT_DE / _FR / _NO.
--
-- Why: three tax-certificate extraction agents (TaxCertDeAgent, TaxCertFrAgent,
-- TaxCertNoAgent) were fully built and completely inert. They sat behind ONE
-- 'TAX_CERT' code, discriminated at runtime by an `issuing_country` argument that
-- nothing ever supplied — rce.documents has no country column — so _agent_class()
-- always returned None and the orchestrator always recorded skipped_no_agent.
--
-- The fix is to change the code, not to build a country selector. A German
-- Lohnsteuerbescheinigung, a French avis d'imposition and a Norwegian skattemelding
-- are genuinely different documents, so they get different codes and the flat
-- EXTRACTION_AGENT_REGISTRY routes them like every other agent. This also handles
-- the case a single code never could: an FR→NO case legitimately receives BOTH an
-- FR and an NO certificate, and each is typed on its own evidence.
--
-- Data-only change to the existing rce.document_types table (no new table → no RLS
-- gate). Idempotent. NOTE: production is applied out-of-band per the migration
-- workflow (CLAUDE.md) — merging this PR does not create the rows in prod.

INSERT INTO rce.document_types (code, expected_fields_json, validator_pack)
VALUES
  (
    'TAX_CERT_DE',
    '{
      "fields": [
        "document_subtype",
        "issuing_authority",
        "is_employer_issued",
        "employer_normalized_name",
        "tax_year",
        "tax_id",
        "holder_name",
        "holder_dob",
        "residence_country_iso3",
        "gross_income_annual",
        "net_taxable_income_annual",
        "total_tax_annual",
        "wage_tax_paid"
      ],
      "subtypes": ["LOHNSTEUERBESCHEINIGUNG", "EINKOMMENSTEUERBESCHEID"],
      "issuing_country_iso3": "DEU"
    }'::jsonb,
    'tax_cert_de_v1'
  ),
  (
    'TAX_CERT_FR',
    '{
      "fields": [
        "issuing_authority",
        "tax_year",
        "tax_id",
        "holder_name",
        "co_declarant_name",
        "residence_country_iso3",
        "foyer_address",
        "gross_income_annual",
        "net_taxable_income_annual",
        "total_tax_annual",
        "number_of_parts",
        "is_joint_filing"
      ],
      "subtypes": ["AVIS_IMPOSITION"],
      "issuing_country_iso3": "FRA"
    }'::jsonb,
    'tax_cert_fr_v1'
  ),
  (
    'TAX_CERT_NO',
    '{
      "fields": [
        "document_subtype",
        "issuing_authority",
        "tax_year",
        "tax_id",
        "holder_name",
        "holder_dob",
        "residence_country_iso3",
        "gross_income_annual",
        "business_income_annual",
        "net_taxable_income_annual",
        "total_tax_annual"
      ],
      "subtypes": ["SKATTEMELDING", "SKATTEOPPGJOR"],
      "issuing_country_iso3": "NOR"
    }'::jsonb,
    'tax_cert_no_v1'
  )
ON CONFLICT (code) DO NOTHING;

-- Retire the superseded bare 'TAX_CERT' row so only one model is live.
--
-- Guarded, not unconditional: at authoring time no rce.documents row referenced it
-- (verified against prod — 0 documents of this type, 0 documents total), but the
-- delete must never break the documents_document_type_id_fkey if that changes
-- between authoring and the out-of-band apply. If any document still points at it,
-- the row is left in place and a notice is raised for the operator to reclassify
-- those documents first.
DO $$
DECLARE
  ref_count integer;
BEGIN
  SELECT count(*) INTO ref_count
  FROM rce.documents d
  JOIN rce.document_types dt ON dt.document_type_id = d.document_type_id
  WHERE dt.code = 'TAX_CERT';

  IF ref_count = 0 THEN
    DELETE FROM rce.document_types WHERE code = 'TAX_CERT';
  ELSE
    RAISE NOTICE
      'AIQ-1774: kept rce.document_types.code=TAX_CERT — % document(s) still reference it. Reclassify them to TAX_CERT_DE/_FR/_NO, then delete the row.',
      ref_count;
  END IF;
END
$$;
