/**
 * AIQ-1602 Seg 4 — admin moderation queue for HR-proposed suppliers.
 * Pairs with backend/app/routers/admin_catalog.py (/supplier-submissions).
 */
import { apiGet, apiPatch } from './client';

export interface AdminSupplierSubmission {
  id: string;
  company_id: string;
  submitted_by_user_id: string | null;
  name: string;
  service_category: string;
  coverage_scope_type: string;
  country_code: string | null;
  city_name: string | null;
  contact_email: string | null;
  status: 'pending' | 'approved' | 'rejected';
  review_notes: string | null;
  created_supplier_id: string | null;
  created_at: string;
}

export const listSupplierSubmissions = (
  status?: string,
): Promise<{ submissions: AdminSupplierSubmission[] }> => {
  const qs = status ? `?status=${encodeURIComponent(status)}` : '';
  return apiGet(`/api/admin/catalog/supplier-submissions${qs}`);
};

export const resolveSupplierSubmission = (
  id: string,
  action: 'approve' | 'reject',
  notes?: string,
): Promise<AdminSupplierSubmission> =>
  apiPatch(`/api/admin/catalog/supplier-submissions/${encodeURIComponent(id)}`, {
    action,
    notes,
  });
