/**
 * Immigration document upload + list API (BL-OCR.2/.4, AIQ-750).
 *
 * Talks to the case-scoped immigration document endpoints. The shared axios
 * instance (`api`) injects the auth token; FormData sets the multipart
 * Content-Type automatically.
 */
import api from './client';

export type ImmigrationOcrStatus = 'pending' | 'processing' | 'done' | 'failed';

export interface ImmigrationDocument {
  document_id: string;
  file_name: string;
  mime_type: string;
  file_size_bytes: number;
  ocr_status: ImmigrationOcrStatus;
  ocr_result: Record<string, unknown> | null;
  uploaded_by: string;
  uploaded_at: string | null;
}

/** Client-side mirror of the backend gate (immigration_documents bucket). */
export const IMMIGRATION_DOC_MAX_BYTES = 20 * 1024 * 1024; // 20 MiB
export const IMMIGRATION_DOC_ACCEPT = [
  'application/pdf',
  'image/png',
  'image/jpeg',
  'image/webp',
  'image/tiff',
];

export const immigrationDocumentsAPI = {
  upload: async (
    caseId: string,
    file: File,
    onProgress?: (pct: number) => void,
  ): Promise<{ document_id: string; ocr_status: string }> => {
    const form = new FormData();
    form.append('file', file);
    const res = await api.post<{ document_id: string; ocr_status: string }>(
      `/api/immigration/cases/${caseId}/documents`,
      form,
      {
        timeout: 120_000,
        onUploadProgress: (e) => {
          if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
        },
      },
    );
    return res.data;
  },

  list: async (caseId: string): Promise<ImmigrationDocument[]> => {
    const res = await api.get<{ documents: ImmigrationDocument[] }>(`/api/immigration/cases/${caseId}/documents`);
    return res.data?.documents ?? [];
  },
};
