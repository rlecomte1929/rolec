# Current check catalog (machine-readable summary)

Convention for each check:

- `check_id`: stable identifier
- `subsystem`: `readiness` | `assignment_compliance` | `case_policy_compliance`
- `inputs`: JSON paths or tables
- `logic`: short description
- `output`: shape
- `supported_by`: `template_row` | `rule_pack` | `policy_engine` | `none`
- `trustworthiness`: `official_pointer` | `internal_operational` | `unverified`

---

## Readiness — resolution

| check_id | subsystem | inputs | logic | output | supported_by | trustworthiness |
|----------|-----------|--------|-------|--------|--------------|-----------------|
| `readiness.destination_resolved` | readiness | profile.movePlan.destination, case.profile_json, case.host_country | Normalize via alias map → ISO2 | `destination_key` or null | none | unverified until HR confirms |
| `readiness.route_resolved` | readiness | (future permit type) | v1 constant `employment` | `route_key` | internal template choice | internal_operational |
| `readiness.store_available` | readiness | DB `readiness_templates` | `SELECT 1` probe | boolean | none | system health |
| `readiness.template_match` | readiness | destination_key + route_key | SQL lookup | template row or null | template_row | internal_operational |
| `readiness.binding` | readiness | assignment_id, template_id | upsert `case_readiness` | row | template_row | internal_operational |

---

## Readiness — checklist & milestones (per template item)

| check_id | subsystem | inputs | logic | output | supported_by | trustworthiness |
|----------|-----------|--------|-------|--------|--------------|-----------------|
| `readiness.checklist.item_state` | readiness | `case_readiness_checklist_state` | COALESCE(status,'pending') | pending / in_progress / done / waived / blocked | template_row | internal_operational |
| `readiness.milestone.completed` | readiness | `case_readiness_milestone_state` | completed_at null/not | boolean | template_row | internal_operational |
| `readiness.item.provenance_map` | readiness | `stable_key`, `readiness_checklist_provenance_map.json` | Map → `source_key` → `compliance_reference_sources.json` | primary_reference | official_pointer rows | official_pointer (URL only; not eligibility proof) |

---

## Assignment compliance engine (`ComplianceEngine`)

| check_id | subsystem | inputs | logic | output | supported_by | trustworthiness |
|----------|-----------|--------|-------|--------|--------------|-----------------|
| `policy.housing_budget_cap` | assignment_compliance | movePlan.housing.budgetMonthlySGD, jobLevel, rules | Parse max vs cap | COMPLIANT / NON_COMPLIANT / NEEDS_REVIEW | rule_pack | internal_operational |
| `policy.job_level_missing` | assignment_compliance | primaryApplicant.employer.jobLevel | presence | NEEDS_REVIEW if missing | rule_pack | internal_operational |
| `policy.lead_time` | assignment_compliance | assignment.startDate, movePlan.targetArrivalDate, minLeadTimeDays | days until vs threshold | status | rule_pack | internal_operational |
| `policy.doc.passport_scans` | assignment_compliance | complianceDocs.hasPassportScans | tri-state bool | per doc | rule_pack | internal_operational |
| `policy.doc.employment_letter` | assignment_compliance | complianceDocs.hasEmploymentLetter | tri-state | per doc | rule_pack | internal_operational |
| `policy.spouse_work_intent` | assignment_compliance | spouse.wantsToWork | if true → NEEDS_REVIEW + extra doc list | heuristic flag | rule_pack | internal_operational |

**Post-process (provenance enrich):** every check receives `output_category: internal_operational_rule`, `primary_reference` from `mobility_rules_provenance.json`, `rationale_legal_safety` stating not immigration law.

---

## Case policy compliance (`policy_engine`)

Not exhaustively cataloged here; remains spend/exceptions/policy JSON. Treat as **internal_operational** unless separately sourced.

---

## Action list generation

| Source | Action shape | Trust label |
|--------|--------------|-------------|
| ComplianceEngine strings | e.g. "Upload Passport scans" | `internal_operational_guidance` after enrich |
| Readiness template | Checklist titles / milestone bodies | `internal_operational_guidance`; mapped rows link official pointers |

---

## Version fields (API)

- `reference_set_version` — bump when `compliance_reference_sources.json` changes materially
- `check_catalog_version` — bump when this catalog or check keys change
- `meta.engine_version` — assignment compliance engine label
