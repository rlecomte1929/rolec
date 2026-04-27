/**
 * Frontend shapes for GET/PUT policy-config matrix API (snake_case, aligned with
 * backend PolicyConfigBenefitRead / working payload from PolicyConfigMatrixService).
 */

/**
 * Section C: per-(jurisdiction × employee_level × assignment_type) override
 * row that hangs off a base PolicyConfigBenefitRow. Empty axes
 * (employee_level / assignment_type === null) are wildcards. Empty
 * fields (amount_value, currency_code, etc.) inherit from the base row
 * — HR can override only the markdown clauses for a region without
 * redefining the cap. Country list is ISO-3166 alpha-2.
 */
export type PolicyJurisdictionOverride = {
  id?: string | null;
  jurisdiction_countries: string[];
  employee_level?: string | null;
  assignment_type?: string | null;
  amount_value?: number | null;
  currency_code?: string | null;
  cap_rule_json?: Record<string, unknown>;
  reimbursement_md?: string | null;
  repayment_md?: string | null;
  display_order?: number;
};

export type PolicyConfigBenefitRow = {
  id?: string | null;
  category?: string;
  benefit_key?: string;
  benefit_label?: string;
  covered?: boolean;
  value_type?: string;
  amount_value?: number | null;
  currency_code?: string | null;
  percentage_value?: number | null;
  unit_frequency?: string;
  notes?: string | null;
  conditions_json?: Record<string, unknown>;
  assignment_types?: string[];
  family_statuses?: string[];
  employee_levels?: string[];
  display_order?: number;
  cap_rule_json?: Record<string, unknown>;
  allowance_cap?: Record<string, unknown> | null;
  is_active?: boolean;
  targeting_signature?: string;
  maximum_budget_explanation?: string;
  /** Section C overrides authored on this benefit row. Empty list when none. */
  jurisdiction_overrides?: PolicyJurisdictionOverride[];
  /** Employee read-side: which override (if any) was applied to resolve this row. */
  override_applied?: boolean;
  override_id?: string | null;
};

export type PolicyConfigCategoryBlock = {
  category_key?: string;
  category_label?: string;
  benefits?: PolicyConfigBenefitRow[];
};

export type PolicyConfigWorkingPayload = {
  policy_version?: string | null;
  version_number?: number | null;
  effective_date?: string;
  status?: string;
  published_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  editable?: boolean;
  source?: string;
  assignment_types_supported?: string[];
  family_statuses_supported?: string[];
  employee_levels_supported?: string[];
  categories?: PolicyConfigCategoryBlock[];
  preview_context?: {
    assignment_type?: string | null;
    family_status?: string | null;
    employee_level?: string | null;
    effective_rows_only?: boolean;
    note?: string;
  };
};

export type PolicyConfigHistoryVersion = {
  id: string;
  version_number: number;
  status: string;
  effective_date: string;
  created_at?: string | null;
  published_at?: string | null;
  created_by?: string | null;
};
