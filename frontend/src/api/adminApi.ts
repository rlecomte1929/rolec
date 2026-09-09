import { logger } from '../lib/logger';
import type {
  AdminAssignment,
  AdminAssignmentDetail,
  AdminCompany,
  AdminCompanyDetailAssignment,
  AdminCompanyDetailCounts,
  AdminCompanyDetailOrphanDiagnostics,
  AdminCompanyDetailPolicy,
  AdminContextResponse,
  AdminEmployee,
  AdminHrUser,
  AdminPoliciesByCompany,
  AdminPolicyCompany,
  AdminPolicyDetail,
  AdminPolicyTemplatesResponse,
  AdminPolicyVersion,
  AdminProfile,
  AdminRelocationCase,
  AdminSupportCase,
  AdminSupportNote,
} from '../types';
import { api, cachedRequest, invalidateApiCache, invalidateApiCachePrefix } from './client';

/** Compact readiness + evaluation snapshot from GET .../mobility/cases/{id}/inspect */
export type AdminMobilityOperationalInspect = {
  assignment_id: string | null;
  mobility_case_id: string;
  bridge_status: 'linked' | 'missing';
  readiness_flags: {
    has_mobility_link: boolean;
    has_employee_person: boolean;
    has_passport_document: boolean;
    has_evaluations: boolean;
  };
  employee_snapshot: {
    full_name: string | null;
    email: string | null;
    nationality: string | null;
    residence_country: string | null;
    passport_country: string | null;
  };
  passport_document_snapshot: {
    document_key: string | null;
    document_status: string | null;
    source_evidence_id: string | null;
    submitted_at: string | null;
  };
  latest_evaluation_summary: {
    evaluated_at: string | null;
    counts_by_status: Record<string, number>;
  };
  latest_results: Array<{
    requirement_code?: string | null;
    evaluation_status?: string | null;
    source_rule_code?: string | null;
    evaluated_at?: string | null;
  }>;
  next_actions_preview: {
    actions: Array<{
      action_title?: string | null;
      priority?: number | null;
      related_requirement_code?: string | null;
    }>;
  };
};

// Admin API
export interface AdminCompanyDetailResponse {
  company: AdminCompany | null;
  summary?: { hr_users_count: number; employee_count: number; assignments_count: number; policies_count: number };
  counts_summary?: AdminCompanyDetailCounts;
  hr_users: AdminHrUser[];
  employees: AdminEmployee[];
  assignments: AdminCompanyDetailAssignment[];
  policies: AdminCompanyDetailPolicy[];
  orphan_diagnostics?: AdminCompanyDetailOrphanDiagnostics;
}

export interface AdminRebuildTestCompanyGraphResponse {
  ok: boolean;
  summary: {
    test_company_id: string;
    profiles_linked: number;
    hr_users_linked: number;
    employees_linked: number;
    relocation_cases_linked: number;
    case_assignments_repaired: number;
    policies_linked: number;
  };
  before: Record<string, number>;
  after: Record<string, number>;
}

export interface AdminMobilityCaseInspectResponse {
  context: Record<string, unknown>;
  audit_logs: Array<Record<string, unknown>>;
  operational?: AdminMobilityOperationalInspect;
}

