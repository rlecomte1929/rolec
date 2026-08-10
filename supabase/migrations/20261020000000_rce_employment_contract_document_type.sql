-- AIQ-1766 — seed the EMPLOYMENT_CONTRACT document type for the new extraction agent.
--
-- Why: EmploymentContractAgent (backend/relopass/agents/extraction/employment_contract.py)
-- is now registered in EXTRACTION_AGENT_REGISTRY, so a classified employment contract
-- has somewhere to route. Until this row exists, rce_document_ingest resolves
-- document_type_id to NULL and the orchestrator records skipped_no_agent regardless
-- of the agent being wired.
--
-- ONE code for all three locales, deliberately NOT the TAX_CERT_DE/_FR/_NO split of
-- 20261019000000. That split existed because a runtime `issuing_country` selector was
-- supplied by nothing; here the locale is read from the document's own text inside the
-- agent, so no selector has to be threaded through the orchestrator. The C1-04a
-- classifier also emits exactly one EMPLOYMENT_CONTRACT code and names FR CDI/CDD, DE
-- Arbeitsvertrag and NO arbeidskontrakt as variants of it — three runtime codes could
-- not be mapped from that single output. And unlike the tax certificates, whose locales
-- carry genuinely different fields, the three contract prompts share one output schema.
--
-- expected_fields_json mirrors the field_keys the agent emits (make_field calls in
-- run()), per the column's existing convention.
--
-- Data-only change to the existing rce.document_types table (no new table → no RLS
-- gate). Idempotent. NOTE: production is applied out-of-band per the migration workflow
-- (CLAUDE.md) — merging this PR does not create the row in prod.

INSERT INTO rce.document_types (code, expected_fields_json, validator_pack)
VALUES
  (
    'EMPLOYMENT_CONTRACT',
    '{
      "fields": [
        "contract_type",
        "employer_legal_name",
        "employer_registry_id",
        "position_title",
        "position_isco_2008",
        "gross_salary_annual",
        "currency_iso3",
        "gross_salary_guaranteed_fixed_only_bool",
        "contract_start_date",
        "contract_duration_months",
        "working_time_percent"
      ],
      "optional": [
        "position_isco_2008",
        "contract_duration_months"
      ],
      "locales": ["FR", "DE", "NO"],
      "locale_resolution": "read from document text by EmploymentContractAgent.detect_jurisdiction; no runtime selector",
      "prompts": [
        "prompts/extraction/employment_contract_fr_v1.txt",
        "prompts/extraction/employment_contract_de_v1.txt",
        "prompts/extraction/employment_contract_no_v1.txt"
      ]
    }'::jsonb,
    'employment_contract_v1'
  )
ON CONFLICT (code) DO NOTHING;
