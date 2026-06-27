/**
 * Documents API client.
 *
 * Phase 1 (backend) shipped a dedicated case-scoped documents surface:
 *   GET  /api/cases/{caseId}/documents  → the case's FULL required-docs set
 *        [{ key, label, status, uploaded_at, file_url }]   (un-uploaded items have status 'required')
 *   POST /api/cases/{caseId}/documents  → multipart { file, document_key, requirement_id? }
 *
 * `documentsAPI.list` maps each CaseDocumentDTO → DocumentItem; `upload` posts the
 * row's document_key so the backend knows which requirement the file satisfies.
 */

import type { DocStatus } from '../types/relopass-api-contracts';
import type { DocumentItem, RequirementCategory } from '../features/platform-v2/documents/DocumentsScreen';
import api from './client';

// ── Backend contract ─────────────────────────────────────────────────────────

/** Shape returned by GET /api/cases/{caseId}/documents. */
interface CaseDocumentDTO {
  key: string;
  label: string;
  status: string;
  uploaded_at: string | null;
  file_url: string | null;
}

// ── document_key → UI category ───────────────────────────────────────────────
//
// The category is purely presentational (which accordion the row sits in). We
// derive it from the document_key via keyword rules and fall back to a sensible
// default so an unknown key always lands somewhere visible.

const KEY_CATEGORY_RULES: ReadonlyArray<readonly [RegExp, RequirementCategory]> = [
  [/passport|national_id|\bid_|identity|birth|photo|biometric/, 'Identity & travel'],
  [/visa|permit|residence|immigration|registration|blue_card/, 'Immigration & permits'],
  [/employment|contract|offer|payslip|salary|reference_letter|employer/, 'Employment'],
  [/lease|address|housing|rental|utility|accommodation|tenancy/, 'Housing & relocation'],
  [/tax|bank|financial|income|statement/, 'Financial & tax'],
  [/marriage|family|child|dependent|spouse|school|partner/, 'Family & dependents'],
];

function keyToCategory(key: string): RequirementCategory {
  const k = key.toLowerCase();
  for (const [re, cat] of KEY_CATEGORY_RULES) {
    if (re.test(k)) return cat;
  }
  return 'Identity & travel';
}

// ── Status mapping ───────────────────────────────────────────────────────────
//
// The endpoint returns lowercase required|submitted|under_review|approved|rejected,
// all valid DocStatus values. Guard the cast so an unexpected value degrades to
// 'required' instead of poisoning the union.

function toDocStatus(status: string): DocStatus {
  switch (status) {
    case 'submitted':    return 'submitted';
    case 'under_review': return 'under_review';
    case 'approved':     return 'approved';
    case 'rejected':     return 'rejected';
    case 'expired':      return 'expired';
    case 'waived':       return 'waived';
    case 'required':
    default:             return 'required';
  }
}

// ── DTO mapper ───────────────────────────────────────────────────────────────

function toDocumentItem(d: CaseDocumentDTO): DocumentItem {
  return {
    id:                  d.key,            // document_key is the stable per-case identifier
    key:                 d.key,
    filename:            d.label,
    category:            keyToCategory(d.key),
    status:              toDocStatus(d.status),
    uploaded_at:         d.uploaded_at ?? null,
    file_url:            d.file_url ?? null,
    submission_deadline: null,            // not exposed by the documents endpoint
    expiry_date:         null,            // not exposed by the documents endpoint
    rejection_reason:    null,
    size_kb:             0,
  };
}

// ── Public API ───────────────────────────────────────────────────────────────

export const documentsAPI = {
  /**
   * List the case's full required-docs set.
   * GET /api/cases/{caseId}/documents → CaseDocumentDTO[] → DocumentItem[].
   */
  list: async (caseId: string): Promise<DocumentItem[]> => {
    const res = await api.get<CaseDocumentDTO[]>(`/api/cases/${caseId}/documents`);
    return (res.data ?? []).map(toDocumentItem);
  },

  /**
   * Upload a file against a specific required document.
   * POST /api/cases/{caseId}/documents — multipart { file, document_key, requirement_id? }.
   */
  upload: async (
    caseId: string,
    file: File,
    documentKey: string,
    requirementId?: string,
  ): Promise<void> => {
    const form = new FormData();
    form.append('file', file);
    form.append('document_key', documentKey);
    if (requirementId) form.append('requirement_id', requirementId);
    await api.post(`/api/cases/${caseId}/documents`, form, { timeout: 120_000 });
  },

  /** Delete / retract a document. */
  remove: async (caseId: string, documentId: string): Promise<void> => {
    await api.delete(`/api/cases/${caseId}/documents/${documentId}`);
  },
};
