import { api } from './client';

// Supplier Registry API (admin)
export const suppliersAPI = {
  list: async (params?: {
    status?: string;
    service_category?: string;
    country_code?: string;
    city_name?: string;
    limit?: number;
    offset?: number;
  }) => {
    const response = await api.get<{ suppliers: unknown[]; total?: number }>('/api/suppliers', { params: params || {} });
    return response.data;
  },
  get: async (supplierId: string) => {
    const response = await api.get<unknown>(`/api/suppliers/${supplierId}`);
    return response.data;
  },
  listPendingCapabilities: async () => {
    const response = await api.get<{ capabilities: unknown[]; total?: number }>(
      '/api/suppliers/capabilities/pending'
    );
    return response.data;
  },
  search: async (params: {
    service_category: string;
    destination_country?: string;
    destination_city?: string;
    limit?: number;
  }) => {
    const response = await api.get<{ suppliers: unknown[]; total?: number }>('/api/suppliers/search', { params });
    return response.data;
  },
  getCategories: async () => {
    const response = await api.get<{ categories: unknown[] }>('/api/suppliers/categories');
    return response.data;
  },
  getCountries: async () => {
    const response = await api.get<{ countries: unknown[] }>('/api/suppliers/countries');
    return response.data;
  },
  create: async (payload: Record<string, unknown>) => {
    const response = await api.post<unknown>('/api/suppliers', payload);
    return response.data;
  },
  update: async (supplierId: string, payload: Record<string, unknown>) => {
    const response = await api.patch<unknown>(`/api/suppliers/${supplierId}`, payload);
    return response.data;
  },
  setStatus: async (supplierId: string, status: 'active' | 'inactive' | 'draft') => {
    const response = await api.patch<unknown>(`/api/suppliers/${supplierId}/status`, { status });
    return response.data;
  },
  addCapability: async (supplierId: string, payload: Record<string, unknown>) => {
    const response = await api.post<unknown>(`/api/suppliers/${supplierId}/capabilities`, payload);
    return response.data;
  },
  updateCapability: async (
    supplierId: string,
    capabilityId: string,
    payload: Record<string, unknown>
  ) => {
    const response = await api.patch<unknown>(
      `/api/suppliers/${supplierId}/capabilities/${capabilityId}`,
      payload
    );
    return response.data;
  },
  removeCapability: async (supplierId: string, capabilityId: string) => {
    const response = await api.delete<unknown>(
      `/api/suppliers/${supplierId}/capabilities/${capabilityId}`
    );
    return response.data;
  },
  approveCapability: async (supplierId: string, capabilityId: string, notes?: string) => {
    const response = await api.post<unknown>(
      `/api/suppliers/${supplierId}/capabilities/${capabilityId}/approve`,
      { notes }
    );
    return response.data;
  },
  rejectCapability: async (supplierId: string, capabilityId: string, notes: string) => {
    const response = await api.post<unknown>(
      `/api/suppliers/${supplierId}/capabilities/${capabilityId}/reject`,
      { notes }
    );
    return response.data;
  },
  updateScoring: async (supplierId: string, payload: Record<string, unknown>) => {
    const response = await api.patch<unknown>(`/api/suppliers/${supplierId}/scoring`, payload);
    return response.data;
  },
  getRankingDebug: async (
    supplierId: string,
    params?: { service_category?: string; destination_country?: string; destination_city?: string }
  ) => {
    const response = await api.get<unknown>(`/api/suppliers/${supplierId}/ranking-debug`, { params });
    return response.data;
  },
};

// Admin Prompt Registry API (admin only) — Parker Step D
export type PromptVersion = {
  id: string;
  task_key: string;
  version: number;
  system_prompt: string;
  user_template: string | null;
  model_name: string;
  temperature: number;
  max_tokens: number;
  status: string;
  created_at?: string;
  notes?: string | null;
};

// Parker Step E — per-version human-feedback win rate, keyed by prompt_version_id.
export type WinRate = {
  version_id: string;
  approvals: number;
  total: number;
  win_rate: number;
  ci_low: number;
  ci_high: number;
};

export const promptsAPI = {
  list: async (): Promise<PromptVersion[]> => {
    const response = await api.get<PromptVersion[]>('/api/admin/prompts');
    return response.data;
  },
  listForTask: async (taskKey: string): Promise<PromptVersion[]> => {
    const response = await api.get<PromptVersion[]>(`/api/admin/prompts/${encodeURIComponent(taskKey)}`);
    return response.data;
  },
  create: async (payload: {
    task_key: string;
    system_prompt: string;
    user_template?: string | null;
    temperature?: number;
    max_tokens?: number;
    status?: string;
    notes?: string | null;
  }) => {
    const response = await api.post<unknown>('/api/admin/prompts', payload);
    return response.data;
  },
  promote: async (versionId: string, targetStatus: string) => {
    const response = await api.post<unknown>(`/api/admin/prompts/${encodeURIComponent(versionId)}/promote`, {
      target_status: targetStatus,
    });
    return response.data;
  },
  setCanaryShare: async (taskKey: string, canaryShare: number) => {
    const response = await api.post<unknown>(`/api/admin/prompts/${encodeURIComponent(taskKey)}/canary-share`, {
      canary_share: canaryShare,
    });
    return response.data;
  },
  // Parker Step E — per-version win rates (approvals / verdicts) with Wilson CI.
  winRates: async (taskKey: string): Promise<Record<string, WinRate>> => {
    const response = await api.get<Record<string, WinRate>>(`/api/admin/prompts/${encodeURIComponent(taskKey)}/win-rates`);
    return response.data;
  },
};
