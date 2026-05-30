import { apiGet } from './client';

export interface ExecSummary {
  company_id: string;
  provider: 'data_to_text' | 'llm' | string;
  period: string;
  /** Null when provider='llm' — caller keeps its own LLM-rendered summary. */
  summary: string | null;
}

export interface PolicyTldr {
  policy_id: string;
  summary: string;
  sentence_count: number;
  source_chars: number;
}

/** Data-to-text executive KPI summary for a company (Parker-J, LLM-free). */
export async function fetchExecSummary(companyId: string, signal?: AbortSignal): Promise<ExecSummary> {
  return apiGet<ExecSummary>(`/api/hr/${encodeURIComponent(companyId)}/exec-summary`, { signal });
}

/** Extractive TL;DR of a policy document (Parker-J, TextRank, LLM-free). */
export async function fetchPolicyTldr(policyId: string, signal?: AbortSignal): Promise<PolicyTldr> {
  return apiGet<PolicyTldr>(`/api/policies/${encodeURIComponent(policyId)}/tldr`, { signal });
}
