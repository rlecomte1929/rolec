/**
 * relocationPolicy.ts
 * Shared types for the HR Policy Builder (AIQ-37-B).
 */

// ── JSON schema stored in policy_versions.json_schema ─────────────────────

export interface PolicyTier {
  id: string;
  name: string;
  /** Employee grade/level codes, e.g. ["VP", "Director"] */
  qualifying_levels: string[];
  description?: string;
}

export interface BudgetCap {
  cap_type: 'absolute' | 'salary_multiple';
  /** Absolute amount in `currency`, or salary multiplier depending on cap_type */
  amount: number;
  currency: string;
}

/** tierId → corridorKey → BudgetCap  e.g. budgets["tier-abc"]["*→US"] */
export type PolicyBudgets = Record<string, Record<string, BudgetCap>>;

/** visaType → list of required document keys  e.g. documents["work_permit"] = ["passport", "cv"] */
export type PolicyDocuments = Record<string, string[]>;

export interface VendorCategoryRule {
  preferred_vendor_ids?: string[];
  open_market: boolean;
  notes?: string;
}

export type PolicyVendorCategories = Record<string, VendorCategoryRule>;

export interface PolicyApprovalWorkflow {
  auto_approve_under_cap: boolean;
  approver_user_ids?: string[];
  notes?: string;
}

export interface RelocationPolicyJson {
  tiers: PolicyTier[];
  budgets: PolicyBudgets;
  documents: PolicyDocuments;
  vendor_categories: PolicyVendorCategories;
  approval_workflow: PolicyApprovalWorkflow;
}

// ── DB row shape (policy_versions table) ──────────────────────────────────

export interface RelocationPolicyRow {
  id: string;
  company_id: string;
  label: string;
  status: 'draft' | 'active' | 'archived';
  json_schema: RelocationPolicyJson;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

// ── API response types ─────────────────────────────────────────────────────

export interface PolicyVersionListResponse {
  policies: RelocationPolicyRow[];
}

export interface ActivePolicyResponse {
  policy: RelocationPolicyRow | null;
}

export interface CreatePolicyVersionRequest {
  label?: string;
  json_schema: RelocationPolicyJson;
}
