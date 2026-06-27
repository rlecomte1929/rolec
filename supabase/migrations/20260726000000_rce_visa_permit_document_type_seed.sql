-- AIQ-1309 follow-up — seed the VISA_PERMIT document type so the rce ingest can
-- assign a document_type_id and the orchestrator routes visa/work-permit docs to
-- the new VisaPermitAgent (EXTRACTION_AGENT_REGISTRY["VISA_PERMIT"]).
--
-- Data-only seed into the existing rce.document_types table (no new table → no RLS
-- gate). Idempotent. NOTE: production is applied out-of-band per the migration
-- workflow (CLAUDE.md) — merging this PR does not create the row in prod.

INSERT INTO rce.document_types (code, expected_fields_json, validator_pack)
VALUES
  (
    'VISA_PERMIT',
    '{
      "fields": [
        "visa_type",
        "document_number",
        "visa_holder_name",
        "issue_date",
        "expiry_date",
        "issuing_country",
        "entry_conditions"
      ],
      "optional": ["entry_conditions"],
      "establishes_document_evidence": "WORK_AUTHORIZATION"
    }'::jsonb,
    'visa_permit_v1'
  )
ON CONFLICT (code) DO NOTHING;
