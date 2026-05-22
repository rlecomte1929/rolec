/**
 * Documents API client.
 *
 * Backend status (May 2026): No dedicated /api/cases/{id}/documents endpoint exists yet.
 * We drive the document list from GET /api/cases/{id}/requirements, mapping
 * RequirementItemDTO → DocumentItem.  When the backend ships a real documents
 * endpoint, update `documentsAPI.list` to call it and remove the mapping helpers.
 */

import api from './client';
import type { CaseRequirementsDTO, RequirementItemDTO } from '../types';
import type { DocStatus } from '../types/relopass-api-contracts';
import type { DocumentItem, RequirementCategory } from '../features/platform-v2/documents/DocumentsScreen';

// ── Pillar → UI category ───────────────────────────────────────────────────────

const PILLAR_MAP: Record<string, RequirementCategory> = {
  IDENTITY:   'Identity & travel',
  TRAVEL:     'Identity & travel',
  PASSPORT:   'Identity & travel',
  VISA:       'Immigration & permits',
  PERMIT:     'Immigration & permits',
  IMMIGRATION:'Immigration & permits',
  TIMELINE:   'Immigration & permits',
  EMPLOYMENT: 'Employment',
  WORK:       'Employment',
  HOUSING:    'Housing & relocation',
  RELOCATION: 'Housing & relocation',
  FINANCIAL:  'Financial & tax',
  FINANCE:    'Financial & tax',
  TAX:        'Financial & tax',
  DEPENDENTS: 'Family & dependents',
  FAMILY:     'Family & dependents',
  SCHOOL:     'Family & dependents',
  CHILDREN:   'Family & dependents',
};

function mapPillarToCategory(pillar: string): RequirementCategory {
  const upper = (pillar ?? '').toUpperCase().trim();
  // Exact hit
  if (PILLAR_MAP[upper]) return PILLAR_MAP[upper];
  // Partial hit — pillar contains or is contained by a known key
  for (const key of Object.keys(PILLAR_MAP)) {
    if (upper.includes(key) || key.includes(upper)) {
      return PILLAR_MAP[key]!;
    }
  }
  // Fallback to most common bucket
  return 'Immigration & permits';
}

// ── Status mapping ─────────────────────────────────────────────────────────────
//
// The requirements endpoint returns MISSING | PROVIDED | NEEDS_REVIEW (uppercase).
// Map these to DocStatus values that DocumentsScreen understands.

function mapStatusToDocStatus(statusForCase: string): DocStatus {
  switch ((statusForCase ?? '').toUpperCase()) {
    case 'PROVIDED':     return 'submitted';
    case 'NEEDS_REVIEW': return 'under_review';
    case 'MISSING':
    default:             return 'required';
  }
}

// ── DTO mapper ─────────────────────────────────────────────────────────────────

export function requirementToDocumentItem(req: RequirementItemDTO): DocumentItem {
  return {
    id:                  req.id,
    filename:            req.title,
    category:            mapPillarToCategory(req.pillar),
    status:              mapStatusToDocStatus(req.statusForCase),
    uploaded_at:         null,   // not available from requirements endpoint
    submission_deadline: null,   // not available from requirements endpoint
    expiry_date:         null,   // not available from requirements endpoint
    rejection_reason:    null,
    size_kb:             0,
  };
}

// ── Public API ─────────────────────────────────────────────────────────────────

export const documentsAPI = {
  /**
   * List documents/requirements for a case.
   *
   * Currently reads from GET /api/cases/{caseId}/requirements and maps each
   * RequirementItemDTO to a DocumentItem.  Replace with a real documents
   * endpoint when the backend ships one.
   */
  list: async (caseId: string): Promise<DocumentItem[]> => {
    const res = await api.get<CaseRequirementsDTO>(`/api/cases/${caseId}/requirements`);
    return (res.data.requirements ?? []).map(requirementToDocumentItem);
  },

  /**
   * Upload a file for a given case + category.
   * Calls POST /api/cases/{caseId}/documents (not yet live — returns 404 until backend ships).
   * UploadZone will surface the error to the user automatically.
   */
  upload: async (
    caseId: string,
    file: File,
    category: RequirementCategory,
    requirementId?: string,
  ): Promise<void> => {
    const form = new FormData();
    form.append('file', file);
    form.append('case_id', caseId);
    form.append('category', category);
    form.append('run_ocr', 'true');
    if (requirementId) form.append('requirement_id', requirementId);
    await api.post(`/api/cases/${caseId}/documents`, form, { timeout: 120_000 });
  },

  /** Delete / retract a document. */
  remove: async (caseId: string, documentId: string): Promise<void> => {
    await api.delete(`/api/cases/${caseId}/documents/${documentId}`);
  },

  /**
   * Build a signed download URL (used for preview and download buttons).
   * The backend serves the file at this path; the URL may be a redirect to
   * Supabase Storage.
   */
  getDownloadUrl: (caseId: string, documentId: string): string =>
    `/api/cases/${caseId}/documents/${documentId}/download`,
};
