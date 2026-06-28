/**
 * [P2-6 / P2-8] policyBuilderPipeline.ts
 *
 * API client for the policy extraction pipeline review queue and document
 * management endpoints.
 *
 * Endpoints consumed:
 *   GET  /api/hr/policy-builder/review              → ReviewQueueResponse
 *   PATCH /api/hr/policy-builder/review/:factId     → ReviewItemActionResponse
 *   GET  /api/hr/policy-builder/conflicts/:conflictId → ConflictDetailResponse
 */
import api from './client';

// ---------------------------------------------------------------------------
// Review queue types
// ---------------------------------------------------------------------------

export type ReviewItemStatus = 'pending' | 'validated' | 'rejected' | 'edited';

export interface ReviewConflictSummary {
  conflict_id: string;
  severity: 'high' | 'medium';
  other_source_doc: string;
  other_value: string | number | null;
  other_page?: number | null;
}

export interface ReviewQueueItem {
  /** policy_facts.id */
  id: string;
  category_code: string;
  category_display_name: string;
  tier: string | null;
  value: string | number | null;
  unit: string | null;
  currency: string | null;
  source_doc: string;
  source_page: number | null;
  source_quote: string | null;
  confidence_score: number | null;
  ambiguity_flag: boolean;
  status: ReviewItemStatus;
  /** HR's edited value (set when status === 'edited') */
  hr_override_value: string | null;
  /** HR's rejection reason (set when status === 'rejected') */
  rejection_note: string | null;
  conflicts: ReviewConflictSummary[];
  fact_type: string;
  snapshot_id: string;
}

export interface ReviewQueueResponse {
  items: ReviewQueueItem[];
  snapshot_id: string | null;
  document_name: string | null;
  total: number;
  pending: number;
  approved: number;
  rejected: number;
  conflicts_remaining: number;
}

export type ReviewAction = 'approve' | 'edit' | 'reject';

export interface ReviewItemActionRequest {
  action: ReviewAction;
  /** For edit: the corrected value */
  hr_override_value?: string | null;
  /** For reject: optional HR note */
  rejection_note?: string | null;
}

export interface ReviewItemActionResponse {
  ok: boolean;
  item: ReviewQueueItem;
}

// ---------------------------------------------------------------------------
// Document management types
// ---------------------------------------------------------------------------

export type PipelineStatus =
  | 'uploaded'
  | 'extracting_text'
  | 'text_ready'
  | 'extracting_facts'
  | 'ready_for_assistant'
  | 'failed';

export interface PolicyDocumentRow {
  id: string;
  filename: string;
  file_size_bytes: number | null;
  uploaded_by_name: string | null;
  uploaded_by_id: string | null;
  uploaded_at: string;
  assistant_import_status: PipelineStatus | null;
  sha256_hash: string | null;
  extracted_value_count: number;
  snapshot_id: string | null;
  /** Per-category extraction summary for expandable row */
  category_summary: Array<{
    category_code: string;
    category_display_name: string;
    value: string | null;
    unit: string | null;
    currency: string | null;
    confidence_score: number | null;
    status: ReviewItemStatus | null;
  }>;
  error_message?: string | null;
}

export interface PolicyDocumentsListResponse {
  documents: PolicyDocumentRow[];
}

export type DiffChangeType = 'added' | 'removed' | 'modified' | 'unchanged';

export interface DiffEntry {
  category_code: string;
  category_display_name: string;
  change_type: DiffChangeType;
  value_before: string | null;
  value_after: string | null;
  unit_before: string | null;
  unit_after: string | null;
  currency_before: string | null;
  currency_after: string | null;
}

export interface DocumentDiffResponse {
  document_a_name: string;
  document_b_name: string;
  entries: DiffEntry[];
  added_count: number;
  removed_count: number;
  modified_count: number;
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export const policyBuilderPipelineAPI = {
  /** Fetch HR review queue for the latest ingestion snapshot */
  getReviewQueue: async (params?: { snapshot_id?: string }): Promise<ReviewQueueResponse> => {
    const response = await api.get<ReviewQueueResponse>('/api/hr/policy-builder/review', { params });
    return response.data;
  },

  /** Approve, edit, or reject a single review queue item */
  actionReviewItem: async (
    factId: string,
    body: ReviewItemActionRequest,
  ): Promise<ReviewItemActionResponse> => {
    const response = await api.patch<ReviewItemActionResponse>(`/api/hr/policy-builder/review/${factId}`, body);
    return response.data;
  },

  /** List all uploaded policy documents with pipeline status */
  listDocuments: async (): Promise<PolicyDocumentsListResponse> => {
    const response = await api.get<PolicyDocumentsListResponse>('/api/hr/policy-builder/documents');
    return response.data;
  },

  /** Diff two document snapshots */
  diffDocuments: async (
    snapshotAId: string,
    snapshotBId: string,
  ): Promise<DocumentDiffResponse> => {
    const response = await api.get<DocumentDiffResponse>('/api/hr/policy-builder/documents/diff', {
      params: { snapshot_a: snapshotAId, snapshot_b: snapshotBId },
    });
    return response.data;
  },
};
