/**
 * Case document extraction — the HR read of what the extraction engine produced
 * (AIQ-1790).
 *
 * Talks to the rce-backed endpoints on /api/hr/cases/{caseId}/..., which are the
 * ones carrying real data. Deliberately separate from `immigrationDocuments.ts`:
 * that client reads `/api/immigration/cases/{id}/documents`, whose `ocr_status` /
 * `ocr_result` come from the MVP OCR queue — a different pipeline, gated on an
 * unset MISTRAL_API_KEY, so its status never advances past "pending". Merging the
 * two contracts into one client would hide that they are different sources.
 *
 * HR/admin only — the endpoints are behind require_admin_or_hr.
 */
import api from './client';

export interface ExtractionDocument {
  document_id: string;
  document_type_code: string;
  document_type_label: string | null;
  filename: string;
  uploaded_at: string;
  confidence_mean: number | null;
  /**
   * Prefer this over `confidence_mean` for a needs-review signal. MRZ fields are
   * deterministic at 1.000 while LLM-derived ones sit at 0.50–0.95, so the mean
   * drags a perfect read down and makes it look mediocre.
   */
  confidence_min: number | null;
  /**
   * Raw row count across ALL extraction runs — it OVER-COUNTS, because
   * re-processing appends rather than replaces (production reads 22 for a
   * 13-field document). Never label it "fields extracted"; use the deduplicated
   * `field_count` from `fields()` below when you need a number.
   */
  extracted_field_count: number | null;
  document_uri: string | null;
  page_count: number | null;
}

export interface ExtractedField {
  field_key: string;
  /** Already masked server-side when `masked` is true — never the raw value. */
  value: string | null;
  confidence: number | null;
  resolution_status: string | null;
  masked: boolean;
  page: number | null;
}

export interface ExtractedFields {
  document_id: string;
  document_type_code: string | null;
  /** Deduplicated — one entry per field_key. Trustworthy, unlike the list count. */
  field_count: number;
  fields: ExtractedField[];
}

export const caseExtractionAPI = {
  listDocuments: async (caseId: string): Promise<ExtractionDocument[]> => {
    const res = await api.get<{ documents: ExtractionDocument[] }>(
      `/api/hr/cases/${caseId}/documents`,
    );
    return res.data?.documents ?? [];
  },

  fields: async (caseId: string, documentId: string): Promise<ExtractedFields> => {
    const res = await api.get<ExtractedFields>(
      `/api/hr/cases/${caseId}/documents/${documentId}/fields`,
    );
    return res.data;
  },
};

export default caseExtractionAPI;
