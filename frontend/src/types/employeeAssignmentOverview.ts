/** Shapes from GET /api/employee/assignments/overview (snake_case keys from API). */
export type EmployeeOverviewCompany = {
  id?: string | null;
  name?: string | null;
};

export type EmployeeOverviewDestination = {
  label?: string | null;
  host_country?: string | null;
  home_country?: string | null;
};

export type EmployeeLinkedOverviewRow = {
  assignment_id: string;
  case_id?: string | null;
  company?: EmployeeOverviewCompany;
  destination?: EmployeeOverviewDestination;
  status?: string;
  created_at?: string | null;
  updated_at?: string | null;
  current_stage?: string | null;
  relocation_case_status?: string | null;
};

export type EmployeePendingClaimInfo = {
  state?: string;
  requires_explicit_claim?: boolean;
  extra_verification_required?: boolean;
};

export type EmployeePendingOverviewRow = {
  assignment_id: string;
  case_id?: string | null;
  company?: EmployeeOverviewCompany;
  destination?: EmployeeOverviewDestination;
  created_at?: string | null;
  claim?: EmployeePendingClaimInfo;
};