export const adminAPI = {
  getContext: async (): Promise<AdminContextResponse> => {
    return cachedRequest('admin:context', 20_000, async () => {
      const response = await api.get<AdminContextResponse>('/api/admin/context');
      return response.data;
    });
  },
  startImpersonation: async (payload: { targetUserId: string; mode: 'hr' | 'employee'; reason?: string }): Promise<{ ok: boolean; impersonation: { targetUserId: string; mode: 'hr' | 'employee' } }> => {
    const response = await api.post<{ ok: boolean; impersonation: { targetUserId: string; mode: 'hr' | 'employee' } }>('/api/admin/impersonate/start', payload);
    invalidateApiCache('admin:context');
    return response.data;
  },
  stopImpersonation: async (): Promise<{ ok: boolean }> => {
    const response = await api.post<{ ok: boolean }>('/api/admin/impersonate/stop');
    invalidateApiCache('admin:context');
    return response.data;
  },
  listCompanies: async (q?: string): Promise<{ companies: AdminCompany[] }> => {
    const key = `admin:companies:${q ?? ''}`;
    return cachedRequest(key, 60_000, async () => {
      const response = await api.get<{ companies: AdminCompany[] }>('/api/admin/companies', { params: { q } });
      return response.data;
    });
  },
  getCompanyDetail: async (companyId: string): Promise<AdminCompanyDetailResponse> => {
    const response = await api.get<AdminCompanyDetailResponse>(`/api/admin/companies/${companyId}`);
    return response.data;
  },
  createCompany: async (payload: {
    name: string;
    country?: string;
    size_band?: string;
    status?: string;
    plan_tier?: string;
    hr_seat_limit?: number;
    employee_seat_limit?: number;
    address?: string;
    phone?: string;
    hr_contact?: string;
    support_email?: string;
  }): Promise<{ company: AdminCompany }> => {
    const response = await api.post<{ company: AdminCompany }>('/api/admin/companies', payload);
    invalidateApiCachePrefix('admin:companies:');
    return response.data;
  },
  updateCompany: async (
    companyId: string,
    payload: Partial<{
      name: string;
      country: string;
      size_band: string;
      status: string;
      plan_tier: string;
      hr_seat_limit: number;
      employee_seat_limit: number;
      address: string;
      phone: string;
      hr_contact: string;
      support_email: string;
    }>
  ): Promise<{ company: AdminCompany }> => {
    const response = await api.patch<{ company: AdminCompany }>(`/api/admin/companies/${companyId}`, payload);
    invalidateApiCachePrefix('admin:companies:');
    return response.data;
  },
  deactivateCompany: async (companyId: string): Promise<{ company: AdminCompany; message?: string }> => {
    const response = await api.post<{ company: AdminCompany; message?: string }>(`/api/admin/companies/${companyId}/deactivate`);
    invalidateApiCachePrefix('admin:companies:');
    return response.data;
  },
  /** Soft delete: sets status='archived' so the company is hidden from active lists. Reversible. */
  archiveCompany: async (companyId: string): Promise<{ company: AdminCompany; message?: string }> => {
    const response = await api.post<{ company: AdminCompany; message?: string }>(`/api/admin/companies/${companyId}/archive`);
    invalidateApiCachePrefix('admin:companies:');
    return response.data;
  },
  /** Hard delete: removes the company row. Irreversible — orphans references in employees/hr_users/profiles/etc. */
  deleteCompany: async (companyId: string): Promise<{ deleted: string; message?: string }> => {
    const response = await api.delete<{ deleted: string; message?: string }>(`/api/admin/companies/${companyId}`);
    invalidateApiCachePrefix('admin:companies:');
    return response.data;
  },
  runReconciliationBackfillTestCompany: async (): Promise<{ ok: boolean; summary?: { test_company_id: string; profiles_linked: number; hr_users_linked: number; relocation_cases_linked: number }; error?: string }> => {
    const response = await api.post<{ ok: boolean; summary?: { test_company_id: string; profiles_linked: number; hr_users_linked: number; relocation_cases_linked: number }; error?: string }>('/api/admin/reconciliation/backfill-test-company');
    return response.data;
  },
  rebuildTestCompanyGraph: async (): Promise<AdminRebuildTestCompanyGraphResponse> => {
    const response = await api.post<AdminRebuildTestCompanyGraphResponse>('/api/admin/reconciliation/rebuild-test-company-graph');
    return response.data;
  },
  listProfiles: async (params?: { q?: string; company_id?: string; role?: string }): Promise<{ profiles: AdminProfile[]; summary?: { count: number; orphans_without_company?: number } }> => {
    const response = await api.get<{ profiles: AdminProfile[]; summary?: { count: number; orphans_without_company?: number } }>('/api/admin/users', { params: params || {} });
    return response.data;
  },
  listPeople: async (params?: { company_id?: string; role?: string; q?: string }): Promise<{ people: AdminProfile[]; summary?: { count: number; orphans_without_company?: number } }> => {
    const response = await api.get<{ people: AdminProfile[]; summary?: { count: number; orphans_without_company?: number } }>('/api/admin/people', { params: params || {} });
    return response.data;
  },
  createPerson: async (payload: { email: string; full_name?: string; role?: string; company_id?: string; password?: string }): Promise<{ person: AdminProfile; invite_sent?: boolean; invite_error?: string; login_ready?: boolean }> => {
    const response = await api.post<{ person: AdminProfile; invite_sent?: boolean; invite_error?: string; login_ready?: boolean }>('/api/admin/people', payload);
    return response.data;
  },
  updatePerson: async (personId: string, payload: Partial<{ full_name: string; role: string; company_id: string; status: string }>): Promise<{ person: AdminProfile }> => {
    const response = await api.patch<{ person: AdminProfile }>(`/api/admin/people/${personId}`, payload);
    return response.data;
  },
  assignPersonCompany: async (personId: string, companyId: string): Promise<{ person: AdminProfile }> => {
    const response = await api.post<{ person: AdminProfile }>(`/api/admin/people/${personId}/assign-company`, { company_id: companyId });
    return response.data;
  },
  setPersonRole: async (personId: string, role: string): Promise<{ person: AdminProfile }> => {
    const response = await api.post<{ person: AdminProfile }>(`/api/admin/people/${personId}/set-role`, { role });
    return response.data;
  },
  deactivatePerson: async (personId: string): Promise<{ person: AdminProfile }> => {
    const response = await api.post<{ person: AdminProfile }>(`/api/admin/people/${personId}/deactivate`);
    return response.data;
  },
  listEmployees: async (companyId?: string): Promise<{ employees: AdminEmployee[] }> => {
    const response = await api.get<{ employees: AdminEmployee[] }>('/api/admin/employees', { params: { company_id: companyId } });
    return response.data;
  },
  listHrUsers: async (companyId?: string): Promise<{ hr_users: AdminHrUser[] }> => {
    const response = await api.get<{ hr_users: AdminHrUser[] }>('/api/admin/hr-users', { params: { company_id: companyId } });
    return response.data;
  },
  listRelocations: async (params?: { company_id?: string; status?: string }): Promise<{ relocations: AdminRelocationCase[] }> => {
    const response = await api.get<{ relocations: AdminRelocationCase[] }>('/api/admin/relocations', { params });
    return response.data;
  },
  listAssignments: async (params?: {
    company_id?: string;
    employee_user_id?: string;
    employee_search?: string;
    status?: string;
    destination_country?: string;
  }): Promise<{ assignments: AdminAssignment[] }> => {
    const response = await api.get<{ assignments: AdminAssignment[] }>('/api/admin/assignments', { params });
    return response.data;
  },
  getAssignmentDetail: async (assignmentId: string): Promise<{ assignment: AdminAssignmentDetail }> => {
    const response = await api.get<{ assignment: AdminAssignmentDetail }>(`/api/admin/assignments/${assignmentId}`);
    return response.data;
  },
  reassignEmployeeCompany: async (assignmentId: string, payload: { reason: string; company_id: string }): Promise<{ ok: boolean }> => {
    const response = await api.patch<{ ok: boolean }>(`/api/admin/assignments/${assignmentId}/reassign-employee-company`, payload);
    return response.data;
  },
  reassignHrOwner: async (assignmentId: string, payload: { reason: string; hr_user_id: string }): Promise<{ ok: boolean }> => {
    const response = await api.patch<{ ok: boolean }>(`/api/admin/assignments/${assignmentId}/reassign-hr-owner`, payload);
    return response.data;
  },
  fixAssignmentCompanyLinkage: async (assignmentId: string, payload: { reason: string; company_id: string }): Promise<{ ok: boolean }> => {
    const response = await api.patch<{ ok: boolean }>(`/api/admin/assignments/${assignmentId}/fix-company-linkage`, payload);
    return response.data;
  },
  updateAssignmentStatus: async (assignmentId: string, payload: { status: string }): Promise<{ ok: boolean; status: string }> => {
    const response = await api.patch<{ ok: boolean; status: string }>(`/api/admin/assignments/${assignmentId}/status`, payload);
    return response.data;
  },
  // Force an eligibility decision for one requirement category on an assignment
  // (POST /api/admin/actions/override-eligibility — reason required, audit-logged).
  overrideEligibility: async (payload: {
    assignment_id: string;
    category: string;
    allowed: boolean;
    reason: string;
    note?: string;
  }): Promise<{ ok: boolean }> => {
    const response = await api.post<{ ok: boolean }>('/api/admin/actions/override-eligibility', {
      reason: payload.reason,
      payload: {
        assignment_id: payload.assignment_id,
        category: payload.category,
        allowed: payload.allowed,
        note: payload.note,
      },
    });
    return response.data;
  },
  // Reactivate a stuck relocation case (status-only; never null-overwrites other fields).
  // `unlocked` reports whether a case actually matched the id.
  unlockCase: async (payload: { case_id: string; reason: string }): Promise<{ ok: boolean; unlocked: boolean }> => {
    const response = await api.post<{ ok: boolean; unlocked: boolean }>('/api/admin/actions/unlock-case', {
      reason: payload.reason,
      payload: { case_id: payload.case_id },
    });
    return response.data;
  },
  createAssignment: async (payload: {
    company_id: string;
    hr_user_id: string;
    employee_user_id?: string;
    employee_identifier?: string;
    destination_country?: string;
  }): Promise<{ ok: boolean; assignment_id: string; case_id: string }> => {
    const response = await api.post<{ ok: boolean; assignment_id: string; case_id: string }>('/api/admin/assignments', payload);
    return response.data;
  },
  listPolicyOverview: async (params?: { company_id?: string }): Promise<{ companies: AdminPolicyCompany[] }> => {
    try {
      const response = await api.get<{ companies: AdminPolicyCompany[] }>('/api/admin/policies/overview', { params });
      return response.data;
    } catch {
      return { companies: [] };
    }
  },
  listAdminPolicies: async (companyId: string): Promise<AdminPoliciesByCompany> => {
    const response = await api.get<AdminPoliciesByCompany>('/api/admin/policies', { params: { company_id: companyId } });
    return response.data;
  },
  getAdminPolicyDetail: async (policyId: string): Promise<AdminPolicyDetail> => {
    const response = await api.get<AdminPolicyDetail>(`/api/admin/policies/${policyId}`);
    return response.data;
  },
  getAdminPolicyVersions: async (policyId: string): Promise<{ policy_id: string; versions: AdminPolicyVersion[] }> => {
    const response = await api.get<{ policy_id: string; versions: AdminPolicyVersion[] }>(`/api/admin/policies/${policyId}/versions`);
    return response.data;
  },
  patchAdminPolicy: async (
    policyId: string,
    payload: { title?: string; version?: string; effective_date?: string; publish_version_id?: string; unpublish?: boolean }
  ): Promise<AdminPolicyDetail> => {
    const response = await api.patch<AdminPolicyDetail>(`/api/admin/policies/${policyId}`, payload);
    return response.data;
  },
  /** Legacy / optional. Never throws — callers must not tie page load to this result. */
  listAdminPolicyTemplates: async (): Promise<AdminPolicyTemplatesResponse> => {
    try {
      const response = await api.get<AdminPolicyTemplatesResponse>('/api/admin/policies/templates');
      return response.data ?? { templates: [] };
    } catch (e) {
      logger.warn('[adminAPI] listAdminPolicyTemplates failed (non-blocking)', e);
      return { templates: [] };
    }
  },
  applyDefaultTemplateToCompany: async (
    companyId: string,
    opts?: { template_id?: string; overwrite_existing?: boolean }
  ): Promise<{ ok: boolean; policy_id?: string; version_id?: string; error?: string }> => {
    const response = await api.post<{ ok: boolean; policy_id?: string; version_id?: string; error?: string }>('/api/admin/policies/apply-default-template', {
      company_id: companyId,
      template_id: opts?.template_id,
      overwrite_existing: opts?.overwrite_existing ?? false,
    });
    return response.data;
  },
  getPolicyAssistantCompanyHistory: async (companyId: string): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>(`/api/admin/policies/company/${companyId}/history`);
    return response.data;
  },
  getPolicyAssistantSnapshotDiff: async (
    companyId: string,
    olderSnapshotId: string,
    newerSnapshotId: string
  ): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>(`/api/admin/policies/company/${companyId}/diff`, {
      params: { older_snapshot_id: olderSnapshotId, newer_snapshot_id: newerSnapshotId },
    });
    return response.data;
  },
  listPolicyAssistantAnswerAudits: async (params: {
    company_id: string;
    case_id?: string;
    snapshot_id?: string;
    evidence_status?: string;
    created_after?: string;
    created_before?: string;
    limit?: number;
  }): Promise<{ audits: Record<string, unknown>[] }> => {
    const response = await api.get<{ audits: Record<string, unknown>[] }>('/api/admin/policies/answers/audits', { params });
    return response.data;
  },
  listSupportCases: async (params?: { status?: string; severity?: string; company_id?: string; priority?: string }): Promise<{ support_cases: AdminSupportCase[] }> => {
    const response = await api.get<{ support_cases: AdminSupportCase[] }>('/api/admin/support-cases', { params });
    return response.data;
  },
  patchSupportCase: async (
    caseId: string,
    payload: { priority?: string; status?: string; assignee_id?: string | null; category?: string }
  ): Promise<AdminSupportCase> => {
    const response = await api.patch<AdminSupportCase>(`/api/admin/support-cases/${caseId}`, payload);
    return response.data;
  },
  listMessageThreads: async (params?: {
    company_id?: string;
    user_id?: string;
    thread_type?: 'hr_employee' | 'collaboration';
    limit?: number;
    offset?: number;
  }): Promise<unknown> => {
    const response = await api.get<unknown>('/api/admin/messages/threads', { params });
    return response.data;
  },
  getHrThreadDetail: async (assignmentId: string): Promise<unknown> => {
    const response = await api.get<unknown>(`/api/admin/messages/threads/hr-employee/${assignmentId}`);
    return response.data;
  },
  listSupportNotes: async (caseId: string): Promise<{ notes: AdminSupportNote[] }> => {
    const response = await api.get<{ notes: AdminSupportNote[] }>(`/api/admin/support-cases/${caseId}/notes`);
    return response.data;
  },
  addSupportNote: async (caseId: string, payload: { note: string; reason: string }): Promise<unknown> => {
    const response = await api.post<unknown>(`/api/admin/support-cases/${caseId}/notes`, payload);
    return response.data;
  },
  adminAction: async (action: string, payload: { reason: string; breakGlass?: boolean; payload?: unknown }): Promise<unknown> => {
    const response = await api.post<unknown>(`/api/admin/actions/${action}`, payload);
    return response.data;
  },
  getReconciliationReport: async (): Promise<unknown> => {
    const response = await api.get<unknown>('/api/admin/reconciliation/report');
    return response.data;
  },
  reconciliationLinkPersonCompany: async (profileId: string, companyId: string): Promise<unknown> => {
    const response = await api.post<unknown>('/api/admin/reconciliation/link-person-company', { profile_id: profileId, company_id: companyId });
    return response.data;
  },
  reconciliationLinkAssignmentCompany: async (assignmentId: string, companyId: string, reason: string): Promise<unknown> => {
    const response = await api.post<unknown>('/api/admin/reconciliation/link-assignment-company', {
      assignment_id: assignmentId,
      company_id: companyId,
      reason,
    });
    return response.data;
  },
  reconciliationLinkAssignmentPerson: async (assignmentId: string, profileId: string): Promise<unknown> => {
    const response = await api.post<unknown>('/api/admin/reconciliation/link-assignment-person', {
      assignment_id: assignmentId,
      profile_id: profileId,
    });
    return response.data;
  },
  reconciliationLinkPolicyCompany: async (policyId: string, companyId: string): Promise<unknown> => {
    const response = await api.post<unknown>('/api/admin/reconciliation/link-policy-company', {
      policy_id: policyId,
      company_id: companyId,
    });
    return response.data;
  },
  listResearchCandidates: async (params?: { destination_country?: string; status?: string }): Promise<unknown> => {
    const response = await api.get<unknown>('/api/admin/research/candidates', { params });
    return response.data;
  },
  researchHealth: async (params: { destination: string }): Promise<unknown> => {
    const response = await api.get<unknown>('/api/admin/research/health', { params });
    return response.data;
  },
  approveResearchCandidate: async (candidateId: string, payload: { domain_area: string }): Promise<unknown> => {
    const response = await api.post<unknown>(`/api/admin/research/candidates/${candidateId}/approve`, payload);
    return response.data;
  },
  ingestUrl: async (payload: { url: string; destination_country: string; domain_area: string }): Promise<unknown> => {
    const response = await api.post<unknown>('/api/admin/ingest/url', payload);
    return response.data;
  },
  ingestBatch: async (payload: { urls: Array<string | { url: string; domain_area?: string }>; destination_country: string; domain_area?: string }): Promise<unknown> => {
    const response = await api.post<unknown>('/api/admin/ingest/batch', payload);
    return response.data;
  },
  listIngestJobs: async (params?: { status?: string }): Promise<unknown> => {
    const response = await api.get<unknown>('/api/admin/ingest/jobs', { params });
    return response.data;
  },
  listKnowledgeDocs: async (params: { destination_country: string }): Promise<unknown> => {
    const response = await api.get<unknown>('/api/admin/knowledge/docs', { params });
    return response.data;
  },
  listRequirementEntities: async (params: { destination: string; status?: string }): Promise<unknown> => {
    const response = await api.get<unknown>('/api/admin/requirements/entities', { params });
    return response.data;
  },
  listRequirementFacts: async (entityId: string, params?: { status?: string }): Promise<unknown> => {
    const response = await api.get<unknown>(`/api/admin/requirements/entities/${entityId}/facts`, { params });
    return response.data;
  },
  listRequirementCriteria: async (params: { destination: string; status?: string }): Promise<unknown> => {
    const response = await api.get<unknown>('/api/admin/requirements/criteria', { params });
    return response.data;
  },
  approveRequirementFacts: async (payload: { fact_ids: string[] }): Promise<unknown> => {
    const response = await api.post<unknown>('/api/admin/requirements/facts/approve', payload);
    return response.data;
  },
  rejectRequirementFacts: async (payload: { fact_ids: string[] }): Promise<unknown> => {
    const response = await api.post<unknown>('/api/admin/requirements/facts/reject', payload);
    return response.data;
  },
  /** Mobility graph: case context + audit logs (admin JWT). */
  inspectMobilityCase: async (
    caseId: string
  ): Promise<AdminMobilityCaseInspectResponse> => {
    const response = await api.get<AdminMobilityCaseInspectResponse>(`/api/admin/mobility/cases/${encodeURIComponent(caseId)}/inspect`);
    return response.data;
  },
  /** Run requirement evaluation for the assignment linked to a mobility case (admin JWT). */
  evaluateMobilityAssignmentRequirements: async (assignmentId: string): Promise<unknown> => {
    const response = await api.post<unknown>(
      `/api/admin/mobility/assignments/${encodeURIComponent(assignmentId)}/evaluate-requirements`
    );
    return response.data;
  },
  /** AIQ-1219: Upload a policy PDF/DOCX and get a workflow summary. */
  analyzePolicy: async (file: File): Promise<PolicyAnalysisResult> => {
    const form = new FormData();
    form.append('file', file);
    const response = await api.post<PolicyAnalysisResult>('/api/admin/policy-analysis', form, { timeout: 120_000 });
    return response.data;
  },
};

export interface PolicyWorkflowSummary {
  policy_title: string | null;
  effective_date: string | null;
  tiers: Array<{ name: string; bands: string[]; benefits_count: number }>;
  tasks: Array<{ category: string; task: string; owner: string; benefit_key: string; confidence: number }>;
  timeline: Array<{ phase: string; duration: string; tasks: string[] }>;
  cost_summary: {
    total_range: { min: number; max: number; currency: string } | null;
    by_category: Array<{ category: string; estimated_range: { min: number; max: number; currency: string } }>;
    note: string;
  };
  benefits_count: number;
}

export interface PolicyAnalysisResult {
  workflow_summary: PolicyWorkflowSummary;
  extraction: {
    llm_used: boolean;
    llm_unavailable_reason: string | null;
    model: string | null;
    truncated: boolean;
    benefits_count: number;
  };
  elapsed_ms: number;
}
