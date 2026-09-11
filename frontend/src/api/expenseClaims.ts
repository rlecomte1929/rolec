/**
 * Expense claims API ([AIQ-2271]).
 *
 * POST/GET /api/cases/:caseId/expense-claims
 * PATCH    /api/expense-claims/:id
 */

import api from './client';

export type ExpenseClaimStatus =
  | 'draft'
  | 'submitted'
  | 'approved'
  | 'rejected'
  | 'paid';

export interface ExpenseClaimLine {
  id?: string;
  benefit_key: string;
  amount: number;
  currency: string;
  cap_currency?: string | null;
  fx_rate_to_cap?: number | null;
  fx_rate_date?: string | null;
  amount_in_cap_currency?: number | null;
  receipt_ocr_id?: string | null;
  vendor_name?: string | null;
  expense_date?: string | null;
}

export interface ExpenseClaim {
  id: string;
  case_id: string;
  company_id: string;
  employee_user_id?: string | null;
  status: ExpenseClaimStatus;
  hr_note?: string | null;
  created_at?: string | null;
  lines: ExpenseClaimLine[];
}

export interface ExpenseClaimCreateBody {
  status?: 'draft' | 'submitted';
  lines: ExpenseClaimLine[];
}

export const expenseClaimsAPI = {
  list: async (caseId: string): Promise<ExpenseClaim[]> => {
    const { data } = await api.get<ExpenseClaim[]>(`/api/cases/${caseId}/expense-claims`);
    return data;
  },
  create: async (caseId: string, body: ExpenseClaimCreateBody): Promise<ExpenseClaim> => {
    const { data } = await api.post<ExpenseClaim>(`/api/cases/${caseId}/expense-claims`, body);
    return data;
  },
  patch: async (
    claimId: string,
    body: { status: ExpenseClaimStatus; hr_note?: string },
  ): Promise<ExpenseClaim> => {
    const { data } = await api.patch<ExpenseClaim>(`/api/expense-claims/${claimId}`, body);
    return data;
  },
};
