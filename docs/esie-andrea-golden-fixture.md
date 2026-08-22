# ES→IE golden fixture — Andrea, and the EEA control persona

**Status: FROZEN.** This file is the executable truth for the ES→IE serving path. It is loaded
by `backend/tests/test_esie_andrea_golden_fixture.py`; change the JSON block and you change what
the serving layer is required to do. Do not edit it to make a test pass.

## Why this file exists

Two mis-serves are possible on this corridor, and they are opposites. This fixture pins both.

1. **Hiding a corridor-wide rule from an EEA mover.** Every one of the 38 records in the ES→IE
   batch is labelled `nationality: "non-EEA"`, because that is the batch's *audience*. But 17 of
   them are tagged `nationality_scope_basis: "audience_scope"` — PPSN, emergency tax, ordinary
   residence, Irish tax-residency tests. Those are nationality-neutral in law: they apply to
   anyone starting a first job in Ireland. Reading the `nationality` label as a restriction hides
   them from a Spanish mover, who then walks into emergency tax at 40%.

2. **Asserting a third-country requirement at an EEA mover.** The other 21 records are
   `nationality_determined` — CSEP, entry visa, IRP registration. Serving those to an EEA
   free-mover tells them to obtain an employment permit they are legally exempt from.

The matcher must therefore gate on `nationality_scope_basis`, not on the `nationality` label.

## Persona — Andrea (FROZEN reading)

Andrea is a **Venezuelan national (third country)**, legally resident in Spain, relocating
Madrid → Dublin (Google, Grand Canal Dock), family of four.

The repo's documents disagreed on this and the disagreement is resolved here, on the record:

| Document | Claim |
|---|---|
| `ReloPass_ES-IE_Andrea_GoLive_Assessment_2026-08-20.md` | Venezuelan national, third-country ✅ **authoritative** |
| `ES-IE_Corridor_Landing_Engineering_Plan_2026-08-22.md` | "non-EEA professional" ✅ consistent |
| `ES-IE_Phase5_Serving_Wiring_DRAFT_2026-08-22.md` | "non-EEA professional" ✅ consistent |
| `ReloPass_ThemeDigest_Architecture_2026-08-22.md` | "Spanish (EEA) national" ❌ superseded |
| `ReloPass_PhaseA_ES-IE_Execution_Pack_2026-08-22.md` | "Spanish (EEA) national" ❌ superseded |

The two superseded documents describe a real and necessary test case — they just attached it to
the wrong name. That case is preserved here as **`eea_control`**, the Spanish mover on the same
corridor. Both personas are asserted; neither is optional.

## must_not_assert

For `eea_control`, the serving layer must never state:

- that she requires an employment permit or work visa (any `nationality_determined` immigration
  or registration rule),
- that she is or is not visa-required — the two `assertion_mode: "conditional"` records assert a
  *sequence*, not a determination, and the determination lives in a separate ISD lookup,
- that she is exempt from Irish emergency tax **because** she is EEA. She is not exempt; the
  emergency-tax rules are `audience_scope` and apply to her in full.

## The fixture

