/**
 * Frontend shapes for GET/PUT policy-config matrix API (snake_case, aligned with
 * backend PolicyConfigBenefitRead / working payload from PolicyConfigMatrixService).
 */
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
  display_order?: number;
  cap_rule_json?: Record<string, unknown>;
  allowance_cap?: Record<string, unknown> | null;
  is_active?: boolean;
  targeting_signature?: string;
  maximum_budget_explanation?: string;
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
  categories?: PolicyConfigCategoryBlock[];
  preview_context?: {
    assignment_type?: string | null;
    family_status?: string | null;
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
