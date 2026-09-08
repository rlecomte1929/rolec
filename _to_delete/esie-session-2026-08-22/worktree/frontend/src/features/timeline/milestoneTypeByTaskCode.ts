/**
 * Maps canonical plan `task_code` → `case_milestones.milestone_type` for PATCH / timeline parity.
 * Keep in sync with `backend/relocation_plan_task_library.py`.
 */
export const MILESTONE_TYPE_BY_TASK_CODE: Record<string, string> = {
  confirm_employee_core_profile: 'task_profile_core',
  confirm_family_details: 'task_family_dependents',
  upload_passport_copy: 'task_passport_upload',
  upload_assignment_letter: 'task_employment_letter',
  verify_destination_route: 'task_route_verify',
  hr_review_case_data: 'task_hr_case_review',
  schedule_immigration_review: 'task_immigration_review',
  prepare_visa_pack: 'task_visa_docs_prep',
  submit_visa_application: 'task_visa_submit',
  book_biometrics: 'task_biometrics',
  arrange_temporary_housing: 'task_temp_housing',
  arrange_movers: 'task_movers_shipment',
  coordinate_relocation_providers: 'task_provider_coordination',
  plan_travel: 'task_travel_plan',
  complete_arrival_registration: 'task_arrival_registration',
  tax_local_registration: 'task_tax_local_registration',
  settle_in: 'task_settling_in',
};

export function milestoneTypeForTaskCode(taskCode: string): string {
  return MILESTONE_TYPE_BY_TASK_CODE[taskCode] || taskCode;
}