```json
{
  "fixture_version": "1.0",
  "corridor": "ES-IE",
  "batch_id": "es-ie-thirdcountry-requirements-2026-08-22",
  "source_artifact": "docs/imports/es-ie-thirdcountry-requirements-2026-08-22/es_ie_thirdcountry_requirements.ndjson",
  "personas": {
    "andrea": {
      "nationality": "Venezuela",
      "nationality_class": "THIRD_COUNTRY",
      "origin_country": "ES",
      "destination_country": "IE",
      "expected_served_rules": [
        "booked_appointment_within_90_days_preserves_lawful_presence",
        "burgh_quay_nationwide_registration_office",
        "cannot_hold_residence_permits_in_two_eu_states",
        "csep_nine_month_employer_lock",
        "csep_no_labour_market_needs_test",
        "csep_processing_fee_and_refund",
        "csep_remuneration_thresholds",
        "csep_stamp4_after_permit_no_support_letter",
        "emergency_tax_first_four_weeks_single_rate_band",
        "emergency_tax_no_ppsn_all_pay_at_40_percent",
        "emergency_tax_trigger_is_missing_rpn",
        "emergency_tax_week_5_full_40_percent",
        "emergency_usc_flat_8_percent",
        "employer_50_percent_eea_workforce_rule",
        "employment_permit_is_not_residence_permission",
        "employment_permit_registration_valid_12_months",
        "entry_visa_follows_permit_if_visa_required",
        "first_job_in_state_must_be_registered_by_employee",
        "health_entitlement_rests_on_ordinary_residence",
        "health_non_eea_immigration_permission_verified",
        "health_ordinary_residence_accommodation_evidence",
        "irish_tax_status_has_three_independent_tests",
        "irp_absence_limit_90_days_rolling_year",
        "irp_registration_fee_300",
        "isd_registration_required_over_90_days",
        "landing_stamp_90_day_registration_deadline",
        "leaving_state_before_registration_needs_new_entry_visa",
        "no_ppsn_route_is_dsp_not_revenue",
        "non_resident_but_ordinarily_resident_and_domiciled",
        "permit_application_12_week_lead_time",
        "ppsn_in_person_appointment_mandatory",
        "ppsn_mygovid_basic_account_prerequisite",
        "ppsn_not_issued_at_appointment_posted_later",
        "ppsn_requires_valid_reason_job_qualifies",
        "registration_appointment_biometrics_and_irp_card",
        "registration_cannot_be_booked_before_arrival",
        "resident_and_domiciled_means_worldwide_income",
        "rpn_follows_first_job_registration"
      ],
      "expected_served_count": 38
    },
    "eea_control": {
      "nationality": "Spain",
      "nationality_class": "EU_EEA",
      "origin_country": "ES",
      "destination_country": "IE",
      "expected_served_rules": [
        "emergency_tax_first_four_weeks_single_rate_band",
        "emergency_tax_no_ppsn_all_pay_at_40_percent",
        "emergency_tax_trigger_is_missing_rpn",
        "emergency_tax_week_5_full_40_percent",
        "emergency_usc_flat_8_percent",
        "first_job_in_state_must_be_registered_by_employee",
        "health_entitlement_rests_on_ordinary_residence",
        "health_ordinary_residence_accommodation_evidence",
        "irish_tax_status_has_three_independent_tests",
        "no_ppsn_route_is_dsp_not_revenue",
        "non_resident_but_ordinarily_resident_and_domiciled",
        "ppsn_in_person_appointment_mandatory",
        "ppsn_mygovid_basic_account_prerequisite",
        "ppsn_not_issued_at_appointment_posted_later",
        "ppsn_requires_valid_reason_job_qualifies",
        "resident_and_domiciled_means_worldwide_income",
        "rpn_follows_first_job_registration"
      ],
      "expected_served_count": 17,
      "must_not_be_served": [
        "booked_appointment_within_90_days_preserves_lawful_presence",
        "burgh_quay_nationwide_registration_office",
        "cannot_hold_residence_permits_in_two_eu_states",
        "csep_nine_month_employer_lock",
        "csep_no_labour_market_needs_test",
        "csep_processing_fee_and_refund",
        "csep_remuneration_thresholds",
        "csep_stamp4_after_permit_no_support_letter",
        "employer_50_percent_eea_workforce_rule",
        "employment_permit_is_not_residence_permission",
        "employment_permit_registration_valid_12_months",
        "entry_visa_follows_permit_if_visa_required",
        "health_non_eea_immigration_permission_verified",
        "irp_absence_limit_90_days_rolling_year",
        "irp_registration_fee_300",
        "isd_registration_required_over_90_days",
        "landing_stamp_90_day_registration_deadline",
        "leaving_state_before_registration_needs_new_entry_visa",
        "permit_application_12_week_lead_time",
        "registration_appointment_biometrics_and_irp_card",
        "registration_cannot_be_booked_before_arrival"
      ]
    }
  },
  "conditional_rules": [
    "entry_visa_follows_permit_if_visa_required",
    "leaving_state_before_registration_needs_new_entry_visa"
  ],
  "non_obvious_rules": [
    "booked_appointment_within_90_days_preserves_lawful_presence",
    "cannot_hold_residence_permits_in_two_eu_states",
    "csep_nine_month_employer_lock",
    "emergency_tax_week_5_full_40_percent",
    "employer_50_percent_eea_workforce_rule",
    "employment_permit_is_not_residence_permission",
    "entry_visa_follows_permit_if_visa_required",
    "first_job_in_state_must_be_registered_by_employee",
    "health_non_eea_immigration_permission_verified",
    "irp_absence_limit_90_days_rolling_year",
    "leaving_state_before_registration_needs_new_entry_visa",
    "non_resident_but_ordinarily_resident_and_domiciled",
    "permit_application_12_week_lead_time",
    "ppsn_not_issued_at_appointment_posted_later",
    "registration_cannot_be_booked_before_arrival",
    "resident_and_domiciled_means_worldwide_income"
  ]
}
```

## Known limitation, recorded rather than hidden

`applies_to.status` on this batch is `"professional"` (an employee-type label). The profile
snapshot built by `build_profile_snapshot` carries no `status` key, so that gate **fails open**
and all 38 records pass it today. That is deliberate — suppressing a requirement on a field we
do not collect would fabricate a "nothing required". If the snapshot ever gains a `status` field
meaning something else (immigration status, say), it will collide with this label and silently
drop facts. Re-check this fixture at that point.
